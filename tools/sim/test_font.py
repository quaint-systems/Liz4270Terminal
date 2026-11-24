# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The firmware's font (firmware/core/font_3270.c, from bake_font.py), through the core."""

import unicodedata
import unittest

import core
from display_codes import MAIN, NAMED_GLYPHS, STATUS

BOXED = [*range(0xC0, 0xCC), 0xD7, 0xD9, *range(0xE0, 0xEC), 0xF9]
BOXES = (0xD5, 0xDE, 0xDF, 0xFC, 0xFF)  # status symbols drawn as boxes to the full advance
HEIGHTS = core.FONT_HEIGHTS
MARKS = {'\u0300', '\u0301', '\u0302', '\u0303', '\u030a'}  # grave, acute, circumflex, tilde, ring


def merged(rows, x):
    """rows with columns x and x + 1 ORed into one: 9 columns down to 8."""
    low = (1 << x) - 1
    return [(r & low) | ((r >> x | r >> (x + 1)) & 1) << x | (r >> (x + 2)) << (x + 1) for r in rows]


def marks(rows, width):
    """The separate marks in rows, 8-connected: each a set of (x, y)."""
    lit = {(x, y) for (y, r) in enumerate(rows) for x in range(width) if r >> x & 1}
    found = []
    while lit:
        stack = [lit.pop()]
        mark = set(stack)
        while stack:
            (x, y) = stack.pop()
            for p in [(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]:
                if p in lit:
                    lit.remove(p)
                    mark.add(p)
                    stack.append(p)
        found.append(mark)
    return found


def accented():
    """(code, the plain letter's code) for each letter with a grave, acute, circumflex, tilde or ring: the
    plain letter from a-z and A-Z (80-99, A0-B9)."""
    plain = {ch: code for (code, ch) in MAIN.items() if 0x80 <= code <= 0xB9}
    found = []
    for (code, ch) in MAIN.items():
        parts = unicodedata.normalize('NFKD', ch)
        if len(parts) == 2 and parts[1] in MARKS and parts[0] in plain:
            found.append((code, plain[parts[0]]))
    return found


def top(rows):
    return next(y for (y, r) in enumerate(rows) if r)


def body(rows):
    """A glyph without a mark it has apart from it above a blank row (the dot of i or j): its letter."""
    first = top(rows)
    gap = next((y for y in range(first, len(rows)) if not rows[y]), len(rows))
    return [0] * gap + rows[gap:] if any(rows[gap:]) else rows


class TestFont(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nine = core.font_rows(9)
        cls.eight = core.font_rows(8)

    def ascii_codes(self):
        return [(code, ch) for (code, ch) in MAIN.items() if code not in NAMED_GLYPHS and '!' <= ch <= '~']

    def test_shape(self):
        self.assertEqual((len(self.nine), {len(g) for g in self.nine}), (256, {19}))
        self.assertEqual((len(self.eight), {len(g) for g in self.eight}), (256, {19}))

    def test_ascii_ink_lies_in_columns_1_to_7(self):
        for (code, ch) in self.ascii_codes():
            self.assertEqual([r & 0x101 for r in self.nine[code]], [0] * 19, f'{code:#04x} {ch!r}')

    def test_blank_codes_draw_nothing(self):
        for (code, ch) in STATUS.items():
            if ch == ' ' and code not in NAMED_GLYPHS:
                self.assertEqual(self.nine[code], [0] * 19, hex(code))

    def test_codes_with_no_glyph_draw_the_box(self):
        box = self.nine[BOXED[0]]
        self.assertEqual(box[4], 0x07C)  # the box's top: columns 2-6
        for code in BOXED:
            self.assertEqual(self.nine[code], box, hex(code))

    def test_everything_else_has_ink(self):
        for code in range(256):
            if code not in BOXED and STATUS[code] != ' ':
                self.assertTrue(any(self.nine[code]), hex(code))

    def test_field_mark_and_dup_are_barred(self):
        for (barred, plain) in ((0x9E, 0xBE), (0x9F, 0xBF)):  # 0xBE and 0xBF are a plain ; and *
            self.assertEqual(self.nine[barred][4:6], [0x0FE, 0x0FE], hex(barred))
            self.assertNotEqual(self.nine[plain][4], 0x0FE, hex(plain))

    def test_eight_columns_come_from_nine(self):
        for code in range(256):
            (nine, eight) = (self.nine[code], self.eight[code])
            if not any(r & 0x100 for r in nine):
                self.assertEqual(eight, [r & 0xFF for r in nine], hex(code))
            else:
                self.assertIn(eight, [merged(nine, x) for x in range(8)], hex(code))

    def test_the_ink_table_has_each_glyphs_lines_with_ink_at_both_widths(self):
        # render.c fills a line no glyph in the row has ink on, by this table (#52).
        ink = core.font_ink()
        for (table, width) in ((self.nine, 9), (self.eight, 8)):
            for code in range(256):
                lines = sum(1 << y for (y, r) in enumerate(table[code]) if r)
                self.assertEqual(ink[code], lines, f'{code:#04x} at {width} columns')

    def test_boxes_keep_both_borders_at_640(self):
        for code in BOXES:
            for (row, (nine, eight)) in enumerate(zip(self.nine[code], self.eight[code])):
                if nine & 0x101 == 0x101:
                    self.assertEqual(eight & 0x81, 0x81, f'{code:#04x} row {row}')

    def test_diaereses_have_both_dots_above_the_letter(self):
        # Each dot is about a pixel square at 16 px; the bake keeps one that straddles a pixel edge (#57). At
        # Model 3's and Model 4's heights too (#110): diaereses were the bake's known difficulty.
        codes = [code for (code, ch) in MAIN.items() if '\u0308' in unicodedata.normalize('NFKD', ch)]
        self.assertEqual(len(codes), 13)  # ¨ ÿ, ü twice, ä ë ï ö, Ä Ë Ï Ö Ü
        for height in HEIGHTS:
            for (width, table) in ((9, core.font_rows(9, height)), (8, core.font_rows(8, height))):
                for code in codes:
                    rows = table[code]
                    first = top(rows)
                    gap = next((y for y in range(first, height) if not rows[y]), height)
                    message = f'{code:#04x} {MAIN[code]} at {width} columns, {height} lines'
                    dots = marks(rows[first:gap], width)
                    self.assertEqual(len(dots), 2, message)
                    self.assertEqual(*[sorted({y for (_, y) in dot}) for dot in dots], message)  # side by side
                    self.assertEqual(*[len(dot) for dot in dots], message)  # alike
                    self.assertEqual(any(rows[gap:]), MAIN[code] != '¨', message)  # the letter, below a blank row


class TestShortCells(unittest.TestCase):
    """The font at Model 3's and Model 4's cells, 14 and 10 lines (#110)."""

    @classmethod
    def setUpClass(cls):
        cls.tables = {h: (core.font_rows(9, h), core.font_rows(8, h)) for h in HEIGHTS}

    def test_shape(self):
        for height in HEIGHTS:
            for table in self.tables[height]:
                self.assertEqual((len(table), {len(g) for g in table}), (256, {height}), height)

    def test_every_glyph_with_ink_keeps_some(self):
        nine19 = self.tables[19][0]
        for height in (14, 10):
            for code in range(256):
                self.assertEqual(any(self.tables[height][0][code]), any(nine19[code]), (hex(code), height))

    def test_blank_codes_draw_nothing_and_boxes_are_alike(self):
        for height in (14, 10):
            nine = self.tables[height][0]
            for (code, ch) in STATUS.items():
                if ch == ' ' and code not in NAMED_GLYPHS:
                    self.assertEqual(nine[code], [0] * height, (hex(code), height))
            for code in BOXED:
                self.assertEqual(nine[code], nine[BOXED[0]], (hex(code), height))

    def test_ascii_ink_lies_in_columns_1_to_7(self):
        for height in (14, 10):
            for (code, ch) in MAIN.items():
                if code not in NAMED_GLYPHS and '!' <= ch <= '~':
                    self.assertEqual([r & 0x101 for r in self.tables[height][0][code]], [0] * height,
                                     (hex(code), ch, height))

    def test_eight_columns_come_from_nine(self):
        for height in (14, 10):
            (nine, eight) = self.tables[height]
            for code in range(256):
                if not any(r & 0x100 for r in nine[code]):
                    self.assertEqual(eight[code], [r & 0xFF for r in nine[code]], (hex(code), height))
                else:
                    self.assertIn(eight[code], [merged(nine[code], x) for x in range(8)], (hex(code), height))

    def test_the_ink_tables(self):
        for height in (14, 10):
            ink = core.font_ink(height)
            for (table, width) in zip(self.tables[height], (9, 8)):
                for code in range(256):
                    lines = sum(1 << y for (y, r) in enumerate(table[code]) if r)
                    self.assertEqual(ink[code], lines, f'{code:#04x} at {width} columns, {height} lines')

    def test_marks_above_letters_survive(self):
        # The grave, acute, circumflex, tilde and ring: the accented letter differs from the plain one and its ink
        # starts no lower than the plain letter's body (i without its dot, which the short cells move up), at
        # every height and width. 3270font sets the first four touching the capitals at 19 lines, so no blank
        # row is asked.
        found = accented()
        self.assertEqual(len(found), 44)
        for height in HEIGHTS:
            for (table, width) in zip(self.tables[height], (9, 8)):
                for (code, plain) in found:
                    message = f'{code:#04x} {MAIN[code]} at {width} columns, {height} lines'
                    self.assertNotEqual(table[code], table[plain], message)
                    self.assertLessEqual(top(table[code]), top(body(table[plain])), message)
