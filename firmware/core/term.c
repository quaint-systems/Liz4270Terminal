// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// Liz4270 terminal core: frame dispatch, the status queue and the answers.
//
// The values marked captured come from traces of a real 3483-V, from Oct 3,
// 2026 on (captures/, indexed in its README; #29 settled what the first
// traces didn't show, and #117 the feature error). What no trace shows is
// marked as a default.

#include <stdatomic.h>
#include <string.h>

#include "term.h"

#define TT_AR 0x000u
#define POWER_ON_RESET 0x00Au
#define FEATURE_ERROR 0x001u  // POLL's bit 0 (captured, #117)
#define STATUS_MASK (TERM_STATUS_SLOTS - 1u)

_Static_assert((TERM_STATUS_SLOTS & STATUS_MASK) == 0u && TERM_STATUS_SLOTS <= 128u,
               "the status counters wrap at 256, so the queue is a power of two up to 128");

// Captured identity (captures/20261003-070935-ids.jsonl).
#define TERMINAL_ID_MODEL_2 0x04u  // CUT, model bits 3-1 010
#define TERMINAL_ID_MODEL_3 0x06u  // 011: captured Oct 12 at 32 x 80 (#110)
#define TERMINAL_ID_MODEL_4 0x0Eu  // 111: captured Oct 12 at 43 x 80
#define STATUS_NOT_BUSY 0x30u  // bit 5 not busy; bit 4 set, unexplained
#define EAB_FEATURE_ADDRESS 7u
#define FEATURE_ID_6 0x66u     // unknown to pycoax; oec ignores it
#define FEATURE_ID_EAB 0x79u
#define SECONDARY_BIG 0x01u    // block reads take 32 bytes, not 4
static const uint8_t extended_id[] = {0xC1, 0x34, 0x83, 0x00};  // IBM 122-key typewriter keyboard

typedef enum {
    CMD_NONE,          // between frames
    CMD_UNKNOWN,       // answered with TT/AR, and counted
    CMD_NO_FEATURE,    // a feature command at an address with no feature: sets the feature error
    CMD_IGNORED_DATA,  // a data-only frame with nothing to carry on
    CMD_POLL,
    CMD_POLL_ACK,
    CMD_READ_TERMINAL_ID,
    CMD_READ_EXTENDED_ID,
    CMD_READ_FEATURE_ID,
    CMD_READ_STATUS,
    CMD_READ_AC_HI,
    CMD_READ_AC_LO,
    CMD_READ_DATA,
    CMD_READ_MULTIPLE,
    CMD_LOAD_CONTROL,
    CMD_LOAD_SECONDARY,
    CMD_LOAD_AC_HI,
    CMD_LOAD_AC_LO,
    CMD_WRITE_DATA,
    CMD_EAB_LOAD_MASK,
    CMD_EAB_WRITE_ALTERNATE,
    CMD_EAB_READ_DATA,
} command_t;

// Base commands by their 5-bit code (bits 6-2). A code not listed is
// unknown, and answered with TT/AR as the 3483-V answers its unassigned codes
// (captured, #29). RESET, CLEAR, the searches and INSERT_BYTE are among them:
// oec sends none of them, and the core doesn't carry them out.
static const uint8_t base_commands[32] = {
    [0x03] = CMD_READ_DATA,
    [0x04] = CMD_LOAD_AC_HI,
    [0x05] = CMD_READ_AC_HI,
    [0x07] = CMD_READ_EXTENDED_ID,
    [0x09] = CMD_READ_TERMINAL_ID,
    [0x0A] = CMD_LOAD_CONTROL,
    [0x0B] = CMD_READ_MULTIPLE,
    [0x0C] = CMD_WRITE_DATA,
    [0x0D] = CMD_READ_STATUS,
    [0x11] = CMD_POLL_ACK,
    [0x14] = CMD_LOAD_AC_LO,
    [0x15] = CMD_READ_AC_LO,
    [0x1A] = CMD_LOAD_SECONDARY,
};

// The ID of the feature at this address, READ_FEATURE_ID's answer, or 0 for
// none: feature 6 and EAB at 7, as the 3483-V reports them, or none without
// EAB. Every feature command decodes by it.
static uint8_t feature_id(const term_t *t, unsigned address) {
    if (!t->cfg.eab)
        return 0u;
    if (address == 6u)
        return FEATURE_ID_6;
    if (address == EAB_FEATURE_ADDRESS)
        return FEATURE_ID_EAB;
    return 0u;
}

