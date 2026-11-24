// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// Revision A's USB fault flag (#97): the AP2171W load switch that powers both
// USB-A ports pulls its open-drain FLG low on over-current or thermal
// shutdown, and holds it off through a blanking time, so a dip at plug-in
// never shows. Each time the flag goes low is one trip. It is re-armed once
// the flag has read high for USB_FAULT_REARM_MS, so a wire touched to the pin
// on the bench counts once however it bounces.
//
// Plain C11, like the rest of the core: the caller passes the time in
// milliseconds, which may wrap, and the pin as it reads it.

#ifndef LIZ_USB_FAULT_H
#define LIZ_USB_FAULT_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define USB_FAULT_REARM_MS 20u

// Defined here so the caller can allocate it. The fields are private to usb_fault.c.
typedef struct {
    uint32_t trips;
    uint32_t low_ms;  // when the flag last read low, or fell
    bool tripped;     // counted, and not yet re-armed
} usb_fault_t;

size_t usb_fault_sizeof(void);  // for ctypes, which can't see sizeof

// No trips yet.
void usb_fault_init(usb_fault_t *f);

// Every millisecond or so: low is the flag now, and fell says whether its pin
// has fallen since the last poll (the GPIO's edge latch), so a trip that ends
// between two polls still counts. Re-arming needs a poll that sees the flag
// high, so a gap in the polls longer than USB_FAULT_REARM_MS can count two
// trips as one; the firmware polls from the USB frame timer, which nothing
// holds up.
void usb_fault_poll(usb_fault_t *f, uint32_t ms, bool low, bool fell);

// Since usb_fault_init.
uint32_t usb_fault_trips(const usb_fault_t *f);

#endif
