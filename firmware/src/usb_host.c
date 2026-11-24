// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// Liz4270 USB host (#14): TinyUSB's host stack on Pico-PIO-USB, into
// the on-board hub's upstream port on GPIO 1 (D+) and 2 (D-), with PIO0 to
// itself. Spec: docs/superpowers/specs/2026-10-05-usb-host-design.md.
//
// Everything here runs on core 0. Pico-PIO-USB sends and receives each packet
// with the CPU waiting on the PIO, so on core 1 it would break the coax link's
// 4 us answers. Its 1 ms frames run from a repeating timer of our own
// (skip_alarm_pool) at the highest IRQ priority: a handshake must go out
// within 2-7 bit times of a packet's end, 0.6 us at full speed, so nothing on
// core 0 may preempt a frame. The renderer (DMA_IRQ_0, lowest) waits; its
// 32-line ring holds about 1 ms. Each frame is timed with core 0's cycle
// counter for the console's u.
//
// Pico-PIO-USB claims its transmit DMA channel by number, and its default, 0,
// is the coax link's, so usb_host_init passes one it found free.
//
// Linking TinyUSB switches off pico_stdio_usb's own tusb_init and its
// background tud_task, so both roles start here and both tasks run from
// main's loop. TinyUSB's callbacks run in tuh_task, in that loop, where the
// console reads what they write; only the frame counters cross from an IRQ.
//
// Keyboards go through the core's translator (keyboard.c, #17): every boot
// report to kbd_report, typematic from usb_host_poll. Neither runs while a
// console reset is pending, when term_init may be running on core 1
// (coax_link.h). Once one lands, kbd_ready resyncs the translator's Shift and
// Alt, since the reset wiped whatever the queue held; the next report puts the
// rest right.

#include <string.h>

#include "pico/stdlib.h"
#include "pico/binary_info.h"
#include "hardware/clocks.h"
#include "hardware/dma.h"
#include "hardware/irq.h"
#include "hardware/sync.h"
#include "hardware/timer.h"
#include "hardware/structs/io_bank0.h"
#include "hardware/structs/m33.h"
#include "pio_usb.h"
#include "tusb.h"
#include "host/hub.h"
#include "host/usbh_pvt.h"  // usbh_class_driver_t, for hub_driver

#include "board.h"
#include "board_detect.h"
#include "coax_link.h"
#include "keyboard.h"
#include "keymap.h"
#include "setup.h"
#include "usb_fault.h"
#include "usb_host.h"

#if !LIZ_TUSB_CONFIG
#error "the tusb_config.h in use is not firmware/src/tinyusb/tusb_config.h"
#endif

static_assert(LIZ_USB_HOST_DM_PIN == LIZ_USB_HOST_DP_PIN + 1, "PIO_USB_PINOUT_DPDM needs D- = D+ + 1");
static_assert(CFG_TUH_HID == USB_HOST_HID_MAX, "one slot per TinyUSB HID interface");
static_assert(KBD_SOURCES == USB_HOST_HID_MAX, "one translator source per HID slot");

#define USB_HOST_RHPORT 1u  // TinyUSB's port for Pico-PIO-USB; 0 is the native USB device
#define FRAME_US 1000
#define RETRY_MS 100  // after a failed HID transfer or a refused re-arm
#define FAILS_TO_RELEASE 2u  // failed transfers in a row that let go of an interface's keys

bi_decl(bi_2pins_with_names(LIZ_USB_HOST_DP_PIN, "USB host D+", LIZ_USB_HOST_DM_PIN, "USB host D-"));
bi_decl(bi_1pin_with_name(LIZ_USB_HOST_POWER_PIN, "USB host 5V power"));
bi_decl(bi_1pin_with_name(LIZ_USB_HOST_FAULT_PIN, "USB host fault flag (rev A)"));

static repeating_timer_t frame_timer;
static unsigned dma_channel, alarm_num;
static uint32_t overrun_cycles;

