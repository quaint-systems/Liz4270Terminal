// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// The 3483-V's keys (#7, #17): the scan code each one sends, which ones send
// a release, and how each repeats when held. All of it comes from captures of
// the real keyboard: the codes and releases from
// captures/20261003-073005-keys-122key-guided.csv and
// 20261003-075629-keys-alt-retest.csv, typematic from the hold captures at
// each of SetUp's Typematic Rates and Delays (keys3483_holds.h, written by
// tools/capture/typematic.py, #107). Nothing about
// USB keyboards is here; tools/sim/test_keys3483.py checks it all against
// the captures.

#ifndef LIZ_KEYS3483_H
#define LIZ_KEYS3483_H

#include <stdint.h>

#include "settings.h"

#define K_BREAK 240u  // the release prefix: 240, then the key's make code

// Typematic classes; keys3483_delay_ms and keys3483_period_ms give each one's timing.
enum {
    KR_NONE = 0,  // never repeats
    KR_NORMAL = 1,
    KR_FAST = 2,
    KR_EARLY = 3,  // a shorter delay than normal, and a slightly shorter period: the 3483-V's Up and Down
    KR_CLASSES = 4,
};

// Scan codes, by the key's main legend.
enum {
    K_NOTHING = 0,  // not a key: a keymap entry that sends nothing
    K_BLANK_LEFT = 1,  // left block, bottom left
    K_EXSEL = 3,
    K_CRSEL = 4,
    K_ATTN = 5,
    K_CLEAR = 6,
    K_PF1 = 7,
    K_PF13 = 8,
    K_BLANK_RIGHT = 9,  // left block, bottom right; oec calls it Ctrl
    K_PLAY = 10,        // Copy/Play/Test: plain Play is local and sends nothing
    K_EREOF = 11,
    K_PAUSE = 12,       // Pause/ErInp: plain Pause is local and sends nothing
    K_TAB = 13,
    K_BACKTICK = 14,
    K_PF2 = 15,
    K_PF14 = 16,
    K_RESET = 17,
    K_LSHIFT = 18,
    K_LESS = 19,
    K_CAPS = 20,
    K_Q = 21,
    K_1 = 22,
    K_PF3 = 23,
    K_PF15 = 24,
    K_LALT = 25,
    K_Z = 26,
    K_S = 27,
    K_A = 28,
    K_W = 29,
    K_2 = 30,
    K_PF4 = 31,
    K_PF16 = 32,
    K_C = 33,
    K_X = 34,
    K_D = 35,
    K_E = 36,
    K_4 = 37,
    K_3 = 38,
    K_PF5 = 39,
    K_PF17 = 40,
    K_SPACE = 41,
    K_V = 42,
    K_F = 43,
    K_T = 44,
    K_R = 45,
    K_5 = 46,
    K_PF6 = 47,
    K_PF18 = 48,
    K_N = 49,
    K_B = 50,
    K_H = 51,
    K_G = 52,
    K_Y = 53,
    K_6 = 54,
    K_PF7 = 55,
    K_PF19 = 56,
    K_RALT = 57,
    K_M = 58,
    K_J = 59,
    K_U = 60,
    K_7 = 61,
    K_8 = 62,
    K_PF8 = 63,
    K_PF20 = 64,
    K_COMMA = 65,
    K_K = 66,
    K_I = 67,
    K_O = 68,
    K_0 = 69,
    K_9 = 70,
    K_PF9 = 71,
    K_PF21 = 72,
    K_PERIOD = 73,
    K_SLASH = 74,
    K_L = 75,
    K_SEMICOLON = 76,
    K_P = 77,
    K_MINUS = 78,
    K_PF10 = 79,
    K_PF22 = 80,
    K_QUOTE = 82,
    K_BRACE = 83,
    K_CENT = 84,
    K_EQUALS = 85,
    K_PF11 = 86,
    K_PF23 = 87,
    K_ENTER = 88,
    K_RSHIFT = 89,
    K_NEWLINE = 90,
    K_BACKSLASH = 91,
    K_PF12 = 94,
    K_PF24 = 95,
    K_DOWN = 96,
    K_LEFT = 97,
    K_RULE = 98,
    K_UP = 99,
    K_BACKTAB = 100,
    K_INSERT = 101,
    K_BACKSPACE = 102,
    K_PA1 = 103,  // Dup with Shift
    K_KP_1 = 105,
    K_RIGHT = 106,
    K_KP_4 = 107,
    K_KP_7 = 108,
    K_DELETE = 109,
    K_PA2 = 110,   // Field Mark with Shift
    K_JUMP = 111,  // PA3 with Alt
    K_KP_0 = 112,
    K_KP_PERIOD = 113,
    K_KP_2 = 114,
    K_KP_5 = 115,
    K_KP_6 = 116,
    K_KP_8 = 117,
    K_KP_BLANK_LEFT = 118,
    K_KP_BLANK_SECOND = 119,
    K_KP_ENTER = 121,
    K_KP_3 = 122,
    K_KP_MINUS = 123,
    K_KP_TAB = 124,
    K_KP_9 = 125,
    K_KP_COMMA = 126,
    K_PRINT = 131,
    K_KP_SPACE = 132,
    K_SETUP = 255,  // not a key: the local SetUp function, which sends nothing
};

typedef struct {
    const char *label;        // the capture row that shows its code
    const char *repeat_from;  // the hold its class comes from; NULL if none was held, and it never repeats
    uint8_t make_break;       // 1: sends 240 and its make when let go
    uint8_t repeat;           // KR_*
} k3483_key_t;

// Typematic (#17, #107): each class's first repeat by SetUp's Typematic
// Delay, and its period by its Rate, in ms, from the hold captures
// (keys3483_holds.h). KR_NONE's are 0.
extern const uint16_t keys3483_delay_ms[SETTINGS_DELAYS][KR_CLASSES];
extern const uint16_t keys3483_period_ms[SETTINGS_RATES][KR_CLASSES];

// The 3483-V key that sends code, or NULL if none does (K_NOTHING and K_SETUP included).
const k3483_key_t *keys3483_key(unsigned code);

#endif
