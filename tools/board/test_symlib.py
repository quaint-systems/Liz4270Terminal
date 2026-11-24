# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""symlib: pins, units and flattened definitions of KiCad's stock symbols the board uses."""

import os
import unittest

import paths
import sexp
import symlib


@unittest.skipUnless(os.path.isdir(paths.STOCK_SYMBOLS), 'needs KiCad')
class TestSymbols(unittest.TestCase):
    def test_rp2350b(self):
        s = symlib.lookup('MCU_RaspberryPi:RP2350B')
        self.assertEqual(s.units, [1])
        names = {p.number: p.name for p in s.pins}
        self.assertEqual(len(names), 81)
        self.assertEqual((names['52'], names['77'], names['81'], names['75']), ('GPIO41/ADC1', 'GPIO0', 'GND', '~{QSPI_SS}'))
        self.assertEqual(s.expr[1], 'MCU_RaspberryPi:RP2350B')

    def test_stacked_supply_pins_share_one_end(self):
        s = symlib.lookup('MCU_RaspberryPi:RP2350B')
        ends = {p.end((0, 0), 0) for p in s.pins if p.name == 'IOVDD'}
        self.assertEqual(len(ends), 1)

    def test_a_box_turns_and_mirrors_with_its_symbol(self):
        # Conn_01x04: pins ending at library x -5.08, its body out to x 1.27, and library y from -6.35 to 3.81
        s = symlib.lookup('Connector_Generic:Conn_01x04')
        self.assertEqual(s.box(0), (-5.08, -3.81, 1.27, 6.35))
        self.assertEqual(s.box(90, mirror=True), (-6.35, -1.27, 3.81, 5.08))

    def test_a_four_unit_driver(self):
        s = symlib.lookup('Interface_LineDriver:MC3487N')
        self.assertEqual(s.units, [1, 2, 3, 4])
        self.assertEqual({p.number for p in s.unit_pins(2)}, {'4', '5', '6', '7', '8', '16'})

    def test_a_derived_symbol_is_flattened(self):
        s = symlib.lookup('Regulator_Linear:AP7361C-33E')
        self.assertIsNone(sexp.find(s.expr, 'extends'))
        self.assertEqual({(p.number, p.name) for p in s.pins}, {('1', 'VI'), ('2', 'GND'), ('3', 'VO')})
        self.assertEqual(s.property('Footprint'), 'Package_TO_SOT_SMD:SOT-223-3_TabPin2')
        subs = [str(x[1]) for x in sexp.find_all(s.expr, 'symbol')]
        self.assertTrue(subs and all(n.startswith('AP7361C-33E_') for n in subs), subs)

    def test_pins_in_every_unit(self):
        s = symlib.lookup('Switch:SW_Push')
        self.assertEqual(s.units, [1])
        self.assertEqual({p.number for p in s.unit_pins(1)}, {'1', '2'})

    def test_diode_cathode_is_pin_1(self):
        for lib_id in ('Device:LED', 'Device:D_Zener'):
            s = symlib.lookup(lib_id)
            self.assertEqual([p.number for p in s.pins if p.name == 'K'], ['1'], lib_id)

    def test_pin_ends_and_directions(self):
        # Device:R pin 1 is at (0, 3.81) in the library, pointing down into the body. kicad-cli confirmed on
        # Oct 8 that at rotation 90 it sits on the left.
        (p1,) = [p for p in symlib.lookup('Device:R').pins if p.number == '1']
        self.assertEqual(p1.end((101.6, 101.6), 0), (101.6, 97.79))
        self.assertEqual(p1.end((101.6, 101.6), 90), (97.79, 101.6))
        self.assertEqual([p1.outward(r) for r in (0, 90, 180, 270)], [(0, -1), (-1, 0), (0, 1), (1, 0)])


if __name__ == '__main__':
    unittest.main()
