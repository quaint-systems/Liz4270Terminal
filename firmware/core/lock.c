// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// Lock sessions and its password (#122). See lock.h.

#include "lock.h"

#include <string.h>

#include "display_text.h"
#include "keys3483.h"

#define FNV_OFFSET 14695981039346656037ull
#define FNV_PRIME 1099511628211ull

static uint64_t fnv(uint64_t h, uint8_t byte) {
    return (h ^ byte) * FNV_PRIME;
}

uint64_t lock_hash(const lock_key_t *keys, unsigned n) {
    uint64_t h = fnv(FNV_OFFSET, (uint8_t)n);
    for (unsigned i = 0; i < n; i++) {
        h = fnv(h, keys[i].code);
        h = fnv(h, keys[i].shift ? 1u : 0u);
    }
    return h ? h : 1u;
}

bool lock_character(uint8_t code) {
    switch (code) {
    case K_A: case K_B: case K_C: case K_D: case K_E: case K_F: case K_G: case K_H: case K_I:
    case K_J: case K_K: case K_L: case K_M: case K_N: case K_O: case K_P: case K_Q: case K_R:
    case K_S: case K_T: case K_U: case K_V: case K_W: case K_X: case K_Y: case K_Z:
    case K_0: case K_1: case K_2: case K_3: case K_4: case K_5: case K_6: case K_7: case K_8: case K_9:
    case K_BACKTICK: case K_LESS: case K_COMMA: case K_PERIOD: case K_SLASH: case K_SEMICOLON:
    case K_MINUS: case K_QUOTE: case K_BRACE: case K_CENT: case K_EQUALS: case K_BACKSLASH:
        return true;
    default:
        return false;
    }
}

static const char prompt[] = "Enter password ===========>";  // lock-2-enter-password-prompt.jpg
_Static_assert(sizeof prompt == LOCK_INPUT_COL, "the asterisks start a blank past the arrow");

size_t lock_sizeof(void) {
    return sizeof(lock_t);
}

void lock_clear(lock_t *l) {
    memset(l, 0, sizeof *l);
}

static void forget(lock_t *l) {
    memset(l->keys, 0, sizeof l->keys);
    l->typed = 0;
}

void lock_engage(lock_t *l) {
    if (l->state == LOCK_OFF)
        l->stats.locks++;
    l->state = LOCK_BLACK;
    forget(l);
}

lock_state_t lock_state(const lock_t *l) {
    return (lock_state_t)l->state;
}

lock_result_t lock_key(lock_t *l, uint8_t code, bool shift, uint64_t password) {
    switch (l->state) {
    case LOCK_BLACK:
        l->state = LOCK_PROMPT;  // the key that brings it up is swallowed (Oct 13)
        forget(l);
        return LOCK_REDRAW;
    case LOCK_PROMPT:
        if (code == K_ENTER) {
            bool right = password == SETTINGS_NO_PASSWORD
                         || (l->typed > 0 && lock_hash(l->keys, l->typed) == password);
            forget(l);
            if (right) {
                l->state = LOCK_OFF;
                l->stats.unlocks++;
                return LOCK_UNLOCKED;
            }
            l->state = LOCK_BLACK;  // the alarm, then the black screen again (lock-9)
            l->stats.wrong++;
            return LOCK_ALARM;
        }
        if (!lock_character(code) || l->typed == LOCK_PASSWORD_MAX)
            return LOCK_ALARM;
        l->keys[l->typed++] = (lock_key_t){code, shift};
        return LOCK_REDRAW;
    default:
        return LOCK_NONE;
    }
}

void lock_status_line(const lock_t *l, lock_line_t *out) {
    memset(out->codes, 0, sizeof out->codes);
    out->cursor = -1;
    out->bar = false;
    if (l->state == LOCK_BLACK) {
        out->codes[LOCK_X_COL] = LOCK_CODE_X;
        out->codes[LOCK_KEY_COL] = LOCK_CODE_KEY_LEFT;
        out->codes[LOCK_KEY_COL + 1u] = LOCK_CODE_KEY_RIGHT;
    } else if (l->state == LOCK_PROMPT) {
        for (unsigned i = 0; prompt[i]; i++)
            out->codes[i] = display_text_code((unsigned char)prompt[i]);
        for (unsigned i = 0; i < l->typed; i++)
            out->codes[LOCK_INPUT_COL + i] = display_text_code('*');
        out->cursor = (int8_t)(LOCK_INPUT_COL + l->typed);
        out->bar = true;
    }
}

lock_dim_t lock_dim_due(const settings_t *s, bool locked) {
    if (locked)
        return LOCK_DIM_NONE;
    return s->lock_sessions && settings_password_set(s) ? LOCK_DIM_LOCK : LOCK_DIM_BLANK;
}

void lock_stats(const lock_t *l, lock_stats_t *out) {
    *out = l->stats;
}
