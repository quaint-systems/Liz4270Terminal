// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// The alarm and the key click on the Fruit Jam (#18): the TLV320DAC3100's
// beep generator, set up over I2C with MCLK from the crystal, so no I2S
// stream and no PIO. beep.h decides when to sound. Core 0 only: the I2C
// transfers block the main loop, about 1.6 ms a sound.

#ifndef LIZ_AUDIO_H
#define LIZ_AUDIO_H

#include <stdbool.h>
#include <stdint.h>

#include "beep.h"
#include "term.h"

typedef struct {
    bool dac_ok;         // the DAC answered at power-on and took its setup
    uint32_t errors;     // I2C transfers that failed or timed out
    uint32_t alarms;     // alarms started
    uint32_t clicks;     // clicks started
    uint32_t swallowed;  // sounds not started (beep_swallowed)
    uint32_t flashes;    // flashes started (#107)
    bool level_set;      // b level's override is on,
    int level_db;        // at this level
    uint32_t click_ms, alarm_ms, flash_ms;
    int power;           // page 0 register 37 masked to its documented bits (0xBB), or -1 if unread
} audio_stats_t;

typedef enum {
    AUDIO_OK,
    AUDIO_MISSING,  // the DAC didn't answer at power-on, or didn't take its setup
    AUDIO_FAILED,   // an I2C transfer failed
} audio_result_t;

// At power-on, after the coax link starts and the USB host is up: MCLK, a
// hardware reset of the DAC (PERIPH_RST, which resets the ESP32-C6 too), its
// setup over I2C, then the alarm, as the 3483-V sounds it at power-on
// whatever Alarm volume says (#107). About
// 10 ms.
void audio_init(const term_t *t);

// From main's loop: sounds the alarm and the clicks as beep_poll says. After a
// sound fails it starts none for a second, so a stuck bus can't hold the loop
// up for every keystroke.
void audio_poll(void);

// Whether the DAC answered at power-on and took its setup, for the banner.
bool audio_dac_ok(void);

// The console's b: the counters, and register 37 read back.
void audio_stats(audio_stats_t *out);

// The console's b click, b alarm and b flash: one now, at its volume's level.
// At Alarm volume Off the alarm is the flash, and at Click Volume Off a click
// is silent, as beep_poll has them (#107).
audio_result_t audio_sound(beep_sound_t sound);

// The console's b click MS, b alarm MS and b flash MS: until power-off.
void audio_set_length(beep_sound_t sound, uint32_t ms);

// The console's b level DB: every sound at DB until power-off or b level off,
// whatever level the volumes give, for tuning the ladder (#107). Off still
// wins: at Click Volume Off a click is silent, and at Alarm volume Off the
// alarm is the flash.
void audio_set_level(int db);
void audio_level_off(void);

// The console's b reg: one register of the DAC, on any page, read or
// written; the page goes back to 0 after. A bench aid. -1 or false if a
// transfer failed or the DAC is missing.
int audio_reg_read(uint8_t page, uint8_t reg);
bool audio_reg_write(uint8_t page, uint8_t reg, uint8_t value);

#endif
