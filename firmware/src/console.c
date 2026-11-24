// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// Line commands over USB serial, on core 0.
//
// Each command prints its output lines, then "ok" or "err <reason>", so a
// script reads up to that line. An empty line answers "ok": a script sends
// one to find the end of the banner. Lines end at CR, LF or CR LF, and
// nothing is echoed.
//
// A reset that answers "err timeout" still happens when the frame in
// progress ends. Until then, k and r answer "err reset pending". While a
// model change has the link off the coax, they answer "err offline" (#110).
//
//   s              one line of key=value counters; model= and offline= say
//                  what the coax link answers as, and whether a model change
//                  has it off the coax (#110)
//   k CODE         queue scan code CODE (decimal) for the next POLLs
//   r [eab|base]   power-on reset, optionally switching EAB on or off
//   d              the address counter, control register and regen buffer
//   v [640|720]    video: the mode and counters, or switch mode
//   v hold MS      hold the renderer off for MS (1-50) milliseconds
//   v stall        stop the scan-out's DMA chain
//   v dim          auto dim on now; a key or a write ends it, and so does the
//                  next tick with auto dim off; at page 1's Lock sessions Yes
//                  with a password set, the lock instead (#122)
//   v rule         the ruler on or off, as a bare Rule press turns it (#51)
//   set            the settings (settings.h) on one line, with password=set
//                  or password=none, which only Password Set changes (#122),
//                  ending saved=yes if flash holds them as they are, or
//                  saved=no
//   set NAME VALUE cursor underline|block, blink on|off, indicator on|off,
//                  dim off|5|10|20, input|input-hi|protected|protected-hi
//                  COLOUR (red, pink, green, yellow, blue, turquoise or
//                  white), mono on|off, rule horizontal|vertical|cross|none,
//                  rule-colour white|green, rule-follows on|off,
//                  typematic-rate normal|fast, typematic-delay
//                  short|normal|long, click on|off, click-volume or
//                  alarm-volume off|1|2|3|4|high, or mono-case on|off (#107),
//                  model 2|3|4 (#110), or lock-sessions on|off (#122):
//                  SetUp's Display Setup choices,
//                  monochrome (#50) and the model, live until set save. A
//                  new model takes the terminal off the coax for a second
//                  and back with a power-on reset at it, as leaving the
//                  3483-V's offline setup does
//   set save       write the settings to flash, as SetUp's F3=Exit: "saved N
//                  ms" or "unchanged", then ok (#69)
//   set defaults   the defaults, live until set save
//   u              USB host: counters, the keyboard translator's with the
//                  Typematic Rate and Delay it times by (#107), then one line
//                  per HID interface with its keymap
//   u clear        zero the frame time counters, overruns and the keyboard's
//   u log          the HID reports since the last u log, oldest first, each with
//                  the scan codes it queued, and "swallowed" if auto dim took the
//                  keys that woke it out
//   b              the DAC (audio.h): its state, counters, b level's override,
//                  each volume and its level, the lengths, and its power flags
//                  read back
//   b click [MS]   sound the key click at Click Volume's level, first setting
//                  its length to MS (1-5000) until power-off (#18, #107)
//   b alarm [MS]   the same for the alarm, which is the flash at Alarm volume Off
//   b flash [MS]   Alarm volume Off's flash, likewise (#107)
//   b level DB     every sound at DB, 2 to -61, until power-off or b level
//                  off, then a click at it; b level off goes back to the
//                  volumes. A volume at Off stays silent (the alarm: the flash)
//   b reg PPRR     the DAC's register RR on page PP, in hex; b reg PPRR=VV
//                  writes VV there
//   setup          SetUp (#102): which screen is up (off, menu, page1-page4,
//                  offline, customize: offline setup's, #110; password:
//                  Password Set, #122) and its counters: opens, keys,
//                  alarms, saves and save_fails (its writes to flash, as it
//                  closes and Password Set's at once, and those that failed);
//                  and the lock (#122): lock=off|black|prompt, locks,
//                  unlocks, wrong
//   setup key NAME one key into SetUp, as the keyboard hands it: setup (which
//                  opens it), up, down, left, right, space, enter, f3, f7,
//                  f8, f11, or a 3483-V code (0-255); while the terminal is
//                  locked, into the lock (#122)
//
// v hold, v stall, v dim, v rule and setup key are bench aids. v dim shows
// auto dim at once, so a check needn't wait 10 minutes; v rule turns the
// ruler on and off with no keyboard, and setup key walks SetUp with none.
// v hold makes the renderer fall behind the beam on purpose, so a check can
// see it catch up (late rises, restarts doesn't). v stall stops the
// scan-out, so a check can see the stall check restart it (restarts rises,
// last_restart=stall). b's lengths and level are for matching the 3483-V by
// ear, and b reg is for trying the DAC's settings live.
//
// tools/sim/rig.py speaks this protocol.

