# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""sexp: KiCad's S-expressions survive a parse and a dump."""

import os
import unittest

import paths
import sexp


class TestParse(unittest.TestCase):
    def test_atoms_lists_and_quotes(self):
        e = sexp.parse('(a "b c" d (e "f\\"g\\\\h") (i))')
        self.assertEqual(e, ['a', 'b c', 'd', ['e', 'f"g\\h'], ['i']])
        self.assertIsInstance(e[1], sexp.Q)
        self.assertNotIsInstance(e[2], sexp.Q)

    def test_content_after_the_first_form_is_refused(self):
        self.assertRaises(ValueError, sexp.parse, '(a) (b)')
        self.assertRaises(ValueError, sexp.parse, '(a) b')

    def test_unbalanced(self):
        self.assertRaises(ValueError, sexp.parse, '(a (b)')
        self.assertRaises(ValueError, sexp.parse, '(a))')

    def test_find(self):
        e = sexp.parse('(s (at 1 2) (pin a) (pin b))')
        self.assertEqual(sexp.find(e, 'at'), ['at', '1', '2'])
        self.assertEqual(len(sexp.find_all(e, 'pin')), 2)
        self.assertIsNone(sexp.find(e, 'nope'))


class TestDump(unittest.TestCase):
    def test_round_trip(self):
        e = sexp.parse('(a "b c" d (e "f\\"g") (i (j 1.5)))')
        self.assertEqual(sexp.parse(sexp.dump(e)), e)
        self.assertEqual(sexp.dump(sexp.parse(sexp.dump(e))), sexp.dump(e))

    def test_numbers(self):
        self.assertEqual([sexp.number(x) for x in (1.0, 2.54, -0.0, 96.19000000001, 1 / 3, 7, -1e-6)],
                         ['1', '2.54', '0', '96.19', '0.3333', '7', '0'])

    def test_booleans_and_quotes(self):
        self.assertEqual(sexp.dump(['dnp', True, sexp.Q('x "y"')]), '(dnp yes "x \\"y\\"")')

    @unittest.skipUnless(os.path.isdir(paths.STOCK_SYMBOLS), 'needs KiCad')
    def test_a_stock_library_round_trips(self):
        with open(os.path.join(paths.STOCK_SYMBOLS, 'power.kicad_sym'), encoding='utf-8') as stream:
            e = sexp.parse(stream.read())
        self.assertEqual(sexp.parse(sexp.dump(e)), e)


if __name__ == '__main__':
    unittest.main()
