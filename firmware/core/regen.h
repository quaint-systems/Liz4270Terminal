// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// Regen buffer and address counter for the Liz4270 terminal core.
//
// Model 2 draws 2000 cells: the status line at 0-79 and the screen at
// 80-1999. The 3483-V's address counter is 13 bits, though, and a write past
// 1999 carries on into buffer that reads back (captured Oct 3, 2026;
// docs/upstream-review.md, "Regen buffer and address counter"). So the buffer
// spans the whole counter, with an EAB byte beside every cell.

#ifndef LIZ_REGEN_H
#define LIZ_REGEN_H

#include <stdint.h>

#define REGEN_SIZE 8192u
#define REGEN_ADDR_MASK (REGEN_SIZE - 1u)

typedef struct {
    uint8_t chars[REGEN_SIZE];
    uint8_t eab[REGEN_SIZE];
    uint16_t ac;  // address counter, which is also the cursor
} regen_t;

void regen_init(regen_t *r);

// The counter loads and reads in 8-bit halves. HI keeps only its low 5 bits
// (LOAD 0xFFFF reads back 0x1FFF), and loading one half leaves the other:
// oec loads only the half that changed.
void regen_load_ac_hi(regen_t *r, uint8_t hi);
void regen_load_ac_lo(regen_t *r, uint8_t lo);
uint8_t regen_ac_hi(const regen_t *r);
uint8_t regen_ac_lo(const regen_t *r);

// Store or fetch at the counter without moving it.
void regen_put_char(regen_t *r, uint8_t code);
void regen_put_eab(regen_t *r, uint8_t eab);
uint8_t regen_get_char(const regen_t *r);

// Step the counter, carrying into HI; 0x1FFF wraps to 0, as on the 3483-V
// (captured, #29).
void regen_advance(regen_t *r);

#endif