// Written by the frame IRQ. usb_host_stats and usb_host_clear take them with
// interrupts off, so the 64-bit sum isn't torn.
static volatile uint32_t frames, frame_cycles_max, frames_timed, overruns;
static volatile uint64_t frame_cycles_sum;

// Written by TinyUSB's callbacks in tuh_task, and read by the console, both
// in main's loop.
typedef struct {
    bool in_use;
    uint8_t failed;            // transfers failed in a row, to FAILS_TO_RELEASE
    absolute_time_t retry_at;  // nil unless a failed transfer or re-arm waits to be retried
    usb_host_hid_t hid;
} hid_slot_t;

// Indexed by TinyUSB's HID index, which counts over every device's HID
// interfaces (hid_host.c's _hidh_itf), not within one device. It is also the
// translator's source.
static hid_slot_t slots[USB_HOST_HID_MAX];
static kbd_t kbd;
static uint32_t resets_seen;  // coax_link_resets() when the translator last resynced
static uint32_t reports, rearm_fail, xfer_fail, hub_fail, log_dropped;
static bool have_last;
static usb_host_report_t last;
static bool has_fault_flag;  // revision A only (#97)
static usb_fault_t fault;
static usb_host_report_t log_ring[USB_HOST_LOG_SIZE];
static uint32_t log_head, log_count;

// Revision A's fault flag, each frame (#97). It is read here rather than from
// the main loop, which set save's erase holds up for about 45 ms: a trip is
// re-armed only once the flag has been seen high for 20 ms, so a second trip
// within such a wait would be counted with the first. The flag's edge latch
// (IO_BANK0's raw INTR, set with no interrupt enabled) catches a fall
// shorter than a frame.
static void poll_fault(void) {
    const uint pin = LIZ_USB_HOST_FAULT_PIN;
    bool fell = (io_bank0_hw->intr[pin / 8u] >> (4u * (pin % 8u))) & GPIO_IRQ_EDGE_FALL;
    if (fell)
        gpio_acknowledge_irq(pin, GPIO_IRQ_EDGE_FALL);
    usb_fault_poll(&fault, to_ms_since_boot(get_absolute_time()), !gpio_get(pin), fell);
}

static bool frame_callback(repeating_timer_t *rt) {
    (void)rt;
    uint32_t start = m33_hw->dwt_cyccnt;
    pio_usb_host_frame();
    uint32_t took = m33_hw->dwt_cyccnt - start;
    frames++;
    frames_timed++;
    frame_cycles_sum += took;
    if (took > frame_cycles_max)
        frame_cycles_max = took;
    if (took >= overrun_cycles)
        overruns++;
    if (has_fault_flag)
        poll_fault();  // after the timing: frame_us_max is the frame's own
    return true;
}

