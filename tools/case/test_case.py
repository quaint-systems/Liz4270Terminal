# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The case against the assembled board's own 3D model and the plugs' bodies, each of its features by probing, and
its committed STLs (#134; docs/superpowers/specs/2026-10-14-case-design.md, "Tests").

A probe is a small body placed where a feature should be solid or clear, and scad.overlap() measures the volume it
shares with a part. Under TOUCH counts as faces touching, not an overlap: the board rests on the standoffs and the
bosses, and the inlay and the light pipes sit in their holes, by design. Coordinates are the case's frame, the
board's with y negated (hardware/case/dims.scad).
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import paths
import scad

HAVE = scad.version() is not None and os.path.exists(paths.KICAD_CLI)
TOUCH = 0.001                   # mm^3
_board = []


def board():
    """An import() of the assembled board's STL, exported once per run."""
    if not _board:
        tmp = tempfile.mkdtemp()
        _board.extend([tmp, f'import("{scad.board_stl(tmp)}")'])
    return _board[1]


def tearDownModule():
    if _board:
        shutil.rmtree(_board[0])


class Probing(unittest.TestCase):
    def assertClear(self, a, b):
        v = scad.overlap(a, b)
        self.assertLess(v, TOUCH, f'{a} and {b} share {v:.3f} mm^3')

    def assertSolid(self, a, b):
        v = scad.overlap(a, b)
        self.assertGreater(v, TOUCH, f'{a} and {b} share nothing')

    def assertBounds(self, body, low, high):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, 'bounds.stl')
            r = scad.build(f'{body};', out, hard=False)
            self.assertEqual(r.returncode, 0, r.stderr)
            (lo, hi) = scad.bounds(out)
        for (got, want) in zip(lo + hi, tuple(low) + tuple(high)):
            self.assertAlmostEqual(got, want, places=2)


@unittest.skipUnless(HAVE, 'needs OpenSCAD and KiCad 10')
class TestHarness(Probing):
    def test_a_shared_cube_measures_its_volume(self):
        self.assertAlmostEqual(scad.overlap('cube(2)', 'cube(3)'), 8.0, places=3)

    def test_the_board_model_loads(self):
        # a block inside the USB-A stack: had the import come in empty, every fit test would pass for nothing
        self.assertSolid('translate([44, -75, 5]) cube(8)', board())

    def test_free_air_is_clear(self):
        self.assertClear('translate([20, -10, 25]) cube(8)', board())

    def test_the_version_is_read(self):
        self.assertRegex(scad.version(), r'^\d{4}\.\d{2}\.\d{2}$')

    def test_a_crash_at_start_is_run_again(self):
        # OpenSCAD 2026.10.11 sometimes dies of SIGSEGV as it starts (scad.ATTEMPTS); this one does, the first time
        want = scad.version()
        real = paths.OPENSCAD
        with tempfile.TemporaryDirectory() as tmp:
            fake = os.path.join(tmp, 'openscad')
            with open(fake, 'w', encoding='utf-8') as stream:
                stream.write(f'#!/bin/sh\nif [ ! -e "{tmp}/crashed" ]; then touch "{tmp}/crashed"; kill -SEGV $$; fi\n'
                             f'exec "{real}" "$@"\n')
            os.chmod(fake, 0o755)
            paths.OPENSCAD = fake
            try:
                self.assertEqual(scad.version(), want)
            finally:
                paths.OPENSCAD = real

    def test_an_unknown_module_is_an_error(self):
        # OpenSCAD only warns and leaves it out, and an intersection with nothing left out is the probe itself
        with self.assertRaises(RuntimeError):
            scad.overlap('no_such_part()', 'cube(1)')


@unittest.skipUnless(HAVE, 'needs OpenSCAD and KiCad 10')
class TestText(Probing):
    def test_the_font_is_where_labels_scad_loads_it(self):
        with open(os.path.join(paths.CASE, 'labels.scad'), encoding='utf-8') as stream:
            line = next(l.strip() for l in stream if l.startswith('use <') and l.rstrip().endswith('.ttf>'))
        font = os.path.normpath(os.path.join(paths.CASE, line[len('use <'):-1]))
        self.assertTrue(os.path.exists(font), font)

    def test_the_text_builds_without_warnings(self):
        # labels.scad asserts, inside its modules, that 3270font loaded and that the connector labels fit
        with tempfile.TemporaryDirectory() as tmp:
            r = scad.build('back_labels();\nlinear_extrude(1) top_text();', os.path.join(tmp, 'text.stl'))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_the_labels_lie_in_the_back_face(self):
        # cut DEBOSS (0.6) into the back face at y = -83.5, and no deeper
        self.assertSolid('back_labels()', 'translate([-5, -83.5, -9]) cube([110, 0.6, 12])')
        self.assertClear('back_labels()', 'translate([-5, -82.9, -9]) cube([110, 5, 12])')