static command_t decode(const term_t *t, uint16_t word) {
    // POLL first: its action bits (9-8) overlap the feature address.
    if ((word & 0xFFu) == 0x05u)
        return CMD_POLL;

    unsigned feature = word >> 6;
    if (feature >= 2u) {
        // Any feature command at an address with no feature, reads and
        // writes alike, sets the feature error (captured, #117).
        if (!feature_id(t, feature))
            return CMD_NO_FEATURE;
        unsigned code = (word >> 2) & 0x0Fu;
        if (code == 0x07u)
            return CMD_READ_FEATURE_ID;
        if (feature == EAB_FEATURE_ADDRESS) {
            if (code == 0x06u)
                return CMD_EAB_LOAD_MASK;
            if (code == 0x0Au)
                return CMD_EAB_WRITE_ALTERNATE;
            if (code == 0x03u)
                return CMD_EAB_READ_DATA;
        }
        return CMD_UNKNOWN;  // feature 6's commands (#112), and EAB's that oec never sends
    }

    command_t command = (command_t)base_commands[(word >> 2) & 0x1Fu];
    return command == CMD_NONE ? CMD_UNKNOWN : command;
}

// A data word: the byte in bits 9-2 and odd parity over it in bit 1, as pycoax
// packs it (the captured terminal ID 0x04 goes out as 0x010).
// READ_TERMINAL_ID's byte for the model the core was powered on as: 3 and 4
// theirs, anything else Model 2's (#110).
static uint8_t terminal_id(uint8_t model) {
    if (model == 3u)
        return TERMINAL_ID_MODEL_3;
    if (model == 4u)
        return TERMINAL_ID_MODEL_4;
    return TERMINAL_ID_MODEL_2;
}

static uint16_t data_word(uint8_t byte) {
    unsigned ones = byte;
    ones ^= ones >> 4;
    ones ^= ones >> 2;
    ones ^= ones >> 1;
    unsigned parity = ~ones & 1u;
    return (uint16_t)((byte << 2) | (parity << 1));
}

// The queue's counters: see term.h. A status is stored before the release
// that publishes it, and a slot is read before the release that frees it.
static unsigned status_count(const term_t *t) {
    uint8_t tail = atomic_load_explicit(&t->status_tail, memory_order_acquire);
    uint8_t head = atomic_load_explicit(&t->status_head, memory_order_acquire);
    return (uint8_t)(tail - head);
}

static bool status_push(term_t *t, uint16_t status) {
    uint8_t tail = atomic_load_explicit(&t->status_tail, memory_order_relaxed);
    uint8_t head = atomic_load_explicit(&t->status_head, memory_order_acquire);
    if ((uint8_t)(tail - head) >= TERM_STATUS_SLOTS)
        return false;
    t->status[tail & STATUS_MASK] = status;
    atomic_store_explicit(&t->status_tail, (uint8_t)(tail + 1u), memory_order_release);
    return true;
}

static void poll_action(term_t *t, unsigned action) {
    switch (action) {
    case 1u:  // clicker off
        t->clicker = false;
        break;
    case 2u:  // alarm
        t->alarms++;
        break;
    case 3u:  // clicker on
        t->clicker = true;
        break;
    default:
        break;
    }
}

// Whether a data-only frame after the command carries it on (captured, #29):
// a write writes on and a load loads again. After anything else it does
// nothing.
static bool takes_data(command_t command) {
    switch (command) {
    case CMD_WRITE_DATA:
    case CMD_EAB_WRITE_ALTERNATE:
    case CMD_LOAD_CONTROL:
    case CMD_LOAD_SECONDARY:
    case CMD_LOAD_AC_HI:
    case CMD_LOAD_AC_LO:
    case CMD_EAB_LOAD_MASK:
        return true;
    default:
        return false;
    }
}

// READ_MULTIPLE and READ_EXTENDED_ID (captured, #29): from the counter to the
// end of its block, 4 bytes or 32 with "big" set, leaving the counter at the
// block's end. READ_EXTENDED_ID reads the ID, which repeats every 4 bytes.
static size_t block_read(term_t *t, bool id, uint16_t *answer) {
    unsigned block = (t->secondary & SECONDARY_BIG) ? 32u : 4u;
    size_t count = block - (t->regen.ac & (block - 1u));
    for (size_t i = 0; i < count; i++) {
        uint8_t byte = id ? extended_id[t->regen.ac & 3u] : regen_get_char(&t->regen);
        answer[i] = data_word(byte);
        regen_advance(&t->regen);
    }
    t->display_gen++;  // the counter is the cursor
    return count;
}

