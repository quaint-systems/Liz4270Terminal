# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""SetUp's About pages (#126): bake_about.py's paging and C, the baked text against LICENSES/, NOTICE and the
display codes, and about_audit.py's reading of a build."""

import os
import re
import tempfile
import unittest

import about_audit
import bake_about
import core
from bake_about import Credit, Group, Page
from display_codes import MAIN, PLACEHOLDER
from paths import ROOT

GLYPHS = {glyph for (code, glyph) in MAIN.items() if code < 0xC0 and glyph != PLACEHOLDER}
A = Group('A', 'A License', 'a', ('C1', 'C2'))
B = Group('B', 'B License', 'b', ('C3',))


def words(lines):
    return ' '.join(lines).split()


class TestPaging(unittest.TestCase):
    def test_each_license_starts_a_new_page_with_its_copyright_lines(self):
        pages = bake_about.pages((A, B), {'A': ['t1', 't2'], 'B': ['u1']})
        self.assertEqual(pages, [Page('A License: a', ('C1', 'C2', '', 't1', 't2')),
                                 Page('B License: b', ('C3', '', 'u1'))])

    def test_a_long_license_continues_on_pages_of_18(self):
        text = [f't{i}' for i in range(30)]
        pages = bake_about.pages((A,), {'A': text})
        self.assertEqual([p.heading for p in pages], ['A License: a', 'A License: a (continued)'])
        self.assertEqual(len(pages[0].lines), 18)
        self.assertEqual(words(pages[0].lines + pages[1].lines), words(['C1', 'C2'] + text))

    def test_no_page_starts_or_ends_blank(self):
        # C1, C2, the blank and t0-t13 are 17 lines, so the paragraph break is page 1's 18th: dropped from its
        # end, and from page 2's start.
        text = [f't{i}' for i in range(14)] + [''] + ['u1', 'u2']
        pages = bake_about.pages((A,), {'A': text})
        self.assertEqual(len(pages[0].lines), 17)
        self.assertEqual(pages[0].lines[-1], 't13')
        self.assertEqual(pages[1].lines, ('u1', 'u2'))

    def test_a_long_copyright_line_wraps_with_a_two_space_indent(self):
        line = 'Copyright 2011-2021 The 3270font Project Authors (https://github.com/rbanffy/3270font)'
        lines = bake_about.group_lines(Group('X', 'X', 'x', (line,)), [])
        self.assertTrue(all(len(l) <= 78 for l in lines))
        self.assertTrue(lines[1].startswith('  ') and not lines[1].startswith('   '))
        self.assertEqual(words(lines), line.split())

    def test_c_strings_escape_latin_1_and_quotes(self):
        self.assertEqual(bake_about.c_string('Hübner'), '"H\\xfc" "bner"')
        self.assertEqual(bake_about.c_string('a"b\\c'), '"a\\"b\\\\c"')

    def test_a_character_with_no_display_code_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'U\\+00A9'):
            bake_about.pages((Group('A', 'A License', 'a', ('\u00a9 2026 X',)),), {'A': []})

    def test_text_wider_than_its_columns_is_refused(self):
        with self.assertRaisesRegex(ValueError, '79 columns, over 78'):
            bake_about.pages((A,), {'A': ['x' * 79]})
        with self.assertRaisesRegex(ValueError, 'over 80'):
            bake_about.pages((Group('A', 'A License', 'a' * 70, ('C1',)),), {'A': []})

    def test_a_character_outside_latin_1_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'U\\+2019'):
            bake_about.c_string('it’s')


