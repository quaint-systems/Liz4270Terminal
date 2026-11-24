#!/usr/bin/env python
# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Bake the firmware's font, firmware/core/font_3270.c, from the 3270font release (#26).

  curl -sSfL -o /tmp/3270.zip https://github.com/rbanffy/3270font/releases/download/v3.0.1/3270_fonts_d916271.zip
  python3 -m venv /tmp/fontvenv && /tmp/fontvenv/bin/pip install fonttools==4.66.1 pillow==12.3.0
  /tmp/fontvenv/bin/python tools/sim/bake_font.py /tmp/3270.zip [--sheet OUT.png]

Each display code gets the first of these that applies:
  1. its glyph in display_codes.NAMED_GLYPHS, by name;
  2. a blank, where STATUS has a space;
  3. STATUS's character, where the font has it;
  4. a box, as the simulator draws a symbol it can't.

The glyphs are drawn as tools/testcard/gen_card_data.py draws them: 16 px, from
160 px with the offset (0.2, 0.7), box-filtered and thresholded at 50%, on
baseline 14 of a 9 x 19 cell. Then a blob of ink (8-connected at 160 px) that
lights no pixel of its own keeps its most-covered pixels, as many as its ink
would fill (#57). A blob lights a pixel of its own when it supplies the most
ink to one of the lit pixels; a diaeresis dot is about a pixel of ink, so one
that straddles a pixel edge would otherwise vanish. Ownership is the test, not
whether any of the blob's ink is lit, because a dot's fringe in a pixel its
letter lights would otherwise pass for the dot. A blob with less ink in all
than the threshold asks of one pixel stays dropped, so a speck of
anti-aliasing never becomes a pixel. The test card's ASCII has no such blob,
so it still matches the card bit for bit. The bake prints the glyphs that kept
a blob, each with the pixels it lit. It stops if any ink falls outside the
cell. font_3270_8x19, for 640 x 480's 8-dot cells, drops a blank ninth column,
or else ORs together the adjacent pair of columns that differ least, nearest
the middle on a tie. font_3270_ink has each glyph's lines with ink, for
render.c to fill a line no glyph in a row has ink on (#52). Fitting a glyph to
8 columns never empties a line, so one table serves both widths.

Model 3's and Model 4's cells are 14 and 10 lines (#110), and their glyphs
come from the 19-line ones, not a new drawing: line k of a short cell ORs the
19-line rows whose centres fall in its band, the 19 lines squashed about the
baseline (row 14 plus the 0.7 offset onto line 10 or 7, 14 x height / 19
rounded down), so no stroke or dot can vanish. A mark apart from its letter
at 19 lines, above a blank row (a diaeresis, the dots on i and j, a lower
case accent), stays apart: where the merge would put it against the letter,
it moves up until a blank line is between them. A mark with no line to move
to stops the bake. A squash of the drawing itself lost the dots at 10 lines
and broke the letters up (#110's bench, Oct 12).

NAMED_GLYPHS are unmapped in the font, so Pillow can't draw them by character.
The script maps them to temporary code points in a copy of the font in memory;
nothing it writes carries them. It refuses a glyph the release maps into the
private use area, where the logos under other terms live.

font_3270.c is a Modified Version of the Font Software, under the SIL Open Font
License 1.1 alone (NOTICE). The same inputs give the same bytes. --sheet draws
every named glyph, and every glyph that kept a blob, at both widths, enlarged,
to check by eye.
"""

import argparse
import io
import os
import sys
import textwrap
import unicodedata
import zipfile

from PIL import Image, ImageDraw, ImageFont

from display_codes import MAIN, NAMED_GLYPHS, PLACEHOLDER, STATUS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(ROOT, 'firmware', 'core', 'font_3270.c')

CELL_W = 9
CELL_H = 19
BASELINE = 14
HEIGHTS = (19, 14, 10)  # Model 2's cells, Model 3's and Model 4's (#110)
SCALE = 10           # drawn at 160 px for the 16 px font, then box-filtered down
OFFSET = (0.2, 0.7)  # gen_card_data.py's: the fewest half-covered pixels
THRESHOLD = 128
MARGIN = 2           # pixels drawn round the cell, to catch ink outside it
TEMP_BASE = 0xF0000  # in-memory code points for NAMED_GLYPHS; never written out

COPYRIGHT = [
    'Copyright 2011-2021 The 3270font Project Authors (https://github.com/rbanffy/3270font)',
    'Copyright 2022 The 3270font Authors (https://github.com/rbanffy/3270font)',
]


def private_use(code_point):
    return 0xE000 <= code_point <= 0xF8FF or code_point >= 0xF0000


def load(release_path):
    """Pillow's font, with NAMED_GLYPHS at temporary code points; the release's cmap; and those code points."""
    # fontTools only here, so test_bake_font.py can import the rest with Pillow alone.
    from fontTools.ttLib import TTFont
    from fontTools.ttLib.tables._c_m_a_p import CmapSubtable
    from subset_font import RELEASE_SHA256, _read_checked

    release = zipfile.ZipFile(io.BytesIO(_read_checked(release_path, RELEASE_SHA256)))
    font = TTFont(io.BytesIO(release.read('3270-Regular.ttf')), recalcTimestamp=False)
    cmap = font.getBestCmap()
    names = sorted(set(NAMED_GLYPHS.values()))
    glyph_order = set(font.getGlyphOrder())
    for name in names:
        if name not in glyph_order:
            sys.exit(f'3270font has no glyph called {name!r}')
        if any(private_use(cp) for (cp, glyph) in cmap.items() if glyph == name):
            sys.exit(f'{name!r} is mapped into the private use area; leave it out')
    temporary = {name: TEMP_BASE + i for (i, name) in enumerate(names)}
    table = CmapSubtable.newSubtable(12)
    (table.platformID, table.platEncID, table.language) = (3, 10, 0)
    table.cmap = {**cmap, **{cp: name for (name, cp) in temporary.items()}}
    font['cmap'].tables = [t for t in font['cmap'].tables if (t.platformID, t.platEncID) != (3, 10)] + [table]
    data = io.BytesIO()
    font.save(data)
    data.seek(0)
    return (ImageFont.truetype(data, 16 * SCALE), cmap, temporary)


def blobs(big):
    """The drawing's blobs of ink, 8-connected at 160 px: for each, the ink it puts in each 16 px pixel."""
    (w, h) = big.size
    ink = big.tobytes()
    seen = bytearray(w * h)
    found = []
    for (start, value) in enumerate(ink):
        if not value or seen[start]:
            continue
        seen[start] = 1
        (stack, share) = ([start], {})
        while stack:
            (y, x) = divmod(stack.pop(), w)
            pixel = (x // SCALE, y // SCALE)
            share[pixel] = share.get(pixel, 0) + ink[y * w + x]
            for ny in range(max(y - 1, 0), min(y + 2, h)):
                for nx in range(max(x - 1, 0), min(x + 2, w)):
                    if ink[ny * w + nx] and not seen[ny * w + nx]:
                        seen[ny * w + nx] = 1
                        stack.append(ny * w + nx)
        found.append(share)
    return found


def vanishing(big, lit):
    """The pixels kept for the blobs that light no pixel of their own (#57).

    A blob lights a pixel of its own when it supplies the most ink to one of
    the lit pixels. One that doesn't keeps its most-covered pixels, as many as
    its ink would fill, the leftmost then topmost on a tie, unless it has less
    ink in all than the threshold asks of one pixel.
    """
    shares = blobs(big)
    owners = {max(range(len(shares)), key=lambda b: shares[b].get(pixel, 0)) for pixel in lit}
    full = SCALE * SCALE * 255  # a 16 px pixel's ink, summed at 160 px
    kept = set()
    for (b, share) in enumerate(shares):
        ink = sum(share.values())
        if b in owners or ink < THRESHOLD * SCALE * SCALE:
            continue
        count = (ink + full // 2) // full  # at least 1: past the floor, the ink rounds up to a pixel
        kept |= set(sorted(share, key=lambda p: (-share[p], p))[:count])
    return kept


def pixels(big):
    """The 16 px pixels a 160 px drawing lights, and those of them lit only to keep a blob."""
    (w, h) = (big.width // SCALE, big.height // SCALE)
    small = big.resize((w, h), Image.BOX)
    lit = {(x, y) for x in range(w) for y in range(h) if small.getpixel((x, y)) >= THRESHOLD}
    added = vanishing(big, lit) - lit
    return (lit | added, added)


def raster(pillow_font, char):
    """The glyph's 19 rows in the 9 x 19 cell, bit x for pixel x, and how many pixels it lit to keep a blob."""
    (w, h) = (CELL_W + 2 * MARGIN, CELL_H + 2 * MARGIN)
    big = Image.new('L', (w * SCALE, h * SCALE), 0)
    (dx, dy) = OFFSET
    ImageDraw.Draw(big).text(((MARGIN + dx) * SCALE, (MARGIN + BASELINE + dy) * SCALE), char,
                             font=pillow_font, fill=255, anchor='ls')
    (lit, added) = pixels(big)
    lit = {(x - MARGIN, y - MARGIN) for (x, y) in lit}
    outside = sorted(p for p in lit if not (0 <= p[0] < CELL_W and 0 <= p[1] < CELL_H))
    if outside:
        sys.exit(f'U+{ord(char):04X}: ink outside the {CELL_W} x {CELL_H} cell at {outside[:4]}')
    return ([sum(1 << x for x in range(CELL_W) if (x, y) in lit) for y in range(CELL_H)], len(added))


def box():
    """What the simulator draws for a symbol it has no glyph for (screen.py)."""
    rows = [0] * CELL_H
    for y in range(4, CELL_H - 4):
        rows[y] = (1 << 2) | (1 << (CELL_W - 3))
    rows[4] = rows[CELL_H - 5] = sum(1 << x for x in range(2, CELL_W - 2))
    return rows


class NoRoom(Exception):
    """A mark apart from its letter at 19 lines that a short cell has no line to keep apart (#110)."""


def baseline(height):
    """The line a cell of this height sets its baseline on: 14 of 19, 10 of 14, 7 of 10 (#110)."""
    return BASELINE * height // CELL_H


def merged_rows(rows, height):
    """rows, 19 lines, merged to height: line k ORs the rows whose centres fall in its band, the 19 lines
    squashed about the baseline with OFFSET's 0.7 (#110)."""
    (dy, step) = (OFFSET[1], CELL_H / height)
    out = []
    for k in range(height):
        lo = BASELINE + dy + (k - baseline(height) - dy) * step
        line = 0
        for y in range(CELL_H):
            if lo <= y + 0.5 < lo + step:
                line |= rows[y]
        out.append(line)
    return out


def shorten(rows, height):
    """A 19-line glyph at a shorter cell's height (#110): merged, with a mark that's apart from its letter at
    19 lines (above a blank row, with ink below it) moved up to keep a blank line between them. NoRoom if it
    can't be."""
    if height == CELL_H:
        return list(rows)
    lit = [y for (y, r) in enumerate(rows) if r]
    if not lit:
        return [0] * height
    gap = next((y for y in range(lit[0], CELL_H) if not rows[y]), CELL_H)
    if not any(rows[gap:]):
        return merged_rows(rows, height)
    mark = merged_rows([r if y < gap else 0 for (y, r) in enumerate(rows)], height)
    body = merged_rows([r if y >= gap else 0 for (y, r) in enumerate(rows)], height)
    mark_top = next(y for (y, r) in enumerate(mark) if r)
    mark_bottom = max(y for (y, r) in enumerate(mark) if r)
    body_top = next(y for (y, r) in enumerate(body) if r)
    shift = max(0, mark_bottom - (body_top - 2))
    if shift > mark_top:
        raise NoRoom(f'no line above the mark at {height} lines')
    mark = mark[shift:] + [0] * shift
    return [m | b for (m, b) in zip(mark, body)]


def ink(rows):
    """A glyph's lines with ink, bit n for line n."""
    return sum(1 << y for (y, r) in enumerate(rows) if r)


def eight_columns(rows):
    """A 9-column glyph fitted to 8 columns: drop a blank ninth, or OR the closest pair."""
    if not any(r >> 8 & 1 for r in rows):
        return [r & 0xFF for r in rows]

    def column(x):
        return [r >> x & 1 for r in rows]

    def cost(x):
        return (sum(a != b for (a, b) in zip(column(x), column(x + 1))), abs(x - 3.5))

    x = min(range(8), key=cost)
    low = (1 << x) - 1
    return [(r & low) | ((r >> x | r >> (x + 1)) & 1) << x | (r >> (x + 2)) << (x + 1) for r in rows]


def glyphs(pillow_font, cmap, temporary):
    """Each display code's 9-column rows, how each was chosen, and how many pixels each code lit to keep a blob."""
    (table, how, kept) = ([], [], {})
    for code in range(256):
        name = NAMED_GLYPHS.get(code)
        char = STATUS[code]
        if name:
            (rows, added) = raster(pillow_font, chr(temporary[name]))
            kind = name
        elif char == ' ':
            (rows, added, kind) = ([0] * CELL_H, 0, 'blank')
        elif char != PLACEHOLDER and ord(char) in cmap:
            (rows, added) = raster(pillow_font, char)
            kind = f'U+{ord(char):04X}'
        else:
            (rows, added, kind) = (box(), 0, 'box')
        table.append(rows)
        how.append(kind)
        if added:
            kept[code] = added
    return (table, how, kept)


def c_source(tables, how):
    nine = tables[19]
    eight = [eight_columns(rows) for rows in nine]
    named = ' '.join(f'{code:02x}={NAMED_GLYPHS[code]}' for code in sorted(NAMED_GLYPHS))
    boxed = ' '.join(f'{code:02x}' for code in range(256) if how[code] == 'box')
    lines = [
        *[f'// {line}' for line in COPYRIGHT],
        '// SPDX-License-Identifier: OFL-1.1',
        '',
        '// Generated by tools/sim/bake_font.py from the 3270font v3.0.1 release (#26). Do not edit.',
        '//',
        '// 3270font at 16 px, one bit per pixel, indexed by display code (font_3270.h), at 19 lines and',
        '// merged to 14 and 10 for Model 3 and Model 4 (#110).',
        '// Named glyphs:',
        *[f'//   {line}' for line in textwrap.wrap(named, 74)],
        '// Boxes, for codes with no glyph:',
        *[f'//   {line}' for line in textwrap.wrap(boxed, 74)],
        '//',
        '// This file is a Modified Version of the Font Software and is licensed under',
        '// the SIL Open Font License, Version 1.1, alone: the license text is',
        '// tools/sim/fonts/OFL.txt.',
        '',
        '#include "font_3270.h"',
        '',
        'const uint16_t font_3270_9x19[FONT_GLYPHS][FONT_ROWS] = {',
        *[f'    /* {code:02x} */ {{{", ".join(f"0x{r:03x}" for r in rows)}}},' for (code, rows) in enumerate(nine)],
        '};',
        '',
        'const uint8_t font_3270_8x19[FONT_GLYPHS][FONT_ROWS] = {',
        *[f'    /* {code:02x} */ {{{", ".join(f"0x{r:02x}" for r in rows)}}},' for (code, rows) in enumerate(eight)],
        '};',
        '',
        'const uint32_t font_3270_ink[FONT_GLYPHS] = {',
        *[f'    /* {code:02x} */ {", ".join(f"0x{ink(rows):05x}" for rows in nine[code:code + 8])},'
          for code in range(0, 256, 8)],
        '};',
        '',
        *[line for height in (14, 10) for line in (
            f'const uint16_t font_3270_9x{height}[FONT_GLYPHS][FONT_ROWS_{height}] = {{',
            *[f'    /* {code:02x} */ {{{", ".join(f"0x{r:03x}" for r in rows)}}},'
              for (code, rows) in enumerate(tables[height])],
            '};',
            '',
            f'const uint8_t font_3270_8x{height}[FONT_GLYPHS][FONT_ROWS_{height}] = {{',
            *[f'    /* {code:02x} */ {{{", ".join(f"0x{r:02x}" for r in eight_columns(rows))}}},'
              for (code, rows) in enumerate(tables[height])],
            '};',
            '',
            f'const uint32_t font_3270_ink{height}[FONT_GLYPHS] = {{',
            *[f'    /* {code:02x} */ {", ".join(f"0x{ink(rows):05x}" for rows in tables[height][code:code + 8])},'
              for code in range(0, 256, 8)],
            '};',
            '',
        )],
    ]
    return '\n'.join(lines)


def sheet(path, tables, how, kept):
    """Every named glyph, every accented letter, and every glyph that kept a blob, at each height and at 9
    columns and 8, enlarged, with its code and kind (#57, #110)."""
    (dot, per_row) = (5, 3)
    accented = {code for (code, ch) in MAIN.items() if len(unicodedata.normalize('NFKD', ch)) > 1}
    codes = sorted({*NAMED_GLYPHS, *accented, *kept})
    (cell_w, cell_h) = (sum(2 * CELL_W * dot + 30 for _ in HEIGHTS), CELL_H * dot + 16)
    image = Image.new('RGB', (per_row * cell_w, -(-len(codes) // per_row) * cell_h), 'white')
    draw = ImageDraw.Draw(image)
    for (i, code) in enumerate(codes):
        (x0, y0) = ((i % per_row) * cell_w, (i // per_row) * cell_h)
        draw.text((x0, y0), f'{code:02X} {how[code]}', fill='black')
        dx = 0
        for height in HEIGHTS:
            nine = tables[height][code]
            for (rows, width) in ((nine, CELL_W), (eight_columns(nine), 8)):
                draw.rectangle([x0 + dx - 1, y0 + 11, x0 + dx + width * dot, y0 + 12 + height * dot],
                               outline=(160, 160, 255))
                for y in range(height):
                    for x in range(width):
                        if rows[y] >> x & 1:
                            draw.rectangle([x0 + dx + x * dot, y0 + 12 + y * dot,
                                            x0 + dx + (x + 1) * dot - 1, y0 + 12 + (y + 1) * dot - 1], fill='black')
                dx += width * dot + 6
            dx += 12
    image.save(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('release', help='3270_fonts_d916271.zip, the 3270font v3.0.1 release')
    parser.add_argument('--sheet', help='also draw the named glyphs, and those that kept a blob, to this PNG')
    args = parser.parse_args()
    (pillow_font, cmap, temporary) = load(args.release)
    (nine, how, kept) = glyphs(pillow_font, cmap, temporary)
    tables = {19: nine}
    for height in HEIGHTS[1:]:
        tables[height] = []
        for (code, rows) in enumerate(nine):
            try:
                tables[height].append(shorten(rows, height))
            except NoRoom as error:
                sys.exit(f'{code:02x} ({how[code]}): {error}')
    with open(OUT, 'w', encoding='ascii', newline='\n') as stream:
        stream.write(c_source(tables, how))
    print(f'{OUT}: {len(NAMED_GLYPHS)} named, {how.count("box")} boxes, {how.count("blank")} blank')
    print(f'kept a blob (pixels lit): {" ".join(f"{code:02x}:{n}" for (code, n) in kept.items()) or "none"}')
    if args.sheet:
        sheet(args.sheet, tables, how, kept)
        print(f'sheet: {args.sheet}')


if __name__ == '__main__':
    main()
