# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

import getpass
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import zlib
from unittest import mock

import manual_paths
import build
import typst_run
from edition import BuildError


def pdf_bytes(path):
    """The PDF's bytes and every stream in it inflated, to search for what mustn't be there."""
    with open(path, 'rb') as stream:
        data = stream.read()
    inflated = []
    for match in re.finditer(rb'stream\r?\n(.*?)endstream', data, re.S):
        try:
            inflated.append(zlib.decompress(match.group(1)))
        except zlib.error:
            pass
    return data + b''.join(inflated)


def read(path):
    with open(path, 'rb') as stream:
        return stream.read()


class TestBuild(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.makedirs(manual_paths.TESTS_OUT, exist_ok=True)
        cls.dir = tempfile.mkdtemp(dir=manual_paths.TESTS_OUT)
        cls.log = []
        cls.pdfs = build.build(out_dir=cls.dir, log=cls.log.append)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir)

    def test_a_draft_on_both_papers(self):
        self.assertEqual([os.path.basename(p) for p in self.pdfs], ['liz4270-users-guide-LZ01-4270-XX-letter.pdf',
                                                                    'liz4270-users-guide-LZ01-4270-XX-a4.pdf'])
        for pdf in self.pdfs:
            self.assertEqual(read(pdf)[:5], b'%PDF-')

    def test_both_papers_break_their_pages_alike(self):
        self.assertIn('both papers break their pages alike', self.log)

    def test_the_keymaps_reach_the_book(self):
        with open(os.path.join(self.dir, 'data', 'keymaps.json'), encoding='utf-8') as stream:
            data = json.load(stream)
        self.assertEqual(data['keymaps'][0]['name'], 'us104')
        self.assertIn('RESET', data['oec_ignores'])

    def test_the_same_commit_builds_the_same_bytes(self):
        first = [read(p) for p in self.pdfs]
        self.assertEqual([read(p) for p in build.build(out_dir=self.dir, log=lambda line: None)], first)

    def test_an_earlier_builds_leftovers_are_cleared(self):
        with tempfile.TemporaryDirectory(dir=manual_paths.TESTS_OUT) as out:
            os.makedirs(os.path.join(out, 'screens'))
            # An earlier build's screen, and its PDF: a release's would otherwise sit beside a draft's.
            strays = [os.path.join(out, 'screens', 'gone-640.png'),
                      os.path.join(out, 'liz4270-users-guide-LZ01-4270-00-letter.pdf')]
            for stray in strays:
                with open(stray, 'wb') as stream:
                    stream.write(b'old')
            build.build(papers=('a4',), out_dir=out, log=lambda line: None)
            for stray in strays:
                self.assertFalse(os.path.exists(stray), stray)

    def test_a_failed_page_check_leaves_no_pdfs(self):
        with tempfile.TemporaryDirectory(dir=manual_paths.TESTS_OUT) as out:
            apart = [[{'what': 'chapter [Sound]', 'page': 23}], [{'what': 'chapter [Sound]', 'page': 25}]]
            with mock.patch.object(build.typst_run, 'placed', side_effect=apart):
                with self.assertRaisesRegex(BuildError, 'paginate differently'):
                    build.build(out_dir=out, log=lambda line: None)
            self.assertEqual([f for f in os.listdir(out) if f.endswith('.pdf')], [])

    def test_the_pdfs_hold_no_home_directory_or_login(self):
        login = getpass.getuser().encode()
        for pdf in self.pdfs:
            data = pdf_bytes(pdf)
            for needle in (os.path.expanduser('~').encode(), b'/Users/', b'/home/'):
                self.assertNotIn(needle, data, pdf)
            if len(login) > 3:
                self.assertNotIn(login, data, pdf)

    def test_the_author_is_coffeemuse(self):
        self.assertIn(b'CoffeeMuse', pdf_bytes(self.pdfs[0]))

    def test_the_command_runs_from_anywhere_for_one_paper(self):
        with tempfile.TemporaryDirectory() as elsewhere, tempfile.TemporaryDirectory(dir=manual_paths.TESTS_OUT) as out:
            result = subprocess.run([sys.executable, os.path.join(manual_paths.HERE, 'build.py'), '--paper', 'a4',
                                     '--out', out], cwd=elsewhere, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(os.listdir(out).count('liz4270-users-guide-LZ01-4270-XX-a4.pdf'), 1)
        self.assertIn('LZ01-4270-XX-a4.pdf', result.stdout)
        self.assertNotIn('alike', result.stdout)

    def test_an_output_outside_the_checkout_is_refused(self):
        with tempfile.TemporaryDirectory() as outside:
            with self.assertRaisesRegex(BuildError, 'outside the checkout'):
                build.build(out_dir=outside, log=lambda line: None)

    def test_every_written_chapter_marks_the_index(self):
        inputs = {'build': '/' + os.path.relpath(self.dir, manual_paths.ROOT)}
        marks = typst_run.placed(build.SOURCE, inputs)
        pages = typst_run.eval_json(build.SOURCE, inputs, 'query(<ix>).map(m => m.location().page())')
        starts = [(m['what'], m['page']) for m in marks if re.match(r'(Chapter|Appendix) \S+ |chapter ', m['what'])]
        spans = {what: (page, after) for ((what, page), (_, after)) in zip(starts, starts[1:] + [('end', 10 ** 6)])}
        for part in ('Chapter 1 ', 'Chapter 2 ', 'Chapter 3 ', 'Chapter 4 ', 'Chapter 5 ', 'Chapter 6 ', 'Chapter 7 ',
                     'Chapter 8 ', 'Appendix A ', 'chapter [Glossary]'):
            (what, (first, after)) = next((w, span) for (w, span) in spans.items() if w.startswith(part))
            self.assertTrue(any(first <= page < after for page in pages), f'{what} marks nothing for the index')

    def test_the_index_finds_the_screen_and_its_size(self):
        # Chapter 8's screen symptoms under "screen", and the sizes Chapter 3 and Customization give (PR 3's review).
        inputs = {'build': '/' + os.path.relpath(self.dir, manual_paths.ROOT)}
        entries = typst_run.eval_json(build.SOURCE, inputs, '{ import "/docs/manual/style.typ": index-groups, '
                                      'index-marks; index-groups(index-marks()).map(g => g.entries).flatten()'
                                      '.map(e => (e.term, e.subs.map(s => s.term), e.see, e.pages.len())) }')
        found = {term: (subs, see, pages) for (term, subs, see, pages) in entries}
        self.assertEqual(found.get('screen'), (['dark', 'goes black', 'stops changing'], None, 0))
        (subs, see, pages) = found.get('screen size', (None, None, 0))
        self.assertEqual((subs, see), ([], None))
        self.assertGreaterEqual(pages, 2)

    def test_the_index_is_in_the_back_matter(self):
        whats = [m['what'] for m in typst_run.placed(build.SOURCE, {'build': '/' + os.path.relpath(self.dir,
                                                                                                manual_paths.ROOT)})]
        after = [w for w in whats[whats.index('Appendix A [Keymaps]') + 1:] if w.startswith('chapter ')]
        self.assertEqual(after[:2], ['chapter [Glossary]', 'chapter [Index]'])
        self.assertIn('Readers', after[2])  # its title's quote is a smartquote, so its repr is a sequence

    def test_no_float_lands_above_its_heading(self):
        # Both papers of the real book: Chapter 5's Customization figure stays under its heading.
        build_dir = '/' + os.path.relpath(self.dir, manual_paths.ROOT)
        for paper in ('us-letter', 'a4'):
            with self.subTest(paper=paper):
                build.check_floats(typst_run.placed(build.SOURCE, {'build': build_dir, 'paper': paper}))

    def test_chapter_5_sets_every_setup_screen_and_table(self):
        build_dir = '/' + os.path.relpath(self.dir, manual_paths.ROOT)
        # Each figure's marker is its label and caption: "Table 5-1 [Online Setup and Utility menu]".
        whats = [re.sub(r'^(Table|Figure) 5-\d+ ', r'\1 ', m['what'])
                 for m in typst_run.placed(build.SOURCE, {'build': build_dir})]
        for caption in ('Online Setup and Utility menu', 'Display Setup, page 1', 'Display Setup, page 2',
                        'Display Setup, page 3', 'Display Setup, page 4', 'Offline Setup menu', 'Customization'):
            self.assertIn(f'Table [{caption}]', whats)
        for caption in ('Online Setup and Utility menu', 'Display Setup, page 1', 'Display Setup, page 2',
                        'Display Setup, page 3', 'Password Set', 'Customization', 'About Liz4270'):
            self.assertIn(f'Figure [{caption}]', whats)


class TestTypstAtOnce(unittest.TestCase):

    def test_both_papers_and_their_page_checks_are_laid_out_at_once(self):
        # None of the four needs another's result, so all four wait at one barrier, which a run made after
        # another never passes.
        barrier = threading.Barrier(4, timeout=5)
        os.makedirs(manual_paths.TESTS_OUT, exist_ok=True)

        def compile_pdf(source, out, inputs, timestamp):
            barrier.wait()

        def placed(source, inputs):
            barrier.wait()
            return [{'what': 'chapter [Sound]', 'page': 23}]

        with tempfile.TemporaryDirectory(dir=manual_paths.TESTS_OUT) as out, \
                mock.patch.object(build.typst_run, 'compile_pdf', side_effect=compile_pdf), \
                mock.patch.object(build.typst_run, 'placed', side_effect=placed):
            log = []
            try:
                build.build(out_dir=out, log=log.append)
            except threading.BrokenBarrierError:
                self.fail('the Typst runs were made one after another')
        # The log keeps the papers' order, whichever run ends first.
        self.assertEqual([line.split('LZ01-4270-XX-')[-1] for line in log],
                         ['letter.pdf', 'a4.pdf', 'both papers break their pages alike'])


class TestComparePlaced(unittest.TestCase):

    def test_the_same_pages_pass(self):
        build.compare_placed([{'what': 'a', 'page': 1}], [{'what': 'a', 'page': 1}])

    def test_a_marker_on_another_page_is_named(self):
        with self.assertRaisesRegex(BuildError, r'chapter \[Sound\] lands on page 23 on one and page 25'):
            build.compare_placed([{'what': 'chapter [Sound]', 'page': 23}], [{'what': 'chapter [Sound]', 'page': 25}])

    def test_a_marker_missing_on_one_paper_is_caught(self):
        with self.assertRaisesRegex(BuildError, '2 markers against 1'):
            build.compare_placed([{'what': 'a', 'page': 1}, {'what': 'b', 'page': 2}], [{'what': 'a', 'page': 1}])

    def test_markers_that_part_mid_book_are_named_both(self):
        # A marker missing in the middle mustn't read as the next one landing on another page.
        with self.assertRaisesRegex(BuildError, r'the markers part at figure \[B\] on one and section \[C\] on the '
                                                r'other \(3 markers against 2\)'):
            build.compare_placed([{'what': 'chapter [A]', 'page': 1}, {'what': 'figure [B]', 'page': 2},
                                  {'what': 'section [C]', 'page': 3}],
                                 [{'what': 'chapter [A]', 'page': 1}, {'what': 'section [C]', 'page': 3}])



class TestFloats(unittest.TestCase):
    """No figure floats above the heading it follows (#141's review: Figure 5-7 floated above Customization)."""

    MARKS = [{'what': 'Chapter 5 [Using SetUp]', 'page': 31, 'y': 100.0},
             {'what': 'subsection [Customization]', 'page': 31, 'y': 400.0},
             {'what': 'Figure 5-7 [Customization]', 'page': 31, 'y': 300.0}]

    def test_a_float_above_its_heading_stops_the_build(self):
        with self.assertRaisesRegex(BuildError, r'Figure 5-7 lands above its heading \[Customization\] on page 31'):
            build.check_floats(self.MARKS)

    def test_a_float_below_its_heading_or_on_a_later_page_is_fine(self):
        build.check_floats(self.MARKS[:2] + [{**self.MARKS[2], 'y': 500.0}])
        build.check_floats(self.MARKS[:2] + [{**self.MARKS[2], 'page': 32, 'y': 50.0}])


if __name__ == '__main__':
    unittest.main()
