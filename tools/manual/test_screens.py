# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

import glob
import os
import re
import tempfile
import unittest

from PIL import Image

import compose
import manual_paths
import screens
import setup_walk
import screen

NAMES = ('lock', 'lock-prompt', 'setup-about-1', 'setup-about-2', 'setup-customize', 'setup-menu',
         'setup-offline', 'setup-page1', 'setup-page2', 'setup-page3', 'setup-page4', 'setup-password',
         'setup-warning', 'splash')


def read(path):
    with open(path, 'rb') as stream:
        return stream.read()


class TestScreens(unittest.TestCase):

    def test_every_screen_is_written_at_640_by_480(self):
        with tempfile.TemporaryDirectory() as out:
            paths = screens.write_core_screens(out, '0.6.0', 'e3f4c94')
            self.assertEqual([os.path.basename(p) for p in paths], sorted(f'{n}-640.png' for n in NAMES))
            for path in paths:
                with Image.open(path) as image:
                    self.assertEqual(image.size, (640, 480), path)

    def test_about_shows_revision_a_and_the_builds_version_and_commit(self):
        (regen, _, _) = screen.setup_screens(identity=screens.identity('0.6.0', 'e3f4c94'))['about-1']
        rows = [setup_walk.row_text(regen, row).rstrip() for row in range(1, 25)]
        self.assertIn('About Liz4270', rows[0])
        self.assertTrue(rows[6].endswith('0.6.0'), rows[6])
        self.assertTrue(rows[7].endswith('e3f4c94'), rows[7])
        self.assertTrue(rows[8].endswith('Liz4270 rev A (ID 00)'), rows[8])

    def test_about_is_drawn_with_it(self):
        with tempfile.TemporaryDirectory() as out, tempfile.TemporaryDirectory() as alone:
            screens.write_core_screens(out, '0.6.0', 'e3f4c94')
            screen.write_setup_pngs(alone, 640, identity=screens.identity('0.6.0', 'e3f4c94'))
            for page in (1, 2):
                name = f'setup-about-{page}-640.png'
                self.assertEqual(read(os.path.join(out, name)), read(os.path.join(alone, name)), name)

    def test_the_splash_shows_the_builds_version_and_commit(self):
        with tempfile.TemporaryDirectory() as out, tempfile.TemporaryDirectory() as alone:
            screens.write_core_screens(out, '0.6.0+dev', 'e3f4c94-dirty')
            path = os.path.join(alone, 'splash-640.png')
            screen.write_splash_png(path, 640, version=b'0.6.0+dev', commit=b'e3f4c94-dirty')
            self.assertEqual(read(os.path.join(out, 'splash-640.png')), read(path))



class TestHostScreens(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.out = tempfile.TemporaryDirectory()
        cls.paths = screens.write_host_screens(cls.out.name)

    @classmethod
    def tearDownClass(cls):
        cls.out.cleanup()

    def test_every_host_figure_is_drawn_at_640_by_480(self):
        names = [os.path.basename(p) for p in self.paths]
        for name in screens.HOST_FIGURES:
            self.assertIn(f'{name}-640.png', names)
            with Image.open(os.path.join(self.out.name, f'{name}-640.png')) as image:
                self.assertEqual(image.size, (640, 480), name)

    def test_a_status_symbol_is_its_cells_of_the_status_line(self):
        for (name, (_, first, last, _)) in compose.STATUS_SYMBOLS.items():
            with Image.open(os.path.join(self.out.name, f'status-{name}-640.png')) as image:
                self.assertEqual(image.size, ((last - first + 1) * 8, 19), name)
        with Image.open(os.path.join(self.out.name, 'status-wait-640.png')) as image:
            self.assertEqual(image.size, (32, 19))
            self.assertGreater(len(image.getcolors(1 << 16)), 1, 'the symbols are drawn')

    def test_a_figures_options_reach_the_renderer(self):
        with tempfile.TemporaryDirectory() as out:
            plain = os.path.join(out, 'plain.png')
            screens.draw(compose.colours(), plain)
            for options in ({'settings': {'mono': True}}, {'ruler': 'cursor', 'settings': {'ruler_style': 2}},
                            {'dimmed': True}):
                path = os.path.join(out, 'other.png')
                screens.draw(compose.colours(), path, **options)
                self.assertNotEqual(read(path), read(plain), options)

    def test_every_screen_the_book_asks_for_is_drawn(self):
        with tempfile.TemporaryDirectory() as out:
            drawn = {os.path.basename(p)[:-len('-640.png')]
                     for p in screens.write_core_screens(out, '0.6.0', 'e3f4c94') + self.paths}
        asked = set()
        for path in glob.glob(os.path.join(manual_paths.MANUAL, '**', '*.typ'), recursive=True):
            with open(path, encoding='utf-8') as stream:
                asked |= set(re.findall(r'(?:screen|cells)-image\("([^"]+)"', stream.read()))
        self.assertIn('setup-menu', asked)
        self.assertEqual(asked - drawn, set())


if __name__ == '__main__':
    unittest.main()
