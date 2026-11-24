# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The board ID (firmware/core/board_id.c, #97): GPIO 4 and 5, read at power-on with the pads' pull-ups on.
The Fruit Jam's buttons 2 and 3 leave both high, revision A's 4.7 kOhm pull-downs hold both low, and
anything else is unknown: on a Fruit Jam, a button held through reset."""

import unittest

import core

# board_id.h's board_t
(UNKNOWN, FRUIT_JAM, REV_A) = (0, 1, 2)


class TestBoardId(unittest.TestCase):
    def test_both_high_is_the_fruit_jam(self):
        self.assertEqual(core.board_from_id(True, True), FRUIT_JAM)
        self.assertEqual(core.board_name(FRUIT_JAM), 'Fruit Jam')

    def test_both_low_is_revision_a(self):
        self.assertEqual(core.board_from_id(False, False), REV_A)
        self.assertEqual(core.board_name(REV_A), 'Liz4270 rev A')

    def test_one_low_is_unknown(self):
        for (gpio4, gpio5) in ((False, True), (True, False)):
            self.assertEqual(core.board_from_id(gpio4, gpio5), UNKNOWN, (gpio4, gpio5))
        self.assertEqual(core.board_name(UNKNOWN), 'unknown')

    def test_a_value_past_the_list_is_unknown(self):
        self.assertEqual(core.board_name(3), 'unknown')

    def test_only_revision_a_has_the_fault_flag_and_hpd(self):
        for board in (UNKNOWN, FRUIT_JAM, REV_A, 3):
            self.assertEqual(core.board_has_usb_fault(board), board == REV_A, board)
            self.assertEqual(core.board_has_hpd(board), board == REV_A, board)


if __name__ == '__main__':
    unittest.main()