void usb_host_init(term_t *t) {
    kbd_init(&kbd, t);
    // Before the ports are powered, so a fault from the start counts. R35
    // pulls the flag up; the pad's own pull-up beside it keeps a bare pin
    // high on a Fruit Jam standing in for revision A (#97).
    usb_fault_init(&fault);
    has_fault_flag = board_has_usb_fault(board_detected().board);
    if (has_fault_flag) {
        gpio_init(LIZ_USB_HOST_FAULT_PIN);
        gpio_pull_up(LIZ_USB_HOST_FAULT_PIN);
        gpio_acknowledge_irq(LIZ_USB_HOST_FAULT_PIN, GPIO_IRQ_EDGE_FALL);
    }
    gpio_init(LIZ_USB_HOST_POWER_PIN);
    gpio_set_dir(LIZ_USB_HOST_POWER_PIN, GPIO_OUT);
    gpio_put(LIZ_USB_HOST_POWER_PIN, 1);

    // The frames are timed with core 0's cycle counter, as video.c times lines.
    m33_hw->demcr |= M33_DEMCR_TRCENA_BITS;
    m33_hw->dwt_ctrl |= M33_DWT_CTRL_CYCCNTENA_BITS;
    overrun_cycles = clock_get_hz(clk_sys) / 1000000u * FRAME_US;

    int channel = dma_claim_unused_channel(true);
    dma_channel_unclaim((uint)channel);  // Pico-PIO-USB claims it by number
    dma_channel = (unsigned)channel;

    pio_usb_configuration_t config = PIO_USB_DEFAULT_CONFIG;
    config.pin_dp = LIZ_USB_HOST_DP_PIN;
    config.pinout = PIO_USB_PINOUT_DPDM;
    config.tx_ch = (uint8_t)dma_channel;
    config.skip_alarm_pool = true;
    tuh_configure(USB_HOST_RHPORT, TUH_CFGID_RPI_PIO_USB_CONFIGURATION, &config);

    const tusb_rhport_init_t device = {.role = TUSB_ROLE_DEVICE, .speed = TUSB_SPEED_AUTO};
    const tusb_rhport_init_t host = {.role = TUSB_ROLE_HOST, .speed = TUSB_SPEED_AUTO};
    tusb_init(0, &device);
    tusb_init(USB_HOST_RHPORT, &host);

    alarm_pool_t *pool = alarm_pool_create_with_unused_hardware_alarm(1);
    alarm_num = alarm_pool_hardware_alarm_num(pool);
    irq_set_priority(hardware_alarm_get_irq_num(alarm_num), PICO_HIGHEST_IRQ_PRIORITY);
    alarm_pool_add_repeating_timer_us(pool, -FRAME_US, frame_callback, NULL, &frame_timer);
}

static void receive_next(uint8_t dev, uint8_t idx);

// Whether the translator may queue keys: not while a console reset is
// pending. After one lands it resyncs first, so the controller's Shift and
// Alt match the PC's again (#17).
static bool kbd_ready(void) {
    if (coax_link_reset_pending())
        return false;
    uint32_t resets = coax_link_resets();
    if (resets != resets_seen) {
        resets_seen = resets;
        kbd_resync(&kbd);
    }
    return true;
}

void usb_host_poll(void) {
    tuh_task();
    for (unsigned i = 0; i < USB_HOST_HID_MAX; i++) {
        hid_slot_t *slot = &slots[i];
        if (slot->in_use && !is_nil_time(slot->retry_at) && time_reached(slot->retry_at)) {
            slot->retry_at = nil_time;
            receive_next(slot->hid.dev, (uint8_t)i);
        }
    }
    if (kbd_ready())
        kbd_tick(&kbd, to_ms_since_boot(get_absolute_time()));
}

void usb_host_stats(usb_host_stats_t *out) {
    uint32_t save = save_and_disable_interrupts();
    out->frames = frames;
    out->frame_cycles_max = frame_cycles_max;
    out->overruns = overruns;
    uint64_t sum = frame_cycles_sum;
    uint32_t timed = frames_timed;
    restore_interrupts(save);
    out->frame_cycles_avg = timed ? (uint32_t)(sum / timed) : 0u;

    uint32_t hid = 0;
    for (unsigned i = 0; i < USB_HOST_HID_MAX; i++)
        hid += slots[i].in_use;
    // TinyUSB's own record, not a count kept from tuh_mount_cb and tuh_umount_cb:
    // a device unplugged mid-enumeration gets an umount with no mount. Hubs
    // take the addresses above CFG_TUH_DEVICE_MAX, so they never count.
    uint32_t devices = 0;
    for (uint8_t daddr = 1; daddr <= CFG_TUH_DEVICE_MAX; daddr++)
        devices += tuh_mounted(daddr);
    out->devices = devices;
    out->hid = hid;
    out->reports = reports;
    out->rearm_fail = rearm_fail;
    out->xfer_fail = xfer_fail;
    out->hub_fail = hub_fail;
    out->log_dropped = log_dropped;
    out->has_fault_flag = has_fault_flag;
    out->fault = has_fault_flag && !gpio_get(LIZ_USB_HOST_FAULT_PIN);
    out->fault_trips = usb_fault_trips(&fault);
    out->have_last = have_last;
    out->last = last;
    kbd_stats(&kbd, &out->kbd);
    out->typematic_rate = kbd_rate(&kbd);
    out->typematic_delay = kbd_delay(&kbd);
    out->dma_channel = dma_channel;
    out->alarm = alarm_num;
}

