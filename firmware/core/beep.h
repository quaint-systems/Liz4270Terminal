// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// The alarm and the key click (#18): one tone, the 3483-V's, which the Fruit
// Jam's DAC sounds short for a click and long for the alarm (audio.c). This
// is the arithmetic for the DAC's beep generator (TI SLAS671C, 6.3.10.7) and
// the rules for when to sound: the alarm on each new alarm POLL
// (term_alarms), or the flash at Alarm volume Off, and a click on each of
// SetUp's keystrokes and on the host's while Click is Yes and the POLL bits
// have the clicker on (term_clicker), at a Click Volume other than Off
// (#107). An alarm is never cut short by a click, and alarms never stack.
//
// Plain C11, like the rest of the core: the caller passes the time in
// milliseconds, which may wrap.

#ifndef LIZ_BEEP_H
#define LIZ_BEEP_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "settings.h"

#define BEEP_HZ 3493u              // the 3483-V's tone: 3492.7 Hz by a phone tuner (Oct 7)
#define BEEP_FS 31250u             // the DAC's sample rate: 12 MHz / (NDAC 1 x MDAC 3 x DOSR 128)
#define BEEP_CLICK_MS 10u          // the lengths and level, as the bench matched them to the 3483-V's
#define BEEP_ALARM_MS 500u
#define BEEP_FLASH_MS 200u         // Alarm volume Off's flash (#107): every cell's reverse flipped this long
// The volume ladder (#107): register 71's beep level, in dB, for Clicker
// Volume and Alarm volume 1, 2, 3, 4 and High, 10 dB apart. 3 is the level
// the bench matched to this 3483-V's 3 by ear (#18); High is the loudest a
// full-scale sine gets without clipping (register 71's +2 dB is left alone).
// Off sounds nothing. Tune them here once the case and its speaker are settled.
#define BEEP_VOLUME_DB {-40, -30, -20, -10, 0}
#define BEEP_POWER_ON_VOLUME 3u    // the power-on alarm's volume when Alarm volume is Off
#define BEEP_LEVEL_MAX_DB 2        // register 71's range, in 1 dB steps
#define BEEP_LEVEL_MIN_DB (-61)
#define BEEP_LENGTH_MAX 0xFFFFFFu  // samples: registers 73-75 hold 24 bits

// Registers 76-79. Both are below 2^15: the tone is below fs / 4.
typedef struct {
    uint16_t sin, cos;
} beep_tone_t;

typedef enum {
    BEEP_NONE = 0,
    BEEP_CLICK = 1,
    BEEP_ALARM = 2,
    BEEP_FLASH = 3,  // Alarm volume Off's flash in the alarm's place (#107)
} beep_sound_t;

// Defined here so the caller can allocate it. The fields are private to beep.c.
typedef struct {
    uint32_t alarms;      // term_alarms when last polled
    uint32_t keystrokes;  // kbd_keystrokes likewise
    uint32_t local;       // kbd_local_keystrokes likewise (#107)
    uint32_t click_ms, alarm_ms, flash_ms;
    bool alarm_on;        // the last sound started was an alarm,
    uint32_t alarm_end;   // and it ends here
    bool flash_on;        // a flash was started (#107),
    uint32_t flash_end;   // and it ends here
    uint32_t swallowed;
} beep_t;

// sin and cos of 2 pi hz / fs, scaled by 2^15 and rounded, for registers
// 76-79. false, with *out untouched, for 0 Hz, or for hz of fs / 4 or more,
// which the generator can't make.
bool beep_tone(uint32_t hz, uint32_t fs, beep_tone_t *out);

// floor(fs * ms / 1000) samples, for registers 73-75: at most BEEP_LENGTH_MAX.
uint32_t beep_samples(uint32_t ms, uint32_t fs);

// Register 71's bits 5-0 for a level in dB: 0 is +2 dB and 63 is -61 dB.
// A level outside that range is held to its end.
uint8_t beep_level_code(int db);

size_t beep_sizeof(void);  // for ctypes, which can't see sizeof

// The ladder's level in dB for volume 1 to SETTINGS_VOLUME_HIGH;
// BEEP_LEVEL_MIN_DB for Off, or a volume past High, which nothing sounds.
int beep_volume_db(uint8_t volume);

// The power-on alarm's volume: Alarm volume's, or BEEP_POWER_ON_VOLUME's at
// Off, since the 3483-V's power-on beeps sound whatever it says (#107).
uint8_t beep_power_on_volume(const settings_t *s);

// What a sound comes to at the live settings, for beep_poll and the
// console's b alike (#107): a click is BEEP_NONE at Click Volume Off, the
// alarm BEEP_FLASH at Alarm volume Off; anything else as it is.
beep_sound_t beep_resolve(beep_sound_t sound, const settings_t *s);

// A click's level in dB, at Click Volume's, or the alarm's, at Alarm
// volume's (beep_volume_db); BEEP_LEVEL_MIN_DB for anything else.
int beep_sound_db(beep_sound_t sound, const settings_t *s);

// Nothing sounding, the counts last seen as given, and the default lengths.
void beep_init(beep_t *b, uint32_t alarms, uint32_t keystrokes, uint32_t local);

// Often, from the loop: what to sound now. keystrokes is every keystroke,
// local SetUp's among them (kbd_local_keystrokes); clicker is the POLL bits'
// (term_clicker); s is the live settings.
// - An alarm (alarms gone up): BEEP_ALARM, or BEEP_FLASH at Alarm volume
//   Off; swallowed while an alarm sounds or a flash shows.
// - A click: a SetUp keystroke, or a host one while clicker is set and Click
//   is Yes, at a Click Volume other than Off: BEEP_CLICK, unless an alarm is
//   sounding. A click may cut a click, and a flash doesn't hold one off.
// - Both in one poll: the alarm or the flash, and the click is swallowed.
// It takes the new counts either way, so keystrokes it doesn't click for
// leave nothing to click later, and a count that goes back sounds nothing (a
// core reset, term_init, takes term_alarms back to 0). A sound it doesn't
// start counts as swallowed.
beep_sound_t beep_poll(beep_t *b, uint32_t ms, uint32_t alarms, uint32_t keystrokes, uint32_t local, bool clicker,
                       const settings_t *s);

// A sound started at ms from elsewhere (the console's b), so beep_poll's
// rules see it: whatever started last is what's sounding.
void beep_start(beep_t *b, uint32_t ms, beep_sound_t sound);

// SetUp's Alarm volume preview (#107): whatever alarm sounds or flash shows
// is over, so the preview's alarm, in the next beep_poll, starts rather than
// being swallowed: each Space on a level is heard, however quick the next.
void beep_preview(beep_t *b);

// The sound just started didn't, because the DAC failed: nothing is sounding,
// so the next alarm or click isn't swallowed for it.
void beep_cancel(beep_t *b);

// A sound's length in ms (BEEP_NONE's is 0, BEEP_FLASH's the flash's), and
// setting it until beep_init.
uint32_t beep_length(const beep_t *b, beep_sound_t sound);
void beep_set_length(beep_t *b, beep_sound_t sound, uint32_t ms);

uint32_t beep_swallowed(const beep_t *b);

#endif
