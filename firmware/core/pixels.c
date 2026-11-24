// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// The masks pixels.h's helpers read (#26). See pixels.h.

#include "pixels.h"

// PAIR(b, k): word k of b's eight pixels, pixel 2k in the low half.
#define PAIR(b, k) ((((b) >> (2 * (k))) & 1u ? 0x0000FFFFu : 0u) | (((b) >> (2 * (k) + 1)) & 1u ? 0xFFFF0000u : 0u))
#define MASK(b) {PAIR(b, 0), PAIR(b, 1), PAIR(b, 2), PAIR(b, 3)}
#define MASK4(b) MASK(b), MASK((b) + 1), MASK((b) + 2), MASK((b) + 3)
#define MASK16(b) MASK4(b), MASK4((b) + 4), MASK4((b) + 8), MASK4((b) + 12)
#define MASK64(b) MASK16(b), MASK16((b) + 16), MASK16((b) + 32), MASK16((b) + 48)
const uint32_t pixels_masks[256][4] = {MASK64(0), MASK64(64), MASK64(128), MASK64(192)};
