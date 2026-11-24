// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// The splash screen (#53): what the Fruit Jam shows from power-on until the
// controller draws, as the 3483-V shows its own. A striped LIZ logo and a few
// lines of text, white or the phosphor (splash_colour), with no rule, status
// line or cursor.
//
// Plain C11, like the rest of the core, so tools/sim draws the same pixels
// through ctypes. It knows nothing of the coax link or term_t: the caller
// passes the time and whether the controller has written the screen
// (term_written). video.c draws splash_line in place of render_line while
// splash_showing.

#ifndef LIZ_SPLASH_H
#define LIZ_SPLASH_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "render.h"

#define SPLASH_MIN_MS 3000u  // the least it shows, whatever the controller does

// Defined here so the caller can allocate it (video.c, statically). The
// fields are private to splash.c.
typedef struct splash {
    uint8_t cells[RENDER_ROWS][RENDER_COLS];  // display codes, and the logo's stripes
    uint32_t row_ink[RENDER_ROWS];            // each row's lines with ink: bit n for line n
    uint32_t start_ms;
    bool ended;
} splash_t;

size_t splash_sizeof(void);  // for ctypes, which can't see sizeof

// At power-on: the screen, with the build's version and commit (Latin-1, as
// version.c's liz_version and liz_commit, #132) under the title, and the time
// the splash counts from. Characters the 3483-V has no display code for show
// as '?'.
void splash_init(splash_t *s, const char *version, const char *commit, uint32_t now_ms);

// Whether the splash still shows: for SPLASH_MIN_MS, then until the
// controller has written the screen (written, from term_written), unless
// splash_dismiss ended it sooner. Once it ends it stays ended, even if
// written goes false again (the console's r runs term_init). The millisecond
// count may wrap.
bool splash_showing(splash_t *s, uint32_t now_ms, bool written);

// A local function (SetUp, #102) takes the screen: the splash ends at once,
// for good. video_splash_dismiss calls it as SetUp opens.
void splash_dismiss(splash_t *s);

// The splash's colour under the settings: RENDER_WHITE, or the phosphor in
// monochrome (#50). video.c picks it as each frame begins, so a frame is all
// one colour.
uint16_t splash_colour(const settings_t *s);

// Line y (0-479) into pairs, as render_line draws them: layout->width / 2
// words, each two RGB565 pixels, the left one in the low half. The text and
// the logo are in colour (splash_colour). Lines may be drawn in any order.
void splash_line(const splash_t *s, const render_layout_t *layout, unsigned y, uint16_t colour, uint32_t *pairs);

#endif
