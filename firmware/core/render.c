// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// The screen as the Fruit Jam draws it (#26). See render.h.
//
// A row's cells are worked out once, when render_line first reaches the row:
// each cell's glyph, colour and EAB masks, the row's cursor, and which of its
// lines have ink anywhere. Each line then draws every cell from its glyph's
// row and its masks, and draws the cursor's cell again on the lines the
// cursor changes, then the ruler over them (#51).

#include <stdbool.h>

#include "font_3270.h"
#include "pixels.h"
#include "render.h"

#define ATTRIBUTE 0xC0u        // codes from here are field attributes in the screen area
#define UNFORMATTED 0xC0u      // no attribute anywhere: unprotected, normal
#define FIELD_PROTECTED 0x20u
#define FIELD_DISPLAY(a) (((a) >> 2) & 3u)
#define DISPLAY_INTENSIFIED 2u
#define DISPLAY_NONE 3u
#define CODE_BLANK 0x00u
#define CODE_DIGIT_0 0x20u
#define CODE_SLASH 0x14u

// An EAB byte's highlight and colour (render.h, "EAB").
#define EAB_HIGHLIGHT(e) ((unsigned)(e) >> 6)
#define EAB_COLOUR(e) (((unsigned)(e) >> 3) & 7u)
#define HIGHLIGHT_NONE 0u
#define HIGHLIGHT_BLINK 1u
#define HIGHLIGHT_REVERSE 2u
#define HIGHLIGHT_UNDERSCORE 3u
#define FOLD_NONE 0u           // render_t's fold_for: fold[] not built yet,
#define FOLD_SAME 1u           // each code as itself,
#define FOLD_CASE 2u           // or Mono case's (#107)

#define INDICATOR_COL 72u                    // RRRR/CCC in columns 72-79

const render_layout_t render_640x480 = {640u, 8u};
const render_layout_t render_720x480 = {720u, 9u};

// Each EAB colour code's colour before the mapping (#50), by bits 5-3 of an
// EAB byte; 0 takes the field's. render_frame_begin builds the frame's
// palette from it.
static const uint16_t eab_colours[8] = {
    0u, RENDER_BLUE, RENDER_RED, RENDER_PINK, RENDER_GREEN, RENDER_TURQUOISE, RENDER_YELLOW, RENDER_WHITE,
};

// Each model's layout (#110): the rows bottom-aligned above the rule's gap,
// the status line a row tall at the bottom, and the cursor on a cell's last
// two lines, or its last at 10 lines, where line 7 holds the letters' bottom
// row, with an EAB underscore on the line above it.
const render_geometry_t render_model_2 = {
    .rows = 24u, .cell_h = 19u, .top = 0u, .gap_y = 456u, .rule_y = 457u, .status_y = 461u, .screen_end = 2000u,
    .underscore_line = 16u, .cursor_first = 17u,
    .nine = &font_3270_9x19[0][0], .eight = &font_3270_8x19[0][0], .ink = font_3270_ink,
};
const render_geometry_t render_model_3 = {
    .rows = 32u, .cell_h = 14u, .top = 13u, .gap_y = 461u, .rule_y = 462u, .status_y = 466u, .screen_end = 2640u,
    .underscore_line = 11u, .cursor_first = 12u,
    .nine = &font_3270_9x14[0][0], .eight = &font_3270_8x14[0][0], .ink = font_3270_ink14,
};
const render_geometry_t render_model_4 = {
    .rows = 43u, .cell_h = 10u, .top = 35u, .gap_y = 465u, .rule_y = 466u, .status_y = 470u, .screen_end = 3520u,
    .underscore_line = 8u, .cursor_first = 9u,
    .nine = &font_3270_9x10[0][0], .eight = &font_3270_8x10[0][0], .ink = font_3270_ink10,
};
_Static_assert(RENDER_ROWS == 24u && RENDER_CELL_H == 19u && RENDER_RULE_Y == 457u && RENDER_STATUS_Y == 461u
                   && RENDER_SCREEN_END == 2000u,
               "render_model_2 is the layout render.h's constants name");