#include <ctype.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "pico/stdlib.h"

#include "coax_link.h"
#include "console.h"

#include "board.h"
#include "hardware/clocks.h"
#include "setup.h"
#include "video.h"
#include "usb_host.h"
#include "audio.h"
#include "render.h"
#include "ruler.h"
#include "keys3483.h"

#define CONSOLE_LINE_MAX 32u
#define RESET_TIMEOUT_MS 100u
#define DUMP_LINE_BYTES 64u
#define HOLD_MS_MAX 50u
#define USAGE_V "err usage: v [640|720|dim|stall|rule|hold MS]"
#define USAGE_SET                                                                                       \
    "err usage: set [save | defaults | cursor underline|block | blink on|off | indicator on|off "        \
    "| dim off|5|10|20 | input|input-hi|protected|protected-hi red|pink|green|yellow|blue|turquoise|white " \
    "| mono on|off | rule horizontal|vertical|cross|none | rule-colour white|green | rule-follows on|off "  \
    "| typematic-rate normal|fast | typematic-delay short|normal|long | click on|off "                    \
    "| click-volume|alarm-volume off|1|2|3|4|high | mono-case on|off | model 2|3|4 "                     \
    "| lock-sessions on|off]"
#define USAGE_U "err usage: u [clear|log]"
#define USAGE_B "err usage: b [click [MS]|alarm [MS]|flash [MS]|level DB|level off|reg PPRR[=VV]]"
#define USAGE_SETUP "err usage: setup [key setup|up|down|left|right|space|enter|f3|f7|f8|f10|f11|CODE]"
#define BEEP_MS_MAX 5000u

static char line[CONSOLE_LINE_MAX];
static size_t line_len;
static bool line_too_long;
static bool after_cr;  // a LF straight after a CR ends no second line

static void stats_command(const term_t *t) {
    coax_link_stats_t s;
    coax_link_stats(&s);
    printf("frames=%" PRIu32 " words=%" PRIu32 " answers=%" PRIu32 " silent=%" PRIu32
           " echoes=%" PRIu32 " backlog_max=%" PRIu32 " overruns=%" PRIu32 " tx_busy=%" PRIu32
           " turnaround_max_us=%" PRIu32 " queued=%u clicker=%d alarms=%" PRIu32
           " unknown=%" PRIu32 " last_unknown=%03x no_feature=%" PRIu32 " last_no_feature=%03x"
           " model=%u offline=%d eab=%d\n",
           s.frames, s.words, s.answers, s.silent, s.echoes, s.backlog_max, s.overruns,
           s.tx_busy, s.turnaround_max_us, term_queued(t), (int)term_clicker(t),
           term_alarms(t), term_unknown(t), (unsigned)term_last_unknown(t), term_no_feature(t),
           (unsigned)term_last_no_feature(t), (unsigned)coax_link_model(), (int)coax_link_offline(),
           (int)coax_link_eab());
    puts("ok");
}

static void key_command(term_t *t, const char *arg) {
    char *end = NULL;
    unsigned long code = arg ? strtoul(arg, &end, 10) : 0;
    if (!arg || *end != '\0' || code > 0xFFu) {
        puts("err usage: k CODE (0-255)");
        return;
    }
    if (coax_link_reset_pending()) {
        puts("err reset pending");
        return;
    }
    if (coax_link_offline()) {
        puts("err offline");
        return;
    }
    bool queued = term_key(t, (uint8_t)code);
    if (queued)
        setup_key();  // activity, as a keystroke is, but never swallowed
    puts(queued ? "ok" : "err full");
}

static void reset_command(const char *arg) {
    coax_reset_t reset;
    if (!arg) {
        reset = COAX_RESET_KEEP;
    } else if (strcmp(arg, "eab") == 0) {
        reset = COAX_RESET_EAB;
    } else if (strcmp(arg, "base") == 0) {
        reset = COAX_RESET_BASE;
    } else {
        puts("err usage: r [eab|base]");
        return;
    }
    if (coax_link_reset_pending()) {
        puts("err reset pending");
        return;
    }
    if (coax_link_offline()) {
        puts("err offline");
        return;
    }
    puts(coax_link_reset(reset, RESET_TIMEOUT_MS) ? "ok" : "err timeout");
}

