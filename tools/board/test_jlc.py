# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""make_jlc: the order files against the spec's assembly decisions and plan 2's spin-1 choices."""

import csv
import os
import tempfile
import unittest
import zipfile

import paths

PCB = os.path.join(paths.BOARD, 'liz4270.kicad_pcb')
HAVE = os.path.exists(paths.KICAD_CLI) and os.path.exists(PCB)
# Not on JLC's order: hand-fitted (T1), not fitted on rev A (J2, R3, U5, C26, C61), bare pads and holes (TP, H)
OFF = {'T1', 'J2', 'R3', 'U5', 'C26', 'C61', 'TP1', 'TP2', 'TP3', 'TP4', 'TP5', 'H1', 'H2', 'H3', 'H4'}
THROUGH_HOLE = {'J3', 'J4', 'J5', 'J6', 'J7', 'SW1', 'SW2'}           # spec: JLC fits these too


@unittest.skipUnless(HAVE, 'needs KiCad 10 and the board')
class TestJlc(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import make_jlc
        cls.make_jlc = make_jlc
        cls.tmp = tempfile.TemporaryDirectory()
        (cls.files, cls.fitted) = make_jlc.write(cls.tmp.name)
        with open(os.path.join(cls.tmp.name, 'liz4270-revA-bom.csv'), newline='', encoding='utf-8') as stream:
            cls.bom = list(csv.DictReader(stream))
        with open(os.path.join(cls.tmp.name, 'liz4270-revA-cpl.csv'), newline='', encoding='utf-8') as stream:
            cls.cpl = {row['Designator']: row for row in csv.DictReader(stream)}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_bom_line_has_an_lcsc_number(self):
        for row in self.bom:
            self.assertRegex(row['LCSC Part #'], r'^C\d+$', row)

    def test_bom_and_cpl_list_the_same_parts(self):
        in_bom = {ref for row in self.bom for ref in row['Designator'].split(',')}
        self.assertEqual(in_bom, set(self.cpl))

    def test_hand_fitted_unfitted_and_bare_parts_stay_off(self):
        self.assertFalse(OFF & set(self.cpl))

    def test_through_hole_parts_are_on_the_order(self):
        self.assertLessEqual(THROUGH_HOLE, set(self.cpl))

    def test_rotation_fixes(self):
        for (ref, fix) in self.make_jlc.ROTATION_FIX.items():
            pos = self.make_jlc.placements(self.tmp.name)[ref]
            self.assertEqual(float(self.cpl[ref]['Rotation']), (float(pos['Rot']) + fix) % 360, ref)

    def test_j6_sits_back_from_the_edge(self):
        # JLC's preview (Oct 10, 2026) drew its USB-C model 1.6 mm toward the edge, its leads off their pads: the CPL
        # moves it 1.6 mm into the board, which is up in the CPL's frame (KiCad's page, y up)
        pos = self.make_jlc.placements(self.tmp.name)['J6']
        self.assertAlmostEqual(float(self.cpl['J6']['Mid X']), float(pos['PosX']), places=4)
        self.assertAlmostEqual(float(self.cpl['J6']['Mid Y']), float(pos['PosY']) + 1.6, places=4)

    def test_gerbers_are_four_layers_and_the_drills(self):
        with zipfile.ZipFile(os.path.join(self.tmp.name, 'liz4270-revA-gerbers.zip')) as z:
            names = z.namelist()
        for ending in ('.gtl', '.g1', '.g2', '.gbl', '.gm1', '.gts', '.gbs', '.gto', '.gtp', '-PTH.drl', '-NPTH.drl'):
            self.assertTrue(any(n.endswith(ending) for n in names), ending)
        self.assertFalse([n for n in names if n.endswith('.gbrjob')])

    def test_the_planes_are_filled_in_the_plots(self):
        # the board is saved with its zones unfilled, so only the plot's own fill puts the planes and pours in: a
        # Gerber without regions (G36) would order a board with no ground or +3V3 plane
        with zipfile.ZipFile(os.path.join(self.tmp.name, 'liz4270-revA-gerbers.zip')) as z:
            for ending in ('.g1', '.g2', '.gtl', '.gbl'):
                (name,) = [n for n in z.namelist() if n.endswith(ending)]
                self.assertTrue(b'G36' in z.read(name), f'{name} has no regions')

    def test_the_committed_files_are_current(self):
        self.assertEqual(self.make_jlc.stale(), [])

    def test_a_changed_gerber_makes_the_zip_stale(self):
        # same file names, different copper: a board change that make_jlc.py wasn't rerun after
        with tempfile.TemporaryDirectory() as old:
            for name in ('liz4270-revA-bom.csv', 'liz4270-revA-cpl.csv'):
                with open(os.path.join(self.tmp.name, name), 'rb') as a, open(os.path.join(old, name), 'wb') as b:
                    b.write(a.read())
            zname = 'liz4270-revA-gerbers.zip'
            with zipfile.ZipFile(os.path.join(self.tmp.name, zname)) as a, \
                    zipfile.ZipFile(os.path.join(old, zname), 'w') as b:
                for n in a.namelist():
                    data = a.read(n)
                    b.writestr(n, data.replace(b'M02*', b'G04 a track that moved since*\nM02*') if n.endswith('.gtl')
                               else data)
            self.assertEqual(self.make_jlc.stale(old), [zname])


if __name__ == '__main__':
    unittest.main()
