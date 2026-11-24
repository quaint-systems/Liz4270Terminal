# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The board against its design (#90) and its floorplan.

The board file is read as KiCad wrote it (pcbfile) and checked by kicad-cli's DRC with schematic parity. As in
test_board.py, the tables here restate the spec and the floorplan on purpose instead of importing layout.py: a slip in
the layout must not slip past its test.
"""

import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

import footprint
import netlist
import paths
import pcb

PCB = os.path.join(paths.BOARD, 'liz4270.kicad_pcb')
HAVE = os.path.exists(paths.KICAD_CLI) and os.path.exists(paths.KICAD_PYTHON) and os.path.exists(PCB)
WIDTH, HEIGHT = 100.0, 80.0
_cache = {}


def board():
    if 'board' not in _cache:
        import pcbfile                                      # Task 4
        _cache['board'] = pcbfile.Board(PCB)
    return _cache['board']


def drc():
    if 'drc' not in _cache:
        _cache['drc'] = netlist.drc(PCB)
    return _cache['drc']


def filled():
    """The board with its zones filled, read back: kicad-cli fills a scratch copy (the file keeps them unfilled)."""
    if 'filled' not in _cache:
        import pcbfile
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('liz4270.kicad_pcb', 'liz4270.kicad_pro', 'liz4270.kicad_dru'):
                shutil.copy(os.path.join(paths.BOARD, name), tmp)
            board_file = os.path.join(tmp, 'liz4270.kicad_pcb')
            subprocess.run([paths.KICAD_CLI, 'pcb', 'drc', '--refill-zones', '--save-board', '-o',
                            os.path.join(tmp, 'drc.rpt'), board_file], check=True, capture_output=True)
            _cache['filled'] = pcbfile.Board(board_file)
    return _cache['filled']


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def xy(pad):
    return (pad.x, pad.y)


def pad_box(part, pad):
    """The pad's extent on the board, (x0, y0, x1, y1), for a part turned by a multiple of 90 degrees."""
    (w, h) = (pad.h, pad.w) if part.rot % 180 else (pad.w, pad.h)
    return (pad.x - w / 2, pad.y - h / 2, pad.x + w / 2, pad.y + h / 2)


def pad_of(name):
    (ref, number) = name.split('.', 1)
    return board().pad(ref, number)


# DRC errors a placement can cause; routing's own (unconnected items) come later
PLACEMENT = {'courtyards_overlap', 'pth_inside_courtyard', 'npth_inside_courtyard', 'copper_edge_clearance',
             'shorting_items', 'hole_clearance', 'hole_to_hole', 'clearance', 'solder_mask_bridge',
             'malformed_courtyard', 'invalid_outline'}


def placement_errors():
    """Placement errors that involve no part still parked below the board."""
    parked = {ref for (ref, p) in board().parts.items() if p.y > HEIGHT + 1}
    out = []
    for v in drc()[0]:
        if v[0] != 'error' or v[1] not in PLACEMENT:
            continue
        refs = set(re.findall(r'(?:of |Footprint )([A-Z]+\d+)', ' '.join(v[3])))
        if not refs & parked:
            out.append(v)
    return out


