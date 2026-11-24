// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// DVI on the Fruit Jam (#26): HSTX scan-out from a ring of 32 lines, which a
// lowest-priority IRQ on core 0 draws just ahead of the beam with render.c,
// or with splash.c from power-on until the controller draws (#53).
// Specs: docs/superpowers/specs/2026-10-04-fruit-jam-screen-design.md,
// "Video", and 2026-10-04-scan-out-dma-chain-design.md (#48).
//
// The scan-out runs itself. DMA channel D sends one block at a time to the
// HSTX FIFO, and channel C loads D from a fixed list of control blocks;
// every block chains D back to C. The list sends each active line's command
// list and then its pixels from the ring, then the whole vertical blank,
// then a block that points C back at the start. No CPU touches it, so no
// interrupt can make it send the wrong memory: the test card's ping-pong had
// under a microsecond to re-arm a channel after each pixel block (#48).
// Nothing from the video preempts PIO-USB either. D's pixel blocks raise
// DMA_IRQ_0, which is the renderer, at the lowest priority. Core 1, the coax
// link, never takes it.
//
// The DVI constants, the command lists and the HSTX setup in video_start
// are adapted from pico-examples
// hstx/dvi_out_hstx_encoder/dvi_out_hstx_encoder.c
// @ 7fe60d6b4027771e45d97f207532c41b1d8c5418, by way of tools/testcard,
// under this notice:
//
//   Copyright (c) 2024 Raspberry Pi (Trading) Ltd.
//   Copyright 2020 (c) 2020 Raspberry Pi (Trading) Ltd.
//
//   Redistribution and use in source and binary forms, with or without
//   modification, are permitted provided that the following conditions are
//   met:
//
//   1. Redistributions of source code must retain the above copyright notice,
//      this list of conditions and the following disclaimer.
//
//   2. Redistributions in binary form must reproduce the above copyright
//      notice, this list of conditions and the following disclaimer in the
//      documentation and/or other materials provided with the distribution.
//
//   3. Neither the name of the copyright holder nor the names of its
//      contributors may be used to endorse or promote products derived from
//      this software without specific prior written permission.
//
//   THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
//   IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
//   THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
//   PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
//   CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
//   EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
//   PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
//   PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
//   LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
//   NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
//   SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
//
// The chain of control blocks follows the design of pico-examples
// dma/control_blocks/control_blocks.c at the same commit: a control channel
// writes a data channel's registers, and the data channel chains back. No
// code is taken from it. The restart block is new.
//
// The rest of the file is Liz4270's own (ISC, LICENSE).

#include "pico/stdlib.h"
#include "pico/binary_info.h"
#include "hardware/clocks.h"
#include "hardware/dma.h"
#include "hardware/gpio.h"
#include "hardware/irq.h"
#include "hardware/pll.h"
#include "hardware/resets.h"
#include "hardware/sync.h"
#include "hardware/timer.h"
#include "hardware/structs/bus_ctrl.h"
#include "hardware/structs/hstx_ctrl.h"
#include "hardware/structs/hstx_fifo.h"
#include "hardware/structs/m33.h"

#include "board.h"
#include "board_detect.h"
#include "coax_link.h"
#include "render.h"
#include "setup.h"
#include "splash.h"
#include "version.h"
#include "video.h"

bi_decl(bi_1pin_with_name(LIZ_HPD_PIN, "HDMI hot-plug detect (rev A)"));

static bool has_hpd;  // revision A only (#97)

typedef struct {
    const char *name;
    uint32_t vco_hz;  // pll_usb's VCO; clk_hstx = vco_hz / (pd1 * pd2), five times the pixel clock
    uint8_t pd1, pd2;
    uint16_t h_front, h_sync, h_back, h_active;
    uint16_t v_front, v_sync, v_back, v_active;
    const render_layout_t *layout;
} timing_t;

