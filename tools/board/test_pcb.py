# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""footprint and pcb: footprint geometry turned as KiCad turns it, and the layout model's rules."""

import math
import unittest

import footprint
import pcb

R0603 = 'Resistor_SMD:R_0603_1608Metric'
QFN80 = 'Package_DFN_QFN:QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm_ThermalVias'


class TestFootprint(unittest.TestCase):
    def test_pads_and_courtyard(self):
        fp = footprint.load(R0603)
        self.assertEqual([(p.number, p.x, p.y) for p in fp.pads], [('1', -0.825, 0.0), ('2', 0.825, 0.0)])
        self.assertEqual(fp.courtyard, (-1.48, -0.73, 1.48, 0.73))

    def test_a_circle_courtyard_is_bounded_by_its_radius(self):
        (x0, y0, x1, y1) = footprint.load('MountingHole:MountingHole_3.2mm_M3').courtyard
        self.assertAlmostEqual(x1 - x0, 6.9, places=2)
        self.assertAlmostEqual(y1 - y0, 6.9, places=2)

    def test_turn_is_kicads(self):
        # KiCad turns counter-clockwise on a screen whose y points down: west goes south at 90
        self.assertEqual(footprint.turn(-0.825, 0, 90), (0.0, 0.825))
        self.assertEqual(footprint.turn(-0.825, 0, 180), (0.825, 0.0))
        self.assertEqual(footprint.turn(-0.825, 0, 270), (0.0, -0.825))
        self.assertEqual(footprint.turn(1, 2, 0), (1.0, 2.0))

    def test_ours_and_stock(self):
        self.assertTrue(footprint.path('liz4270:Murata_786J').endswith('lib/liz4270.pretty/Murata_786J.kicad_mod'))
        pads = footprint.load(QFN80).pads
        self.assertEqual(sum(1 for p in pads if p.number == '81' and p.kind == 'thru_hole'), 9)   # the thermal vias
        self.assertEqual(sum(1 for p in pads if p.number.isdigit() and int(p.number) <= 80), 80)
        with self.assertRaises(KeyError):
            footprint.pad(R0603, '3')


