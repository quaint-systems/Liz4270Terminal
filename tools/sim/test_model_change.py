# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""A model change on the coax (firmware/core/model_change.c, #110): when the live record's model isn't the one
the link answers as, off the coax for a second, then a power-on reset at the live model."""

import unittest

import core

CHANGE = core.constants('model_change.h', 'MODEL_CHANGE_')
NONE, OFFLINE, ONLINE = CHANGE['NONE'], CHANGE['OFFLINE'], CHANGE['ONLINE']
SILENCE = CHANGE['SILENCE_MS']


class TestModelChange(unittest.TestCase):
    def test_a_second_of_silence(self):
        self.assertEqual(SILENCE, 1000)  # more than ten of oec's POLLs (1/15 s)

    def test_the_same_model_does_nothing(self):
        change = core.ModelChange()
        for ms in (0, 500, 5000):
            self.assertEqual(change.poll(ms, live=2, link=2), NONE, ms)
        self.assertEqual(change.power_ons, 0)

    def test_a_change_goes_offline_then_online_a_second_later(self):
        change = core.ModelChange()
        self.assertEqual(change.poll(0, live=4, link=2), OFFLINE)
        self.assertEqual(change.poll(500, live=4, link=2, offline=True), NONE)
        self.assertEqual(change.poll(SILENCE - 1, live=4, link=2, offline=True), NONE)
        self.assertEqual(change.poll(SILENCE, live=4, link=2, offline=True), ONLINE)
        self.assertEqual(change.power_ons, 1)
        self.assertEqual(change.poll(SILENCE + 10, live=4, link=4), NONE)

    def test_changing_back_during_the_silence_still_resets_once(self):
        # The record goes 2 -> 4 -> 2 within the second: one reset, at the live model, which the caller passes on.
        change = core.ModelChange()
        self.assertEqual(change.poll(0, live=4, link=2), OFFLINE)
        self.assertEqual(change.poll(300, live=2, link=2, offline=True), NONE)
        self.assertEqual(change.poll(SILENCE, live=2, link=2, offline=True), ONLINE)
        self.assertEqual(change.poll(SILENCE + 10, live=2, link=2), NONE)
        self.assertEqual(change.power_ons, 1)

    def test_nothing_while_a_request_is_pending(self):
        change = core.ModelChange()
        self.assertEqual(change.poll(0, live=4, link=2, pending=True), NONE)
        self.assertEqual(change.poll(10, live=4, link=2), OFFLINE)

    def test_a_timed_out_request_still_brings_the_link_back(self):
        # The review's case: the offline request times out (core 1 had no gap within 100 ms) and is still pending
        # when the record goes back to 2. Core 1 then takes it: the link is offline at the live model, and must
        # still come back after the silence, not stay off the coax for good.
        change = core.ModelChange()
        self.assertEqual(change.poll(0, live=4, link=2), OFFLINE)  # posted; it timed out
        self.assertEqual(change.poll(50, live=2, link=2, pending=True), NONE)
        self.assertEqual(change.poll(200, live=2, link=2, offline=True), NONE)
        self.assertEqual(change.poll(SILENCE, live=2, link=2, offline=True), ONLINE)
        self.assertEqual(change.power_ons, 1)

    def test_a_link_found_offline_comes_back(self):
        # However it got there, a link off the coax with no change under way comes back after a silence.
        change = core.ModelChange()
        self.assertEqual(change.poll(0, live=2, link=2, offline=True), NONE)
        self.assertEqual(change.poll(SILENCE, live=2, link=2, offline=True), ONLINE)

    def test_offline_setup_holds_the_link_offline(self):
        change = core.ModelChange()
        self.assertEqual(change.poll(0, live=2, link=2, held=True), OFFLINE)
        for ms in (10, SILENCE, 5 * SILENCE):
            self.assertEqual(change.poll(ms, live=2, link=2, offline=True, held=True), NONE, ms)
        self.assertEqual(change.power_ons, 0)

    def test_leaving_offline_setup_resets_at_once(self):
        # As the 3483-V: the silence is behind it, and the power-on reset comes even at the same model.
        change = core.ModelChange()
        self.assertEqual(change.poll(0, live=2, link=2, held=True), OFFLINE)
        self.assertEqual(change.poll(3000, live=2, link=2, offline=True, held=True), NONE)
        self.assertEqual(change.poll(3010, live=2, link=2, offline=True), ONLINE)
        self.assertEqual(change.power_ons, 1)

    def test_leaving_offline_setup_early_waits_out_the_silence(self):
        # Out within the second (a script can be): no reset until the controller must have missed a POLL.
        change = core.ModelChange()
        self.assertEqual(change.poll(0, live=2, link=2, held=True), OFFLINE)
        self.assertEqual(change.poll(30, live=4, link=2, offline=True, held=True), NONE)
        self.assertEqual(change.poll(40, live=4, link=2, offline=True), NONE)
        self.assertEqual(change.poll(SILENCE - 1, live=4, link=2, offline=True), NONE)
        self.assertEqual(change.poll(SILENCE, live=4, link=2, offline=True), ONLINE)
        self.assertEqual(change.power_ons, 1)

    def test_leaving_offline_setup_at_a_new_model(self):
        change = core.ModelChange()
        self.assertEqual(change.poll(0, live=2, link=2, held=True), OFFLINE)
        self.assertEqual(change.poll(3000, live=4, link=2, offline=True, held=True), NONE)
        self.assertEqual(change.poll(3010, live=4, link=2, offline=True), ONLINE)
        self.assertEqual(change.poll(3020, live=4, link=4), NONE)

    def test_offline_setup_during_a_change(self):
        # set model, then offline setup within the second: held until it closes, then one reset.
        change = core.ModelChange()
        self.assertEqual(change.poll(0, live=4, link=2), OFFLINE)
        self.assertEqual(change.poll(200, live=4, link=2, offline=True, held=True), NONE)
        self.assertEqual(change.poll(5000, live=4, link=2, offline=True, held=True), NONE)
        self.assertEqual(change.poll(5010, live=4, link=2, offline=True), ONLINE)
        self.assertEqual(change.power_ons, 1)

    def test_the_clock_wraps(self):
        change = core.ModelChange()
        start = 0xFFFFFFFF - 200
        self.assertEqual(change.poll(start, live=3, link=2), OFFLINE)
        self.assertEqual(change.poll((start + SILENCE - 1) & 0xFFFFFFFF, live=3, link=2, offline=True), NONE)
        self.assertEqual(change.poll((start + SILENCE) & 0xFFFFFFFF, live=3, link=2, offline=True), ONLINE)


if __name__ == '__main__':
    unittest.main()
