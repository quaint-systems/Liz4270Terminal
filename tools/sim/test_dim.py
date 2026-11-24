# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Auto dim (firmware/core/dim.c, #49), as the 3483-V did it on Oct 5 and 6 (docs/upstream-review.md):
on after the delay with no keystroke and no write; a write ends it; a keystroke ends it and is swallowed.
Only the keys pressed to wake it are taken out, each until it's let go: a key pressed after them is typed."""

import unittest

import core
import screen

MINUTE = 60000
U = core.usages()
(A, L, O) = (U['A'], U['L'], U['O'])
LSHIFT = 0x02
NOTHING = (0, [])


class TestTimer(unittest.TestCase):
    def test_on_at_the_delay_and_not_a_millisecond_before(self):
        for minutes in (5, 10, 20):
            dim = core.Dim(ms=1000)
            settings = screen.Settings(dim_minutes=minutes)
            dim.tick(1000 + minutes * MINUTE - 1, settings=settings)
            self.assertFalse(dim.on, minutes)
            dim.tick(1000 + minutes * MINUTE, settings=settings)
            self.assertTrue(dim.on, minutes)

    def test_due_is_whether_tick_would_turn_it_on(self):
        # Asked first where auto dim locks instead (#122), so it never comes on before the lock.
        settings = screen.Settings(dim_minutes=5)
        dim = core.Dim(ms=1000)
        self.assertFalse(dim.due(1000 + 5 * MINUTE - 1, settings=settings))
        self.assertTrue(dim.due(1000 + 5 * MINUTE, settings=settings))
        self.assertFalse(dim.on)  # asking changes nothing
        self.assertFalse(dim.due(1000 + 5 * MINUTE, writes=1, settings=settings))  # a write is activity
        self.assertFalse(dim.due(1000 + 5 * MINUTE, settings=screen.Settings(auto_dim=False)))
        dim.tick(1000 + 5 * MINUTE, settings=settings)
        self.assertFalse(dim.due(1000 + 5 * MINUTE, settings=settings))  # already on

    def test_a_write_ends_it_and_restarts_the_timer(self):
        dim = core.Dim(writes=5)
        dim.tick(10 * MINUTE, writes=5)
        self.assertTrue(dim.on)
        dim.tick(10 * MINUTE + 1, writes=6)
        self.assertFalse(dim.on)
        dim.tick(20 * MINUTE, writes=6)
        self.assertFalse(dim.on)
        dim.tick(20 * MINUTE + 1, writes=6)
        self.assertTrue(dim.on)

    def test_a_write_every_30_s_keeps_it_off(self):
        # Oct 6: 23 writes 30 s apart held the 3483-V's rows up for 11.5 minutes.
        dim = core.Dim()
        for n in range(1, 41):
            dim.tick(n * 30000, writes=n)
            self.assertFalse(dim.on, n)

    def test_the_setting_off_ends_it_and_keeps_it_off(self):
        dim = core.Dim()
        dim.tick(10 * MINUTE)
        self.assertTrue(dim.on)
        off = screen.Settings(auto_dim=False)
        dim.tick(10 * MINUTE + 1, settings=off)
        self.assertFalse(dim.on)
        dim.tick(60 * MINUTE, settings=off)
        self.assertFalse(dim.on)
        dim.tick(70 * MINUTE - 1)  # back on: the timer counts from the last tick it was off
        self.assertFalse(dim.on)
        dim.tick(70 * MINUTE)
        self.assertTrue(dim.on)

    def test_the_millisecond_count_may_wrap(self):
        start = 2**32 - 3 * MINUTE
        dim = core.Dim(ms=start)
        dim.tick((start + 10 * MINUTE - 1) % 2**32)
        self.assertFalse(dim.on)
        dim.tick((start + 10 * MINUTE) % 2**32)
        self.assertTrue(dim.on)

    def test_now_and_activity(self):
        dim = core.Dim()
        dim.now()
        self.assertTrue(dim.on)
        dim.activity(5)
        self.assertFalse(dim.on)
        dim.tick(5 + 10 * MINUTE - 1)
        self.assertFalse(dim.on)


