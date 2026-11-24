// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// The 3483-V's keys (#7, #17): see keys3483.h.

#include "keys3483.h"

#include <stddef.h>

#include "keys3483_holds.h"  // R_* and the class timings, from the hold captures

const uint16_t keys3483_delay_ms[SETTINGS_DELAYS][KR_CLASSES] = {
    [SETTINGS_DELAY_SHORT] = TIMING_DELAY_SHORT,
    [SETTINGS_DELAY_NORMAL] = TIMING_DELAY_NORMAL,
    [SETTINGS_DELAY_LONG] = TIMING_DELAY_LONG,
};

const uint16_t keys3483_period_ms[SETTINGS_RATES][KR_CLASSES] = {
    [SETTINGS_RATE_NORMAL] = TIMING_PERIOD_NORMAL,
    [SETTINGS_RATE_FAST] = TIMING_PERIOD_FAST,
};

// Each key: its capture row's label, the hold that gives its class (NULL if
// none was held: it then never repeats), whether it sends a release, and the
// class. Keys not held take the class of a held key of their kind.
static const k3483_key_t keys[256] = {
    // Function keys: PF1-12 on the second row, PF13-24 on the top row.
    [K_PF1] = {"F1", "Hold PF1", 0, R_PF1},
    [K_PF2] = {"F2", "Hold PF1", 0, R_PF1},
    [K_PF3] = {"F3", "Hold PF1", 0, R_PF1},
    [K_PF4] = {"F4", "Hold PF1", 0, R_PF1},
    [K_PF5] = {"F5", "Hold PF1", 0, R_PF1},
    [K_PF6] = {"F6", "Hold PF1", 0, R_PF1},
    [K_PF7] = {"F7", "Hold PF1", 0, R_PF1},
    [K_PF8] = {"F8", "Hold PF1", 0, R_PF1},
    [K_PF9] = {"F9", "Hold PF1", 0, R_PF1},
    [K_PF10] = {"F10", "Hold PF1", 0, R_PF1},
    [K_PF11] = {"F11", "Hold PF1", 0, R_PF1},
    [K_PF12] = {"F12", "Hold PF1", 0, R_PF1},
    [K_PF13] = {"F13", "Hold PF13", 0, R_PF13},
    [K_PF14] = {"F14", "Hold PF13", 0, R_PF13},
    [K_PF15] = {"F15", "Hold PF13", 0, R_PF13},
    [K_PF16] = {"F16", "Hold PF13", 0, R_PF13},
    [K_PF17] = {"F17", "Hold PF13", 0, R_PF13},
    [K_PF18] = {"F18", "Hold PF13", 0, R_PF13},
    [K_PF19] = {"F19", "Hold PF13", 0, R_PF13},
    [K_PF20] = {"F20", "Hold PF13", 0, R_PF13},
    [K_PF21] = {"F21", "Hold PF13", 0, R_PF13},
    [K_PF22] = {"F22", "Hold PF13", 0, R_PF13},
    [K_PF23] = {"F23", "Hold PF13", 0, R_PF13},
    [K_PF24] = {"F24", "Hold PF13", 0, R_PF13},

    // The left block. Plain Play and Pause are local and send nothing, so
    // their codes come from Shift+Play and Alt+Pause.
    [K_ATTN] = {"Attn/SysRq", "Hold Attn", 0, R_ATTN},
    [K_CLEAR] = {"Clear", "Hold Clear", 0, R_CLEAR},
    [K_CRSEL] = {"CrSel", NULL, 0, KR_NONE},
    [K_PAUSE] = {"Left Alt+Pause (ErInp)", NULL, 0, KR_NONE},
    [K_EXSEL] = {"ExSel/SetUp", NULL, 0, KR_NONE},
    [K_EREOF] = {"ErEoF/Record", "Hold ErEOF", 0, R_EREOF},
    [K_PRINT] = {"Print/Ident", NULL, 0, KR_NONE},
    [K_PLAY] = {"Shift+Copy/Play", NULL, 0, KR_NONE},
    [K_BLANK_LEFT] = {"Left block blank, left", NULL, 0, KR_NONE},
    [K_BLANK_RIGHT] = {"Left block blank, right", NULL, 1, KR_NONE},

    // The typewriter keys repeat as A does.
    [K_BACKTICK] = {"`~", "Hold A", 0, R_A},
    [K_1] = {"1|", "Hold A", 0, R_A},
    [K_2] = {"2@", "Hold A", 0, R_A},
    [K_3] = {"3#", "Hold A", 0, R_A},
    [K_4] = {"4$", "Hold A", 0, R_A},
    [K_5] = {"5%", "Hold A", 0, R_A},
    [K_6] = {"6¬", "Hold A", 0, R_A},
    [K_7] = {"7&", "Hold A", 0, R_A},
    [K_8] = {"8*", "Hold A", 0, R_A},
    [K_9] = {"9(", "Hold A", 0, R_A},
    [K_0] = {"0)", "Hold A", 0, R_A},
    [K_MINUS] = {"-_", "Hold A", 0, R_A},
    [K_EQUALS] = {"=+", "Hold A", 0, R_A},
    [K_BACKSPACE] = {"Backspace", "Hold Backspace", 0, R_BACKSPACE},
    [K_TAB] = {"Tab", "Hold Tab", 0, R_TAB},
    [K_Q] = {"Q", "Hold A", 0, R_A},
    [K_W] = {"W", "Hold A", 0, R_A},
    [K_E] = {"E", "Hold A", 0, R_A},
    [K_R] = {"R", "Hold A", 0, R_A},
    [K_T] = {"T", "Hold A", 0, R_A},
    [K_Y] = {"Y", "Hold A", 0, R_A},
    [K_U] = {"U", "Hold A", 0, R_A},
    [K_I] = {"I", "Hold A", 0, R_A},
    [K_O] = {"O", "Hold A", 0, R_A},
    [K_P] = {"P", "Hold A", 0, R_A},
    [K_CENT] = {"¢!", "Hold A", 0, R_A},
    [K_BACKSLASH] = {"\\|", "Hold A", 0, R_A},
    [K_NEWLINE] = {"New Line", "Hold New Line", 0, R_NEW_LINE},
    [K_CAPS] = {"Caps Lock", "Hold Caps Lock", 1, R_CAPS_LOCK},
    [K_A] = {"A", "Hold A", 0, R_A},
    [K_S] = {"S", "Hold A", 0, R_A},
    [K_D] = {"D", "Hold A", 0, R_A},
    [K_F] = {"F", "Hold A", 0, R_A},
    [K_G] = {"G", "Hold A", 0, R_A},
    [K_H] = {"H", "Hold A", 0, R_A},
    [K_J] = {"J", "Hold A", 0, R_A},
    [K_K] = {"K", "Hold A", 0, R_A},
    [K_L] = {"L", "Hold A", 0, R_A},
    [K_SEMICOLON] = {";:", "Hold A", 0, R_A},
    [K_QUOTE] = {"'\"", "Hold A", 0, R_A},
    [K_BRACE] = {"{}", "Hold A", 0, R_A},
    // The capture lost Left Shift's release to a timing slip
    // (captures/README.md); it sends one, as Right Shift does.
    [K_LSHIFT] = {"Left Shift", "Hold Left Shift", 1, R_LEFT_SHIFT},
    [K_LESS] = {"<>", "Hold A", 0, R_A},
    [K_Z] = {"Z", "Hold A", 0, R_A},
    [K_X] = {"X", "Hold A", 0, R_A},
    [K_C] = {"C", "Hold A", 0, R_A},
    [K_V] = {"V", "Hold A", 0, R_A},
    [K_B] = {"B", "Hold A", 0, R_A},
    [K_N] = {"N", "Hold A", 0, R_A},
    [K_M] = {"M", "Hold A", 0, R_A},
    [K_COMMA] = {",", "Hold A", 0, R_A},
    [K_PERIOD] = {".", "Hold A", 0, R_A},
    [K_SLASH] = {"/?", "Hold A", 0, R_A},
    [K_RSHIFT] = {"Right Shift", "Hold Left Shift", 1, R_LEFT_SHIFT},
    [K_RESET] = {"Reset/Quit", "Hold Reset", 1, R_RESET},
    [K_LALT] = {"Left Alt", "Hold Left Alt", 1, R_LEFT_ALT},
    [K_SPACE] = {"Space", "Hold Space", 0, R_SPACE},
    [K_RALT] = {"Right Alt", "Hold Left Alt", 1, R_LEFT_ALT},
    [K_ENTER] = {"Enter", "Hold Enter", 0, R_ENTER},

    // The centre block. PA2 and Jump repeat as PA1 does.
    [K_PA1] = {"Dup/PA1", "Hold PA1", 0, R_PA1},
    [K_PA2] = {"FldMk/PA2", "Hold PA1", 0, R_PA1},
    [K_JUMP] = {"Jump/PA3", "Hold PA1", 0, R_PA1},
    [K_BACKTAB] = {"Back Tab", "Hold Back Tab", 0, R_BACK_TAB},
    [K_INSERT] = {"Insert", "Hold Insert", 0, R_INSERT},
    [K_DELETE] = {"Delete/DelWd", "Hold Delete", 0, R_DELETE},
    [K_UP] = {"Up", "Hold Up", 0, R_UP},
    [K_LEFT] = {"Left", "Hold Left", 0, R_LEFT},
    [K_RULE] = {"Rule", NULL, 0, KR_NONE},
    [K_RIGHT] = {"Right", "Hold Right", 0, R_RIGHT},
    [K_DOWN] = {"Down", "Hold Down", 0, R_DOWN},

    // The keypad repeats as its 5 does, but for Enter.
    [K_KP_BLANK_LEFT] = {"Keypad blank, left", NULL, 0, KR_NONE},
    [K_KP_BLANK_SECOND] = {"Keypad blank, second", NULL, 0, KR_NONE},
    [K_KP_COMMA] = {"Keypad ,", "Hold Keypad 5", 0, R_KEYPAD_5},
    [K_KP_SPACE] = {"Keypad Space", "Hold Keypad 5", 0, R_KEYPAD_5},
    [K_KP_7] = {"Keypad 7", "Hold Keypad 5", 0, R_KEYPAD_5},
    [K_KP_8] = {"Keypad 8", "Hold Keypad 5", 0, R_KEYPAD_5},
    [K_KP_9] = {"Keypad 9", "Hold Keypad 5", 0, R_KEYPAD_5},
    [K_KP_TAB] = {"Keypad Tab", "Hold Keypad 5", 0, R_KEYPAD_5},
    [K_KP_4] = {"Keypad 4", "Hold Keypad 5", 0, R_KEYPAD_5},
    [K_KP_5] = {"Keypad 5", "Hold Keypad 5", 0, R_KEYPAD_5},
    [K_KP_6] = {"Keypad 6", "Hold Keypad 5", 0, R_KEYPAD_5},
    [K_KP_MINUS] = {"Keypad -", "Hold Keypad 5", 0, R_KEYPAD_5},
    [K_KP_1] = {"Keypad 1", "Hold Keypad 5", 0, R_KEYPAD_5},
    [K_KP_2] = {"Keypad 2", "Hold Keypad 5", 0, R_KEYPAD_5},
    [K_KP_3] = {"Keypad 3", "Hold Keypad 5", 0, R_KEYPAD_5},
    [K_KP_ENTER] = {"Keypad Enter", "Hold Keypad Enter", 0, R_KEYPAD_ENTER},
    [K_KP_0] = {"Keypad 0", "Hold Keypad 5", 0, R_KEYPAD_5},
    [K_KP_PERIOD] = {"Keypad .", "Hold Keypad 5", 0, R_KEYPAD_5},
};

const k3483_key_t *keys3483_key(unsigned code) {
    return code < 256u && keys[code].label ? &keys[code] : NULL;
}