// From tools/testcard. Both modes' sync pulses are negative.
static const timing_t timings[] = {
    [VIDEO_640X480] = {"640x480", 1512000000u, 6, 2, 16, 96, 48, 640, 10, 2, 33, 480, &render_640x480},
    [VIDEO_720X480] = {"720x480", 1080000000u, 4, 2, 16, 62, 60, 720, 9, 6, 30, 480, &render_720x480},
};

#define TMDS_CTRL_00 0x354u
#define TMDS_CTRL_01 0x0abu
#define TMDS_CTRL_10 0x154u
#define TMDS_CTRL_11 0x2abu

#define HSTX_CMD_RAW_REPEAT (0x1u << 12)
#define HSTX_CMD_TMDS       (0x2u << 12)

#define HSTX_FIRST_PIN 12u  // HSTX output bit n is GPIO 12 + n
#define HSTX_LAST_PIN 19u

#define RING_LINES 32u
// Active lines are counted continuously across frames, modulo LINE_WRAP. It's
// a multiple of 480 and of 32, so a count gives the frame's line (n % 480)
// and its ring slot (n % 32) the same way across the wrap, and its frame
// (n / 480) wraps at 64, EAB blink's cycle (render.h, #70).
#define LINE_WRAP (RENDER_LINES * RENDER_FRAME_CYCLE)
_Static_assert(LINE_WRAP % RING_LINES == 0u, "a count gives its ring slot the same way across the wrap");
_Static_assert((LINE_WRAP / RENDER_LINES) % RENDER_FRAME_CYCLE == 0u,
               "frames (n / 480) wrap only at a multiple of EAB blink's cycle (render.h, #70)");
// The chain moves about 58 blocks a millisecond, so C's read address standing
// still this long, across polls that come often, means it has stopped. It
// rests longest on the vertical blank's block, about 1.4 ms, and comes round
// to the same block every frame, so two polls further apart than POLL_GAP_US
// (the main loop held up) can match on a healthy chain: such a gap counts as
// a move. POLL_GAP_US is well over the 1.4 ms rest and under a frame.
#define STALL_US 100000u
#define POLL_GAP_US 10000u
#define NO_FRAME UINT32_MAX  // frame_begun before the first line is drawn

// The vertical blank: front porch, sync and back porch, 45 lines in both
// modes (build_command_lists checks), six words a line.
#define VBLANK_LINES 45u
#define VBLANK_LINE_WORDS 6u

// The list: line y's command list is block 2y and its pixels 2y + 1, then
// come the vertical blank and the restart.
#define BLOCK_VBLANK (2u * RENDER_LINES)
#define BLOCK_RESTART (BLOCK_VBLANK + 1u)
#define BLOCKS (BLOCK_RESTART + 1u)

// One control block: D's alias-0 registers in order. C copies it into D, and
// its last word, CTRL_TRIG, starts D.
typedef struct {
    uint32_t read_addr, write_addr, transfer_count, ctrl;
} dma_block_t;

static uint32_t ring[RING_LINES][RENDER_MAX_WIDTH / 2u];
static uint32_t vactive_line[7];
static uint32_t vblank_lines[VBLANK_LINES * VBLANK_LINE_WORDS];

// Written only by build_list, while the chain is stopped. Every block holds a
// WRITE_ADDR, so a stray write here could make D write anywhere; nothing else
// writes the list, and nothing in the firmware allocates.
static dma_block_t blocks[BLOCKS];
static uint32_t list_start;  // &blocks[0], which the restart block copies into C's READ_ADDR

static const term_t *term;
static video_mode_t mode_now;
static uint dma_data, dma_ctrl;  // D and C
static uint32_t h_words;         // a line's pixels, two RGB565 pixels a word

// render_irq_handler's own, reset by video_start with the IRQ off.
static render_t renderer;
static uint32_t frame_base;   // the line count of the current frame's line 0
static uint32_t last_p;       // beam_lines when last read
static uint32_t drawn;        // the next line to draw
static uint32_t frame_begun;  // the frame (line count / 480) render_frame_begin last ran for
static uint32_t line_cycles_max, frame_cycles_max;
static uint64_t line_cycles_sum, lines_timed;