// v hold MS: the bench aid that makes the renderer fall behind on purpose.
static void hold_command(const char *text) {
    char *end = NULL;
    unsigned long ms = strtoul(text, &end, 10);
    if (*end != '\0' || ms < 1u || ms > HOLD_MS_MAX) {
        puts(USAGE_V);
        return;
    }
    video_hold((uint32_t)ms);
    puts("ok");
}

// The ruler's cell now (#51), as RRRR/CCC counted from 1 like the status
// line's indicator, or off while none is drawn (off, or Style none); then
// the line's end.
static void print_ruler(const term_t *t) {
    const settings_t *s = setup_settings();
    uint16_t at = ruler_address(setup_ruler(), term_ac(t), s->ruler_follows);
    if (at == RULER_OFF || s->ruler_style > SETTINGS_RULER_CROSS) {
        puts("off");
        return;
    }
    uint8_t text[8];
    render_indicator_text(render_place(at, coax_link_model()), text, '0', '/');
    printf("%.8s\n", (const char *)text);
}

// ms is the word after arg: only v hold takes one.
static void video_command(const term_t *t, const char *arg, const char *ms) {
    if (!arg) {
        video_stats_t v;
        video_stats(&v);
        uint32_t per_us = clock_get_hz(clk_sys) / 1000000u;
        uint32_t max = v.line_cycles_max * 100u / per_us, avg = v.line_cycles_avg * 100u / per_us;
        uint32_t frame_max = v.frame_cycles_max * 100u / per_us;
        printf("mode=%s clk_hstx=%" PRIu32 " fps=%" PRIu32 " line_us_max=%" PRIu32 ".%02" PRIu32
               " line_us_avg=%" PRIu32 ".%02" PRIu32 " frame_us_max=%" PRIu32 ".%02" PRIu32
               " late=%" PRIu32 " restarts=%" PRIu32 " last_restart=%s dim=%s hpd=%s rule=",
               v.mode, v.clk_hstx_khz * 1000u, v.fps, max / 100u, max % 100u, avg / 100u, avg % 100u,
               frame_max / 100u, frame_max % 100u, v.late, v.restarts, v.last_restart,
               setup_dimmed() ? "on" : "off", !v.has_hpd ? "n/a" : v.hpd ? "1" : "0");
        print_ruler(t);
        puts("ok");
    } else if (strcmp(arg, "640") == 0 && !ms) {
        video_set_mode(VIDEO_640X480);
        puts("ok");
    } else if (strcmp(arg, "720") == 0 && !ms) {
        video_set_mode(VIDEO_720X480);
        puts("ok");
    } else if (strcmp(arg, "dim") == 0 && !ms) {
        setup_dim_now();
        puts("ok");
    } else if (strcmp(arg, "rule") == 0 && !ms) {
        setup_ruler_toggle();
        puts("ok");
    } else if (strcmp(arg, "stall") == 0 && !ms) {
        video_stall();
        puts("ok");
    } else if (strcmp(arg, "hold") == 0 && ms) {
        hold_command(ms);
    } else {
        puts(USAGE_V);
    }
}

// SetUp's colours by EAB colour code (settings_colour_t); 0 isn't one.
static const char *const colour_names[SETTINGS_WHITE + 1] = {
    [SETTINGS_BLUE] = "blue", [SETTINGS_RED] = "red", [SETTINGS_PINK] = "pink", [SETTINGS_GREEN] = "green",
    [SETTINGS_TURQUOISE] = "turquoise", [SETTINGS_YELLOW] = "yellow", [SETTINGS_WHITE] = "white",
};

// SetUp's Clicker Volume and Alarm volume (#107), by value.
static const char *const volume_names[SETTINGS_VOLUMES] = {"off", "1", "2", "3", "4", "high"};

// SetUp's Typematic Rate and Delay (#107), by settings_rate_t and settings_delay_t.
static const char *const rate_names[SETTINGS_RATES] = {"normal", "fast"};
static const char *const delay_names[SETTINGS_DELAYS] = {"short", "normal", "long"};

// A name of n into *out as its index: false if value is none of them.
static bool named(const char *value, const char *const names[], unsigned n, uint8_t *out) {
    for (unsigned i = 0; i < n; i++)
        if (strcmp(value, names[i]) == 0) {
            *out = (uint8_t)i;
            return true;
        }
    return false;
}

