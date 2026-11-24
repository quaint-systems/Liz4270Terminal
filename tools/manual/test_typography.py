# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The book's sources, scanned (#136). Its apostrophes are typographic: Typst's smart quotes make a ' after a
digit a prime (Liz4270′s), and a string handed to text() is set as typed, so both must be written as ’. No index
marker sits where the template repeats it, and the text cites no issue number."""

import glob
import os
import re
import unittest

import manual_paths


def typ_sources():
    return sorted(glob.glob(os.path.join(manual_paths.MANUAL, '**', '*.typ'), recursive=True))


def repeated_markers(text):
    """The index markers in a heading or a caption, which the contents, the lists of figures and tables, and a
    chapter's footers repeat: each copy would add its own page to the index."""
    lines = [line for line in text.splitlines() if line.lstrip().startswith('=') and '#ix' in line]
    flat = ' '.join(text.split())
    # What opens one: a caption, an unnumbered chapter's title, or #heading with any arguments.
    opens = r'(?:caption: ?|unnumbered\(|#heading(?:\([^)]*\))?)\['
    # Its text up to the marker, past brackets nested one deep, such as #key[F3], or inside one.
    before = r'(?:[^\[\]]|\[[^\[\]]*\])*?(?:\[[^\[\]]*)?'
    return lines + re.findall(opens + before + r'#ix(?:\[[^\]]*\]|\([^)]*\))', flat)


def issue_numbers(text):
    """Each line holding # and a digit, as an issue is cited, with its // comment cut off."""
    return [line for line in text.splitlines() if re.search(r'#\d', line.split('//')[0])]


class TestTypography(unittest.TestCase):

    def test_the_sources_are_found(self):
        self.assertIn(os.path.join(manual_paths.MANUAL, 'chapters', '05-setup.typ'), typ_sources())

    def test_no_digit_is_followed_by_a_typewriter_apostrophe(self):
        found = []
        for path in typ_sources():
            with open(path, encoding='utf-8') as stream:
                for (number, line) in enumerate(stream, 1):
                    if not line.lstrip().startswith('//') and re.search(r"[0-9]'", line):
                        found.append(f'{os.path.relpath(path, manual_paths.ROOT)}:{number}')
        self.assertEqual(found, [], "write ’ after a digit: Typst sets ' there as a prime")

    def test_the_templates_strings_have_no_typewriter_apostrophe(self):
        with open(os.path.join(manual_paths.MANUAL, 'style.typ'), encoding='utf-8') as stream:
            strings = re.findall(r'^#let ([\w-]+) = "([^"]*)"', stream.read(), re.M)
        self.assertIn('book-title', [name for (name, _) in strings])
        self.assertEqual([name for (name, value) in strings if "'" in value], [],
                         "a string set with text() isn't smart-quoted: write ’")

    def test_every_list_marker_is_in_plex_serif(self):
        # Typst's own second-level marker, ‣, isn't in Plex Serif, and a missing glyph is set as a box, unwarned:
        # the font's .notdef, which a private-use character draws too.
        from PIL import ImageFont
        font = ImageFont.truetype(os.path.join(manual_paths.MANUAL, 'fonts', 'IBMPlexSerif-Regular.otf'), 40)

        def drawn(text):
            mask = font.getmask(text)
            return (mask.size, bytes(mask))
        with open(os.path.join(manual_paths.MANUAL, 'style.typ'), encoding='utf-8') as stream:
            found = re.search(r'set list\(marker: \(([^)]*)\)', stream.read())
        self.assertIsNotNone(found, "style.typ sets the list's markers")
        markers = re.findall(r'\[([^\]]+)\]', found.group(1))
        self.assertGreaterEqual(len(markers), 2)
        self.assertEqual(drawn('‣'), drawn('\ue000'), 'the check sees a missing glyph')
        self.assertEqual([m for m in markers if any(drawn(c) == drawn('\ue000') for c in m)], [])

    def test_no_index_marker_in_a_heading_or_caption(self):
        self.assertTrue(repeated_markers('== Auto dim #ix[auto dim]\n'))
        self.assertTrue(repeated_markers('#figure(x, caption: [The\nrule #ix[rule line] line]) <fig>\n'))
        self.assertFalse(repeated_markers('== Auto dim\nAuto dim #ix[auto dim] blanks it.\n'))
        found = []
        for path in typ_sources():
            with open(path, encoding='utf-8') as stream:
                found += [f'{os.path.relpath(path, manual_paths.ROOT)}: {m}' for m in repeated_markers(stream.read())]
        self.assertEqual(found, [], 'put #ix in the text after a heading or a caption, never in it')

    def test_a_marker_past_a_nested_bracket_or_in_heading_markup_is_caught(self):
        # PR 3's review: a caption's #key[...] or #emph[...] ended the scan at its ], and #heading[...] wasn't read.
        self.assertTrue(repeated_markers('#figure(x, caption: [Press #key[F3] to leave #ix[SetUp]]) <fig>\n'))
        self.assertTrue(repeated_markers('#figure(x, caption: [The #emph[rule #ix[rule line]] line])\n'))
        self.assertTrue(repeated_markers('#heading[Auto dim #ix[auto dim]]\n'))
        self.assertTrue(repeated_markers('#heading(level: 2, outlined: false)[Auto dim #ix[auto dim]]\n'))
        self.assertFalse(repeated_markers('#figure(x, caption: [Press #key[F3]]) Then #ix[SetUp] closes.\n'))
        self.assertFalse(repeated_markers('#heading[Auto dim] It blanks #ix[auto dim] the screen.\n'))

    def test_no_semicolon_follows_an_index_marker(self):
        # Typst ends an embedded expression at a semicolon and drops it: "Controller#ix[3174]; or" prints no ;.
        swallowed = re.compile(r'#ix(?:\[[^\]]*\]|\([^)]*\));')
        self.assertTrue(swallowed.search('Controller#ix[3174]; or'))
        found = []
        for path in typ_sources():
            with open(path, encoding='utf-8') as stream:
                found += [f'{os.path.relpath(path, manual_paths.ROOT)}: {m.group(0)}'
                          for m in swallowed.finditer(stream.read())]
        self.assertEqual(found, [], 'put the marker after the semicolon: Typst drops a ; that ends #ix[...]')

    def test_the_book_cites_no_issue_number(self):
        self.assertTrue(issue_numbers('As #136 says.\n'))
        self.assertFalse(issue_numbers('Text. // as #136 says\n'))
        found = []
        for path in typ_sources():
            with open(path, encoding='utf-8') as stream:
                found += [f'{os.path.relpath(path, manual_paths.ROOT)}: {line}' for line in issue_numbers(stream.read())]
        self.assertEqual(found, [], "the book's text cites no issue number: readers can't follow one")


if __name__ == '__main__':
    unittest.main()
