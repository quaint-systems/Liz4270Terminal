// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// USB keyboards to 3483-V scan codes (#17): see keyboard.h.

#include "keyboard.h"

#include <string.h>

#include "keys3483.h"
#include "usb_usage.h"

// The boot report's modifier byte.
#define RM_LSHIFT 0x02u
#define RM_LALT 0x04u
#define RM_RSHIFT 0x20u
#define RM_RALT 0x40u
#define RM_SHIFT_ALT (RM_LSHIFT | RM_LALT | RM_RSHIFT | RM_RALT)
#define RM_CTRL 0x11u  // Left and Right Ctrl

// The 3483-V modifiers the controller holds down, as bits of kbd_t.sent.
#define CM_LSHIFT 0x01u
#define CM_RSHIFT 0x02u
#define CM_LALT 0x04u
#define CM_RALT 0x08u
#define CM_SHIFT (CM_LSHIFT | CM_RSHIFT)
#define CM_ALT (CM_LALT | CM_RALT)

static const uint8_t cm_code[4] = {K_LSHIFT, K_RSHIFT, K_LALT, K_RALT};

// A sequence, queued whole or not at all. The longest is four modifier
// releases and the key: 9 codes. A modifier is released or made, never both.
#define SEQ_MAX 16u

typedef struct {
    uint8_t code[SEQ_MAX];
    uint8_t n;
    uint8_t sent;  // the controller's modifiers once it is queued
} seq_t;

size_t kbd_sizeof(void) {
    return sizeof(kbd_t);
}

void kbd_init(kbd_t *k, term_t *t) {
    memset(k, 0, sizeof *k);
    k->term = t;
    k->rate = SETTINGS_RATE_NORMAL;
    k->delay = SETTINGS_DELAY_NORMAL;
}

void kbd_attach(kbd_t *k, unsigned src, const keymap_t *map) {
    if (src >= KBD_SOURCES)
        return;
    memset(&k->src[src], 0, sizeof k->src[src]);
    k->src[src].map = map;
    if (k->active && k->active_src == src)
        k->active = false;  // its release will never come
}

static bool contains(const uint8_t *keys, uint8_t usage) {
    for (unsigned i = 0; i < KBD_REPORT_KEYS; i++)
        if (keys[i] == usage)
            return true;
    return false;
}

static void hold(kbd_source_t *s, uint8_t usage, uint8_t key) {
    if (s->held_count < KBD_HELD_MAX)
        s->held[s->held_count++] = (kbd_held_t){usage, key};
}

// What usage's press queued, now that it is let go; K_NOTHING if it wasn't held.
static uint8_t let_go(kbd_source_t *s, uint8_t usage) {
    for (unsigned i = 0; i < s->held_count; i++)
        if (s->held[i].usage == usage) {
            uint8_t key = s->held[i].key;
            s->held[i] = s->held[--s->held_count];
            return key;
        }
    return K_NOTHING;
}

// Whether a held key, on any source, holds key down. A make/break key goes
// down once, however many held keys send it, and up when the last of them is
// let go (#62's M4).
static bool held_anywhere(const kbd_t *k, uint8_t key) {
    for (unsigned i = 0; i < KBD_SOURCES; i++)
        for (unsigned j = 0; j < k->src[i].held_count; j++)
            if (k->src[i].held[j].key == key)
                return true;
    return false;
}

// The PC's Shift and Alt, side for side, over every source.
static uint8_t physical(const kbd_t *k) {
    uint8_t m = 0;
    for (unsigned i = 0; i < KBD_SOURCES; i++) {
        if (!k->src[i].map)
            continue;
        uint8_t r = k->src[i].mods;
        if (r & RM_LSHIFT)
            m |= CM_LSHIFT;
        if (r & RM_RSHIFT)
            m |= CM_RSHIFT;
        if (r & RM_LALT)
            m |= CM_LALT;
        if (r & RM_RALT)
            m |= CM_RALT;
    }
    return m;
}

// The chord a press is looked up under: the PC's Shift and Alt, either side.
static uint8_t chord(const kbd_t *k) {
    uint8_t p = physical(k), c = 0;
    if (p & CM_SHIFT)
        c |= KM_SHIFT;
    if (p & CM_ALT)
        c |= KM_ALT;
    return c;
}

// The controller's modifiers a key needs: the PC's own for KM_KEEP, otherwise
// exactly mods, keeping whichever side the controller already holds.
static uint8_t target(const kbd_t *k, uint8_t mods) {
    if (mods == KM_KEEP)
        return physical(k);
    uint8_t want = 0;
    if (mods & KM_SHIFT)
        want |= (k->sent & CM_SHIFT) ? (k->sent & CM_SHIFT) : CM_LSHIFT;
    if (mods & KM_ALT)
        want |= (k->sent & CM_ALT) ? (k->sent & CM_ALT) : CM_LALT;
    return want;
}

