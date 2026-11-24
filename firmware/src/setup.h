// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// The terminal's local state on the Fruit Jam (#49): its settings
// (settings.h), which the console and SetUp (#102) set, kept in
// flash (#69), auto dim (dim.h), and the Rule key's ruler (ruler.h, #51).
// Core 0 only.

#ifndef LIZ_SETUP_H
#define LIZ_SETUP_H

#include <stdbool.h>
#include <stdint.h>

#include "settings.h"
#include "lock.h"
#include "setup_ui.h"
#include "term.h"

// At power-on: the newest valid record in flash (#69), or the defaults with
// none, and auto dim off with its timer from now. Its timer runs from
// power-on: the splash shows until the controller first writes, and that
// write is activity.
void setup_init(const term_t *t);

// The model flash's record holds, or Model 2 with none: main powers the
// core on as it (#110), before setup_init.
uint8_t setup_saved_model(void);

// The record: the renderer reads it as each frame begins, and the console writes it.
settings_t *setup_settings(void);

typedef enum {
    SETUP_SAVE_SAVED,      // written, and read back the same
    SETUP_SAVE_UNCHANGED,  // flash already holds the live record: nothing written
    SETUP_SAVE_FAILED,     // the image reaches the slot, or the read-back differed
} setup_save_t;

// Writes the live record to flash, as SetUp's F3=Exit does on the 3483-V
// (#69): the console's set save now, SetUp (#102) later. From core 0's main
// loop only, which waits for the erase. *us gets the time a write took.
setup_save_t setup_save(uint32_t *us);

// Whether flash holds exactly the live record.
bool setup_saved(void);

// From main's loop: ticks auto dim with the time and term_writes, and turns
// the ruler on or off for each bare Rule press (#51).
void setup_poll(void);

// Whether auto dim is on: the renderer reads it as each frame begins.
bool setup_dimmed(void);

// A keyboard's boot report, before the translator (dim_report): writes the
// report the translator gets into out, and returns true if auto dim took the
// keys that woke it out of it.
bool setup_report(unsigned src, uint32_t ms, const uint8_t report[8], uint8_t out[8]);

// A HID interface mounted or unplugged (dim_forget): its keys, masked or not, are forgotten.
void setup_forget(unsigned src);

// The console's k: activity, never swallowed, so the rig's keys still reach the controller.
void setup_key(void);

// The console's v dim: auto dim on now.
void setup_dim_now(void);

// The Rule key's ruler (ruler.h, #51): RULER_OFF, or the address counter when
// it came on. The renderer reads it as each frame begins, and the console's v.
uint16_t setup_ruler(void);

// The console's v rule: the ruler on or off, as a Rule press turns it, at the
// address counter now.
void setup_ruler_toggle(void);

// SetUp (#102), driven from setup_poll: the keyboard's K_SETUP (or the
// console's setup key setup) opens it, the keys the keyboard's local mode
// holds walk it, and F3 from its menu closes it and saves the settings, as
// set save does. A key that reached the ring after the F3 that closes it,
// in the same report, is dropped.
//
// Whether SetUp's image is up: video draws it in place of the host's as
// each frame begins, setup_regen's codes and setup_eab's bytes.
bool setup_showing(void);
const uint8_t *setup_regen(void);
const uint8_t *setup_eab(void);

// The front image's cursor cell (#122): Password Set's, or 0 for none.
uint16_t setup_cursor(void);

// The lock (#122): whether it's up, and its status line, which the renderer
// copies as each frame begins.
bool setup_locked(void);
const lock_line_t *setup_lock_line(void);

// The alarms SetUp has sounded, for keys it can't use, for failed saves and
// for Alarm volume's previews (#107): the beep rules count them with
// term_alarms (audio.c).
uint32_t setup_alarms(void);

// Alarm volume's previews among them (#107): audio.c lets each cut the alarm
// or flash before it, so every Space is heard.
uint32_t setup_previews(void);

// The power-on resets a model change has made (#110): audio.c sounds the
// power-on alarm for each, as the 3483-V does leaving offline setup.
uint32_t setup_power_ons(void);

typedef struct {
    setup_ui_screen_t screen;
    uint32_t opens, keys, alarms;  // setup_ui's: alarms for keys only
    uint32_t saves;                // SetUp's writes to flash: closes, and Password Set's (#122)
    uint32_t save_fails;           // those that failed, closes and Password Set's: each sounds the alarm
    lock_state_t lock;             // Lock sessions (#122)
    uint32_t locks, unlocks, wrong;
} setup_stats_t;

void setup_stats(setup_stats_t *out);

// The console's setup key: one key into SetUp, as the keyboard hands it, and
// activity for auto dim. K_SETUP opens it, turning the keyboard's local mode
// on; any other key while SetUp is off and the terminal isn't locked returns
// false. Locked, the key goes to the lock (#122).
bool setup_press(uint8_t key);

#endif
