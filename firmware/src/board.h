// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// The board's pin map, and the constraints the coax PIO programs put on it.
// The Fruit Jam is the one board (#78).

#ifndef LIZ_BOARD_H
#define LIZ_BOARD_H

#include <assert.h>

#include "pico.h"

#if defined(ADAFRUIT_FRUIT_JAM)
#include "boards/fruit_jam.h"
#else
#error "Liz4270 builds for PICO_BOARD adafruit_fruit_jam"
#endif

// xmit_serial sets TX and TX_ACTIVE as one two-pin group, and recv_serial
// reads TX_ACTIVE as its third input pin.
static_assert(LIZ_COAX_TX_ACTIVE_PIN == LIZ_COAX_TX_PIN + 1, "TX_ACTIVE must be TX + 1");
static_assert(LIZ_COAX_TX_ACTIVE_PIN == LIZ_COAX_RX_PIN + 2, "TX_ACTIVE must be RX + 2");

// A PIO block reaches 32 GPIOs from its base.
#define LIZ_IN_PIO_WINDOW(pin) \
    ((pin) >= LIZ_COAX_PIO_GPIO_BASE && (pin) < LIZ_COAX_PIO_GPIO_BASE + 32)
static_assert(LIZ_IN_PIO_WINDOW(LIZ_COAX_RX_PIN) && LIZ_IN_PIO_WINDOW(LIZ_COAX_TX_PIN) &&
              LIZ_IN_PIO_WINDOW(LIZ_COAX_TX_ACTIVE_PIN) && LIZ_IN_PIO_WINDOW(LIZ_COAX_TX_DELAY_PIN),
              "coax pins must lie within the PIO GPIO window");

#endif
