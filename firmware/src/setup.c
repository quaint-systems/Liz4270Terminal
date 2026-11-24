// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// The terminal's local state on the Fruit Jam (#49, #69), and SetUp (#102).
// See setup.h.

#include <assert.h>
#include <stdatomic.h>

#include "pico/stdlib.h"

#include "board_detect.h"
#include "coax_link.h"
#include "dim.h"
#include "flash_store.h"
#include "keyboard.h"
#include "keys3483.h"
#include "lock.h"
#include "model_change.h"
#include "ruler.h"
#include "setup.h"
#include "setup_ui.h"
#include "usb_host.h"
#include "version.h"
#include "video.h"

// A model change's requests to core 1 (#110), which takes each between
// frames, under 2 ms. One that times out still lands (model_change.h).
#define LINK_TIMEOUT_MS 100u

static_assert(DIM_SOURCES == KBD_SOURCES, "auto dim swallows by the translator's source");
static_assert(SETTINGS_PAGE == FLASH_STORE_PAGE, "a record is one flash page");
static_assert(LOCK_LINE_COLS == RENDER_COLS, "the lock's status line is the renderer's");

static settings_t settings;          // the live record: the renderer reads it, the console writes it
static settings_t saved;             // the newest valid record in flash, or the defaults with none
static uint32_t saved_seq;           // its sequence: 0 with none
static int saved_slot;               // its slot: -1 with none
static uint8_t page[SETTINGS_PAGE];  // in RAM: flash can't be programmed from flash
static dim_t dim;
static const term_t *term;
static ruler_t ruler;  // the Rule key's (#51): main's loop changes it, the renderer's IRQ reads at
static setup_ui_t ui;           // SetUp (#102): main's loop changes it, the renderer's IRQ reads its front image
static volatile bool showing;   // SetUp's image is the one to draw: set once its first draw is in
static bool leaving;            // out of offline setup, its image up until the link's power-on reset lands (#110)
static bool redraw;             // opened, or a key, since the last draw
static settings_t drawn;        // the settings the front image shows
static uint32_t drawn_at;       // video_frames_begun at the last draw
static uint32_t saves, save_fails, previews;
static model_change_t change;   // the model the controller sees, as the live record says (#110)
static lock_t lock;                  // Lock sessions (#122): main's loop changes it
static lock_line_t lock_lines[2];    // its status line, double-buffered: the renderer's IRQ copies the front as a
static volatile uint8_t lock_front;  // frame begins
static volatile bool locked;         // the lock is the one to draw: set once its first line is in
static uint32_t lock_alarms;         // the alarms it sounded: wrong passwords and keys the prompt can't use

static void draw_lock(void);

static uint32_t now_ms(void) {
    return to_ms_since_boot(get_absolute_time());
}

// What flash holds now, into saved, saved_seq and saved_slot.
static void read_saved(void) {
    const uint8_t *slots[FLASH_STORE_SLOTS];
    for (unsigned i = 0; i < FLASH_STORE_SLOTS; i++)
        slots[i] = flash_store_slot(i);
    saved_slot = settings_load(&saved, &saved_seq, slots, FLASH_STORE_SLOTS);
}

void setup_init(const term_t *t) {
    term = t;
    read_saved();
    settings = saved;
    dim_init(&dim, now_ms(), term_writes(t));
    ruler_init(&ruler, usb_host_rule_presses());
    setup_ui_init(&ui);
    // About's page 1 (#126): the board as the banner names it. board_detect() ran first (main.c).
    char name[SETUP_UI_BOARD_MAX];
    board_describe(name, sizeof name, "");
    setup_ui_identify(&ui, liz_version, liz_commit, name);
    model_change_init(&change);
    lock_clear(&lock);
    draw_lock();
    usb_host_typematic(settings.typematic_rate, settings.typematic_delay);  // the saved ones (#107)
}

uint8_t setup_saved_model(void) {
    read_saved();
    return saved.model;
}

settings_t *setup_settings(void) {
    return &settings;
}

bool setup_saved(void) {
    return saved_slot >= 0 && settings_equal(&settings, &saved);
}

// One write of next to flash in the slot after the newest: SETUP_SAVE_SAVED
// once it reads back the same. saved, saved_seq and saved_slot follow it.
static setup_save_t write_record(const settings_t *next, uint32_t *us) {
    if (!flash_store_fits())
        return SETUP_SAVE_FAILED;
    uint32_t seq = saved_seq + 1u;
    unsigned slot = (unsigned)(saved_slot + 1) % FLASH_STORE_SLOTS;  // slot 0 with none saved
    settings_pack(next, seq, page);
    *us = flash_store_write(slot, page);
    settings_t back;
    uint32_t back_seq;
    bool same = settings_unpack(&back, &back_seq, flash_store_slot(slot)) && settings_equal(&back, next)
                && back_seq == seq;
    read_saved();  // what flash holds now, whether the write took or not
    return same ? SETUP_SAVE_SAVED : SETUP_SAVE_FAILED;
}