const render_geometry_t *render_geometry(uint8_t model) {
    if (model == 3u)
        return &render_model_3;
    if (model == 4u)
        return &render_model_4;
    return &render_model_2;
}

// A cell's lines, all lit: what a reversed cell has ink on.
static inline uint32_t all_lines(const render_geometry_t *g) {
    return (1u << g->cell_h) - 1u;
}

size_t render_sizeof(void) {
    return sizeof(render_t);
}

uint16_t render_place(uint16_t ac, uint8_t model) {
    return ac >= RENDER_SCREEN_START && ac < render_geometry(model)->screen_end ? ac : RENDER_OFFSCREEN_CURSOR;
}

// What a mapping slot draws its colour as: the colour it holds, or its own if
// it holds one SetUp doesn't offer. settings_valid keeps those out, but the
// renderer mustn't read past eab_colours[] whatever it's given.
static uint16_t mapped(uint8_t colour, unsigned slot) {
    return eab_colours[settings_colour_valid(colour) ? (unsigned)colour : slot];
}

// A field's base colour as an EAB colour code: green, red, blue or white by
// protection and intensify (concept.md).
static unsigned field_code(uint8_t field) {
    bool intensified = FIELD_DISPLAY(field) == DISPLAY_INTENSIFIED;
    if (field & FIELD_PROTECTED)
        return intensified ? SETTINGS_WHITE : SETTINGS_BLUE;
    return intensified ? SETTINGS_RED : SETTINGS_GREEN;
}

// A cell's colour from its field and its EAB colour code (0 for the field's):
// the frame's palette, or in monochrome the phosphor, brighter in an
// intensified field whatever the code (#50).
static uint16_t cell_colour(const render_t *r, uint8_t field, unsigned code) {
    if (r->mono)
        return FIELD_DISPLAY(field) == DISPLAY_INTENSIFIED ? RENDER_PHOSPHOR_BRIGHT : RENDER_PHOSPHOR;
    return r->palette[code ? code : field_code(field)];
}

// Mono case (#107): the 3483-V draws each lower case code as the one 20 above
// it, 40-5F as 60-7F and 80-9F as A0-BF, on the host's screen and status line,
// never on SetUp's (captured Oct 12). Field Mark and DUP lose their overbars.
// fold[] gives each code as drawn, so a cell costs one load either way; it's
// built again only when Mono case or a SetUp frame changes which it is.
static void build_fold(render_t *r, uint8_t fold_for) {
    if (r->fold_for == fold_for)
        return;
    for (unsigned code = 0; code < 256u; code++) {
        unsigned band = code & 0xE0u;
        bool lower = band == 0x40u || band == 0x80u;
        r->fold[code] = (uint8_t)(fold_for == FOLD_CASE && lower ? code | 0x20u : code);
    }
    r->fold_for = fold_for;
}

