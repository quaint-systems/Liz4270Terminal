// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// The screen as the Fruit Jam draws it (#26), one line of RGB565 at a time.
//
// Plain C11, like the rest of the core, so tools/sim draws the same pixels
// through ctypes. video.c calls render_frame_begin once a frame and
// render_line for each of its 480 lines, in any order. The spec is
// docs/superpowers/specs/2026-10-04-fruit-jam-screen-design.md ("Renderer",
// "What's drawn"), for EAB 2026-10-07-eab-render-design.md, and for the
// colour mapping and monochrome 2026-10-10-monochrome-colour-mapping-design.md,
// and for the Rule key's ruler 2026-10-10-rule-line-design.md;
// tools/sim/screen.py's render() is the reference.

#ifndef LIZ_RENDER_H
#define LIZ_RENDER_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "settings.h"
#include "ruler.h"

#define RENDER_LINES 480u
#define RENDER_MAX_WIDTH 720u
#define RENDER_COLS 80u
// Model 2's layout, which SetUp and the splash always draw at; each model's
// is a render_geometry_t (#110).
#define RENDER_ROWS 24u
#define RENDER_CELL_H 19u
#define RENDER_RULE_Y 457u     // the rule: lines 457-458
#define RENDER_RULE_H 2u
#define RENDER_STATUS_Y 461u   // the status line: lines 461-479
#define RENDER_TITLE_RULE_Y 28u  // SetUp's title rule (#102): lines 9-10 of row 2, RENDER_RULE_H thick
#define RENDER_SCREEN_START 80u
#define RENDER_SCREEN_END 2000u
#define RENDER_ROWS_MAX 43u  // Model 4's rows: render_t's per-row arrays (#110)

// A model's layout (#110): its rows of cell_h lines from line top, the 5-line
// gap that holds the rule, then the status line, a row tall, at the bottom.
// A shorter screen's spare lines are a blank band at the top. The font is
// 3270font at the cell's height (font_3270.h).
typedef struct {
    uint8_t rows;             // 24, 32 or 43
    uint8_t cell_h;           // 19, 14 or 10 lines
    uint16_t top;             // the first row's first line
    uint16_t gap_y;           // top + rows * cell_h: the gap's first line
    uint16_t rule_y;          // gap_y + 1: the rule, RENDER_RULE_H lines
    uint16_t status_y;        // gap_y + 5: the status line, cell_h lines to 479
    uint16_t screen_end;      // RENDER_SCREEN_START + rows * RENDER_COLS
    uint8_t underscore_line;  // an EAB underscore's line in a cell: the one above the cursor's
    uint8_t cursor_first;     // the underscore cursor's first line; it runs to the cell's last
    const uint16_t *nine;     // the font at cell_h lines, 9 dots: glyph g's line n is nine[g * cell_h + n]
    const uint8_t *eight;     // and 8 dots
    const uint32_t *ink;      // each glyph's lines with ink
} render_geometry_t;

extern const render_geometry_t render_model_2;
extern const render_geometry_t render_model_3;
extern const render_geometry_t render_model_4;

// A model's layout: 3's and 4's, anything else Model 2's.
const render_geometry_t *render_geometry(uint8_t model);

// Control register bits (docs/upstream-review.md).
#define RENDER_BLINK 0x01u
#define RENDER_REVERSE_CURSOR 0x02u
#define RENDER_CURSOR_INHIBIT 0x04u
// Bit 1 toggles the Cursor Style setting and bit 0 its Blink (all 16
// combinations captured Oct 6, captures/README.md). A blinking cursor is lit
// for RENDER_BLINK_FRAMES frames, then out for as many: 533 ms a cycle on the
// 3483-V (two videos, Oct 5), 534 ms at the Fruit Jam's 59.94 Hz.
#define RENDER_BLINK_FRAMES 16u
// Display inhibit blanks the 24 screen rows; the cursor, the rule and the
// status line with its indicator stay, as on the 3483-V (captured Oct 4,
// docs/upstream-review.md). oec never sets it.
#define RENDER_DISPLAY_INHIBIT 0x08u

// Where the cursor is drawn while the address counter is off the screen (on
// the status line, or at 2000 and above): address 1023, row 12, column 64,
// with RRRR/CCC 0012/064. There is never a cursor on the status line, but
// the lock's prompt's (#122)
// (captured Oct 6, #49: captures/photos-20261006/offscreen-*.jpg).
#define RENDER_OFFSCREEN_CURSOR 1023u

// Auto dim (dim.h): the 24 rows blank, RRRR/CCC goes, and display code 1F
// replaces status column 71; the cursor, the rule and the status line stay
// (captured Oct 5 and 6, #49).
#define RENDER_DIM_MARK 0x1Fu
#define RENDER_DIM_MARK_COL 71u