class TestBakedText(unittest.TestCase):
    def test_the_committed_files_are_current(self):
        self.assertEqual(bake_about.stale(), [])

    def test_the_header_counts_the_tables(self):
        about = core.constants('about_text.h', 'ABOUT_')
        self.assertEqual(about['CREDITS'], len(bake_about.CREDITS))
        self.assertEqual(about['PAGES'], len(bake_about.pages()))
        self.assertEqual(about['PAGE_LINES'], 18)

    def test_every_line_fits_and_has_a_display_code(self):
        for page in bake_about.pages():
            self.assertLessEqual(len(page.heading), 80, page.heading)
            self.assertEqual(set(page.heading) - GLYPHS, set(), page.heading)
            for line in page.lines:
                self.assertLessEqual(len(line), 78, line)
                self.assertEqual(set(line) - GLYPHS, set(), line)
        for credit in bake_about.CREDITS:
            for (text, width) in zip(credit, (19, 36, 19)):
                self.assertLessEqual(len(text), width, credit)
                self.assertEqual(set(text) - GLYPHS, set(), credit)

    def test_page_1s_credits_fit_rows_12_to_19(self):
        self.assertLessEqual(len(bake_about.CREDITS), 8)

    def test_each_license_keeps_its_files_words(self):
        pages = bake_about.pages()
        for group in bake_about.GROUPS:
            with self.subTest(license=group.spdx):
                heading = f'{group.name}: {group.covers}'
                shown = [line for page in pages if page.heading in (heading, heading + ' (continued)')
                         for line in page.lines]
                with open(os.path.join(ROOT, 'LICENSES', f'{group.spdx}.txt'), encoding='utf-8') as stream:
                    text = stream.read().splitlines()
                self.assertEqual(words(shown), words(list(group.copyrights) + text))

    def test_every_licenses_file_is_shown_and_fits(self):
        spdx = {group.spdx for group in bake_about.GROUPS}
        for name in sorted(os.listdir(os.path.join(ROOT, 'LICENSES'))):
            with self.subTest(file=name):
                self.assertIn(name[:-len('.txt')], spdx)
                with open(os.path.join(ROOT, 'LICENSES', name), encoding='utf-8') as stream:
                    self.assertTrue(all(len(line) <= 78 for line in stream.read().splitlines()))

    def test_every_copyright_line_is_in_notice(self):
        with open(os.path.join(ROOT, 'NOTICE'), encoding='utf-8') as stream:
            notice = ' '.join(stream.read().split())
        for group in bake_about.GROUPS:
            for line in group.copyrights:
                with self.subTest(line=line):
                    self.assertIn(' '.join(line.split()), notice)


def write(root, path, text):
    full = os.path.join(root, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'w', encoding='utf-8') as stream:
        stream.write(text)


