// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// Liz4270 terminal core: an IBM 3483-V in CUT mode, as the controller sees
// it on the coax.
//
// Plain C11 with no Pico headers, no malloc and no stdio, so the firmware and
// the host simulator (tools/sim) run the same code. The firmware feeds it each
// word recv_tap decodes and transmits what term_rx_end returns; the simulator
// does the same for each frame oec sends. The contract is
// docs/upstream-review.md, "Terminal-side contract".

#ifndef LIZ_TERM_H
#define LIZ_TERM_H

#include <stdatomic.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "regen.h"

#define TERM_TX_MAX 32u         // the longest answer, a block read with "big" set
#define TERM_STATUS_SLOTS 32u   // status queue; a power of two

typedef struct {
    bool eab;       // answer the feature probe as the 3483-V does: EAB at 7
    uint8_t model;  // the model to answer as (#110): 3 or 4, anything else Model 2
} term_config_t;

// Defined here so the caller can allocate it (the firmware, statically).
// The fields are private to term.c.
typedef struct term {
    term_config_t cfg;
    regen_t regen;
    uint8_t control;
    uint8_t secondary;
    uint8_t eab_mask;  // stored; it doesn't govern EAB_WRITE_ALTERNATE (#29)

    // Status queue: power-on reset, then keystrokes, each answered to every
    // POLL until a POLL_ACK, with bit 0 set while the feature error is. POLL_ACK
    // takes the head unless the last POLL found the queue empty. term_key is
    // the only writer of status_tail and POLL_ACK the only writer of
    // status_head; both counters run free and wrap at 256. Each side
    // publishes its counter with release ordering and reads the other's with
    // acquire, so term_key may run on the other core (the firmware's console
    // does). term_init writes both counters, so it must not run alongside
    // term_key.
    uint16_t status[TERM_STATUS_SLOTS];
    _Atomic uint8_t status_head;
    _Atomic uint8_t status_tail;

    // The Feature Error bit (#117): set by a feature command at an address
    // with no feature, shown as bit 0 of every POLL's answer, and cleared by
    // POLL_ACK and READ_TERMINAL_ID. Only the frame handling writes these.
    bool feature_error;
    bool poll_empty;  // the last POLL since the last POLL_ACK found the queue empty

    // The frame being received.
    uint16_t first_word;
    uint8_t command;    // what the frame is doing (term.c's command_t)
    uint8_t continues;  // the command a data-only frame would carry on
    bool eab_phase;     // EAB_WRITE_ALTERNATE: the next byte is an EAB byte
    bool have_byte;
    uint8_t byte;       // the first data byte, for the one-byte loads

    bool clicker;
    uint32_t alarms;
    uint32_t unknown;
    uint16_t last_unknown;
    uint32_t no_feature;  // feature commands at an address with no feature (#117)
    uint16_t last_no_feature;
    uint32_t display_gen;
    bool written;  // the controller has written the regen buffer since term_init
    uint32_t writes;  // bytes written to the regen buffer since term_init: auto dim's activity (dim.h)
} term_t;

size_t term_sizeof(void);  // for ctypes, which can't see sizeof

// Power-on: buffers zeroed, counter and registers 0, and the power-on reset
// status (0x00A) waiting for the first POLL.
void term_init(term_t *t, const term_config_t *cfg);

// One 10-bit word of a frame, applied as it arrives.
void term_rx_word(term_t *t, uint16_t word);

// The end of a frame (recv_tap's 0xFFFFFFFF). Writes the answer to tx and
// returns its length; 0 means stay silent.
size_t term_rx_end(term_t *t, uint16_t *tx, size_t tx_max);

// Drops the frame being received, in place of term_rx_end: no answer, and
// none of the effects that come at a frame's end. Data words already taken
// stay written, and a data-only frame after it doesn't continue the write,
// since words may be missing. For the firmware, after a receive overrun.
void term_rx_abort(term_t *t);

// Queue a scan code for the next POLLs; false when the queue is full.
bool term_key(term_t *t, uint8_t code);

// Statuses waiting for POLL_ACK, the power-on reset included.
unsigned term_queued(const term_t *t);

// Changes whenever something drawn changes: a write, a counter load (the
// counter is the cursor) or a control register load.
uint32_t term_display_gen(const term_t *t);

// Whether the controller has written the regen buffer (WRITE_DATA or
// EAB_WRITE_ALTERNATE) since term_init: what ends the splash screen
// (splash.h). Reads, counter and control loads, and the controller's
// discovery of the terminal don't count.
bool term_written(const term_t *t);

// The bytes written to the regen buffer (WRITE_DATA, its data-only frames and
// EAB_WRITE_ALTERNATE) since term_init, wrapping at 2^32. Auto dim takes a
// change as activity (#49).
uint32_t term_writes(const term_t *t);

const uint8_t *term_regen(const term_t *t);  // REGEN_SIZE bytes
const uint8_t *term_eab(const term_t *t);    // REGEN_SIZE bytes
uint16_t term_ac(const term_t *t);
uint8_t term_control(const term_t *t);
uint8_t term_secondary(const term_t *t);
bool term_clicker(const term_t *t);          // from the POLL action bits
uint32_t term_alarms(const term_t *t);       // POLLs that sounded the alarm
uint32_t term_unknown(const term_t *t);      // commands the core doesn't carry out
uint16_t term_last_unknown(const term_t *t);
// Feature commands at an address with no feature, each setting the feature
// error (#117): oec's feature scan sends 12 at every attach.
uint32_t term_no_feature(const term_t *t);
uint16_t term_last_no_feature(const term_t *t);

#endif
