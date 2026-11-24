// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// The 3483-V's SetUp (#102). See setup_ui.h.
//
// Each screen is a table: rows, each with a label and its choices, and each
// choice where it's drawn and the value Space gives the row's settings
// field. The selector's walks, its start and what Space does all come from
// the tables, so a row the firmware gains later is one entry: its field in
// place of PINK. Rows and columns count from 1, as the row/column indicator
// does, and are read off the photos.

#include "setup_ui.h"

#include <stdatomic.h>
#include <string.h>

#include "about_text.h"
#include "display_text.h"
#include "keys3483.h"

#define CHOICES_MAX 8u  // Customization's Keyboard layout has eight (#110)
#define HEADING 0xFEu  // a row with no choices: a heading
#define PINK 0xFFu     // a row the firmware doesn't act on yet: Space sounds the alarm
_Static_assert(sizeof(settings_t) < HEADING, "every settings field's offset fits below HEADING");

#define MENU_COL 3u

// An EAB byte: bits 7-6 the highlight, 5-3 the colour (render.h).
#define EAB_OF(colour) ((uint8_t)((colour) << 3))
#define EAB_REVERSE 0x80u
#define TEXT_BLUE EAB_OF(SETTINGS_BLUE)
#define TEXT_GREEN EAB_OF(SETTINGS_GREEN)
#define TEXT_WHITE EAB_OF(SETTINGS_WHITE)
// Field attributes, which only monochrome reads here: every cell has an EAB
// colour of its own. Protected, normal or intensified (brighter in mono).
#define ATTR_NORMAL 0xE0u
#define ATTR_BRIGHT 0xE8u

#define TITLE_ROW 1u
#define INSTRUCTION_ROW 3u
#define LEGEND_ROW 24u
#define MORE_COL 72u  // "More:", then - at 78 and + at 79
#define WARNING_ROW 23u  // offline setup's warning (#110): row 23, column 2, in yellow
#define WARNING_COL 2u
#define TEXT_YELLOW EAB_OF(SETTINGS_YELLOW)
#define OPENS_NOTHING 0u     // a menu item Enter sounds the alarm for
#define OPENS_WARNING 0xFFu  // Go to offline setup: the warning first (#110)

// Password Set (#122): captures/photos-20261013/password-1-set-screen.jpg and the rest.
#define LOCK_ITEM 0u              // the menu's Lock sessions
#define OPENS_LOCK 0xFEu          // Lock sessions: the lock, or Password Set first with none set (#122)
#define PASSWORD_HEADING_COL 3u   // Lock sessions, on row 6
#define PASSWORD_ROW(f) (7u + 2u * (f))
#define PASSWORD_LABEL_COL 5u
#define PASSWORD_FIRST_DOT 15u    // two past the label's end, on the last dot's parity
#define PASSWORD_LAST_DOT 37u
#define PASSWORD_FIELD_COL 41u    // ten cells, to 50
#define MESSAGE_ROW 22u
#define MESSAGE_COL 2u
#define F11_COL 43u

// About (#126).
#define ABOUT_LAST_DOT 30u      // page 1's dot leaders, as Display Setup page 1's
#define ABOUT_VALUE_COL 33u
#define CREDIT_BY_COL 25u
#define CREDIT_LICENSE_COL 62u
#define ABOUT_TEXT_ROW 5u       // a license page's first line, from column 2
#define ABOUT_TEXT_COL 2u
_Static_assert(ABOUT_CREDITS <= 8u, "page 1's credits fit rows 12-19");
_Static_assert(ABOUT_PAGE_LINES == 18u, "a license page's lines fit rows 5-22");
_Static_assert(ABOUT_PAGES <= UINT8_MAX, "setup_ui_t's about_page counts the license pages in a uint8_t");

enum { MESSAGE_NONE, MESSAGE_INVALID, MESSAGE_CHANGED, MESSAGE_CLEARED };
static const char *const messages[] = {
    [MESSAGE_NONE] = "",
    [MESSAGE_INVALID] = "Invalid password. Password has not been changed.",
    [MESSAGE_CHANGED] = "Password has been changed.",
    [MESSAGE_CLEARED] = "Password has been cleared.",
};

typedef struct {
    uint8_t row, col;
    const char *text;
    uint8_t value;  // what Space writes into the row's field
} choice_t;

typedef struct {
    uint8_t row, col;  // the label's
    const char *label;
    uint8_t field;     // offsetof(settings_t, ...), HEADING or PINK
    uint8_t fixed;     // a PINK row's choice the firmware behaves as: drawn as set
    uint8_t count;
    choice_t choices[CHOICES_MAX];
} row_t;

typedef struct {
    const row_t *rows;
    uint8_t count;
    uint8_t last_dot;        // the column of the dot leaders' last dot
    const char *title;
    uint8_t back, forward;   // the screens F7 and F8 open, or SETUP_UI_OFF: the alarm, and no More: mark
    uint8_t parent;          // the screen F3 goes back to
    const char *legend[3];   // F3's, F7's and F8's, or NULL
} page_t;