class TestAudit(unittest.TestCase):
    """about_audit.py on a small tree: a map, ninja's deps, and the files they name."""

    ISC = 'Copyright (c) 2026, CoffeeMuse'
    RPI_2020 = 'Copyright 2020 (c) 2020 Raspberry Pi (Trading) Ltd.'
    RPI_2024 = 'Copyright (c) 2024 Raspberry Pi (Trading) Ltd.'

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = self.dir.name
        firmware = os.path.join(self.root, 'firmware')
        self.build = os.path.join(firmware, 'build', 'x')
        write(self.root, 'LICENSE', f'{self.ISC}\n\nPermission to use, copy, modify, and/or distribute this\n')
        write(self.root, 'firmware/core/a.c', f'// {self.ISC}\n// SPDX-License-Identifier: ISC\n')
        write(self.root, 'firmware/pico-sdk/LICENSE.TXT',
              f'{self.RPI_2020}\n\nRedistribution and use in source and binary forms\n3. Neither the name\n')
        write(self.root, 'firmware/pico-sdk/src/b.c',
              f'/*\n * {self.RPI_2024}\n *\n * SPDX-License-Identifier: BSD-3-Clause\n */\n')
        write(self.root, 'firmware/pico-sdk/src/c.c', 'int c;\n')  # no notice: pico-sdk's LICENSE.TXT
        write(self.root, 'firmware/src/d.pio', f'; {self.ISC}\n; SPDX-License-Identifier: ISC\n')
        write(self.root, 'firmware/build/x/d.pio.h', '// generated by pioasm\n')
        write(self.root, 'firmware/build/x/generated/pico_base/pico/version.h', '// generated\n')
        write(self.root, 'tool/include/_newlib_version.h', '#define _NEWLIB_VERSION "4.6.0"\n')
        self.map = ('Archive member included to satisfy reference by file (symbol)\n\n'
                    'core/libcore.a(a.c.o)  CMakeFiles/t.dir/src/main.c.o (a)\n'
                    f'{self.root}/tool/lib/libg.a(libc_a-memcpy.o)\n'
                    '                              core/libcore.a(a.c.o) (memcpy)\n'
                    f'{self.root}/tool/lib/libgcc.a(_udivmoddi4.o)\n'
                    '\nDiscarded input sections\n\n'
                    f' .text 0x0 0x10 {self.root}/tool/lib/libg.a(libc_a-memset.o)\n'  # indented: not a member line
                    f'\n{about_audit.MEMORY_MAP}\n\n'
                    'LOAD CMakeFiles/t.dir/src/main.c.o\n'
                    'LOAD core/libcore.a\n')
        # The memory map's sections, after self.map's lines: debug information first, then .text, so keep() adds
        # to .text. a.c.o's section name stands alone on its line, as a long one does.
        self.memory = ('\n.debug_info     0x00000000       0x10\n'
                       ' .debug_info    0x00000000       0x10 CMakeFiles/t.dir/src/main.c.o\n'
                       '\n.text           0x20000000       0x40\n'
                       ' .text.main     0x20000000       0x10 CMakeFiles/t.dir/src/main.c.o\n'
                       '                0x20000000                main\n'
                       ' .text.a_function_whose_name_is_long\n'
                       '                0x20000010       0x10 core/libcore.a(a.c.o)\n'
                       ' *fill*         0x20000020        0x4 \n'
                       f' .text.memcpy   0x20000024       0x10 {self.root}/tool/lib/libg.a(libc_a-memcpy.o)\n'
                       f' .text          0x20000034        0x4 {self.root}/tool/lib/libgcc.a(_udivmoddi4.o)\n')
        self.inline = {}  # NEWLIB_HEADERS'
        self.deps = (f'CMakeFiles/t.dir/src/main.c.o: #deps 4, deps mtime 1 (VALID)\n'
                     f'    {firmware}/pico-sdk/src/b.c\n'
                     f'    {firmware}/pico-sdk/src/c.c\n'
                     f'    {self.build}/d.pio.h\n'
                     f'    {self.build}/generated/pico_base/pico/version.h\n'
                     f'\n'
                     f'core/CMakeFiles/core.dir/a.c.o: #deps 1, deps mtime 1 (VALID)\n'
                     f'    {firmware}/core/a.c\n'
                     f'\n'
                     f'core/CMakeFiles/core.dir/unlinked.c.o: #deps 1, deps mtime 1 (VALID)\n'
                     f'    {firmware}/core/unlinked.c\n')  # not in the map, and not on disk: never read
        self.groups = [Group('ISC', 'ISC License', 'x', (self.ISC,)),
                       Group('BSD-3-Clause', 'BSD 3-Clause License', 'y', (self.RPI_2020, self.RPI_2024)),
                       Group('LicenseRef-x', 'X License', 'newlib', ('Copyright (c) 1990 X',),
                             objects=('libc_a-memcpy.o',))]
        self.pio_inputs = [f'{firmware}/src/d.pio']

    def tearDown(self):
        self.dir.cleanup()

    def query(self, path):
        """`ninja -t query`'s text: d.pio.h built from src/d.pio, or self.pio_inputs."""
        self.queries.append(path)
        inputs = self.pio_inputs if path == 'd.pio.h' else []
        return f'{path}:\n  input: CUSTOM_COMMAND\n' + ''.join(f'    {i}\n' for i in inputs) + '  outputs:\n    x\n'

    def keep(self, path, size=4):
        """An input section of path, size bytes, in the memory map's .text."""
        self.memory += f' .text.kept     0x20000100 {size:#10x} {path}\n'

    def audit(self):
        self.queries = []
        return about_audit.audit(self.map + self.memory, self.deps, self.build, self.root, self.groups, self.query,
                                 self.inline)

    def test_a_complete_table_passes(self):
        (problems, counts) = self.audit()
        self.assertEqual(problems, [])
        self.assertEqual(counts, {'objects': 2, 'files': 4, 'archive members': 1, 'objects dropped': 0,
                                  'archive members dropped': 0})

    def test_the_memory_map_keeps_what_the_image_loads(self):
        text = ('x.o(y.o)  z.o (y)\n'
                ' .text.gone    0x00000000       0x10 discarded.o\n'  # before the memory map: discarded
                f'{about_audit.MEMORY_MAP}\n\n'
                '.ram_vector_table\n'
                '                0x20000000      0x110\n'
                ' .ram_vector_table\n'
                '                0x20000000      0x110 ./vectors.o\n'
                '.ARM.extab\n'
                ' *(.ARM.extab*)\n'
                ' .ARM.extab    0x10000000        0x8 extab.o\n'      # its section's address is on no line
                '.text           0x20000110       0x30 load address 0x10000244\n'
                ' .text         0x20000110        0x0 empty.o\n'
                ' .text.f       0x20000110       0x10 lib/libx.a(m.o)\n'
                ' COMMON        0x20000120        0x8 common.o\n'
                ' .text.g       0x20000128        0x8 linker stubs\n'
                'LOAD after.o\n'
                ' .text.h       0x20000130        0x4 orphan.o\n'     # a line at column 0 ended .text
                '.debug_info     0x00000000      0x100\n'
                ' .debug_info   0x00000040       0x20 debug.o\n')
        self.assertEqual(about_audit.kept(text), {'vectors.o', 'lib/libx.a(m.o)', 'common.o', 'linker stubs'})
        self.assertEqual(about_audit.kept('LOAD x.o\n .text 0x20000000 0x10 x.o\n'), set())  # no memory map

    def test_an_object_pulled_in_but_wholly_discarded_is_left_out(self):
        write(self.root, 'firmware/pico-sdk/src/gone.c',
              '/*\n * Copyright (c) 2019 Gone\n *\n * SPDX-License-Identifier: BSD-3-Clause\n */\n')
        self.map += ('LOAD CMakeFiles/t.dir/src/gone.c.o\n'
                     f'{self.root}/tool/lib/libg.a(libc_a-strlcpy.o)\n')  # in no group
        self.deps += (f'\nCMakeFiles/t.dir/src/gone.c.o: #deps 1, deps mtime 1 (VALID)\n'
                      f'    {self.root}/firmware/pico-sdk/src/gone.c\n')
        self.memory = self.memory.replace(  # only its debug information and an empty .text
            ' .debug_info    0x00000000       0x10 CMakeFiles/t.dir/src/main.c.o\n',
            ' .debug_info    0x00000000       0x10 CMakeFiles/t.dir/src/main.c.o\n'
            ' .debug_info    0x00000010       0x20 CMakeFiles/t.dir/src/gone.c.o\n')
        self.keep('CMakeFiles/t.dir/src/gone.c.o', size=0)
        (problems, counts) = self.audit()
        self.assertEqual(problems, [])
        self.assertEqual((counts['objects'], counts['files'], counts['archive members']), (2, 4, 1))
        self.assertEqual((counts['objects dropped'], counts['archive members dropped']), (1, 1))
        self.keep('CMakeFiles/t.dir/src/gone.c.o')
        self.keep(f'{self.root}/tool/lib/libg.a(libc_a-strlcpy.o)')
        (problems, counts) = self.audit()
        self.assertTrue(any(p.startswith('pico-sdk/src/gone.c:') and 'Gone' in p for p in problems), problems)
        self.assertIn('libg.a(libc_a-strlcpy.o) is in no group', problems)
        self.assertEqual((counts['objects dropped'], counts['archive members dropped']), (0, 0))

    def test_a_listed_newlib_object_the_image_keeps_none_of_is_reported(self):
        self.map += f'{self.root}/tool/lib/libg.a(libc_a-strlcpy.o)\n'  # pulled in, but dropped
        self.groups[2] = self.groups[2]._replace(objects=('libc_a-memcpy.o', 'libc_a-strlcpy.o', 'libc_a-div.o'))
        (problems, _) = self.audit()
        self.assertEqual(problems, ['LicenseRef-x: libc_a-strlcpy.o is listed, but the image keeps none of it',
                                    'LicenseRef-x: libc_a-div.o is listed, but the image keeps none of it'])

    def test_a_newlib_header_no_kept_object_includes_is_reported(self):
        self.inline = {'sys/time.h': 'LicenseRef-x'}
        (problems, _) = self.audit()
        self.assertEqual(problems, ['newlib sys/time.h: in NEWLIB_HEADERS, but no kept object includes it'])
        write(self.root, 'tool/include/sys/time.h', '/* Copyright (c) 1982 X */\n')
        self.deps = self.deps.replace(f'    {self.build}/d.pio.h\n',
                                      f'    {self.build}/d.pio.h\n    {self.root}/tool/include/sys/time.h\n')
        (problems, _) = self.audit()
        self.assertEqual(problems, [])

    def test_a_map_whose_memory_map_keeps_nothing_is_reported(self):
        self.memory = ''
        (problems, _) = self.audit()
        self.assertIn(f'{about_audit.MAP_NAME}: its memory map keeps none of the objects it loads, so the audit '
                      f'misreads it', problems)

    def test_a_line_on_no_page_is_reported(self):
        self.groups[1] = self.groups[1]._replace(copyrights=(self.RPI_2020,))
        (problems, _) = self.audit()
        self.assertTrue(any(p.startswith('pico-sdk/src/b.c:') and '2024' in p for p in problems), problems)

    def test_a_file_with_no_notice_takes_its_projects(self):
        write(self.root, 'firmware/pico-sdk/LICENSE.TXT',
              'Copyright 2021 (c) Someone\n\nRedistribution and use in source and binary forms\n3. Neither the name\n')
        (problems, _) = self.audit()
        self.assertTrue(any(p.startswith('pico-sdk/src/c.c:') and 'Someone' in p for p in problems), problems)

    def test_a_pio_header_stands_for_its_source(self):
        write(self.root, 'firmware/src/d.pio', '; Copyright (c) 2025, Someone\n; SPDX-License-Identifier: ISC\n')
        (problems, _) = self.audit()
        self.assertTrue(any(p.startswith('src/d.pio:') for p in problems), problems)

    def test_a_pio_header_stands_for_the_pio_ninja_names_once_asked(self):
        write(self.root, 'firmware/pico-sdk/other/d.pio', '; Copyright (c) 2025, Someone\n')  # the same name
        self.deps += f'\ncore/CMakeFiles/core.dir/a.c.o: #deps 2, deps mtime 1 (VALID)\n'
        self.deps += f'    {self.root}/firmware/core/a.c\n    {self.build}/d.pio.h\n'
        (problems, _) = self.audit()
        self.assertEqual(problems, [])
        self.assertEqual(self.queries, ['d.pio.h'])

    def test_a_pio_header_ninja_names_no_one_pio_for_is_reported(self):
        for inputs in ([], ['../../src/d.pio', '| ../../pico-sdk/other/e.pio']):
            with self.subTest(inputs=inputs):
                self.pio_inputs = inputs
                (problems, _) = self.audit()
                self.assertIn('d.pio.h: ninja names no one .pio it is built from', problems)

    def test_an_archive_at_the_build_directorys_top_is_traced(self):
        self.map += 'libtop.a(top.c.o)  CMakeFiles/t.dir/src/main.c.o (top)\n'
        self.keep('libtop.a(top.c.o)')
        self.deps += (f'\nCMakeFiles/top.dir/top.c.o: #deps 1, deps mtime 1 (VALID)\n'
                      f'    {self.root}/firmware/core/a.c\n')
        (problems, counts) = self.audit()
        self.assertEqual(problems, [])
        self.assertEqual(counts['objects'], 3)

    def test_a_notice_that_doesnt_start_copyright_is_reported(self):
        write(self.root, 'firmware/pico-sdk/src/b.c',
              f'/*\n * {self.RPI_2024}\n * Portions copyrighted (c) 2021 Someone\n *\n'
              f' * SPDX-License-Identifier: BSD-3-Clause\n */\n')
        (problems, _) = self.audit()
        self.assertTrue(any(p.startswith('pico-sdk/src/b.c:') and 'Someone' in p and 'NOTICE_LINES' in p
                            for p in problems), problems)

    def test_unread_notices_skip_license_wording_code_and_strings(self):
        text = ('// (C) 2024 Foo\n * Additions Copyright (c) 2020, Bar\n// \u00a9 2025 Baz\n'
                '// Copyright (c) 2019 Taken\n * 1. Redistributions must retain the above copyright\n'
                '// The above copyright notice\n * IN NO EVENT SHALL THE COPYRIGHT\n'
                '#define tolower(c) __tolower(c)\n    return putchar(c);\n#define ROM_DATA_COPYRIGHT 1\n'
                '    {16u, "Microcode (c) Copyright 2026 X."},\n')
        self.assertEqual(about_audit.unread_notices(text),
                         ['(C) 2024 Foo', 'Additions Copyright (c) 2020, Bar', '\u00a9 2025 Baz'])

    def test_a_newlib_header_with_a_notice_must_be_audited(self):
        self.inline = {'stdio.h': 'LicenseRef-newlib-UCB'}
        headers = {'sys/new.h': '/* Copyright (c) 1999 X */\n',      # a notice, on neither list
                   'sys/old.h': ' *  COPYRIGHT (c) 1989-2010.\n',    # so is this one
                   'stdio.h': '/* Copyright (c) 1990 Y */\n',        # NEWLIB_HEADERS', but no such group here
                   'sys/cdefs.h': '/* Copyright (c) 1991 Z */\n',    # NEWLIB_DECLARATIONS'
                   'plain.h': 'int plain;\n',                         # no notice
                   'c++/cstdlib': '// Copyright (C) 1997 FSF\n'}     # libstdc++'s: GCC's exception
        for (name, text) in headers.items():
            write(self.root, f'tool/include/{name}', text)
            self.deps = self.deps.replace(f'    {self.build}/d.pio.h\n',
                                          f'    {self.build}/d.pio.h\n    {self.root}/tool/include/{name}\n')
        write(self.root, 'tool/lib/gcc/include/stddef.h', '/* Copyright (C) 1989 FSF */\n')  # GCC's own
        self.deps = self.deps.replace(f'    {self.build}/d.pio.h\n',
                                      f'    {self.build}/d.pio.h\n    {self.root}/tool/lib/gcc/include/stddef.h\n')
        (problems, _) = self.audit()
        self.assertEqual(sorted(p.split(':')[0] for p in problems if p.startswith('newlib ')),
                         ['newlib stdio.h', 'newlib sys/new.h', 'newlib sys/old.h'])
        self.groups.append(Group('LicenseRef-newlib-UCB', 'Berkeley License', 'newlib', ('Copyright (c) 1990 Y',),
                                 ('libc_a-fclose.o',)))
        (problems, _) = self.audit()
        self.assertNotIn('newlib stdio.h', [p.split(':')[0] for p in problems])

    def test_a_toolchain_member_in_no_group_is_reported_but_not_libgccs(self):
        self.groups[2] = self.groups[2]._replace(objects=())
        (problems, _) = self.audit()
        self.assertIn('libg.a(libc_a-memcpy.o) is in no group', problems)
        self.assertFalse(any('libgcc' in p for p in problems), problems)

    def test_a_listed_line_nothing_linked_holds_is_reported(self):
        self.groups[0] = self.groups[0]._replace(copyrights=(self.ISC, 'Copyright (c) 1999 Nobody'))
        (problems, _) = self.audit()
        self.assertTrue(any('Nobody' in p and 'nothing kept' in p for p in problems), problems)

    def test_a_load_path_with_a_dot_segment_is_traced(self):
        self.map = self.map.replace('LOAD CMakeFiles/t.dir/src/main.c.o', 'LOAD CMakeFiles/t.dir/./src/main.c.o')
        (problems, counts) = self.audit()
        self.assertEqual(problems, [])
        self.assertEqual(counts['objects'], 2)

    def test_a_linked_object_ninja_has_no_record_of_is_reported(self):
        self.map += 'LOAD CMakeFiles/t.dir/src/extra.c.o\ncore/libcore.a(b.c.o)  CMakeFiles/t.dir/src/main.c.o (b)\n'
        self.keep('CMakeFiles/t.dir/src/extra.c.o')
        self.keep('core/libcore.a(b.c.o)')
        (problems, _) = self.audit()
        self.assertIn('CMakeFiles/t.dir/src/extra.c.o: linked, but ninja has no record of its sources', problems)
        self.assertIn('core/libcore.a(b.c.o): linked, but ninja has no record of its sources', problems)

    def test_an_unexpected_file_in_the_build_tree_is_reported(self):
        write(self.root, 'firmware/build/x/generated/other.S', '// generated\n')
        self.deps = self.deps.replace(f'    {self.build}/d.pio.h\n',
                                      f'    {self.build}/d.pio.h\n    {self.build}/generated/other.S\n')
        (problems, _) = self.audit()
        self.assertIn('generated/other.S: generated in the build tree, from sources the audit can\'t name', problems)

    def test_the_version_header_holds_no_notice(self):
        # firmware/version.cmake writes it at every build (#132), and version.c is the one object including it.
        write(self.root, 'firmware/build/x/generated/liz_version.h', '// generated\n')
        self.deps = self.deps.replace(f'    {self.build}/d.pio.h\n',
                                      f'    {self.build}/d.pio.h\n    {self.build}/generated/liz_version.h\n')
        (problems, _) = self.audit()
        self.assertFalse([p for p in problems if 'liz_version.h' in p], problems)

    def test_boot_stage_2s_generated_source_stands_for_its_sources(self):
        padded = 'pico-sdk/src/rp2350/boot_stage2/bs2_default_padded.S'
        target = 'pico-sdk/src/rp2350/boot_stage2/CMakeFiles/bs2_default.dir/compile_time_choice.S.o'
        firmware = os.path.join(self.root, 'firmware')
        write(self.root, f'firmware/build/x/{padded}', '// generated\n')
        write(self.root, 'firmware/pico-sdk/src/rp2350/boot_stage2/boot2.S',
              '/*\n * Copyright (c) 2019-2022 Raspberry Pi (Trading) Ltd.\n'
              ' * SPDX-License-Identifier: BSD-3-Clause\n */\n')
        self.map += 'LOAD pico-sdk/src/rp2350/boot_stage2/CMakeFiles/bs2_default_library.dir/./bs2_default_padded.S.o\n'
        self.keep('pico-sdk/src/rp2350/boot_stage2/CMakeFiles/bs2_default_library.dir/./bs2_default_padded.S.o')
        self.deps += (f'\npico-sdk/src/rp2350/boot_stage2/CMakeFiles/bs2_default_library.dir/bs2_default_padded.S.o: '
                      f'#deps 1, deps mtime 1 (VALID)\n    {self.build}/{padded}\n'
                      f'\n{target}: #deps 1, deps mtime 1 (VALID)\n'
                      f'    {firmware}/pico-sdk/src/rp2350/boot_stage2/boot2.S\n')
        (problems, _) = self.audit()
        self.assertTrue(any(p.startswith('pico-sdk/src/rp2350/boot_stage2/boot2.S:') and '2019-2022' in p
                            for p in problems), problems)

    def test_another_newlib_version_is_reported(self):
        write(self.root, 'tool/include/_newlib_version.h', '#define _NEWLIB_VERSION "4.5.0"\n')
        (problems, _) = self.audit()
        self.assertIn(f'newlib 4.5.0 is linked, but its notices were audited at {bake_about.NEWLIB_VERSION}', problems)

    def test_a_toolchain_without_its_newlib_version_is_reported(self):
        os.remove(os.path.join(self.root, 'tool/include/_newlib_version.h'))
        (problems, _) = self.audit()
        self.assertTrue(any('_newlib_version.h' in p for p in problems), problems)

    def test_printf_h_carries_marco_palands_notice(self):
        paland = '(c) Marco Paland (info@paland.com) 2014-2019, PALANDesign Hannover, Germany'
        write(self.root, 'firmware/pico-sdk/src/rp2_common/pico_printf/include/pico/printf.h',
              '// \\author (c) Marco Paland (info@paland.com)\n//         2014-2019, PALANDesign Hannover, Germany\n'
              '// Permission is hereby granted, free of charge, to any person\n')
        printf_h = f'{self.root}/firmware/pico-sdk/src/rp2_common/pico_printf/include/pico/printf.h'
        self.deps = self.deps.replace(f'    {self.build}/d.pio.h\n', f'    {self.build}/d.pio.h\n    {printf_h}\n')
        self.groups.append(Group('MIT', 'MIT License', 'z', (paland,)))
        (problems, _) = self.audit()
        self.assertEqual(problems, [])

    def test_a_line_listed_under_the_wrong_license_is_reported(self):
        self.groups[0] = self.groups[0]._replace(copyrights=(self.ISC, self.RPI_2024))  # b.c holds it under BSD
        (problems, _) = self.audit()
        self.assertIn(f'ISC: {self.RPI_2024!r} is listed, but nothing kept holds it', problems)

    def test_a_vendored_project_the_audit_doesnt_know_is_reported(self):
        write(self.root, 'firmware/vendor/other/x.c', 'int x;\n')  # no notice: no project's license to fall back on
        self.deps = self.deps.replace(f'    {self.build}/d.pio.h\n',
                                      f'    {self.build}/d.pio.h\n    {self.root}/firmware/vendor/other/x.c\n')
        (problems, _) = self.audit()
        self.assertIn('vendor/other/x.c: in vendor/, in no project the audit knows', problems)

    def test_copyright_lines_lose_their_comment_marks(self):
        text = ' * Copyright (c) 2019 Ha Thach (tinyusb.org) */\n// The above copyright notice\n# Copyright 2022 X\n'
        self.assertEqual(about_audit.copyright_lines(text),
                         ['Copyright (c) 2019 Ha Thach (tinyusb.org)', 'Copyright 2022 X'])

    def test_licenses_by_identifier_or_words(self):
        self.assertEqual(about_audit.licenses_in('SPDX-License-Identifier: BSD-3-Clause\n'), {'BSD-3-Clause'})
        self.assertEqual(about_audit.licenses_in('Permission is hereby granted, free of charge, to'), {'MIT'})
        self.assertEqual(about_audit.licenses_in('Redistribution and use in source and binary forms'),
                         {'BSD-2-Clause'})


if __name__ == '__main__':
    unittest.main()
