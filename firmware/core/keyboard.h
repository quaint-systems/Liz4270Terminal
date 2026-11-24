// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// USB keyboards to 3483-V scan codes (#17): each HID interface's boot reports
// in, the 3483-V's scan codes out into the terminal's status queue
// (term_key), as the controller's POLLs expect them. Which key sends what is
// a keymap's business (keymap.h). This keeps the controller's Shift and Alt
// in step with the PC's, sends releases, repeats the held key, and keeps room
// in the queue for releases. Spec:
// docs/superpowers/specs/2026-10-05-usb-keyboard-map-design.md.
//
// Plain C11 with no Pico headers, like the rest of the core. The firmware
// calls it all from core 0 (usb_host.c), where term_key is safe.

#ifndef LIZ_KEYBOARD_H
#define LIZ_KEYBOARD_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "keymap.h"
#include "term.h"

#define KBD_SOURCES 4u                       // HID interfaces at once: usb_host.h's USB_HOST_HID_MAX
#define KBD_REPORT_KEYS 6u                   // usages in a boot report
#define KBD_HELD_MAX (KBD_REPORT_KEYS + 4u)  // and the Ctrl and GUI bits, both sides
#define KBD_RESERVE 18u                      // status slots a press leaves free for releases
#define KBD_REPEAT_QUEUED 2u                 // a repeat goes in only while fewer statuses wait
#define KBD_LOCAL_MAX 16u                    // SetUp's keys waiting for setup.c's loop (#102)

typedef struct {
    uint8_t usage;  // U_*; U_LCTRL, U_LGUI, U_RCTRL or U_RGUI for those bits
    uint8_t key;    // what its press queued, or found down already: a K_* code, or K_NOTHING
} kbd_held_t;

typedef struct {
    const keymap_t *map;            // NULL: nothing attached
    uint8_t mods;                   // the last report's modifier byte
    uint8_t keys[KBD_REPORT_KEYS];  // the last report's usages, 0 in empty slots
    uint8_t consumed;               // Ctrl bits a same-report chord took: no action of their own
    uint8_t held_count;
    kbd_held_t held[KBD_HELD_MAX];
} kbd_source_t;

typedef struct {
    uint32_t presses;  // keys other than Shift and Alt: sent, local or nothing
    uint32_t repeats;  // typematic repeats queued
    uint32_t drops;    // presses dropped whole: the queue, or SetUp's ring, had no room
    uint32_t local;    // local functions (SetUp)
    uint32_t codes;    // scan codes queued, 240 included
    uint32_t lost;     // releases that didn't fit: the controller may still hold a key down
} kbd_stats_t;

// Defined here so the caller can allocate it (the firmware, statically). The
// fields are private to keyboard.c.
typedef struct kbd {
    term_t *term;
    kbd_source_t src[KBD_SOURCES];
    uint8_t sent;      // the 3483-V modifiers the controller holds down (keyboard.c's CM_*)
    uint8_t may_hold;  // the ones it may hold down after a reset: sent, and any made since kbd_tick saw the queue empty
    bool active;       // the active key: the most recent press still held
    uint8_t active_src, active_usage, active_key, active_mods;
    bool active_shift;  // the active key's Shift, for its repeats into the ring (#122)
    uint32_t due;  // when the active key next repeats, in ms
    uint16_t period_ms;  // the active key's period, fixed at its press
    uint8_t rate, delay; // SetUp's Typematic Rate and Delay (#107): the next press's timing
    kbd_stats_t stats;
    uint32_t keystrokes;  // the clicker's: see kbd_keystrokes (#18)
    uint32_t local_keystrokes;  // SetUp's among them: see kbd_local_keystrokes (#107)
    uint32_t rule_presses;  // the ruler's: see kbd_rule_presses (#51)
    bool local;                         // SetUp is up (#102): keys go to local_keys, not the queue
    uint8_t local_keys[KBD_LOCAL_MAX];  // a ring of 3483-V codes for SetUp
    bool local_shift[KBD_LOCAL_MAX];    // and whether each went with Shift (#122)
    uint8_t local_head, local_count;
    uint8_t *out;  // kbd_report's caller's copy of the codes it queued
    size_t out_max, out_count;
} kbd_t;

size_t kbd_sizeof(void);  // for ctypes, which can't see sizeof

// Nothing attached, nothing held. It only stores t, so it may run before
// term_init does.
void kbd_init(kbd_t *k, term_t *t);

// An interface mounted, translated with map (NULL attaches nothing). Whatever
// src held before is forgotten without a release, and its key stops repeating.
void kbd_attach(kbd_t *k, unsigned src, const keymap_t *map);

