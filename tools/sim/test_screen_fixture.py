# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The screen fixture file that snap writes and the manual draws (#136)."""

import json
import os
import re
import tempfile
import unittest

import paths  # noqa: F401
import screen_fixture
from screen_fixture import Fixture

RECORDED = {'when': '2026-10-18', 'host': 'MVS/CE', 'how': 'tools/sim snap, driven by oec master'}
SIZES = {2: 2000, 3: 2640, 4: 3520}


def fixture(model, eab=True):
    size = SIZES[model]
    regen = bytes((i * 7) & 0xFF for i in range(size))
    return Fixture(model, 81, 0b010, regen, bytes((i * 3) & 0xFF for i in range(size)) if eab else None, RECORDED)


class TestScreenFixture(unittest.TestCase):

    def setUp(self):
        out = tempfile.TemporaryDirectory()
        self.addCleanup(out.cleanup)
        self.path = os.path.join(out.name, 'screen.json')

    def written(self, f):
        screen_fixture.write(self.path, f)
        with open(self.path, encoding='utf-8') as stream:
            return json.load(stream)

    def rewrite(self, **changes):
        """The fixture file of a Model 2 screen, with some of its fields changed."""
        data = self.written(fixture(2))
        data.update(changes)
        with open(self.path, 'w', encoding='utf-8') as stream:
            json.dump(data, stream)

    def test_a_fixture_round_trips_at_each_model(self):
        for model in (2, 3, 4):
            for eab in (True, False):
                with self.subTest(model=model, eab=eab):
                    f = fixture(model, eab)
                    self.assertEqual(len(f.regen), SIZES[model])
                    screen_fixture.write(self.path, f)
                    self.assertEqual(screen_fixture.read(self.path), f)

    def test_rows_are_one_hex_string_per_80_bytes(self):
        for (model, rows) in ((2, 25), (4, 44)):
            data = self.written(fixture(model))
            self.assertEqual(len(data['regen']), rows)
            self.assertEqual(len(data['eab']), rows)
            self.assertTrue(all(len(row) == 160 and row == row.lower() for row in data['regen']))

    def test_the_file_reads_in_order_with_its_licence(self):
        data = self.written(fixture(2, eab=False))
        self.assertEqual(list(data), ['copyright', 'license', 'recorded', 'model', 'ac', 'control', 'regen', 'eab'])
        self.assertEqual(data['license'], 'CC-BY-4.0')
        self.assertIsNone(data['eab'])
        with open(self.path, encoding='utf-8') as stream:
            self.assertTrue(stream.read().endswith('}\n'))

    def test_the_copyright_is_the_recordings_year(self):
        data = self.written(fixture(2)._replace(recorded={**RECORDED, 'when': '2027-01-02'}))
        self.assertEqual(data['copyright'], 'Copyright (c) 2027, CoffeeMuse')

    def test_a_file_that_isnt_a_fixture_at_all_is_refused_naming_it(self):
        for text in ('{"model": 2,', '[1, 2]', ''):
            with self.subTest(text=text):
                with open(self.path, 'w', encoding='utf-8') as stream:
                    stream.write(text)
                with self.assertRaisesRegex(ValueError, re.escape(self.path)):
                    screen_fixture.read(self.path)

    def test_a_wrong_file_is_refused_naming_it(self):
        rows = self.written(fixture(2))['regen']
        for changes in ({'regen': rows[:-1] + [rows[-1][:158]]}, {'regen': rows[:-1]}, {'model': 5},
                        {'eab': rows[:-1]}, {'ac': 2000}, {'regen': rows[:-1] + ['zz' * 80]}):
            with self.subTest(changes=list(changes)):
                self.rewrite(**changes)
                with self.assertRaisesRegex(ValueError, re.escape(self.path)):
                    screen_fixture.read(self.path)


if __name__ == '__main__':
    unittest.main()
