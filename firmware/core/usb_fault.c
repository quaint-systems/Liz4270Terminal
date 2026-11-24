// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// Revision A's USB fault flag (#97). See usb_fault.h.

#include "usb_fault.h"

size_t usb_fault_sizeof(void) {
    return sizeof(usb_fault_t);
}

void usb_fault_init(usb_fault_t *f) {
    *f = (usb_fault_t){0};
}

void usb_fault_poll(usb_fault_t *f, uint32_t ms, bool low, bool fell) {
    if (low || fell) {
        if (!f->tripped) {
            f->trips++;
            f->tripped = true;
        }
        f->low_ms = ms;
    } else if (f->tripped && ms - f->low_ms >= USB_FAULT_REARM_MS) {
        f->tripped = false;
    }
}

uint32_t usb_fault_trips(const usb_fault_t *f) {
    return f->trips;
}