class TestKeys(unittest.TestCase):
    """Dim.report gives (mods, usages) as the translator gets them, and took says whether any were taken out."""

    def dimmed(self):
        dim = core.Dim()
        dim.tick(10 * MINUTE)
        self.assertTrue(dim.on)
        return dim

    def test_while_its_off_a_key_passes_and_restarts_the_timer(self):
        dim = core.Dim()
        self.assertEqual(dim.report(0, [A], ms=9 * MINUTE), (0, [A]))
        self.assertFalse(dim.took)
        self.assertEqual(dim.report(ms=9 * MINUTE + 100), NOTHING)
        dim.tick(10 * MINUTE)
        self.assertFalse(dim.on)
        dim.tick(19 * MINUTE)
        self.assertTrue(dim.on)

    def test_the_waking_key_is_taken_out_until_its_let_go(self):
        dim = self.dimmed()
        self.assertEqual(dim.report(0, [A], ms=10 * MINUTE + 1), NOTHING)
        self.assertTrue(dim.took)
        self.assertFalse(dim.on)
        self.assertEqual(dim.report(0, [A], ms=10 * MINUTE + 2), NOTHING)  # still held: still taken out
        self.assertEqual(dim.report(ms=10 * MINUTE + 3), NOTHING)  # let go: nothing for the translator to release
        self.assertFalse(dim.took)
        self.assertEqual(dim.report(0, [A], ms=10 * MINUTE + 4), (0, [A]))  # the next press is a key again

    def test_keys_pressed_while_the_waking_key_is_held_are_typed(self):
        # Typing "lo" on a dimmed screen: the L wakes it, the O is typed.
        dim = self.dimmed()
        self.assertEqual(dim.report(0, [L], ms=10 * MINUTE + 1), NOTHING)
        self.assertEqual(dim.report(0, [L, O], ms=10 * MINUTE + 2), (0, [O]))
        self.assertTrue(dim.took)
        self.assertEqual(dim.report(0, [O], ms=10 * MINUTE + 3), (0, [O]))
        self.assertFalse(dim.took)
        self.assertEqual(dim.report(ms=10 * MINUTE + 4), NOTHING)

    def test_a_waking_shift_is_taken_out_until_its_let_go(self):
        # The modifier was the keystroke that woke it, so it never reaches the controller: the A after it
        # is typed without it.
        dim = self.dimmed()
        self.assertEqual(dim.report(LSHIFT, ms=10 * MINUTE + 1), NOTHING)
        self.assertEqual(dim.report(LSHIFT, [A], ms=10 * MINUTE + 2), (0, [A]))
        self.assertEqual(dim.report(ms=10 * MINUTE + 3), NOTHING)
        self.assertEqual(dim.report(LSHIFT, ms=10 * MINUTE + 4), (LSHIFT, []))

    def test_a_shift_held_through_the_delay_stays_held(self):
        # Shift down before auto dim, then A wakes it: only the A is taken out.
        dim = core.Dim()
        self.assertEqual(dim.report(LSHIFT, ms=0), (LSHIFT, []))
        dim.tick(10 * MINUTE)
        self.assertTrue(dim.on)
        self.assertEqual(dim.report(LSHIFT, [A], ms=10 * MINUTE + 1), (LSHIFT, []))
        self.assertEqual(dim.report(LSHIFT, ms=10 * MINUTE + 2), (LSHIFT, []))
        self.assertEqual(dim.report(ms=10 * MINUTE + 3), NOTHING)

    def test_only_the_waking_keyboard_has_keys_taken_out(self):
        dim = self.dimmed()
        self.assertEqual(dim.report(0, [A], src=1, ms=10 * MINUTE + 1), NOTHING)
        self.assertEqual(dim.report(0, [A], src=2, ms=10 * MINUTE + 2), (0, [A]))
        self.assertEqual(dim.report(0, [A], src=1, ms=10 * MINUTE + 3), NOTHING)

    def test_a_report_that_only_lets_go_isnt_activity(self):
        dim = core.Dim()
        dim.report(0, [A], ms=0)
        dim.tick(5 * MINUTE)
        self.assertEqual(dim.report(ms=5 * MINUTE), NOTHING)
        dim.tick(10 * MINUTE)
        self.assertTrue(dim.on)
        self.assertEqual(dim.report(ms=10 * MINUTE + 1), NOTHING)  # nor does it wake it
        self.assertTrue(dim.on)

    def test_a_rollover_report_wakes_it_and_is_taken_out(self):
        # Too many keys at once: a boot keyboard sends ErrorRollOver (1) in every slot.
        dim = self.dimmed()
        self.assertEqual(dim.report(0, [1] * 6, ms=10 * MINUTE + 1), NOTHING)
        self.assertFalse(dim.on)

    def test_a_source_past_those_tracked_wakes_it_and_passes(self):
        dim = self.dimmed()
        self.assertEqual(dim.report(0, [A], src=7, ms=10 * MINUTE + 1), (0, [A]))
        self.assertFalse(dim.on)

    def test_an_unplug_forgets_the_waking_key(self):
        dim = self.dimmed()
        self.assertEqual(dim.report(0, [A], ms=10 * MINUTE + 1), NOTHING)
        dim.forget(0)  # the keyboard went with A down, and came back with it down
        self.assertEqual(dim.report(0, [A], ms=10 * MINUTE + 2), (0, [A]))  # a key again, and activity
        dim.tick(20 * MINUTE + 1)
        self.assertFalse(dim.on)
        dim.tick(20 * MINUTE + 2)
        self.assertTrue(dim.on)

    def test_forgetting_a_source_past_those_tracked_is_harmless(self):
        dim = self.dimmed()
        dim.forget(7)
        self.assertEqual(dim.report(0, [A], ms=10 * MINUTE + 1), NOTHING)

    def test_a_press_while_the_waking_key_is_held_is_activity(self):
        dim = self.dimmed()
        self.assertEqual(dim.report(0, [A], ms=10 * MINUTE + 1), NOTHING)  # the wake
        self.assertEqual(dim.report(0, [A, O], ms=15 * MINUTE), (0, [O]))  # another key, typed
        dim.tick(20 * MINUTE + 1)  # 10 minutes after the wake
        self.assertFalse(dim.on)
        dim.tick(25 * MINUTE - 1)
        self.assertFalse(dim.on)
        dim.tick(25 * MINUTE)  # 10 minutes after the later press
        self.assertTrue(dim.on)


