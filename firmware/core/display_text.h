// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// Text as the 3483-V's display codes: Latin-1 in, the code that shows each
// character out, as tools/sim/display_codes.py has them from the
// photographs. The splash (#53) and SetUp (#102) write their text with it.
//
// Plain C11, like the rest of the core.

#ifndef LIZ_DISPLAY_TEXT_H
#define LIZ_DISPLAY_TEXT_H

#include <stdint.h>

#define DISPLAY_TEXT_UNKNOWN 0x18u  // '?': what a character with no display code shows as

// Digits and letters as the controller writes them (coaxlog.to_display),
// ahead of 0x67-0x6F, the accented capitals the 3483-V draws plain; the rest
// at the first code that shows them. Characters without one show as '?'.
uint8_t display_text_code(unsigned char ch);

#endif
