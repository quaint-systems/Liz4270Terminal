// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// The 3483-V's Lock sessions and its password (#122): Password Set keeps a
// password, typed twice, and the lock hides the host's screen until it's
// typed at a prompt on the status line (captured Oct 13, captures/README.md).
//
// Plain C11, like the rest of the core, so tools/sim tests it through ctypes.

#ifndef LIZ_LOCK_H
#define LIZ_LOCK_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "settings.h"

#define LOCK_PASSWORD_MAX 10u  // a Password Set field's cells, and the prompt's

// A key as typed into a password: its 3483-V code (keys3483.h), and whether
// it went with Shift, so case counts, as on the 3483-V.
typedef struct {
    uint8_t code;
    bool shift;
} lock_key_t;

// The password's hash, as the settings record keeps it (settings.h): FNV-1a
// 64 over the byte n, then each key's code and a byte 1 or 0 for Shift. A
// result of 0 becomes 1, so SETTINGS_NO_PASSWORD (0) always means none. It's
// no defence against brute force, nor meant as one: the lock is a courtesy,
// as the 3483-V's is (a power cycle unlocks it).
uint64_t lock_hash(const lock_key_t *keys, unsigned n);

// Whether a key types a character into a password: the letters, the digits
// and the typewriter block's punctuation. Space (the alarm on the 3483-V,
// Oct 13), the keypad (the hash is of keys, so each character has one) and
// every key with no character are not.
bool lock_character(uint8_t code);

// The lock's states: off, locked with the host's rows black, and the prompt
// up on the status line (captured Oct 13).
typedef enum { LOCK_OFF = 0, LOCK_BLACK = 1, LOCK_PROMPT = 2 } lock_state_t;

typedef enum {
    LOCK_NONE = 0,      // off: nothing
    LOCK_REDRAW = 1,    // the prompt came up, or took a key: draw the status line again
    LOCK_ALARM = 2,     // a wrong password (black again), or a key the prompt can't use: sound the alarm
    LOCK_UNLOCKED = 3,  // the right password: the host's screen again
} lock_result_t;

// What auto dim's delay means now (lock_dim_due).
typedef enum {
    LOCK_DIM_BLANK = 0,  // blank, as auto dim does without the lock (#49)
    LOCK_DIM_LOCK = 1,   // page 1's Lock sessions Yes with a password set: lock instead
    LOCK_DIM_NONE = 2,   // already locked: nothing, since auto dim never blanks the lock
} lock_dim_t;

#define LOCK_LINE_COLS 80u  // the status line's cells (render.h's RENDER_COLS)
#define LOCK_X_COL 8u       // the X (display code F6, 3270font's lock), counted from 0 (lock-1-locked-blank.jpg)
#define LOCK_KEY_COL 10u    // the key symbol, two cells: FA FB, keyleft and keyright
#define LOCK_INPUT_COL 28u  // the prompt's first asterisk, past "Enter password ===========> " (lock-3)
#define LOCK_CODE_X 0xF6u
#define LOCK_CODE_KEY_LEFT 0xFAu
#define LOCK_CODE_KEY_RIGHT 0xFBu

typedef struct {
    uint32_t locks;    // engaged from off
    uint32_t unlocks;  // the right password
    uint32_t wrong;    // wrong ones
} lock_stats_t;

// Defined here so the caller can allocate it. The fields are private to lock.c.
typedef struct {
    uint8_t state;                       // a lock_state_t
    uint8_t typed;                       // keys at the prompt
    lock_key_t keys[LOCK_PASSWORD_MAX];  // and what they were, wiped once checked
    lock_stats_t stats;
} lock_t;

// The status line the renderer draws while locked.
typedef struct {
    uint8_t codes[LOCK_LINE_COLS];  // display codes
    int8_t cursor;                  // the prompt's cursor column, or -1 for none
    bool bar;                       // SetUp's white bar (the prompt), else the status line's blue
} lock_line_t;

size_t lock_sizeof(void);  // for ctypes, which can't see sizeof

// Off, its counters at zero. (Not lock_init: the pico-sdk's lock_core.h has one.)
void lock_clear(lock_t *l);

// Locked, the host's rows black, with no prompt: from SetUp's Lock sessions,
// or auto dim at page 1's Lock sessions Yes.
void lock_engage(lock_t *l);

lock_state_t lock_state(const lock_t *l);

// One key while locked, a 3483-V code with its Shift; password is the live
// record's hash. Black: the key brings up the prompt and is swallowed. At the
// prompt: a character key (lock_character) adds itself, up to
// LOCK_PASSWORD_MAX, and an asterisk; Enter checks what's typed and wipes
// it, unlocking on a match, or with no password set at all (the console's
// set defaults can clear it while locked), and going black on anything
// else; any other key sounds the alarm. Off: nothing.
lock_result_t lock_key(lock_t *l, uint8_t code, bool shift, uint64_t password);

// The status line as the lock shows it: black, only the X and the key
// symbol in the status blue; the prompt, "Enter password ===========>" on
// SetUp's bar, an asterisk a key from LOCK_INPUT_COL, and the cursor after
// them; off, blank.
void lock_status_line(const lock_t *l, lock_line_t *out);

// Auto dim's delay is up: blank, lock instead, or nothing while locked. With
// page 1's Lock sessions Yes and no password set, it blanks, since there's no
// password to lock with (not captured).
lock_dim_t lock_dim_due(const settings_t *s, bool locked);

void lock_stats(const lock_t *l, lock_stats_t *out);

#endif
