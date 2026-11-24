// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// Keymaps (#17): the registry and lookup. See keymap.h.

#include "keymap.h"

#include <stddef.h>

// Every keymap, the default first. Adding one: its file under keymaps/, and
// a line here (keymaps/README.md).
static const keymap_t *const maps[] = {
    &keymap_us104,
};

unsigned keymap_count(void) {
    return (unsigned)(sizeof maps / sizeof maps[0]);
}

const keymap_t *keymap_at(unsigned i) {
    return i < keymap_count() ? maps[i] : NULL;
}

const keymap_t *keymap_for(uint16_t vid, uint16_t pid) {
    uint32_t id = (uint32_t)vid << 16 | pid;
    for (unsigned i = 0; i < keymap_count(); i++)
        for (const uint32_t *d = maps[i]->devices; d && *d; d++)
            if (*d == id)
                return maps[i];
    return maps[0];
}

static const keymap_entry_t *find(const keymap_t *map, uint8_t usage, uint8_t when) {
    for (const keymap_t *m = map; m; m = m->base)
        for (uint16_t i = 0; i < m->count; i++)
            if (m->entries[i].usage == usage && m->entries[i].when == when)
                return &m->entries[i];
    return NULL;
}

const keymap_entry_t *keymap_lookup_exact(const keymap_t *map, uint8_t usage, uint8_t chord) {
    return find(map, usage, chord);
}

const keymap_entry_t *keymap_lookup(const keymap_t *map, uint8_t usage, uint8_t chord) {
    const keymap_entry_t *e = find(map, usage, chord);
    return e ? e : find(map, usage, KM_ANY);
}
