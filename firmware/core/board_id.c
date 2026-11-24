// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// Which board the firmware runs on (#97). See board_id.h.

#include "board_id.h"

board_t board_from_id(bool gpio4, bool gpio5) {
    if (gpio4 && gpio5)
        return BOARD_FRUIT_JAM;
    if (!gpio4 && !gpio5)
        return BOARD_REV_A;
    return BOARD_UNKNOWN;
}

const char *board_name(board_t board) {
    switch (board) {
    case BOARD_FRUIT_JAM:
        return "Fruit Jam";
    case BOARD_REV_A:
        return "Liz4270 rev A";
    default:
        return "unknown";
    }
}

bool board_has_usb_fault(board_t board) {
    return board == BOARD_REV_A;
}

bool board_has_hpd(board_t board) {
    return board == BOARD_REV_A;
}
