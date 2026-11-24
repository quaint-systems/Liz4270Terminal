// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// The settings record's flash on the Fruit Jam (#69): a table of slots, each
// a 4 KB sector near the end of flash, read through XIP and rewritten whole.
//
// A write takes XIP down while core 1, the video's DMA and every interrupt
// keep running. That's safe because nothing reads flash while the firmware
// runs: it runs from SRAM (copy_to_ram), both cores' vector tables are in
// RAM, and only the boot code, binary_info and the default fault handlers stay
// in flash. check_flash_sections.cmake fails the build if anything else does.
// So there's no flash_safe_execute, which would pause core 1 and miss polls.
// Core 0's main loop waits for the erase: about 45 ms, up to 400 ms.

#ifndef LIZ_FLASH_STORE_H
#define LIZ_FLASH_STORE_H

#include <stdbool.h>
#include <stdint.h>

// One slot now. A second, for saves that alternate, goes in flash_store.c's table.
#define FLASH_STORE_SLOTS 1u
#define FLASH_STORE_PAGE 256u

// Slot's bytes, through XIP with no cache and no address translation, as the
// erase and program see them.
const uint8_t *flash_store_slot(unsigned slot);

// Whether the image ends below every slot.
bool flash_store_fits(void);

// Erases slot's sector and programs page at its start: the microseconds taken.
// Core 0's main loop only.
uint32_t flash_store_write(unsigned slot, const uint8_t page[FLASH_STORE_PAGE]);

#endif