setup_save_t setup_save(uint32_t *us) {
    if (setup_saved())
        return SETUP_SAVE_UNCHANGED;
    return write_record(&settings, us);
}

// Password Set's change, or F11 (#122): the record flash holds with only the
// password replaced, as the 3483-V keeps a new password at once, before F3
// (captured Oct 13). Display Setup's pending changes still wait for F3.
static void save_password(void) {
    if (saved_slot >= 0 && saved.password == settings.password)
        return;
    settings_t next = saved;
    next.password = settings.password;
    uint32_t us;
    if (write_record(&next, &us) == SETUP_SAVE_SAVED)
        saves++;
    else
        save_fails++;
}

static void draw_setup(void) {
    setup_ui_draw(&ui, &settings);
    drawn = settings;
    drawn_at = video_frames_begun();
    redraw = false;
}

// SetUp shows from its first draw, which setup_poll makes as soon as the
// renderer is off the image it would draw into: a frame begun before a
// close may still be drawing it.
static void open_setup(void) {
    setup_ui_open(&ui);
    leaving = false;
    usb_host_local(true);    // the console's open, too, so the keyboard's keys go to SetUp
    video_splash_dismiss();  // SetUp takes the screen, and the splash doesn't come back
    redraw = true;
}

// Out of offline setup (#110), SetUp's image stays up through the save until
// the link's power-on reset lands (setup_poll), so the host's screen from
// before it never shows again. Into the lock (#122), the keyboard stays in
// local mode.
static void close_setup(bool left_offline, bool locking) {
    if (left_offline)
        leaving = true;
    else
        showing = false;
    if (!locking)
        usb_host_local(false);
    uint32_t us;
    setup_save_t saved = setup_save(&us);  // as set save does: only if the record changed
    if (saved == SETUP_SAVE_SAVED)
        saves++;
    else if (saved == SETUP_SAVE_FAILED)
        save_fails++;
}

// The lock's status line into the image the renderer isn't reading, then
// made the front with one store after it.
static void draw_lock(void) {
    unsigned back = lock_front ^ 1u;
    lock_status_line(&lock, &lock_lines[back]);
    atomic_signal_fence(memory_order_release);
    lock_front = (uint8_t)back;
}

// Locks the terminal (#122): from SetUp's Lock sessions, or auto dim at page
// 1's Lock sessions Yes. The keyboard stays in local mode, so only Shift and
// Alt reach the controller, as on the 3483-V (captured Oct 13).
static void engage_lock(void) {
    lock_engage(&lock);
    draw_lock();
    locked = true;
    usb_host_local(true);  // and a held key repeats no further (kbd_local)
    video_splash_dismiss();
}

static void lock_handle(uint8_t key, bool shift) {
    switch (lock_key(&lock, key, shift, settings.password)) {
    case LOCK_UNLOCKED:
        locked = false;
        draw_lock();  // blank, so the next lock never shows this one's prompt
        usb_host_local(false);
        dim_activity(&dim, now_ms());  // the unlock is activity: auto dim's timer starts again from it
        break;
    case LOCK_ALARM:
        lock_alarms++;
        draw_lock();
        break;
    case LOCK_REDRAW:
        draw_lock();
        break;
    case LOCK_NONE:
        break;
    }
}

// One of SetUp's keys. A key that comes after the F3 that closed it, still
// in the ring, is dropped.
static void handle(uint8_t key, bool shift) {
    if (lock_state(&lock) != LOCK_OFF) {
        lock_handle(key, shift);
        return;
    }
    if (setup_ui_screen(&ui) == SETUP_UI_OFF) {
        if (key == K_SETUP)
            open_setup();
        return;
    }
    setup_ui_result_t result = setup_ui_key(&ui, key, shift, &settings);
    if (result == SETUP_UI_CLOSED || result == SETUP_UI_LEFT_OFFLINE) {
        close_setup(result == SETUP_UI_LEFT_OFFLINE, false);  // F3 out of offline setup saves too (#110)
    } else if (result == SETUP_UI_LOCK) {
        engage_lock();             // first, so no frame between shows the host's screen
        close_setup(false, true);  // saves, as F3 does (not captured), and keeps local mode for the lock
    } else if (result == SETUP_UI_PREVIEW) {
        previews++;  // the alarm at Alarm volume's new level, or the flash at Off (#107)
        redraw = true;
    } else if (result == SETUP_UI_PASSWORD_SET || result == SETUP_UI_PASSWORD_CLEARED) {
        save_password();  // holds this loop for the erase, about 45 ms, as F3's save does
        redraw = true;
    } else if (result != SETUP_UI_ALARM) {
        redraw = true;
    }
}