// names[value], or "?" for one SetUp doesn't offer.
static const char *name_of(const char *const names[], unsigned n, uint8_t value) {
    return value < n ? names[value] : "?";
}

// A code's name, or "?" for one SetUp doesn't offer (settings_valid keeps those out).
static const char *colour_name(uint8_t colour) {
    return settings_colour_valid(colour) ? colour_names[colour] : "?";
}

// The field a mapping slot's name sets (#50), or NULL.
static uint8_t *colour_slot(settings_t *s, const char *name) {
    if (strcmp(name, "input") == 0)
        return &s->colour_input;
    if (strcmp(name, "input-hi") == 0)
        return &s->colour_input_hi;
    if (strcmp(name, "protected") == 0)
        return &s->colour_protected;
    if (strcmp(name, "protected-hi") == 0)
        return &s->colour_protected_hi;
    return NULL;
}

// A colour's name into *out as its code: false if it isn't one of SetUp's.
static bool colour_named(const char *text, uint8_t *out) {
    for (uint8_t c = SETTINGS_BLUE; c <= SETTINGS_WHITE; c++)
        if (strcmp(text, colour_names[c]) == 0) {
            *out = c;
            return true;
        }
    return false;
}

// SetUp's Rule line Styles (#51), by settings_ruler_t.
static const char *const ruler_style_names[SETTINGS_RULER_NONE + 1] = {
    [SETTINGS_RULER_HORIZONTAL] = "horizontal",
    [SETTINGS_RULER_VERTICAL] = "vertical",
    [SETTINGS_RULER_CROSS] = "cross",
    [SETTINGS_RULER_NONE] = "none",
};

static void print_settings(const settings_t *s) {
    printf("cursor=%s blink=%s indicator=%s dim=", s->cursor == SETTINGS_CURSOR_BLOCK ? "block" : "underline",
           s->cursor_blink ? "on" : "off", s->indicator ? "on" : "off");
    if (s->auto_dim)
        printf("%u", (unsigned)s->dim_minutes);
    else
        printf("off");
    printf(" input=%s input-hi=%s protected=%s protected-hi=%s mono=%s", colour_name(s->colour_input),
           colour_name(s->colour_input_hi), colour_name(s->colour_protected), colour_name(s->colour_protected_hi),
           s->mono ? "on" : "off");
    printf(" rule=%s rule-colour=%s rule-follows=%s",
           s->ruler_style <= SETTINGS_RULER_NONE ? ruler_style_names[s->ruler_style] : "?",
           colour_name(s->ruler_colour), s->ruler_follows ? "on" : "off");
    printf(" typematic-rate=%s typematic-delay=%s click=%s click-volume=%s alarm-volume=%s mono-case=%s",
           name_of(rate_names, SETTINGS_RATES, s->typematic_rate),
           name_of(delay_names, SETTINGS_DELAYS, s->typematic_delay), s->click ? "on" : "off",
           name_of(volume_names, SETTINGS_VOLUMES, s->click_volume),
           name_of(volume_names, SETTINGS_VOLUMES, s->alarm_volume), s->mono_case ? "on" : "off");
    printf(" model=%u", (unsigned)s->model);
    printf(" lock-sessions=%s", s->lock_sessions ? "on" : "off");
    printf(" password=%s", settings_password_set(s) ? "set" : "none");
    printf(" saved=%s\n", setup_saved() ? "yes" : "no");
}

// on or off into *out: false if text is neither.
static bool on_off(const char *text, bool *out) {
    if (strcmp(text, "on") == 0)
        *out = true;
    else if (strcmp(text, "off") == 0)
        *out = false;
    else
        return false;
    return true;
}