// Set once by video_init, then the render IRQ's own (but for
// video_splash_dismiss). video_start leaves them, so a mode change or a
// restart keeps the splash's place.
static splash_t splash;
static bool splash_on;  // decided as each frame begins, so a frame is all splash or all screen
static uint16_t splash_ink;  // splash_colour (#50), decided with splash_on

// Written by the render IRQ, read by the main loop.
static volatile uint32_t frames, late;
static volatile uint32_t begun;  // frames begun, for SetUp's double buffer (#102)
// Alarm volume Off's flash (#107): set by video_flash in core 0's loop, read
// as each frame begins. The flag keeps an old end from looking like the
// future once the clock has run 2^31 ms past it.
static volatile bool flash_set;
static volatile uint32_t flash_end;  // to_ms_since_boot when it ends

// video_poll's own.
static uint32_t fps, frames_at_second, restarts;
static uint64_t second_start_us, last_move_us, last_poll_us;
static uint32_t last_position;             // C's read address when video_poll last saw it move
static const char *last_restart = "none";  // the cause: "stall" or "error"

// v's times start afresh: at each (re)start, and as the splash ends, so that
// they time splash.c while it shows and render.c alone after it.
static void timing_reset(void) {
    line_cycles_max = 0;
    frame_cycles_max = 0;
    line_cycles_sum = 0;
    lines_timed = 0;
}

// How far line count a is past b.
static inline uint32_t line_ahead(uint32_t a, uint32_t b) {
    return (a + LINE_WRAP - b) % LINE_WRAP;
}

// How many of this frame's 480 lines D has started, by command list or
// pixels: 0 just after the restart, y + 1 on line y, 480 through the
// vertical blank. C's read address is in block i, the next block C loads
// or the one it is loading, so D is on block i - 1.
static uint32_t beam_lines(void) {
    uint32_t i = (dma_hw->ch[dma_ctrl].read_addr - (uint32_t)(uintptr_t)blocks) / sizeof(dma_block_t);
    uint32_t p = (i + 1u) / 2u;
    return p < RENDER_LINES ? p : RENDER_LINES;
}

// The line count of the next line D starts: line armed - 1 is being sent. A
// drop in beam_lines means a frame has begun since the last call. Missing a
// whole frame leaves the count a frame behind, which still gives every line
// its own slot (480 is a multiple of 32).
static uint32_t beam_armed(void) {
    uint32_t p = beam_lines();
    if (p < last_p) {
        frame_base = (frame_base + RENDER_LINES) % LINE_WRAP;
        frames++;
    }
    last_p = p;
    return (frame_base + p) % LINE_WRAP;
}

