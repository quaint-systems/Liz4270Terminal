# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The bake's rule for ink the threshold drops (bake_font.py, #57), on drawings made here."""

import unittest

from PIL import Image

from bake_font import SCALE, NoRoom, baseline, pixels, shorten


def drawing(*boxes):
    """A 160 px drawing, 6 x 6 pixels at 16 px, with each box (x0, y0, x1, y1) inked: 160 px units, x1 and y1 outside it."""
    big = Image.new('L', (6 * SCALE, 6 * SCALE), 0)
    for box in boxes:
        big.paste(255, box)
    return big


class TestBakeRule(unittest.TestCase):
    def test_a_dot_inside_a_pixel_lights_it_at_the_threshold(self):
        self.assertEqual(pixels(drawing((10, 10, 19, 19))), ({(1, 1)}, set()))  # 81% of (1, 1)

    def test_a_dot_across_a_pixel_edge_keeps_its_most_covered_pixel(self):
        # 45% of (1, 1) and 36% of (2, 1): the threshold drops both.
        self.assertEqual(pixels(drawing((15, 10, 24, 19))), ({(1, 1)}, {(1, 1)}))

    def test_each_dropped_dot_keeps_a_pixel(self):
        self.assertEqual(pixels(drawing((15, 10, 24, 19), (45, 10, 54, 19)))[1], {(1, 1), (4, 1)})

    def test_a_tie_keeps_the_leftmost_pixel_then_the_topmost(self):
        self.assertEqual(pixels(drawing((15, 10, 25, 19)))[1], {(1, 1)})  # 45% each of (1, 1) and (2, 1)
        self.assertEqual(pixels(drawing((10, 15, 19, 25)))[1], {(1, 1)})  # 45% each of (1, 1) and (1, 2)

    def test_a_blob_with_less_ink_than_the_threshold_stays_dropped(self):
        self.assertEqual(pixels(drawing((10, 10, 14, 20))), (set(), set()))  # 40% of (1, 1)
        speck = drawing()
        speck.putpixel((15, 15), 1)
        self.assertEqual(pixels(speck), (set(), set()))

    def test_a_hairline_keeps_as_many_pixels_as_its_ink_fills(self):
        # 40% of each of (1, 1) to (1, 5): two pixels of ink, all tied, so the topmost two.
        self.assertEqual(pixels(drawing((13, 10, 17, 60))), ({(1, 1), (1, 2)}, {(1, 1), (1, 2)}))

    def test_a_blob_that_lights_a_pixel_of_its_own_keeps_no_other(self):
        # 60% of (1, 1), then a tail of 40% down (1, 2) and (1, 3): the tail stays dropped.
        self.assertEqual(pixels(drawing((10, 10, 16, 20), (10, 20, 14, 40))), ({(1, 1)}, set()))

    def test_a_blob_that_only_shares_a_pixel_another_lights_keeps_its_own(self):
        # The dot puts 45% in (1, 1) and 27% in (2, 1). The stroke beside it puts 60% in (2, 1),
        # so (2, 1) is lit as the stroke's, and the dot keeps (1, 1).
        self.assertEqual(pixels(drawing((15, 10, 23, 19), (24, 10, 30, 20))), ({(1, 1), (2, 1)}, {(1, 1)}))


def glyph(*rows):
    """A 19-line glyph: rows {y: bits}."""
    found = dict(rows)
    return [found.get(y, 0) for y in range(19)]


DOTS = 0b100100     # two dots, columns 2 and 5
STEMS = 0b1000010   # two stems, columns 1 and 6


class TestShortenRule(unittest.TestCase):
    """Model 3's and Model 4's cells from the 19-line glyphs (#110): each short line ORs the 19-line rows whose
    centres fall in its band, the 19 lines squashed about the baseline, and a mark apart from its letter at 19
    lines stays apart."""

    def test_baselines(self):
        # The line each height sets its baseline on, the 19-line cell's 14 scaled down.
        self.assertEqual([baseline(h) for h in (19, 14, 10)], [14, 10, 7])

    def test_the_letters_last_row_lands_on_the_baseline_line(self):
        # Row 14, the 19-line letters' last, is line 7 of 10 and line 10 of 14.
        self.assertEqual(shorten(glyph((14, 2)), 10), [0] * 7 + [2] + [0] * 2)
        self.assertEqual(shorten(glyph((14, 2)), 14), [0] * 10 + [2] + [0] * 3)

    def test_no_row_is_lost(self):
        # Every 19-line row falls in some line's band: OR loses nothing.
        for height in (14, 10):
            for y in range(19):
                self.assertTrue(any(shorten(glyph((y, 1)), height)), (height, y))

    def test_rows_that_share_a_line_are_ored(self):
        self.assertEqual(shorten(glyph((8, 0b0011), (9, 0b1100)), 10)[4], 0b1111)

    def test_a_separate_mark_moves_up_to_keep_a_blank_line(self):
        # Dots at row 5, a blank row, the letter from row 7: at 10 lines the dots would touch it.
        rows = shorten(glyph((5, DOTS), *((y, STEMS) for y in range(7, 15))), 10)
        first = rows.index(DOTS)
        self.assertEqual((rows[first + 1], rows[first + 2]), (0, STEMS))

    def test_a_mark_already_apart_stays(self):
        # Dots at row 1, the letter from row 7: at 10 lines, line 0 and line 3, two blank lines between.
        self.assertEqual(shorten(glyph((1, DOTS), *((y, STEMS) for y in range(7, 15))), 10),
                         [DOTS, 0, 0] + [STEMS] * 5 + [0, 0])

    def test_a_touching_mark_isnt_moved(self):
        # An accent on the letter, with no blank row between them at 19 lines, is merged as it is.
        accent = glyph((4, 0b10000), (5, 0b10000), *((y, STEMS) for y in range(6, 15)))
        self.assertEqual(shorten(accent, 10)[1:4], [0, 0b10000, STEMS])

    def test_a_mark_with_no_room_stops_the_bake(self):
        # Dots on row 0 right above the letter: no line above them to move to.
        with self.assertRaises(NoRoom):
            shorten(glyph((0, DOTS), *((y, STEMS) for y in range(2, 15))), 10)

    def test_19_lines_are_as_they_are(self):
        rows = glyph((5, DOTS), *((y, STEMS) for y in range(7, 15)))
        self.assertEqual(shorten(rows, 19), rows)
