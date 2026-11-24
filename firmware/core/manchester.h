// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// Manchester encoding of one coax word, as xmit_serial shifts it out.

#ifndef LIZ_MANCHESTER_H
#define LIZ_MANCHESTER_H

#include <stdint.h>

// One 10-bit word, MSB first: the sync bit, the ten bits, then odd parity over
// them. Each bit is two half-bit levels (1 is 10, 0 is 01), with 8 zero bits of
// padding on the right. Bits above the tenth are ignored.
uint32_t coax_manchester_encode(uint16_t value);

#endif
