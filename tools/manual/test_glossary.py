# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The glossary: the terms the book relies on are defined, and it defines none the book doesn't use (#136)."""

import glob
import os
import re
import unittest

import manual_paths


def source(path):
    with open(path, encoding='utf-8') as stream:
        return stream.read()


class TestGlossary(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raw = source(os.path.join(manual_paths.MANUAL, 'chapters', 'glossary.typ'))
        # Each entry, "TERM": (expands: "EXPANSION", ...), opens a line of its own.
        cls.entries = re.findall(r'^  "([^"]+)": \((?:expands: "([^"]+)")?', cls.raw, re.M)
        chapters = sorted(glob.glob(os.path.join(manual_paths.MANUAL, 'chapters', '*.typ')))
        cls.book = ' '.join(source(p) for p in chapters if not p.endswith('glossary.typ')).replace('~', ' ').lower()

    def test_the_terms_the_book_relies_on_are_defined(self):
        terms = [term for (term, _) in self.entries]
        for term in ('CUT', 'DFT', 'EAB', 'OIA', 'regen buffer'):
            self.assertIn(term, terms)

    def test_the_3174_attaches_by_coax_and_connects_to_the_host(self):
        # Its display stations attach to it by coax; its link to the host is another matter (PR 3's review).
        text = ' '.join(self.raw.split())
        self.assertIn('it attaches them by coax, and connects them to the host', text)
        self.assertNotIn('to the host by coax', text)

    def test_every_glossary_term_is_used_in_the_book(self):
        self.assertGreater(len(self.entries), 20)
        unused = [term for (term, expands) in self.entries
                  if term.lower() not in self.book and (not expands or expands.lower() not in self.book)]
        self.assertEqual(unused, [], 'the glossary defines terms no chapter uses')


if __name__ == '__main__':
    unittest.main()
