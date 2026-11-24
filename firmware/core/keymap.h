// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// Keymaps (#17): which 3483-V key each USB key sends, as data. Each keymap
// lists, per USB usage, a base entry and optional chord entries for the PC's
// Shift and Alt; keymap_lookup picks one for a press. The translator
// (keyboard.c) does the rest: the 3270 modifiers, releases and typematic.
// keymaps/README.md says how to write one.

#ifndef LIZ_KEYMAP_H
#define LIZ_KEYMAP_H

#include <stdint.h>

// when: the chord an entry is for. KM_ANY is the base entry; anything else is
// an exact set of KM_SHIFT, KM_ALT and KM_CTRL (0: exactly no Shift or Alt).
// KM_CTRL matches only a Ctrl bit that rose in the same report as the usage.
#define KM_SHIFT 0x01u
#define KM_ALT 0x02u
#define KM_CTRL 0x04u
#define KM_ANY 0x80u

// mods: the 3270 modifiers the key is sent with. KM_KEEP passes the PC's
// Shift and Alt through as they are; anything else is an exact set of
// KM_SHIFT and KM_ALT, KM_NONE for neither.
#define KM_NONE 0x00u
#define KM_KEEP 0x80u

typedef struct {
    uint8_t usage;  // U_* (usb_usage.h)
    uint8_t when;   // KM_ANY or a chord
    uint8_t key;    // K_* (keys3483.h), K_NOTHING, or K_SETUP
    uint8_t mods;   // KM_KEEP or a set
} keymap_entry_t;

typedef struct keymap {
    const char *name;            // "us104": its reference page, docs/keymaps/<name>.md, and u's map=
    const char *title;           // "US 104-key (ANSI)"
    const char *status;          // "bench-tested: <keyboard>", or "contributed, not tested by the project"
    const struct keymap *base;   // an overlay names the map it changes; NULL otherwise
    const uint32_t *devices;     // VID << 16 | PID it claims, ending in 0; NULL claims none
    const keymap_entry_t *entries;
    uint16_t count;
} keymap_t;

extern const keymap_t keymap_us104;

// The first registered map that claims vid:pid, or the default (us104).
const keymap_t *keymap_for(uint16_t vid, uint16_t pid);

unsigned keymap_count(void);
const keymap_t *keymap_at(unsigned i);  // NULL past the end; 0 is the default

// The entry for a press of usage under chord (KM_SHIFT | KM_ALT | KM_CTRL
// bits): an exact chord entry from map or any of its bases, else a base entry
// from map or any of its bases; NULL if none.
const keymap_entry_t *keymap_lookup(const keymap_t *map, uint8_t usage, uint8_t chord);

// The exact chord entry only, through the bases; NULL if none.
const keymap_entry_t *keymap_lookup_exact(const keymap_t *map, uint8_t usage, uint8_t chord);

#endif