// When the live model isn't the link's (set model, set defaults): offline
// for a second, then online at the live model, whatever it is by then. And
// offline setup (#110): offline while it's up, then online as it closes,
// once the link has been off the coax for that second.
static void drive_link(void) {
    switch (model_change_poll(&change, now_ms(), settings.model, coax_link_model(), coax_link_offline(),
                              setup_ui_offline(&ui), coax_link_reset_pending())) {
    case MODEL_CHANGE_OFFLINE:
        coax_link_go_offline(LINK_TIMEOUT_MS);
        break;
    case MODEL_CHANGE_ONLINE:
        coax_link_go_online(settings.model, LINK_TIMEOUT_MS);
        break;
    case MODEL_CHANGE_NONE:
        break;
    }
}

void setup_poll(void) {
    uint32_t now = now_ms();
    lock_dim_t due = lock_dim_due(&settings, lock_state(&lock) != LOCK_OFF);
    if (due == LOCK_DIM_NONE) {
        dim_activity(&dim, now);  // locked, auto dim never blanks (Oct 13); its timer runs from the unlock
    } else if (due == LOCK_DIM_LOCK && setup_ui_screen(&ui) == SETUP_UI_OFF
               && (dim_on(&dim) || dim_due(&dim, &settings, now, term_writes(term)))) {
        // Page 1's Lock sessions Yes: lock instead of blanking, from the host's screen only (with SetUp up,
        // auto dim blanks as before; not captured). Asked before dim_tick, so auto dim never comes on first;
        // v dim's locks too. The lock first, so no frame between shows the host's screen.
        engage_lock();
        dim_activity(&dim, now);
    } else {
        dim_tick(&dim, &settings, now, term_writes(term));
    }
    ruler_poll(&ruler, usb_host_rule_presses(), term_ac(term), settings.ruler_follows, coax_link_model());
    uint8_t key;
    bool shift;
    while (usb_host_local_key(&key, &shift))
        handle(key, shift);
    // A draw as SetUp opens, for a key, or for the console's set changing
    // what SetUp shows, once the renderer has begun a frame on the last image
    // (the double buffer).
    bool open = setup_ui_screen(&ui) != SETUP_UI_OFF;
    if (open && (redraw || !settings_equal(&settings, &drawn)) && video_frames_begun() != drawn_at) {
        draw_setup();
        showing = true;
    }
    // The translator's Typematic Rate and Delay, as SetUp or the console
    // left the live record (#107).
    usb_host_typematic(settings.typematic_rate, settings.typematic_delay);
    drive_link();  // the model the controller sees, as the live record says (#110)
    if (leaving && !coax_link_offline() && !coax_link_reset_pending()) {
        showing = false;  // the power-on reset is in: the host's screen, cleared
        leaving = false;
    }
}

bool setup_showing(void) {
    return showing;
}

const uint8_t *setup_regen(void) {
    return setup_ui_regen(&ui);
}

const uint8_t *setup_eab(void) {
    return setup_ui_eab(&ui);
}

uint16_t setup_cursor(void) {
    return setup_ui_cursor(&ui);
}

bool setup_locked(void) {
    return locked;
}

const lock_line_t *setup_lock_line(void) {
    return &lock_lines[lock_front];
}

uint32_t setup_alarms(void) {
    setup_ui_stats_t s;
    setup_ui_stats(&ui, &s);
    return s.alarms + save_fails + previews + lock_alarms;
}

uint32_t setup_previews(void) {
    return previews;
}

uint32_t setup_power_ons(void) {
    return model_change_power_ons(&change);
}

void setup_stats(setup_stats_t *out) {
    setup_ui_stats_t s;
    setup_ui_stats(&ui, &s);
    lock_stats_t l;
    lock_stats(&lock, &l);
    *out = (setup_stats_t){setup_ui_screen(&ui), s.opens, s.keys, s.alarms, saves, save_fails,
                           lock_state(&lock), l.locks, l.unlocks, l.wrong};
}

bool setup_press(uint8_t key) {
    if (lock_state(&lock) == LOCK_OFF && setup_ui_screen(&ui) == SETUP_UI_OFF && key != K_SETUP)
        return false;
    dim_activity(&dim, now_ms());
    handle(key, false);
    return true;
}

bool setup_dimmed(void) {
    return dim_on(&dim);
}

bool setup_report(unsigned src, uint32_t ms, const uint8_t report[8], uint8_t out[8]) {
    return dim_report(&dim, src, ms, report, out);
}

void setup_forget(unsigned src) {
    dim_forget(&dim, src);
}

void setup_key(void) {
    dim_activity(&dim, now_ms());
}

void setup_dim_now(void) {
    dim_now(&dim);
}

uint16_t setup_ruler(void) {
    return ruler.at;
}

void setup_ruler_toggle(void) {
    ruler_toggle(&ruler, term_ac(term));
}