static void take_data(term_t *t, uint8_t byte) {
    switch ((command_t)t->command) {
    case CMD_WRITE_DATA:
        regen_put_char(&t->regen, byte);
        regen_advance(&t->regen);
        t->display_gen++;
        t->written = true;
        t->writes++;
        break;
    case CMD_EAB_WRITE_ALTERNATE:
        // Character, then its EAB byte, then the next cell. The phase carries
        // across data-only frames, so a split on an odd byte still pairs up.
        if (!t->eab_phase) {
            regen_put_char(&t->regen, byte);
        } else {
            regen_put_eab(&t->regen, byte);
            regen_advance(&t->regen);
        }
        t->eab_phase = !t->eab_phase;
        t->display_gen++;
        t->written = true;
        t->writes++;
        break;
    case CMD_LOAD_CONTROL:
    case CMD_LOAD_SECONDARY:
    case CMD_LOAD_AC_HI:
    case CMD_LOAD_AC_LO:
    case CMD_EAB_LOAD_MASK:
        if (!t->have_byte) {
            t->byte = byte;
            t->have_byte = true;
        }
        break;
    default:
        break;  // data this command doesn't take
    }
}

// The answer to the frame that just ended; returns its length.
static size_t respond(term_t *t, command_t command, uint16_t *answer) {
    switch (command) {
    case CMD_NONE:
        return 0;  // an empty frame
    case CMD_UNKNOWN:
        t->unknown++;
        t->last_unknown = t->first_word;
        break;
    case CMD_NO_FEATURE:
        // The manual's all-zeros word with bad parity, which reads as TT/AR.
        // The features aren't blocked while it's set: the 3483-V answered
        // READ_FEATURE_ID at 7 as ever (captured Oct 12, #117).
        t->feature_error = true;
        t->no_feature++;
        t->last_no_feature = t->first_word;
        break;
    case CMD_POLL: {
        poll_action(t, t->first_word >> 8);
        uint8_t head = atomic_load_explicit(&t->status_head, memory_order_relaxed);
        unsigned count = status_count(t);
        answer[0] = (uint16_t)((count ? t->status[head & STATUS_MASK] : TT_AR) |
                               (t->feature_error ? FEATURE_ERROR : 0u));
        t->poll_empty = count == 0u;
        return 1;
    }
    case CMD_POLL_ACK:
        // It clears the feature error, and the status the POLL showed goes
        // with it, a keystroke included (captured Oct 13, #117). A status
        // queued after a POLL that found the queue empty was never shown,
        // so it stays (a default).
        if (status_count(t) && !t->poll_empty) {
            uint8_t head = atomic_load_explicit(&t->status_head, memory_order_relaxed);
            atomic_store_explicit(&t->status_head, (uint8_t)(head + 1u), memory_order_release);
        }
        t->feature_error = false;
        t->poll_empty = false;
        break;
    case CMD_READ_TERMINAL_ID:
        t->feature_error = false;  // captured, #117
        answer[0] = data_word(terminal_id(t->cfg.model));
        return 1;
    case CMD_READ_EXTENDED_ID:
        return block_read(t, true, answer);
    case CMD_READ_MULTIPLE:
        return block_read(t, false, answer);
    case CMD_READ_FEATURE_ID:  // only at an address with a feature
        answer[0] = data_word(feature_id(t, t->first_word >> 6));
        return 1;
    case CMD_READ_STATUS:
        answer[0] = data_word(STATUS_NOT_BUSY);
        return 1;
    case CMD_READ_AC_HI:
        answer[0] = data_word(regen_ac_hi(&t->regen));
        return 1;
    case CMD_READ_AC_LO:
        answer[0] = data_word(regen_ac_lo(&t->regen));
        return 1;
    case CMD_READ_DATA:
        answer[0] = data_word(regen_get_char(&t->regen));
        regen_advance(&t->regen);  // captured (#29)
        t->display_gen++;
        return 1;
    case CMD_EAB_READ_DATA:
        // The byte is captured (#29). The step is a default: every capture
        // loads the counter first. It steps like READ_DATA.
        answer[0] = data_word(t->regen.eab[t->regen.ac]);
        regen_advance(&t->regen);
        t->display_gen++;
        return 1;
    case CMD_LOAD_CONTROL:
        // Bit 4, "step inhibit" to pycoax, is kept: it has no effect on the
        // step of WRITE_DATA or READ_DATA (captured, #29).
        if (t->have_byte) {
            t->control = t->byte;
            t->display_gen++;
        }
        break;
    case CMD_LOAD_SECONDARY:
        if (t->have_byte)
            t->secondary = t->byte;
        break;
    case CMD_LOAD_AC_HI:
        if (t->have_byte) {
            regen_load_ac_hi(&t->regen, t->byte);
            t->display_gen++;
        }
        break;
    case CMD_LOAD_AC_LO:
        if (t->have_byte) {
            regen_load_ac_lo(&t->regen, t->byte);
            t->display_gen++;
        }
        break;
    case CMD_EAB_LOAD_MASK:
        // Kept, and nothing reads it. oec loads 0xFF before every
        // EAB_WRITE_ALTERNATE, but on the 3483-V the mask doesn't govern that
        // write, and lets it through from power-on (captured, #29).
        if (t->have_byte)
            t->eab_mask = t->byte;
        break;
    default:
        break;  // writes and data-only frames: the data went in as it arrived
    }
    answer[0] = TT_AR;
    return 1;
}

