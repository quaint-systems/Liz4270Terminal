// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// Which board this is (#97): GPIO 4 and 5, read once at power-on and named
// by board_id.h.

#ifndef LIZ_BOARD_DETECT_H
#define LIZ_BOARD_DETECT_H

#include <stdbool.h>
#include <stddef.h>

#include "board_id.h"

// What board_detect found: GPIO 4 and 5 as read, for the banner, and the
// board they name.
typedef struct {
    bool gpio4, gpio5;
    board_t board;
} board_info_t;

// Once, early in main, before usb_host_init and video_init, which ask which
// board it is. Reads GPIO 4 and 5 with the pads' pull-ups on, then puts both
// pads back exactly as they were.
void board_detect(void);

board_info_t board_detected(void);

// The board as the banner and SetUp's About page name it, into out (#126): its name and the ID, GPIO4 first,
// with more inside the parentheses, "" for none: "Fruit Jam (ID 11)".
void board_describe(char *out, size_t size, const char *more);

#endif