static seq_t start(const kbd_t *k) {
    return (seq_t){.n = 0, .sent = k->sent};
}

// Appends what takes the controller's modifiers from q->sent to want:
// releases first, then makes.
static void reconcile(seq_t *q, uint8_t want) {
    for (unsigned i = 0; i < 4u; i++)
        if (q->sent & ~want & (1u << i)) {
            q->code[q->n++] = K_BREAK;
            q->code[q->n++] = cm_code[i];
        }
    for (unsigned i = 0; i < 4u; i++)
        if (want & ~q->sent & (1u << i))
            q->code[q->n++] = cm_code[i];
    q->sent = want;
}

// Queues q whole: a press only if it leaves KBD_RESERVE slots free, anything
// else if it fits. term_queued only falls while this runs (core 1 takes
// statuses), so a stale count errs on the safe side.
static bool queue(kbd_t *k, const seq_t *q, bool press) {
    unsigned queued = term_queued(k->term);
    unsigned room = queued < TERM_STATUS_SLOTS ? TERM_STATUS_SLOTS - queued : 0u;
    if (q->n > room || (press && room - q->n < KBD_RESERVE))
        return false;
    for (unsigned i = 0; i < q->n; i++) {
        term_key(k->term, q->code[i]);
        if (k->out_count < k->out_max)
            k->out[k->out_count] = q->code[i];
        k->out_count++;
    }
    k->stats.codes += q->n;
    k->may_hold |= (uint8_t)(q->sent & ~k->sent);
    k->sent = q->sent;
    return true;
}

// Into SetUp's ring: false, a drop, if it's full.
static bool local_put(kbd_t *k, uint8_t key, bool shift) {
    if (k->local_count == KBD_LOCAL_MAX) {
        k->stats.drops++;
        return false;
    }
    unsigned at = (k->local_head + k->local_count) % KBD_LOCAL_MAX;
    k->local_keys[at] = key;
    k->local_shift[at] = shift;
    k->local_count++;
    return true;
}

// The active key's first repeat from ms and its period, by its class at the
// translator's Rate and Delay (#107).
static void start_repeat(kbd_t *k, unsigned cls, uint32_t ms) {
    k->due = ms + keys3483_delay_ms[k->delay][cls];
    k->period_ms = keys3483_period_ms[k->rate][cls];
}

static void press(kbd_t *k, unsigned src, uint8_t usage, uint8_t c, uint32_t ms) {
    kbd_source_t *s = &k->src[src];
    const keymap_entry_t *e = keymap_lookup(s->map, usage, c);
    uint8_t key = e ? e->key : (uint8_t)K_NOTHING;
    const k3483_key_t *info = keys3483_key(key);
    // The Shift the 3483-V would send it with (#122): the entry's own, or the PC's where it keeps them.
    bool shift = e && e->mods != KM_KEEP ? (e->mods & KM_SHIFT) != 0 : (c & KM_SHIFT) != 0;

    k->stats.presses++;
    // Every key clicks, local ones and ones that send nothing included, but
    // the 3483-V's that send a release: Shift, Alt, Reset and Caps Lock (#18).
    bool keystroke = !info || !info->make_break;
    if (keystroke)
        k->keystrokes++;
    if (key == K_SETUP)
        k->stats.local++;
    // It becomes the active key even if it sends nothing, so it ends another's repeat.
    k->active = true;
    k->active_src = (uint8_t)src;
    k->active_usage = usage;
    k->active_key = K_NOTHING;
    k->active_mods = KM_KEEP;

    if (k->local || key == K_SETUP) {
        if (keystroke)
            k->local_keystrokes++;  // SetUp's (#107)
        // SetUp's (#102): to it, and nothing to the controller.
        k->local = true;
        hold(s, usage, K_NOTHING);  // so its release sends nothing
        if (!local_put(k, key, shift))
            return;                 // dropped whole: it doesn't repeat either
        k->active_key = key;        // so it repeats into SetUp
        k->active_shift = shift;
        start_repeat(k, info ? info->repeat : KR_NONE, ms);
        return;
    }
    if (!info) {  // no entry, K_NOTHING, or a local function
        hold(s, usage, K_NOTHING);
        return;
    }
    seq_t q = start(k);
    reconcile(&q, target(k, e->mods));
    if (key == K_RULE && !(q.sent & CM_ALT))
        k->rule_presses++;  // a bare Rule, even if the queue drops it: the ruler is local (#51)
    if (!info->make_break || !held_anywhere(k, key))
        q.code[q.n++] = key;
    if (q.n && !queue(k, &q, true)) {
        k->stats.drops++;
        hold(s, usage, K_NOTHING);
        return;
    }
    hold(s, usage, key);
    k->active_key = key;
    k->active_mods = e->mods;
    start_repeat(k, info->repeat, ms);
}

