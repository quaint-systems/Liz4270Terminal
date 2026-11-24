// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// Auto dim (#49): the 3483-V's screen saver. After the delay its SetUp sets
// (settings.h) with no keystroke and no write to the regen buffer, the screen
// dims, as render.c draws it. POLLs neither hold it off nor end it. A write
// ends it, and so does a keystroke, which is swallowed: the keys pressed to
// wake it are taken out of that keyboard's reports until each is let go, so
// they never reach the translator (captured Oct 5 and 6,
// docs/upstream-review.md). A key pressed after them is typed.
//
// Plain C11, like the rest of the core: the caller passes the time in
// milliseconds, which may wrap, and term_writes.

#ifndef LIZ_DIM_H
#define LIZ_DIM_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "settings.h"

#define DIM_SOURCES 4u  // keyboards it tracks, by the translator's source (keyboard.h's KBD_SOURCES)
#define DIM_KEYS 6u     // a boot report's key slots

// One keyboard, as auto dim sees it.
typedef struct {
    uint8_t mods;                  // the modifiers down in its last report
    uint8_t keys[DIM_KEYS];        // and the usages
    uint8_t masked_mods;           // modifiers pressed to wake auto dim, still down
    uint8_t masked_keys[DIM_KEYS]; // and usages (0 for an empty slot)
} dim_source_t;

// Defined here so the caller can allocate it. The fields are private to dim.c.
typedef struct {
    uint32_t last_ms;  // the last activity
    uint32_t writes;   // term_writes at the last tick
    bool on;
    dim_source_t src[DIM_SOURCES];
} dim_t;

size_t dim_sizeof(void);  // for ctypes, which can't see sizeof

// Off, with its timer from ms and term_writes at writes.
void dim_init(dim_t *d, uint32_t ms, uint32_t writes);

// Often, from the loop: a change in writes is activity, and with the
// auto_dim setting on, dim_minutes without activity turn it on. With the
// setting off it stays off, and its timer counts from the last tick.
void dim_tick(dim_t *d, const settings_t *s, uint32_t ms, uint32_t writes);

// Whether dim_tick would turn it on now: asked first where auto dim locks
// instead (lock.h, #122), so it never comes on before the lock.
bool dim_due(const dim_t *d, const settings_t *s, uint32_t ms, uint32_t writes);

// One 8-byte boot report from src, before the translator: writes the report
// the translator gets into out, and returns true if it took anything out.
// A report that presses a modifier or a key not down in src's last report is
// a keystroke, and activity. While auto dim is on it ends it, and those newly
// pressed keys are masked: taken out of src's reports until each is let go.
// Anything else passes, so a key held through the delay stays held, and a
// key pressed after the waking one is typed. A report that only lets keys go
// is never activity. A source past DIM_SOURCES wakes it, but nothing is
// masked.
bool dim_report(dim_t *d, unsigned src, uint32_t ms, const uint8_t report[8], uint8_t out[8]);

// A keyboard mounted or gone: its last report, and any keys masked, are forgotten.
void dim_forget(dim_t *d, unsigned src);

// A keystroke that isn't swallowed (the console's k): ends it, and restarts the timer.
void dim_activity(dim_t *d, uint32_t ms);

// On now (the console's v dim): a key or a write ends it.
void dim_now(dim_t *d);

bool dim_on(const dim_t *d);

#endif
