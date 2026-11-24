// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// DVI on the Fruit Jam (#26): the regen buffer drawn over HSTX, from a ring
// of lines that render.c fills just ahead of the beam. Core 0 only.

#ifndef LIZ_VIDEO_H
#define LIZ_VIDEO_H

#include <stdbool.h>
#include <stdint.h>

#include "term.h"

typedef enum {
    VIDEO_640X480,  // the default
    VIDEO_720X480,
} video_mode_t;

typedef struct {
    const char *mode;           // "640x480" or "720x480"
    uint32_t clk_hstx_khz;      // measured
    uint32_t fps;               // frames a second, measured over a window of at least 1 s
    uint32_t line_cycles_max;   // drawing one line, in clk_sys cycles, since the last start, restart or the splash's end
    uint32_t line_cycles_avg;   // (so the splash's lines while it shows, and render.c's alone after)
    uint32_t frame_cycles_max;  // render_frame_begin, in clk_sys cycles, likewise
    uint32_t late;              // lines sent before they were drawn, since power-on
    uint32_t restarts;          // restarts by the stall check, since power-on
    const char *last_restart;   // the last one's cause: "stall", or "error" for a DMA bus error; "none" before one
    bool has_hpd;               // revision A's HDMI hot-plug detect on GPIO7 (#97); the Fruit Jam has none
    bool hpd;                   // read now: high while a monitor drives it
} video_stats_t;

// Once, at power-on: claims two DMA channels and DMA_IRQ_0, and starts mode
// with the splash screen (splash.c), which shows for at least 3 s and then
// until the controller writes t's regen buffer (term_written). After it, the
// drawing reads t's regen buffer, address counter and control register, and the settings (setup.h).
void video_init(const term_t *t, video_mode_t mode);

// SetUp (#102) takes the screen: the splash ends at once, for good. setup.c
// calls it as SetUp opens. From thread context on core 0.
void video_splash_dismiss(void);

// Frames begun since power-on, splash or screen: once it moves past a value
// read, the renderer has read SetUp's front image anew (setup.c's double
// buffer, #102).
uint32_t video_frames_begun(void);

// Alarm volume Off's flash (#107): every cell's reverse flipped from now for
// ms, from core 0's loop. A second call restarts it, and 0 ends one showing
// (an Alarm volume preview's, audio.c).
void video_flash(uint32_t ms);

// Stops, re-times pll_usb and HSTX, and starts again in mode. Core 1 and the
// coax link never notice. From thread context on core 0, not from an IRQ.
void video_set_mode(video_mode_t mode);

// From the main loop, every millisecond or so, in thread context on core 0
// (not from an IRQ): measures the frame rate, and restarts the video if the
// scan-out's DMA chain has stood still for 100 ms. Polls more than 10 ms apart
// (the main loop held up) count as the chain moving, since its place in the
// list comes round every frame.
void video_poll(void);

// A bench aid (the console's v hold): holds the render IRQ off for ms
// milliseconds, so the renderer falls behind the beam on purpose and has to
// catch up; late counts the lines sent undrawn. The renderer finds the beam
// from the chain's place in its list, which repeats every frame, so late
// counts only the part of a frame the beam moved on: a hold of exactly whole
// frames (50 ms at 640x480) adds nothing. From thread context on core 0; the
// console allows 1-50 ms.
void video_hold(uint32_t ms);

// A bench aid (the console's v stall): stops the scan-out's DMA chain, so
// video_poll has to find the stall and restart the video (restarts rises and
// last_restart becomes "stall"). From thread context on core 0.
void video_stall(void);

void video_stats(video_stats_t *out);

#endif
