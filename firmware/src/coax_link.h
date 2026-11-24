// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// The coax link: recv_term's words into the terminal core, and its answers
// out through xmit_serial. Core 1 runs coax_link_run; core 0 reads the
// counters and queues keys with term_key.

#ifndef LIZ_COAX_LINK_H
#define LIZ_COAX_LINK_H

#include <stdbool.h>
#include <stdint.h>

#include "term.h"

// The coax programs run at 12 PIO cycles per bit. Same value as PIO_FREQ in
// coax-tcp interface3/firmware/coax.h.
#define COAX_BIT_RATE 2358700
#define COAX_PIO_FREQ (12 * COAX_BIT_RATE)

// The least time from recv_term's end marker to the answer, in microseconds.
// The controller drives the rest of its end bit and a 2-bit tail for about
// 1.1 us after the marker. The 3483-V's gap on the line is the same, about
// 3 us (#8).
#define COAX_TURNAROUND_US 3u

// Since power-on. Core 1 writes them; core 0 reads a copy.
typedef struct {
    uint32_t frames;             // end markers
    uint32_t words;              // other words
    uint32_t answers;            // frames answered
    uint32_t silent;             // frames the core left unanswered
    uint32_t echoes;             // words received while our TX_ACTIVE was high
    uint32_t backlog_max;        // most words waiting in the ring at one look
    uint32_t overruns;           // looks that found the ring nearly full
    uint32_t tx_busy;            // answers dropped: the transmitter was busy
    // The longest from the loop reading an end marker to the answer pushed,
    // in whole microsecond ticks. The guard alone makes it
    // COAX_TURNAROUND_US + 1, so more means something held an answer up.
    // Time the marker spent waiting in the ring isn't counted. For the time
    // on the wire, see docs/upstream-review.md, "Timing".
    uint32_t turnaround_max_us;
} coax_link_stats_t;

// Core 0, before core 1 starts: power on the core with cfg (at its model,
// #110), and set up the PIO programs and the receive DMA.
void coax_link_init(term_t *t, const term_config_t *cfg);

// Core 1's entry point. Never returns.
void coax_link_run(void);

// Core 0: a copy of the counters.
void coax_link_stats(coax_link_stats_t *out);

// The EAB setting the core was last powered on with.
bool coax_link_eab(void);

typedef enum {
    COAX_RESET_KEEP,  // keep the EAB setting
    COAX_RESET_EAB,   // answer the feature probe as the 3483-V does
    COAX_RESET_BASE,  // no features
} coax_reset_t;

// Core 0: a power-on reset of the core, which core 1 applies between frames.
// False if core 1 hadn't done it within timeout_ms (it still will, when the
// frame in progress ends).
bool coax_link_reset(coax_reset_t reset, uint32_t timeout_ms);

// Core 0: whether a reset that timed out is still to happen. Until it has,
// queue no keys (term_init would race term_key) and post no other reset.
bool coax_link_reset_pending(void);

// Core 0: how many resets core 1 has applied since power-on (it wraps), so a
// caller can tell that one wiped the status queue.
uint32_t coax_link_resets(void);

// Model changes (#110), through the same handshake as a reset: core 1 acts
// on each between frames. Offline, it drops every frame unanswered, so the
// controller loses the terminal; online, it powers the core on at model and
// answers again, so the controller finds it afresh and reads its new ID.
// False if core 1 hadn't done it within timeout_ms: it still will, and
// coax_link_reset_pending says so until it has.
bool coax_link_go_offline(uint32_t timeout_ms);
bool coax_link_go_online(uint8_t model, uint32_t timeout_ms);

// What core 1 is doing (#110): the model the core was last powered on as,
// and whether the link is offline.
uint8_t coax_link_model(void);
bool coax_link_offline(void);

#endif
