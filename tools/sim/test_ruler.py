# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The Rule key's ruler (firmware/core/ruler.c, #51): off at power-on, on and off with each bare Rule press,
and where it goes with Follows cursor (captures/README.md, "2026-10-10 session, later")."""

import unittest

import core

OFF = core.RULER_OFF
AC = 80 + 14 * 80 + 18  # 0015/019, where the 3483-V's photos have the cursor


class TestToggle(unittest.TestCase):
    def test_off_at_power_on(self):
        self.assertEqual(OFF, 0xFFFF)
        self.assertEqual(core.Ruler().at, OFF)

    def test_presses_before_it_starts_dont_turn_it_on(self):
        ruler = core.Ruler(presses=3)  # setup_init seeds it from kbd_rule_presses
        ruler.poll(3, AC)
        self.assertEqual(ruler.at, OFF)
        ruler.poll(4, AC)
        self.assertEqual(ruler.at, AC)

    def test_on_where_the_cursor_is_then_off(self):
        ruler = core.Ruler()
        ruler.toggle(AC)
        self.assertEqual(ruler.at, AC)
        ruler.toggle(1500)
        self.assertEqual(ruler.at, OFF)
        ruler.toggle(1500)
        self.assertEqual(ruler.at, 1500)  # on again where the cursor is now


class TestPoll(unittest.TestCase):
    def test_each_press_toggles_it(self):
        ruler = core.Ruler()
        ruler.poll(1, AC)
        self.assertEqual(ruler.at, AC)
        ruler.poll(1, 1500)  # no new press: the cursor moving doesn't move where it came on
        self.assertEqual(ruler.at, AC)
        ruler.poll(2, 1500)
        self.assertEqual(ruler.at, OFF)

    def test_two_presses_between_polls_leave_it_as_it_was(self):
        # A double tap while core 0's loop waits out a flash erase (#69).
        ruler = core.Ruler()
        ruler.poll(2, AC)
        self.assertEqual(ruler.at, OFF)
        ruler.toggle(500)
        ruler.poll(4, 900)
        self.assertEqual(ruler.at, 500)

    def test_the_count_wraps(self):
        ruler = core.Ruler()
        ruler.poll(0xFFFFFFFF, 80)  # an odd count since power-on
        self.assertEqual(ruler.at, 80)
        ruler.poll(0, 81)  # one more press, past the wrap
        self.assertEqual(ruler.at, OFF)
        ruler.poll(1, 82)
        self.assertEqual(ruler.at, 82)

    def test_the_console_and_the_key_share_it(self):
        ruler = core.Ruler()
        ruler.toggle(100)  # v rule
        ruler.poll(1, 200)  # then a Rule press
        self.assertEqual(ruler.at, OFF)

    def test_off_the_screen_it_waits_for_the_counter_to_come_back(self):
        # A press while oec writes the status line: the counter is in 0-79 for a moment.
        ruler = core.Ruler()
        ruler.poll(1, 5)
        self.assertEqual(ruler.at, 5)
        ruler.poll(1, 30)  # still writing
        self.assertEqual(ruler.at, 30)
        ruler.poll(1, AC)  # the cursor again: it stays here
        self.assertEqual(ruler.at, AC)
        ruler.poll(1, 1500)
        self.assertEqual(ruler.at, AC)

    def test_past_the_screen_counts_as_off_it(self):
        ruler = core.Ruler()
        ruler.toggle(2000)
        ruler.poll(0, 1999)
        self.assertEqual(ruler.at, 1999)

    def test_with_the_counter_left_off_the_screen_it_stays_off_it(self):
        # After r nothing polls, so the counter stays 0 and the ruler is drawn where the cursor is: 1023.
        ruler = core.Ruler()
        ruler.toggle(0)  # v rule
        ruler.poll(0, 0)
        self.assertEqual(ruler.at, 0)
        self.assertEqual(core.render_place(ruler.at), 1023)


class TestAddress(unittest.TestCase):
    def test_following_it_goes_by_the_cursor(self):
        self.assertEqual(core.ruler_address(AC, 1500, True), 1500)

    def test_not_following_it_stays_where_it_came_on(self):
        self.assertEqual(core.ruler_address(AC, 1500, False), AC)

    def test_off_is_off_either_way(self):
        for follows in (False, True):
            self.assertEqual(core.ruler_address(OFF, 1500, follows), OFF, follows)


ROW_5 = 80 + 4 * 80 + 9     # 0005/010, where the Oct 11 probe turned the ruler on
ROW_10 = 80 + 9 * 80 + 9    # 0010/010, where the cursor was when Follows cursor went off
ROW_15 = 80 + 14 * 80 + 9   # 0015/010, where the cursor went after


class TestFollows(unittest.TestCase):
    """Follows cursor turned off with the ruler on pins it where the cursor is then (captured Oct 11, #102)."""

    def test_while_it_follows_it_keeps_up_with_the_cursor(self):
        ruler = core.Ruler()
        ruler.toggle(ROW_5)
        ruler.poll(0, ROW_10, follows=True)
        self.assertEqual(ruler.at, ROW_10)

    def test_follows_turned_off_pins_it_where_the_cursor_is_then(self):
        ruler = core.Ruler()
        ruler.toggle(ROW_5)
        ruler.poll(0, ROW_10, follows=True)
        ruler.poll(0, ROW_15, follows=False)   # Follows off, then the cursor moved
        self.assertEqual(ruler.at, ROW_10)
        self.assertEqual(core.ruler_address(ruler.at, ROW_15, False), ROW_10)

    def test_turned_back_on_it_goes_back_to_the_cursor(self):
        ruler = core.Ruler()
        ruler.toggle(ROW_5)
        ruler.poll(0, ROW_15, follows=True)
        self.assertEqual(core.ruler_address(ruler.at, ROW_15, True), ROW_15)

    def test_the_status_line_doesnt_move_it(self):
        # oec parks the counter in the status line only to write it (#104's review fix).
        ruler = core.Ruler()
        ruler.toggle(ROW_10)
        ruler.poll(0, 40, follows=True)
        self.assertEqual(ruler.at, ROW_10)
        ruler.poll(0, 2000, follows=True)
        self.assertEqual(ruler.at, ROW_10)

    def test_off_it_stays_off(self):
        ruler = core.Ruler()
        ruler.poll(0, ROW_10, follows=True)
        self.assertEqual(ruler.at, OFF)

    def test_a_press_while_it_follows_turns_it_off(self):
        ruler = core.Ruler()
        ruler.poll(1, ROW_5, follows=True)
        self.assertEqual(ruler.at, ROW_5)
        ruler.poll(2, ROW_10, follows=True)
        self.assertEqual(ruler.at, OFF)


if __name__ == '__main__':
    unittest.main()
