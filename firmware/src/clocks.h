// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// Clocks for every Liz4270 build (#16, #26).

#ifndef LIZ_CLOCKS_H
#define LIZ_CLOCKS_H

// Moves clk_usb and clk_adc onto pll_sys / 3, which leaves pll_usb free for
// the Fruit Jam's video clock (video.c). Call it before USB starts.
void clocks_init_liz(void);

#endif