// The settings with name set to value, into next: false if either isn't one
// of SetUp's (the ruler's and page 2's included, #51, #107), of
// monochrome's (#50), or of the model's (#110).
static bool set_one(settings_t *next, const char *name, const char *value) {
    if (strcmp(name, "cursor") == 0) {
        if (strcmp(value, "underline") == 0)
            next->cursor = SETTINGS_CURSOR_UNDERLINE;
        else if (strcmp(value, "block") == 0)
            next->cursor = SETTINGS_CURSOR_BLOCK;
        else
            return false;
        return true;
    }
    if (strcmp(name, "blink") == 0)
        return on_off(value, &next->cursor_blink);
    if (strcmp(name, "indicator") == 0)
        return on_off(value, &next->indicator);
    if (strcmp(name, "dim") == 0) {
        if (strcmp(value, "off") == 0) {
            next->auto_dim = false;  // the delay stays for when it comes back on
            return true;
        }
        char *end = NULL;
        unsigned long minutes = strtoul(value, &end, 10);
        next->auto_dim = true;
        next->dim_minutes = minutes <= 255u ? (uint8_t)minutes : 0u;
        return *value != '\0' && *end == '\0' && settings_valid(next);
    }
    if (strcmp(name, "mono") == 0)
        return on_off(value, &next->mono);
    if (strcmp(name, "rule") == 0) {
        for (unsigned style = SETTINGS_RULER_HORIZONTAL; style <= SETTINGS_RULER_NONE; style++)
            if (strcmp(value, ruler_style_names[style]) == 0) {
                next->ruler_style = (uint8_t)style;
                return true;
            }
        return false;
    }
    if (strcmp(name, "rule-colour") == 0) {
        uint8_t colour;
        if (!colour_named(value, &colour) || (colour != SETTINGS_WHITE && colour != SETTINGS_GREEN))
            return false;
        next->ruler_colour = colour;
        return true;
    }
    if (strcmp(name, "rule-follows") == 0)
        return on_off(value, &next->ruler_follows);
    if (strcmp(name, "typematic-rate") == 0)
        return named(value, rate_names, SETTINGS_RATES, &next->typematic_rate);
    if (strcmp(name, "typematic-delay") == 0)
        return named(value, delay_names, SETTINGS_DELAYS, &next->typematic_delay);
    if (strcmp(name, "click") == 0)
        return on_off(value, &next->click);
    if (strcmp(name, "click-volume") == 0)
        return named(value, volume_names, SETTINGS_VOLUMES, &next->click_volume);
    if (strcmp(name, "alarm-volume") == 0)
        return named(value, volume_names, SETTINGS_VOLUMES, &next->alarm_volume);
    if (strcmp(name, "lock-sessions") == 0)
        return on_off(value, &next->lock_sessions);
    if (strcmp(name, "mono-case") == 0)
        return on_off(value, &next->mono_case);
    if (strcmp(name, "model") == 0) {
        if (strlen(value) != 1u || value[0] < '2' || value[0] > '4')
            return false;
        next->model = (uint8_t)(value[0] - '0');
        return true;
    }
    uint8_t *slot = colour_slot(next, name);
    if (slot)
        return colour_named(value, slot);
    return false;
}

// set save: SetUp's F3=Exit. The result goes on its own line, before ok.
static void save_command(void) {
    uint32_t us = 0;
    switch (setup_save(&us)) {
    case SETUP_SAVE_SAVED:
        printf("saved %" PRIu32 " ms\n", (us + 500u) / 1000u);
        puts("ok");
        break;
    case SETUP_SAVE_UNCHANGED:
        puts("unchanged");
        puts("ok");
        break;
    default:
        puts("err save failed");
        break;
    }
}

static void set_command(const char *name, const char *value) {
    settings_t *s = setup_settings();
    if (!name) {
        print_settings(s);
        puts("ok");
        return;
    }
    if (!value && strcmp(name, "save") == 0) {
        save_command();
        return;
    }
    settings_t next = *s;
    if (!value && strcmp(name, "defaults") == 0) {
        settings_defaults(&next);
    } else if (!value || !set_one(&next, name, value)) {
        puts(USAGE_SET);
        return;
    }
    *s = next;  // a byte a field: a frame begun meanwhile sees each field old or new
    puts("ok");
}

static void print_hex(const uint8_t *data, unsigned len) {
    for (unsigned i = 0; i < len; i++)
        printf("%02x", data[i]);
}

