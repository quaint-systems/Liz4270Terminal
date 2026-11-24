// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// The terminal's local settings (#49): what the 3483-V's SetUp sets on its
// Display Setup pages, with its choices, and this 3483-V's values as the
// defaults (captures/photos-20261006/setup-1-display-cursor-autodim.jpg,
// setup-3-display-colour-mapping.jpg), and monochrome, which it lacks (#50),
// and the Rule key's ruler (#51), and Display Setup's second page (#107),
// and offline setup's Screen rows x columns (#110).
//
// Plain C11, like the rest of the core, so tools/sim reads the same record
// through ctypes. The renderer and auto dim read it; the console sets it now,
// and SetUp (#102) will. The Fruit Jam keeps it in flash as a record (#69,
// below). Each field is a byte, so a reader on the same core never sees one
// torn, but the password's hash, which only core 0's main loop reads (#122).
// The other Display Setup fields (docs/upstream-review.md) join it with the
// issues that use them.

#ifndef LIZ_SETTINGS_H
#define LIZ_SETTINGS_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef enum {
    SETTINGS_CURSOR_UNDERLINE,
    SETTINGS_CURSOR_BLOCK,
} settings_cursor_t;

// The colours SetUp's Four base color mapping offers, as oec's EAB colour
// codes (docs/upstream-review.md), so the renderer looks them up directly.
typedef enum {
    SETTINGS_BLUE = 1,
    SETTINGS_RED,
    SETTINGS_PINK,
    SETTINGS_GREEN,
    SETTINGS_TURQUOISE,
    SETTINGS_YELLOW,
    SETTINGS_WHITE,
} settings_colour_t;

// SetUp's Rule line Style (#51), in its order.
typedef enum {
    SETTINGS_RULER_HORIZONTAL,
    SETTINGS_RULER_VERTICAL,
    SETTINGS_RULER_CROSS,
    SETTINGS_RULER_NONE,
} settings_ruler_t;

// SetUp's Typematic Rate and Delay (#107), in its order.
typedef enum {
    SETTINGS_RATE_NORMAL,
    SETTINGS_RATE_FAST,
} settings_rate_t;
#define SETTINGS_RATES 2u

typedef enum {
    SETTINGS_DELAY_SHORT,
    SETTINGS_DELAY_NORMAL,
    SETTINGS_DELAY_LONG,
} settings_delay_t;
#define SETTINGS_DELAYS 3u

// SetUp's Clicker Volume and Alarm volume (#107): Off, 1-4, then High.
#define SETTINGS_VOLUME_OFF 0u
#define SETTINGS_VOLUME_HIGH 5u
#define SETTINGS_VOLUMES 6u

// Customization's Screen rows x columns (#110): the model the terminal
// answers as and draws, by its number.
#define SETTINGS_MODEL_2 2u  // 24 x 80
#define SETTINGS_MODEL_3 3u  // 32 x 80
#define SETTINGS_MODEL_4 4u  // 43 x 80

// Password Set's password (#122): its hash (lock.h), or this for none.
#define SETTINGS_NO_PASSWORD 0u

#define SETTINGS_DIM_CHOICES 3u

