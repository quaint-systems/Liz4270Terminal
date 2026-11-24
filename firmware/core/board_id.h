// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// Which board the firmware runs on (#97). One UF2 serves the Fruit Jam and
// the Liz4270 board, so at power-on the firmware reads GPIO 4 and 5 with the
// pads' pull-ups on. The Fruit Jam's buttons 2 and 3 are bare switches to
// ground there, so it reads both high. Revision A holds both low through
// 4.7 kOhm (the unified board spec, "Pin map"). Either one low alone is
// unknown: on a Fruit Jam, a button held through reset. A later revision can
// claim one. The ID is written in pin order, GPIO4 first: `11`, `00`.
//
// Which boards have the signals revision A added is decided here too, not by
// the drivers that read them: only revision A has the USB fault flag on GPIO6
// and hot-plug detect on GPIO7. On the Fruit Jam those are bare header pins,
// so nothing reads them.

#ifndef LIZ_BOARD_ID_H
#define LIZ_BOARD_ID_H

#include <stdbool.h>

typedef enum {
    BOARD_UNKNOWN = 0,
    BOARD_FRUIT_JAM = 1,
    BOARD_REV_A = 2,
} board_t;

// GPIO 4 and 5 as read with the pull-ups on.
board_t board_from_id(bool gpio4, bool gpio5);

// "Fruit Jam", "Liz4270 rev A" or "unknown".
const char *board_name(board_t board);

// The USB-A load switch's fault flag on GPIO6 (usb_fault.h).
bool board_has_usb_fault(board_t board);

// HDMI hot-plug detect on GPIO7.
bool board_has_hpd(board_t board);

#endif