void render_frame_begin(render_t *r, const render_layout_t *layout, const render_frame_t *in) {
    const uint8_t *regen = in->regen;
    const uint8_t *eab = in->eab;
    r->layout = layout;
    r->regen = regen;
    r->eab = eab;
    // The host's screen at its model's layout, SetUp's always at Model 2's (#110).
    uint8_t model = in->setup ? SETTINGS_MODEL_2 : in->model;
    const render_geometry_t *g = render_geometry(model);
    r->geometry = g;
    // SetUp's image (#102) is its own, so the host's control register has no
    // say in it: display inhibit doesn't blank its rows.
    uint8_t control = in->setup ? 0u : in->control;
    r->control = control;
    // The lock (#122): never over SetUp's own image.
    r->locked = in->locked && !in->setup;
    r->cursor = render_place(in->ac, model);
    const settings_t *s = in->settings;
    bool blinking = s->cursor_blink != ((control & RENDER_BLINK) != 0);
    bool out = blinking && (in->frame / RENDER_BLINK_FRAMES) % 2u == 1u;
    r->cursor_shown = !(control & RENDER_CURSOR_INHIBIT) && !out;
    r->cursor_block = (s->cursor == SETTINGS_CURSOR_BLOCK) != ((control & RENDER_REVERSE_CURSOR) != 0);
    r->dimmed = in->dimmed && !r->locked;  // locked, auto dim never blanks (Oct 13): the lock wins
    r->indicator = s->indicator && !r->dimmed && !r->locked;
    r->blink_out = (in->frame / RENDER_BLINK_FRAMES) % 4u == RENDER_EAB_BLINK_OUT;
    // The mapping swaps green, red, blue and white wherever they're drawn,
    // once; the rule, the status line and the cursor's underscore keep
    // theirs, and monochrome draws all of it in the phosphor (#50).
    for (unsigned c = 0; c < 8u; c++)
        r->palette[c] = eab_colours[c];
    r->palette[SETTINGS_GREEN] = mapped(s->colour_input, SETTINGS_GREEN);
    r->palette[SETTINGS_RED] = mapped(s->colour_input_hi, SETTINGS_RED);
    r->palette[SETTINGS_BLUE] = mapped(s->colour_protected, SETTINGS_BLUE);
    r->palette[SETTINGS_WHITE] = mapped(s->colour_protected_hi, SETTINGS_WHITE);
    r->mono = s->mono;
    r->status_colour = s->mono ? RENDER_PHOSPHOR : RENDER_STATUS_COLOUR;
    r->cursor_colour = s->mono ? RENDER_PHOSPHOR : RENDER_WHITE;
    // The Rule key's ruler (#51): the row of its horizontal line and the
    // column of its vertical one, from its cell, placed as the cursor is; -1
    // for none. A style SetUp doesn't offer draws nothing, and a colour other
    // than green is white, as the cursor's.
    bool horizontal = s->ruler_style == SETTINGS_RULER_HORIZONTAL || s->ruler_style == SETTINGS_RULER_CROSS;
    bool vertical = s->ruler_style == SETTINGS_RULER_VERTICAL || s->ruler_style == SETTINGS_RULER_CROSS;
    uint16_t at = in->setup || r->locked ? RULER_OFF : ruler_address(in->ruler, in->ac, s->ruler_follows);
    unsigned ruler_cell = at == RULER_OFF ? 0u : render_place(at, model) - RENDER_SCREEN_START;
    r->ruler_row = at != RULER_OFF && horizontal ? (int8_t)(ruler_cell / RENDER_COLS) : -1;
    r->ruler_col = at != RULER_OFF && vertical ? (int8_t)(ruler_cell % RENDER_COLS) : -1;
    r->ruler_colour = s->mono ? RENDER_PHOSPHOR : s->ruler_colour == SETTINGS_GREEN ? RENDER_GREEN : RENDER_WHITE;
    // SetUp's screen (#102): no cursor and no indicator, and its own status line.
    r->setup = in->setup;
    r->bar_colour = s->mono ? RENDER_PHOSPHOR : RENDER_WHITE;
    build_fold(r, s->mono_case && !in->setup ? FOLD_CASE : FOLD_SAME);
    r->flash = in->flash && !r->dimmed;
    if (in->setup) {
        // Password Set's cursor (#122), drawn as the host's is under the
        // settings, with no control register: the only SetUp screen with one.
        r->cursor = in->setup_cursor;
        r->cursor_shown = in->setup_cursor != 0 && !out;
        r->indicator = false;
    }
    if (r->locked) {
        for (unsigned c = 0; c < RENDER_COLS; c++)
            r->status[c] = in->status[c];
        r->status_cursor = in->status_cursor;
        r->status_bar = in->status_bar;
    }
    r->built_row = -1;

    // Attributes govern round from 1999 to 80, so the field in force at 80 is
    // the last attribute in the screen area, with its EAB byte.
    uint8_t field = UNFORMATTED;
    uint8_t field_eab = 0;
    for (unsigned a = g->screen_end; a-- > RENDER_SCREEN_START;) {
        if (regen[a] >= ATTRIBUTE) {
            field = regen[a];
            field_eab = eab[a];
            break;
        }
    }
    for (unsigned row = 0; row < g->rows; row++) {
        r->row_field[row] = field;
        r->row_field_eab[row] = field_eab;
        unsigned first = RENDER_SCREEN_START + row * RENDER_COLS;
        for (unsigned col = 0; col < RENDER_COLS; col++)
            if (regen[first + col] >= ATTRIBUTE) {
                field = regen[first + col];
                field_eab = eab[first + col];
            }
    }
}

