// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// Auto dim (#49). See dim.h.

#include <string.h>

#include "dim.h"

#define MS_PER_MINUTE 60000u

size_t dim_sizeof(void) {
    return sizeof(dim_t);
}

void dim_init(dim_t *d, uint32_t ms, uint32_t writes) {
    *d = (dim_t){.last_ms = ms, .writes = writes};
}

void dim_activity(dim_t *d, uint32_t ms) {
    d->on = false;
    d->last_ms = ms;
}

void dim_tick(dim_t *d, const settings_t *s, uint32_t ms, uint32_t writes) {
    if (writes != d->writes) {
        d->writes = writes;
        dim_activity(d, ms);
    } else if (!s->auto_dim) {
        dim_activity(d, ms);
    } else if (dim_due(d, s, ms, writes)) {
        d->on = true;
    }
}

bool dim_due(const dim_t *d, const settings_t *s, uint32_t ms, uint32_t writes) {
    return writes == d->writes && s->auto_dim && !d->on && ms - d->last_ms >= (uint32_t)s->dim_minutes * MS_PER_MINUTE;
}

static bool holds(const uint8_t keys[DIM_KEYS], uint8_t usage) {
    for (unsigned i = 0; i < DIM_KEYS; i++)
        if (keys[i] == usage)
            return true;
    return false;
}

// Any modifier, or any key slot in use (ErrorRollOver's 1 included).
static bool anything_down(const uint8_t report[8]) {
    if (report[0])
        return true;
    for (unsigned i = 2; i < 8; i++)
        if (report[i])
            return true;
    return false;
}

static void mask_key(dim_source_t *s, uint8_t usage) {
    if (holds(s->masked_keys, usage))
        return;
    for (unsigned i = 0; i < DIM_KEYS; i++) {
        if (!s->masked_keys[i]) {
            s->masked_keys[i] = usage;
            return;
        }
    }
}

bool dim_report(dim_t *d, unsigned src, uint32_t ms, const uint8_t report[8], uint8_t out[8]) {
    const uint8_t *keys = &report[2];
    memcpy(out, report, 8u);
    if (src >= DIM_SOURCES) {
        if (anything_down(report))
            dim_activity(d, ms);
        return false;
    }

    dim_source_t *s = &d->src[src];
    // Masked keys let go leave the mask (a key slot never comes back masked).
    s->masked_mods &= report[0];
    for (unsigned i = 0; i < DIM_KEYS; i++)
        if (s->masked_keys[i] && !holds(keys, s->masked_keys[i]))
            s->masked_keys[i] = 0;

    // A keystroke: something down now that wasn't in the last report.
    uint8_t new_mods = report[0] & (uint8_t)~s->mods;
    bool pressed = new_mods != 0;
    for (unsigned i = 0; i < DIM_KEYS; i++)
        if (keys[i] && !holds(s->keys, keys[i]))
            pressed = true;
    if (pressed) {
        if (d->on) {
            s->masked_mods |= new_mods;
            for (unsigned i = 0; i < DIM_KEYS; i++)
                if (keys[i] && !holds(s->keys, keys[i]))
                    mask_key(s, keys[i]);
        }
        dim_activity(d, ms);
    }
    s->mods = report[0];
    memcpy(s->keys, keys, DIM_KEYS);

    bool took = false;
    if (out[0] & s->masked_mods) {
        out[0] &= (uint8_t)~s->masked_mods;
        took = true;
    }
    for (unsigned i = 2; i < 8; i++) {
        if (out[i] && holds(s->masked_keys, out[i])) {
            out[i] = 0;
            took = true;
        }
    }
    return took;
}

void dim_forget(dim_t *d, unsigned src) {
    if (src < DIM_SOURCES)
        d->src[src] = (dim_source_t){0};
}

void dim_now(dim_t *d) {
    d->on = true;
}

bool dim_on(const dim_t *d) {
    return d->on;
}
