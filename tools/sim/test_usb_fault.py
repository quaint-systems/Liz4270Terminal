# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Revision A's USB fault flag (firmware/core/usb_fault.c, #97): one trip for each time the AP2171W's flag
goes low, re-armed once it has read high for 20 ms, so a wire touched to the pin counts once however it
bounces. A fall the loop only sees in the pin's edge latch counts too."""

import unittest

import core

REARM_MS = 20


class TestTrips(unittest.TestCase):
    def test_high_counts_nothing(self):
        fault = core.UsbFault()
        for ms in range(100):
            fault.poll(ms)
        self.assertEqual(fault.trips, 0)

    def test_one_trip_however_long_the_flag_stays_low(self):
        fault = core.UsbFault()
        for ms in range(100):
            fault.poll(ms, low=True)
        self.assertEqual(fault.trips, 1)

    def test_a_fall_seen_only_in_the_edge_latch_counts(self):
        fault = core.UsbFault()
        fault.poll(0, fell=True)
        self.assertEqual(fault.trips, 1)

    def test_rearmed_after_20_ms_high_and_not_a_millisecond_before(self):
        fault = core.UsbFault()
        fault.poll(0, low=True)
        for ms in range(1, REARM_MS):
            fault.poll(ms)
        fault.poll(REARM_MS - 1, low=True)
        self.assertEqual(fault.trips, 1)
        for ms in range(REARM_MS, 2 * REARM_MS):
            fault.poll(ms)
        fault.poll(2 * REARM_MS, low=True)
        self.assertEqual(fault.trips, 2)

    def test_a_bouncing_contact_counts_once(self):
        fault = core.UsbFault()
        for touch in range(3):
            start = touch * 100
            for ms in range(start, start + 10):
                fault.poll(ms, low=ms % 2 == 0, fell=ms % 3 == 0)
            for ms in range(start + 10, start + 100):
                fault.poll(ms)
            self.assertEqual(fault.trips, touch + 1)

    def test_a_long_gap_between_polls_rearms_it(self):
        # The flag reads high 45 ms after the trip, so that poll re-arms it at once.
        fault = core.UsbFault()
        fault.poll(0, low=True)
        fault.poll(45)
        fault.poll(46, fell=True)
        self.assertEqual(fault.trips, 2)

    def test_the_millisecond_count_may_wrap(self):
        start = 2**32 - 5
        fault = core.UsbFault()
        fault.poll(start, low=True)
        fault.poll((start + REARM_MS - 1) % 2**32)
        fault.poll((start + REARM_MS - 1) % 2**32, low=True)
        self.assertEqual(fault.trips, 1)
        fault.poll((start + 2 * REARM_MS) % 2**32)
        fault.poll((start + 2 * REARM_MS + 1) % 2**32, low=True)
        self.assertEqual(fault.trips, 2)


if __name__ == '__main__':
    unittest.main()
