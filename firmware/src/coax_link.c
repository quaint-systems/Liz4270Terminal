// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// The coax link on core 1: recv_term into a DMA ring, the terminal core, and
// its answers through xmit_serial.
//
// The PIO and DMA setup follows coax-tcp interface3's coax.c and tap.c (ISC;
// the notices are in firmware/vendor/coax-tcp/LICENSE, the record in NOTICE).

#include <stdatomic.h>

#include "pico/stdlib.h"
#include "hardware/clocks.h"
#include "hardware/dma.h"
#include "hardware/gpio.h"
#include "hardware/pio.h"

#include "board.h"
#include "coax.pio.h"
#include "coax_link.h"
#include "coax_term.pio.h"
#include "manchester.h"

#define END_OF_FRAME 0xFFFFFFFFu  // recv_term's marker, tested before narrowing a word

// recv_term's words land here by DMA. The DMA wraps its write address within
// the ring by itself, which needs a power-of-two size and matching alignment.
#define RING_WORDS 2048u
#define RING_BYTES (RING_WORDS * 4u)
#define RING_BITS 13u   // log2(RING_BYTES), for channel_config_set_ring
#define RING_SLACK 8u   // a backlog this close to the ring size counts as an overrun
static_assert((1u << RING_BITS) == RING_BYTES, "RING_BITS must match the ring size");

static volatile uint32_t ring[RING_WORDS] __attribute__((aligned(RING_BYTES)));

static term_t *term;
static term_config_t config;  // what the core was last powered on with
static _Atomic bool eab_now;  // config.eab, for core 0
static _Atomic uint8_t model_now;  // config.model, for core 0 (#110)
static bool offline;               // core 1's: every frame dropped unanswered (#110)
static _Atomic bool offline_now;   // offline, for core 0

static uint rx_sm;
static uint tx_sm;
static uint tx_delay_sm;
static uint rx_dma;

static volatile coax_link_stats_t stats;  // written by core 1 only
static_assert(sizeof(coax_link_stats_t) % sizeof(uint32_t) == 0, "the counters are 32-bit words");

// One request at a time from core 0: a reset, offline or online (#110). It
// stores the request, then publishes reset_seq; core 1 acts on it between
// frames and publishes the same number in reset_done.
typedef enum {
    REQUEST_RESET,
    REQUEST_OFFLINE,
    REQUEST_ONLINE,
} request_t;
static request_t request;
static coax_reset_t reset_request;  // a reset's EAB change
static uint8_t request_model;       // an online request's model
static _Atomic uint32_t reset_seq;
static _Atomic uint32_t reset_done;

static void serve_reset(void) {
    uint32_t seq = atomic_load_explicit(&reset_seq, memory_order_acquire);
    if (seq == atomic_load_explicit(&reset_done, memory_order_relaxed))
        return;
    if (request == REQUEST_OFFLINE) {
        offline = true;  // the core keeps its state; the next online request powers it on again
    } else {
        if (request == REQUEST_ONLINE)
            config.model = request_model;
        else if (reset_request == COAX_RESET_EAB)
            config.eab = true;
        else if (reset_request == COAX_RESET_BASE)
            config.eab = false;
        offline = false;
        term_init(term, &config);
    }
    atomic_store_explicit(&eab_now, config.eab, memory_order_relaxed);
    atomic_store_explicit(&model_now, config.model, memory_order_relaxed);
    atomic_store_explicit(&offline_now, offline, memory_order_relaxed);
    atomic_store_explicit(&reset_done, seq, memory_order_release);
}

static void init_receive(float div) {
    PIO pio = LIZ_COAX_RX_PIO;
    pio_set_gpio_base(pio, LIZ_COAX_PIO_GPIO_BASE);
    uint offset = pio_add_program(pio, &recv_term_program);
    rx_sm = (uint)pio_claim_unused_sm(pio, true);

    // As interface3 sets up its tap (tap.c), with recv_term for recv_tap.
    pio_sm_config c = recv_term_program_get_default_config(offset);
    sm_config_set_in_shift(&c, false, true, 10);  // shift left, autopush at 10 bits
    sm_config_set_fifo_join(&c, PIO_FIFO_JOIN_RX);
    sm_config_set_in_pins(&c, LIZ_COAX_RX_PIN);   // pin 2 of the group is TX_ACTIVE
    sm_config_set_jmp_pin(&c, LIZ_COAX_RX_PIN);
    sm_config_set_set_pins(&c, LIZ_COAX_RX_PIN, 0);  // the debug sets drive nothing
    sm_config_set_clkdiv(&c, div);
    pio_sm_set_consecutive_pindirs(pio, rx_sm, LIZ_COAX_RX_PIN, 1, false);
    pio_sm_init(pio, rx_sm, offset, &c);

    // Endless and wrapping in the ring: the loop reads behind the write address.
    rx_dma = (uint)dma_claim_unused_channel(true);
    dma_channel_config d = dma_channel_get_default_config(rx_dma);
    channel_config_set_transfer_data_size(&d, DMA_SIZE_32);
    channel_config_set_read_increment(&d, false);
    channel_config_set_write_increment(&d, true);
    channel_config_set_ring(&d, true, RING_BITS);
    channel_config_set_dreq(&d, pio_get_dreq(pio, rx_sm, false));
    dma_channel_configure(rx_dma, &d, ring, &pio->rxf[rx_sm], dma_encode_endless_transfer_count(), true);
}

