// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// The 3483-V's SetUp (#102): Online Setup and Utility's menu and Display
// Setup's three pages, as photographed (captures/photos-20261006/setup-*.jpg,
// photos-20261011/setup-*.jpg), and a fourth page for monochrome, which the
// 3483-V lacks, with the keys that walk them, as probed on Oct 11
// (captures/README.md). Spec:
// docs/superpowers/specs/2026-10-11-setup-screen-design.md. And offline
// setup's way in, its menu and Customization's first page (#110),
// photographed Oct 12 (captures/photos-20261012/offline-setup-*.jpg). And
// About Liz4270 (#126), Liz4270's own: F10 from Online Setup and Utility, the
// firmware's version, commit and board with the credits, then every license
// the binary is under (about_text.h).
//
// Plain C11, like the rest of the core, so tools/sim tests it through ctypes.
// The firmware keeps one in setup.c, on core 0: its main loop hands it keys
// and draws it, and the renderer's IRQ reads its front image as lines are
// drawn.

#ifndef LIZ_SETUP_UI_H
#define LIZ_SETUP_UI_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "lock.h"
#include "render.h"
#include "settings.h"

#define SETUP_UI_CELLS RENDER_SCREEN_END  // an image: the status line at 0-79 and the 24 rows, as render.c reads them
#define SETUP_UI_MENU_ITEMS 6u     // Online Setup and Utility's
#define SETUP_UI_OFFLINE_ITEMS 4u  // Offline Setup's (#110)
#define SETUP_UI_VERSION_MAX 16u  // About's page 1 (#126): setup_ui_identify's fields, each with its NUL
#define SETUP_UI_COMMIT_MAX 24u
#define SETUP_UI_BOARD_MAX 32u

typedef enum {
    SETUP_UI_OFF = 0,
    SETUP_UI_MENU = 1,
    SETUP_UI_PAGE1 = 2,
    SETUP_UI_PAGE2 = 3,
    SETUP_UI_PAGE3 = 4,
    SETUP_UI_PAGE4 = 5,
    SETUP_UI_OFFLINE_MENU = 6,  // offline setup (#110): its menu
    SETUP_UI_CUSTOMIZE = 7,     // and Customization's first page
    SETUP_UI_PASSWORD = 8,      // Password Set (#122)
    SETUP_UI_ABOUT = 9,         // About Liz4270 (#126): F10 from the menu, page 1 then the licenses
    SETUP_UI_SCREENS,           // how many there are: keep it last
} setup_ui_screen_t;

typedef enum {
    SETUP_UI_NONE = 0,     // the selector moved or the screen changed: draw again
    SETUP_UI_ALARM = 1,    // a key SetUp can't use: sound the alarm, as the 3483-V does
    SETUP_UI_CHANGED = 2,  // Space set a field of the settings: draw again
    SETUP_UI_CLOSED = 3,   // F3 from the menu: SetUp is off, and its changes are to be saved
    SETUP_UI_PREVIEW = 4,  // Space set Alarm volume: draw again, and sound the alarm at its new level (#107)
    SETUP_UI_LEFT_OFFLINE = 5,  // F3 from the Offline Setup menu (#110): as CLOSED, and the link to come back
                                // with a power-on reset, SetUp's image up until it does
    SETUP_UI_PASSWORD_SET = 6,      // Password Set's two fields matched (#122): the hash is in the live record, to
                                    // be saved at once
    SETUP_UI_PASSWORD_CLEARED = 7,  // F11 on Password Set: the live record's password is cleared, likewise
    SETUP_UI_LOCK = 8,              // the menu's Lock sessions with a password set, or F3 on the Password Set it
                                    // opened once one is (#122): SetUp is off, and the terminal is to lock
} setup_ui_result_t;

typedef struct {
    uint32_t opens;   // setup_ui_open calls
    uint32_t keys;    // keys handed to it while it was up
    uint32_t alarms;  // of those, the ones it sounded the alarm for
} setup_ui_stats_t;