typedef struct {
    uint8_t cursor;       // Cursor Style: a settings_cursor_t
    bool cursor_blink;    // Cursor Blink
    bool indicator;       // Row/column indicator: RRRR/CCC at the right of the status line
    bool auto_dim;        // Auto dim
    uint8_t dim_minutes;  // Auto dim's Delay (minutes): one of settings_dim_minutes
    // Four base color mapping (#50): what each base colour is drawn as,
    // wherever it comes from, a field attribute or an EAB byte (captured
    // Oct 10). Each a settings_colour_t.
    uint8_t colour_input;         // Input: what green becomes
    uint8_t colour_input_hi;      // Intensified input: what red becomes
    uint8_t colour_protected;     // Protected: what blue becomes
    uint8_t colour_protected_hi;  // Intensified protected: what white becomes
    bool mono;                    // monochrome (#50): everything in one green phosphor
    // The Rule key's ruler (#51): SetUp's Rule line.
    uint8_t ruler_style;   // Style: a settings_ruler_t
    uint8_t ruler_colour;  // Color: SETTINGS_WHITE or SETTINGS_GREEN
    bool ruler_follows;    // Follows cursor
    // Display Setup's second page (#107).
    uint8_t typematic_rate;   // Typematic Rate: a settings_rate_t
    uint8_t typematic_delay;  // Typematic Delay: a settings_delay_t
    bool click;               // Clicker Click: Yes lets the controller's clicker click the host's keys
    uint8_t click_volume;     // Clicker Volume: SETTINGS_VOLUME_OFF to SETTINGS_VOLUME_HIGH
    uint8_t alarm_volume;     // Alarm volume: the same
    bool mono_case;           // Mono case: the host's lower case drawn as capitals
    // Offline setup's Customization (#110).
    uint8_t model;            // Screen rows x columns: SETTINGS_MODEL_2, _3 or _4
    // Display Setup page 1's Lock sessions, and Password Set's password (#122).
    bool lock_sessions;       // Lock sessions: auto dim locks the terminal instead of blanking it
    uint64_t password;        // the password's hash (lock.h), SETTINGS_NO_PASSWORD for none
} settings_t;

// SetUp's choices of Delay, in minutes.
extern const uint8_t settings_dim_minutes[SETTINGS_DIM_CHOICES];

// This 3483-V's SetUp on Oct 6: Underline, Blink No, the indicator On, Auto
// dim Yes after 10 minutes, each base colour as itself, and the Rule line
// Horizontal, White and following the cursor; monochrome off; page 2's
// Typematic Normal and Normal, Click Yes, both volumes 3 and Mono case No;
// and 24 x 80 (#110).
void settings_defaults(settings_t *s);

// Whether colour is one of the seven SetUp's colour mapping offers.
bool settings_colour_valid(uint8_t colour);

// Whether the fields that can hold a value SetUp doesn't offer (the cursor's
// style, the delay, the four colours, the ruler's style and colour, the
// typematic rate and delay, the two volumes, and the model) hold one of its
// choices.
bool settings_valid(const settings_t *s);

// Whether a password is set (#122).
bool settings_password_set(const settings_t *s);

// The record the Fruit Jam keeps in flash (#69): one 256-byte page, written
// byte by byte, never as a copy of the struct.
//
//   0-3      magic "LIZS"
//   4        layout version: SETTINGS_VERSION
//   5        payload length, N
//   6-9      sequence number, little-endian: one more than the record it replaces
//   10..     payload: a byte a field, in settings_t's order, the password's hash as eight, little-endian;
//            new fields are appended
//   10+N..   CRC-32 of bytes 0 to 9+N, little-endian (as zlib.crc32)
//
// The rest of the page is 0xFF. A shorter payload, from an older build, leaves
// the fields after it at their defaults; a longer one, from a newer build, has
// fields this build ignores. SETTINGS_VERSION changes only for a layout an
// older build can't read.
#define SETTINGS_PAGE 256u
#define SETTINGS_VERSION 1u

// The record for s with sequence seq, into page, the rest 0xFF. Returns the
// record's length.
size_t settings_pack(const settings_t *s, uint32_t seq, uint8_t page[SETTINGS_PAGE]);

// The settings and sequence from the record at the start of page: false, with
// *s and *seq untouched, for a wrong magic or version, a length that runs past
// the page, a CRC that doesn't match, a bool that isn't 0 or 1, or a value
// SetUp doesn't offer.
bool settings_unpack(settings_t *s, uint32_t *seq, const uint8_t page[SETTINGS_PAGE]);

// The valid record with the highest sequence among n slots, the first on a
// tie: its index, with *s and *seq. With none, -1, the defaults and 0.
int settings_load(settings_t *s, uint32_t *seq, const uint8_t *const slots[], unsigned n);

// Whether a and b hold the same settings.
bool settings_equal(const settings_t *a, const settings_t *b);

// CRC-32 (IEEE 802.3, reflected, as zlib.crc32).
uint32_t settings_crc32(const uint8_t *data, size_t len);

#endif
