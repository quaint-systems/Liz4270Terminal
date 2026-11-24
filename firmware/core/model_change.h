// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// A model change on the coax (#110). oec reads the terminal's ID only when
// it finds the terminal afresh, after a POLL goes unanswered, so when the
// live record's model isn't the one the link answers as (set model, set
// defaults), the link goes off the coax for MODEL_CHANGE_SILENCE_MS, then
// comes back with a power-on reset at the live model, whatever it is by
// then, as the 3483-V leaving offline setup. While offline setup is up the
// link stays offline, and as it closes the power-on reset comes, whether the
// model changed or not: at once, or once the link has been silent for
// MODEL_CHANGE_SILENCE_MS, so the controller can't miss it.
//
// The caller posts what model_change_poll returns to core 1, and a posted
// request counts as done, whether or not core 1 took it within the caller's
// timeout: it will, between frames, and until it has the caller passes
// pending and nothing new is asked.
//
// Plain C11, like the rest of the core: the caller passes the time in
// milliseconds, which may wrap.

#ifndef LIZ_MODEL_CHANGE_H
#define LIZ_MODEL_CHANGE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

// More than ten of oec's POLLs (1/15 s), so the controller loses the terminal.
#define MODEL_CHANGE_SILENCE_MS 1000u

typedef enum {
    MODEL_CHANGE_NONE = 0,
    MODEL_CHANGE_OFFLINE = 1,  // post coax_link_go_offline
    MODEL_CHANGE_ONLINE = 2,   // post coax_link_go_online at the live model
} model_change_action_t;

// Defined here so the caller can allocate it. The fields are private to model_change.c.
typedef struct {
    bool silencing;         // off the coax since silent_since
    uint32_t silent_since;
    uint32_t power_ons;     // ONLINEs returned (it wraps)
} model_change_t;

size_t model_change_sizeof(void);  // for ctypes, which can't see sizeof

void model_change_init(model_change_t *m);

// Often, from the loop: what to post now, given the live record's model,
// the link's (the model the core was last powered on as), whether the link
// is offline, whether offline setup holds it offline, and whether a request
// is still on its way to core 1. A link found offline with no change under
// way comes back after the silence too.
model_change_action_t model_change_poll(model_change_t *m, uint32_t now_ms, uint8_t live_model, uint8_t link_model,
                                        bool link_offline, bool held, bool pending);

// The power-on resets asked for since init: audio.c sounds the power-on
// alarm for each.
uint32_t model_change_power_ons(const model_change_t *m);

#endif