@unittest.skipUnless(HAVE, 'needs OpenSCAD and KiCad 10')
class TestBase(Probing):
    def test_it_misses_the_board(self):
        for probe in ('false', 'true'):
            with self.subTest(debug_probe_hole=probe):
                self.assertClear(f'base({probe})', board())

    def test_it_misses_the_plugs(self):
        self.assertClear('base()', 'plug_keepouts()')

    def test_the_board_lowers_straight_in(self):
        for dz in (1, 3, 6, 10, 15, 25):
            with self.subTest(dz=dz):
                self.assertClear('base()', f'translate([0, 0, {dz}]) {board()}')

    def test_the_screw_holes(self):
        self.assertClear('base()', 'translate([96, -66, -9]) cylinder(d = 3.2, h = 9.5, $fn = 16)')
        self.assertClear('base()', 'translate([96, -66, -8.5]) cylinder(d = 6.0, h = 3.0, $fn = 32)')   # counterbore
        self.assertSolid('base()', 'translate([98.5, -66, -3]) cube([0.5, 0.5, 2])')                   # standoff

    def test_the_foot_recesses(self):
        self.assertClear('base()', 'translate([14, -2.75, -8.5]) cylinder(d = 10, h = 0.9, $fn = 32)')

    def test_the_rim_stops_below_the_seam_and_the_lip_rises(self):
        self.assertClear('base()', 'translate([20, 2.1, 1.35]) cube([10, 1.4, 0.2])')   # outside the lip, z 1.3-1.6
        self.assertSolid('base()', 'translate([30.9, 0.6, 1.5]) cube([3, 1, 1.5])')     # the lip, at the front

    def test_the_plug_notches(self):
        self.assertClear('base()', 'translate([27, -84, -0.3]) cube([6, 4, 1.5])')      # under USB-C's plug
        self.assertSolid('base()', 'translate([6, -83, 0.5]) cube([8, 2, 0.6])')        # the rim under the BNC

    def test_the_probe_notch(self):
        self.assertClear('base(true)', 'translate([30.9, 0, 1.4]) cube([3, 4, 3.1])')

    def test_the_labels_are_cut(self):
        self.assertClear('base()', 'back_labels()')

    def test_the_outside(self):
        self.assertBounds('base()', (-3.5, -83.5, -8.0), (103.5, 3.5, 3.3))