class TestLayout(unittest.TestCase):
    def setUp(self):
        self.L = pcb.Layout({'R1': R0603, 'R2': R0603, 'U1': QFN80}, 50, 40)

    def test_a_pad_names_its_net(self):
        L = pcb.Layout({'R1': R0603}, 50, 40, pins={('R1', '1'): 'Net-(R1-Pad1)'})
        self.assertEqual(L.net('R1.1'), 'Net-(R1-Pad1)')

    def test_pads_follow_their_part(self):
        self.L.place('R1', 10, 20, 90)
        self.assertEqual(self.L.pad('R1', '1'), (10.0, 20.825))
        self.assertEqual(self.L.point('R1.2'), (10.0, 19.175))

    def test_a_part_once_and_only_from_the_netlist(self):
        self.L.place('R1', 10, 20)
        with self.assertRaises(ValueError):
            self.L.place('R1', 11, 20)
        with self.assertRaises(KeyError):
            self.L.place('R9', 1, 1)
        with self.assertRaises(KeyError):
            self.L.pad('R2', '1')
        self.assertEqual(self.L.unplaced(), ['R2', 'U1'])

    def test_tracks_end_on_pads(self):
        self.L.place('R1', 10, 20)
        self.L.place('R2', 20, 20)
        self.L.track('X', 'F.Cu', 0.2, 'R1.2', (15, 20), 'R2.1')
        self.assertEqual(self.L.tracks[0].points, ((10.825, 20.0), (15.0, 20.0), (19.175, 20.0)))
        with self.assertRaises(ValueError):
            self.L.track('X', 'F.SilkS', 0.2, (0, 0), (1, 1))

    def test_a_track_drops_a_repeated_point(self):
        """A neck that ends where a pair's line begins gives that point twice; it isn't a zero-length segment."""
        self.L.place('R1', 10, 20)
        self.L.track('X', 'F.Cu', 0.2, 'R1.2', (15, 20), (15.0, 20.0), (15, 25))
        self.assertEqual(self.L.tracks[0].points, ((10.825, 20.0), (15.0, 20.0), (15.0, 25.0)))
        with self.assertRaises(ValueError):
            self.L.track('X', 'F.Cu', 0.2, (1, 1), (1.0, 1.0))

    def test_pours_only_on_the_outer_layers(self):
        self.L.pour('GND', 'B.Cu', pcb.rect(0, 0, 50, 40))
        with self.assertRaises(ValueError):
            self.L.pour('GND', 'In1.Cu', pcb.rect(0, 0, 50, 40))

    def test_box_turns_with_the_part(self):
        self.L.place('R1', 10, 20, 90)
        self.assertEqual(self.L.box('R1'), (9.27, 18.52, 10.73, 21.48))

    def test_stitching_skips_parts_keepouts_copper_and_other_vias(self):
        self.L.place('R1', 10, 20)
        self.L.keepout('k', ['F.Cu'], pcb.rect(30, 0, 40, 10))
        self.L.track('X', 'F.Cu', 0.2, (0, 30), (50, 30))
        self.L.zone('Y', 'F.Cu', pcb.rect(40, 15, 45, 25))
        self.L.zone('+3V3', 'In2.Cu', pcb.rect(0, 0, 50, 40))           # a plane doesn't block ground stitching
        self.L.stitch('GND', [(10, 20), (20, 20), (35, 5), (25, 30.5), (42, 20), (20.5, 20), (5, 35)])
        self.assertEqual([(v.x, v.y) for v in self.L.vias], [(20.0, 20.0), (5.0, 35.0)])

    def test_fanout_puts_a_via_beside_each_pad_of_the_net(self):
        L = pcb.Layout({'R1': R0603, 'R2': R0603}, 50, 40,
                       pins={('R1', '1'): 'GND', ('R1', '2'): 'X', ('R2', '1'): 'GND', ('R2', '2'): 'Y'})
        L.place('R1', 10, 20)
        L.place('R2', 30, 20)
        L.track('GND', 'F.Cu', 0.2, 'R2.1', (25, 20))       # R2's pad 1 has copper of its own already
        self.assertEqual(L.fanout('GND'), [])
        self.assertEqual([v.net for v in L.vias], ['GND'])
        v = L.vias[0]
        self.assertLess(v.x, 9.175 - 0.4)                    # outward, away from its part's other pad
        self.assertAlmostEqual(v.y, 20.0)
        self.assertEqual((L.tracks[-1].net, L.tracks[-1].points), ('GND', ((9.175, 20.0), (v.x, v.y))))

    def test_fanout_keeps_clear_of_other_copper(self):
        L = pcb.Layout({'R1': R0603}, 50, 40, pins={('R1', '1'): 'GND', ('R1', '2'): 'X'})
        L.place('R1', 10, 20)
        L.track('Y', 'F.Cu', 0.2, (8.4, 15), (8.4, 25))      # a line left of pad 1, where the via would go
        L.fanout('GND', clearance=lambda net: 0.2)
        (v, stub) = (L.vias[0], L.tracks[-1].points)
        self.assertGreaterEqual(pcb.to_segment((v.x, v.y), (8.4, 15), (8.4, 25)), 0.1 + v.size / 2 + 0.2 - 1e-9)
        self.assertGreater(min(abs(p[0] - 8.4) for p in stub), 0.1 + 0.125 + 0.2 - 1e-9)

    def test_fanout_from_a_fine_pitch_pin_keeps_to_the_pin_width(self):
        # U1's pin 5 (+3V3) between pins 4 and 6, 0.4 mm apart: a 0.25 mm track couldn't leave it
        L = pcb.Layout({'U1': QFN80}, 50, 40, pins={('U1', '4'): 'A', ('U1', '5'): '+3V3', ('U1', '6'): 'B'})
        L.place('U1', 20, 20)
        self.assertEqual(L.fanout('+3V3'), [])
        self.assertLessEqual(L.tracks[-1].width, 0.2)

    def test_fanout_stays_out_of_another_nets_zone(self):
        L = pcb.Layout({'R1': R0603}, 50, 40, pins={('R1', '1'): 'GND', ('R1', '2'): 'X'})
        L.place('R1', 10, 20)
        L.zone('Z', 'F.Cu', pcb.rect(7.0, 18.0, 8.6, 22.0))         # where the via would go, outward
        L.fanout('GND')
        v = L.vias[0]
        self.assertFalse(7.0 - 0.425 < v.x < 8.6 + 0.425 and 18.0 - 0.425 < v.y < 22.0 + 0.425, (v.x, v.y))

    def test_fanout_only_the_pads_asked_for_copper_or_not(self):
        L = pcb.Layout({'R1': R0603, 'R2': R0603}, 50, 40,
                       pins={('R1', '1'): 'S', ('R1', '2'): 'X', ('R2', '1'): 'S', ('R2', '2'): 'Y'})
        L.place('R1', 10, 20)
        L.place('R2', 30, 20)
        L.track('S', 'F.Cu', 0.2, 'R1.1', (5, 20))
        L.fanout('S', only={('R1', '1')})
        self.assertEqual([(v.net, v.x < 10) for v in L.vias], [('S', True)])      # R1's, though tracked; not R2's

    def test_fanout_inward_turns_toward_the_part(self):
        L = pcb.Layout({'U1': QFN80}, 50, 40, pins={('U1', '75'): 'S'})
        L.place('U1', 20, 20)
        (x, y) = L.pad('U1', '75')
        L.fanout('S', inward=True)
        v = L.vias[0]
        self.assertLess(math.hypot(v.x - 20, v.y - 20), math.hypot(x - 20, y - 20))

    def test_fanout_reports_a_pad_with_no_room(self):
        L = pcb.Layout({'R1': R0603}, 50, 40, pins={('R1', '1'): 'GND', ('R1', '2'): 'X'})
        L.place('R1', 10, 20)
        L.track('Y', 'F.Cu', 0.2, (8.4, 19.0), (8.4, 21.0), (10.0, 21.0), (10.0, 19.0), (8.4, 19.0))
        self.assertEqual(L.fanout('GND'), [('R1', '1')])
        self.assertEqual(L.vias, [])

    def test_a_label_moves_once(self):
        self.L.place('R1', 10, 20)
        self.L.label('R1', 0, -1.5)
        self.assertEqual(self.L.labels['R1'], (0.0, -1.5, 0.0))
        with self.assertRaises(ValueError):
            self.L.label('R1', 1, 1)

    def test_lines_only_off_copper(self):
        self.L.line('F.SilkS', 0.15, (0, 0), (1, 1), (2, 1))
        with self.assertRaises(ValueError):
            self.L.line('F.Cu', 0.15, (0, 0), (1, 1))

    def test_a_pair_keeps_its_pitch(self):
        self.L.place('R1', 0, 0)
        self.L.place('R2', 20, 0)
        self.L.pair('P', 'N', 'F.Cu', 0.225, 0.2, (1, -0.2125), (1, 0.2125), [(2, 0), (10, 0), (15, 5)],
                    (19, 4.7875), (19, 5.2125))
        (p, n) = (self.L.tracks[0].points, self.L.tracks[1].points)
        self.assertAlmostEqual(p[1][1] - n[1][1], -0.425, places=6)     # P left of a walk to the right: above
        # a right turn (east, then south-east on a screen whose y points down): P, on the left, runs outside
        self.assertAlmostEqual(pcb.length(p[1:-1]) - pcb.length(n[1:-1]), 4 * 0.2125 * 0.41421, places=4)