// Cell col of the built row shows code in colour, reversed or underscored by
// highlight (HIGHLIGHT_NONE, _REVERSE or _UNDERSCORE: blink is worked out
// before). Returns the cell's lines with ink. Always inlined: it runs for
// every cell of a row, and once the layout came in (#110) GCC stopped
// inlining it, which cost about 1.2 us a line on the logon at 640 and 720.
static inline __attribute__((always_inline)) uint32_t set_cell(render_t *r, unsigned col, uint8_t code, uint16_t colour, unsigned highlight) {
    const render_geometry_t *g = r->geometry;
    render_cell_t *cell = &r->cells[col];
    uint16_t full;
    if (r->layout->cell_w == 9u) {
        cell->rows9 = g->nine + code * g->cell_h;
        full = 0x1FFu;
    } else {
        cell->rows8 = g->eight + code * g->cell_h;
        full = 0xFFu;
    }
    cell->colour = colour * 0x00010001u;
    // The flash flips every cell's reverse (#107): the cost of a screen of reversed cells.
    bool inverted = (highlight == HIGHLIGHT_REVERSE) != r->flash_row;
    cell->invert = inverted ? full : 0u;
    cell->underscore = highlight == HIGHLIGHT_UNDERSCORE ? full : 0u;
    if (inverted)
        return all_lines(g);
    return g->ink[code] | (highlight == HIGHLIGHT_UNDERSCORE ? 1u << g->underscore_line : 0u);
}

// cells[] holds addresses first to first + 79. The host's cursor is always on
// the screen (r->cursor), so never on the status line's 0-79; the lock's
// prompt has its own (build_status_row).
static void find_cursor(render_t *r, unsigned first) {
    bool here = r->cursor_shown && r->cursor >= first && r->cursor < first + RENDER_COLS;
    r->cursor_col = here ? (int8_t)(r->cursor - first) : -1;
}

// Each cell's colour and highlight (render.h, "EAB"), and its glyph: the
// blank one when non-display, display inhibit or auto dim blanks it, or while
// blink is out. Those drop the highlight and keep the colour for a block cursor.
static void build_screen_row(render_t *r, unsigned row) {
    r->flash_row = r->flash && !r->locked;  // locked, nothing behind the lock shows (#122)
    r->row_block = r->cursor_block;
    r->row_cursor_ink = r->cursor_colour;
    unsigned first = RENDER_SCREEN_START + row * RENDER_COLS;
    bool inhibit = (r->control & RENDER_DISPLAY_INHIBIT) || r->dimmed || r->locked;
    uint8_t field = r->row_field[row];
    uint8_t field_eab = r->row_field_eab[row];
    uint32_t ink = 0;
    for (unsigned col = 0; col < RENDER_COLS; col++) {
        uint8_t code = r->fold[r->regen[first + col]];
        uint8_t eab = r->eab[first + col];
        if (code >= ATTRIBUTE) {
            field = code;
            field_eab = eab;
            // A reverse cursor on an attribute is an unformatted screen's
            // colour: green as mapped, or the phosphor, as in screen.py (#50).
            ink |= set_cell(r, col, CODE_BLANK, cell_colour(r, UNFORMATTED, 0u), HIGHLIGHT_NONE);
            continue;
        }
        unsigned colour = EAB_COLOUR(eab) ? EAB_COLOUR(eab) : EAB_COLOUR(field_eab);
        unsigned highlight = EAB_HIGHLIGHT(eab) ? EAB_HIGHLIGHT(eab) : EAB_HIGHLIGHT(field_eab);
        bool blank = inhibit || FIELD_DISPLAY(field) == DISPLAY_NONE;
        if (blank || highlight == HIGHLIGHT_BLINK) {
            blank = blank || r->blink_out;
            highlight = HIGHLIGHT_NONE;
        }
        ink |= set_cell(r, col, blank ? CODE_BLANK : code, cell_colour(r, field, colour), highlight);
    }
    r->row_ink = ink;
    find_cursor(r, first);
}

