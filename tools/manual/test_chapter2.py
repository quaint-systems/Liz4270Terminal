# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""What Chapter 2 says about setting up, where the board or the case is easy to get wrong (#136)."""

import json
import os
import unittest

import manual_paths


class TestChapter2(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(manual_paths.MANUAL, 'chapters', '02-setting-up.typ'), encoding='utf-8') as stream:
            cls.raw = stream.read()
        cls.text = ' '.join(cls.raw.replace('~', ' ').split())

    def test_every_opening_in_the_back_is_described_under_the_cases_label(self):
        # The case prints these over its openings (make_exports.py); Figure 2-1 draws them from the same file.
        with open(os.path.join(manual_paths.ROOT, 'hardware', 'board', 'export', 'liz4270-case.json'),
                  encoding='utf-8') as stream:
            labels = [name for name, _ in json.load(stream)['labels']]
        self.assertEqual(labels, ['COAX', 'USB-C 5V', 'USB', 'HDMI', 'BOOT', 'RESET'])
        for name in labels:
            self.assertIn(f'/ {name}: ', self.raw)
            self.assertIn(f'"{name}": ', self.raw)  # its shape in the drawing

    def test_the_lids_lights_are_named_as_the_case_names_them(self):
        with open(os.path.join(manual_paths.ROOT, 'hardware', 'case', 'dims.scad'), encoding='utf-8') as stream:
            self.assertIn('LED_LABELS = [["PWR", D5], ["RUN", D1]];', stream.read())
        self.assertIn('#on-case[PWR] is lit while the display station has power', self.text)
        self.assertIn('#on-case[RUN] blinks once a second', self.text)  # main.c: HEARTBEAT_MS 500, a toggle

    def test_there_is_no_power_switch(self):
        # The board spec, "The board and its edge": there is no power switch.
        self.assertIn('It has no power switch', self.text)
        self.assertIn('Plug the power cable into #on-case[USB-C 5V].', self.text)

    def test_power_goes_in_last(self):
        steps = self.text.split('== Connecting it', 1)[1].split('== Switching on', 1)[0]
        order = [steps.index(word) for word in ('#on-case[HDMI]', '#on-case[USB]', '#on-case[COAX]',
                                                '#on-case[USB-C 5V]')]
        self.assertEqual(order, sorted(order))

    def test_the_coax_is_93_ohm_rg_62(self):
        self.assertIn('RG-62 cable#ix[RG-62], which is 93 Ω, with a BNC plug at each end', self.text)

    def test_the_power_figures_stay_open_until_measured(self):
        # The spec's 300 to 350 mA is an estimate; the book gives no figure as fact until one is measured.
        power = self.text.split('== Power', 1)[1].split('== The coax', 1)[0]
        self.assertIn('#to-confirm[', power)
        self.assertNotRegex(power.split('#to-confirm[', 1)[0], r'\d+ mA|\d A\b')


if __name__ == '__main__':
    unittest.main()
