# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Every keymap as the manual's data, with the terminal's own keys and what oec ignores (#136)."""

import unittest

import keys


def row(keymap, chord, key):
    [found] = [r for r in keymap['rows'] if r['chord'] == chord and r['key'] == key]
    return found


class TestKeys(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.data = keys.keymaps_data()
        cls.us104 = cls.data['keymaps'][0]

    def test_rows_read_as_the_keymaps_page_does(self):
        self.assertEqual({k: v for (k, v) in row(self.us104, ['Alt'], '1').items() if k not in ('code', 'codes')},
                         {'chord': ['Alt'], 'key': '1', 'label': 'Dup/PA1', 'modifiers': 'none', 'reads': ['PA1'],
                          'local': None, 'rule': False, 'sends': None})
        setup = row(self.us104, ['Shift', 'Alt'], 'X')
        self.assertEqual((setup['local'], setup['code'], setup['label']), ('SetUp', None, None))
        rule = row(self.us104, ['Shift'], 'Home')
        self.assertEqual((rule['local'], rule['code'], rule['modifiers'], rule['reads']), ('Rule', 98, 'none', []))
        self.assertEqual(row(self.us104, [], '\\')['reads'], ['\\'])

    def test_a_key_sent_with_nothing_oec_reads_is_named_for_its_description(self):
        # Caps Lock and the 3483-V's Copy send a code oec reads no key from: each is named for keys.typ.
        self.assertEqual(row(self.us104, [], 'Caps Lock')['sends'], 'Caps Lock')
        self.assertEqual(row(self.us104, ['Shift'], 'ScrLk')['sends'], 'Shift+Copy/Play/Test')
        self.assertIsNone(row(self.us104, ['Alt'], '1')['sends'])
        self.assertIsNone(row(self.us104, [], ']')['sends'])  # sends nothing at all
        self.assertIsNone(row(self.us104, ['Shift'], 'Home')['sends'])  # Rule: a local key
        self.assertIn('Shift+Copy/Play/Test', self.data['oec_ignores'])
        self.assertNotIn('Caps Lock', self.data['oec_ignores'])  # oec keeps it as a lock

    def test_each_terminal_key_is_in_every_keymap(self):
        for keymap in self.data['keymaps']:
            for name in keys.TERMINAL_KEYS:
                with self.subTest(keymap=keymap['name'], key=name):
                    self.assertIn(name, [r['local'] for r in keymap['rows']])

    def test_the_default_keymap_comes_first(self):
        self.assertEqual(self.us104['name'], 'us104')
        self.assertEqual(self.us104['title'], 'US 104-key (ANSI)')
        self.assertEqual(self.us104['devices'], [])

    def test_oec_ignores_the_keys_it_has_no_branch_for(self):
        names = ['RESET', 'ATTN', 'SYS_RQ', 'JUMP', 'ENTER', 'PF1', 'a', 'INSERT', 'DUP']
        self.assertEqual(keys.oec_ignores(names), ['RESET', 'ATTN', 'SYS_RQ', 'JUMP'])

    def test_what_oec_ignores_is_read_from_every_keymap(self):
        self.assertIn('RESET', self.data['oec_ignores'])
        self.assertNotIn('ENTER', self.data['oec_ignores'])
        self.assertEqual(self.data['oec_ignores'], sorted(self.data['oec_ignores']))


if __name__ == '__main__':
    unittest.main()