static void usb_counters(void) {
    usb_host_stats_t u;
    usb_host_stats(&u);
    uint32_t per_us = clock_get_hz(clk_sys) / 1000000u;
    uint32_t max = u.frame_cycles_max * 100u / per_us, avg = u.frame_cycles_avg * 100u / per_us;
    printf("frames=%" PRIu32 " frame_us_max=%" PRIu32 ".%02" PRIu32 " frame_us_avg=%" PRIu32 ".%02" PRIu32
           " overruns=%" PRIu32 " devices=%" PRIu32 " hid=%" PRIu32 " reports=%" PRIu32 " rearm_fail=%" PRIu32
           " xfer_fail=%" PRIu32 " hub_fail=%" PRIu32 " log_dropped=%" PRIu32,
           u.frames, max / 100u, max % 100u, avg / 100u, avg % 100u, u.overruns, u.devices, u.hid, u.reports,
           u.rearm_fail, u.xfer_fail, u.hub_fail, u.log_dropped);
    if (u.has_fault_flag)
        printf(" fault=%d fault_trips=%" PRIu32, u.fault, u.fault_trips);
    else
        printf(" fault=n/a fault_trips=n/a");
    printf(" last=");
    if (u.have_last) {
        printf("%u/%u:", (unsigned)u.last.dev, (unsigned)u.last.itf);
        print_hex(u.last.data, u.last.len);
    } else {
        printf("none");
    }
    putchar('\n');
    printf("kbd presses=%" PRIu32 " repeats=%" PRIu32 " drops=%" PRIu32 " local=%" PRIu32 " codes=%" PRIu32
           " lost=%" PRIu32 " rate=%s delay=%s\n",
           u.kbd.presses, u.kbd.repeats, u.kbd.drops, u.kbd.local, u.kbd.codes, u.kbd.lost,
           name_of(rate_names, SETTINGS_RATES, u.typematic_rate),
           name_of(delay_names, SETTINGS_DELAYS, u.typematic_delay));

    usb_host_hid_t h;
    for (unsigned i = 0; i < USB_HOST_HID_MAX; i++)
        if (usb_host_hid(i, &h))
            printf("hid dev=%u itf=%u vid=%04x pid=%04x proto=%s reports=%" PRIu32 " map=%s\n", (unsigned)h.dev,
                   (unsigned)h.itf, (unsigned)h.vid, (unsigned)h.pid, usb_host_proto_name(h.proto), h.reports,
                   h.map ? h.map : "none");
    puts("ok");
}

// The codes a report queued, decimal as the capture CSVs write them, then
// ",+N" for any past the first USB_HOST_SENT_MAX.
static void print_sent(const usb_host_report_t *r) {
    unsigned shown = r->sent_count < USB_HOST_SENT_MAX ? r->sent_count : USB_HOST_SENT_MAX;
    printf(" sent=");
    for (unsigned i = 0; i < shown; i++)
        printf(i ? ",%u" : "%u", (unsigned)r->sent[i]);
    if (r->sent_count > shown)
        printf(",+%u", (unsigned)(r->sent_count - shown));
}

static void usb_log(void) {
    usb_host_report_t r;
    while (usb_host_log_take(&r)) {
        printf("report seq=%" PRIu32 " ms=%" PRIu32 " dev=%u itf=%u data=", r.seq, r.ms, (unsigned)r.dev,
               (unsigned)r.itf);
        print_hex(r.data, r.len);
        print_sent(&r);
        if (r.swallowed)
            printf(" swallowed");  // auto dim took the keys that woke it out
        putchar('\n');
    }
    puts("ok");
}

static void usb_command(const char *arg) {
    if (!arg) {
        usb_counters();
    } else if (strcmp(arg, "clear") == 0) {
        usb_host_clear();
        puts("ok");
    } else if (strcmp(arg, "log") == 0) {
        usb_log();
    } else {
        puts(USAGE_U);
    }
}

// b's MS, 1 to BEEP_MS_MAX, into *out: false if text isn't one.
static bool beep_ms(const char *text, uint32_t *out) {
    char *end = NULL;
    unsigned long ms = strtoul(text, &end, 10);
    if (*text < '0' || *text > '9' || *end != '\0' || ms < 1u || ms > BEEP_MS_MAX)
        return false;
    *out = (uint32_t)ms;
    return true;
}

// b level's DB, BEEP_LEVEL_MIN_DB to BEEP_LEVEL_MAX_DB, into *out.
static bool beep_db(const char *text, int *out) {
    char *end = NULL;
    long db = strtol(text, &end, 10);
    if (*text == '\0' || *end != '\0' || db < BEEP_LEVEL_MIN_DB || db > BEEP_LEVEL_MAX_DB)
        return false;
    *out = (int)db;
    return true;
}

// Two hex digits at text, into *out: false if they aren't. sscanf's %x would
// take a sign or 0x too.
static bool hex_byte(const char *text, unsigned *out) {
    if (!isxdigit((unsigned char)text[0]) || !isxdigit((unsigned char)text[1]))
        return false;
    const char digits[] = {text[0], text[1], '\0'};
    *out = (unsigned)strtoul(digits, NULL, 16);
    return true;
}