@unittest.skipUnless(HAVE, 'needs OpenSCAD and KiCad 10')
class TestLid(Probing):
    HOLES = ((4, -4), (96, -4), (96, -66), (4, -46))

    def test_it_misses_the_board(self):
        for probe in ('false', 'true'):
            with self.subTest(debug_probe_hole=probe):
                self.assertClear(f'lid({probe})', board())

    def test_it_misses_the_plugs(self):
        self.assertClear('lid()', 'plug_keepouts()')

    def test_it_lowers_straight_on(self):
        for dz in (1, 3, 6, 10, 15, 25):
            with self.subTest(dz=dz):
                self.assertClear(f'translate([0, 0, {dz}]) lid()', board())

    def test_it_misses_the_base(self):
        for probe in ('false', 'true'):
            with self.subTest(debug_probe_hole=probe):
                self.assertClear(f'lid({probe})', f'base({probe})')

    def test_the_bosses(self):
        for (x, y) in self.HOLES:
            with self.subTest(x=x, y=y):
                self.assertClear('lid()', f'translate([{x}, {y}, 1.7]) cylinder(d = 2.3, h = 9.8, $fn = 16)')
                self.assertSolid('lid()', f'translate([{x + 2.5}, {y - 0.5}, 5]) cube(1)')
                self.assertSolid('lid()', f'translate([{x}, {y}, 21]) cylinder(d = 2, h = 1.5, $fn = 16)')

    def test_bootsel_has_a_pinhole(self):
        self.assertClear('lid()', 'translate([85, -79.9, 5.1]) rotate([90, 0, 0]) cylinder(d = 1.2, h = 5, $fn = 16)')
        self.assertSolid('lid()', 'translate([85, -82, 8.5]) cube(1, center = true)')

    def test_reset_has_a_flexure(self):
        self.assertSolid('lid()', 'translate([93.6, -80.45, 4.1]) cube([2, 0.2, 2])')   # the nub
        self.assertClear('lid()', 'translate([92.6, -80.15, 3.6]) cube([4, 0.2, 3])')   # NUB_GAP short of the tip
        self.assertClear('lid()', 'translate([91.05, -84, 4]) cube([0.2, 4, 11])')      # the slits
        self.assertClear('lid()', 'translate([97.95, -84, 4]) cube([0.2, 4, 11])')
        self.assertSolid('lid()', 'translate([94.1, -81.6, 8]) cube(1)')                # the tongue
        self.assertClear('lid()', 'translate([92, -83.6, 8]) cube([5, 1.7, 1])')        # the well, 1.8 deep

    def test_the_bnc_slot_is_open_below(self):
        self.assertClear('lid()', 'translate([6, -84, 1.5]) cube([8, 4, 1])')

    def test_the_probe_notch(self):
        self.assertSolid('lid()', 'translate([30.9, 1, 1.7]) cube([3, 2, 2.8])')
        self.assertClear('lid(true)', 'translate([30.9, 0, 1.4]) cube([3, 4, 3.1])')

    def test_the_outside(self):
        self.assertBounds('lid()', (-3.5, -83.5, 1.6), (103.5, 3.5, 22.55))


@unittest.skipUnless(HAVE, 'needs OpenSCAD and KiCad 10')
class TestLidTop(Probing):
    PIPES = ((29.25, -46.5), (32.0, -24.3))
    SPEAKER = 'linear_extrude(4.8) hull() for (s = [-1, 1]) translate([s * 5, 0]) circle(d = 20, $fn = 64)'

    def test_the_pipes_and_the_inlay_miss_the_board(self):
        for body in ('light_pipes_in_place()', 'inlay()'):
            with self.subTest(body=body):
                self.assertClear(body, board())

    def test_the_pipes_and_the_inlay_fit_the_lid(self):
        for body in ('light_pipes_in_place()', 'inlay()'):
            with self.subTest(body=body):
                self.assertClear(body, 'lid()')

    def test_the_inlay_is_there(self):
        self.assertSolid('inlay()', 'translate([-5, -90, 21.9]) cube([110, 100, 0.7])')

    def test_the_pipe_holes_and_sleeves(self):
        for (x, y) in self.PIPES:
            with self.subTest(x=x, y=y):
                self.assertClear('lid()', f'translate([{x}, {y}, 3.8]) cylinder(d = 3.0, h = 20, $fn = 24)')
                self.assertSolid('lid()', f'translate([{x + 1.9}, {y}, 10]) cube([0.4, 0.4, 1])')

    def test_the_speaker_fits_its_pocket(self):
        self.assertClear('lid()', f'translate([74, -14, 14.75]) {self.SPEAKER}')
        self.assertSolid('lid()', 'translate([89.55, -14, 16]) cube([0.5, 0.5, 1])')     # the pocket's wall
        self.assertSolid('lid()', 'translate([73, -4.2, 14.5]) cube([2, 0.4, 0.2])')      # a hook, under its back

    def test_the_speaker_tabs_bend(self):
        # each tab hangs free from the top's inner face, slit either side and thinned, so it bends without cracking
        for (y, side) in ((-14 + 10.4, 1), (-14 - 11.6, -1)):
            with self.subTest(side=side):
                self.assertClear('lid()', f'translate([77.2, {y}, 18.7]) cube([0.2, 1.2, 0.8])')       # a slit, at the top
        self.assertClear('lid()', 'translate([72, -14 + 11.1, 15]) cube([4, 0.6, 4])')                  # outside the tab
        self.assertSolid('lid()', 'translate([72, -14 + 10.2, 15]) cube([4, 0.6, 4])')                  # the tab

    def test_a_thicker_speaker_still_seats_and_the_hooks_hold_it(self):
        self.assertClear('lid()', f'translate([74, -14, 14.65]) linear_extrude(4.9) hull() '
                                  f'for (s = [-1, 1]) translate([s * 5, 0]) circle(d = 20, $fn = 64)')   # 0.1 mm over
        self.assertSolid('lid()', 'translate([73, -14 + 9.75, 14.45]) cube([2, 0.2, 0.1])')             # under its edge

    def test_the_grille(self):
        self.assertClear('lid()', 'translate([74, -14, 19]) cylinder(d = 1.5, h = 5, $fn = 16)')   # the middle hole
        self.assertSolid('lid()', 'translate([75.5, -12.9, 20]) cube([0.2, 0.2, 2])')             # between holes


