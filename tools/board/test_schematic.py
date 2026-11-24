# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""schematic: what it writes, read back through kicad-cli."""

import os
import tempfile
import unittest

import netlist
import paths
import sexp
from schematic import Project, Spec

RES = Spec('Device:R', '10k', 'Resistor_SMD:R_0603_1608Metric', lcsc='C25804')
DRV = Spec('Interface_LineDriver:MC3487N', 'DS34LV87TM/NOPB', 'Package_SO:SOIC-16_3.9x9.9mm_P1.27mm', 'DS34LV87TM/NOPB', 'C1543778')
TP = Spec('Connector:TestPoint', 'TP', 'TestPoint:TestPoint_Pad_D1.5mm', bom=False)
CONN = Spec('Connector_Generic:Conn_01x04', 'Conn', 'Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical',
            'header', 'C1')
USB_C = Spec('Connector:USB_C_Receptacle_USB2.0_16P', 'USB-C', 'Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12',
             'TYPE-C-31-M-12', 'C165948')


def build(directory):
    p = Project('t', directory, title='Test', rev='0', date='2026-10-08', company='CoffeeMuse')
    a = p.sheet('a.kicad_sch', 'A', 'Sheet A')
    g = a.group('Passives at every rotation')
    g.add(RES, 'R1', {'1': 'SIG', '2': 'GND'}, dnp=True)
    g.add(RES, 'R2', {'1': 'SIG', '2': 'LOCAL'}, rot=90)
    g.add(RES, 'R4', {'1': 'LOCAL', '2': 'GND'}, rot=180)
    g.add(RES, 'R5', {'1': 'EN', '2': 'GND'}, rot=270)
    g.add(TP, 'TP1', {'1': 'SIG'})
    d = a.group('A four-unit driver')
    d.add(DRV, 'U1', {'1': 'SIG', '7': 'GND', '9': 'GND', '15': 'GND', '4': 'EN', '12': 'GND',
                      '16': '+3V3', '8': 'GND', '2': 'OUTP', '3': 'OUTN'}, nc=['5', '6', '10', '11', '13', '14'])
    d.add(RES, 'R6', {'1': 'OUTP', '2': 'OUTN'})
    a.flag('GND')
    a.flag('+3V3')
    b = p.sheet('b.kicad_sch', 'B', 'Sheet B')
    b.group('Other').add(RES, 'R3', {'1': 'SIG', '2': '+3V3'})
    return p


def drawn(directory, wires=True):
    """A divider drawn as a circuit: R1 over R2, wired, with R3 teed onto their joint and labelled there."""
    p = Project('d', directory, title='Test', rev='0', date='2026-10-09', company='CoffeeMuse')
    a = p.sheet('a.kicad_sch', 'A', 'Sheet A')
    d = a.drawing('A divider, drawn')
    d.add(RES, 'R1', {'1': '+3V3', '2': 'MID'}, at=(0, 0))                 # pins at (0, -3.81) and (0, 3.81)
    d.add(RES, 'R2', {'1': 'MID', '2': 'GND'}, at=(0, 15.24))              # pins at (0, 11.43) and (0, 19.05)
    d.add(RES, 'R3', {'1': 'MID', '2': 'OUT'}, rot=90, at=(12.7, 7.62))    # pins at (8.89, 7.62) and (16.51, 7.62)
    if wires:
        d.wire('R1.2', 'R2.1')
        d.wire('R3.1', (0, 7.62))
        d.label('MID', (5.08, 7.62), 'up')
    a.group('Elsewhere').add(RES, 'R4', {'1': 'OUT', '2': 'GND'})
    a.flag('GND')
    a.flag('+3V3')
    return p


def items(text, kind):
    return sexp.find_all(sexp.parse(text), kind)