// b reg PPRR reads page PP's register RR, b reg PPRR=VV writes VV there
// (hex): a bench aid.
static void beep_reg(const char *text) {
    size_t len = text ? strlen(text) : 0u;
    unsigned page = 0, reg = 0, value = 0;
    if ((len != 4u && len != 7u) || !hex_byte(text, &page) || !hex_byte(text + 2, &reg)
        || (len == 7u && (text[4] != '=' || !hex_byte(text + 5, &value)))) {
        puts(USAGE_B);
    } else if (len == 7u) {
        puts(audio_reg_write((uint8_t)page, (uint8_t)reg, (uint8_t)value) ? "ok" : "err i2c failed");
    } else {
        int got = audio_reg_read((uint8_t)page, (uint8_t)reg);
        if (got < 0) {
            puts("err i2c failed");
            return;
        }
        printf("%02x\n", (unsigned)got);
        puts("ok");
    }
}

static void print_audio(void) {
    audio_stats_t a;
    audio_stats(&a);
    const settings_t *s = setup_settings();
    printf("dac=%s errors=%" PRIu32 " alarms=%" PRIu32 " clicks=%" PRIu32 " flashes=%" PRIu32 " swallowed=%" PRIu32
           " level=",
           a.dac_ok ? "ok" : "missing", a.errors, a.alarms, a.clicks, a.flashes, a.swallowed);
    if (a.level_set)
        printf("%d", a.level_db);
    else
        printf("off");
    const uint8_t volumes[2] = {s->click_volume, s->alarm_volume};
    static const char *const names[2] = {"click", "alarm"};
    for (unsigned i = 0; i < 2u; i++) {
        uint8_t v = volumes[i] < SETTINGS_VOLUMES ? volumes[i] : SETTINGS_VOLUME_OFF;
        printf(" %s_volume=%s %s_db=", names[i], volume_names[v], names[i]);
        if (v == SETTINGS_VOLUME_OFF)
            printf("off");
        else
            printf("%d", beep_volume_db(v));
    }
    printf(" click_ms=%" PRIu32 " alarm_ms=%" PRIu32 " flash_ms=%" PRIu32 " power=", a.click_ms, a.alarm_ms,
           a.flash_ms);
    if (a.power < 0)
        puts("--");
    else
        printf("%02x\n", (unsigned)a.power);
    puts("ok");
}

// value is the word after arg: b click and b alarm take an MS, b level a DB.
static void beep_command(const char *arg, const char *value) {
    if (!arg) {
        print_audio();
        return;
    }
    if (strcmp(arg, "reg") == 0) {
        beep_reg(value);
        return;
    }
    beep_sound_t sound = BEEP_CLICK;
    if (strcmp(arg, "level") == 0) {
        int db = 0;
        if (value && strcmp(value, "off") == 0) {
            audio_level_off();  // then a click at Click Volume's level
        } else if (!value || !beep_db(value, &db)) {
            puts(USAGE_B);
            return;
        } else {
            audio_set_level(db);  // then a click at it
        }
    } else {
        if (strcmp(arg, "alarm") == 0) {
            sound = BEEP_ALARM;
        } else if (strcmp(arg, "flash") == 0) {
            sound = BEEP_FLASH;
        } else if (strcmp(arg, "click") != 0) {
            puts(USAGE_B);
            return;
        }
        uint32_t ms = 0;
        if (value && !beep_ms(value, &ms)) {
            puts(USAGE_B);
            return;
        }
        if (value)
            audio_set_length(sound, ms);
    }
    switch (audio_sound(sound)) {
    case AUDIO_OK:
        puts("ok");
        break;
    case AUDIO_MISSING:
        puts("err dac missing");
        break;
    default:
        puts("err i2c failed");
        break;
    }
}

// Read while core 1 may be writing: a dump taken during a write can tear.
static void dump_command(const term_t *t) {
    static const char hex[] = "0123456789abcdef";
    const uint8_t *regen = term_regen(t);
    char text[DUMP_LINE_BYTES * 2u + 1u];

    printf("ac=%04x control=%02x\n", (unsigned)term_ac(t), (unsigned)term_control(t));
    for (size_t at = 0; at < REGEN_SIZE; at += DUMP_LINE_BYTES) {
        for (size_t i = 0; i < DUMP_LINE_BYTES; i++) {
            text[2u * i] = hex[regen[at + i] >> 4];
            text[2u * i + 1u] = hex[regen[at + i] & 0xFu];
        }
        text[sizeof text - 1u] = '\0';
        puts(text);
    }
    puts("ok");
}

