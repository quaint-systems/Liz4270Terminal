# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Text as the 3483-V's display codes (firmware/core/display_text.c), shared by the splash (#53) and SetUp
(#102), against tools/sim/display_codes.py, which has them from the photographs."""

import unittest

import core
from display_codes import MAIN


class TestDisplayText(unittest.TestCase):
    def test_digits_and_letters_as_the_controller_writes_them(self):
        for (ch, code) in (('0', 0x20), ('9', 0x29), ('a', 0x80), ('z', 0x99), ('A', 0xA0), ('Z', 0xB9)):
            with self.subTest(ch=ch):
                self.assertEqual(core.display_text_code(ch), code)

    def test_setups_punctuation_draws_what_it_says(self):
        for ch in ' ,./()=:+-':
            with self.subTest(ch=ch):
                code = core.display_text_code(ch)
                self.assertNotEqual(code, 0x18)
                self.assertEqual(MAIN[code], ch)

    def test_latin_1_from_the_splash(self):
        self.assertEqual(MAIN[core.display_text_code('\xfc')], 'ü')  # Hübner, on the splash

    def test_a_character_with_no_code_is_a_question_mark(self):
        self.assertEqual(core.display_text_code('\x01'), 0x18)
        self.assertEqual(MAIN[0x18], '?')


if __name__ == '__main__':
    unittest.main()