void usb_host_clear(void) {
    uint32_t save = save_and_disable_interrupts();
    frame_cycles_max = 0;
    frame_cycles_sum = 0;
    frames_timed = 0;
    overruns = 0;
    restore_interrupts(save);
    kbd_clear_stats(&kbd);
}

uint32_t usb_host_keys(void) {
    return kbd_keystrokes(&kbd);
}

uint32_t usb_host_local_keystrokes(void) {
    return kbd_local_keystrokes(&kbd);
}

uint32_t usb_host_rule_presses(void) {
    return kbd_rule_presses(&kbd);
}

void usb_host_local(bool on) {
    kbd_local(&kbd, on);
}

bool usb_host_local_key(uint8_t *key, bool *shift) {
    return kbd_local_key(&kbd, key, shift);
}

void usb_host_typematic(uint8_t rate, uint8_t delay) {
    kbd_typematic(&kbd, rate, delay);
}

bool usb_host_hid(unsigned slot, usb_host_hid_t *out) {
    if (slot >= USB_HOST_HID_MAX || !slots[slot].in_use)
        return false;
    *out = slots[slot].hid;
    return true;
}

bool usb_host_log_take(usb_host_report_t *out) {
    if (!log_count)
        return false;
    *out = log_ring[log_head];
    log_head = (log_head + 1u) % USB_HOST_LOG_SIZE;
    log_count--;
    return true;
}

const char *usb_host_proto_name(uint8_t proto) {
    return proto == HID_ITF_PROTOCOL_KEYBOARD ? "keyboard" : proto == HID_ITF_PROTOCOL_MOUSE ? "mouse" : "none";
}

// TinyUSB's HID callbacks, from tuh_task.

static hid_slot_t *slot_at(uint8_t dev, uint8_t idx) {
    return idx < USB_HOST_HID_MAX && slots[idx].in_use && slots[idx].hid.dev == dev ? &slots[idx] : NULL;
}

static uint8_t interface_number(uint8_t dev, uint8_t idx) {
    tuh_itf_info_t info;
    return tuh_hid_itf_get_info(dev, idx, &info) ? info.desc.bInterfaceNumber : 0xFFu;
}

// A refusal is retried later too, or the interface would stay silent.
static void receive_next(uint8_t dev, uint8_t idx) {
    if (tuh_hid_receive_report(dev, idx))
        return;
    rearm_fail++;
    hid_slot_t *slot = slot_at(dev, idx);
    if (slot)
        slot->retry_at = make_timeout_time_ms(RETRY_MS);
}

void tuh_hid_mount_cb(uint8_t dev, uint8_t idx, const uint8_t *desc, uint16_t len) {
    (void)desc;
    (void)len;
    if (idx < USB_HOST_HID_MAX) {
        hid_slot_t *slot = &slots[idx];
        slot->in_use = true;
        slot->failed = 0;
        slot->retry_at = nil_time;
        slot->hid = (usb_host_hid_t){
            .dev = dev,
            .itf = interface_number(dev, idx),
            .proto = tuh_hid_interface_protocol(dev, idx),
        };
        tuh_vid_pid_get(dev, &slot->hid.vid, &slot->hid.pid);
        const keymap_t *map =
            slot->hid.proto == HID_ITF_PROTOCOL_KEYBOARD ? keymap_for(slot->hid.vid, slot->hid.pid) : NULL;
        slot->hid.map = map ? map->name : NULL;
        kbd_attach(&kbd, idx, map);
        setup_forget(idx);
    }
    receive_next(dev, idx);
}