// DMA_IRQ_0, which D's pixel blocks raise: draws lines into the ring up to 31
// past the one being sent, whose slot it never touches. Everything else on
// core 0 preempts it.
static void render_irq_handler(void) {
    dma_hw->ints0 = 1u << dma_data;
    for (;;) {
        uint32_t a = beam_armed(), n = drawn;
        uint32_t ahead = line_ahead(n, a);
        if (ahead > LINE_WRAP / 2u) {
            // Behind the beam: lines n to a - 1 went out undrawn, and line a
            // will too. Jump to two lines past the one being sent, at least a
            // line time before D starts it.
            late += line_ahead(a, n) + 1u;
            n = (a + 1u) % LINE_WRAP;
        } else if (ahead >= RING_LINES - 1u) {
            return;  // the ring is full
        }

        // A frame begins at the first of its lines drawn: line 0, or where a
        // catch-up lands. A catch-up within the frame keeps it, and costs a
        // row build and a line. render_frame_begin can take longer than the
        // jump allows (v's frame_us_max), so running it on every catch-up
        // could fall behind each time and never return.
        uint y = n % RENDER_LINES;
        uint32_t frame = n / RENDER_LINES;
        if (frame != frame_begun) {
            uint32_t start = m33_hw->dwt_cyccnt;
            bool was_splash = splash_on;
            bool local = setup_showing();  // SetUp's image in place of the host's (#102)
            uint32_t now = to_ms_since_boot(get_absolute_time());
            splash_on = !local && splash_showing(&splash, now, term_written(term));
            bool flash = flash_set && (int32_t)(now - flash_end) < 0;
            if (flash_set && !flash)
                flash_set = false;
            if (splash_on) {
                // The first line drawn always begins a frame (NO_FRAME), so
                // the first splash frame after power-on has its colour too.
                splash_ink = splash_colour(setup_settings());
            } else {
                const lock_line_t *line = setup_lock_line();  // the lock's (#122), copied as the frame begins
                render_frame_t in = {
                    .regen = local ? setup_regen() : term_regen(term),
                    .eab = local ? setup_eab() : term_eab(term),
                    .ac = term_ac(term),
                    .control = term_control(term),
                    .settings = setup_settings(),
                    .frame = frame,
                    .dimmed = setup_dimmed(),
                    .ruler = setup_ruler(),
                    .setup = local,
                    .flash = flash,
                    .model = coax_link_model(),  // what the controller was told (#110)
                    .setup_cursor = local ? setup_cursor() : 0u,  // Password Set's (#122)
                    .locked = !local && setup_locked(),
                    .status = line->codes,
                    .status_cursor = line->cursor,
                    .status_bar = line->bar,
                };
                render_frame_begin(&renderer, timings[mode_now].layout, &in);
            }
            uint32_t took = m33_hw->dwt_cyccnt - start;
            if (was_splash && !splash_on)
                timing_reset();
            if (took > frame_cycles_max)
                frame_cycles_max = took;
            frame_begun = frame;
            begun++;
        }
        uint32_t start = m33_hw->dwt_cyccnt;
        if (splash_on)
            splash_line(&splash, timings[mode_now].layout, y, splash_ink, ring[n % RING_LINES]);
        else
            render_line(&renderer, y, ring[n % RING_LINES]);
        uint32_t took = m33_hw->dwt_cyccnt - start;
        if (took > line_cycles_max)
            line_cycles_max = took;
        line_cycles_sum += took;
        lines_timed++;
        drawn = (n + 1u) % LINE_WRAP;

        // D started line n before it was drawn, so part of its slot went out
        // old. (Counted from its command list, which D starts less than a
        // microsecond before it reads the slot's first words.)
        uint32_t past = line_ahead(beam_armed(), n);
        if (past != 0u && past <= LINE_WRAP / 2u)
            late++;
    }
}

// The control symbols on lane 0 carry HSYNC (C0) and VSYNC (C1); the other
// lanes send 00. Both modes' pulses are negative: low while active.
static uint32_t sync_word(bool vsync, bool hsync) {
    static const uint32_t ctrl[4] = {TMDS_CTRL_00, TMDS_CTRL_01, TMDS_CTRL_10, TMDS_CTRL_11};
    uint v = !vsync, h = !hsync;
    return ctrl[v << 1 | h] | TMDS_CTRL_00 << 10 | TMDS_CTRL_00 << 20;
}

static void build_command_lists(const timing_t *m) {
    hard_assert((uint)m->v_active == RENDER_LINES);  // the list holds a block pair for each of 480 lines
    uint32_t *l = vactive_line;
    *l++ = HSTX_CMD_RAW_REPEAT | m->h_front;
    *l++ = sync_word(false, false);
    *l++ = HSTX_CMD_RAW_REPEAT | m->h_sync;
    *l++ = sync_word(false, true);
    *l++ = HSTX_CMD_RAW_REPEAT | m->h_back;
    *l++ = sync_word(false, false);
    *l++ = HSTX_CMD_TMDS | m->h_active;

    uint sync_start = m->v_front, sync_end = sync_start + m->v_sync;
    hard_assert(sync_end + m->v_back == VBLANK_LINES);
    l = vblank_lines;
    for (uint line = 0; line < VBLANK_LINES; line++) {
        bool vsync = line >= sync_start && line < sync_end;
        *l++ = HSTX_CMD_RAW_REPEAT | m->h_front;
        *l++ = sync_word(vsync, false);
        *l++ = HSTX_CMD_RAW_REPEAT | m->h_sync;
        *l++ = sync_word(vsync, true);
        *l++ = HSTX_CMD_RAW_REPEAT | (m->h_back + m->h_active);
        *l++ = sync_word(vsync, false);
    }

    h_words = m->h_active / 2u;
}