static const char *const lock_names[] = {"off", "black", "prompt"};  // lock_state_t (#122)

static const char *const setup_screen_names[] = {
    "off", "menu", "page1", "page2", "page3", "page4", "offline", "customize", "password", "about",
};
_Static_assert(sizeof setup_screen_names / sizeof setup_screen_names[0] == SETUP_UI_SCREENS,
               "a name for every SetUp screen");

static const struct {
    const char *name;
    uint8_t key;
} setup_key_names[] = {
    {"setup", K_SETUP}, {"up", K_UP},       {"down", K_DOWN},   {"left", K_LEFT}, {"right", K_RIGHT},
    {"space", K_SPACE}, {"enter", K_ENTER}, {"f3", K_PF3},      {"f7", K_PF7},    {"f8", K_PF8},
    {"f10", K_PF10}, {"f11", K_PF11},
};

static void setup_command(const char *arg, const char *arg2) {
    if (!arg) {
        setup_stats_t s;
        setup_stats(&s);
        printf("setup=%s opens=%" PRIu32 " keys=%" PRIu32 " alarms=%" PRIu32 " saves=%" PRIu32
               " save_fails=%" PRIu32 " lock=%s locks=%" PRIu32 " unlocks=%" PRIu32 " wrong=%" PRIu32 "\n",
               setup_screen_names[s.screen], s.opens, s.keys, s.alarms, s.saves, s.save_fails,
               lock_names[s.lock], s.locks, s.unlocks, s.wrong);
        puts("ok");
        return;
    }
    if (strcmp(arg, "key") != 0 || !arg2) {
        puts(USAGE_SETUP);
        return;
    }
    int key = -1;
    for (size_t i = 0; i < sizeof setup_key_names / sizeof setup_key_names[0]; i++)
        if (strcmp(arg2, setup_key_names[i].name) == 0)
            key = setup_key_names[i].key;
    if (key < 0 && isdigit((unsigned char)arg2[0])) {
        char *end = NULL;
        unsigned long code = strtoul(arg2, &end, 10);
        if (*end == '\0' && code <= 0xFFu)
            key = (int)code;
    }
    if (key < 0) {
        puts(USAGE_SETUP);
        return;
    }
    puts(setup_press((uint8_t)key) ? "ok" : "err not open");
}

static void run(term_t *t, char *text) {
    char *command = strtok(text, " \t");
    char *arg = command ? strtok(NULL, " \t") : NULL;
    // v hold's MS, set's VALUE, b's MS or DB, or setup key's NAME; no other takes two
    char *arg2 = arg ? strtok(NULL, " \t") : NULL;
    char *extra = arg2 ? strtok(NULL, " \t") : NULL;

    if (!command)
        puts("ok");  // an empty line: the sync after the banner
    else if (extra || (arg2 && strcmp(command, "v") != 0 && strcmp(command, "set") != 0 && strcmp(command, "b") != 0
                       && strcmp(command, "setup") != 0))
        puts("err too many arguments");
    else if (strcmp(command, "s") == 0 && !arg)
        stats_command(t);
    else if (strcmp(command, "k") == 0)
        key_command(t, arg);
    else if (strcmp(command, "r") == 0)
        reset_command(arg);
    else if (strcmp(command, "d") == 0 && !arg)
        dump_command(t);
    else if (strcmp(command, "v") == 0)
        video_command(t, arg, arg2);
    else if (strcmp(command, "set") == 0)
        set_command(arg, arg2);
    else if (strcmp(command, "u") == 0)
        usb_command(arg);
    else if (strcmp(command, "b") == 0)
        beep_command(arg, arg2);
    else if (strcmp(command, "setup") == 0)
        setup_command(arg, arg2);
    else
        puts("err unknown command");
}

void console_poll(term_t *t) {
    for (;;) {
        int c = getchar_timeout_us(0);
        if (c == PICO_ERROR_TIMEOUT)
            return;
        bool lf_after_cr = c == '\n' && after_cr;
        after_cr = c == '\r';
        if (lf_after_cr)
            continue;
        if (c == '\r' || c == '\n') {
            if (line_too_long) {
                puts("err line too long");
            } else {
                line[line_len] = '\0';
                run(t, line);
            }
            line_len = 0;
            line_too_long = false;
        } else if (line_len < CONSOLE_LINE_MAX - 1u) {
            line[line_len++] = (char)c;
        } else {
            line_too_long = true;
        }
    }
}