void render_indicator_text(unsigned ac, uint8_t text[8], uint8_t zero, uint8_t slash) {
    unsigned at = ac - RENDER_SCREEN_START;
    unsigned row = at / RENDER_COLS + 1u, col = at % RENDER_COLS + 1u;
    text[0] = (uint8_t)(zero + row / 1000u % 10u);
    text[1] = (uint8_t)(zero + row / 100u % 10u);
    text[2] = (uint8_t)(zero + row / 10u % 10u);
    text[3] = (uint8_t)(zero + row % 10u);
    text[4] = slash;
    text[5] = (uint8_t)(zero + col / 100u % 10u);
    text[6] = (uint8_t)(zero + col / 10u % 10u);
    text[7] = (uint8_t)(zero + col % 10u);
}

// The status line is in the rule's blue, as on the 3483-V (#95), under any
// colour mapping, or in the phosphor in monochrome (#50). It ignores EAB:
// oec writes 0 there. SetUp's (#102) is its bar instead, and dimmed it's
// blank but for the mark.
static void build_status_row(render_t *r) {
    // The row/column indicator, of the cell the cursor is drawn on, in columns 72-79.
    uint8_t text[8];
    render_indicator_text(r->cursor, text, CODE_DIGIT_0, CODE_SLASH);
    r->flash_row = r->flash;
    uint32_t ink = 0;
    for (unsigned col = 0; col < RENDER_COLS; col++) {
        uint8_t code = r->indicator && col >= INDICATOR_COL ? text[col - INDICATOR_COL] : r->fold[r->regen[col]];
        uint16_t colour = r->status_colour;
        unsigned highlight = HIGHLIGHT_NONE;
        if (r->locked) {
            code = r->status[col];  // the lock's own line (#122)
            if (r->status_bar) {
                colour = r->bar_colour;
                highlight = HIGHLIGHT_REVERSE;
            }
        } else if (r->setup && !r->dimmed) {
            colour = r->bar_colour;  // SetUp's bar: the line reversed in white (captured Oct 11)
            highlight = HIGHLIGHT_REVERSE;
        } else if (r->setup) {
            code = CODE_BLANK;  // dimmed, SetUp's status line is blank but for the mark
        }
        if (r->dimmed && col == RENDER_DIM_MARK_COL)
            code = RENDER_DIM_MARK;
        ink |= set_cell(r, col, code, colour, highlight);
    }
    r->row_ink = ink;
    if (r->locked && r->status_cursor >= 0 && r->status_cursor < (int)RENDER_COLS) {
        // The prompt's cursor (lock-2): an underline, black on SetUp's bar.
        r->cursor_col = r->status_cursor;
        r->row_block = false;
        r->row_cursor_ink = r->status_bar ? RENDER_BLACK : r->cursor_colour;
    } else {
        find_cursor(r, 0);
        r->row_block = r->cursor_block;
        r->row_cursor_ink = r->cursor_colour;
    }
}

// All ones on the layout's EAB underscore line, else 0: the line's mask for underscored cells.
static inline uint32_t underscore_on(const render_t *r, unsigned line) {
    return line == r->geometry->underscore_line ? ~0u : 0u;
}