class TestGeometry(unittest.TestCase):
    def test_a_segment_clips_to_a_box(self):
        box = (0.0, 0.0, 10.0, 8.0)
        self.assertEqual(pcb.clip((2, 2), (4, 4), box), ((2.0, 2.0), (4.0, 4.0)))      # inside: as it was
        self.assertEqual(pcb.clip((5, 6), (5, 12), box), ((5.0, 6.0), (5.0, 8.0)))     # across the edge: cut there
        self.assertIsNone(pcb.clip((12, 1), (14, 5), box))                            # outside: gone

    def test_parallel_offsets_left_and_mitres(self):
        line = [(0, 0), (10, 0), (20, 10)]
        left = pcb.parallel(line, 0.5)
        self.assertEqual(left[0], (0.0, -0.5))
        self.assertAlmostEqual(left[-1][0] - 20, 0.5 * 0.7071, places=3)
        k = 0.5 / 0.92388                                   # a 45 degree bend: the mitre is d / cos(22.5)
        self.assertAlmostEqual(pcb.length([(10, 0), left[1]]), k, places=3)

    def test_inside(self):
        square = pcb.rect(0, 0, 10, 10)
        self.assertTrue(pcb.inside((5, 5), square))
        self.assertFalse(pcb.inside((15, 5), square))

    def test_fingerprint_moves_with_the_layout(self):
        L = pcb.Layout({'R1': R0603}, 50, 40)
        L.place('R1', 10, 20)
        before = pcb.fingerprint(L, {'X': [('R1', '1')]})
        self.assertEqual(before, pcb.fingerprint(L, {'X': [('R1', '1')]}))
        L.places['R1'] = (10.0, 21.0, 0.0)
        self.assertNotEqual(before, pcb.fingerprint(L, {'X': [('R1', '1')]}))


if __name__ == '__main__':
    unittest.main()
