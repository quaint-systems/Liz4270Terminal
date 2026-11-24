// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

#include <string.h>

#include "regen.h"

void regen_init(regen_t *r) {
    memset(r, 0, sizeof *r);
}

void regen_load_ac_hi(regen_t *r, uint8_t hi) {
    r->ac = (uint16_t)(((hi & 0x1Fu) << 8) | (r->ac & 0xFFu));
}

void regen_load_ac_lo(regen_t *r, uint8_t lo) {
    r->ac = (uint16_t)((r->ac & 0x1F00u) | lo);
}

uint8_t regen_ac_hi(const regen_t *r) {
    return (uint8_t)(r->ac >> 8);
}

uint8_t regen_ac_lo(const regen_t *r) {
    return (uint8_t)(r->ac & 0xFFu);
}

void regen_put_char(regen_t *r, uint8_t code) {
    r->chars[r->ac] = code;
}

void regen_put_eab(regen_t *r, uint8_t eab) {
    r->eab[r->ac] = eab;
}

uint8_t regen_get_char(const regen_t *r) {
    return r->chars[r->ac];
}

void regen_advance(regen_t *r) {
    r->ac = (uint16_t)((r->ac + 1u) & REGEN_ADDR_MASK);
}
