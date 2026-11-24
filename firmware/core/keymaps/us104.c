// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// The US 104-key (ANSI) keymap (#17), the default. Keys type what their
// legends say; the 3270 keys sit where LizTerm's defaults put them
// (src/LizTerm.App/Keyboard/DefaultKeymap.cs @ 4e4fada: Vista TN3270's table,
// cross-checked against wc3270), except that Left Ctrl is Reset and Right
// Ctrl is Enter, as keys of their own: no Ctrl chords. The table, with what
// oec reads for each chord, is docs/keymaps/us104.md.

#include <stddef.h>

#include "keymap.h"
#include "keys3483.h"
#include "usb_usage.h"

#define ANY KM_ANY
#define SHIFT KM_SHIFT
#define ALT KM_ALT
#define SHIFT_ALT (KM_SHIFT | KM_ALT)
#define KEEP KM_KEEP
#define NONE KM_NONE

static const keymap_entry_t entries[] = {
    // Letters keep the PC's Shift and Alt. Alt+C and Alt+X are CrSel and
    // ExSel; Shift+Alt+X is SetUp (the 3483-V's Alt+ExSel, with Alt+X taken).
    {U_A, ANY, K_A, KEEP},
    {U_B, ANY, K_B, KEEP},
    {U_C, ANY, K_C, KEEP},
    {U_D, ANY, K_D, KEEP},
    {U_E, ANY, K_E, KEEP},
    {U_F, ANY, K_F, KEEP},
    {U_G, ANY, K_G, KEEP},
    {U_H, ANY, K_H, KEEP},
    {U_I, ANY, K_I, KEEP},
    {U_J, ANY, K_J, KEEP},
    {U_K, ANY, K_K, KEEP},
    {U_L, ANY, K_L, KEEP},
    {U_M, ANY, K_M, KEEP},
    {U_N, ANY, K_N, KEEP},
    {U_O, ANY, K_O, KEEP},
    {U_P, ANY, K_P, KEEP},
    {U_Q, ANY, K_Q, KEEP},
    {U_R, ANY, K_R, KEEP},
    {U_S, ANY, K_S, KEEP},
    {U_T, ANY, K_T, KEEP},
    {U_U, ANY, K_U, KEEP},
    {U_V, ANY, K_V, KEEP},
    {U_W, ANY, K_W, KEEP},
    {U_X, ANY, K_X, KEEP},
    {U_Y, ANY, K_Y, KEEP},
    {U_Z, ANY, K_Z, KEEP},
    {U_C, ALT, K_CRSEL, NONE},
    {U_X, ALT, K_EXSEL, NONE},
    {U_X, SHIFT_ALT, K_SETUP, NONE},

    // Digits. Shift+1 is '!'. Alt+1-3 are PA1-3, and Shift+Alt+1-3 are Dup,
    // Field Mark and Jump, as Shift+PA1, Shift+PA2 and Jump are on the 3483-V.
    {U_1, ANY, K_1, KEEP},
    {U_2, ANY, K_2, KEEP},
    {U_3, ANY, K_3, KEEP},
    {U_4, ANY, K_4, KEEP},
    {U_5, ANY, K_5, KEEP},
    {U_6, ANY, K_6, KEEP},
    {U_7, ANY, K_7, KEEP},
    {U_8, ANY, K_8, KEEP},
    {U_9, ANY, K_9, KEEP},
    {U_0, ANY, K_0, KEEP},
    {U_1, SHIFT, K_CENT, SHIFT},
    {U_1, ALT, K_PA1, NONE},
    {U_2, ALT, K_PA2, NONE},
    {U_3, ALT, K_JUMP, ALT},
    {U_1, SHIFT_ALT, K_PA1, SHIFT},
    {U_2, SHIFT_ALT, K_PA2, SHIFT},
    {U_3, SHIFT_ALT, K_JUMP, NONE},

    // Punctuation, by legend. The 3483-V's own characters the PC lacks:
    // '[' is the cent sign, Alt+\ the broken bar (and Shift+6 gives the not
    // sign, as on the 3483-V). Alt+. is the 3483-V's Shift+., whose keycap
    // reads '.': oec makes it a centre period it can't draw, and leaves a
    // blank cell on the 3483-V too (#63).
    {U_GRAVE, ANY, K_BACKTICK, KEEP},
    {U_MINUS, ANY, K_MINUS, KEEP},
    {U_EQUALS, ANY, K_EQUALS, KEEP},
    {U_SEMICOLON, ANY, K_SEMICOLON, KEEP},
    {U_QUOTE, ANY, K_QUOTE, KEEP},
    {U_COMMA, ANY, K_COMMA, KEEP},
    {U_COMMA, SHIFT, K_LESS, NONE},
    {U_PERIOD, ANY, K_PERIOD, KEEP},
    {U_PERIOD, SHIFT, K_LESS, SHIFT},
    {U_PERIOD, ALT, K_PERIOD, SHIFT},
    {U_SLASH, ANY, K_SLASH, KEEP},
    {U_LBRACKET, ANY, K_CENT, NONE},
    {U_LBRACKET, SHIFT, K_BRACE, NONE},
    {U_RBRACKET, ANY, K_NOTHING, NONE},
    {U_RBRACKET, SHIFT, K_BRACE, SHIFT},
    {U_BACKSLASH, ANY, K_BACKSLASH, NONE},
    {U_BACKSLASH, SHIFT, K_1, SHIFT},
    {U_BACKSLASH, ALT, K_BACKSLASH, SHIFT},
    // Some keyboards send the \ key as Non-US # (the bench 104-key does);
    // Linux reads both as backslash, and so does this keymap.
    {U_NONUS_HASH, ANY, K_BACKSLASH, NONE},
    {U_NONUS_HASH, SHIFT, K_1, SHIFT},
    {U_NONUS_HASH, ALT, K_BACKSLASH, SHIFT},

    // Editing and the 3270 keys. Shift+Enter is New Line, Shift+Tab Back Tab,
    // Shift+Esc SysReq.
    {U_ENTER, ANY, K_ENTER, KEEP},
    {U_ENTER, SHIFT, K_NEWLINE, NONE},
    {U_RCTRL, ANY, K_ENTER, KEEP},
    {U_LCTRL, ANY, K_RESET, KEEP},
    {U_ESC, ANY, K_ATTN, KEEP},
    {U_ESC, SHIFT, K_ATTN, ALT},
    {U_BACKSPACE, ANY, K_BACKSPACE, KEEP},
    {U_TAB, ANY, K_TAB, KEEP},
    {U_TAB, SHIFT, K_BACKTAB, NONE},  // oec reads Shift+Tab as Tab
    {U_SPACE, ANY, K_SPACE, KEEP},
    {U_CAPS_LOCK, ANY, K_CAPS, KEEP},
    {U_PAUSE, ANY, K_CLEAR, KEEP},
    {U_PRINT_SCREEN, ANY, K_PRINT, KEEP},
    // Scroll Lock is the Copy/Play key: alone, Play, which is local.
    {U_SCROLL_LOCK, ANY, K_NOTHING, NONE},
    {U_SCROLL_LOCK, SHIFT, K_PLAY, SHIFT},
    {U_SCROLL_LOCK, ALT, K_PLAY, ALT},
    {U_INSERT, ANY, K_INSERT, KEEP},
    {U_DELETE, ANY, K_DELETE, KEEP},
    // Home is the 3483-V's Alt+Rule, and Shift+Home its Rule.
    {U_HOME, ANY, K_RULE, ALT},
    {U_HOME, SHIFT, K_RULE, NONE},
    {U_END, ANY, K_EREOF, KEEP},
    {U_END, ALT, K_PAUSE, ALT},
    {U_PAGE_UP, ANY, K_PF7, KEEP},
    {U_PAGE_DOWN, ANY, K_PF8, KEEP},
    {U_UP, ANY, K_UP, KEEP},
    {U_DOWN, ANY, K_DOWN, KEEP},
    {U_LEFT, ANY, K_LEFT, KEEP},
    {U_RIGHT, ANY, K_RIGHT, KEEP},

    // PF keys: F1-F12, and Shift+F1-F12 for PF13-24. F13-F24 send nothing:
    // Windows keyboards send their Copilot key as Win+Shift+F23.
    {U_F1, ANY, K_PF1, KEEP},
    {U_F2, ANY, K_PF2, KEEP},
    {U_F3, ANY, K_PF3, KEEP},
    {U_F4, ANY, K_PF4, KEEP},
    {U_F5, ANY, K_PF5, KEEP},
    {U_F6, ANY, K_PF6, KEEP},
    {U_F7, ANY, K_PF7, KEEP},
    {U_F8, ANY, K_PF8, KEEP},
    {U_F9, ANY, K_PF9, KEEP},
    {U_F10, ANY, K_PF10, KEEP},
    {U_F11, ANY, K_PF11, KEEP},
    {U_F12, ANY, K_PF12, KEEP},
    {U_F1, SHIFT, K_PF13, NONE},
    {U_F2, SHIFT, K_PF14, NONE},
    {U_F3, SHIFT, K_PF15, NONE},
    {U_F4, SHIFT, K_PF16, NONE},
    {U_F5, SHIFT, K_PF17, NONE},
    {U_F6, SHIFT, K_PF18, NONE},
    {U_F7, SHIFT, K_PF19, NONE},
    {U_F8, SHIFT, K_PF20, NONE},
    {U_F9, SHIFT, K_PF21, NONE},
    {U_F10, SHIFT, K_PF22, NONE},
    {U_F11, SHIFT, K_PF23, NONE},
    {U_F12, SHIFT, K_PF24, NONE},

    // The keypad, by legend and always numeric: its own digits, '.', '-'
    // and Enter, and the main block's '/', '*' and '+'.
    {U_KP_0, ANY, K_KP_0, KEEP},
    {U_KP_1, ANY, K_KP_1, KEEP},
    {U_KP_2, ANY, K_KP_2, KEEP},
    {U_KP_3, ANY, K_KP_3, KEEP},
    {U_KP_4, ANY, K_KP_4, KEEP},
    {U_KP_5, ANY, K_KP_5, KEEP},
    {U_KP_6, ANY, K_KP_6, KEEP},
    {U_KP_7, ANY, K_KP_7, KEEP},
    {U_KP_8, ANY, K_KP_8, KEEP},
    {U_KP_9, ANY, K_KP_9, KEEP},
    {U_KP_PERIOD, ANY, K_KP_PERIOD, KEEP},
    {U_KP_MINUS, ANY, K_KP_MINUS, KEEP},
    {U_KP_ENTER, ANY, K_KP_ENTER, KEEP},
    {U_KP_SLASH, ANY, K_SLASH, NONE},
    {U_KP_STAR, ANY, K_8, SHIFT},
    {U_KP_PLUS, ANY, K_EQUALS, SHIFT},
    {U_NUM_LOCK, ANY, K_NOTHING, NONE},

    // Nothing.
    {U_LGUI, ANY, K_NOTHING, NONE},
    {U_RGUI, ANY, K_NOTHING, NONE},
    {U_MENU, ANY, K_NOTHING, NONE},
};

const keymap_t keymap_us104 = {
    .name = "us104",
    .title = "US 104-key (ANSI)",
    .status = "bench-tested: Inland 104-key 1a86:0600 on the Fruit Jam rig, Oct 2026",
    .base = NULL,
    .devices = NULL,
    .entries = entries,
    .count = (uint16_t)(sizeof entries / sizeof entries[0]),
};