// A line of a cell as drawn: its glyph's row, inverted for reverse, with the
// underscore on its line.
static inline uint32_t cell_bits(const render_cell_t *cell, uint32_t glyph, uint32_t ul) {
    return (glyph ^ cell->invert) | (cell->underscore & ul);
}

// Every cell as drawn: the cursor's change comes after (draw_cursor).
static void draw_8(const render_t *r, unsigned line, uint32_t *out) {
    uint32_t ul = underscore_on(r, line);
    for (const render_cell_t *cell = r->cells; cell < r->cells + RENDER_COLS; cell++, out += 4)
        pixels_put_8(out, cell_bits(cell, cell->rows8[line], ul), cell->colour);
}

static void draw_9(const render_t *r, unsigned line, uint32_t *out) {
    uint32_t ul = underscore_on(r, line);
    for (const render_cell_t *a = r->cells; a < r->cells + RENDER_COLS; a += 2, out += 9)
        pixels_put_9_pair(out, cell_bits(&a[0], a[0].rows9[line], ul), a[0].colour,
                          cell_bits(&a[1], a[1].rows9[line], ul), a[1].colour);
}

// A line of the cursor's cell with its change, from the cell's drawn bits:
// full is the cell's columns, all lit. The block inverts the cell as drawn,
// as the 3483-V does (#70).
static uint32_t cursor_bits(const render_t *r, unsigned line, uint32_t bits, uint32_t full) {
    if (r->row_block)
        return ~bits & full;
    if (line >= r->geometry->cursor_first)
        return full;
    return bits;
}

// The cursor's cell again, over the plain one, on the lines the cursor
// changes. A 9-dot cell shares its middle word with its pair, so the pair is
// drawn again. The underscore is white in any field and under any mapping,
// as the 3483-V draws it, or the phosphor in monochrome (#50); the reverse
// cursor is the cell's colour.
static void draw_cursor(const render_t *r, unsigned line, uint32_t *pairs) {
    bool reverse = r->row_block;
    if (!reverse && line < r->geometry->cursor_first)
        return;
    unsigned col = (unsigned)r->cursor_col;
    uint32_t ul = underscore_on(r, line);
    uint32_t ink = r->row_cursor_ink * 0x00010001u;
    if (r->layout->cell_w == 9u) {
        const render_cell_t *a = &r->cells[col & ~1u], *b = a + 1;
        uint32_t bits_a = cell_bits(a, a->rows9[line], ul), bits_b = cell_bits(b, b->rows9[line], ul);
        uint32_t colour_a = a->colour, colour_b = b->colour;
        if (col & 1u) {
            bits_b = cursor_bits(r, line, bits_b, 0x1FFu);
            colour_b = reverse ? colour_b : ink;
        } else {
            bits_a = cursor_bits(r, line, bits_a, 0x1FFu);
            colour_a = reverse ? colour_a : ink;
        }
        pixels_put_9_pair(pairs + col / 2u * 9u, bits_a, colour_a, bits_b, colour_b);
    } else {
        const render_cell_t *cell = &r->cells[col];
        pixels_put_8(pairs + col * 4u, cursor_bits(r, line, cell_bits(cell, cell->rows8[line], ul), 0xFFu),
                     reverse ? cell->colour : ink);
    }
}

// Pixel x of a line in colour: the low half of its word for an even x, the
// high half for an odd one.
static inline void put_pixel(uint32_t *pairs, unsigned x, uint16_t colour) {
    unsigned shift = (x & 1u) * 16u;
    pairs[x / 2u] = (pairs[x / 2u] & ~(0xFFFFu << shift)) | (uint32_t)colour << shift;
}

