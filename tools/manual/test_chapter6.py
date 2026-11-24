# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""What Chapter 6 says about the alarm and the key click, where the firmware is easy to get wrong (#136)."""

import os
import unittest

import manual_paths
import core
import keys


class TestChapter6(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(manual_paths.MANUAL, 'chapters', '06-sound.typ'), encoding='utf-8') as stream:
            cls.text = ' '.join(stream.read().split())

    def test_the_power_on_alarm_always_sounds(self):
        # beep_power_on_volume: at Alarm volume Off, the power-on alarm sounds at 3's level (#107).
        self.assertIn('The power-on alarm still sounds', self.text)

    def test_alarm_volume_off_flashes_the_screen(self):
        # beep_resolve turns an alarm at Off into the flash, which is Liz4270's own (page 2's design, #107).
        self.assertIn('The screen flashes instead', self.text)
        self.assertIn('a 3483-V at Off shows nothing', self.text)

    def test_setups_keys_click_whatever_click_says(self):
        # beep_poll: a local keystroke clicks whatever Click and the POLL bits say (captured Oct 12, #107).
        self.assertIn('whatever Click says', self.text)

    def test_the_hosts_keys_need_the_controllers_clicker(self):
        # beep_poll: a host keystroke needs Click Yes and term_clicker; oec sets it only with --clicker.
        self.assertIn('only when Click is Yes and the controller has turned the clicker on', self.text)
        self.assertIn('--clicker', self.text)

    def test_the_waking_key_doesnt_click(self):
        # dim_report takes the waking key out of the report before the translator counts it.
        self.assertIn("The key that brings the screen back from auto dim doesn't click", self.text)

    def test_a_held_key_clicks_as_it_repeats(self):
        # keyboard.c counts each typematic repeat as a keystroke.
        self.assertIn('A held key clicks each time it repeats', self.text)

    def test_the_keys_said_not_to_click_are_the_ones_that_send_a_release(self):
        # The 3483-V's keys that send a release never click (docs/upstream-review.md, "What sounds on the 3483-V"):
        # those the default keymap ever sends are Reset, Caps Lock, and the Shift and Alt it sends for either of the
        # PC's.
        make_break = {code: key['label'] for (code, key) in core.keys3483().items() if key['make_break']}
        rows = keys.keymaps_data()['keymaps'][0]['rows']
        sent = {make_break[code] for row in rows for code in row['codes'] if code in make_break}
        self.assertEqual(sent, {'Reset/Quit', 'Caps Lock', 'Left Shift', 'Left Alt'})
        self.assertIn('Shift, Alt, Reset (#keys-for(km, "RESET")) and Caps Lock never click', self.text)

    def test_f7_alarms_before_the_first_page(self):
        # setup_ui.c: F7 with no page before it, or F8 with none after, sounds the alarm.
        self.assertIn('#key("F7") before the first page or #key("F8") past the last', self.text)

    def test_only_the_second_fields_eleventh_character_alarms(self):
        # setup_ui.c: the tenth character in the first field moves on to the second, which alarms at eleven.
        self.assertIn('an eleventh character into the second field', self.text)

    def test_the_alarm_volume_preview_flashes_at_off(self):
        # SETUP_UI_PREVIEW counts as an alarm, which beep_resolve makes the flash at Off.
        self.assertIn('You hear the volume you chose, or at Off see the flash', self.text)

    def test_a_failed_save_names_the_password_too(self):
        # setup.c's save_fails counts the settings' saves and the password's.
        self.assertIn('or Password Set saves a password', self.text)
        self.assertIn('open SetUp and close it again', self.text)

    def test_no_volume_is_given_in_decibels(self):
        # beep.h's ladder is to be tuned to the case's speaker, so the book gives no levels.
        self.assertNotIn('dB', self.text)


if __name__ == '__main__':
    unittest.main()
