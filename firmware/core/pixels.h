// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// Pixels as HSTX takes them (#26): two RGB565 a word, the left one in the
// low half. render.c and splash.c draw their lines with these.
//
// Plain C11, like the rest of the core. The helpers are inline, as the
// renderer calls them for every cell of every line; the masks they read are
// defined once, in pixels.c.

#ifndef LIZ_PIXELS_H
#define LIZ_PIXELS_H

#include <stdint.h>

// pixels_masks[b]: eight pixels, two to a word, lit (0xFFFF) where bit x of b is set.
extern const uint32_t pixels_masks[256][4];

_Static_assert(640u / 2u % 8u == 0u && 720u / 2u % 8u == 0u,
               "pixels_fill writes eight words a step, so each layout's line (width / 2 words) is whole steps");

// Words all one value: a line with no ink, or the gap and its rule. Both
// layouts' lines (320 and 360 words) are whole multiples of eight, as the
// assertion above checks.
static inline void pixels_fill(uint32_t *out, unsigned words, uint32_t value) {
    for (uint32_t *end = out + words; out < end; out += 8) {
        out[0] = value;
        out[1] = value;
        out[2] = value;
        out[3] = value;
        out[4] = value;
        out[5] = value;
        out[6] = value;
        out[7] = value;
    }
}

// Eight pixels, lit in colour (doubled) where bit x of bits is set: four
// words. A cell with no ink on the line skips the masks: pixels_masks[0] is
// all black anyway.
static inline void pixels_put_8(uint32_t *out, uint32_t bits, uint32_t colour) {
    uint32_t w0 = 0, w1 = 0, w2 = 0, w3 = 0;
    if (bits != 0) {
        const uint32_t *m = pixels_masks[bits];
        w0 = m[0] & colour;
        w1 = m[1] & colour;
        w2 = m[2] & colour;
        w3 = m[3] & colour;
    }
    out[0] = w0;
    out[1] = w1;
    out[2] = w2;
    out[3] = w3;
}

// Two 9-dot cells, a and b, 18 pixels in nine words: a's columns 0-7 take
// four words from the masks; its column 8 and b's column 0 share the middle
// word; b's columns 1-8 take the last four.
static inline void pixels_put_9_pair(uint32_t *out, uint32_t bits_a, uint32_t colour_a, uint32_t bits_b,
                                     uint32_t colour_b) {
    pixels_put_8(out, bits_a & 0xFFu, colour_a);
    out[4] = ((bits_a >> 8) & 1u ? colour_a & 0x0000FFFFu : 0u) | (bits_b & 1u ? colour_b & 0xFFFF0000u : 0u);
    pixels_put_8(out + 5, (bits_b >> 1) & 0xFFu, colour_b);
}

#endif
