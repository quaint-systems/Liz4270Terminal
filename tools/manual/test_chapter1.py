# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""What Chapter 1 says about what Liz4270 is and needs, where it is easy to get wrong (#136)."""

import os
import re
import unittest

import manual_paths


class TestChapter1(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(manual_paths.MANUAL, 'chapters', '01-introducing.typ'), encoding='utf-8') as stream:
            cls.text = ' '.join(stream.read().replace('~', ' ').split())  # ~ is a space no line breaks at

    def test_it_is_a_3483_v_in_cut_mode(self):
        # CLAUDE.md, "What the device is": it impersonates an IBM 3483-V in CUT mode.
        self.assertIn('an IBM 3483-V display station in CUT mode', self.text)

    def test_it_needs_a_3174_or_oec(self):
        self.assertIn('IBM 3174 Establishment Controller', self.text)
        self.assertIn('oec', self.text)
        self.assertIn('Liz 4174', self.text)

    def test_what_isnt_there_is_named(self):
        # concept.md: DFT mode, the selector pen, the magnetic stripe reader and printers are out of scope.
        for words in ('DFT mode', 'selector pen', 'magnetic stripe reader', 'no printer port'):
            self.assertIn(words, self.text)

    def test_nearly_any_usb_keyboard(self):
        # usb_host.c gives a keymap only to a boot keyboard interface, so not every USB keyboard types.
        self.assertIn('A USB keyboard: nearly any will do', self.text)
        self.assertIn('*The keyboard* (@keyboard): nearly any USB keyboard', self.text)
        self.assertNotRegex(self.text.lower(), r'(?<!nearly )\bany usb keyboard')

    def test_figure_1_1_follows_what_you_need_in_the_text(self):
        # Floated, it landed between two of What you need's items on both papers; CoffeeMuse chose it after the
        # list, in the text, at the cost of a gap at the page's foot (PR 3's review).
        after = self.text.split('- Power, as @setting-up says.', 1)[1].split('== What it does', 1)[0]
        self.assertIn('<fig-system>', after)
        figure = re.search(r'#figure\((.*?)\) <fig-system>', self.text)
        self.assertNotIn('placement', figure.group(1))

    def test_the_monitor_needs_640_by_480(self):
        # main.c starts the video at 640x480, 60 Hz, every time; 720x480 is a console bench aid only.
        self.assertIn('640 × 480 at 60 Hz', self.text)


if __name__ == '__main__':
    unittest.main()
