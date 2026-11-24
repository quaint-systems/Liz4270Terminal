# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The terminal's local settings (firmware/core/settings.c, #49, and the ruler's #51): SetUp's choices and this
3483-V's values (captures/photos-20261006/setup-1-display-cursor-autodim.jpg)."""

import unittest

import core
import screen


SLOTS = ('colour_input', 'colour_input_hi', 'colour_protected', 'colour_protected_hi')


class TestDefaults(unittest.TestCase):
    def test_this_3483vs_setup(self):
        # Cursor Style Underline, Blink No, Row/column indicator On, Auto dim Yes, Delay 10; the four base
        # colours as themselves (setup-3-display-colour-mapping.jpg); monochrome, our own, off (#50); Rule line
        # Horizontal, White, Follows cursor Yes (setup-4-display-blink-selected.jpg, #51); page 2's Typematic
        # Normal and Normal, Click Yes, both volumes 3 and Mono case No (setup-2-display-typematic-clicker.jpg,
        # #107); offline setup's Screen rows x columns, 24 x 80 (#110); and page 1's Lock sessions No, with no
        # password set (#122).
        self.assertEqual(core.settings_defaults(), {'cursor': 0, 'cursor_blink': False, 'indicator': True,
                                                    'auto_dim': True, 'dim_minutes': 10, 'colour_input': 4,
                                                    'colour_input_hi': 2, 'colour_protected': 1,
                                                    'colour_protected_hi': 7, 'mono': False, 'ruler_style': 0,
                                                    'ruler_colour': 7, 'ruler_follows': True, 'typematic_rate': 0,
                                                    'typematic_delay': 1, 'click': True, 'click_volume': 3,
                                                    'alarm_volume': 3, 'mono_case': False, 'model': 2,
                                                    'lock_sessions': False, 'password': 0})

    def test_setups_delays(self):
        self.assertEqual(core.dim_minutes_choices(), [5, 10, 20])

    def test_screen_py_keeps_the_same_record(self):
        self.assertEqual(screen.DEFAULT_SETTINGS._asdict(), core.settings_defaults())
        self.assertEqual(list(screen.DIM_MINUTES), core.dim_minutes_choices())
        self.assertEqual((screen.UNDERLINE, screen.BLOCK), (0, 1))  # settings.h's order
        self.assertEqual((screen.EAB_BLUE, screen.EAB_RED, screen.EAB_PINK, screen.EAB_GREEN, screen.EAB_TURQUOISE,
                          screen.EAB_YELLOW, screen.EAB_WHITE), tuple(range(1, 8)))  # oec's EAB codes
        self.assertEqual([screen.EAB_COLOURS[code] for code in (screen.EAB_GREEN, screen.EAB_RED, screen.EAB_BLUE,
                                                                screen.EAB_WHITE)],
                         [screen.GREEN, screen.RED, screen.BLUE, screen.WHITE])
        self.assertEqual((screen.RULER_HORIZONTAL, screen.RULER_VERTICAL, screen.RULER_CROSS, screen.RULER_NONE),
                         (0, 1, 2, 3))  # settings.h's settings_ruler_t, SetUp's order
        self.assertEqual((screen.RATE_NORMAL, screen.RATE_FAST), (0, 1))  # settings_rate_t, SetUp's order
        self.assertEqual((screen.DELAY_SHORT, screen.DELAY_NORMAL, screen.DELAY_LONG), (0, 1, 2))


class TestValid(unittest.TestCase):
    def test_the_defaults_and_every_choice(self):
        self.assertTrue(core.settings_valid())
        for minutes in (5, 10, 20):
            self.assertTrue(core.settings_valid(dim_minutes=minutes), minutes)
        self.assertTrue(core.settings_valid(cursor=1, cursor_blink=True, indicator=False, auto_dim=False))
        for slot in SLOTS:
            for colour in range(1, 8):
                self.assertTrue(core.settings_valid(**{slot: colour}), (slot, colour))
        self.assertTrue(core.settings_valid(mono=True))
        for style in range(4):
            for colour in (screen.EAB_WHITE, screen.EAB_GREEN):
                for follows in (False, True):
                    self.assertTrue(core.settings_valid(ruler_style=style, ruler_colour=colour, ruler_follows=follows),
                                    (style, colour, follows))
        for rate in range(2):
            for delay in range(3):
                self.assertTrue(core.settings_valid(typematic_rate=rate, typematic_delay=delay), (rate, delay))
        for volume in range(6):
            self.assertTrue(core.settings_valid(click_volume=volume, alarm_volume=volume), volume)
        self.assertTrue(core.settings_valid(click=False, mono_case=True))
        for model in (2, 3, 4):
            self.assertTrue(core.settings_valid(model=model), model)
        for lock_sessions in (False, True):
            for password in (0, 1, 0xFFFFFFFFFFFFFFFF):
                self.assertTrue(core.settings_valid(lock_sessions=lock_sessions, password=password),
                                (lock_sessions, password))

    def test_anything_setup_doesnt_offer(self):
        cases = [('cursor', 2), ('dim_minutes', 0), ('dim_minutes', 15), ('dim_minutes', 255)]
        cases += [(slot, colour) for slot in SLOTS for colour in (0, 8, 255)]
        cases += [('ruler_style', 4), ('ruler_style', 255)]
        cases += [('ruler_colour', colour) for colour in (0, 1, 2, 3, 5, 6, 8, 255)]  # only white and green
        cases += [('typematic_rate', 2), ('typematic_rate', 255), ('typematic_delay', 3), ('typematic_delay', 255)]
        cases += [(name, volume) for name in ('click_volume', 'alarm_volume') for volume in (6, 255)]
        cases += [('model', model) for model in (0, 1, 5, 255)]
        for (field, value) in cases:
            self.assertFalse(core.settings_valid(**{field: value}), (field, value))


if __name__ == '__main__':
    unittest.main()
