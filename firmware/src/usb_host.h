// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// USB host on the Fruit Jam (#14): keyboards through the on-board hub.
// Everything here runs on core 0.

#ifndef LIZ_USB_HOST_H
#define LIZ_USB_HOST_H

#include <stdbool.h>
#include <stdint.h>

#include "keyboard.h"

#define USB_HOST_HID_MAX 4u       // HID interfaces tracked: CFG_TUH_HID
#define USB_HOST_REPORT_BYTES 8u  // bytes kept of each report: a boot keyboard's
#define USB_HOST_LOG_SIZE 64u     // reports u log can hold between drains
#define USB_HOST_SENT_MAX 16u     // codes u log keeps of what a report queued

typedef struct {
    uint8_t dev;       // TinyUSB's device address
    uint8_t itf;       // interface number, 255 if unknown
    uint8_t proto;     // HID_ITF_PROTOCOL_NONE, _KEYBOARD or _MOUSE
    uint16_t vid, pid;
    uint32_t reports;  // this interface's, since it mounted
    const char *map;   // its keymap's name; NULL if it isn't a keyboard
} usb_host_hid_t;

typedef struct {
    uint32_t seq;  // the report's place in reports, from 1
    uint32_t ms;   // milliseconds since boot
    uint8_t dev, itf, len;
    uint8_t data[USB_HOST_REPORT_BYTES];
    uint8_t sent_count;                // codes the report queued (to 255); the first USB_HOST_SENT_MAX are in sent
    uint8_t sent[USB_HOST_SENT_MAX];
    bool swallowed;  // auto dim took the keys that woke it out (setup.h), so they never reached the translator
} usb_host_report_t;

typedef struct {
    uint32_t frames;            // frame IRQs since power-on
    uint32_t frame_cycles_max;  // in clk_sys cycles, since power-on or usb_host_clear
    uint32_t frame_cycles_avg;
    uint32_t overruns;          // frames of 1000 us or more, likewise
    uint32_t devices;           // mounted now; TinyUSB reports no hubs
    uint32_t hid;               // HID interfaces mounted now
    uint32_t reports;           // since power-on
    uint32_t rearm_fail;        // tuh_hid_receive_report refusals, each retried later, since power-on
    uint32_t xfer_fail;         // failed HID transfers, each retried later, since power-on
    uint32_t hub_fail;          // failed hub status polls, each queued again, since power-on
    uint32_t log_dropped;       // reports the full log had no room for, since power-on
    bool has_fault_flag;        // revision A's USB-A fault flag on GPIO6 (#97); the Fruit Jam has none
    bool fault;                 // the flag low now: the load switch is limiting or shut down
    uint32_t fault_trips;       // since power-on (usb_fault.h)
    bool have_last;
    usb_host_report_t last;
    unsigned dma_channel;       // Pico-PIO-USB's transmit DMA channel
    unsigned alarm;             // the frame timer's hardware alarm
    kbd_stats_t kbd;            // the keyboard translator's, since power-on or usb_host_clear
    uint8_t typematic_rate;     // and the Typematic Rate and Delay it times presses by (#107)
    uint8_t typematic_delay;
} usb_host_stats_t;

// Powers the host ports and starts TinyUSB in both roles (USB serial on the
// native port, the host on PIO0), then the 1 ms frame timer. Keyboards are
// translated into t's status queue (keyboard.h); t need not be initialised
// yet. Call on core 0, before stdio_init_all.
void usb_host_init(term_t *t);

// Runs TinyUSB's host task, and retries failed HID transfers when their time
// comes. Call from main's loop, beside tud_task.
void usb_host_poll(void);

void usb_host_stats(usb_host_stats_t *out);

// Zeroes the frame time counters, overruns and the keyboard counters; frames and the rest stay.
void usb_host_clear(void);

// The keyboard translator's keystrokes (kbd_keystrokes), which usb_host_clear
// leaves alone: what the clicker clicks for (#18).
uint32_t usb_host_keys(void);

// SetUp's share of them (kbd_local_keystrokes, #107).
uint32_t usb_host_local_keystrokes(void);

// The keyboard translator's bare Rule presses (kbd_rule_presses), which
// usb_host_clear leaves alone: what turns the ruler on and off (#51).
uint32_t usb_host_rule_presses(void);

// SetUp's local mode (kbd_local, #102): on, every key but Shift and Alt goes
// to SetUp, which usb_host_local_key takes, oldest first, with its Shift (#122).
void usb_host_local(bool on);
bool usb_host_local_key(uint8_t *key, bool *shift);

// SetUp's Typematic Rate and Delay (kbd_typematic, #107).
void usb_host_typematic(uint8_t rate, uint8_t delay);

// Slot 0 to USB_HOST_HID_MAX - 1: false if no HID interface holds it.
bool usb_host_hid(unsigned slot, usb_host_hid_t *out);

// The oldest report not yet taken: false if there is none.
bool usb_host_log_take(usb_host_report_t *out);

// "keyboard", "mouse" or "none", for usb_host_hid_t's proto.
const char *usb_host_proto_name(uint8_t proto);

#endif