@unittest.skipUnless(HAVE, 'needs KiCad 10 and hardware/board/liz4270.kicad_pcb')
class TestBuild(unittest.TestCase):
    def test_the_board_is_what_the_generator_writes(self):
        result = subprocess.run([sys.executable, os.path.join(paths.HERE, 'build_board.py'), '--check'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_parity_with_the_schematic(self):
        self.assertEqual(drc()[2], [])

    def test_stackup_is_jlc04161h_7628(self):
        with open(PCB, encoding='utf-8') as stream:
            text = stream.read()
        for needle in ('"In1.Cu" power "GND"', '"In2.Cu" power "+3V3"', '(thickness 0.2104)', '(epsilon_r 4.4)',
                       '(thickness 1.065)', '(thickness 0.0152)'):
            self.assertIn(needle, text)

    def test_net_classes(self):
        with open(os.path.join(paths.BOARD, 'liz4270.kicad_pro'), encoding='utf-8') as stream:
            classes = {c['name']: c for c in json.load(stream)['net_settings']['classes']}
        self.assertEqual((classes['TMDS']['diff_pair_width'], classes['TMDS']['diff_pair_gap']), (0.225, 0.2))
        self.assertEqual((classes['USB']['diff_pair_width'], classes['USB']['diff_pair_gap']), (0.25, 0.15))
        self.assertIn('CoaxLine', classes)

    def test_a_pairs_own_gap_keeps_its_class_clearance(self):
        """KiCad holds a pair's two lines to their class's clearance too, so a clearance above the pair's gap fails
        DRC along every pair."""
        with open(os.path.join(paths.BOARD, 'liz4270.kicad_pro'), encoding='utf-8') as stream:
            classes = {c['name']: c for c in json.load(stream)['net_settings']['classes']}
        for name in ('TMDS', 'USB'):
            self.assertLessEqual(classes[name]['clearance'], classes[name]['diff_pair_gap'], name)

    def test_the_isolation_rule(self):
        with open(os.path.join(paths.BOARD, 'liz4270.kicad_dru'), encoding='utf-8') as stream:
            self.assertIn("(constraint clearance (min 1.5mm))", stream.read())

    def test_each_net_in_its_class(self):
        """Which class KiCad puts each net in: a pattern that misses a sheet's prefix leaves its nets in Default."""
        script = ('import pcbnew, sys\n'
                  'b = pcbnew.LoadBoard(sys.argv[1])\n'
                  'for (name, net) in b.GetNetsByName().items():\n'
                  '    print(str(name) + "|" + net.GetNetClassName())\n')
        out = subprocess.run([paths.KICAD_PYTHON, '-c', script, PCB], capture_output=True, text=True).stdout
        classes = {netlist.leaf(name): cls for (name, cls) in (line.split('|') for line in out.splitlines() if line)}
        want = {
            'TMDS': ['HSTX_CKP', 'HSTX_CKN', 'HSTX_D0P', 'HSTX_D2N', 'HDMI_CKP', 'HDMI_CKN', 'HDMI_D0P', 'HDMI_D0N',
                     'HDMI_D1P', 'HDMI_D1N', 'HDMI_D2P', 'HDMI_D2N'],
            'USB': ['USBC_DP', 'USBC_DM', 'USBH_DP', 'USBH_DM', 'USBA1_DP', 'USBA1_DM', 'USBA2_DP', 'USBA2_DM',
                    'Net-(U1-USB_DP)', 'Net-(U1-USB_DM)'],
            'CoaxLine': ['LINE_C', 'LINE_S'],
            'Power': ['GND', '+5V', '+3V3', '+1V1', '+1V8', 'VBUS', 'VBUS_F', 'USBH_5V', 'HDMI_5V', 'VREG_LX'],
            'Default': ['COAX_RX', 'I2C_SDA', 'QSPI_SCLK'],
        }
        for (cls, nets) in want.items():
            for net in nets:
                self.assertEqual(classes.get(net), cls, net)


@unittest.skipUnless(HAVE, 'needs KiCad 10 and hardware/board/liz4270.kicad_pcb')
class TestRead(unittest.TestCase):
    def test_every_part_once_with_its_footprint_and_fitting(self):
        nl = netlist.export(os.path.join(paths.BOARD, 'liz4270.kicad_sch'))
        self.assertEqual(sorted(board().parts), sorted(nl.parts))
        for (ref, part) in nl.parts.items():
            self.assertEqual(board().parts[ref].fpid, part.footprint, ref)
            self.assertEqual(board().parts[ref].dnp, part.dnp, ref)

    def test_pads_where_kicad_has_them(self):
        """pcbfile turns each pad as KiCad does: KiCad's own Python lists every pad's centre to compare."""
        script = ('import pcbnew, sys\n'
                  'b = pcbnew.LoadBoard(sys.argv[1])\n'
                  'for fp in b.GetFootprints():\n'
                  '    for p in fp.Pads():\n'
                  '        q = p.GetPosition()\n'
                  '        print("|".join((fp.GetReference(), p.GetNumber(), str(pcbnew.ToMM(q.x)), str(pcbnew.ToMM(q.y)))))\n')
        out = subprocess.run([paths.KICAD_PYTHON, '-c', script, PCB], capture_output=True, text=True).stdout
        import pcb
        seen = 0
        for line in out.splitlines():
            (ref, number, x, y) = line.split('|')                # a mechanical pad's number is empty
            mine = [p for p in board().parts[ref].pads if p.number == number]
            here = (float(x) - pcb.ORIGIN[0], float(y) - pcb.ORIGIN[1])
            self.assertTrue(any(distance((p.x, p.y), here) < 1e-3 for p in mine), (ref, number, here))
            seen += 1
        self.assertGreater(seen, 600)

    def test_the_outline(self):
        self.assertEqual(board().outline(), (0.0, 0.0, WIDTH, HEIGHT))


@unittest.skipUnless(HAVE, 'needs KiCad 10 and hardware/board/liz4270.kicad_pcb')
class TestModels(unittest.TestCase):
    def test_every_fitted_part_has_a_model_that_exists(self):
        stock = os.path.join(paths.KICAD, 'Contents', 'SharedSupport', '3dmodels')
        bare = ('MountingHole:', 'TestPoint:')                  # holes and pads in the board have no body
        for part in board().parts.values():
            if part.fpid.startswith(bare):
                continue
            self.assertTrue(part.models, part.ref)
            for model in part.models:
                self.assertFalse(model.startswith('kicad-embed://'), f'{part.ref}: {model} has no data with it')
                path = (model.replace('${KICAD10_3DMODEL_DIR}', stock).replace('${KIPRJMOD}', paths.BOARD))
                self.assertTrue(os.path.exists(path), f'{part.ref}: {model}')

    def test_the_models_are_what_make_models_writes(self):
        if not os.path.exists(paths.FREECAD_CMD):
            self.skipTest('needs FreeCAD')
        result = subprocess.run([sys.executable, os.path.join(paths.HERE, 'make_models.py'), '--check'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


# ref -> its front in the footprint's own frame: the mouth, panel line or actuator tip that sits on the edge
FRONT = {'J3': (0.0, -12.7), 'J6': (0.0, 3.65), 'J5': (3.5, 15.61), 'J4': (7.03, 0.0),
         'SW2': (2.25, -3.85), 'SW1': (2.25, -3.85)}
# left to right along the edge (the floorplan): BOOTSEL's pinhole beside the HDMI plug, RESET in the corner (gate 2)
ORDER = ['J3', 'J6', 'J5', 'J4', 'SW1', 'SW2']
# the plug's width along the edge (spec: HDMI and USB-A overmoulds run about 20 mm); BOOTSEL's actuator, which the case
# hides behind a pinhole; RESET's fingertip inside the case's guard
PLUG = {'J3': 15.0, 'J6': 12.5, 'J5': 20.0, 'J4': 20.0, 'SW1': 3.5, 'SW2': 10.0}


def front(ref):
    p = board().parts[ref]
    (dx, dy) = footprint.turn(FRONT[ref][0], FRONT[ref][1], p.rot)
    return (p.x + dx, p.y + dy)


@unittest.skipUnless(HAVE, 'needs KiCad 10 and hardware/board/liz4270.kicad_pcb')
class TestEdge(unittest.TestCase):
    def test_each_front_is_on_the_edge_facing_out(self):
        for ref in FRONT:
            self.assertAlmostEqual(front(ref)[1], HEIGHT, delta=0.05, msg=ref)
            self.assertLess(board().parts[ref].y, HEIGHT - 1, ref)     # the body lies behind its front

    def test_the_order_along_the_edge(self):
        xs = [front(ref)[0] for ref in ORDER]
        self.assertEqual(xs, sorted(xs))

    def test_plugs_clear_each_other_and_the_bnc_has_finger_room(self):
        spans = [(front(r)[0] - PLUG[r] / 2, front(r)[0] + PLUG[r] / 2, r) for r in ORDER]
        for ((_, right, a), (left, _, b)) in zip(spans, spans[1:]):
            self.assertGreaterEqual(left - right, 5.0 if a == 'J3' else 1.0, (a, b))
        self.assertGreaterEqual(spans[0][0], 0.0)
        self.assertLessEqual(spans[-1][1], WIDTH)

    def test_mounting_holes_and_h4_unplated_by_the_bnc(self):
        # H3 backs the edge's right end, where the HDMI plug and the buttons push (gate 2); H4 stays above the line side
        holes = {r: (board().parts[r].x, board().parts[r].y) for r in ('H1', 'H2', 'H3', 'H4')}
        self.assertEqual(holes, {'H1': (4.0, 4.0), 'H2': (96.0, 4.0), 'H3': (96.0, 66.0), 'H4': (4.0, 46.0)})
        bnc = (board().parts['J3'].x, board().parts['J3'].y)
        self.assertEqual(min(holes, key=lambda r: distance(holes[r], bnc)), 'H4')
        self.assertEqual(board().parts['H4'].fpid, 'MountingHole:MountingHole_3.2mm_M3')

    def test_button_frames_are_grounded(self):
        """The PTS645's metal frame comes down as two legs at the edge, where fingers touch it: on GND, a discharge
        goes to ground rather than across the switch into RUN or the flash's chip select."""
        for ref in ('SW1', 'SW2'):
            pads = board().parts[ref].pads
            self.assertEqual([p.net for p in pads if p.number == 'SH'], ['GND', 'GND'], ref)
            self.assertNotIn('', [p.net for p in pads], ref)

    def test_silkscreen(self):
        texts = {(t.text, t.layer) for t in board().texts}
        for t in (('Liz4270 rev A', 'F.SilkS'), ('© 2026 CoffeeMuse', 'B.SilkS'), ('CERN-OHL-P-2.0', 'B.SilkS'),
                  ('JLCJLCJLCJLC', 'B.SilkS')):
            self.assertIn(t, texts)
        for label in ('COAX', 'USB-C 5V', 'USB', 'HDMI', 'RESET', 'BOOT'):
            self.assertIn((label, 'B.SilkS'), texts)

    def test_no_placement_errors(self):
        self.assertEqual(placement_errors(), [])


# Raspberry Pi's minimal design, RPI-RP2350A-MINIMAL_R4-S1 (MIT), read Oct 9, 2026: the regulator's pads around its
# VREG_LX pad, in the chip's frame (x along the VREG side the way its pin numbers fall, y negative away from the
# chip). RP2350A and B share that side's order and pitch. (ref, pad) of ours -> (x, y); theirs in the comment.
REGULATOR = {
    ('L1', '1'): (-0.7, -3.75), ('L1', '2'): (0.7, -3.75),          # L1: pad 1 +1V1, pad 2 VREG_LX
    ('C1', '1'): (-0.515, -1.16), ('C1', '2'): (0.515, -1.16),      # C6, CIN
    ('C2', '1'): (-0.515, -2.1), ('C2', '2'): (0.515, -2.1),        # C7, COUT
    ('C4', '1'): (2.2, -2.075), ('C4', '2'): (2.2, -1.125),         # C9, VREG_AVDD's 4.7 uF
    ('R1', '1'): (2.2, -3.925), ('R1', '2'): (2.2, -2.975),         # R3, 33 R
}

# capacitor -> (ref, pad it serves, the most mm from the capacitor's pad on that rail to the pin)
DECOUPLING = {
    'C3': ('U1', '32', 3.0),                                         # 6.3.8.1: the second 4.7 uF at DVDD pin 32
    'C5': ('U1', '5', 6.0), 'C6': ('U1', '15', 6.0), 'C7': ('U1', '24', 6.0), 'C8': ('U1', '29', 6.0),
    'C9': ('U1', '41', 6.0), 'C10': ('U1', '50', 6.0), 'C11': ('U1', '59', 6.0), 'C12': ('U1', '60', 6.0),
    'C13': ('U1', '68', 6.0), 'C14': ('U1', '69', 6.0), 'C15': ('U1', '76', 6.0),
    'C16': ('U1', '10', 6.0), 'C17': ('U1', '32', 6.0), 'C18': ('U1', '51', 6.0),
    'C21': ('U2', '8', 3.0),
    'C22': ('U3', '16', 3.0), 'C23': ('U3', '16', 4.0), 'C24': ('U4', '16', 3.0), 'C25': ('U4', '16', 4.0),
    'C30': ('U6', '5', 3.0), 'C31': ('U6', '6', 3.0),
    'C32': ('U7', '5', 3.0), 'C33': ('U8', '20', 3.0), 'C34': ('U8', '20', 3.0), 'C35': ('U8', '19', 4.0),
    'C36': ('U8', '19', 3.0), 'C40': ('FB1', '2', 5.0), 'C41': ('FB1', '2', 5.0), 'C42': ('U12', '1', 4.0),
    'C43': ('U12', '3', 4.0), 'C44': ('U12', '3', 4.0),
    'C50': ('U13', '1', 3.0), 'C51': ('U13', '5', 3.0), 'C52': ('U14', '2', 3.0), 'C53': ('U14', '3', 3.0),
    'C54': ('U14', '3', 4.0), 'C55': ('U14', '17', 3.0), 'C56': ('U14', '17', 5.0), 'C57': ('U14', '28', 3.0),
    'C58': ('U14', '21', 3.0), 'C59': ('U14', '24', 3.0), 'C60': ('U14', '21', 5.0),
}
MCU = ['U1', 'U2', 'Y1', 'L1', 'R44', 'R45', 'D1', 'J1', 'J2', 'C61'] + [f'C{i}' for i in range(1, 22)] + \
      [f'R{i}' for i in range(1, 10)]


def placed(refs):
    return [r for r in refs if board().parts[r].y <= HEIGHT]


def rail_pad(cap, ref, pad):
    """The pad of cap on the net of ref's pad."""
    net = board().pad(ref, pad).net
    return next(p for p in board().parts[cap].pads if p.net == net)


@unittest.skipUnless(HAVE, 'needs KiCad 10 and hardware/board/liz4270.kicad_pcb')
class TestCore(unittest.TestCase):
    def test_every_part_placed(self):
        self.assertEqual(placed(MCU), MCU)

    def test_u1_where_the_floorplan_puts_it(self):
        u1 = board().parts['U1']
        self.assertEqual((u1.x, u1.y, u1.rot), (42.0, 32.0, 180.0))

    def test_regulator_is_the_minimal_designs(self):
        u1 = board().parts['U1']
        lx = board().pad('U1', '63')
        for ((ref, pad), (x, y)) in REGULATOR.items():
            p = board().pad(ref, pad)
            (cx, cy) = footprint.turn(p.x - lx.x, p.y - lx.y, -u1.rot)
            self.assertAlmostEqual(cx, x, delta=0.05, msg=(ref, pad))
            self.assertAlmostEqual(cy, y, delta=0.05, msg=(ref, pad))

    def test_crystal_at_xin_and_xout(self):
        self.assertLessEqual(distance(xy(board().pad('Y1', '1')), xy(board().pad('U1', '30'))), 6.0)
        self.assertLessEqual(distance(xy(board().pad('R2', '1')), xy(board().pad('U1', '31'))), 3.0)
        for c in ('C19', 'C20'):
            self.assertLessEqual(min(distance(xy(p), xy(q)) for p in board().parts[c].pads
                                     for q in board().parts['Y1'].pads), 3.0, c)

    def test_flash_close_and_r4_at_its_chip_select(self):
        self.assertLessEqual(distance(xy(board().pad('U2', '6')), xy(board().pad('U1', '71'))), 12.0)
        self.assertLessEqual(distance(xy(board().pad('R4', '1')), xy(board().pad('U2', '1'))), 4.0)

    def test_swd_opens_toward_the_top_edge(self):
        """JST SH side entry: the plug goes in on the side of its mounting tabs (MP), the signal pads behind."""
        pads = board().parts['J1'].pads
        tabs = max(p.y for p in pads if p.number == 'MP')
        signals = min(p.y for p in pads if p.number in ('1', '2', '3'))
        self.assertLess(tabs, signals)

    def test_small_parts_at_their_pins(self):
        for (a, b, most) in (('R5.1', 'U1.67', 5.5), ('R6.1', 'U1.66', 5.5), ('R7.1', 'U1.1', 6.0),
                             ('R8.1', 'U1.2', 6.0), ('D1.1', 'U1.37', 8.0), ('R44.1', 'U1.33', 4.0),
                             ('R45.1', 'U1.34', 4.0), ('C61.1', 'U1.35', 6.0)):
            self.assertLessEqual(distance(xy(pad_of(a)), xy(pad_of(b))), most, (a, b))


@unittest.skipUnless(HAVE, 'needs KiCad 10 and hardware/board/liz4270.kicad_pcb')
class TestDecoupling(unittest.TestCase):
    def test_each_capacitor_at_its_pin(self):
        for (cap, (ref, pad, most)) in DECOUPLING.items():
            if not placed([cap, ref]) == [cap, ref]:
                continue                                    # its block isn't placed yet; TestX.test_every_part_placed
            gap = distance(xy(rail_pad(cap, ref, pad)), xy(board().pad(ref, pad)))
            self.assertLessEqual(gap, most, f'{cap} is {gap:.1f} mm from {ref} pin {pad}')

    def test_the_hubs_regulator_capacitors_join_it_directly(self):
        """Gate-3 review, finding 3: the CH334F's own 3.3 V regulator (VDD33, pin 20) reaches its 1 u, C34, and its
        10 u, C33, each by a few mm of copper, not by a loop through vias."""
        for cap in ('C33', 'C34'):
            way = run('HUB_V33', xy(pad_of(cap + '.1')), xy(pad_of('U8.20')))
            self.assertGreater(way, 0.0, cap)
            self.assertLessEqual(way, 5.0, f'{cap} is {way:.1f} mm of copper from U8 pin 20')


LINE = {'LINE_C', 'LINE_S'}
LINE_SIDE = (0.0, 59.02, 19.5, 80.0)               # x0, y0, x1, y1: the BNC corner (plan 2's floorplan)
BAND = 1.5
COAX = ['T1', 'U3', 'U4', 'U5'] + [f'R{i}' for i in range(10, 17)] + [f'C{i}' for i in range(22, 27)]


def in_box(p, box, margin=0.0):
    return box[0] - margin <= p[0] <= box[2] + margin and box[1] - margin <= p[1] <= box[3] + margin


@unittest.skipUnless(HAVE, 'needs KiCad 10 and hardware/board/liz4270.kicad_pcb')
class TestCoax(unittest.TestCase):
    def test_every_part_placed(self):
        self.assertEqual(placed(COAX), COAX)

    def test_t1_line_pins_face_the_bnc(self):
        t1 = board().parts['T1']
        self.assertEqual((t1.x, t1.y, t1.rot), (10.0, 57.0, 180.0))
        line = [board().pad('T1', n).y for n in ('1', '6')]
        others = [board().pad('T1', n).y for n in ('2', '3', '4', '5')]
        self.assertGreater(min(line), max(others))

    def test_line_copper_inside_the_line_side_and_nothing_else(self):
        for part in board().parts.values():
            for p in part.pads:
                if p.net in LINE:
                    self.assertTrue(in_box(xy(p), LINE_SIDE), (part.ref, p.number))
                elif p.kind != 'np_thru_hole' and part.ref != 'H4':
                    self.assertFalse(in_box(xy(p), LINE_SIDE, margin=BAND), (part.ref, p.number, p.net))

    def test_keepouts_on_every_layer(self):
        rules = {z.name: z for z in board().zones if z.rule}
        side = rules['Coax line side']
        band = rules['Coax isolation band']
        self.assertEqual(set(side.layers), {'F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu'})
        self.assertEqual(set(band.layers), {'F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu'})
        self.assertTrue(side.rule['copperpour'])
        self.assertTrue(band.rule['tracks'] and band.rule['vias'] and band.rule['copperpour'])

    def test_h4_outside_the_gap(self):
        self.assertFalse(in_box(xy(board().parts['H4']), LINE_SIDE, margin=BAND + 3.5))

    def test_drive_is_symmetric(self):
        for (a, b) in ((('R13', '2'), ('R14', '2')), (('R11', '2'), ('R12', '2'))):
            da = distance(xy(board().pad(*a)), xy(board().pad('T1', '3')))
            db = distance(xy(board().pad(*b)), xy(board().pad('T1', '4')))
            self.assertLessEqual(abs(da - db), 1.0, (a, b))
        d1 = distance(xy(board().pad('R15', '1')), xy(board().pad('T1', '3')))
        d2 = distance(xy(board().pad('R15', '2')), xy(board().pad('T1', '4')))
        self.assertLessEqual(abs(d1 - d2), 1.0)

    def test_tx_active_pull_down_at_the_driver(self):
        self.assertLessEqual(distance(xy(board().pad('R16', '1')), xy(board().pad('U4', '4'))), 4.0)


VIDEO = ['U6', 'Q1', 'Q2', 'C30', 'C31'] + [f'R{i}' for i in range(20, 34)]
# U6 pad -> the J4 pad its line ends on (spec, Video; TI's D0 clamps take HDMI Data2, D2 Data0, D3 the clock)
CLAMP = {'16': '1', '15': '3', '14': '4', '13': '6', '12': '7', '11': '9', '10': '10', '9': '12'}


@unittest.skipUnless(HAVE, 'needs KiCad 10 and hardware/board/liz4270.kicad_pcb')
class TestVideo(unittest.TestCase):
    def test_every_part_placed(self):
        self.assertEqual(placed(VIDEO), VIDEO)

    def test_clamps_on_the_way_to_the_connector(self):
        for (u6, j4) in CLAMP.items():
            self.assertLessEqual(distance(xy(board().pad('U6', u6)), xy(board().pad('J4', j4))), 8.0, u6)
        resistors = [xy(board().pad(f'R{i}', '2')) for i in range(20, 28)]
        j4 = xy(board().pad('J4', '10'))
        self.assertLess(distance(xy(board().pad('U6', '10')), j4), min(distance(r, j4) for r in resistors))

    def test_series_resistors_in_pairs(self):
        for i in range(20, 28, 2):
            (a, b) = (board().parts[f'R{i}'], board().parts[f'R{i + 1}'])
            self.assertEqual(a.rot, b.rot, i)
            self.assertLessEqual(distance((a.x, a.y), (b.x, b.y)), 2.0, i)

    def test_ddc_and_hot_plug_at_the_connector(self):
        for (a, b, most) in (('Q1.3', 'J4.15', 12.0), ('Q2.3', 'J4.16', 12.0), ('R30.2', 'J4.15', 12.0),
                             ('R31.2', 'J4.16', 12.0), ('R32.1', 'J4.19', 10.0), ('R33.1', 'R32.2', 3.0)):
            self.assertLessEqual(distance(xy(pad_of(a)), xy(pad_of(b))), most, (a, b))


USB_HOST = ['U7', 'U8', 'U9', 'U10', 'Y2', 'R34', 'R35', 'R36', 'D2', 'D3'] + [f'C{i}' for i in range(32, 39)]
POWER = ['U11', 'U12', 'F1', 'D4', 'FB1', 'R40', 'R41', 'R42', 'D5'] + [f'C{i}' for i in range(40, 45)] + \
        [f'TP{i}' for i in range(1, 6)]


@unittest.skipUnless(HAVE, 'needs KiCad 10 and hardware/board/liz4270.kicad_pcb')
class TestUsbHost(unittest.TestCase):
    def test_every_part_placed(self):
        self.assertEqual(placed(USB_HOST), USB_HOST)

    def test_hub_between_the_chip_and_the_ports(self):
        self.assertLessEqual(distance(xy(pad_of('U8.15')), xy(pad_of('U1.78'))), 25.0)
        self.assertLessEqual(distance(xy(pad_of('Y2.1')), xy(pad_of('U8.4'))), 5.0)

    def test_the_upstream_pair_can_leave_the_hub(self):
        """U8's upstream pins (14, 15) are on its right side: the pair turns there or drops to vias, so 2 mm beside
        that side stays clear of other parts' pads (USB class: 0.25 + 0.15 + 0.25 mm with 0.2 mm each side, or a
        0.6 mm via; gate 2)."""
        side = [p for p in board().parts['U8'].pads if p.number in ('13', '14', '15', '16', '17', '18')]
        x0 = max(p.x + p.w / 2 for p in side)
        (y0, y1) = (min(p.y for p in side) - 0.5, max(p.y for p in side) + 0.5)
        for part in board().parts.values():
            for p in part.pads if part.ref != 'U8' else ():
                (bx0, by0, bx1, by1) = pad_box(part, p)
                if by1 > y0 and by0 < y1:
                    self.assertFalse(bx1 > x0 and bx0 < x0 + 2.0, (part.ref, p.number, round(bx0 - x0, 2)))

    def test_esd_at_the_ports(self):
        for (a, b) in (('U9.1', 'J5.3'), ('U10.1', 'J5.7')):
            self.assertLessEqual(distance(xy(pad_of(a)), xy(pad_of(b))), 10.0, a)

    def test_bulk_at_the_ports(self):
        for c in ('C37', 'C38'):
            self.assertLessEqual(min(distance(xy(rail_pad(c, 'J5', n)), xy(pad_of(f'J5.{n}'))) for n in ('1', '5')),
                                 10.0, c)


@unittest.skipUnless(HAVE, 'needs KiCad 10 and hardware/board/liz4270.kicad_pcb')
class TestPower(unittest.TestCase):
    def test_every_part_placed(self):
        self.assertEqual(placed(POWER), POWER)

    def test_protection_at_the_input(self):
        for (a, b, most) in (('U11.1', 'J6.A6', 6.0), ('F1.1', 'J6.A4', 10.0), ('D4.1', 'F1.2', 6.0),
                             ('FB1.1', 'F1.2', 8.0), ('R40.1', 'J6.A5', 5.0), ('R41.1', 'J6.B5', 5.0)):
            self.assertLessEqual(distance(xy(pad_of(a)), xy(pad_of(b))), most, (a, b))

    def test_test_points_have_room_for_a_probe(self):
        tps = [f'TP{i}' for i in range(1, 6)]
        for tp in tps:
            p = board().parts[tp]
            for other in board().parts.values():
                if other.ref != tp and other.y <= HEIGHT:
                    for q in other.pads:
                        self.assertGreaterEqual(distance((p.x, p.y), xy(q)), 2.0, (tp, other.ref))


AUDIO = ['U13', 'U14', 'J7', 'R43'] + [f'C{i}' for i in range(50, 61)]


@unittest.skipUnless(HAVE, 'needs KiCad 10 and hardware/board/liz4270.kicad_pcb')
class TestAudio(unittest.TestCase):
    def test_every_part_placed(self):
        self.assertEqual(placed(AUDIO), AUDIO)

    def test_speaker_away_from_the_coax(self):
        """Gate-1 review: J7 and the speaker leads away from the coax front end; the class-D output is unfiltered."""
        j7 = board().parts['J7']
        for ref in ('T1', 'U3', 'U4', 'J3'):
            self.assertGreaterEqual(distance((j7.x, j7.y), (board().parts[ref].x, board().parts[ref].y)), 50.0, ref)

    def test_dac_in_the_top_right(self):
        u14 = board().parts['U14']
        self.assertTrue(u14.x >= 60 and u14.y <= 32, (u14.x, u14.y))

    def test_reset_pull_up_at_its_pin(self):
        self.assertLessEqual(distance(xy(pad_of('R43.2')), xy(pad_of('U14.31'))), 5.0)


@unittest.skipUnless(HAVE, 'needs KiCad 10 and hardware/board/liz4270.kicad_pcb')
class TestPlaced(unittest.TestCase):
    def test_nothing_parked(self):
        self.assertEqual([r for (r, p) in board().parts.items() if p.y > HEIGHT], [])

    def test_everything_inside_the_outline(self):
        for part in board().parts.values():
            for p in part.pads:
                self.assertTrue(0.3 <= p.x <= WIDTH - 0.3 and 0.3 <= p.y <= HEIGHT - 0.3, (part.ref, p.number))


def stadium(box, out, n=48):
    """n points out mm from a round or oval pad filling box (x0, y0, x1, y1), its ends round on its short side."""
    (x0, y0, x1, y1) = box
    r = min(x1 - x0, y1 - y0) / 2
    (cx, cy) = ((x0 + x1) / 2, (y0 + y1) / 2)
    (hx, hy) = ((x1 - x0) / 2 - r, (y1 - y0) / 2 - r)      # the straight sides' half lengths (one is 0)
    points = []
    for i in range(n):
        a = 2 * math.pi * (i + 0.5) / n
        (dx, dy) = (math.cos(a), math.sin(a))
        points.append((cx + math.copysign(hx, dx) + (r + out) * dx, cy + math.copysign(hy, dy) + (r + out) * dy))
    return points


def frange(a, b, step):
    out = []
    while a <= b + 1e-9:
        out.append(round(a, 6))
        a += step
    return out


@unittest.skipUnless(HAVE, 'needs KiCad 10 and hardware/board/liz4270.kicad_pcb')
class TestPlanes(unittest.TestCase):
    def test_in1_is_ground_and_in2_is_3v3(self):
        planes = {(z.net, z.layers) for z in board().zones if not z.rule}
        self.assertIn(('GND', ('In1.Cu',)), planes)
        self.assertIn(('+3V3', ('In2.Cu',)), planes)
        self.assertIn(('GND', ('F.Cu',)), planes)
        self.assertIn(('GND', ('B.Cu',)), planes)

    def test_the_vreg_lx_cut_out(self):
        """Datasheet 6.3.8.1, Figure 27: no copper on In1 under VREG_LX, between U1's pin 63 and L1's pad 2."""
        (a, b) = (xy(pad_of('U1.63')), xy(pad_of('L1.2')))
        for t in (0.25, 0.5, 0.75):
            p = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
            for z in filled().zones:
                for poly in z.filled.get('In1.Cu', []):
                    self.assertFalse(pcb.inside(p, poly), (z.net, t))

    def test_exposed_pads_join_the_pours_solid(self):
        """The thermal vias in U1's, U8's and U14's exposed pads leave no room for thermal spokes, and belong on the
        planes solid anyway."""
        self.assertEqual([v for v in drc()[0] if v[1] == 'starved_thermal'], [])

    def test_ground_is_stitched(self):
        self.assertGreaterEqual(sum(1 for v in board().vias if v.net == 'GND'), 40)

    def test_through_hole_pins_meet_the_planes_by_spokes(self):
        """Gate-3 review, finding 2: a through-hole pin on GND or +3V3 meets In1 or In2 by thermal spokes, as it meets
        the outer pours, so that the bench header, the connectors' shells and the buttons' frames solder. The exposed
        pads' thermal vias and the plated mounting holes join solid, and so do USB-A's ground pins on In1, which port
        2's D+ passes over. Each pad is sampled on a ring 0.25 mm out from its edge, inside the 0.5 mm thermal gap:
        solid copper covers all of the ring, spokes a part of it."""
        solid = {'U1', 'U8', 'U14', 'H1', 'H2', 'H3', ('J5', '4', 'In1.Cu'), ('J5', '8', 'In1.Cu')}
        b = filled()
        for (net, layer) in (('GND', 'In1.Cu'), ('+3V3', 'In2.Cu')):
            polys = [poly for z in b.zones if z.net == net and not z.rule for poly in z.filled.get(layer, [])]
            for part in b.parts.values():
                for pad in part.pads:
                    if pad.kind != 'thru_hole' or pad.net != net:
                        continue
                    ring = stadium(pad_box(part, pad), 0.25)
                    share = sum(any(pcb.inside(p, poly) for poly in polys) for p in ring) / len(ring)
                    if part.ref in solid or (part.ref, pad.number, layer) in solid:
                        self.assertGreater(share, 0.9, (part.ref, pad.number, layer, share))
                    else:
                        self.assertLess(share, 0.75, (part.ref, pad.number, layer, share))


@unittest.skipUnless(HAVE, 'needs KiCad 10 and hardware/board/liz4270.kicad_pcb')
class TestIsolation(unittest.TestCase):
    def test_no_foreign_copper_in_the_line_side(self):
        """Spec, Coax front end: nothing but the line's own copper inside the line side or its band, on any layer."""
        (x0, y0, x1, y1) = (LINE_SIDE[0], LINE_SIDE[1] - BAND, LINE_SIDE[2] + BAND, LINE_SIDE[3])

        def inner(p):
            return x0 + 0.01 < p[0] < x1 - 0.01 and y0 + 0.01 < p[1] < y1 - 0.01
        probes = [(x, y) for x in frange(x0 + 0.5, x1 - 0.5, 2.0) for y in frange(y0 + 0.5, y1 - 0.5, 2.0)]
        b = filled()
        for z in b.zones:
            if z.net in LINE or z.rule:
                continue
            for (layer, polys) in z.filled.items():
                for poly in polys:
                    self.assertFalse(any(inner(p) for p in poly), (z.net, layer))
                    self.assertFalse(any(pcb.inside(q, poly) for q in probes), (z.net, layer))
        for s in b.segments:
            if s.net not in LINE:
                for t in [i / 20 for i in range(21)]:
                    p = (s.start[0] + t * (s.end[0] - s.start[0]), s.start[1] + t * (s.end[1] - s.start[1]))
                    self.assertFalse(inner(p), (s.net, s.layer, s.start, s.end))
        for v in b.vias:
            if v.net not in LINE:
                self.assertFalse(inner((v.x, v.y)), (v.net, v.x, v.y))

    def test_nothing_but_ground_under_the_connector_shells(self):
        """Gate-3 review, finding 1: past the tails of J4's pins, and past the posts of J6's housing, the connectors'
        metal shells (ground) sit on the board, with only solder mask between; F.Cu carries nothing but ground there.
        Each body is J4's 15 mm and J6's 8.94 mm wide, out to the edge."""
        b = board()
        (j4, j6) = (b.parts['J4'], b.parts['J6'])
        tails = max(pad_box(j4, p)[3] for p in j4.pads if p.kind == 'smd')
        posts = max(p.y + p.h / 2 for p in j6.pads if p.kind == 'np_thru_hole')
        for (ref, (x0, y0, x1, y1)) in (('J4', (j4.x - 7.5, tails, j4.x + 7.5, HEIGHT)),
                                         ('J6', (j6.x - 4.47, posts, j6.x + 4.47, HEIGHT))):
            def under(p, r):
                return x0 - r < p[0] < x1 + r and y0 - r < p[1] < y1 + r
            for s in b.segments:
                if s.layer == 'F.Cu' and s.net != 'GND':
                    for t in [i / 20 for i in range(21)]:
                        p = (s.start[0] + t * (s.end[0] - s.start[0]), s.start[1] + t * (s.end[1] - s.start[1]))
                        self.assertFalse(under(p, s.width / 2), (ref, s.net, s.start, s.end))
            for v in b.vias:
                if v.net != 'GND':
                    self.assertFalse(under((v.x, v.y), v.size / 2), (ref, v.net, v.x, v.y))


# (P, N, the most their routed lengths may differ, mm)
PAIRS = [(f'HSTX_{p}P', f'HSTX_{p}N', 0.25) for p in ('CK', 'D0', 'D1', 'D2')] + \
        [(f'HDMI_{p}P', f'HDMI_{p}N', 0.25) for p in ('CK', 'D0', 'D1', 'D2')] + \
        [('USBC_DP', 'USBC_DM', 1.5), ('Net-(U1-USB_DP)', 'Net-(U1-USB_DM)', 1.0), ('USBH_DP', 'USBH_DM', 1.5),
         ('USBA1_DP', 'USBA1_DM', 1.5), ('USBA2_DP', 'USBA2_DM', 1.5)]
TMDS_NETS = {n for (p, q, _) in PAIRS[:8] for n in (p, q)}


def routed(net):
    return sum(distance(s.start, s.end) for s in board().segments if s.net == net)


def run(net, a, b):
    """The shortest way along net's tracks from point a to point b, through its vias (tracks meet end to end)."""
    def key(p):
        return (round(p[0], 3), round(p[1], 3))
    graph = {}
    for s in board().segments:
        if s.net == net:
            (u, v, d) = (key(s.start), key(s.end), distance(s.start, s.end))
            graph.setdefault(u, []).append((v, d))
            graph.setdefault(v, []).append((u, d))
    (best, todo) = ({key(a): 0.0}, [(0.0, key(a))])
    while todo:
        todo.sort()
        (d, u) = todo.pop(0)
        if u == key(b):
            return d
        for (v, e) in graph.get(u, []):
            if d + e < best.get(v, float('inf')):
                best[v] = d + e
                todo.append((d + e, v))
    return 0.0


@unittest.skipUnless(HAVE, 'needs KiCad 10 and hardware/board/liz4270.kicad_pcb')
class TestCritical(unittest.TestCase):
    def test_pairs_routed_and_matched(self):
        for (p, n, most) in PAIRS:
            (lp, ln) = (routed(p), routed(n))
            self.assertGreater(min(lp, ln), 0.0, (p, n))
            self.assertLessEqual(abs(lp - ln), most, f'{p} {lp:.2f} mm, {n} {ln:.2f} mm')

    def test_tmds_on_top_without_vias_at_their_width(self):
        for s in board().segments:
            if s.net in TMDS_NETS:
                self.assertEqual(s.layer, 'F.Cu', s)
                self.assertTrue(s.width == 0.225 or distance(s.start, s.end) <= 1.0, s)   # necks at pads
        self.assertFalse([v for v in board().vias if v.net in TMDS_NETS])

    def test_pairs_over_unbroken_ground(self):
        """Spec, Video: each pair over unbroken ground; every point of every pair's top-layer track lies on In1's fill."""
        nets = {n for (p, q, _) in PAIRS for n in (p, q)}
        polys = [poly for z in filled().zones if z.net == 'GND' for poly in z.filled.get('In1.Cu', [])]
        # (net, x, y, radius) of each via and through-hole pad on a pair's line
        holes = [(v.net, v.x, v.y, v.size / 2) for v in board().vias if v.net in nets] + \
                [(q.net, q.x, q.y, max(q.w, q.h) / 2) for part in board().parts.values() for q in part.pads
                 if q.kind == 'thru_hole' and q.net in nets]
        for s in board().segments:
            if s.net in nets and s.layer == 'F.Cu':
                for t in (0.0, 0.5, 1.0):
                    p = (s.start[0] + t * (s.end[0] - s.start[0]), s.start[1] + t * (s.end[1] - s.start[1]))
                    # where a line leaves F.Cu by a via or a through-hole pin of its own, In1 has its clearance hole
                    if any(n == s.net and distance(p, (x, y)) <= r + 0.5 for (n, x, y, r) in holes):
                        continue
                    self.assertTrue(any(pcb.inside(p, poly) for poly in polys), (s.net, p))

    def test_crystals_short(self):
        for net in ('XIN', 'XOUT', board().pad('Y1', '3').net, 'HUB_XI', 'HUB_XO'):
            self.assertGreater(routed(net), 0.0, net)
        # gate 2 set Y1 6 mm above XIN (TestCore allows 6), so XIN alone runs 6.2 mm and R2 back to Y1's pin 3 5.2:
        # 18.7 mm in all, routed as short as that placement goes
        self.assertLessEqual(routed('XIN') + routed('XOUT') + routed(board().pad('Y1', '3').net), 19.0)
        self.assertLessEqual(routed('HUB_XI') + routed('HUB_XO'), 10.0)

    def test_coax_drive_symmetric(self):
        """Each drive line, from its 150 R through its 33 R and R15 to T1, runs the same length; U5's branches (not
        fitted, on the P side, so TX_N's runs 10 mm) aren't part of the drive."""
        p = run('TX_P', xy(pad_of('R11.2')), xy(pad_of('T1.3')))
        n = run('TX_N', xy(pad_of('R12.2')), xy(pad_of('T1.4')))
        self.assertGreater(min(p, n), 0.0)
        self.assertLessEqual(abs(p - n), 2.0)
        for pad in ('2', '3', '5', '6'):
            self.assertGreater(routed(board().pad('U4', pad).net), 0.0, pad)
            self.assertLessEqual(routed(board().pad('U4', pad).net), 10.0, pad)


@unittest.skipUnless(HAVE, 'needs KiCad 10 and hardware/board/liz4270.kicad_pcb')
class TestRouted(unittest.TestCase):
    def test_the_session_is_current(self):
        import build_board
        with open(build_board.ROUTE, encoding='utf-8') as stream:
            route = json.load(stream)
        with tempfile.TemporaryDirectory() as tmp:
            xml = os.path.join(tmp, 'liz4270.xml')
            netlist.export_xml(os.path.join(paths.BOARD, 'liz4270.kicad_sch'), xml)
            self.assertEqual(build_board.fingerprint(xml), route['fingerprint'])

    def test_the_fingerprint_follows_what_freerouting_routes_by(self):
        """Final review: a net class, a DRC rule or a footprint changed is a stale session, as a place changed is."""
        import board_setup
        import build_board
        with tempfile.TemporaryDirectory() as tmp:
            xml = os.path.join(tmp, 'liz4270.xml')
            netlist.export_xml(os.path.join(paths.BOARD, 'liz4270.kicad_sch'), xml)
            before = build_board.fingerprint(xml)
            (default, path) = (board_setup.DEFAULT, footprint.path)
            try:
                board_setup.DEFAULT = default[:2] + (default[2] + 0.05,) + default[3:]
                self.assertNotEqual(build_board.fingerprint(xml), before, 'a class width')
                board_setup.DEFAULT = default
                copy = os.path.join(tmp, 'Murata_786J.kicad_mod')
                with open(path('liz4270:Murata_786J'), encoding='utf-8') as stream:
                    text = stream.read()
                with open(copy, 'w', encoding='utf-8') as stream:
                    stream.write(text.replace('(size 2.759 1.016)', '(size 2.759 1.1)', 1))
                footprint.path = lambda fpid: copy if fpid == 'liz4270:Murata_786J' else path(fpid)
                self.assertNotEqual(build_board.fingerprint(xml), before, 'a footprint')
            finally:
                (board_setup.DEFAULT, footprint.path) = (default, path)

    def test_drc_clean(self):
        (violations, unconnected, parity) = drc()
        self.assertEqual([v for v in violations if v[0] == 'error'], [])
        self.assertEqual(unconnected, [])
        self.assertEqual(parity, [])

    def test_no_via_left_dangling(self):
        """Gate-3 review, finding 5: an escape via that Freerouting's routes don't use goes, with its stub, and so does
        a via of Freerouting's own that its tracks meet on one layer only. The one via that may dangle is the regulator
        copy's: of the minimal design's touching +1V1 pair, one meets copper on F.Cu only unless a route reaches it."""
        dangling = [v[3] for v in drc()[0] if v[1] == 'via_dangling']
        self.assertLessEqual(len(dangling), 1)
        self.assertEqual([d for d in dangling if d != ('Via [+1V1] on F.Cu - B.Cu',)], [])


@unittest.skipUnless(HAVE, 'needs KiCad 10 and hardware/board/liz4270.kicad_pcb')
class TestSilk(unittest.TestCase):
    def test_no_silkscreen_overlaps(self):
        bad = [v for v in drc()[0] if v[1] in ('silk_overlap', 'silk_edge_clearance')]
        self.assertEqual(bad, [])

    def test_the_case_exports_are_current(self):
        result = subprocess.run([sys.executable, os.path.join(paths.HERE, 'make_exports.py'), '--check'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_the_bench_reads_the_board(self):
        """Gate-2 review, finding 8: what bring-up reads off a bare board."""
        texts = [(t.text, t.x, t.y) for t in board().texts if t.layer == 'F.SilkS']

        def near(name, at, most):
            return any(t == name and distance((x, y), at) <= most for (t, x, y) in texts)

        for (tp, name) in (('TP1', '+5V'), ('TP2', '3V3'), ('TP3', '1V8'), ('TP4', '1V1'), ('TP5', 'GND')):
            self.assertTrue(near(name, (board().parts[tp].x, board().parts[tp].y), 3.0), tp)
        for (pin, name) in (('1', 'RX'), ('3', 'TX'), ('5', 'TXA'), ('7', 'TXD'), ('9', 'UTX'), ('11', 'URX'),
                            ('13', '3V3')):
            self.assertTrue(near(name, xy(board().pad('J2', pin)), 3.5), name)
        self.assertTrue(any(near('GND', xy(board().pad('J2', str(n))), 3.5) for n in range(2, 15, 2)))
        for (ref, name) in (('SW1', 'BOOT'), ('SW2', 'RESET')):
            self.assertTrue(near(name, (front(ref)[0], 70.5), 2.0), ref)
        self.assertTrue(any('NOT GND' in t for (t, _, _) in texts))


if __name__ == '__main__':
    unittest.main()