// Every key of src let go, as an empty report would; it stays attached. For
// a failed transfer.
void kbd_release_all(kbd_t *k, unsigned src);

// kbd_release_all, then nothing attached. For an unmount.
void kbd_detach(kbd_t *k, unsigned src);

// One 8-byte boot report from src at ms. Copies up to sent_max of the codes
// it queued into sent (which may be NULL), and returns how many it queued.
size_t kbd_report(kbd_t *k, unsigned src, const uint8_t report[8], uint32_t ms, uint8_t *sent, size_t sent_max);

// Typematic: queues the active key's bare make when its time comes, at the
// period its 3483-V key's class has at the Rate it was pressed under
// (keys3483.h), and only while fewer than KBD_REPEAT_QUEUED statuses wait.
// Call it often, from the core that calls kbd_report. Once the controller
// has taken every status, it also notes that the controller holds just the
// modifiers it was sent.
void kbd_tick(kbd_t *k, uint32_t ms);

// SetUp's Typematic Rate and Delay (#107), a settings_rate_t and a
// settings_delay_t: the next press repeats by them; a key held now keeps the
// timing it started with. A value SetUp doesn't offer changes nothing.
// kbd_init starts at Normal and Normal.
void kbd_typematic(kbd_t *k, uint8_t rate, uint8_t delay);

// The Rate and Delay the next press takes, for the console's u (#107).
uint8_t kbd_rate(const kbd_t *k);
uint8_t kbd_delay(const kbd_t *k);

// After a power-on reset wiped the status queue (term_init), which may have
// held modifier makes or releases: releases the 3483-V modifiers the
// controller may hold down, then makes the PC's held ones again, so the
// controller agrees with the PC. With nothing typed since the controller last
// took every status, it queues nothing, as the 3483-V after a power-on.
void kbd_resync(kbd_t *k);

void kbd_stats(const kbd_t *k, kbd_stats_t *out);
void kbd_clear_stats(kbd_t *k);

// What the clicker clicks for (beep.h, #18), since kbd_init: key presses,
// those the controller never gets included (local functions, keys that send
// nothing, presses dropped for a full queue), and typematic repeats. Not the
// 3483-V's keys that send a release, which don't click on the 3483-V: Shift,
// Alt, Reset and Caps Lock. kbd_clear_stats leaves it alone.
uint32_t kbd_keystrokes(const kbd_t *k);

// The keystrokes that went to SetUp, its own key and typematic repeats
// included: kbd_keystrokes counts them too. SetUp's click whatever Click
// says; the host's need it (#107). kbd_clear_stats leaves it alone.
uint32_t kbd_local_keystrokes(const kbd_t *k);

// Bare Rule presses since kbd_init: K_RULE reaching the controller with Alt
// up, Shift up or down, which turn the ruler on and off (ruler.h, #51).
// Alt+Rule, Home to oec, isn't one. A press the queue drops counts, since the
// ruler is local. kbd_clear_stats leaves it alone.
uint32_t kbd_rule_presses(const kbd_t *k);

// SetUp's local mode (#102). While it's on, every press and typematic repeat
// but Shift's and Alt's, which keep the controller in step as the 3483-V's
// do from inside its SetUp (captured Oct 11), puts its 3483-V code
// (K_NOTHING for a key with none) into a ring for SetUp, and nothing into the
// queue. Such a key holds nothing, so its release sends nothing, and Rule
// doesn't count. A K_SETUP press turns it on itself, in the same report, so a
// key typed straight after can't reach the controller first; K_SETUP goes
// into the ring too. Repeats go in only while fewer than KBD_REPEAT_QUEUED
// keys wait; a press that finds the ring full counts as a drop, and doesn't
// repeat. kbd_local(k, false), as SetUp closes, empties the ring, and either
// call ends any repeat, so a key held for the controller as the lock engages
// never repeats into the ring (#122).
void kbd_local(kbd_t *k, bool on);
bool kbd_local_on(const kbd_t *k);

// The oldest key in the ring into *key, and into *shift (unless it's NULL)
// whether it went with Shift as the 3483-V would send it: the keymap entry's
// own Shift, or the PC's where the entry keeps it (#122). A repeat keeps its
// press's. False if there's none.
bool kbd_local_key(kbd_t *k, uint8_t *key, bool *shift);

// A copy of a report as the console's u log and u's last= keep it (#122): in
// local mode its key bytes, 2 to len - 1, are zeroed, so what's typed into
// Password Set or at the lock's prompt never shows there. The modifiers stay,
// since Shift and Alt reach the controller anyway.
void kbd_redact(const kbd_t *k, uint8_t *report, size_t len);

#endif