void tuh_hid_umount_cb(uint8_t dev, uint8_t idx) {
    hid_slot_t *slot = slot_at(dev, idx);
    if (!slot)
        return;
    if (kbd_ready())
        kbd_detach(&kbd, idx);
    else
        kbd_attach(&kbd, idx, NULL);  // forget it without queueing: term_init may be running
    setup_forget(idx);
    slot->in_use = false;
}

void tuh_hid_report_received_cb(uint8_t dev, uint8_t idx, const uint8_t *report, uint16_t len) {
    hid_slot_t *slot = slot_at(dev, idx);
    if (len == 0) {
        // TinyUSB reports a failed transfer as a zero-length report (hidh_xfer_cb
        // ignores the result). Retrying at once put a transaction to a vanished
        // device in every frame, and one of them failed the hub's status poll
        // (#14; hub_driver below now polls again). By the retry, an unplug has
        // usually closed this; if not, the retry fails again, harmlessly.
        xfer_fail++;
        if (slot) {
            slot->retry_at = make_timeout_time_ms(RETRY_MS);
            // A key held through an unplug must not repeat forever (#17), but one
            // failure may be a glitch with the keyboard still there: letting go
            // then had the next report press the held keys again. After an
            // unplug the retry fails too.
            if (slot->failed < FAILS_TO_RELEASE)
                slot->failed++;
            if (slot->failed == FAILS_TO_RELEASE && kbd_ready())
                kbd_release_all(&kbd, idx);
        }
        return;
    }
    reports++;
    if (slot) {
        slot->hid.reports++;
        slot->failed = 0;
    }

    usb_host_report_t r = {
        .seq = reports,
        .ms = to_ms_since_boot(get_absolute_time()),
        .dev = dev,
        .itf = slot ? slot->hid.itf : interface_number(dev, idx),
        .len = (uint8_t)MIN(len, USB_HOST_REPORT_BYTES),
    };
    memcpy(r.data, report, r.len);
    // Only a boot keyboard report, which is 8 bytes. The bench 104-key's second
    // interface claims the boot keyboard protocol but sends 3-byte consumer
    // reports with a report ID (01 23 02 is AC Home), whose first byte would
    // read as Left Ctrl, and so Reset (#17).
    if (slot && slot->hid.map && len == USB_HOST_REPORT_BYTES && kbd_ready()) {
        // Auto dim takes out the keys that woke it, until each is let go.
        uint8_t keys[USB_HOST_REPORT_BYTES];
        r.swallowed = setup_report(idx, r.ms, report, keys);
        size_t sent = kbd_report(&kbd, idx, keys, r.ms, r.sent, USB_HOST_SENT_MAX);
        r.sent_count = (uint8_t)MIN(sent, 255u);
    }
    kbd_redact(&kbd, r.data, r.len);  // what's typed in SetUp or at the lock stays off the console (#122)
    last = r;
    have_last = true;
    if (log_count == USB_HOST_LOG_SIZE) {
        log_dropped++;
    } else {
        log_ring[(log_head + log_count) % USB_HOST_LOG_SIZE] = r;
        log_count++;
    }
    receive_next(dev, idx);
}

// TinyUSB's hub driver, but a failed status poll is queued again. Its own
// hub_xfer_cb gives up after a failure, and the hub then reports no plug or
// unplug until reset (#14). Application drivers come before the built-in
// ones, so this one takes the hub's interface; init and close run twice,
// harmlessly.
static bool hub_xfer_rearm(uint8_t dev, uint8_t ep, xfer_result_t result, uint32_t len) {
    if (result != XFER_RESULT_SUCCESS) {
        hub_fail++;
        return hub_edpt_status_xfer(dev);
    }
    return hub_xfer_cb(dev, ep, result, len);
}

static const usbh_class_driver_t hub_driver = {
    .name = "HUB",
    .init = hub_init,
    .deinit = hub_deinit,
    .open = hub_open,
    .set_config = hub_set_config,
    .xfer_cb = hub_xfer_rearm,
    .close = hub_close,
};

const usbh_class_driver_t *usbh_app_driver_get_cb(uint8_t *count) {
    *count = 1;
    return &hub_driver;
}
