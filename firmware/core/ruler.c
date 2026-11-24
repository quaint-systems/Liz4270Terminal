// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// The Rule key's ruler (#51). See ruler.h.

#include "render.h"
#include "ruler.h"

void ruler_init(ruler_t *r, uint32_t presses) {
    r->at = RULER_OFF;
    r->presses = presses;
}

void ruler_toggle(ruler_t *r, uint16_t ac) {
    // One store: a frame begun meanwhile sees the ruler as it was or as it is.
    r->at = r->at == RULER_OFF ? ac : RULER_OFF;
}

void ruler_poll(ruler_t *r, uint32_t presses, uint16_t ac, bool follows, uint8_t model) {
    if ((presses - r->presses) & 1u)
        ruler_toggle(r, ac);
    r->presses = presses;
    if (r->at == RULER_OFF)
        return;
    uint16_t end = render_geometry(model)->screen_end;  // the screen the controller drives (#110)
    bool on_screen = ac >= RENDER_SCREEN_START && ac < end;
    // Off the screen, the counter is passing through: oec parks it in the
    // status line only to write it. So until it's back on the screen, where
    // the ruler came on is wherever it is now. A smaller model's screen
    // leaves a ruler past its end off it the same way.
    if (r->at < RENDER_SCREEN_START || r->at >= end)
        r->at = ac;
    else if (follows && on_screen)
        r->at = ac;  // where Follows cursor turned off will pin it (#102)
}

uint16_t ruler_address(uint16_t at, uint16_t ac, bool follows) {
    if (at == RULER_OFF)
        return RULER_OFF;
    return follows ? ac : at;
}