// The list for the mode. D's CTRL is the same in every block that feeds the
// FIFO but for the IRQ, which only the pixel blocks raise; every block, the
// restart too, chains D to C.
static void build_list(void) {
    dma_channel_config c = dma_channel_get_default_config(dma_data);
    channel_config_set_dreq(&c, DREQ_HSTX);
    channel_config_set_chain_to(&c, dma_ctrl);
    channel_config_set_irq_quiet(&c, true);
    uint32_t quiet = channel_config_get_ctrl_value(&c);
    channel_config_set_irq_quiet(&c, false);
    uint32_t loud = channel_config_get_ctrl_value(&c);
    // The restart writes a DMA register, not the FIFO, so it runs unpaced and
    // spends none of HSTX's DREQ credits on a word the FIFO never gets.
    channel_config_set_irq_quiet(&c, true);
    channel_config_set_dreq(&c, DREQ_FORCE);
    uint32_t unpaced = channel_config_get_ctrl_value(&c);

    uint32_t fifo = (uint32_t)(uintptr_t)&hstx_fifo_hw->fifo;
    for (uint y = 0; y < RENDER_LINES; y++) {
        blocks[2u * y] = (dma_block_t){(uint32_t)(uintptr_t)vactive_line, fifo, count_of(vactive_line), quiet};
        blocks[2u * y + 1u] = (dma_block_t){(uint32_t)(uintptr_t)ring[y % RING_LINES], fifo, h_words, loud};
    }
    blocks[BLOCK_VBLANK] = (dma_block_t){(uint32_t)(uintptr_t)vblank_lines, fifo, count_of(vblank_lines), quiet};
    // The restart: one word, the list's address, into C's READ_ADDR. D's
    // chain then starts C on block 0.
    list_start = (uint32_t)(uintptr_t)blocks;
    blocks[BLOCK_RESTART] = (dma_block_t){(uint32_t)(uintptr_t)&list_start,
                                          (uint32_t)(uintptr_t)&dma_hw->ch[dma_ctrl].read_addr, 1u, unpaced};
}

// pll_usb is free: clocks.c moved clk_usb and clk_adc onto pll_sys.
static void retime(const timing_t *m) {
    clock_stop(clk_hstx);
    pll_init(pll_usb, 1, m->vco_hz, m->pd1, m->pd2);
    clock_configure_undivided(clk_hstx, 0, CLOCKS_CLK_HSTX_CTRL_AUXSRC_VALUE_CLKSRC_PLL_USB,
                              m->vco_hz / (m->pd1 * m->pd2));
}

