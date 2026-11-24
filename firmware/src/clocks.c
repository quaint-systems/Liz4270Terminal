// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// Clocks for the Fruit Jam (#16, #26).
//
// CMakeLists.txt sets pll_sys to 1440 MHz / 5 / 2 = 144 MHz, which the SDK's
// start-up gives clk_sys: a multiple of 12 MHz, as PIO-USB needs (#17). This
// file moves clk_usb and clk_adc onto pll_sys / 3 = 48 MHz, as
// tools/testcard does, so pll_usb is free for video.c to re-time for each
// mode.

#include <assert.h>

#include "hardware/clocks.h"

#include "clocks.h"

static_assert(SYS_CLK_HZ == 144000000, "CMakeLists.txt sets clk_sys to 144 MHz");
static_assert(SYS_CLK_HZ / 3 == 48000000, "clk_usb is clk_sys / 3");

void clocks_init_liz(void) {
    uint32_t sys_hz = clock_get_hz(clk_sys);
    clock_configure_int_divider(clk_usb, 0, CLOCKS_CLK_USB_CTRL_AUXSRC_VALUE_CLKSRC_PLL_SYS, sys_hz, 3);
    clock_configure_int_divider(clk_adc, 0, CLOCKS_CLK_ADC_CTRL_AUXSRC_VALUE_CLKSRC_PLL_SYS, sys_hz, 3);
}