static void release(kbd_t *k, unsigned src, uint8_t usage) {
    uint8_t key = let_go(&k->src[src], usage);
    if (k->active && k->active_src == src && k->active_usage == usage)
        k->active = false;
    const k3483_key_t *info = keys3483_key(key);
    if (info && info->make_break && !held_anywhere(k, key)) {
        seq_t q = start(k);
        q.code[q.n++] = K_BREAK;
        q.code[q.n++] = key;
        if (!queue(k, &q, false))
            k->stats.lost++;
    }
}

// Unless the active key holds the controller's modifiers to its own, they
// follow the PC's. Releases always go in. Makes count as a press, so they never
// spend the reserve: one refused here goes in before the next press or repeat,
// which both reconcile first (the final review's I1: as a restore, a refused
// Shift went in through the reserve on every report until a release no longer
// fitted).
static void settle(kbd_t *k) {
    if (k->active && k->active_mods != KM_KEEP)
        return;
    uint8_t want = physical(k);
    seq_t q = start(k);
    reconcile(&q, (uint8_t)(k->sent & want));
    if (q.n && !queue(k, &q, false))
        k->stats.lost++;
    q = start(k);
    reconcile(&q, want);
    if (q.n)
        queue(k, &q, true);
}

size_t kbd_report(kbd_t *k, unsigned src, const uint8_t report[8], uint32_t ms, uint8_t *sent, size_t sent_max) {
    if (src >= KBD_SOURCES || !k->src[src].map)
        return 0;
    kbd_source_t *s = &k->src[src];
    // The usages, without the modifiers' (E0-E7): the modifier byte carries
    // those, so a keyboard that lists them here too would press them twice
    // (#62's M1).
    uint8_t keys[KBD_REPORT_KEYS];
    for (unsigned i = 0; i < KBD_REPORT_KEYS; i++) {
        uint8_t usage = report[2u + i];
        if (usage == U_ROLLOVER)
            return 0;  // too many keys down: keep the last state
        keys[i] = usage >= U_LCTRL && usage <= U_RGUI ? 0u : usage;
    }
    k->out = sent;
    k->out_max = sent ? sent_max : 0u;
    k->out_count = 0;

    uint8_t was = s->mods, now = report[0];

    // Releases first: usages that went, then Ctrl and GUI bits that fell.
    for (unsigned i = 0; i < KBD_REPORT_KEYS; i++)
        if (s->keys[i] && !contains(keys, s->keys[i]))
            release(k, src, s->keys[i]);
    for (unsigned b = 0; b < 8u; b++) {
        uint8_t bit = (uint8_t)(1u << b);
        if ((bit & RM_SHIFT_ALT) || !(was & bit) || (now & bit))
            continue;
        if (s->consumed & bit)
            s->consumed &= (uint8_t)~bit;
        else
            release(k, src, (uint8_t)(U_LCTRL + b));
    }

    // Then the PC's Shift and Alt take their new state, and presses follow:
    // Ctrl and GUI bits that rose, then new usages, in the report's order.
    s->mods = now;
    uint8_t c = chord(k);
    // A Ctrl bit that rose with a usage the map has a Ctrl chord for is part
    // of that chord, not a key: the Unicomp sends Ctrl+F2 as one report. A
    // Ctrl pressed on its own first is always its own key.
    uint8_t ctrl = now & ~was & RM_CTRL;
    for (unsigned i = 0; ctrl && i < KBD_REPORT_KEYS; i++)
        if (keys[i] && !contains(s->keys, keys[i]) && keymap_lookup_exact(s->map, keys[i], (uint8_t)(c | KM_CTRL)))
            s->consumed |= ctrl;
    for (unsigned b = 0; b < 8u; b++) {
        uint8_t bit = (uint8_t)(1u << b);
        if ((bit & RM_SHIFT_ALT) || (was & bit) || !(now & bit) || (s->consumed & bit))
            continue;
        press(k, src, (uint8_t)(U_LCTRL + b), c, ms);
    }
    for (unsigned i = 0; i < KBD_REPORT_KEYS; i++) {
        if (!keys[i] || contains(s->keys, keys[i]))
            continue;
        uint8_t with_ctrl = (uint8_t)(c | KM_CTRL);
        bool chorded = (s->consumed & ctrl) && keymap_lookup_exact(s->map, keys[i], with_ctrl);
        press(k, src, keys[i], chorded ? with_ctrl : c, ms);
    }
    memcpy(s->keys, keys, KBD_REPORT_KEYS);
    settle(k);

    size_t count = k->out_count;
    k->out = NULL;
    k->out_max = 0;
    return count;
}

