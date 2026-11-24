// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// Line commands over USB serial, on core 0.

#ifndef LIZ_CONSOLE_H
#define LIZ_CONSOLE_H

#include "term.h"

// Reads whatever has arrived, without waiting, and runs each complete line.
void console_poll(term_t *t);

#endif
