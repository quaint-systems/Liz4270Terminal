// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// The terminal's local settings (#49). See settings.h.

#include <string.h>

#include "settings.h"

const uint8_t settings_dim_minutes[SETTINGS_DIM_CHOICES] = {5u, 10u, 20u};

void settings_defaults(settings_t *s) {
    *s = (settings_t){
        .cursor = SETTINGS_CURSOR_UNDERLINE,
        .cursor_blink = false,
        .indicator = true,
        .auto_dim = true,
        .dim_minutes = 10u,
        .colour_input = SETTINGS_GREEN,
        .colour_input_hi = SETTINGS_RED,
        .colour_protected = SETTINGS_BLUE,
        .colour_protected_hi = SETTINGS_WHITE,
        .mono = false,
        .ruler_style = SETTINGS_RULER_HORIZONTAL,
        .ruler_colour = SETTINGS_WHITE,
        .ruler_follows = true,
        .typematic_rate = SETTINGS_RATE_NORMAL,
        .typematic_delay = SETTINGS_DELAY_NORMAL,
        .click = true,
        .click_volume = 3u,
        .alarm_volume = 3u,
        .mono_case = false,
        .model = SETTINGS_MODEL_2,
        .lock_sessions = false,
        .password = SETTINGS_NO_PASSWORD,
    };
}

bool settings_colour_valid(uint8_t colour) {
    return colour >= SETTINGS_BLUE && colour <= SETTINGS_WHITE;
}

bool settings_valid(const settings_t *s) {
    if (s->cursor > SETTINGS_CURSOR_BLOCK)
        return false;
    if (!settings_colour_valid(s->colour_input) || !settings_colour_valid(s->colour_input_hi)
        || !settings_colour_valid(s->colour_protected) || !settings_colour_valid(s->colour_protected_hi))
        return false;
    if (s->ruler_style > SETTINGS_RULER_NONE)
        return false;
    if (s->ruler_colour != SETTINGS_WHITE && s->ruler_colour != SETTINGS_GREEN)
        return false;
    if (s->typematic_rate >= SETTINGS_RATES || s->typematic_delay >= SETTINGS_DELAYS)
        return false;
    if (s->click_volume >= SETTINGS_VOLUMES || s->alarm_volume >= SETTINGS_VOLUMES)
        return false;
    if (s->model < SETTINGS_MODEL_2 || s->model > SETTINGS_MODEL_4)
        return false;
    for (unsigned i = 0; i < SETTINGS_DIM_CHOICES; i++)
        if (s->dim_minutes == settings_dim_minutes[i])
            return true;
    return false;
}

#define HEAD_BYTES 10u  // magic, version, length and sequence
#define CRC_BYTES 4u
#define FIELDS 29u      // settings_t's fields as bytes: version 1's payload, 5 of them before #50, 10 before #51, 13
                        // before #107, 19 before #110, 20 before #122 (the password's hash is eight)

static const uint8_t magic[4] = {'L', 'I', 'Z', 'S'};

// settings_t's fields as the payload's bytes, a bool as 0 or 1.
static void to_bytes(const settings_t *s, uint8_t f[FIELDS]) {
    f[0] = s->cursor;
    f[1] = s->cursor_blink ? 1u : 0u;
    f[2] = s->indicator ? 1u : 0u;
    f[3] = s->auto_dim ? 1u : 0u;
    f[4] = s->dim_minutes;
    f[5] = s->colour_input;
    f[6] = s->colour_input_hi;
    f[7] = s->colour_protected;
    f[8] = s->colour_protected_hi;
    f[9] = s->mono ? 1u : 0u;
    f[10] = s->ruler_style;
    f[11] = s->ruler_colour;
    f[12] = s->ruler_follows ? 1u : 0u;
    f[13] = s->typematic_rate;
    f[14] = s->typematic_delay;
    f[15] = s->click ? 1u : 0u;
    f[16] = s->click_volume;
    f[17] = s->alarm_volume;
    f[18] = s->mono_case ? 1u : 0u;
    f[19] = s->model;
    f[20] = s->lock_sessions ? 1u : 0u;
    for (unsigned i = 0; i < 8u; i++)
        f[21 + i] = (uint8_t)(s->password >> (8u * i));
}

