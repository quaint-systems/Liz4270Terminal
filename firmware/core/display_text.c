// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// Text as the 3483-V's display codes. See display_text.h.

#include "display_text.h"

#define CODE_MAIN_END 0xC0u  // codes from here are field attributes and status-line symbols

// What display codes 0x00-0xBF show, in Latin-1, sixteen codes a line, as
// tools/sim/display_codes.py has them from the photographs. A NUL stands in
// where Latin-1 has no character (0x1E peseta, 0x39 caron) and for Field
// Mark and DUP (0x9E and 0x9F: ; and * with a bar above). The text is
// NUL-terminated, so display_text_code never finds those.
static const char main_codes[CODE_MAIN_END + 1u] =
    "        ><[])(}{"
    " ='\"/\\|\xa6?!$\xa2\xa3\xa5" "\0" "\xa4"
    "0123456789\xdf\xa7#@%_"
    "&-.,:+\xac\xaf\xb0" "\0" "^~\xa8`\xb4\xb8"
    "\xe0\xe8\xec\xf2\xf9\xe3\xf5\xff\xe0\xe8\xe9\xec\xf2\xf9\xfc\xe7"
    "\xe4\xeb\xef\xf6\xfc\xe2\xea\xee\xf4\xfb\xe1\xe9\xed\xf3\xfa\xf1"
    "\xc0\xc8\xcc\xd2\xd9\xc3\xd5" "YAEEIOUYC"
    "\xc4\xcb\xcf\xd6\xdc\xc2\xca\xce\xd4\xdb\xc1\xc9\xcd\xd3\xda\xd1"
    "abcdefghijklmnop"
    "qrstuvwxyz\xe6\xf8\xe5\xe7" "\0\0"
    "ABCDEFGHIJKLMNOP"
    "QRSTUVWXYZ\xc6\xd8\xc5\xc7;*";
_Static_assert(sizeof main_codes == CODE_MAIN_END + 1u, "twelve lines of sixteen codes, and the NUL");

uint8_t display_text_code(unsigned char ch) {
    if (ch >= '0' && ch <= '9')
        return (uint8_t)(0x20u + (ch - '0'));
    if (ch >= 'a' && ch <= 'z')
        return (uint8_t)(0x80u + (ch - 'a'));
    if (ch >= 'A' && ch <= 'Z')
        return (uint8_t)(0xA0u + (ch - 'A'));
    for (unsigned code = 0; ch != 0u && code < CODE_MAIN_END; code++)
        if ((unsigned char)main_codes[code] == ch)
            return (uint8_t)code;
    return DISPLAY_TEXT_UNKNOWN;
}
