// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// Which board this is (#97). See board_detect.h.
//
// The pads' pull-ups are tens of kOhm, so against revision A's 4.7 kOhm to
// ground a pin reads well under VIL. The Fruit Jam's buttons 2 and 3 are
// bare switches, so there the pull-up alone holds each pin high.

#include <stdio.h>

#include "pico/stdlib.h"
#include "pico/binary_info.h"
#include "hardware/structs/io_bank0.h"
#include "hardware/structs/pads_bank0.h"

#include "board.h"
#include "board_detect.h"

#define SETTLE_US 1000u  // for the pull-ups to charge the pins before the read

bi_decl(bi_2pins_with_names(LIZ_BOARD_ID1_PIN, "board ID, first digit",
                            LIZ_BOARD_ID2_PIN, "board ID, second digit"));

static board_info_t info = {.board = BOARD_UNKNOWN};

void board_detect(void) {
    static const uint pins[] = {LIZ_BOARD_ID1_PIN, LIZ_BOARD_ID2_PIN};
    uint32_t ctrl[count_of(pins)], pad[count_of(pins)];
    for (size_t i = 0; i < count_of(pins); i++) {
        ctrl[i] = io_bank0_hw->io[pins[i]].ctrl;
        pad[i] = pads_bank0_hw->io[pins[i]];
        gpio_init(pins[i]);
        gpio_pull_up(pins[i]);
    }
    busy_wait_us(SETTLE_US);
    info.gpio4 = gpio_get(LIZ_BOARD_ID1_PIN);
    info.gpio5 = gpio_get(LIZ_BOARD_ID2_PIN);
    // The pad first, so it is isolated again before its function goes back.
    for (size_t i = 0; i < count_of(pins); i++) {
        pads_bank0_hw->io[pins[i]] = pad[i];
        io_bank0_hw->io[pins[i]].ctrl = ctrl[i];
    }
    info.board = board_from_id(info.gpio4, info.gpio5);
}

board_info_t board_detected(void) {
    return info;
}

void board_describe(char *out, size_t size, const char *more) {
    snprintf(out, size, "%s (ID %d%d%s)", board_name(info.board), info.gpio4, info.gpio5, more);
}
