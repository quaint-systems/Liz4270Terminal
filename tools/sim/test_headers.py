# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Source files and CI workflows open with their copyright and license header
(#78, #136).

Ours carry the ISC header, under the shebang if there is one, then a blank line:

    // Copyright (c) 2026, CoffeeMuse
    // SPDX-License-Identifier: ISC

Python, CMake and TOML comment with #, PIO with ;. The user manual's sources under docs/manual/ carry
CC-BY-4.0 in place of ISC, as the manual is licensed (docs/manual/LICENSE). The baked font is a
Modified Version of 3270font, so it carries its copyright lines and OFL-1.1 instead (NOTICE). firmware/vendor/ and the SDK's
pico_sdk_import.cmake aren't ours. Untracked files count too, so a new one fails here before it is
committed.

OpenSCAD sources under hardware/ are hardware, so they carry CERN-OHL-P-2.0 in place of ISC (#134);
make_exports.py writes the same into the board's OpenSCAD export.
"""

import os
import re
import shutil
import subprocess
import unittest

from paths import ROOT

NOT_OURS = ('firmware/vendor/', 'firmware/pico_sdk_import.cmake')
COMMENT = {'.c': '//', '.h': '//', '.pio': ';', '.py': '#', '.cmake': '#', '.typ': '//', '.toml': '#', '.yml': '#'}
MANUAL = 'docs/manual/'  # CC BY 4.0, not ISC (#136)
OFL = {
    'firmware/core/font_3270.c': 'tools/sim/bake_font.py',
}
OFL_HEADER = [
    '// Copyright 2011-2021 The 3270font Project Authors (https://github.com/rbanffy/3270font)',
    '// Copyright 2022 The 3270font Authors (https://github.com/rbanffy/3270font)',
    '// SPDX-License-Identifier: OFL-1.1',
]


def comment(path):
    """The line comment for path's language, or None if it isn't source."""
    if os.path.basename(path) == 'CMakeLists.txt':
        return '#'
    return COMMENT.get(os.path.splitext(path)[1])


def sources():
    """Our source files and workflows, tracked or not yet added."""
    listed = subprocess.run(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard',
                             'firmware', 'tools', MANUAL, '.github/workflows'], cwd=ROOT, capture_output=True, check=True).stdout
    paths = sorted(set(listed.decode('utf-8').split('\0')))
    return [path for path in paths
            if path and comment(path) and not path.startswith(NOT_OURS) and os.path.isfile(os.path.join(ROOT, path))]


def header(path):
    """The file's first lines after any shebang, up to the first blank one."""
    with open(os.path.join(ROOT, path), encoding='utf-8') as stream:
        lines = stream.read().split('\n')
    if lines[0].startswith('#!'):
        lines = lines[1:]
    return lines[:lines.index('')] if '' in lines else lines


def our_header(c, license='ISC'):
    return [rf'{re.escape(c)} Copyright \(c\) 20\d\d(-20\d\d)?, CoffeeMuse',
            rf'{re.escape(c)} SPDX-License-Identifier: {re.escape(license)}']


def wanted(path):
    """The header path should open with: the manual's CC BY 4.0, or ISC."""
    return our_header(comment(path), 'CC-BY-4.0' if path.startswith(MANUAL) else 'ISC')


HARDWARE = ('hardware/case', 'hardware/board/export')


def hardware_sources():
    """Our OpenSCAD files under hardware/, tracked or not yet added."""
    listed = subprocess.run(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard', *HARDWARE],
                            cwd=ROOT, capture_output=True, check=True).stdout
    paths = sorted(set(listed.decode('utf-8').split('\0')))
    return [path for path in paths if path.endswith('.scad') and os.path.isfile(os.path.join(ROOT, path))]


CERN_HEADER = [r'// Copyright \(c\) 20\d\d(-20\d\d)?, CoffeeMuse', r'// SPDX-License-Identifier: CERN-OHL-P-2\.0']


@unittest.skipUnless(shutil.which('git') and os.path.exists(os.path.join(ROOT, '.git')), 'needs a git checkout')
class TestHeaders(unittest.TestCase):

    def setUp(self):
        self.sources = sources()

    def test_the_sources_are_found(self):
        # A wrong path or a git failure would otherwise leave nothing to check.
        self.assertGreater(len(self.sources), 100)
        for path in ('firmware/src/main.c', 'firmware/src/coax_term.pio', 'firmware/CMakeLists.txt',
                     'firmware/check_flash_sections.cmake', 'tools/sim/core.py', '.github/workflows/firmware.yml',
                     'docs/manual/edition.toml'):
            self.assertIn(path, self.sources)
        for path in ('firmware/vendor/coax-tcp/coax.pio', 'firmware/pico_sdk_import.cmake'):
            self.assertNotIn(path, self.sources)

    def test_ours_carry_our_header(self):
        missing = []
        for path in self.sources:
            if path in OFL:
                continue
            got = header(path)
            want = wanted(path)
            if len(got) != len(want) or not all(re.fullmatch(w, g) for (w, g) in zip(want, got)):
                missing.append(path)
        self.assertEqual(missing, [], 'these need the header (two lines, then a blank line)')

    def test_the_manual_is_cc_by_and_the_rest_isc(self):
        for (path, line) in (('docs/manual/style.typ', '// SPDX-License-Identifier: CC-BY-4.0'),
                             ('docs/manual/edition.toml', '# SPDX-License-Identifier: CC-BY-4.0'),
                             ('tools/manual/build.py', '# SPDX-License-Identifier: ISC')):
            with self.subTest(path=path):
                self.assertRegex(line, '^' + wanted(path)[1] + '$')

    def test_the_hardware_sources_carry_the_cern_header(self):
        sources = hardware_sources()
        self.assertIn('hardware/board/export/liz4270-board.scad', sources)
        missing = [path for path in sources
                   if len(header(path)) != 2 or not all(re.fullmatch(w, g) for (w, g) in zip(CERN_HEADER,
                                                                                                header(path)))]
        self.assertEqual(missing, [], 'these need the CERN-OHL-P header (two lines, then a blank line)')

    def test_the_baked_font_carries_the_ofl_header(self):
        for (path, generator) in OFL.items():
            with self.subTest(path=path):
                self.assertIn(path, self.sources)
                self.assertEqual(header(path), OFL_HEADER)
            with self.subTest(generator=generator), open(os.path.join(ROOT, generator), encoding='utf-8') as stream:
                self.assertIn('// SPDX-License-Identifier: OFL-1.1', stream.read())


if __name__ == '__main__':
    unittest.main()
