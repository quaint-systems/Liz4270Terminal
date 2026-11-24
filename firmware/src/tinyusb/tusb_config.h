// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// Liz4270's TinyUSB configuration (#14). This directory is on the
// include path ahead of pico_stdio_usb's own tusb_config.h, which is empty
// once the application links TinyUSB.
//
// Device on rhport0, the native USB: USB serial, as pico_stdio_usb sets it,
// so the console and rig.py see the same port. Host on rhport1: Pico-PIO-USB,
// through the board's USB hub (usb_host.c).

#ifndef LIZ_TUSB_CONFIG_H
#define LIZ_TUSB_CONFIG_H

#define LIZ_TUSB_CONFIG 1  // usb_host.c checks that this file is the one in use

#define CFG_TUD_ENABLED 1
#define CFG_TUH_ENABLED 1
#define CFG_TUH_RPI_PIO_USB 1

// Device: as pico_stdio_usb's tusb_config.h.
#define CFG_TUD_CDC 1
#define CFG_TUD_CDC_RX_BUFSIZE (TUD_OPT_HIGH_SPEED ? 512 : 64)
#define CFG_TUD_CDC_TX_BUFSIZE (TUD_OPT_HIGH_SPEED ? 512 : 64)
#define CFG_TUD_CDC_EP_BUFSIZE (TUD_OPT_HIGH_SPEED ? 512 : 64)
#define CFG_TUD_VENDOR 0  // pico_usb_reset's interface has its own driver

// Host: the hub, in a slot of its own, and up to four devices behind it.
// Room for a large keyboard's whole configuration descriptor: a longer one
// fails enumeration in a way that stops the hub reporting plugs (usbh.c).
#define CFG_TUH_ENUMERATION_BUFSIZE 1024
#define CFG_TUH_HUB 1
#define CFG_TUH_DEVICE_MAX 4
#define CFG_TUH_HID 4  // USB_HOST_HID_MAX
#define CFG_TUH_HID_EPIN_BUFSIZE 64
#define CFG_TUH_HID_EPOUT_BUFSIZE 64

#endif