static void put32(uint8_t *p, uint32_t v) {
    for (unsigned i = 0; i < 4u; i++)
        p[i] = (uint8_t)(v >> (8u * i));
}

static uint32_t get32(const uint8_t *p) {
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

static uint64_t get64(const uint8_t *p) {
    uint64_t v = 0;
    for (unsigned i = 8u; i-- > 0;)
        v = v << 8 | p[i];
    return v;
}

uint32_t settings_crc32(const uint8_t *data, size_t len) {
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (unsigned bit = 0; bit < 8u; bit++)
            crc = (crc & 1u) ? (crc >> 1) ^ 0xEDB88320u : crc >> 1;
    }
    return ~crc;
}

size_t settings_pack(const settings_t *s, uint32_t seq, uint8_t page[SETTINGS_PAGE]) {
    memset(page, 0xFF, SETTINGS_PAGE);
    memcpy(page, magic, sizeof magic);
    page[4] = SETTINGS_VERSION;
    page[5] = FIELDS;
    put32(page + 6, seq);
    to_bytes(s, page + HEAD_BYTES);
    size_t crc_at = HEAD_BYTES + FIELDS;
    put32(page + crc_at, settings_crc32(page, crc_at));
    return crc_at + CRC_BYTES;
}

bool settings_unpack(settings_t *s, uint32_t *seq, const uint8_t page[SETTINGS_PAGE]) {
    size_t length = page[5];
    size_t crc_at = HEAD_BYTES + length;
    if (memcmp(page, magic, sizeof magic) != 0 || page[4] != SETTINGS_VERSION || crc_at + CRC_BYTES > SETTINGS_PAGE
        || get32(page + crc_at) != settings_crc32(page, crc_at))
        return false;
    // The defaults, then as many fields as the record has.
    settings_t defaults;
    uint8_t f[FIELDS];
    settings_defaults(&defaults);
    to_bytes(&defaults, f);
    memcpy(f, page + HEAD_BYTES, length < FIELDS ? length : FIELDS);
    if (f[1] > 1u || f[2] > 1u || f[3] > 1u || f[9] > 1u || f[12] > 1u || f[15] > 1u || f[18] > 1u
        || f[20] > 1u)
        return false;  // a C bool would read 2 as 1, so check the byte
    settings_t next = {
        .cursor = f[0],
        .cursor_blink = f[1],
        .indicator = f[2],
        .auto_dim = f[3],
        .dim_minutes = f[4],
        .colour_input = f[5],
        .colour_input_hi = f[6],
        .colour_protected = f[7],
        .colour_protected_hi = f[8],
        .mono = f[9],
        .ruler_style = f[10],
        .ruler_colour = f[11],
        .ruler_follows = f[12],
        .typematic_rate = f[13],
        .typematic_delay = f[14],
        .click = f[15],
        .click_volume = f[16],
        .alarm_volume = f[17],
        .mono_case = f[18],
        .model = f[19],
        .lock_sessions = f[20],
        .password = get64(f + 21),
    };
    if (!settings_valid(&next))
        return false;
    *s = next;
    *seq = get32(page + 6);
    return true;
}

int settings_load(settings_t *s, uint32_t *seq, const uint8_t *const slots[], unsigned n) {
    int chosen = -1;
    settings_defaults(s);
    *seq = 0u;
    for (unsigned i = 0; i < n; i++) {
        settings_t found;
        uint32_t found_seq;
        if (settings_unpack(&found, &found_seq, slots[i]) && (chosen < 0 || found_seq > *seq)) {
            *s = found;
            *seq = found_seq;
            chosen = (int)i;
        }
    }
    return chosen;
}

bool settings_equal(const settings_t *a, const settings_t *b) {
    uint8_t fa[FIELDS], fb[FIELDS];
    to_bytes(a, fa);
    to_bytes(b, fb);
    return memcmp(fa, fb, FIELDS) == 0;
}

bool settings_password_set(const settings_t *s) {
    return s->password != SETTINGS_NO_PASSWORD;
}
