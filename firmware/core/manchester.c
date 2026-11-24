// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// coax_manchester_encode, verbatim from hanshuebner/coax-tcp
// interface3/firmware/coax.c @ 78a0040b4f42a689128f8b34371459e5c430cee1.
// Recorded in NOTICE.
//
// Copyright (c) 2019, Andrew Kay
// Copyright (c) 2025, Hans Hübner
//
// Permission to use, copy, modify, and/or distribute this software for any
// purpose with or without fee is hereby granted, provided that the above
// copyright notice and this permission notice appear in all copies.
//
// THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
// WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
// MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
// ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
// WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
// ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
// OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

#include "manchester.h"

uint32_t coax_manchester_encode(uint16_t value) {
    uint32_t parity = 1;
    uint32_t encoded = 0b10;  // start bit

    for (int i = 9; i >= 0; i--) {
        encoded <<= 2;
        if (value & (1 << i)) {
            encoded |= 0b10;
            parity++;
        } else {
            encoded |= 0b01;
        }
    }

    // Parity bit
    encoded <<= 2;
    if (parity & 1) {
        encoded |= 0b10;
    } else {
        encoded |= 0b01;
    }

    // Pad 8 bits to the right
    encoded <<= 8;
    return encoded;
}