MAKE_CASE = os.path.join(paths.HERE, 'make_case.py')


def openscad_case(*defines):
    """case.scad built with -D defines into a scratch STL; the CompletedProcess."""
    with tempfile.TemporaryDirectory() as tmp:
        args = ['--hardwarnings', '-o', os.path.join(tmp, 'part.stl'), '--export-format', 'binstl']
        for d in defines:
            args += ['-D', d]
        return scad.run(args + [os.path.join(paths.CASE, 'case.scad')])


@unittest.skipUnless(HAVE, 'needs OpenSCAD and KiCad 10')
class TestBuild(unittest.TestCase):
    def test_every_part_builds_without_warnings(self):
        for part in ('base', 'lid', 'inlay', 'light_pipe'):
            for probe in ('false', 'true'):
                with self.subTest(part=part, debug_probe_hole=probe):
                    r = openscad_case(f'part="{part}"', f'debug_probe_hole={probe}')
                    self.assertEqual(r.returncode, 0, r.stderr)

    def test_an_unknown_part_fails(self):
        r = openscad_case('part="lids"')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('no part called lids', r.stderr)

    def test_the_stls_are_current(self):
        r = subprocess.run([sys.executable, MAKE_CASE, '--check'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_the_inlay_lies_in_the_lids_cut_as_printed(self):
        # Bambu Studio loads the two as one object's parts, so they must share a frame: both upside down, on the bed
        (lid_lo, lid_hi) = scad.bounds(os.path.join(paths.STL, 'lid.stl'))
        (inlay_lo, inlay_hi) = scad.bounds(os.path.join(paths.STL, 'inlay.stl'))
        self.assertAlmostEqual(lid_lo[2], 0.0, places=3)
        self.assertAlmostEqual(inlay_lo[2], 0.0, places=3)
        self.assertAlmostEqual(inlay_hi[2], 0.6, places=3)
        for i in (0, 1):
            self.assertGreater(inlay_lo[i], lid_lo[i])
            self.assertLess(inlay_hi[i], lid_hi[i])


class TestRun(unittest.TestCase):
    def test_the_users_own_fonts_stay_out(self):
        # a 3270font in ~/Library/Fonts has the repo's subset's family name, and OpenSCAD would draw in it instead
        real = paths.OPENSCAD
        with tempfile.TemporaryDirectory() as tmp:
            fake = os.path.join(tmp, 'openscad')
            with open(fake, 'w', encoding='utf-8') as stream:
                stream.write('#!/bin/sh\necho "$HOME"\n')
            os.chmod(fake, 0o755)
            paths.OPENSCAD = fake
            try:
                home = scad.run([]).stdout.strip()
            finally:
                paths.OPENSCAD = real
        self.assertTrue(home)
        self.assertNotEqual(home, os.path.expanduser('~'))


class TestVersion(unittest.TestCase):
    def test_a_different_openscad_is_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = os.path.join(tmp, 'openscad')
            with open(fake, 'w', encoding='utf-8') as stream:
                stream.write('#!/bin/sh\necho "OpenSCAD version 2021.01"\n')
            os.chmod(fake, 0o755)
            r = subprocess.run([sys.executable, MAKE_CASE, '--check'], capture_output=True, text=True,
                               env={**os.environ, 'OPENSCAD': fake})
        self.assertEqual(r.returncode, 1)
        self.assertIn('OpenSCAD 2021.01', r.stdout)
        self.assertIn(f'built with {paths.OPENSCAD_VERSION}', r.stdout)
        self.assertNotIn('stale:', r.stdout)


if __name__ == '__main__':
    unittest.main()