@unittest.skipUnless(os.path.exists(paths.KICAD_CLI), 'needs kicad-cli')
class TestDrawn(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.project = drawn(cls.tmp.name)
        cls.project.write()
        cls.schematic = os.path.join(cls.tmp.name, 'd.kicad_sch')
        cls.n = netlist.export(cls.schematic)
        with open(os.path.join(cls.tmp.name, 'a.kicad_sch'), encoding='utf-8') as stream:
            cls.text = stream.read()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_wires_join_the_pins_of_a_net(self):
        self.assertEqual(self.n.on('MID'), {('R1', '2'), ('R2', '1'), ('R3', '1')})
        self.assertEqual(self.n.on('OUT'), {('R3', '2'), ('R4', '1')})

    def test_a_tee_gets_one_junction_and_the_net_one_label(self):
        self.assertEqual(len(items(self.text, 'junction')), 1)
        # MID's one label is the drawing's; the wired pins have none. OUT's two are R3.2's and R4.1's, unwired.
        self.assertEqual(sorted(str(lab[1]) for lab in items(self.text, 'label')), ['MID', 'OUT', 'OUT'])

    def test_erc_is_clean(self):
        bad = [v for v in netlist.erc(self.schematic)
               if v[0] == 'error' or v[1] in ('endpoint_off_grid', 'pin_not_connected', 'label_dangling',
                                              'unconnected_wire_endpoint', 'wire_dangling', 'multiple_net_names')]
        self.assertEqual(bad, [])


@unittest.skipUnless(os.path.exists(paths.KICAD_CLI), 'needs kicad-cli')
class TestTurned(unittest.TestCase):
    def test_each_unit_turns_on_its_own(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project('u', tmp, title='Test', rev='0', date='2026-10-09', company='CoffeeMuse')
            a = p.sheet('a.kicad_sch', 'A', 'Sheet A')
            g = a.group('Units turned four ways')
            g.add(DRV, 'U1', {'1': 'IN', '2': 'P', '3': 'N', '4': '+3V3', '7': 'IN', '6': 'P', '5': 'N', '9': 'GND',
                              '12': 'GND', '15': 'GND', '8': 'GND', '16': '+3V3'}, nc=['10', '11', '13', '14'],
                  rot={1: 180, 2: 0, 3: 90, 4: 270})
            g.add(RES, 'R1', {'1': 'P', '2': 'N'})
            g.add(RES, 'R2', {'1': 'IN', '2': 'GND'})
            a.flag('GND')
            a.flag('+3V3')
            p.write()
            n = netlist.export(os.path.join(tmp, 'u.kicad_sch'))
            with open(os.path.join(tmp, 'a.kicad_sch'), encoding='utf-8') as stream:
                symbols = items(stream.read(), 'symbol')
        self.assertEqual(n.on('P'), {('U1', '2'), ('U1', '6'), ('R1', '1')})
        self.assertEqual(n.on('N'), {('U1', '3'), ('U1', '5'), ('R1', '2')})
        self.assertEqual(n.on('IN'), {('U1', '1'), ('U1', '7'), ('R2', '1')})
        turned = {int(sexp.find(s, 'unit')[1]): int(sexp.find(s, 'at')[3]) for s in symbols
                  if str(sexp.find(s, 'lib_id')[1]) == 'Interface_LineDriver:MC3487N'}
        self.assertEqual(turned, {1: 180, 2: 0, 3: 90, 4: 270})


@unittest.skipUnless(os.path.exists(paths.KICAD_CLI), 'needs kicad-cli')
class TestMirrored(unittest.TestCase):
    def test_a_mirrored_unit_joins_at_every_rotation(self):
        # J1 to J4 are flipped left to right (KiCad's mirror y) at each rotation, every pin on a stub and a label, so
        # a pin reaches its net only if its stub ends where KiCad puts it. J5, mirrored, is wired in a drawing.
        conn = {'1': 'A', '2': 'B', '3': 'C', '4': 'D'}
        with tempfile.TemporaryDirectory() as tmp:
            p = Project('m', tmp, title='Test', rev='0', date='2026-10-09', company='CoffeeMuse')
            a = p.sheet('a.kicad_sch', 'A', 'Sheet A')
            g = a.group('Mirrored at every rotation')
            for (i, rot) in enumerate((0, 90, 180, 270), 1):
                g.add(CONN, f'J{i}', conn, rot=rot, mirror=True)
            d = a.drawing('Mirrored and wired')
            d.add(CONN, 'J5', conn, mirror=True, at=(0, 0))          # pins point right, ending at x 5.08
            d.add(RES, 'R1', {'1': 'A', '2': 'D'}, at=(25.4, 1.27))  # pins at (25.4, -2.54) and (25.4, 5.08)
            d.wire('J5.1', 'R1.1')
            d.wire('J5.4', 'R1.2')
            d.label('A', (15.24, -2.54), 'right')
            d.label('D', (15.24, 5.08), 'right')
            p.write()
            n = netlist.export(os.path.join(tmp, 'm.kicad_sch'))
            with open(os.path.join(tmp, 'a.kicad_sch'), encoding='utf-8') as stream:
                symbols = [s for s in items(stream.read(), 'symbol')
                           if str(sexp.find(s, 'lib_id')[1]) == CONN.lib_id]
        refs = [f'J{i}' for i in range(1, 6)]
        self.assertEqual(n.on('A'), {(ref, '1') for ref in refs} | {('R1', '1')})
        self.assertEqual(n.on('B'), {(ref, '2') for ref in refs})
        self.assertEqual(n.on('C'), {(ref, '3') for ref in refs})
        self.assertEqual(n.on('D'), {(ref, '4') for ref in refs} | {('R1', '2')})
        self.assertEqual([sexp.find(s, 'mirror') for s in symbols], [['mirror', 'y']] * 5)


@unittest.skipUnless(os.path.exists(paths.KICAD_CLI), 'needs kicad-cli')
class TestSplitUnits(unittest.TestCase):
    def test_a_drawing_may_place_some_units_and_a_group_the_rest(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project('s', tmp, title='Test', rev='0', date='2026-10-09', company='CoffeeMuse')
            a = p.sheet('a.kicad_sch', 'A', 'Sheet A')
            d = a.drawing('Channel A, drawn')
            d.add(DRV, 'U1', {'1': 'IN', '2': 'P', '3': 'N', '4': '+3V3', '8': 'GND', '16': '+3V3', '7': 'GND',
                              '9': 'GND', '15': 'GND', '12': 'GND'}, nc=['5', '6', '10', '11', '13', '14'],
                  at={1: (0, 0)})
            d.add(RES, 'R1', {'1': 'N', '2': 'P'}, at=(20.32, 0))       # pins at (20.32, -3.81) and (20.32, 3.81)
            d.wire('U1.3', (20.32, -2.54), 'R1.1')
            d.wire('U1.2', (20.32, 2.54), 'R1.2')
            a.group('The other channels').take('U1', [2, 3, 4])
            a.group('Elsewhere').add(RES, 'R2', {'1': 'IN', '2': 'GND'})
            a.flag('GND')
            a.flag('+3V3')
            p.write()
            n = netlist.export(os.path.join(tmp, 's.kicad_sch'))
            with open(os.path.join(tmp, 'a.kicad_sch'), encoding='utf-8') as stream:
                placed = sorted(int(sexp.find(s, 'unit')[1]) for s in items(stream.read(), 'symbol')
                                if str(sexp.find(s, 'lib_id')[1]) == 'Interface_LineDriver:MC3487N')
        self.assertEqual(placed, [1, 2, 3, 4])
        self.assertEqual(n.on(n.net('U1', '3')), {('U1', '3'), ('R1', '1')})
        self.assertLessEqual({('U1', '7'), ('U1', '9'), ('U1', '15'), ('U1', '12')}, n.on('GND'))

    def test_a_unit_placed_nowhere_or_twice_is_refused(self):
        p = Project('s', '/nonexistent', title='Test', rev='0', date='2026-10-09', company='CoffeeMuse')
        a = p.sheet('a.kicad_sch', 'A', 'Sheet A')
        a.drawing('d').add(DRV, 'U1', {'1': 'IN', '2': 'P', '3': 'N', '4': 'EN', '8': 'GND', '16': '+3V3', '7': 'X',
                                       '9': 'X', '15': 'X', '12': 'X'}, nc=['5', '6', '10', '11', '13', '14'],
                           at={1: (0, 0)})
        g = a.group('g')
        g.take('U1', [2, 3])
        with self.assertRaisesRegex(ValueError, r'U1: unit 4 is placed nowhere'):
            p.render()
        with self.assertRaisesRegex(ValueError, r'U1: unit 2 is placed twice'):
            g.take('U1', [2])

    def test_a_drawing_does_not_take_units(self):
        # A drawing draws only the units it gives a place, so units it took would vanish from the sheet
        p = Project('s', '/nonexistent', title='Test', rev='0', date='2026-10-09', company='CoffeeMuse')
        d = p.sheet('a.kicad_sch', 'A', 'Sheet A').drawing('d')
        d.add(DRV, 'U1', {'1': 'IN', '2': 'P', '3': 'N', '4': 'EN', '8': 'GND', '16': '+3V3', '7': 'X', '9': 'X',
                          '15': 'X', '12': 'X'}, nc=['5', '6', '10', '11', '13', '14'], at={1: (0, 0)})
        with self.assertRaisesRegex(ValueError, r'U1.*ordinary group'):
            d.take('U1', [2, 3, 4])


def stacked(directory, pins=None, vbus='J1.A4'):
    """A USB-C receptacle drawn with one wire on its four stacked VBUS pins (vbus names them) and one on its four GND
    pins."""
    p = Project('k', directory, title='Test', rev='0', date='2026-10-09', company='CoffeeMuse')
    a = p.sheet('a.kicad_sch', 'A', 'Sheet A')
    d = a.drawing('Stacked pins, drawn')
    d.add(USB_C, 'J1', pins or {'VBUS': 'VBUS', 'GND': 'GND', 'SHIELD': 'GND', 'CC1': 'CC1', 'CC2': 'CC2',
                                'D+': 'DP', 'D-': 'DM'}, nc=['SBU1', 'SBU2'], at=(0, 0))   # VBUS at (15.24, -15.24)
    d.add(RES, 'R1', {'1': 'VBUS', '2': 'LOAD'}, rot=90, at=(25.4, -15.24))  # pins at (21.59, -15.24) and (29.21, -15.24)
    d.wire(vbus, 'R1.1')
    d.label('VBUS', (17.78, -15.24), 'up')
    d.wire('J1.A1', (0, 25.4))                                              # the GND pins end at (0, 22.86)
    d.label('GND', (0, 25.4), 'down')
    g = a.group('Elsewhere')
    for (i, net) in enumerate(('LOAD', 'CC1', 'CC2', 'DP', 'DM'), 2):
        g.add(RES, f'R{i}', {'1': net, '2': 'GND'})
    a.flag('GND')
    a.flag('VBUS')
    return p


@unittest.skipUnless(os.path.exists(paths.KICAD_CLI), 'needs kicad-cli')
class TestStacked(unittest.TestCase):
    def test_a_wire_on_one_stacked_pin_takes_them_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            stacked(tmp).write()
            n = netlist.export(os.path.join(tmp, 'k.kicad_sch'))
            bad = [v for v in netlist.erc(os.path.join(tmp, 'k.kicad_sch'))
                   if v[0] == 'error' or v[1] in ('pin_not_connected', 'unconnected_wire_endpoint', 'wire_dangling')]
            with open(os.path.join(tmp, 'a.kicad_sch'), encoding='utf-8') as stream:
                text = stream.read()
        self.assertEqual(n.on('VBUS'), {('J1', 'A4'), ('J1', 'A9'), ('J1', 'B4'), ('J1', 'B9'), ('R1', '1')})
        self.assertLessEqual({('J1', 'A1'), ('J1', 'A12'), ('J1', 'B1'), ('J1', 'B12')}, n.on('GND'))
        self.assertEqual(items(text, 'junction'), [])          # one wire on a stack of pins is no tee
        self.assertEqual(bad, [])

    def test_a_wire_may_name_a_pin(self):
        # VBUS is the name of four pins stacked on one end, so naming it wires all four
        with tempfile.TemporaryDirectory() as tmp:
            stacked(tmp, vbus='J1.VBUS').write()
            n = netlist.export(os.path.join(tmp, 'k.kicad_sch'))
        self.assertEqual(n.on('VBUS'), {('J1', 'A4'), ('J1', 'A9'), ('J1', 'B4'), ('J1', 'B9'), ('R1', '1')})

    def test_a_stacked_pin_on_another_net_is_refused(self):
        p = stacked('/nonexistent', {'A4': 'VBUS', 'A9': 'VBUS', 'B4': 'VBUS', 'B9': 'VBUS2', 'GND': 'GND',
                                     'SHIELD': 'GND', 'CC1': 'CC1', 'CC2': 'CC2', 'D+': 'DP', 'D-': 'DM'})
        with self.assertRaisesRegex(ValueError, r'J1\.B9.*stacked.*VBUS2'):
            p.render()


class TestTexts(unittest.TestCase):
    def test_a_turned_symbols_texts_still_read_across(self):
        # KiCad draws a field at angle 0 upright on a symbol turned 90 or 270 degrees only if the file stores 90,
        # and mirrors a field's justification on a symbol turned 180 (seen on its plots, Oct 9, 2026).
        p = Project('t', '/nonexistent', title='T', rev='0', date='2026-10-09', company='CoffeeMuse')
        g = p.sheet('a.kicad_sch', 'A', '').group('g')
        for (i, rot) in enumerate((0, 90, 180, 270)):
            g.add(RES, f'R{i + 1}', {'1': 'A', '2': 'B'}, rot=rot)
        fields = {}
        for symbol in items(p.render()['a.kicad_sch'], 'symbol'):
            if str(sexp.find(symbol, 'lib_id')[1]) == 'Device:R':
                ref = next(f for f in sexp.find_all(symbol, 'property') if str(f[1]) == 'Reference')
                justify = sexp.find(sexp.find(ref, 'effects'), 'justify')
                fields[int(sexp.find(symbol, 'at')[3])] = (int(sexp.find(ref, 'at')[3]),
                                                          [str(j) for j in justify[1:]] if justify else [])
        self.assertEqual({rot: angle for (rot, (angle, _)) in fields.items()}, {0: 0, 90: 90, 180: 0, 270: 90})
        self.assertEqual(fields[0][1], ['left'])                # beside the body, reading away from it
        self.assertEqual(fields[180][1], ['right'])             # stored mirrored, so it shows as left

    def test_a_mirrored_symbols_texts_still_read_as_meant(self):
        # On a mirrored symbol KiCad shows a field's justification flipped left to right, on top of what the
        # rotation does (seen on its plots, Oct 9, 2026), so the file stores it flipped.
        p = Project('t', '/nonexistent', title='T', rev='0', date='2026-10-09', company='CoffeeMuse')
        g = p.sheet('a.kicad_sch', 'A', '').group('g')
        for (i, rot) in enumerate((0, 90, 180, 270)):
            g.add(RES, f'R{i + 1}', {'1': 'A', '2': 'B'}, rot=rot, mirror=True)
        g.add(CONN, 'J1', {'1': 'A', '2': 'B', '3': 'GND', '4': '+3V3'}, mirror=True)
        fields = {}
        for symbol in items(p.render()['a.kicad_sch'], 'symbol'):
            if str(sexp.find(symbol, 'lib_id')[1]) in ('Device:R', CONN.lib_id):
                ref = next(f for f in sexp.find_all(symbol, 'property') if str(f[1]) == 'Reference')
                justify = sexp.find(sexp.find(ref, 'effects'), 'justify')
                key = (str(sexp.find(symbol, 'lib_id')[1]), int(sexp.find(symbol, 'at')[3]))
                fields[key] = (int(sexp.find(ref, 'at')[3]), [str(j) for j in justify[1:]] if justify else [])
        self.assertEqual({rot: angle for ((lib, rot), (angle, _)) in fields.items() if lib == 'Device:R'},
                         {0: 0, 90: 90, 180: 0, 270: 90})
        self.assertEqual(fields[('Device:R', 0)][1], ['right'])     # beside the body: shows as left
        self.assertEqual(fields[('Device:R', 180)][1], ['left'])    # the turn and the mirror cancel
        self.assertEqual(fields[(CONN.lib_id, 0)][1], [])             # above and below it, centred

    def test_a_sideways_power_symbols_name_reads_away_from_it(self):
        # J1's pins point left, so GND (turned 270) and +3V3 (turned 90) hang off them pointing left. Each name must
        # start past its symbol's graphic and run left, so it shows justified right. KiCad shows a field mirrored on
        # a symbol turned 90, so +3V3's is stored left (seen on its plots, Oct 9, 2026).
        p = Project('t', '/nonexistent', title='T', rev='0', date='2026-10-09', company='CoffeeMuse')
        p.sheet('a.kicad_sch', 'A', '').group('g').add(CONN, 'J1', {'1': 'A', '2': 'B', '3': 'GND', '4': '+3V3'})
        stored = {}
        for symbol in items(p.render()['a.kicad_sch'], 'symbol'):
            lib = str(sexp.find(symbol, 'lib_id')[1])
            if lib.startswith('power:'):
                tip = float(sexp.find(symbol, 'at')[1])
                value = next(f for f in sexp.find_all(symbol, 'property') if str(f[1]) == 'Value')
                self.assertLess(float(sexp.find(value, 'at')[1]), tip - 2.54, lib)
                justify = sexp.find(sexp.find(value, 'effects'), 'justify')
                stored[lib] = (int(sexp.find(symbol, 'at')[3]), [str(j) for j in justify[1:]] if justify else [])
        self.assertEqual(stored, {'power:GND': (270, ['right']), 'power:+3V3': (90, ['left'])})

class TestRoom(unittest.TestCase):
    """A unit's or a drawing's box, which keeps groups apart on the sheet, holds every name it shows."""

    def test_a_sideways_power_name_is_inside_its_units_box(self):
        # J1's pins point left, so GND (pin 3, on a 2.54 mm stub) and +3V3 (pin 4, on a 7.62 mm one) hang off them
        # pointing left. A name starts 3.175 mm past its symbol's point and runs about 1.3 mm a character further:
        # +3V3's ends 5.08 + 7.62 + 3.175 + 4 * 1.3 = 21.075 mm left of J1's origin.
        p = Project('t', '/nonexistent', title='T', rev='0', date='2026-10-09', company='CoffeeMuse')
        a = p.sheet('a.kicad_sch', 'A', '')
        j1 = a.group('g').add(CONN, 'J1', {'1': 'A', '2': 'B', '3': 'GND', '4': '+3V3'})
        self.assertLessEqual(a._extent(j1, 1)[0], -21.075)

    def test_a_drawings_sideways_power_name_is_inside_its_box(self):
        # +3V3 hangs left off the drawing's leftmost point, so its name, 3.175 + 4 * 1.3 = 8.375 mm long, is the
        # drawing's left edge, which sits on the sheet's 25.4 mm margin.
        p = Project('t', '/nonexistent', title='T', rev='0', date='2026-10-09', company='CoffeeMuse')
        a = p.sheet('a.kicad_sch', 'A', '')
        d = a.drawing('d')
        d.add(RES, 'R1', {'1': '+3V3', '2': 'GND'}, rot=90, at=(0, 0))      # pins at (-3.81, 0) and (3.81, 0)
        d.wire('R1.1', (-6.35, 0))
        d.label('+3V3', (-6.35, 0), 'left')
        d.wire('R1.2', (6.35, 0))
        d.label('GND', (6.35, 0), 'down')
        (symbol,) = [s for s in items(p.render()['a.kicad_sch'], 'symbol')
                     if str(sexp.find(s, 'lib_id')[1]) == 'power:+3V3']
        value = next(f for f in sexp.find_all(symbol, 'property') if str(f[1]) == 'Value')
        self.assertGreaterEqual(float(sexp.find(value, 'at')[1]) - 4 * 1.3, 25.4)


class TestDrawnRules(unittest.TestCase):
    def setUp(self):
        self.p = drawn('/nonexistent', wires=False)
        self.d = self.p.sheets[0].groups[0]

    def test_a_wire_between_two_nets_is_refused(self):
        self.d.wire('R1.1', (5.08, -3.81), (5.08, 3.81), 'R1.2')
        with self.assertRaisesRegex(ValueError, r'joins \+3V3 and MID'):
            self.p.render()

    def test_a_wire_over_a_stray_pin_is_refused(self):
        self.d.wire('R1.2', (0, 7.62), 'R3.1')                  # the run from R1.2 down passes nothing, then
        self.d.wire('R3.1', (8.89, 19.05), (0, 19.05))          # this one ends on R2.2, a GND pin
        with self.assertRaisesRegex(ValueError, r'R2\.2'):
            self.p.render()

    def test_a_stub_on_another_pins_end_is_refused(self):
        # R5.2 ends on the tip of R1.1's stub, and its own stub runs back to R1.1's end: KiCad joins Y to +3V3
        self.d.add(RES, 'R5', {'1': 'X', '2': 'Y'}, at=(0, -10.16))
        with self.assertRaisesRegex(ValueError, r'R1\.1 and R5\.2 touch'):
            self.p.render()

    def test_a_wire_ending_on_a_stub_is_refused(self):
        # OUT turns left and ends half-way along R1.1's stub. KiCad joins a tee only at a junction, but it reads as one.
        self.d.wire('R3.2', (16.51, -5.08), (0, -5.08))
        self.d.label('OUT', (8.89, -5.08), 'up')
        with self.assertRaisesRegex(ValueError, r'wire of OUT touches R1\.1'):
            self.p.render()

    def test_a_span_two_runs_share_is_drawn_once(self):
        # Both runs cover R1.2 to R2.1, the second the other way. Written twice, every point where the span splits
        # (the pins, the tee, the label) would count three ends or more and get a junction.
        self.d.wire('R1.2', 'R2.1')
        self.d.wire('R2.1', 'R1.2')
        self.d.wire('R3.1', (0, 7.62))
        self.d.label('MID', (0, 5.08), 'left')
        text = self.p.render()['a.kicad_sch']
        spans = [frozenset(tuple(float(v) for v in xy[1:]) for xy in sexp.find(w, 'pts')[1:])
                 for w in items(text, 'wire')]
        self.assertEqual(len(spans), len(set(spans)))
        self.assertEqual(len(items(text, 'junction')), 1)           # the tee's, where R3 meets the divider

    def test_a_pin_name_on_pins_apart_is_refused(self):
        # USB-C's D+ is A6 and B6, which end apart, so the name alone doesn't say where the wire goes
        p = stacked('/nonexistent', vbus='J1.D+')
        with self.assertRaisesRegex(ValueError, r'J1\.D\+ is pins A6, B6'):
            p.render()

    def test_a_wire_to_a_missing_pin_is_refused(self):
        self.d.wire('R3.3', (21.59, 7.62))
        with self.assertRaisesRegex(ValueError, r"R3 .*has no pin '3'"):
            self.p.render()

    def test_a_sheets_drawings_need_their_own_titles(self):
        # A drawing's wires, junctions and labels take their UUIDs from its title, so two of one title would share them
        with self.assertRaisesRegex(ValueError, r"'A divider, drawn'"):
            self.p.sheets[0].drawing('A divider, drawn')

    def test_a_wired_net_that_leaves_the_drawing_needs_a_name(self):
        self.d.wire('R3.2', (21.59, 7.62))                      # OUT reaches R4 elsewhere, but has no label here
        with self.assertRaisesRegex(ValueError, r'OUT.*label'):
            self.p.render()

    def test_every_unit_needs_a_place_on_the_grid(self):
        with self.assertRaisesRegex(ValueError, r'R9'):
            self.d.add(RES, 'R9', {'1': 'X', '2': 'Y'}, at=(1.0, 0))


@unittest.skipUnless(os.path.exists(paths.KICAD_CLI), 'needs kicad-cli')
class TestWritten(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.project = build(cls.tmp.name)
        cls.files = cls.project.write()
        cls.schematic = os.path.join(cls.tmp.name, 't.kicad_sch')
        cls.n = netlist.export(cls.schematic)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_files(self):
        self.assertEqual(self.files, ['a.kicad_sch', 'b.kicad_sch', 't.kicad_sch'])
        self.assertTrue(os.path.exists(os.path.join(self.tmp.name, 't.kicad_pro')))

    def test_a_net_across_sheets_is_one_net(self):
        self.assertEqual(self.n.on('SIG'), {('R1', '1'), ('R2', '1'), ('U1', '1'), ('R3', '1'), ('TP1', '1')})

    def test_rotations_and_local_nets(self):
        self.assertEqual(self.n.on('LOCAL'), {('R2', '2'), ('R4', '1')})
        self.assertEqual(self.n.on('EN'), {('R5', '1'), ('U1', '4')})
        self.assertLessEqual({('R1', '2'), ('R4', '2'), ('R5', '2'), ('U1', '8'), ('U1', '12')}, self.n.on('GND'))
        self.assertLessEqual({('U1', '16'), ('R3', '2')}, self.n.on('+3V3'))

    def test_no_connects_are_alone(self):
        for pin in ('5', '6', '10', '11', '13', '14'):
            self.assertIsNone(self.n.net('U1', pin))

    def test_fields_fitting_and_bom(self):
        self.assertTrue(self.n.parts['R1'].dnp)
        self.assertFalse(self.n.parts['R2'].dnp)
        self.assertEqual(self.n.parts['U1'].fields['LCSC'], 'C1543778')
        self.assertEqual(self.n.parts['U1'].fields['MPN'], 'DS34LV87TM/NOPB')
        self.assertFalse(self.n.parts['TP1'].in_bom)
        self.assertTrue(self.n.parts['R2'].in_bom)

    def test_erc_is_clean(self):
        bad = [v for v in netlist.erc(self.schematic)
               if v[0] == 'error' or v[1] in ('endpoint_off_grid', 'pin_not_connected', 'label_dangling',
                                              'isolated_pin_label', 'global_label_dangling', 'multiple_net_names',
                                              'unconnected_wire_endpoint', 'wire_dangling', 'single_global_label')]
        self.assertEqual(bad, [])


class TestRules(unittest.TestCase):
    def test_an_unassigned_pin_is_refused(self):
        p = Project('t', '/nonexistent', title='T', rev='0', date='2026-10-08', company='CoffeeMuse')
        p.sheet('a.kicad_sch', 'A', '').group('g').add(RES, 'R7', {'1': 'X'})
        with self.assertRaisesRegex(ValueError, r'R7: pins 2 '):
            p.render()

    def test_a_pin_on_two_nets_is_refused(self):
        p = Project('t', '/nonexistent', title='T', rev='0', date='2026-10-08', company='CoffeeMuse')
        s = p.sheet('a.kicad_sch', 'A', '')
        s.group('g').add(RES, 'R7', {'1': 'X', '2': 'Y'})
        with self.assertRaises(ValueError):
            s.connect('R7', '1', 'Z')

    def test_a_reference_used_twice_is_refused(self):
        p = Project('t', '/nonexistent', title='T', rev='0', date='2026-10-08', company='CoffeeMuse')
        g = p.sheet('a.kicad_sch', 'A', '').group('g')
        g.add(RES, 'R7', {'1': 'X', '2': 'Y'})
        with self.assertRaises(ValueError):
            g.add(RES, 'R7', {'1': 'X', '2': 'Y'})

    def test_the_same_description_gives_the_same_files(self):
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            self.assertEqual(build(one).render(), build(two).render())

    def test_neighbours_wires_alternate_short_and_long(self):
        p = Project('t', '/nonexistent', title='T', rev='0', date='2026-10-08', company='CoffeeMuse')
        g = p.sheet('a.kicad_sch', 'A', '').group('g')
        g.add(CONN, 'J1', {'1': 'A', '2': 'B', '3': 'GND', '4': '+3V3'})   # four pins down one side, 2.54 mm apart
        sheet = sexp.parse(p.render()['a.kicad_sch'])
        wires = []
        for wire in sexp.find_all(sheet, 'wire'):
            (x0, y0), (x1, y1) = [(float(xy[1]), float(xy[2])) for xy in sexp.find_all(sexp.find(wire, 'pts'), 'xy')]
            self.assertEqual(y0, y1)                                     # all four leave sideways
            wires.append((y0, round(abs(x1 - x0), 4)))
        self.assertEqual([length for (_, length) in sorted(wires)], [2.54, 7.62, 2.54, 7.62])

    def test_stale_lists_what_differs(self):
        with tempfile.TemporaryDirectory() as tmp:
            build(tmp).write()
            self.assertEqual(build(tmp).stale(), [])
            with open(os.path.join(tmp, 'b.kicad_sch'), 'a', encoding='utf-8') as stream:
                stream.write('\n')
            self.assertEqual(build(tmp).stale(), ['b.kicad_sch'])

    def test_stale_lists_a_sheet_no_module_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            build(tmp).write()
            with open(os.path.join(tmp, 'old.kicad_sch'), 'w', encoding='utf-8') as stream:
                stream.write('(kicad_sch)\n')
            self.assertEqual(build(tmp).stale(), ['old.kicad_sch'])


if __name__ == '__main__':
    unittest.main()
