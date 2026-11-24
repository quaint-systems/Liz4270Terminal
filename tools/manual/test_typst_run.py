# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

import os
import tempfile
import unittest

import manual_paths
import typst_run
from edition import BuildError

WHEN = 1791979200  # a commit's time, as build.py passes it


class TestTypstRun(unittest.TestCase):

    def setUp(self):
        os.makedirs(manual_paths.TESTS_OUT, exist_ok=True)
        self.dir = tempfile.TemporaryDirectory(dir=manual_paths.TESTS_OUT)
        self.addCleanup(self.dir.cleanup)
        self.pdf = os.path.join(self.dir.name, 'doc.pdf')

    def doc(self, text):
        path = os.path.join(self.dir.name, 'doc.typ')
        with open(path, 'w', encoding='utf-8') as stream:
            stream.write(text)
        return path

    def fake_typst(self, says):
        path = os.path.join(self.dir.name, 'typst')
        with open(path, 'w', encoding='utf-8') as stream:
            stream.write(f'#!/bin/sh\necho "{says}"\n')
        os.chmod(path, 0o755)
        return path

    def fake_typst_warning(self, warning):
        """A typst that succeeds, but says warning on stderr as Typst's short format does."""
        path = os.path.join(self.dir.name, 'typst')
        with open(path, 'w', encoding='utf-8') as stream:
            stream.write(f'#!/bin/sh\necho "{warning}" >&2\n')
        os.chmod(path, 0o755)
        return path

    def test_the_pinned_version_is_installed(self):
        typst_run.check_version()

    def test_another_version_is_refused_with_how_to_get_the_right_one(self):
        with self.assertRaisesRegex(BuildError, r'Typst 0\.15\.1 is needed, found 0\.14\.0: brew install typst'):
            typst_run.check_version(self.fake_typst('typst 0.14.0 (b1e2c3d4)'))

    def test_a_typst_that_fails_its_version_says_so(self):
        path = os.path.join(self.dir.name, 'typst')
        with open(path, 'w', encoding='utf-8') as stream:
            stream.write('#!/bin/sh\necho "dyld: Library not loaded" >&2\nexit 1\n')
        os.chmod(path, 0o755)
        with self.assertRaisesRegex(BuildError, r'typst --version failed \(exit 1\): dyld: Library not loaded'):
            typst_run.check_version(path)

    def test_no_typst_at_all_is_refused(self):
        with self.assertRaisesRegex(BuildError, 'none is installed'):
            typst_run.check_version('typst-that-is-not-installed')

    def test_a_document_in_the_repos_fonts_builds(self):
        typst_run.compile_pdf(self.doc('#set text(font: "IBM Plex Serif")\nHello\n'), self.pdf, {}, WHEN)
        with open(self.pdf, 'rb') as stream:
            self.assertEqual(stream.read(5), b'%PDF-')

    def test_a_missing_font_fails_the_build(self):
        with self.assertRaisesRegex(BuildError, 'unknown font family: nope sans'):
            typst_run.compile_pdf(self.doc('#set text(font: "Nope Sans")\nHello\n'), self.pdf, {}, WHEN)

    def test_a_system_font_isnt_seen(self):
        # Helvetica is on every Mac; the build must not depend on what a machine has installed.
        with self.assertRaisesRegex(BuildError, 'unknown font family: helvetica'):
            typst_run.compile_pdf(self.doc('#set text(font: "Helvetica")\nHello\n'), self.pdf, {}, WHEN)

    def test_a_font_bundled_in_typst_isnt_seen(self):
        # Only the repo's fonts: Typst's own Libertinus would otherwise stand in unnoticed.
        with self.assertRaisesRegex(BuildError, 'unknown font family: libertinus serif'):
            typst_run.compile_pdf(self.doc('#set text(font: "Libertinus Serif")\nHello\n'), self.pdf, {}, WHEN)

    def test_an_error_fails_the_build(self):
        with self.assertRaisesRegex(BuildError, 'boom'):
            typst_run.compile_pdf(self.doc('#panic("boom")\n'), self.pdf, {}, WHEN)

    def test_a_warning_in_the_page_query_fails_too(self):
        with self.assertRaisesRegex(BuildError, 'unknown font family: nope sans'):
            typst_run.placed(self.doc('#set text(font: "Nope Sans")\nHello\n'), {})

    def test_a_warning_with_no_place_in_the_source_fails_too(self):
        # Typst's short format prints one with no span as a bare "warning: ...", with no path before it.
        exe = self.fake_typst_warning('warning: html export is under active development and incomplete')
        with self.assertRaisesRegex(BuildError, 'Typst warned.*\nwarning: html export'):
            typst_run.compile_pdf(self.doc('Hello\n'), self.pdf, {}, WHEN, exe)

    def test_a_line_that_only_mentions_a_warning_isnt_one(self):
        exe = self.fake_typst_warning('compiled with no warning: nothing to say')
        typst_run.compile_pdf(self.doc('Hello\n'), self.pdf, {}, WHEN, exe)

    def test_inputs_reach_the_document(self):
        doc = self.doc('#metadata((what: sys.inputs.at("paper"), page: 1)) <placed>\n')
        self.assertEqual(typst_run.placed(doc, {'paper': 'a4'}), [{'what': 'a4', 'page': 1}])

    def test_placed_markers_carry_their_pages(self):
        doc = self.doc('#let mark(w) = context [#metadata((what: w, page: here().page())) <placed>]\n'
                       '#mark("one")\n#pagebreak()\n#mark("two")\n')
        self.assertEqual(typst_run.placed(doc, {}), [{'what': 'one', 'page': 1}, {'what': 'two', 'page': 2}])

    def test_eval_json_reads_a_documents_values(self):
        doc = self.doc('#let mark(w) = context [#metadata((what: w, page: here().page())) <placed>]\n'
                       '#mark("one")\n#pagebreak()\n#mark("two")\n')
        self.assertEqual(typst_run.eval_json(doc, {}, 'query(<placed>).map(it => it.value)'), typst_run.placed(doc, {}))
        self.assertEqual(typst_run.eval_json(doc, {}, 'query(<placed>).map(it => it.location().page())'), [1, 2])


if __name__ == '__main__':
    unittest.main()
