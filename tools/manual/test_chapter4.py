# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""What Chapter 4 and its keys say where the firmware is easy to get wrong (#136)."""

import os
import re
import unittest

import manual_paths
import core
import keys


def source(*parts):
    with open(os.path.join(manual_paths.MANUAL, *parts), encoding='utf-8') as stream:
        return stream.read()


class TestChapter4(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raw = source('chapters', '04-keyboard.typ')
        cls.text = ' '.join((cls.raw + source('keys.typ')).split())

    def test_shift_and_alt_still_reach_the_controller_in_setup(self):
        # The keyboard's local mode hands SetUp and the lock every key but Shift and Alt (#102, #122).
        self.assertIn('every key goes to it but Shift and Alt, which still go to the controller', self.text)

    def test_nearly_any_usb_keyboard(self):
        # usb_host.c gives a keymap only to a boot keyboard interface, so not every USB keyboard types.
        self.assertIn('Nearly any USB keyboard will do: the display station uses the USB boot keyboard interface',
                      self.text)
        self.assertNotRegex(self.text.lower(), r'(?<!nearly )\bany usb keyboard')

    def test_rule_also_goes_to_the_controller(self):
        # A bare Rule turns the ruler on or off and is sent too: the keymap's row has its code, 98 (#51).
        self.assertIn('It also goes to the controller', self.text)

    def test_alt_x_alone_is_exsel(self):
        self.assertIn('"EXTEND_SELECT": (name: "ExSel"', self.text)
        self.assertIn('keys-for(km, "SetUp")', self.text)

    def test_no_chord_is_typed_by_hand(self):
        # A chord with a letter or a digit comes from the keymap, through keys-for, so it can't drift from the
        # firmware; the one exception, the not sign's, is checked below.
        found = re.findall(r'#keys\([^)]*"(?:Shift|Alt)"[^)]*"[A-Za-z0-9]"\)', self.raw)
        self.assertEqual(found, ['#keys("Shift", "6")'])

    def test_the_not_sign_is_on_shift_6(self):
        # The 6 key keeps the PC's Shift, and the 3483-V key it sends is 6¬: shifted, the not sign.
        self.assertIn('¬, the not sign, is on #keys("Shift", "6")', self.text)
        [six] = [r for r in keys.keymaps_data()['keymaps'][0]['rows'] if r['chord'] == [] and r['key'] == '6']
        self.assertEqual((six['label'], six['modifiers']), ('6¬', 'kept'))

    def test_appendix_a_is_named_once(self):
        self.assertIn('@keymaps lists every keymap, key by key', self.text)
        self.assertNotIn('key by key (@keymaps)', self.text)

    def test_setup_takes_shift_because_exsel_is_on_alt_x(self):
        self.assertIn('The keymap already puts ExSel on #keys-for(km, "EXTEND_SELECT"), so SetUp takes '
                      '#keys-for(km, "SetUp")', self.text)

    def test_the_pf_keys_are_named_as_pf_keys(self):
        self.assertIn('PF3 to leave a screen, and PF7 and PF8 to page back and forward, are common', self.text)

    def test_appendix_as_dash_is_a_key_that_sends_nothing(self):
        appendix = ' '.join(source('chapters', 'appendix-a-keymaps.typ').split())
        self.assertIn('A dash means the key sends nothing.', appendix)

    def test_the_keys_oec_ignores_are_explained(self):
        self.assertIn('oec does nothing with the keys marked †; a 3174 can act on them', self.text)

    def test_the_keys_said_to_repeat_are_the_ones_that_do(self):
        # keys3483's repeat classes (captured from a 3483-V): characters and these keys repeat, nothing else.
        self.assertIn('Held down, the keys that type a character repeat, and so do Space, Backspace, Delete, Tab, '
                      'Back Tab, New Line and the arrows; other keys, such as Enter and the PF keys, don’t', self.text)
        said = {'SPACE', 'BACKSPACE', 'DELETE', 'TAB', 'BACKTAB', 'NEWLINE', 'UP', 'DOWN', 'LEFT', 'RIGHT'}
        characters = {'CENT', 'BROKEN_BAR', 'CENTER_PERIOD'}
        found = keys.keymaps_data()['keymaps'][0]['rows']
        repeat = {code: key['repeat'] for (code, key) in core.keys3483().items()}
        for row in found:
            if row['code'] is None:
                continue
            reading = row['reads'][0] if row['reads'] else None
            expected = reading is not None and (len(reading) == 1 or reading in said | characters)
            self.assertEqual(bool(repeat[row['code']]), expected, row)


if __name__ == '__main__':
    unittest.main()
