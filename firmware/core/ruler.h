// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// The Rule key's ruler (#51): a bare Rule press turns it on and off, and
// nothing else does. It's off at power-on and never saved, as on the 3483-V
// (captured Oct 10: captures/README.md, "2026-10-10 session, later"). How it
// looks is the settings' (settings.h: Style, Color and Follows cursor) and the
// renderer's (render.c). The spec is
// docs/superpowers/specs/2026-10-10-rule-line-design.md.
//
// Plain C11, like the rest of the core. The firmware keeps one in setup.c and
// changes it from core 0's main loop; the renderer reads at as each frame
// begins, in an IRQ that may interrupt that loop, and a halfword is never read
// torn.

#ifndef LIZ_RULER_H
#define LIZ_RULER_H

#include <stdbool.h>
#include <stdint.h>

#define RULER_OFF 0xFFFFu  // no address counter reaches it: they're below 8192

typedef struct {
    uint16_t at;       // the address counter when it came on (on the screen), or RULER_OFF
    uint32_t presses;  // the Rule presses seen (kbd_rule_presses)
} ruler_t;

// Off, with presses (kbd_rule_presses now) seen, so a Rule press counted
// before it doesn't turn the ruler on.
void ruler_init(ruler_t *r, uint32_t presses);

// On at ac, or off: what a Rule press does, and the console's v rule.
void ruler_toggle(ruler_t *r, uint16_t ac);

// One toggle for each Rule press since the last poll, at ac, the address
// counter now: an even number leaves it as it was. presses counts up and may
// wrap. While the ruler is on at an address off the screen, it moves to ac:
// oec parks the counter in the status line only to write it, so the ruler
// stays where it came on only once the counter is back on the screen. While
// it follows the cursor (follows, the settings' Follows cursor), it keeps at
// up with ac on the screen, so Follows cursor turned off pins it where the
// cursor is then, as the 3483-V does (captured Oct 11, #102). The screen is
// model's (#110): a ruler past a smaller model's end is off it.
void ruler_poll(ruler_t *r, uint32_t presses, uint16_t ac, bool follows, uint8_t model);

// The address counter the ruler goes by: ac when it follows the cursor, at
// (where it came on) when it doesn't, or RULER_OFF while it's off. The
// renderer and the console place it as the cursor is placed (render_place).
uint16_t ruler_address(uint16_t at, uint16_t ac, bool follows);

#endif