class TestThroughTheTranslator(unittest.TestCase):
    """Each report through auto dim, then the translator: the codes the controller gets."""

    def setUp(self):
        self.kb = core.Keyboard()
        self.dim = core.Dim()

    def feed(self, mods=0, usages=(), ms=0):
        (mods, usages) = self.dim.report(mods, usages, ms=ms)
        return self.kb.report(mods, usages, ms=ms)

    def test_a_shift_held_through_the_delay_is_released_with_the_key(self):
        # Review Focus 2: Shift held through the delay, a key wakes the screen, all up.
        self.assertEqual(self.feed(LSHIFT, ms=0), [18])
        self.dim.tick(10 * MINUTE)
        self.assertTrue(self.dim.on)
        self.assertEqual(self.feed(LSHIFT, [A], ms=10 * MINUTE + 1), [])
        self.assertEqual(self.feed(ms=10 * MINUTE + 2), [240, 18])
        self.assertFalse(self.dim.on)

    def test_typing_lo_on_a_dimmed_screen_types_the_o(self):
        k = core.scan_codes()
        self.dim.tick(10 * MINUTE)
        self.assertEqual(self.feed(0, [L], ms=10 * MINUTE + 1), [])
        self.assertEqual(self.feed(0, [L, O], ms=10 * MINUTE + 2), [k['O']])
        self.assertEqual(self.feed(ms=10 * MINUTE + 3), [])


if __name__ == '__main__':
    unittest.main()