// A settings field's offset, for a row whose field Space writes one byte
// of: one that isn't a byte, or a bool, fails the build.
#define FIELD(name)                                                                                 \
    ((uint8_t)(offsetof(settings_t, name)                                                           \
               + 0u * sizeof(struct {                                                              \
                     _Static_assert(sizeof(((settings_t *)0)->name) == 1u, #name " isn't one byte"); \
                     int unused;                                                                    \
                 })))
#define ROWS(a) ((uint8_t)(sizeof(a) / sizeof((a)[0])))
#define YES_NO(r, yes, no) {(r), (yes), "Yes", 1u}, {(r), (no), "No", 0u}

// Page 1 (setup-1-display-cursor-autodim.jpg, setup-4-display-blink-selected.jpg).
static const row_t page1_rows[] = {
    {.row = 6, .col = 3, .label = "Rule line", .field = HEADING},
    {.row = 7, .col = 5, .label = "Style", .field = FIELD(ruler_style), .count = 4,
     .choices = {{7, 33, "Horizontal", SETTINGS_RULER_HORIZONTAL}, {7, 47, "Vertical", SETTINGS_RULER_VERTICAL},
                 {7, 61, "Cross", SETTINGS_RULER_CROSS}, {7, 75, "None", SETTINGS_RULER_NONE}}},
    {.row = 8, .col = 5, .label = "Color", .field = FIELD(ruler_colour), .count = 2,
     .choices = {{8, 33, "White", SETTINGS_WHITE}, {8, 47, "Green", SETTINGS_GREEN}}},
    {.row = 9, .col = 5, .label = "Follows cursor", .field = FIELD(ruler_follows), .count = 2,
     .choices = {YES_NO(9, 33, 47)}},
    {.row = 11, .col = 3, .label = "Row/column indicator", .field = FIELD(indicator), .count = 2,
     .choices = {{11, 33, "On", 1u}, {11, 47, "Off", 0u}}},
    {.row = 13, .col = 3, .label = "Cursor", .field = HEADING},
    {.row = 14, .col = 5, .label = "Style", .field = FIELD(cursor), .count = 2,
     .choices = {{14, 33, "Underline", SETTINGS_CURSOR_UNDERLINE}, {14, 47, "Block", SETTINGS_CURSOR_BLOCK}}},
    {.row = 15, .col = 5, .label = "Blink", .field = FIELD(cursor_blink), .count = 2, .choices = {YES_NO(15, 33, 47)}},
    {.row = 17, .col = 3, .label = "Auto dim", .field = FIELD(auto_dim), .count = 2, .choices = {YES_NO(17, 33, 47)}},
    {.row = 18, .col = 5, .label = "Delay (minutes)", .field = FIELD(dim_minutes), .count = 3,
     .choices = {{18, 33, "5", 5u}, {18, 47, "10", 10u}, {18, 61, "20", 20u}}},
    {.row = 19, .col = 5, .label = "Lock sessions", .field = FIELD(lock_sessions), .count = 2,
     .choices = {YES_NO(19, 33, 47)}},
};

// Page 2 (setup-2-display-typematic-clicker.jpg), live since #107 but for Trim
// border, which frames the trim area of the Print key's Trim Print, and
// Liz4270 has no local print: its yellow is the 3483-V's own White.
#define VOLUMES(r) {(r), 46, "Off", 0u}, {(r), 60, "1", 1u}, {(r), 73, "2", 2u}, \
                   {(r) + 1, 46, "3", 3u}, {(r) + 1, 60, "4", 4u}, {(r) + 1, 73, "High", 5u}
static const row_t page2_rows[] = {
    {.row = 6, .col = 3, .label = "Typematic", .field = HEADING},
    {.row = 7, .col = 5, .label = "Rate", .field = FIELD(typematic_rate), .count = 2,
     .choices = {{7, 46, "Normal", SETTINGS_RATE_NORMAL}, {7, 60, "Fast", SETTINGS_RATE_FAST}}},
    {.row = 8, .col = 5, .label = "Delay", .field = FIELD(typematic_delay), .count = 3,
     .choices = {{8, 46, "Short", SETTINGS_DELAY_SHORT}, {8, 60, "Normal", SETTINGS_DELAY_NORMAL},
                 {8, 73, "Long", SETTINGS_DELAY_LONG}}},
    {.row = 10, .col = 3, .label = "Clicker", .field = HEADING},
    {.row = 11, .col = 5, .label = "Click", .field = FIELD(click), .count = 2, .choices = {YES_NO(11, 46, 60)}},
    {.row = 12, .col = 5, .label = "Volume", .field = FIELD(click_volume), .count = 6, .choices = {VOLUMES(12)}},
    {.row = 14, .col = 3, .label = "Alarm volume", .field = FIELD(alarm_volume), .count = 6, .choices = {VOLUMES(14)}},
    {.row = 17, .col = 3, .label = "Trim border", .field = PINK, .fixed = 0, .count = 2,
     .choices = {{17, 46, "White", 0u}, {17, 60, "Green", 1u}}},
    {.row = 19, .col = 3, .label = "Mono case", .field = FIELD(mono_case), .count = 2, .choices = {YES_NO(19, 46, 60)}},
};
_Static_assert(SETTINGS_VOLUME_HIGH == 5u, "VOLUMES' values are settings.h's");

// Page 3 (setup-3-display-colour-mapping.jpg): each row's seven colours on two lines.
#define COLOURS(r) {(r), 33, "Red", SETTINGS_RED}, {(r), 45, "Pink", SETTINGS_PINK}, \
                   {(r), 57, "Green", SETTINGS_GREEN}, {(r), 69, "Yellow", SETTINGS_YELLOW}, \
                   {(r) + 1, 33, "Blue", SETTINGS_BLUE}, {(r) + 1, 45, "Turquoise", SETTINGS_TURQUOISE}, \
                   {(r) + 1, 57, "White", SETTINGS_WHITE}
static const row_t page3_rows[] = {
    {.row = 6, .col = 3, .label = "Four base color mapping", .field = HEADING},
    {.row = 8, .col = 5, .label = "Input", .field = FIELD(colour_input), .count = 7, .choices = {COLOURS(8)}},
    {.row = 11, .col = 5, .label = "Intensified input", .field = FIELD(colour_input_hi), .count = 7,
     .choices = {COLOURS(11)}},
    {.row = 14, .col = 5, .label = "Protected", .field = FIELD(colour_protected), .count = 7,
     .choices = {COLOURS(14)}},
    {.row = 17, .col = 5, .label = "Intensified protected", .field = FIELD(colour_protected_hi), .count = 7,
     .choices = {COLOURS(17)}},
};

// Page 4: Liz4270's own (#50, #102).
static const row_t page4_rows[] = {
    {.row = 6, .col = 3, .label = "Liz4270", .field = HEADING},
    {.row = 7, .col = 5, .label = "Monochrome", .field = FIELD(mono), .count = 2, .choices = {YES_NO(7, 33, 47)}},
};

// Offline setup's Customization, its first page (offline-setup-3-customization.jpg, #110): Screen rows x
// columns is live; the rest is drawn as the firmware behaves, Standard keys, no numeric lock, a solid
// underscore, no markup and no black on white, with the other choices pink. The second page, a printer, has
// no place here: Liz4270 has no printer emulation.
static const row_t customization_rows[] = {
    {.row = 6, .col = 3, .label = "Screen rows x columns", .field = FIELD(model), .count = 3,
     .choices = {{6, 34, "24 x 80", SETTINGS_MODEL_2}, {6, 47, "32 x 80", SETTINGS_MODEL_3},
                 {6, 60, "43 x 80", SETTINGS_MODEL_4}}},
    {.row = 9, .col = 3, .label = "Keyboard layout", .field = PINK, .fixed = 0, .count = 8,
     .choices = {{9, 34, "Standard", 0u}, {9, 47, "APL", 1u}, {9, 60, "DataEntry", 2u}, {9, 73, "78EMU", 3u},
                 {10, 34, "User1", 4u}, {10, 47, "User2", 5u}, {10, 60, "User3", 6u}, {10, 73, "User4", 7u}}},
    {.row = 12, .col = 3, .label = "Numeric lock", .field = PINK, .fixed = 1, .count = 2,
     .choices = {YES_NO(12, 34, 47)}},
    {.row = 14, .col = 3, .label = "Underscore style", .field = PINK, .fixed = 1, .count = 2,
     .choices = {{14, 34, "- - -", 0u}, {14, 47, "_____", 1u}}},
    {.row = 16, .col = 3, .label = "Unprotected field", .field = HEADING},
    {.row = 17, .col = 5, .label = "Markup", .field = PINK, .fixed = 1, .count = 2, .choices = {YES_NO(17, 34, 47)}},
    {.row = 20, .col = 3, .label = "Black-On-White emulation", .field = PINK, .fixed = 1, .count = 2,
     .choices = {YES_NO(20, 34, 47)}},
};

// Each page by its screen; the menus' entries are unused.
static const page_t pages[SETUP_UI_SCREENS] = {
    [SETUP_UI_PAGE1] = {page1_rows, ROWS(page1_rows), 30u, "Display Setup", SETUP_UI_OFF, SETUP_UI_PAGE2, SETUP_UI_MENU,
                        {"F3=Exit", NULL, "F8=Forward"}},
    [SETUP_UI_PAGE2] = {page2_rows, ROWS(page2_rows), 43u, "Display Setup", SETUP_UI_PAGE1, SETUP_UI_PAGE3,
                        SETUP_UI_MENU, {"F3=Exit", "F7=Backward", "F8=Forward"}},
    [SETUP_UI_PAGE3] = {page3_rows, ROWS(page3_rows), 30u, "Display Setup", SETUP_UI_PAGE2, SETUP_UI_PAGE4,
                        SETUP_UI_MENU, {"F3=Exit", "F7=Backward", "F8=Forward"}},
    [SETUP_UI_PAGE4] = {page4_rows, ROWS(page4_rows), 30u, "Display Setup", SETUP_UI_PAGE3, SETUP_UI_OFF,
                        SETUP_UI_MENU, {"F3=Exit", "F7=Backward", NULL}},
    [SETUP_UI_CUSTOMIZE] = {customization_rows, ROWS(customization_rows), 31u, "Customization", SETUP_UI_OFF,
                            SETUP_UI_OFF, SETUP_UI_OFFLINE_MENU, {"F3=Exit", NULL, NULL}},
};

typedef struct {
    uint8_t row;
    const char *text;
    uint8_t opens;  // the screen Enter opens, OPENS_WARNING, or OPENS_NOTHING
} item_t;

typedef struct {
    const char *title;
    const item_t *items;
    uint8_t count;
} menu_t;

static const item_t online_items[SETUP_UI_MENU_ITEMS] = {
    {6u, "Lock sessions", OPENS_LOCK},          {8u, "Setup display", SETUP_UI_PAGE1},
    {10u, "Setup local functions", OPENS_NOTHING}, {12u, "Set password", SETUP_UI_PASSWORD},
    {14u, "Setup color palette", OPENS_NOTHING},   {20u, "Go to offline setup", OPENS_WARNING},
};
// offline-setup-2-menu.jpg (#110).
static const item_t offline_items[SETUP_UI_OFFLINE_ITEMS] = {
    {6u, "Customize display station", SETUP_UI_CUSTOMIZE}, {8u, "Set printer definition utility", OPENS_NOTHING},
    {10u, "Update serial number", OPENS_NOTHING},          {12u, "Test display station", OPENS_NOTHING},
};
static const menu_t online_menu = {"Online Setup and Utility", online_items, SETUP_UI_MENU_ITEMS};
static const menu_t offline_menu = {"Offline Setup", offline_items, SETUP_UI_OFFLINE_ITEMS};
static const char warning[] = "Sessions will be terminated, press Enter to continue or any other key to quit.";

static bool on_menu(const setup_ui_t *u) {
    return u->screen == SETUP_UI_MENU || u->screen == SETUP_UI_OFFLINE_MENU;
}

static const menu_t *menu_of(const setup_ui_t *u) {
    return u->screen == SETUP_UI_OFFLINE_MENU ? &offline_menu : &online_menu;
}

size_t setup_ui_sizeof(void) {
    return sizeof(setup_ui_t);
}

void setup_ui_init(setup_ui_t *u) {
    memset(u, 0, sizeof *u);
}

// src into a field of size bytes, cut to fit, with its NUL.
static void copy_field(char *field, size_t size, const char *src) {
    size_t n = 0;
    for (; src && src[n] && n < size - 1u; n++)
        field[n] = src[n];
    field[n] = '\0';
}

void setup_ui_identify(setup_ui_t *u, const char *version, const char *commit, const char *board) {
    copy_field(u->version, sizeof u->version, version);
    copy_field(u->commit, sizeof u->commit, commit);
    copy_field(u->board, sizeof u->board, board);
}

void setup_ui_open(setup_ui_t *u) {
    u->screen = SETUP_UI_MENU;
    u->selector = 0;
    u->warning = false;
    u->stats.opens++;
}

setup_ui_screen_t setup_ui_screen(const setup_ui_t *u) {
    return (setup_ui_screen_t)u->screen;
}

bool setup_ui_offline(const setup_ui_t *u) {
    return u->screen == SETUP_UI_OFFLINE_MENU || u->screen == SETUP_UI_CUSTOMIZE;
}

void setup_ui_stats(const setup_ui_t *u, setup_ui_stats_t *out) {
    *out = u->stats;
}

static const page_t *page_of(const setup_ui_t *u) {
    return &pages[u->screen];
}

// How many choices a page has.
static unsigned choice_count(const page_t *p) {
    unsigned n = 0;
    for (unsigned r = 0; r < p->count; r++)
        n += p->rows[r].count;
    return n;
}

// A page's choice i in reading order (the tables' order), with its row.
static const choice_t *choice_at(const page_t *p, unsigned i, const row_t **row) {
    for (unsigned r = 0; r < p->count; r++) {
        if (i < p->rows[r].count) {
            *row = &p->rows[r];
            return &p->rows[r].choices[i];
        }
        i -= p->rows[r].count;
    }
    *row = &p->rows[0];
    return &p->rows[0].choices[0];  // never: i is below choice_count
}

// A choice's place in a walk: by column, then row (Down and Up), or by row,
// then column (Right and Left).
static unsigned order(const choice_t *c, bool by_column) {
    return by_column ? (unsigned)c->col << 8 | c->row : (unsigned)c->row << 8 | c->col;
}

// The choice after (forward) or before the one at from in a walk, wrapping
// from the last to the first and back (captured Oct 11).
static uint8_t walk(const page_t *p, unsigned from, bool by_column, bool forward) {
    const row_t *row;
    unsigned n = choice_count(p);
    unsigned here = order(choice_at(p, from, &row), by_column);
    int next = -1, end = -1;  // the nearest past here, and where a wrap lands
    unsigned next_key = 0, end_key = 0;
    for (unsigned i = 0; i < n; i++) {
        unsigned key = order(choice_at(p, i, &row), by_column);
        bool past = forward ? key > here : key < here;
        if (past && (next < 0 || (forward ? key < next_key : key > next_key))) {
            next = (int)i;
            next_key = key;
        }
        if (end < 0 || (forward ? key < end_key : key > end_key)) {
            end = (int)i;
            end_key = key;
        }
    }
    return (uint8_t)(next >= 0 ? next : end);
}

static setup_ui_result_t alarm(setup_ui_t *u) {
    u->stats.alarms++;
    return SETUP_UI_ALARM;
}

// The keys typed into Password Set gone, their count (the asterisks) kept.
static void wipe(setup_ui_t *u) {
    memset(u->keys, 0, sizeof u->keys);
}

static void blank_fields(setup_ui_t *u) {
    wipe(u);
    u->typed[0] = u->typed[1] = 0;
    u->field = 0;
}

static void open_password(setup_ui_t *u, uint8_t opener) {
    u->screen = SETUP_UI_PASSWORD;
    u->opener = opener;
    u->message = MESSAGE_NONE;
    u->changed = false;
    blank_fields(u);
}

static setup_ui_result_t menu_key(setup_ui_t *u, uint8_t key, const settings_t *s) {
    const menu_t *m = menu_of(u);
    if (u->warning) {  // Enter goes on to offline setup; any other key quits the warning (#110)
        u->warning = false;
        if (key != K_ENTER)
            return SETUP_UI_NONE;
        u->screen = SETUP_UI_OFFLINE_MENU;  // setup_ui_offline: setup.c holds the link off the coax
        u->selector = 0;
        return SETUP_UI_NONE;
    }
    switch (key) {
    case K_DOWN:
    case K_RIGHT:
        u->selector = (uint8_t)((u->selector + 1u) % m->count);
        return SETUP_UI_NONE;
    case K_UP:
    case K_LEFT:
        u->selector = (uint8_t)((u->selector + m->count - 1u) % m->count);
        return SETUP_UI_NONE;
    case K_ENTER: {
        uint8_t opens = m->items[u->selector].opens;
        if (opens == OPENS_NOTHING)
            return alarm(u);
        if (opens == OPENS_WARNING) {
            u->warning = true;
            return SETUP_UI_NONE;
        }
        if (opens == OPENS_LOCK) {
            if (settings_password_set(s)) {  // lock-1: at once, no question
                u->screen = SETUP_UI_OFF;
                u->selector = 0;
                return SETUP_UI_LOCK;
            }
            open_password(u, u->selector);  // lock-4: Password Set first
            return SETUP_UI_NONE;
        }
        if (opens == SETUP_UI_PASSWORD) {
            open_password(u, u->selector);
            return SETUP_UI_NONE;
        }
        u->screen = opens;
        u->selector = 0;
        return SETUP_UI_NONE;
    }
    case K_PF10:  // About (#126): Online Setup and Utility's alone
        if (u->screen != SETUP_UI_MENU)
            return alarm(u);
        u->opener = u->selector;
        u->screen = SETUP_UI_ABOUT;
        u->about_page = 0;
        return SETUP_UI_NONE;
    case K_PF3: {
        bool offline = u->screen == SETUP_UI_OFFLINE_MENU;
        u->screen = SETUP_UI_OFF;
        u->selector = 0;
        return offline ? SETUP_UI_LEFT_OFFLINE : SETUP_UI_CLOSED;
    }
    default:
        return alarm(u);
    }
}

static setup_ui_result_t page_key(setup_ui_t *u, uint8_t key, settings_t *s) {
    const page_t *p = page_of(u);
    switch (key) {
    case K_DOWN:
        u->selector = walk(p, u->selector, true, true);
        return SETUP_UI_NONE;
    case K_UP:
        u->selector = walk(p, u->selector, true, false);
        return SETUP_UI_NONE;
    case K_RIGHT:
        u->selector = walk(p, u->selector, false, true);
        return SETUP_UI_NONE;
    case K_LEFT:
        u->selector = walk(p, u->selector, false, false);
        return SETUP_UI_NONE;
    case K_SPACE: {
        const row_t *row;
        const choice_t *c = choice_at(p, u->selector, &row);
        if (row->field == PINK)
            return alarm(u);
        ((uint8_t *)s)[row->field] = c->value;  // a byte field, a bool's 0 or 1 included
        // Alarm volume sounds the alarm at its new level, as the 3483-V does (Oct 12, #107).
        return row->field == offsetof(settings_t, alarm_volume) ? SETUP_UI_PREVIEW : SETUP_UI_CHANGED;
    }
    case K_PF8:
    case K_PF7: {
        uint8_t next = key == K_PF8 ? p->forward : p->back;
        if (next == SETUP_UI_OFF)
            return alarm(u);
        u->screen = next;
        u->selector = 0;
        return SETUP_UI_NONE;
    }
    case K_PF3:
        u->screen = p->parent;
        u->selector = 0;
        return SETUP_UI_NONE;
    default:
        return alarm(u);
    }
}

// About (#126): F8 and F7 page through, and F3 goes back to the menu with the selector where F10 left it.
static setup_ui_result_t about_key(setup_ui_t *u, uint8_t key) {
    switch (key) {
    case K_PF8:
        if (u->about_page == ABOUT_PAGES)
            return alarm(u);
        u->about_page++;
        return SETUP_UI_NONE;
    case K_PF7:
        if (u->about_page == 0u)
            return alarm(u);
        u->about_page--;
        return SETUP_UI_NONE;
    case K_PF3:
        u->screen = SETUP_UI_MENU;
        u->selector = u->opener;
        return SETUP_UI_NONE;
    default:
        return alarm(u);
    }
}

// Enter in the second field, or in an empty first: the two fields the same
// and not empty set the password (captured Oct 13).
static setup_ui_result_t submit(setup_ui_t *u, settings_t *s) {
    bool same = u->typed[0] > 0 && u->typed[0] == u->typed[1];
    for (unsigned i = 0; same && i < u->typed[0]; i++)
        same = u->keys[0][i].code == u->keys[1][i].code && u->keys[0][i].shift == u->keys[1][i].shift;
    if (!same) {
        u->message = MESSAGE_INVALID;
        blank_fields(u);
        return SETUP_UI_NONE;
    }
    s->password = lock_hash(u->keys[0], u->typed[0]);
    wipe(u);
    u->message = MESSAGE_CHANGED;
    u->changed = true;
    return SETUP_UI_PASSWORD_SET;
}

static setup_ui_result_t password_key(setup_ui_t *u, uint8_t key, bool shift, settings_t *s) {
    if (key == K_PF3) {
        wipe(u);
        if (u->opener == LOCK_ITEM && settings_password_set(s)) {  // Lock sessions' Password Set, once set (Oct 13)
            u->screen = SETUP_UI_OFF;
            u->selector = 0;
            return SETUP_UI_LOCK;
        }
        u->screen = SETUP_UI_MENU;
        u->selector = u->opener;
        return SETUP_UI_NONE;
    }
    if (key == K_PF11) {  // no old password asked for (Oct 13)
        s->password = SETTINGS_NO_PASSWORD;
        u->message = MESSAGE_CLEARED;
        u->changed = false;
        blank_fields(u);
        return SETUP_UI_PASSWORD_CLEARED;
    }
    if (u->changed)
        return alarm(u);  // not captured: the screen no longer holds a password to save again
    if (key == K_ENTER) {
        if (u->field == 0 && u->typed[0] > 0) {
            u->field = 1;
            return SETUP_UI_NONE;
        }
        return submit(u, s);
    }
    if (!lock_character(key) || u->typed[u->field] == LOCK_PASSWORD_MAX)
        return alarm(u);
    u->keys[u->field][u->typed[u->field]++] = (lock_key_t){key, shift};
    if (u->field == 0 && u->typed[0] == LOCK_PASSWORD_MAX)
        u->field = 1;  // full: on into the second, as the 3483-V wraps (password-10)
    return SETUP_UI_NONE;
}

setup_ui_result_t setup_ui_key(setup_ui_t *u, uint8_t key, bool shift, settings_t *s) {
    if (u->screen == SETUP_UI_OFF)
        return SETUP_UI_NONE;
    u->stats.keys++;
    if (u->screen == SETUP_UI_PASSWORD)
        return password_key(u, key, shift, s);
    if (u->screen == SETUP_UI_ABOUT)
        return about_key(u, key);
    return on_menu(u) ? menu_key(u, key, s) : page_key(u, key, s);
}

// A screen address from a row and column counted from 1.
static uint16_t address(unsigned row, unsigned col) {
    return (uint16_t)(RENDER_SCREEN_START + (row - 1u) * RENDER_COLS + (col - 1u));
}

uint16_t setup_ui_selector_at(const setup_ui_t *u) {
    if (u->screen == SETUP_UI_OFF || u->screen == SETUP_UI_PASSWORD || u->screen == SETUP_UI_ABOUT)
        return 0;
    if (on_menu(u))
        return address(menu_of(u)->items[u->selector].row, MENU_COL);
    const row_t *row;
    const choice_t *c = choice_at(page_of(u), u->selector, &row);
    return address(c->row, c->col);
}

uint16_t setup_ui_cursor_at(const setup_ui_t *u) {
    if (u->screen != SETUP_UI_PASSWORD)
        return 0;
    unsigned f = u->changed ? 1u : u->field;  // after a change, past the second field's asterisks (password-6)
    // A full field keeps it on its last cell, not the attribute after it (not captured: password-6's is shorter).
    unsigned at = u->typed[f] < LOCK_PASSWORD_MAX ? u->typed[f] : LOCK_PASSWORD_MAX - 1u;
    return address(PASSWORD_ROW(f), PASSWORD_FIELD_COL + at);
}

uint16_t setup_ui_cursor(const setup_ui_t *u) {
    return u->cursor[u->front];
}

static const uint8_t legend_cols[3] = {1u, 13u, 29u};

typedef struct {
    uint8_t *regen, *eab;
} image_t;

static void put(image_t im, uint16_t at, const char *text, uint8_t eab) {
    for (const char *p = text; *p && at < SETUP_UI_CELLS; p++, at++) {
        im.regen[at] = display_text_code((unsigned char)*p);
        im.eab[at] = eab;
    }
}

static void attribute(image_t im, uint16_t at, uint8_t attr) {
    im.regen[at] = attr;
    im.eab[at] = 0;
}

static unsigned centred(const char *text) {
    return (RENDER_COLS - strlen(text)) / 2u + 1u;
}

// Whether a choice is drawn as set: the row's field holds its value, or it's
// a PINK row's choice the firmware behaves as.
static bool is_set(const row_t *row, const choice_t *c, unsigned i, const settings_t *s) {
    if (row->field == PINK)
        return i == row->fixed;
    return ((const uint8_t *)s)[row->field] == c->value;
}

// More: on row 1, with - when there's a page before and + when there's one after.
static void more(image_t im, bool back, bool forward) {
    put(im, address(TITLE_ROW, MORE_COL), "More:", TEXT_WHITE);
    if (back)
        put(im, address(TITLE_ROW, MORE_COL + 6u), "-", TEXT_WHITE);
    if (forward)
        put(im, address(TITLE_ROW, MORE_COL + 7u), "+", TEXT_WHITE);
}

// A heading at column 3, as Display Setup's are.
static void heading(image_t im, unsigned row, const char *text) {
    attribute(im, address(row, 2u), ATTR_NORMAL);
    put(im, address(row, 3u), text, TEXT_BLUE);
}

// About's label at column 5, its dot leaders to ABOUT_LAST_DOT on its parity, and its value (#126).
static void about_value(image_t im, unsigned row, const char *label, const char *value) {
    attribute(im, address(row, 4u), ATTR_NORMAL);
    put(im, address(row, 5u), label, TEXT_GREEN);
    unsigned first = 5u + strlen(label) + 1u;
    if (first % 2u != ABOUT_LAST_DOT % 2u)
        first++;
    for (unsigned col = first; col <= ABOUT_LAST_DOT; col += 2u)
        put(im, address(row, col), ".", TEXT_GREEN);
    attribute(im, address(row, ABOUT_VALUE_COL - 1u), ATTR_NORMAL);
    put(im, address(row, ABOUT_VALUE_COL), value, TEXT_WHITE);
}

static void draw_menu(image_t im, const setup_ui_t *u) {
    const menu_t *m = menu_of(u);
    put(im, address(TITLE_ROW, centred(m->title)), m->title, TEXT_BLUE);
    put(im, address(INSTRUCTION_ROW, 1u), "Move cursor to desired selection and press ENTER.", TEXT_GREEN);
    for (unsigned i = 0; i < m->count; i++) {
        attribute(im, address(m->items[i].row, MENU_COL - 1u), ATTR_NORMAL);
        uint8_t eab = i == u->selector ? (uint8_t)(EAB_OF(SETTINGS_YELLOW) | EAB_REVERSE) : TEXT_WHITE;
        put(im, address(m->items[i].row, MENU_COL), m->items[i].text, eab);
    }
    if (u->warning)
        put(im, address(WARNING_ROW, WARNING_COL), warning, TEXT_YELLOW);
    put(im, address(LEGEND_ROW, 1u), "F3=Exit", TEXT_BLUE);
    if (u->screen == SETUP_UI_MENU)  // in the slot F7 has on Display Setup (#126)
        put(im, address(LEGEND_ROW, legend_cols[1]), "F10=About", TEXT_BLUE);
}

static void draw_page(image_t im, const setup_ui_t *u, const settings_t *s) {
    const page_t *p = page_of(u);
    put(im, address(TITLE_ROW, centred(p->title)), p->title, TEXT_BLUE);
    if (p->back != SETUP_UI_OFF || p->forward != SETUP_UI_OFF)  // Customization has no second page here (#110)
        more(im, p->back != SETUP_UI_OFF, p->forward != SETUP_UI_OFF);
    put(im, address(INSTRUCTION_ROW, 1u), "Move cursor to desired choice, then press SPACEBAR to select.", TEXT_GREEN);
    unsigned index = 0;  // each choice's place in reading order, as the selector counts
    for (unsigned r = 0; r < p->count; r++) {
        const row_t *row = &p->rows[r];
        bool is_heading = row->field == HEADING;
        attribute(im, address(row->row, row->col - 1u), ATTR_NORMAL);
        put(im, address(row->row, row->col), row->label, is_heading ? TEXT_BLUE : TEXT_GREEN);
        if (!is_heading) {
            // Dot leaders on the columns of the last dot's parity, from two past the label's end.
            unsigned first = row->col + strlen(row->label) + 1u;
            if (first % 2u != p->last_dot % 2u)
                first++;
            for (unsigned col = first; col <= p->last_dot; col += 2u)
                put(im, address(row->row, col), ".", TEXT_GREEN);
        }
        for (unsigned i = 0; i < row->count; i++, index++) {
            const choice_t *c = &row->choices[i];
            bool set = is_set(row, c, i, s);
            uint8_t colour = set ? SETTINGS_YELLOW : row->field == PINK ? SETTINGS_PINK : SETTINGS_WHITE;
            uint8_t eab = (uint8_t)(EAB_OF(colour) | (index == u->selector ? EAB_REVERSE : 0u));
            attribute(im, address(c->row, c->col - 1u), set ? ATTR_BRIGHT : ATTR_NORMAL);
            put(im, address(c->row, c->col), c->text, eab);
            attribute(im, address(c->row, c->col + strlen(c->text)), ATTR_NORMAL);
        }
    }
    for (unsigned i = 0; i < 3u; i++)
        if (p->legend[i])
            put(im, address(LEGEND_ROW, legend_cols[i]), p->legend[i], TEXT_BLUE);
}

static void draw_password(image_t im, const setup_ui_t *u) {
    static const char title[] = "Password Set";
    put(im, address(TITLE_ROW, centred(title)), title, TEXT_BLUE);
    put(im, address(INSTRUCTION_ROW, 1u), "Specify password twice and press ENTER.", TEXT_GREEN);
    attribute(im, address(PASSWORD_ROW(0) - 1u, PASSWORD_HEADING_COL - 1u), ATTR_NORMAL);
    put(im, address(PASSWORD_ROW(0) - 1u, PASSWORD_HEADING_COL), "Lock sessions", TEXT_BLUE);
    for (unsigned f = 0; f < 2u; f++) {
        unsigned row = PASSWORD_ROW(f);
        attribute(im, address(row, PASSWORD_LABEL_COL - 1u), ATTR_NORMAL);
        put(im, address(row, PASSWORD_LABEL_COL), "Password", TEXT_GREEN);
        for (unsigned col = PASSWORD_FIRST_DOT; col <= PASSWORD_LAST_DOT; col += 2u)
            put(im, address(row, col), ".", TEXT_GREEN);
        attribute(im, address(row, PASSWORD_FIELD_COL - 1u), ATTR_NORMAL);
        for (unsigned i = 0; i < LOCK_PASSWORD_MAX; i++)
            put(im, address(row, PASSWORD_FIELD_COL + i), i < u->typed[f] ? "*" : "_", TEXT_WHITE);
        attribute(im, address(row, PASSWORD_FIELD_COL + LOCK_PASSWORD_MAX), ATTR_NORMAL);
    }
    put(im, address(MESSAGE_ROW, MESSAGE_COL), messages[u->message], TEXT_YELLOW);
    put(im, address(LEGEND_ROW, 1u), "F3=Exit", TEXT_BLUE);
    put(im, address(LEGEND_ROW, F11_COL), "F11=Clear password", TEXT_BLUE);
}

// About (#126): page 1, the identity and the credits, or a license page from about_text.c.
static void draw_about(image_t im, const setup_ui_t *u) {
    static const char title[] = "About Liz4270";
    put(im, address(TITLE_ROW, centred(title)), title, TEXT_BLUE);
    more(im, u->about_page > 0u, u->about_page < ABOUT_PAGES);
    if (u->about_page == 0u) {
        put(im, address(INSTRUCTION_ROW, 1u), "Press F8 to read the licenses.", TEXT_GREEN);
        heading(im, 6u, "Firmware");
        about_value(im, 7u, "Version", u->version);
        about_value(im, 8u, "Commit", u->commit);
        about_value(im, 9u, "Board", u->board);
        heading(im, 11u, "Credits");
        for (unsigned i = 0; i < ABOUT_CREDITS; i++) {
            unsigned row = 12u + i;
            attribute(im, address(row, 4u), ATTR_NORMAL);
            put(im, address(row, 5u), about_credits[i].component, TEXT_WHITE);
            put(im, address(row, CREDIT_BY_COL), about_credits[i].by, TEXT_WHITE);
            put(im, address(row, CREDIT_LICENSE_COL), about_credits[i].license, TEXT_WHITE);
        }
        attribute(im, address(21u, 2u), ATTR_NORMAL);
        put(im, address(21u, 3u), "Named for Liz, the mainframe cat.", TEXT_WHITE);
    } else {
        const about_page_t *p = &about_pages[u->about_page - 1u];
        put(im, address(INSTRUCTION_ROW, 1u), p->heading, TEXT_GREEN);
        for (unsigned i = 0; i < p->count; i++) {
            attribute(im, address(ABOUT_TEXT_ROW + i, 1u), ATTR_NORMAL);
            put(im, address(ABOUT_TEXT_ROW + i, ABOUT_TEXT_COL), p->lines[i], TEXT_WHITE);
        }
    }
    put(im, address(LEGEND_ROW, legend_cols[0]), "F3=Exit", TEXT_BLUE);
    if (u->about_page > 0u)
        put(im, address(LEGEND_ROW, legend_cols[1]), "F7=Backward", TEXT_BLUE);
    if (u->about_page < ABOUT_PAGES)
        put(im, address(LEGEND_ROW, legend_cols[2]), "F8=Forward", TEXT_BLUE);
}

void setup_ui_draw(setup_ui_t *u, const settings_t *s) {
    unsigned back = u->front ^ 1u;
    image_t im = {u->regen[back], u->eab[back]};
    memset(im.regen, 0, SETUP_UI_CELLS);
    memset(im.eab, 0, SETUP_UI_CELLS);
    put(im, 0u, "SETUP", 0u);  // the status line, which render.c draws as SetUp's bar
    attribute(im, address(1u, 1u), ATTR_NORMAL);  // so no field wraps round from 1999 intensified
    if (on_menu(u))
        draw_menu(im, u);
    else if (u->screen == SETUP_UI_PASSWORD)
        draw_password(im, u);
    else if (u->screen == SETUP_UI_ABOUT)
        draw_about(im, u);
    else if (u->screen != SETUP_UI_OFF)
        draw_page(im, u, s);
    u->cursor[back] = setup_ui_cursor_at(u);
    // One store, after the image's: a frame begun meanwhile draws the old image whole.
    atomic_signal_fence(memory_order_release);
    u->front = (uint8_t)back;
}

const uint8_t *setup_ui_regen(const setup_ui_t *u) {
    return u->regen[u->front];
}

const uint8_t *setup_ui_eab(const setup_ui_t *u) {
    return u->eab[u->front];
}