static void video_start(video_mode_t mode) {
    const timing_t *m = &timings[mode];
    mode_now = mode;
    retime(m);
    build_command_lists(m);
    build_list();

    // DMA_IRQ_0 is off here (not yet enabled, or video_stop). C starts on the
    // vertical blank, where beam_lines is 480, so line count 0 is line 0.
    frame_base = LINE_WRAP - RENDER_LINES;
    last_p = RENDER_LINES;
    drawn = 0;
    frame_begun = NO_FRAME;  // so the first line drawn begins a frame
    timing_reset();

    // Fruit Jam: CK on 13/12, D0 on 15/14, D1 on 17/16, D2 on 19/18 (P/N);
    // the N pin is the inverted copy.
    hstx_ctrl_hw->bit[ADAFRUIT_FRUIT_JAM_DVI_CKP_PIN - HSTX_FIRST_PIN] = HSTX_CTRL_BIT0_CLK_BITS;
    hstx_ctrl_hw->bit[ADAFRUIT_FRUIT_JAM_DVI_CKN_PIN - HSTX_FIRST_PIN] = HSTX_CTRL_BIT0_CLK_BITS | HSTX_CTRL_BIT0_INV_BITS;
    static const uint lane_p[3] = {ADAFRUIT_FRUIT_JAM_DVI_D0P_PIN, ADAFRUIT_FRUIT_JAM_DVI_D1P_PIN,
                                   ADAFRUIT_FRUIT_JAM_DVI_D2P_PIN};
    static const uint lane_n[3] = {ADAFRUIT_FRUIT_JAM_DVI_D0N_PIN, ADAFRUIT_FRUIT_JAM_DVI_D1N_PIN,
                                   ADAFRUIT_FRUIT_JAM_DVI_D2N_PIN};
    for (uint lane = 0; lane < 3; lane++) {
        uint32_t sel = (lane * 10) << HSTX_CTRL_BIT0_SEL_P_LSB | (lane * 10 + 1) << HSTX_CTRL_BIT0_SEL_N_LSB;
        hstx_ctrl_hw->bit[lane_p[lane] - HSTX_FIRST_PIN] = sel;
        hstx_ctrl_hw->bit[lane_n[lane] - HSTX_FIRST_PIN] = sel | HSTX_CTRL_BIT0_INV_BITS;
    }
    // TMDS from RGB565, two pixels a word: red is bits 15-11 (lane 2), green
    // 10-5 (lane 1) and blue 4-0 (lane 0), each rotated to bit 7.
    hstx_ctrl_hw->expand_tmds =
        4 << HSTX_CTRL_EXPAND_TMDS_L2_NBITS_LSB | 8 << HSTX_CTRL_EXPAND_TMDS_L2_ROT_LSB |
        5 << HSTX_CTRL_EXPAND_TMDS_L1_NBITS_LSB | 3 << HSTX_CTRL_EXPAND_TMDS_L1_ROT_LSB |
        4 << HSTX_CTRL_EXPAND_TMDS_L0_NBITS_LSB | 29 << HSTX_CTRL_EXPAND_TMDS_L0_ROT_LSB;
    hstx_ctrl_hw->expand_shift =
        2 << HSTX_CTRL_EXPAND_SHIFT_ENC_N_SHIFTS_LSB | 16 << HSTX_CTRL_EXPAND_SHIFT_ENC_SHIFT_LSB |
        1 << HSTX_CTRL_EXPAND_SHIFT_RAW_N_SHIFTS_LSB | 0 << HSTX_CTRL_EXPAND_SHIFT_RAW_SHIFT_LSB;
    // Clock period of 5 HSTX cycles, a pop every 5, two bits shifted per cycle.
    hstx_ctrl_hw->csr = 0;
    hstx_ctrl_hw->csr = HSTX_CTRL_CSR_EXPAND_EN_BITS | 5u << HSTX_CTRL_CSR_CLKDIV_LSB |
                        5u << HSTX_CTRL_CSR_N_SHIFTS_LSB | 2u << HSTX_CTRL_CSR_SHIFT_LSB | HSTX_CTRL_CSR_EN_BITS;

    // C copies one block into D's alias-0 registers each time D finishes:
    // four words, unpaced, through a 16-byte write ring. It starts on the
    // vertical blank, which gives the renderer 1.4 ms to fill the ring.
    dma_channel_config c = dma_channel_get_default_config(dma_ctrl);
    channel_config_set_write_increment(&c, true);
    channel_config_set_ring(&c, true, 4);
    channel_config_set_irq_quiet(&c, true);
    dma_channel_configure(dma_ctrl, &c, &dma_hw->ch[dma_data].read_addr, &blocks[BLOCK_VBLANK],
                          sizeof(dma_block_t) / sizeof(uint32_t), false);
    dma_channel_acknowledge_irq0(dma_data);
    dma_channel_set_irq0_enabled(dma_data, true);
    irq_set_enabled(DMA_IRQ_0, true);
    dma_channel_start(dma_ctrl);
    irq_set_pending(DMA_IRQ_0);  // fill the ring now
}