// EAB (#70): each cell's EAB byte, bits 7-6 its highlight (01 blink, 10
// reverse, 11 underscore) and bits 5-3 its colour, as oec writes them. The
// attribute in force carries the field's, and a cell's own non-zero colour or
// highlight replaces the field's (captured Oct 7: docs/upstream-review.md,
// "Display codes and attributes"). Reverse inverts the cell's lines and
// underscore lights the layout's EAB underscore line (Model 2's is
// RENDER_UNDERSCORE_LINE), in the cell's colour; the cursor's underscore is
// below it (#110). Blink blanks the glyph for the last
// RENDER_BLINK_FRAMES of every RENDER_FRAME_CYCLE frames: 16 out of 64, inside
// one of a blinking cursor's out phases. So a caller's frame count may wrap
// only at a multiple of RENDER_FRAME_CYCLE.
#define RENDER_UNDERSCORE_LINE 16u
#define RENDER_EAB_BLINK_OUT 3u   // (frame / RENDER_BLINK_FRAMES) % 4 while EAB blink is out
#define RENDER_FRAME_CYCLE (4u * RENDER_BLINK_FRAMES)

// LizTerm's palette (concept.md) in RGB565; HSTX widens each to 8 bits with
// zeros, so the monitor gets green 50FC50, red F85050, blue 5888F8 and white
// F0F0F0. Pink, turquoise and yellow are EAB's (#70).
#define RENDER_RGB565(r, g, b) ((uint16_t)((((r) >> 3) << 11) | (((g) >> 2) << 5) | ((b) >> 3)))
#define RENDER_BLACK RENDER_RGB565(0x00, 0x00, 0x00)
#define RENDER_GREEN RENDER_RGB565(0x50, 0xFF, 0x50)
#define RENDER_RED RENDER_RGB565(0xFF, 0x50, 0x50)
#define RENDER_BLUE RENDER_RGB565(0x5C, 0x8A, 0xFF)
#define RENDER_WHITE RENDER_RGB565(0xF0, 0xF0, 0xF0)
#define RENDER_PINK RENDER_RGB565(0xFF, 0x70, 0xFF)
#define RENDER_TURQUOISE RENDER_RGB565(0x50, 0xFF, 0xFF)
#define RENDER_YELLOW RENDER_RGB565(0xFF, 0xFF, 0x50)
// Monochrome (#50): LizTerm's phosphor, and intensified text blended 35%
// toward white (its Palette.cs Blend); the monitor gets 30FC30 and 78FC78.
#define RENDER_PHOSPHOR RENDER_RGB565(0x33, 0xFF, 0x33)
#define RENDER_PHOSPHOR_BRIGHT RENDER_RGB565(0x7A, 0xFF, 0x7A)
// The rule and the status line under it, in one colour as on the 3483-V
// (#95), which keeps it blue under any colour mapping (Oct 10, #50).
#define RENDER_STATUS_COLOUR RENDER_BLUE

typedef struct {
    uint16_t width;  // active pixels: 640 or 720
    uint8_t cell_w;  // 8 or 9
} render_layout_t;

extern const render_layout_t render_640x480;
extern const render_layout_t render_720x480;

// One cell of the built row, as each line of it needs it.
typedef struct {
    union {  // the drawn code's glyph in the frame's font: its line n is rows8[n] or rows9[n]
        const uint8_t *rows8;   // font_3270_8x19, for 8-dot cells
        const uint16_t *rows9;  // font_3270_9x19, for 9-dot cells
    };
    uint32_t colour;      // RGB565 in both halves: a word of two pixels
    uint16_t invert;      // reverse: all the cell's columns (0xFF or 0x1FF), else 0 (#70)
    uint16_t underscore;  // underscore: all the cell's columns, lit on RENDER_UNDERSCORE_LINE, else 0
} render_cell_t;

