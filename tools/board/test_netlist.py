# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""netlist: what kicad-cli says about a schematic. The fixture is the Oct 8, 2026 spike that kicad-cli read:
R1 (10k, LCSC C25804, not fitted) at rotation 90, pin 1 on global label SIG and pin 2 on GND, on a sheet of its own."""

import os
import tempfile
import unittest

import netlist
import paths
import sexp
import symlib
from sexp import Q

ROOT = '11111111-1111-4111-8111-111111111111'
SUB = '22222222-2222-4222-8222-222222222222'
SHEET = '33333333-3333-4333-8333-333333333333'


def _u(n):
    return Q(f'00000000-0000-4000-8000-{n:012d}')


def _font(hidden=False):
    return ['effects', ['font', ['size', 1.27, 1.27]]] + ([['hide', 'yes']] if hidden else [])


def _props(ref, value, x, y, footprint='', lcsc=None):
    out = [['property', Q('Reference'), Q(ref), ['at', x, y - 5.08, 0], _font(ref.startswith('#'))],
           ['property', Q('Value'), Q(value), ['at', x, y + 5.08, 0], _font()],
           ['property', Q('Footprint'), Q(footprint), ['at', x, y, 0], _font(True)]]
    if lcsc:
        out.append(['property', Q('LCSC'), Q(lcsc), ['at', x, y, 0], _font(True)])
    return out


def write_spike(directory):
    r, gnd = symlib.lookup('Device:R'), symlib.lookup('power:GND')
    path = ['path', Q(f'/{ROOT}/{SHEET}')]
    head = ['version', 20250114], ['generator', Q('eeschema')], ['generator_version', Q('9.0')]
    sub = ['kicad_sch', *head, ['uuid', Q(SUB)], ['paper', Q('A4')], ['lib_symbols', r.expr, gnd.expr],
           ['symbol', ['lib_id', Q('Device:R')], ['at', 101.6, 101.6, 90], ['unit', 1], ['exclude_from_sim', 'no'],
            ['in_bom', 'yes'], ['on_board', 'yes'], ['dnp', 'yes'], ['uuid', _u(1)],
            *_props('R1', '10k', 101.6, 101.6, 'Resistor_SMD:R_0603_1608Metric', 'C25804'),
            ['pin', Q('1'), ['uuid', _u(2)]], ['pin', Q('2'), ['uuid', _u(3)]],
            ['instances', ['project', Q('spike'), path + [['reference', Q('R1')], ['unit', 1]]]]],
           ['wire', ['pts', ['xy', 97.79, 101.6], ['xy', 95.25, 101.6]], ['stroke', ['width', 0], ['type', 'default']],
            ['uuid', _u(4)]],
           ['global_label', Q('SIG'), ['shape', 'bidirectional'], ['at', 95.25, 101.6, 180],
            ['effects', ['font', ['size', 1.27, 1.27]], ['justify', 'right']], ['uuid', _u(5)]],
           ['wire', ['pts', ['xy', 105.41, 101.6], ['xy', 107.95, 101.6]], ['stroke', ['width', 0], ['type', 'default']],
            ['uuid', _u(6)]],
           ['symbol', ['lib_id', Q('power:GND')], ['at', 107.95, 101.6, 90], ['unit', 1], ['exclude_from_sim', 'no'],
            ['in_bom', 'yes'], ['on_board', 'yes'], ['dnp', 'no'], ['uuid', _u(7)],
            *_props('#PWR01', 'GND', 107.95, 101.6),
            ['pin', Q('1'), ['uuid', _u(8)]],
            ['instances', ['project', Q('spike'), path + [['reference', Q('#PWR01')], ['unit', 1]]]]],
           ['embedded_fonts', 'no']]
    root = ['kicad_sch', *head, ['uuid', Q(ROOT)], ['paper', Q('A4')], ['lib_symbols'],
            ['sheet', ['at', 50.8, 50.8], ['size', 30.48, 20.32], ['exclude_from_sim', 'no'], ['in_bom', 'yes'],
             ['on_board', 'yes'], ['dnp', 'no'], ['stroke', ['width', 0.1524], ['type', 'solid']],
             ['fill', ['color', 0, 0, 0, 0.0]], ['uuid', Q(SHEET)],
             ['property', Q('Sheetname'), Q('Sub'), ['at', 50.8, 49.53, 0], _font()],
             ['property', Q('Sheetfile'), Q('sub.kicad_sch'), ['at', 50.8, 72.39, 0], _font()],
             ['instances', ['project', Q('spike'), ['path', Q(f'/{ROOT}'), ['page', Q('2')]]]]],
            ['sheet_instances', ['path', Q('/'), ['page', Q('1')]]], ['embedded_fonts', 'no']]
    for (name, expr) in (('spike.kicad_sch', root), ('sub.kicad_sch', sub)):
        with open(os.path.join(directory, name), 'w', encoding='utf-8') as stream:
            stream.write(sexp.dump(expr) + '\n')
    with open(os.path.join(directory, 'spike.kicad_pro'), 'w', encoding='utf-8') as stream:
        stream.write('{"meta": {"filename": "spike.kicad_pro", "version": 3}}\n')
    return os.path.join(directory, 'spike.kicad_sch')


class TestShort(unittest.TestCase):
    def test_names(self):
        self.assertEqual(netlist.short('/Coax/RX_P'), 'RX_P')
        self.assertEqual(netlist.short('+3V3'), '+3V3')
        self.assertIsNone(netlist.short('unconnected-(U1-GPIO0-Pad77)'))


class TestBoardNames(unittest.TestCase):
    def test_kicad_keeps_the_slash_in_a_pin_name(self):
        self.assertEqual(netlist.kicad_name('unconnected-(U1-GPIO40/ADC0-Pad49)'),
                         'unconnected-(U1-GPIO40{slash}ADC0-Pad49)')
        self.assertEqual(netlist.kicad_name('/Coax/LINE_C'), '/Coax/LINE_C')

    def test_leaf(self):
        self.assertEqual(netlist.leaf('/Coax/LINE_C'), 'LINE_C')
        self.assertEqual(netlist.leaf('+3V3'), '+3V3')
        self.assertEqual(netlist.leaf('Net-(U1-USB_DM)'), 'Net-(U1-USB_DM)')


class TestMerge(unittest.TestCase):
    def test_two_nets_with_one_short_name_are_refused(self):
        with self.assertRaises(ValueError):
            netlist._merge([('/A/SIG', {('R1', '1')}), ('/B/SIG', {('R2', '1')})])

    def test_unconnected_pins_are_dropped(self):
        self.assertEqual(netlist._merge([('SIG', {('R1', '1')}), ('unconnected-(R9-Pad1)', {('R9', '1')})]),
                         {'SIG': {('R1', '1')}})


@unittest.skipUnless(os.path.exists(paths.KICAD_CLI), 'needs kicad-cli')
class TestSpike(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.schematic = write_spike(cls.tmp.name)
        cls.n = netlist.export(cls.schematic)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_parts(self):
        self.assertEqual(set(self.n.parts), {'R1'})          # power symbols aren't parts
        r1 = self.n.parts['R1']
        self.assertEqual((r1.value, r1.footprint, r1.fields['LCSC']), ('10k', 'Resistor_SMD:R_0603_1608Metric', 'C25804'))
        self.assertTrue(r1.dnp)
        self.assertTrue(r1.in_bom)

    def test_nets(self):
        self.assertEqual(self.n.net('R1', '1'), 'SIG')
        self.assertEqual(self.n.net('R1', '2'), 'GND')
        self.assertEqual(self.n.on('SIG'), {('R1', '1')})

    def test_erc_reports_the_undriven_ground(self):
        types = {v[1] for v in netlist.erc(self.schematic) if v[0] == 'error'}
        self.assertIn('power_pin_not_driven', types)


if __name__ == '__main__':
    unittest.main()