// Defined here so the caller can allocate it (setup.c, statically). The
// fields are private to setup_ui.c.
typedef struct setup_ui {
    uint8_t screen;          // a setup_ui_screen_t
    uint8_t selector;        // the menu's item, or the page's choice in reading order
    bool warning;            // the menu's offline setup warning is up (#110)
    // Password Set (#122).
    uint8_t field;                           // the field the cursor is in: 0 or 1
    uint8_t typed[2];                        // the keys in each
    lock_key_t keys[2][LOCK_PASSWORD_MAX];   // and what they were, wiped once hashed
    uint8_t message;                         // the message on row 22: setup_ui.c's MESSAGE_*
    bool changed;                            // Password has been changed: keys and Enter sound the alarm
    uint8_t opener;                          // the menu item that opened it, or the selector F10 left (#126), for F3
    // About (#126).
    uint8_t about_page;                      // 0 for page 1, then each license page
    char version[SETUP_UI_VERSION_MAX];      // setup_ui_identify's, cut to fit
    char commit[SETUP_UI_COMMIT_MAX];
    char board[SETUP_UI_BOARD_MAX];
    uint16_t cursor[2];                      // each image's cursor cell, 0 for none
    volatile uint8_t front;  // the image the renderer draws: 0 or 1, read from its IRQ
    uint8_t regen[2][SETUP_UI_CELLS];
    uint8_t eab[2][SETUP_UI_CELLS];
    setup_ui_stats_t stats;
} setup_ui_t;

size_t setup_ui_sizeof(void);  // for ctypes, which can't see sizeof

// Off, with both images blank.
void setup_ui_init(setup_ui_t *u);

// About's page 1 (#126): the firmware's version number, its commit and its board, each copied and cut to fit
// its field. setup_ui_init leaves them empty.
void setup_ui_identify(setup_ui_t *u, const char *version, const char *commit, const char *board);

// Alt+ExSel: the menu, with the selector on its first item, Lock sessions.
void setup_ui_open(setup_ui_t *u);

// One key, a 3483-V code (K_* in keys3483.h), with whether it went with
// Shift (Password Set counts case, #122), while SetUp is up; Space writes a
// field of the live settings s, and Password Set its password. Off, it does
// nothing and returns SETUP_UI_NONE.
setup_ui_result_t setup_ui_key(setup_ui_t *u, uint8_t key, bool shift, settings_t *s);

setup_ui_screen_t setup_ui_screen(const setup_ui_t *u);

// Whether offline setup is up (#110): its menu or Customization. setup.c
// holds the coax link offline meanwhile.
bool setup_ui_offline(const setup_ui_t *u);

// The address of the selected item's or choice's first cell (as the renderer
// counts them, the 24 rows from 80), or 0 while SetUp is off or on Password
// Set, which has none.
uint16_t setup_ui_selector_at(const setup_ui_t *u);

// Password Set's cursor cell (#122), where the next key goes, or 0 on every
// other screen: the only SetUp screen with a cursor.
uint16_t setup_ui_cursor_at(const setup_ui_t *u);

// The front image's cursor cell, as setup_ui_draw found it: the renderer draws
// it with that image.
uint16_t setup_ui_cursor(const setup_ui_t *u);

void setup_ui_stats(const setup_ui_t *u, setup_ui_stats_t *out);

// Builds the screen under s into the image the renderer isn't drawing, then
// makes it the front with one store, which a compiler fence keeps after the
// image's: the renderer's IRQ may begin a frame between any two. The
// renderer may still be drawing the old front, so the caller doesn't draw
// again until the renderer has begun a frame since (setup.c waits for
// video_frames_begun to move).
void setup_ui_draw(setup_ui_t *u, const settings_t *s);

// The front image's display codes and EAB bytes, SETUP_UI_CELLS each.
const uint8_t *setup_ui_regen(const setup_ui_t *u);
const uint8_t *setup_ui_eab(const setup_ui_t *u);

#endif
