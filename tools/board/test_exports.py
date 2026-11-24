# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""What make_exports.py hands the case (#134): the parts inside it, the labels, and its OpenSCAD include."""

import unittest

import layout_edge
import make_exports

CASE = {'outline': {'width': 100.0, 'height': 80.0, 'corner': 1.0},
        'holes': {'H2': {'x': 96.0, 'y': 4.0, 'plated': True}, 'H1': {'x': 4.0, 'y': 4.0, 'plated': True}},
        'edge': {'J3': {'x': 10.0, 'y': 67.3, 'rot': 180.0, 'fpid': 'Connector_Coaxial:BNC'}},
        'inside': {'D1': {'x': 32.0, 'y': 24.3}},
        'labels': [['COAX', 10.0], ['RESET', 94.6]]}


class TestScad(unittest.TestCase):
    def test_it_opens_with_the_hardware_header(self):
        self.assertEqual(make_exports.scad(CASE).split('\n')[:3],
                         ['// Copyright (c) 2026, CoffeeMuse', '// SPDX-License-Identifier: CERN-OHL-P-2.0', ''])

    def test_it_negates_y_and_lists_the_holes_in_order(self):
        text = make_exports.scad(CASE)
        self.assertIn('H1 = [4.0, -4.0];\nH2 = [96.0, -4.0];\nHOLES = [H1, H2];\n', text)
        self.assertIn('D1 = [32.0, -24.3];\nJ3 = [10.0, -67.3];\n', text)

    def test_it_writes_the_outline_and_the_labels(self):
        text = make_exports.scad(CASE)
        self.assertIn('BOARD_W = 100.0;\nBOARD_H = 80.0;\nBOARD_CORNER = 1.0;\n', text)
        self.assertTrue(text.endswith('LABELS = [["COAX", 10.0], ["RESET", 94.6]];\n'))

    def test_num_rounds_and_never_writes_minus_zero(self):
        self.assertEqual(make_exports.num(76.15000000000001), '76.15')
        self.assertEqual(make_exports.num(-0.0), '0.0')


class TestTheCase(unittest.TestCase):
    def test_it_carries_the_parts_inside_and_the_labels(self):
        c = make_exports.case()
        self.assertEqual(sorted(c['inside']), ['D1', 'D5', 'J1', 'J7'])
        self.assertAlmostEqual(c['inside']['D1']['x'], 32.0)
        self.assertAlmostEqual(c['inside']['D1']['y'], 24.3)
        self.assertEqual(c['labels'], [list(label) for label in layout_edge.LABELS])