static void init_transmit(float div) {
    PIO pio = LIZ_COAX_TX_PIO;
    pio_set_gpio_base(pio, LIZ_COAX_PIO_GPIO_BASE);
    uint offset = pio_add_program(pio, &xmit_serial_program);
    uint delay_offset = pio_add_program(pio, &xmit_serial_delay_program);
    tx_sm = (uint)pio_claim_unused_sm(pio, true);
    tx_delay_sm = (uint)pio_claim_unused_sm(pio, true);

    // interface3's coax.c settings for both programs.
    pio_sm_config c = xmit_serial_program_get_default_config(offset);
    sm_config_set_out_shift(&c, false, false, 32);  // shift left, no autopull
    sm_config_set_fifo_join(&c, PIO_FIFO_JOIN_TX);  // 8 entries
    sm_config_set_out_pins(&c, LIZ_COAX_TX_PIN, 1);
    sm_config_set_set_pins(&c, LIZ_COAX_TX_PIN, 2);  // TX and TX_ACTIVE
    sm_config_set_clkdiv(&c, div);
    pio_sm_init(pio, tx_sm, offset, &c);

    pio_sm_config d = xmit_serial_delay_program_get_default_config(delay_offset);
    sm_config_set_in_pins(&d, LIZ_COAX_TX_PIN);
    sm_config_set_set_pins(&d, LIZ_COAX_TX_DELAY_PIN, 1);
    sm_config_set_clkdiv(&d, div);
    pio_sm_init(pio, tx_delay_sm, delay_offset, &d);

    // Hand the pins over already driven low. coax_pins_safe holds them low
    // through SIO; giving them to the PIO before it drives them would float
    // TX_ACTIVE, which has no pull-down on the Liz 4174 (#25).
    uint64_t tx_pins = (1ull << LIZ_COAX_TX_PIN) | (1ull << LIZ_COAX_TX_ACTIVE_PIN);
    uint64_t delay_pin = 1ull << LIZ_COAX_TX_DELAY_PIN;
    pio_sm_set_pins_with_mask64(pio, tx_sm, 0, tx_pins);
    pio_sm_set_pindirs_with_mask64(pio, tx_sm, tx_pins, tx_pins);
    pio_sm_set_pins_with_mask64(pio, tx_delay_sm, 0, delay_pin);
    pio_sm_set_pindirs_with_mask64(pio, tx_delay_sm, delay_pin, delay_pin);
    pio_gpio_init(pio, LIZ_COAX_TX_PIN);
    pio_gpio_init(pio, LIZ_COAX_TX_ACTIVE_PIN);
    pio_gpio_init(pio, LIZ_COAX_TX_DELAY_PIN);
}

void coax_link_init(term_t *t, const term_config_t *cfg) {
    term = t;
    config = *cfg;
    term_init(term, &config);
    atomic_store(&eab_now, config.eab);
    atomic_store(&model_now, config.model);
    atomic_store(&offline_now, false);

    float div = (float)clock_get_hz(clk_sys) / COAX_PIO_FREQ;
    init_receive(div);
    init_transmit(div);

    pio_sm_set_enabled(LIZ_COAX_TX_PIO, tx_delay_sm, true);
    pio_sm_set_enabled(LIZ_COAX_TX_PIO, tx_sm, true);
    pio_sm_set_enabled(LIZ_COAX_RX_PIO, rx_sm, true);
}

static uint32_t ring_write_index(void) {
    uintptr_t next = (uintptr_t)dma_channel_hw_addr(rx_dma)->write_addr;
    return (uint32_t)((next - (uintptr_t)ring) / sizeof ring[0]) & (RING_WORDS - 1u);
}

static bool transmitter_idle(void) {
    return pio_sm_is_tx_fifo_empty(LIZ_COAX_TX_PIO, tx_sm) && !gpio_get(LIZ_COAX_TX_ACTIVE_PIN);
}

// Words encoded before the guard: every answer but a block read with "big"
// set. Encoding takes most of a microsecond a word, so more would delay the
// answer.
#define TX_EARLY_WORDS 4u

