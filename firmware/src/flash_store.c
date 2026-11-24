// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// The settings record's flash on the Fruit Jam (#69). See flash_store.h.

#include <assert.h>

#include "pico/stdlib.h"
#include "hardware/flash.h"
#include "hardware/regs/addressmap.h"

#include "flash_store.h"

static_assert(FLASH_STORE_PAGE == FLASH_PAGE_SIZE, "a slot's record is one flash page");

// The sector below the last. Every UF2 the SDK builds for the RP2350 starts
// with an absolute block at 0x10FFFF00, the RP2350-E10 workaround, and a
// reflash may write it. A second slot would go at the sector below this one.
static const uint32_t slot_offsets[FLASH_STORE_SLOTS] = {
    PICO_FLASH_SIZE_BYTES - 2u * FLASH_SECTOR_SIZE,
};

extern char __flash_binary_end;

const uint8_t *flash_store_slot(unsigned slot) {
    return (const uint8_t *)(XIP_NOCACHE_NOALLOC_NOTRANSLATE_BASE + slot_offsets[slot]);
}

bool flash_store_fits(void) {
    uintptr_t end = (uintptr_t)&__flash_binary_end - XIP_BASE;
    for (unsigned i = 0; i < FLASH_STORE_SLOTS; i++)
        if (end > slot_offsets[i])
            return false;
    return true;
}

uint32_t flash_store_write(unsigned slot, const uint8_t page[FLASH_STORE_PAGE]) {
    absolute_time_t start = get_absolute_time();
    flash_range_erase(slot_offsets[slot], FLASH_SECTOR_SIZE);
    flash_range_program(slot_offsets[slot], page, FLASH_STORE_PAGE);
    return (uint32_t)absolute_time_diff_us(start, get_absolute_time());
}