// The ruler (#51) over a screen row's line as drawn: its dots in its colour,
// the rest left alone. The horizontal line lights pixels 4n and 4n+1 on the
// cursor's lines of its row; the vertical one its column's first pixel on even
// lines. On the lines the cursor draws (the underscore's, or every line for
// the block) the cursor's cell is left out, so the cursor shows whole over it, as
// on the 3483-V (captured Oct 10).
static void draw_ruler(const render_t *r, unsigned row, unsigned line, unsigned y, uint32_t *pairs) {
    unsigned cell_w = r->layout->cell_w;
    unsigned skip_from = 0u, skip_to = 0u;  // the cursor's pixels on this line, if it draws on it
    if (r->cursor_col >= 0 && (r->row_block || line >= r->geometry->cursor_first)) {
        skip_from = (unsigned)r->cursor_col * cell_w;
        skip_to = skip_from + cell_w;
    }
    if (r->ruler_row == (int)row && line >= r->geometry->cursor_first) {
        // A dot is pixels 4n and 4n+1: word 2n. The dots clear of the
        // cursor's cell are a word store each, in two tight runs; only the
        // one or two words the cell cuts go pixel by pixel.
        uint32_t ink = r->ruler_colour * 0x00010001u;
        unsigned words = r->layout->width / 2u;
        unsigned before = (skip_from + 2u) / 4u * 2u;  // the first dot word that reaches the cell
        unsigned after = (skip_to + 3u) / 4u * 2u;     // the first wholly past it
        for (unsigned w = 0; w < before; w += 2u)
            pairs[w] = ink;
        for (unsigned w = before; w < after; w += 2u) {
            if (2u * w < skip_from)
                put_pixel(pairs, 2u * w, r->ruler_colour);
            if (2u * w + 1u >= skip_to)
                put_pixel(pairs, 2u * w + 1u, r->ruler_colour);
        }
        for (unsigned w = after; w < words; w += 2u)
            pairs[w] = ink;
    }
    if (r->ruler_col >= 0 && y % 2u == 0u) {
        unsigned x = (unsigned)r->ruler_col * cell_w;
        if (x < skip_from || x >= skip_to)
            put_pixel(pairs, x, r->ruler_colour);
    }
}

void render_line(render_t *r, unsigned y, uint32_t *pairs) {
    const render_geometry_t *g = r->geometry;
    unsigned words = r->layout->width / 2u;
    if (y >= RENDER_LINES)
        return;
    if (r->setup && !r->dimmed && y >= RENDER_TITLE_RULE_Y && y < RENDER_TITLE_RULE_Y + RENDER_RULE_H) {
        pixels_fill(pairs, words, r->status_colour * 0x00010001u);  // SetUp's title rule (#102)
        return;
    }
    if (y < g->top) {
        pixels_fill(pairs, words, 0u);  // the band above a shorter screen's rows (#110)
        return;
    }
    if (y >= g->gap_y && y < g->status_y) {
        bool rule = y >= g->rule_y && y < g->rule_y + RENDER_RULE_H;
        pixels_fill(pairs, words, rule ? r->status_colour * 0x00010001u : 0u);
        return;
    }

    int status_row = (int)g->rows;
    int row = y < g->gap_y ? (int)((y - g->top) / g->cell_h) : status_row;
    unsigned line = y < g->gap_y ? (y - g->top) % g->cell_h : y - g->status_y;
    if (r->built_row != row) {
        if (row == status_row)
            build_status_row(r);
        else
            build_screen_row(r, (unsigned)row);
        r->built_row = (int8_t)row;
    }
    // Every cell as drawn, then the cursor's cell over it. A line no cell in
    // the row has ink on is all black, so it's a fill.
    if (!((r->row_ink >> line) & 1u))
        pixels_fill(pairs, words, 0u);
    else if (r->layout->cell_w == 9u)
        draw_9(r, line, pairs);
    else
        draw_8(r, line, pairs);
    if (r->cursor_col >= 0)
        draw_cursor(r, line, pairs);
    if (row != status_row && (r->ruler_row >= 0 || r->ruler_col >= 0))
        draw_ruler(r, (unsigned)row, line, y, pairs);
}
