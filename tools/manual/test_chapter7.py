# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""What Chapter 7 says about updating the firmware, where it is easy to get wrong (#136)."""

import os
import unittest

import manual_paths


class TestChapter7(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(manual_paths.MANUAL, 'chapters', '07-updating.typ'), encoding='utf-8') as stream:
            cls.text = ' '.join(stream.read().replace('~', ' ').split())

    def test_boot_is_held_through_reset(self):
        # BOOTSEL is read as the RP2350 comes out of reset, so BOOT is held until RESET is let go.
        step = self.text.split('+ Put the display station in update mode', 1)[1].split('+ ', 1)[0]
        hold, reset, out = (step.index(words) for words in ('hold it there', 'Press and release #on-case[RESET]',
                                                            'Then take the paper clip out'))
        self.assertLess(hold, reset)
        self.assertLess(reset, out)

    def test_the_drive_is_the_boot_roms(self):
        self.assertIn('a drive named #raw("RP2350") appears', self.text)

    def test_the_computer_powers_it_during_the_update(self):
        # The board has one USB-C connector, for power and for the RP2350's own USB.
        self.assertIn('During the update the computer powers the display station', self.text)
        self.assertIn('plug the power cable back in', self.text)

    def test_the_version_is_checked_on_the_splash(self):
        self.assertIn('the splash screen shows the new version', self.text)

    def test_the_release_lists_the_firmware_file_and_checksum(self):
        self.assertIn('#raw("liz4270-vX.Y.Z.uf2")', self.text)
        self.assertIn('#raw("SHA256SUMS")', self.text)

    def test_settings_survival_is_still_to_be_confirmed(self):
        self.assertIn('#to-confirm[That a display station with saved settings and a password still has both',
                      self.text)


if __name__ == '__main__':
    unittest.main()