// Sends the core's answer once the guard has passed since the end marker
// seen at t_end. time_us_32 counts whole microseconds, so waiting for more
// than COAX_TURNAROUND_US ticks gives at least COAX_TURNAROUND_US us.
//
// The rest of a longer answer (up to 32 words) is encoded and fed as the
// FIFO drains, which is far quicker than the ~5 us a word takes to send.
// Every answer starts 4 us after its frame, except a long block read with
// "big" set: the core builds the whole answer first, so a 31-word one starts
// at 10 us (two-Pico rig, #29). oec never sets "big".
static void transmit(const uint16_t *answer, size_t count, uint32_t t_end) {
    size_t early = count < TX_EARLY_WORDS ? count : TX_EARLY_WORDS;
    uint32_t encoded[TX_EARLY_WORDS];
    for (size_t i = 0; i < early; i++)
        encoded[i] = coax_manchester_encode(answer[i]);

    while (time_us_32() - t_end <= COAX_TURNAROUND_US)
        tight_loop_contents();

    if (!transmitter_idle()) {
        stats.tx_busy++;
        return;
    }
    // xmit_serial takes the word count less one, then the words.
    pio_sm_put(LIZ_COAX_TX_PIO, tx_sm, (uint32_t)(count - 1u));
    for (size_t i = 0; i < early; i++)
        pio_sm_put(LIZ_COAX_TX_PIO, tx_sm, encoded[i]);

    uint32_t took = time_us_32() - t_end;
    stats.answers++;
    if (took > stats.turnaround_max_us)
        stats.turnaround_max_us = took;

    for (size_t i = early; i < count; i++)
        pio_sm_put_blocking(LIZ_COAX_TX_PIO, tx_sm, coax_manchester_encode(answer[i]));
}

void coax_link_run(void) {
    uint32_t read = 0;        // the next ring index to process
    bool discarding = false;  // after an overrun, until the next end marker
    bool in_frame = false;    // words since the last end marker

    for (;;) {
        uint32_t backlog = (ring_write_index() - read) & (RING_WORDS - 1u);
        if (backlog == 0u) {
            if (!in_frame)
                serve_reset();
            continue;
        }
        if (backlog > stats.backlog_max)
            stats.backlog_max = backlog;
        if (backlog >= RING_WORDS - RING_SLACK) {
            // The DMA may have lapped us: nothing up to the write index can
            // be trusted, and the frame in progress is broken. The core
            // drops it, and the words up to the next end marker don't reach it.
            stats.overruns++;
            read = ring_write_index();
            term_rx_abort(term);
            discarding = true;
            continue;
        }

        uint32_t word = ring[read];
        read = (read + 1u) & (RING_WORDS - 1u);

        if (word == END_OF_FRAME) {
            uint32_t t_end = time_us_32();
            stats.frames++;
            in_frame = false;
            if (discarding) {
                discarding = false;  // a broken frame gets no answer
                continue;
            }
            if (offline) {
                stats.silent++;  // off the coax (#110): the core never sees the frame
                continue;
            }
            uint16_t answer[TERM_TX_MAX];
            size_t count = term_rx_end(term, answer, TERM_TX_MAX);
            if (count == 0u)
                stats.silent++;
            else
                transmit(answer, count, t_end);
            continue;
        }

        stats.words++;
        in_frame = true;
        if (gpio_get(LIZ_COAX_TX_ACTIVE_PIN))
            stats.echoes++;  // recv_term's gate should make this impossible
        if (!discarding && !offline)
            term_rx_word(term, (uint16_t)(word & 0x3FFu));
    }
}

void coax_link_stats(coax_link_stats_t *out) {
    const volatile uint32_t *from = (const volatile uint32_t *)&stats;
    uint32_t *to = (uint32_t *)out;
    for (size_t i = 0; i < sizeof *out / sizeof(uint32_t); i++)
        to[i] = from[i];
}

bool coax_link_eab(void) {
    return atomic_load(&eab_now);
}

bool coax_link_reset_pending(void) {
    return atomic_load_explicit(&reset_done, memory_order_acquire) !=
           atomic_load_explicit(&reset_seq, memory_order_relaxed);
}

uint32_t coax_link_resets(void) {
    return atomic_load_explicit(&reset_done, memory_order_acquire);
}

static bool post(request_t kind, coax_reset_t reset, uint8_t model, uint32_t timeout_ms) {
    request = kind;
    reset_request = reset;
    request_model = model;
    uint32_t seq = atomic_load_explicit(&reset_seq, memory_order_relaxed) + 1u;
    atomic_store_explicit(&reset_seq, seq, memory_order_release);

    absolute_time_t deadline = make_timeout_time_ms(timeout_ms);
    while (atomic_load_explicit(&reset_done, memory_order_acquire) != seq) {
        if (time_reached(deadline))
            return false;
        tight_loop_contents();
    }
    return true;
}

bool coax_link_reset(coax_reset_t reset, uint32_t timeout_ms) {
    return post(REQUEST_RESET, reset, 0u, timeout_ms);
}

bool coax_link_go_offline(uint32_t timeout_ms) {
    return post(REQUEST_OFFLINE, COAX_RESET_KEEP, 0u, timeout_ms);
}

bool coax_link_go_online(uint8_t model, uint32_t timeout_ms) {
    return post(REQUEST_ONLINE, COAX_RESET_KEEP, model, timeout_ms);
}

uint8_t coax_link_model(void) {
    return atomic_load(&model_now);
}

bool coax_link_offline(void) {
    return atomic_load(&offline_now);
}