// One frame's inputs (#49).
typedef struct {
    const uint8_t *regen;        // REGEN_SIZE bytes, read as lines are drawn
    const uint8_t *eab;          // the REGEN_SIZE EAB bytes beside them (#70), read the same way
    uint16_t ac;                 // the address counter
    uint8_t control;             // the control register
    const settings_t *settings;  // read as the frame begins
    uint32_t frame;              // counts up a frame at a time, wrapping only at a multiple of
                                 // RENDER_FRAME_CYCLE: blink's phase comes from it
    bool dimmed;                 // auto dim is on (dim.h)
    uint16_t ruler;              // the Rule key's ruler (ruler.h, #51): RULER_OFF, or the address
                                 // counter when it came on
    bool setup;                  // SetUp's screen (#102): no indicator or ruler, no cursor but
                                 // setup_cursor, and control ignored; the status line as SetUp's bar,
                                 // reversed in white, and its title rule on row 2; dimmed, the status
                                 // line is blank but for the dim's mark (captured Oct 11)
    bool flash;                  // Alarm volume Off's flash (#107): every cell's reverse flipped, the status
                                 // line's too; not while dimmed
    uint8_t model;               // the host's model (#110): its layout; a setup frame is Model 2's whatever this says
    uint16_t setup_cursor;       // a SetUp frame's cursor cell (#122): Password Set's, or 0 for none
    bool locked;                 // the lock (#122): the host's rows blanked as display inhibit blanks them, its
                                 // cursor kept, no indicator or ruler, and the status line from status; ignored
                                 // on a setup frame, and over dimmed
    const uint8_t *status;       // the lock's status line: RENDER_COLS display codes, read as the frame begins
    int8_t status_cursor;        // the prompt's cursor column, or -1: the only cursor drawn on the status line
    bool status_bar;             // status as SetUp's white bar, with the cursor a black underline on it
} render_frame_t;

// Defined here so the caller can allocate it (video.c, statically). The
// fields are private to render.c.
typedef struct render {
    const render_layout_t *layout;
    const render_geometry_t *geometry;  // the frame's layout (#110)
    const uint8_t *regen;
    const uint8_t *eab;
    uint8_t control;
    uint16_t cursor;                  // the cell the cursor is drawn on: the counter, or RENDER_OFFSCREEN_CURSOR
    bool cursor_shown;
    bool cursor_block;                // a block, else the underscore
    bool indicator;                   // RRRR/CCC in status columns 72-79
    bool dimmed;
    bool blink_out;                   // EAB blink's glyphs are out this frame
    bool mono;                        // monochrome (#50): every cell in the phosphor
    uint16_t palette[8];              // by EAB colour code: what each is drawn as under the mapping (#50)
    uint16_t status_colour;           // the rule and the status line
    uint16_t cursor_colour;           // the cursor's underscore
    int8_t ruler_row;                 // the ruler's horizontal line, on lines 17-18 of this row, or -1 (#51)
    int8_t ruler_col;                 // its vertical line, down this column's first pixel, or -1
    uint16_t ruler_colour;            // white, the field green, or the phosphor
    bool setup;                       // a SetUp frame (#102)
    bool flash;                       // the frame's flash, off while dimmed (#107)
    bool locked;                       // a locked frame (#122)
    uint8_t status[RENDER_COLS];       // the lock's status line, copied as the frame began
    int8_t status_cursor;
    bool status_bar;
    bool flash_row;                    // the built row's flash: the status line's only, while locked
    bool row_block;                    // the built row's cursor is a block: the frame's, but the prompt's never
    uint16_t row_cursor_ink;           // and its underline's colour: the cursor's, or black on the prompt's bar
    uint8_t fold_for;                 // what fold[] holds: nothing yet (a zeroed render_t), each code as
                                      // itself, or Mono case's capitals (#107)
    uint16_t bar_colour;              // SetUp's status line bar: white, or the phosphor
    int8_t built_row;                 // the row cells[] holds: 0 to rows - 1, rows for the status line, or -1
    int8_t cursor_col;                // the built row's cursor column, or -1
    uint8_t row_field[RENDER_ROWS_MAX];      // the field attribute in force where each row starts
    uint8_t row_field_eab[RENDER_ROWS_MAX];  // and its EAB byte
    uint32_t row_ink;                 // the built row's lines with ink in any cell: bit n for line n
    render_cell_t cells[RENDER_COLS];
    uint8_t fold[256];                // the code each regen code is drawn as, by fold_for
} render_t;

size_t render_sizeof(void);  // for ctypes, which can't see sizeof

// The cell the cursor is drawn on for address counter ac at a model: ac on
// that model's screen, else RENDER_OFFSCREEN_CURSOR. The ruler's cell is
// placed the same way (#51).
uint16_t render_place(uint16_t ac, uint8_t model);

// The terminal's own RRRR/CCC for address ac on the screen, counted from 1,
// in the character set whose 0 and slash are zero and slash: display codes
// for the status line's indicator, ASCII for the console's v rule= (#51).
void render_indicator_text(unsigned ac, uint8_t text[8], uint8_t zero, uint8_t slash);

// Once per frame: the layout, and the frame's inputs. Everything but the
// regen and EAB buffers is read here; those are read as lines are drawn.
void render_frame_begin(render_t *r, const render_layout_t *layout, const render_frame_t *in);

// Line y (0-479) into pairs: layout->width / 2 words, each two RGB565
// pixels, the left one in the low half (as HSTX takes them).
void render_line(render_t *r, unsigned y, uint32_t *pairs);

#endif