// A bus error's flags stay set until written with ones.
static void clear_dma_errors(uint ch) {
    io_rw_32 *ctrl = &dma_hw->ch[ch].al1_ctrl;
    *ctrl = *ctrl | DMA_CH0_CTRL_TRIG_READ_ERROR_BITS | DMA_CH0_CTRL_TRIG_WRITE_ERROR_BITS;
}

static void video_stop(void) {
    irq_set_enabled(DMA_IRQ_0, false);  // video_start resets what the renderer reads
    // C first, so a paused C can't start D again with a CTRL_TRIG write. Then
    // abort both, which neither can now trigger.
    hw_clear_bits(&dma_hw->ch[dma_ctrl].al1_ctrl, DMA_CH0_CTRL_TRIG_EN_BITS);
    hw_clear_bits(&dma_hw->ch[dma_data].al1_ctrl, DMA_CH0_CTRL_TRIG_EN_BITS);
    uint32_t mask = 1u << dma_ctrl | 1u << dma_data;
    dma_hw->abort = mask;
    while (dma_hw->abort & mask)
        tight_loop_contents();
    clear_dma_errors(dma_ctrl);
    clear_dma_errors(dma_data);
    dma_channel_set_irq0_enabled(dma_data, false);
    dma_hw->intr = 1u << dma_data;
    hstx_ctrl_hw->csr = 0;
    // The aborted DMA leaves up to 8 words, cut from an arbitrary point, in
    // the HSTX FIFO, and the expander mid-TMDS; with EN low the FIFO is not
    // popped, so nothing else clears them. Restarting would pop them first, as
    // pixels or as commands. A block reset empties both (and the bit[] pin
    // map, which video_start sets again). clk_hstx still runs here, as the
    // reset needs.
    reset_block_num(RESET_HSTX);
    unreset_block_num_wait_blocking(RESET_HSTX);
}

// The rate window and the stall check start afresh after a (re)start.
static void restart_window(uint64_t now) {
    second_start_us = last_move_us = last_poll_us = now;
    frames_at_second = frames;
    last_position = dma_hw->ch[dma_ctrl].read_addr;
}

void video_init(const term_t *t, video_mode_t mode) {
    term = t;
    // HPD comes in through 220 Ohm, with 4.7 kOhm to ground. The pad keeps
    // its pull-down, so a bare pin reads low on a Fruit Jam standing in for
    // revision A (#97), and its input buffer is off but for read_hpd.
    has_hpd = board_has_hpd(board_detected().board);
    if (has_hpd) {
        gpio_init(LIZ_HPD_PIN);
        gpio_pull_down(LIZ_HPD_PIN);
        gpio_set_input_enabled(LIZ_HPD_PIN, false);
    }
    dma_data = (uint)dma_claim_unused_channel(true);
    dma_ctrl = (uint)dma_claim_unused_channel(true);

    irq_set_exclusive_handler(DMA_IRQ_0, render_irq_handler);
    irq_set_priority(DMA_IRQ_0, PICO_LOWEST_IRQ_PRIORITY);  // video_start enables it

    for (uint pin = HSTX_FIRST_PIN; pin <= HSTX_LAST_PIN; pin++)
        gpio_set_function(pin, GPIO_FUNC_HSTX);

    bus_ctrl_hw->priority = BUSCTRL_BUS_PRIORITY_DMA_W_BITS | BUSCTRL_BUS_PRIORITY_DMA_R_BITS;

    // The cycle counter times each line, for the console's v.
    m33_hw->demcr |= M33_DEMCR_TRCENA_BITS;
    m33_hw->dwt_ctrl |= M33_DWT_CTRL_CYCCNTENA_BITS;

    splash_init(&splash, liz_version, liz_commit, to_ms_since_boot(get_absolute_time()));
    splash_on = true;

    video_start(mode);
    restart_window(time_us_64());
}

