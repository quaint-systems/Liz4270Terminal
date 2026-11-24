// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// The alarm and the key click (#18). See beep.h.

#include <math.h>

#include "beep.h"

#define TWO_PI 6.28318531f

// A value from 0 to 1, scaled by 2^15 and rounded, held below 2^15: cos of a
// very low tone would round to 2^15, which doesn't fit.
static uint16_t q15(float x) {
    float scaled = x * 32768.0f + 0.5f;
    return scaled >= 32768.0f ? 32767u : (uint16_t)scaled;
}

bool beep_tone(uint32_t hz, uint32_t fs, beep_tone_t *out) {
    if (hz == 0u || (uint64_t)hz * 4u >= fs)
        return false;  // the generator needs the tone below fs / 4
    float w = TWO_PI * (float)hz / (float)fs;
    out->sin = q15(sinf(w));
    out->cos = q15(cosf(w));
    return true;
}

uint32_t beep_samples(uint32_t ms, uint32_t fs) {
    uint64_t n = (uint64_t)fs * ms / 1000u;
    return n > BEEP_LENGTH_MAX ? BEEP_LENGTH_MAX : (uint32_t)n;
}

uint8_t beep_level_code(int db) {
    if (db > BEEP_LEVEL_MAX_DB)
        db = BEEP_LEVEL_MAX_DB;
    if (db < BEEP_LEVEL_MIN_DB)
        db = BEEP_LEVEL_MIN_DB;
    return (uint8_t)(BEEP_LEVEL_MAX_DB - db);
}

static const int8_t ladder[] = BEEP_VOLUME_DB;
_Static_assert(sizeof ladder == SETTINGS_VOLUMES - 1u, "a level for each volume but Off");

int beep_volume_db(uint8_t volume) {
    if (volume == SETTINGS_VOLUME_OFF || volume >= SETTINGS_VOLUMES)
        return BEEP_LEVEL_MIN_DB;
    return ladder[volume - 1u];
}

uint8_t beep_power_on_volume(const settings_t *s) {
    return s->alarm_volume == SETTINGS_VOLUME_OFF ? (uint8_t)BEEP_POWER_ON_VOLUME : s->alarm_volume;
}

beep_sound_t beep_resolve(beep_sound_t sound, const settings_t *s) {
    if (sound == BEEP_CLICK && s->click_volume == SETTINGS_VOLUME_OFF)
        return BEEP_NONE;
    if (sound == BEEP_ALARM && s->alarm_volume == SETTINGS_VOLUME_OFF)
        return BEEP_FLASH;
    return sound;
}

int beep_sound_db(beep_sound_t sound, const settings_t *s) {
    if (sound == BEEP_CLICK)
        return beep_volume_db(s->click_volume);
    if (sound == BEEP_ALARM)
        return beep_volume_db(s->alarm_volume);
    return BEEP_LEVEL_MIN_DB;
}

size_t beep_sizeof(void) {
    return sizeof(beep_t);
}

void beep_init(beep_t *b, uint32_t alarms, uint32_t keystrokes, uint32_t local) {
    *b = (beep_t){
        .alarms = alarms,
        .keystrokes = keystrokes,
        .local = local,
        .click_ms = BEEP_CLICK_MS,
        .alarm_ms = BEEP_ALARM_MS,
        .flash_ms = BEEP_FLASH_MS,
    };
}

// Whether a count has gone up since it was last seen, across a wrap.
static bool rose(uint32_t now, uint32_t before) {
    return (int32_t)(now - before) > 0;
}

static bool alarm_sounding(const beep_t *b, uint32_t ms) {
    return b->alarm_on && (int32_t)(ms - b->alarm_end) < 0;
}

static bool flash_showing(const beep_t *b, uint32_t ms) {
    return b->flash_on && (int32_t)(ms - b->flash_end) < 0;
}

beep_sound_t beep_poll(beep_t *b, uint32_t ms, uint32_t alarms, uint32_t keystrokes, uint32_t local, bool clicker,
                       const settings_t *s) {
    // An alarm or flash that has ended is over for good: kept on, its end
    // would come round again as the future after 2^31 ms (24.9 days) of quiet.
    if (b->alarm_on && !alarm_sounding(b, ms))
        b->alarm_on = false;
    if (b->flash_on && !flash_showing(b, ms))
        b->flash_on = false;
    bool alarm = rose(alarms, b->alarms);
    // SetUp's keys click whatever Click and the POLL bits say; the host's
    // need both (captured Oct 12, #107).
    bool host_key = rose(keystrokes - local, b->keystrokes - b->local);
    bool local_key = rose(local, b->local);
    bool click = (local_key || (host_key && clicker && s->click)) && beep_resolve(BEEP_CLICK, s) == BEEP_CLICK;
    b->alarms = alarms;
    b->keystrokes = keystrokes;
    b->local = local;
    if (alarm) {
        if (click)
            b->swallowed++;  // the alarm, or its flash, wins
        if (alarm_sounding(b, ms) || flash_showing(b, ms)) {
            b->swallowed++;
            return BEEP_NONE;
        }
        beep_sound_t sound = beep_resolve(BEEP_ALARM, s);
        beep_start(b, ms, sound);
        return sound;
    }
    if (!click)
        return BEEP_NONE;
    if (alarm_sounding(b, ms)) {
        b->swallowed++;
        return BEEP_NONE;
    }
    beep_start(b, ms, BEEP_CLICK);
    return BEEP_CLICK;
}

void beep_start(beep_t *b, uint32_t ms, beep_sound_t sound) {
    if (sound == BEEP_FLASH) {
        b->flash_on = true;
        b->flash_end = ms + b->flash_ms;
    } else if (sound != BEEP_NONE) {
        b->alarm_on = sound == BEEP_ALARM;
        b->alarm_end = ms + b->alarm_ms;
    }
}

void beep_preview(beep_t *b) {
    b->alarm_on = false;
    b->flash_on = false;
}

void beep_cancel(beep_t *b) {
    b->alarm_on = false;
}

uint32_t beep_length(const beep_t *b, beep_sound_t sound) {
    switch (sound) {
    case BEEP_ALARM:
        return b->alarm_ms;
    case BEEP_CLICK:
        return b->click_ms;
    case BEEP_FLASH:
        return b->flash_ms;
    default:
        return 0u;
    }
}

void beep_set_length(beep_t *b, beep_sound_t sound, uint32_t ms) {
    if (sound == BEEP_ALARM)
        b->alarm_ms = ms;
    else if (sound == BEEP_CLICK)
        b->click_ms = ms;
    else if (sound == BEEP_FLASH)
        b->flash_ms = ms;
}

uint32_t beep_swallowed(const beep_t *b) {
    return b->swallowed;
}
