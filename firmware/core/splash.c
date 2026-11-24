// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// The splash screen (#53). See splash.h.
//
// Laid out after the 3483-V's own: IBM's logo is eight stripes, one a text
// row, each about 60% of the row's height, with ends on cell boundaries, and
// the text under it is white, mixed case and centred. Ours spells LIZ to the
// same weight (44 columns, 5-column stems, 2-column gaps).
//
// splash_init lays the screen out once as cells, the logo's stripes among
// them, and notes which lines of each row have ink. A line then is a fill,
// or every cell from the font as render.c draws a row (pixels.h).

#include "display_text.h"
#include "font_3270.h"
#include "pixels.h"
#include "splash.h"

#define LOGO_TOP 3u
#define LOGO_LEFT 18u
#define LOGO_ROWS 8u
#define LOGO_COLS 44u
#define STRIPE_FIRST 4u  // the lines of a cell a stripe fills: 11 of 19
#define STRIPE_LAST 14u
#define VERSION_ROW 14u
#define COMMIT_ROW 15u

#define CODE_BLANK 0x00u
#define STRIPE 0xFFu         // a cell of the logo in cells[]: the text's codes are all below 0xC0

// '#' is a cell of stripe. Shorter rows end in NULs, which aren't stripe.
static const char logo[LOGO_ROWS][LOGO_COLS + 1u] = {
    "#####           #########  #################",
    "#####           #########  #################",
    "#####             #####                #####",
    "#####             #####            #####",
    "#####             #####        #####",
    "#####             #####    #####",
    "##############  #########  #################",
    "##############  #########  #################",
};

// Latin-1, as the 3483-V's display codes have it (tools/sim/display_codes.py).
static const struct {
    uint8_t row;
    const char *text;
} lines[] = {
    {13u, "Liz4270 Control Program"},
    {17u, "Liz4270 Microcode (c) Copyright 2026 CoffeeMuse."},
    {18u, "ISC license. Built on coax and oec by Andrew Kay,"},
    {19u, "and on coax-tcp by Hans H\xfc" "bner."},
    {21u, "Named For Liz, The Mainframe Cat."},
};

size_t splash_sizeof(void) {
    return sizeof(splash_t);
}

// Text centred on row, cut at the right edge: a and then b.
static void put_line(splash_t *s, unsigned row, const char *a, const char *b) {
    unsigned length = 0;
    for (const char *p = a; *p; p++)
        length++;
    for (const char *p = b; *p; p++)
        length++;
    unsigned col = length < RENDER_COLS ? (RENDER_COLS - length) / 2u : 0u;
    for (const char *p = a; *p && col < RENDER_COLS; p++)
        s->cells[row][col++] = display_text_code((unsigned char)*p);
    for (const char *p = b; *p && col < RENDER_COLS; p++)
        s->cells[row][col++] = display_text_code((unsigned char)*p);
}

// A cell's line in each font: bit x for pixel x.
static uint32_t bits_8(uint8_t cell, unsigned line) {
    if (cell == STRIPE)
        return line >= STRIPE_FIRST && line <= STRIPE_LAST ? 0xFFu : 0u;
    return font_3270_8x19[cell][line];
}

static uint32_t bits_9(uint8_t cell, unsigned line) {
    if (cell == STRIPE)
        return line >= STRIPE_FIRST && line <= STRIPE_LAST ? 0x1FFu : 0u;
    return font_3270_9x19[cell][line];
}

void splash_init(splash_t *s, const char *version, const char *commit, uint32_t now_ms) {
    for (unsigned row = 0; row < RENDER_ROWS; row++)
        for (unsigned col = 0; col < RENDER_COLS; col++)
            s->cells[row][col] = CODE_BLANK;
    for (unsigned r = 0; r < LOGO_ROWS; r++)
        for (unsigned c = 0; c < LOGO_COLS; c++)
            if (logo[r][c] == '#')
                s->cells[LOGO_TOP + r][LOGO_LEFT + c] = STRIPE;
    for (unsigned i = 0; i < sizeof lines / sizeof lines[0]; i++)
        put_line(s, lines[i].row, lines[i].text, "");
    put_line(s, VERSION_ROW, "Version ", version);
    put_line(s, COMMIT_ROW, "Commit ", commit);

    // Ink in either font, so splash_line can fill the lines with none.
    for (unsigned row = 0; row < RENDER_ROWS; row++) {
        uint32_t ink = 0;
        for (unsigned col = 0; col < RENDER_COLS; col++)
            for (unsigned line = 0; line < RENDER_CELL_H; line++)
                if (bits_8(s->cells[row][col], line) | bits_9(s->cells[row][col], line))
                    ink |= 1u << line;
        s->row_ink[row] = ink;
    }

    s->start_ms = now_ms;
    s->ended = false;
}

bool splash_showing(splash_t *s, uint32_t now_ms, bool written) {
    if (s->ended)
        return false;
    if (now_ms - s->start_ms < SPLASH_MIN_MS)  // unsigned, so right across the wrap
        return true;
    if (written)
        s->ended = true;
    return !s->ended;
}

void splash_dismiss(splash_t *s) {
    s->ended = true;
}

uint16_t splash_colour(const settings_t *s) {
    return s->mono ? RENDER_PHOSPHOR : RENDER_WHITE;
}

void splash_line(const splash_t *s, const render_layout_t *layout, unsigned y, uint16_t colour, uint32_t *pairs) {
    if (y >= RENDER_LINES)
        return;
    unsigned row = y / RENDER_CELL_H, line = y % RENDER_CELL_H;
    // Where the rule and status line would be, and every line no cell has ink on.
    if (row >= RENDER_ROWS || !((s->row_ink[row] >> line) & 1u)) {
        pixels_fill(pairs, layout->width / 2u, 0u);
        return;
    }
    uint32_t ink = colour * 0x00010001u;
    const uint8_t *cells = s->cells[row];
    if (layout->cell_w == 9u) {
        for (unsigned col = 0; col < RENDER_COLS; col += 2u, pairs += 9)
            pixels_put_9_pair(pairs, bits_9(cells[col], line), ink, bits_9(cells[col + 1u], line), ink);
    } else {
        for (unsigned col = 0; col < RENDER_COLS; col++, pairs += 4)
            pixels_put_8(pairs, bits_8(cells[col], line), ink);
    }
}
