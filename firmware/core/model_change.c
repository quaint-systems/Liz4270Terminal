// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// A model change on the coax (#110). See model_change.h.

#include "model_change.h"

size_t model_change_sizeof(void) {
    return sizeof(model_change_t);
}

void model_change_init(model_change_t *m) {
    *m = (model_change_t){0};
}

model_change_action_t model_change_poll(model_change_t *m, uint32_t now_ms, uint8_t live_model, uint8_t link_model,
                                        bool link_offline, bool held, bool pending) {
    if (pending)
        return MODEL_CHANGE_NONE;
    if (held) {
        // Offline setup: silent from when it opened (or from a change under
        // way), so it comes back as it closes once the silence is behind it.
        if (!m->silencing) {
            m->silencing = true;
            m->silent_since = now_ms;
        }
        return link_offline ? MODEL_CHANGE_NONE : MODEL_CHANGE_OFFLINE;
    }
    if (!m->silencing) {
        if (!link_offline && live_model == link_model)
            return MODEL_CHANGE_NONE;
        m->silencing = true;
        m->silent_since = now_ms;
        return link_offline ? MODEL_CHANGE_NONE : MODEL_CHANGE_OFFLINE;
    }
    if (now_ms - m->silent_since < MODEL_CHANGE_SILENCE_MS)
        return MODEL_CHANGE_NONE;
    m->silencing = false;
    m->power_ons++;
    return MODEL_CHANGE_ONLINE;
}

uint32_t model_change_power_ons(const model_change_t *m) {
    return m->power_ons;
}