void video_splash_dismiss(void) {
    splash_dismiss(&splash);
}

uint32_t video_frames_begun(void) {
    return begun;
}

void video_flash(uint32_t ms) {
    flash_end = to_ms_since_boot(get_absolute_time()) + ms;
    flash_set = true;
}

void video_set_mode(video_mode_t mode) {
    if (mode == mode_now)
        return;
    video_stop();
    video_start(mode);
    restart_window(time_us_64());
}

void video_poll(void) {
    uint64_t now = time_us_64();

    uint64_t window_us = now - second_start_us;
    if (window_us >= 1000000u) {
        // Frames a second over the whole window, which runs longer than a
        // second if the loop was held up.
        uint32_t f = frames;
        fps = (uint32_t)(((uint64_t)(f - frames_at_second) * 1000000u + window_us / 2u) / window_us);
        frames_at_second = f;
        second_start_us = now;
    }

    uint32_t position = dma_hw->ch[dma_ctrl].read_addr;
    if (position != last_position || now - last_poll_us > POLL_GAP_US) {
        last_position = position;
        last_move_us = now;
    } else if (now - last_move_us > STALL_US) {
        uint32_t ctrl = dma_hw->ch[dma_ctrl].al1_ctrl | dma_hw->ch[dma_data].al1_ctrl;
        restarts++;
        last_restart = ctrl & DMA_CH0_CTRL_TRIG_AHB_ERROR_BITS ? "error" : "stall";
        video_stop();
        video_start(mode_now);
        restart_window(now);
    }
    last_poll_us = now;
}

void video_hold(uint32_t ms) {
    irq_set_enabled(DMA_IRQ_0, false);
    busy_wait_us((uint64_t)ms * 1000u);
    irq_set_enabled(DMA_IRQ_0, true);
    irq_set_pending(DMA_IRQ_0);  // D's interrupt is raised by now anyway
}

void video_stall(void) {
    // C ignores D's chain once its EN is clear: D finishes its block, and the
    // chain stops there.
    hw_clear_bits(&dma_hw->ch[dma_ctrl].al1_ctrl, DMA_CH0_CTRL_TRIG_EN_BITS);
}

// RP2350-E9: a pad with its input buffer on can hold itself near 2 V once
// driven high and let go, which the pad's own pull-down can't overcome.
// Revision A's 4.7 kOhm can, but a Fruit Jam standing in for it has only the
// pull-down on D7, so the buffer is on only while the pin is read.
static bool read_hpd(void) {
    gpio_set_input_enabled(LIZ_HPD_PIN, true);
    busy_wait_us(1);  // for the pad write to land and the input's synchroniser to follow
    bool high = gpio_get(LIZ_HPD_PIN);
    gpio_set_input_enabled(LIZ_HPD_PIN, false);
    return high;
}

void video_stats(video_stats_t *out) {
    uint32_t save = save_and_disable_interrupts();
    uint32_t max = line_cycles_max, frame_max = frame_cycles_max;
    uint64_t sum = line_cycles_sum, count = lines_timed;
    restore_interrupts(save);

    out->mode = timings[mode_now].name;
    out->clk_hstx_khz = frequency_count_khz(CLOCKS_FC0_SRC_VALUE_CLK_HSTX);
    out->fps = fps;
    out->line_cycles_max = max;
    out->line_cycles_avg = count ? (uint32_t)(sum / count) : 0u;
    out->frame_cycles_max = frame_max;
    out->late = late;
    out->restarts = restarts;
    out->last_restart = last_restart;
    out->has_hpd = has_hpd;
    out->hpd = has_hpd && read_hpd();
}
