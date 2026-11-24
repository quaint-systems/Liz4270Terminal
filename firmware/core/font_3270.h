// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// The firmware's font: 3270font at 16 px, one bit per pixel, indexed by
// display code. Row y of a glyph has bit x set for pixel x lit.
//
// tools/sim/bake_font.py writes the tables into font_3270.c, which is under
// the SIL Open Font License 1.1 (NOTICE); this header is Liz4270's own (ISC).
//
// Letters keep their ink in columns 1-7. Most status-line symbols are drawn
// to 3270font's full advance (8.64 px at 16 px), so they use columns 0-8:
// font_3270_9x19 keeps all nine for 720 x 480's 9-dot cells, and
// font_3270_8x19 fits them to 640 x 480's 8-dot cells.
//
// At 14 and 10 lines (#110) the glyphs are the 19-line drawing squashed
// vertically, for Model 3's and Model 4's cells; bake_font.py says how.

#ifndef LIZ_FONT_3270_H
#define LIZ_FONT_3270_H

#include <stdint.h>

#define FONT_GLYPHS 256u
#define FONT_ROWS 19u
#define FONT_ROWS_14 14u  // Model 3's cells (#110)
#define FONT_ROWS_10 10u  // Model 4's

extern const uint16_t font_3270_9x19[FONT_GLYPHS][FONT_ROWS];
extern const uint8_t font_3270_8x19[FONT_GLYPHS][FONT_ROWS];

// Each glyph's lines with ink, bit n for line n, the same in both tables.
extern const uint32_t font_3270_ink[FONT_GLYPHS];

// The same font squashed to Model 3's and Model 4's cells (#110), with
// their ink tables: full width, at 14 and 10 lines.
extern const uint16_t font_3270_9x14[FONT_GLYPHS][FONT_ROWS_14];
extern const uint8_t font_3270_8x14[FONT_GLYPHS][FONT_ROWS_14];
extern const uint32_t font_3270_ink14[FONT_GLYPHS];
extern const uint16_t font_3270_9x10[FONT_GLYPHS][FONT_ROWS_10];
extern const uint8_t font_3270_8x10[FONT_GLYPHS][FONT_ROWS_10];
extern const uint32_t font_3270_ink10[FONT_GLYPHS];

#endif