size_t term_sizeof(void) {
    return sizeof(term_t);
}

void term_init(term_t *t, const term_config_t *cfg) {
    memset(t, 0, sizeof *t);
    t->cfg = *cfg;
    regen_init(&t->regen);
    t->command = CMD_NONE;
    t->continues = CMD_NONE;
    status_push(t, POWER_ON_RESET);  // held until the controller acknowledges it
}

void term_rx_word(term_t *t, uint16_t word) {
    word &= 0x3FFu;
    if (t->command == CMD_NONE) {
        t->first_word = word;
        if (word & 1u) {
            t->command = (uint8_t)decode(t, word);
            t->have_byte = false;
            if (t->command == CMD_EAB_WRITE_ALTERNATE)
                t->eab_phase = false;  // a new write starts on a character
            return;
        }
        // No command word: a data-only frame. It carries on the write or
        // load just before it (oec splits writes at 1024 words), a load
        // taking its first byte; otherwise it's ignored.
        t->command = t->continues != CMD_NONE ? t->continues : CMD_IGNORED_DATA;
        t->have_byte = false;
    }
    if (!(word & 1u))
        take_data(t, (uint8_t)(word >> 2));
}

size_t term_rx_end(term_t *t, uint16_t *tx, size_t tx_max) {
    command_t command = (command_t)t->command;
    uint16_t answer[TERM_TX_MAX];
    size_t count = respond(t, command, answer);

    t->continues = takes_data(command) ? (uint8_t)command : (uint8_t)CMD_NONE;
    t->command = CMD_NONE;

    if (count > tx_max)
        count = tx_max;
    if (count)
        memcpy(tx, answer, count * sizeof answer[0]);
    return count;
}

void term_rx_abort(term_t *t) {
    t->command = CMD_NONE;
    t->continues = CMD_NONE;
}

bool term_key(term_t *t, uint8_t code) {
    return status_push(t, (uint16_t)(((unsigned)code << 2) | 0x2u));
}

unsigned term_queued(const term_t *t) {
    return status_count(t);
}

uint32_t term_display_gen(const term_t *t) {
    return t->display_gen;
}

bool term_written(const term_t *t) {
    return t->written;
}

uint32_t term_writes(const term_t *t) {
    return t->writes;
}

const uint8_t *term_regen(const term_t *t) {
    return t->regen.chars;
}

const uint8_t *term_eab(const term_t *t) {
    return t->regen.eab;
}

uint16_t term_ac(const term_t *t) {
    return t->regen.ac;
}

uint8_t term_control(const term_t *t) {
    return t->control;
}

uint8_t term_secondary(const term_t *t) {
    return t->secondary;
}

bool term_clicker(const term_t *t) {
    return t->clicker;
}

uint32_t term_alarms(const term_t *t) {
    return t->alarms;
}

uint32_t term_unknown(const term_t *t) {
    return t->unknown;
}

uint16_t term_last_unknown(const term_t *t) {
    return t->last_unknown;
}

uint32_t term_no_feature(const term_t *t) {
    return t->no_feature;
}

uint16_t term_last_no_feature(const term_t *t) {
    return t->last_no_feature;
}
