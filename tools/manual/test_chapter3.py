# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""What Chapter 3 says where the firmware is easy to get wrong (#136)."""

import os
import unittest

import manual_paths


class TestChapter3(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(manual_paths.MANUAL, 'chapters', '03-screen.typ'), encoding='utf-8') as stream:
            cls.text = ' '.join(stream.read().split())

    def test_the_rule_line_is_off_at_power_on_and_never_saved(self):
        # firmware/core/ruler.c: off at power-on, and never in the settings record (#51).
        self.assertIn('The rule line is off when the display station is switched on, and whether it is on is '
                      'never saved', self.text)

    def test_the_waking_key_isnt_sent(self):
        # Auto dim swallows the key that wakes it, make and release (#26, #49).
        self.assertIn('Any key brings the screen back, and that key is not sent to the host', self.text)

    def test_the_cursor_is_white_in_colour(self):
        # The 3483-V's cursor underscore is white in every field colour (#26, #49); monochrome draws it green.
        self.assertIn('the cursor is white, whatever the colour of the field it is in, and green in monochrome',
                      self.text)

    def test_the_lock_takes_the_whole_status_line(self):
        # render.c draws the lock's own line in every column; lock.h puts the X and the key at its left.
        self.assertIn('the lock takes the whole status line', self.text)
        self.assertNotIn('It draws the lock there too', self.text)

    def test_every_field_has_its_kinds_colour_unless_the_host_chooses(self):
        self.assertIn('Unless the host chooses otherwise, each field is drawn in one of four colours, by its kind',
                      self.text)

    def test_page_3_maps_the_colours_wherever_they_come_from(self):
        # The mapping swaps green, red, blue and white from a field attribute or an EAB byte alike (#50).
        self.assertIn('whether a field’s kind or the host chose them', self.text)

    def test_the_rule_line_follows_or_stays_put(self):
        # Follows cursor No pins it where the cursor is then, whether it came on then or was already on (#102).
        self.assertIn('follow the cursor or stay put', self.text)
        self.assertNotIn('when you turned them on', self.text)

    def test_monochrome_and_mono_case_have_their_pages(self):
        self.assertIn('Monochrome Yes, on Display Setup’s page 4 (@tab-page4)', self.text)
        self.assertIn('== Mono case', self.text)
        self.assertIn('in colour or in monochrome', self.text)

    def test_setup_keeps_model_2s_layout(self):
        # SetUp and the splash stay at Model 2's layout at every model (#110).
        self.assertIn('SetUp and the splash screen keep Model 2’s layout', self.text)


if __name__ == '__main__':
    unittest.main()