void kbd_release_all(kbd_t *k, unsigned src) {
    static const uint8_t empty[8] = {0};
    kbd_report(k, src, empty, 0u, NULL, 0u);
}

void kbd_detach(kbd_t *k, unsigned src) {
    kbd_release_all(k, src);
    kbd_attach(k, src, NULL);
}

void kbd_tick(kbd_t *k, uint32_t ms) {
    // The controller has taken every status, releases included, so a reset
    // now could wipe none of them. Never between a reset and kbd_resync: the
    // firmware ticks only once it has resynced.
    if (term_queued(k->term) == 0)
        k->may_hold = k->sent;
    if (!k->active)
        return;
    const k3483_key_t *info = keys3483_key(k->active_key);
    if (!info || info->repeat == KR_NONE || (int32_t)(ms - k->due) < 0)
        return;
    if (k->local) {
        // Into SetUp's ring, and only while it hasn't two to take.
        if (k->local_count >= KBD_REPEAT_QUEUED)
            return;
        k->due = ms + k->period_ms;
        local_put(k, k->active_key, k->active_shift);
        k->stats.repeats++;
        k->keystrokes++;
        k->local_keystrokes++;
        return;
    }
    // Only while fewer than KBD_REPEAT_QUEUED statuses wait, so a held key never
    // builds a backlog that goes on typing after it is let go. A repeat that
    // waits goes in as soon as one is taken: into an empty queue only, oec's
    // POLLs (up to three every 1/15 s) held the arrows to 15 a second, not 20.
    if (term_queued(k->term) >= KBD_REPEAT_QUEUED)
        return;
    // The next one counts from now, not from when this was due: a late tick
    // sends one repeat, never a burst.
    k->due = ms + k->period_ms;
    // A Shift or Alt make refused since the press goes in first.
    seq_t q = start(k);
    reconcile(&q, target(k, k->active_mods));
    q.code[q.n++] = k->active_key;
    if (queue(k, &q, true)) {
        k->stats.repeats++;
        k->keystrokes++;
    }
}

void kbd_typematic(kbd_t *k, uint8_t rate, uint8_t delay) {
    if (rate < SETTINGS_RATES)
        k->rate = rate;
    if (delay < SETTINGS_DELAYS)
        k->delay = delay;
}

uint8_t kbd_rate(const kbd_t *k) {
    return k->rate;
}

uint8_t kbd_delay(const kbd_t *k) {
    return k->delay;
}

void kbd_resync(kbd_t *k) {
    // may_hold stays: the next reset may wipe these releases too.
    seq_t q = {.n = 0, .sent = k->may_hold};
    reconcile(&q, 0u);
    if (!queue(k, &q, false))
        k->stats.lost++;
    settle(k);
}

void kbd_stats(const kbd_t *k, kbd_stats_t *out) {
    *out = k->stats;
}

void kbd_clear_stats(kbd_t *k) {
    memset(&k->stats, 0, sizeof k->stats);
}

uint32_t kbd_keystrokes(const kbd_t *k) {
    return k->keystrokes;
}

uint32_t kbd_local_keystrokes(const kbd_t *k) {
    return k->local_keystrokes;
}

uint32_t kbd_rule_presses(const kbd_t *k) {
    return k->rule_presses;
}

void kbd_local(kbd_t *k, bool on) {
    k->local = on;
    k->active = false;  // either way: a key held for the controller never repeats into the ring (the lock, #122)
    if (!on) {
        k->local_head = 0;
        k->local_count = 0;
    }
}

bool kbd_local_on(const kbd_t *k) {
    return k->local;
}

bool kbd_local_key(kbd_t *k, uint8_t *key, bool *shift) {
    if (k->local_count == 0)
        return false;
    *key = k->local_keys[k->local_head];
    if (shift)
        *shift = k->local_shift[k->local_head];
    k->local_head = (uint8_t)((k->local_head + 1u) % KBD_LOCAL_MAX);
    k->local_count--;
    return true;
}

void kbd_redact(const kbd_t *k, uint8_t *report, size_t len) {
    if (!k->local)
        return;
    for (size_t i = 2; i < len; i++)
        report[i] = 0;
}
