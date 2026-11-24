# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The host screens the manual composes, since no host shows them on cue (#136)."""

import unittest

import compose
import screen


def text(codes):
    return ''.join(screen.STATUS[c] for c in codes)


class TestStatusLine(unittest.TestCase):

    def test_the_status_line_is_oecs(self):
        line = compose.oec_status()
        self.assertEqual(len(line), 80)
        self.assertEqual(text(line[0:3]), 'OEC')
        self.assertEqual(text(line[20:31]), 'unencrypted')
        self.assertEqual(line[8:17], bytes(9))
        self.assertEqual(compose.oec_status('wait')[8:12], bytes([0xF6, 0x00, 0xF4, 0xF5]))
        self.assertEqual(text(compose.oec_status('system')[10:16]), 'SYSTEM')
        self.assertEqual(compose.oec_status('protected')[8:13], bytes([0xF6, 0x00, 0xF8, 0xDB, 0xD8]))
        self.assertEqual(compose.oec_status('overflow')[8:11], bytes([0xF6, 0x00, 0xDB]))
        self.assertEqual(compose.oec_status(shift=True)[35], 0xDA)
        self.assertEqual(compose.oec_status(insert=True)[45], 0xD3)
        self.assertEqual(text(compose.oec_status(secure=True)[20:29]), 'encrypted')
        for args in ((), ('wait',), ('protected',)):
            self.assertEqual(compose.oec_status(*args)[46:80], bytes(34), args)

    def test_every_symbol_is_cut_from_its_own_status_line(self):
        self.assertEqual(list(compose.STATUS_SYMBOLS),
                         ['oec', 'wait', 'system', 'protected', 'overflow', 'security', 'shift', 'insert',
                          'indicator', 'dim'])
        for (name, (codes, first, last, dimmed)) in compose.STATUS_SYMBOLS.items():
            self.assertEqual(len(codes), 80, name)
            self.assertLessEqual(first, last, name)
        self.assertEqual(compose.STATUS_SYMBOLS['wait'][1:3], (8, 11))
        self.assertTrue(compose.STATUS_SYMBOLS['dim'][3])


class TestScreens(unittest.TestCase):

    def test_colours_shows_every_colour_and_highlight(self):
        f = compose.colours()
        self.assertEqual((f.model, len(f.regen), len(f.eab)), (2, 2000, 2000))
        rows = ' '.join(screen.screen_rows(f.regen))
        for label in ('Input', 'Intensified input', 'Protected', 'Intensified protected', 'Blue', 'Red', 'Pink',
                      'Green', 'Turquoise', 'Yellow', 'White', 'Blink', 'Reverse', 'Underscore'):
            self.assertIn(label, rows)
        attributes = [f.eab[a] for a in range(80, 2000) if screen.is_attribute(f.regen[a])]
        self.assertEqual({(e >> 3) & 7 for e in attributes} - {0}, set(range(1, 8)))
        self.assertEqual({e >> 6 for e in attributes} - {0}, {1, 2, 3})
        self.assertEqual(f.regen[:80], compose.oec_status())

    def test_colours_keeps_all_four_field_kinds(self):
        kinds = {screen.field_of_attribute(c) for c in compose.colours().regen[80:] if screen.is_attribute(c)}
        self.assertLessEqual({(False, screen.NORMAL), (False, screen.INTENSIFIED), (True, screen.NORMAL),
                              (True, screen.INTENSIFIED)}, {(k.protected, k.display) for k in kinds})

    def test_layout_numbers_every_row(self):
        for (model, rows) in ((3, 32), (4, 43)):
            f = compose.layout(model)
            found = screen.screen_rows(f.regen, model)
            self.assertEqual(len(found), rows)
            self.assertTrue(found[0].startswith('----+----1'), found[0])
            self.assertEqual(found[0][75:80], '----8')
            self.assertTrue(found[-1].startswith(f'Row {rows}'), found[-1])
            self.assertEqual((f.model, f.ac), (model, 80))

    def test_every_composed_screen_is_named(self):
        self.assertEqual(sorted(compose.SCREENS), ['colours', 'model3', 'model4'])


if __name__ == '__main__':
    unittest.main()
