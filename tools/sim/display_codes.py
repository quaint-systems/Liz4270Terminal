# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""3483-V display codes to Unicode, for the simulator's text and PNG.

Transcribed from our photographs of the terminal (captures/photos-20261003/
and, for the status line symbols 0xC0-0xFF, the close-ups in
captures/photos-20261004/; drawn by tools/capture/charmap.py): the main grid
shows 0x00-0xBF, and the status line pages show 0x00-0xFF in the status
line's own glyphs.
test_display_codes.py compares the table with oec's CHAR_MAP as a cross-check;
none of CHAR_MAP's entries disagree with the photos.

Medium confidence: 0x38 (degree, or a spacing ring above), 0x39 (caron) and
0x3F (cedilla). The status line symbols 0xC0-0xFF are settled by the
close-ups; most have no Unicode equivalent and show as the placeholder.
NAMED_GLYPHS gives the 3270font glyph the firmware draws for the symbols that have one.
"""

PLACEHOLDER = '�'  # a symbol with no Unicode equivalent

# Field Mark and DUP are ; and * with a bar above. Unicode has no single
# character for either, so the text shows the base character and the PNG
# draws the bar.
OVERBARRED = {0x9E, 0x9F}

_MAIN_ROWS = {
    0x00: '        ><[])(}{',
    0x10: ' =\'"/\\|¦?!$¢£¥₧¤',
    0x20: '0123456789ß§#@%_',
    0x30: '&-.,:+¬¯°ˇ^~¨`´¸',
    0x40: 'àèìòùãõÿàèéìòùüç',
    0x50: 'äëïöüâêîôûáéíóúñ',
    # The capitals of 0x40-0x4F, but 0x67-0x6F are drawn without their
    # accents, and 0x6E is a plain Y although 0x4E is ü (five photos).
    0x60: 'ÀÈÌÒÙÃÕYAEEIOUYC',
    0x70: 'ÄËÏÖÜÂÊÎÔÛÁÉÍÓÚÑ',
    0x80: 'abcdefghijklmnop',
    0x90: 'qrstuvwxyzæøåç;*',
    0xA0: 'ABCDEFGHIJKLMNOP',
    0xB0: 'QRSTUVWXYZÆØÅÇ;*',
}

_ = PLACEHOLDER
_OIA_ROWS = {
    # A frame open at the bottom: C0 empty, C1 with a block low in the middle,
    # C4 with one high on the right, C5 with both; C8 and C9 are C4 and C5 in
    # a dotted frame. Bit 1 makes no difference a still close-up shows: C2 is
    # drawn as C0, C3 as C1, C6 as C4, C7 as C5, CA as C8 and CB as C9.
    0xC0: _ * 12 + '    ',
    # P, S, A over a double underline, the insert caret (oec), B over a double
    # underline, 6 in a box, ▶, ▭, → (oec), a hollow wedge struck through by a
    # diagonal, ⇧ shift (oec), the operator stick figure (oec), B over an
    # underline, ⇩, ⍰, a solid block.
    0xD0: f'PS{_}‸{_}{_}▶▭→{_}⇧{_}{_}⇩⍰█',
    # As 0xC0-0xCB, with a tick at the foot of the frame's right side and the
    # low block on the left: E0 has the low block, E1 two side by side, E4 and
    # E5 add the high one, and E8 and E9 are E4 and E5 dotted. The bit 1 pairs
    # are drawn alike, as in the 0xC0 row.
    0xE0: _ * 12 + '    ',
    # A thin bolt (a diagonal with a short bar to the left), −, a Z-shaped
    # hook, _, the two halves of the clock (oec), ✗ (oec), ▬, ← (oec), the
    # solid form of D9's crossed wedge, ◦, a heavy ¬, 4 in a square, A over an
    # underline, ≡, the stick figure in a box.
    0xF0: f'{_}−{_}_{_}{_}✗▬←{_}◦¬{_}{_}≡{_}',
}
del _


def _table(rows):
    table = {}
    for (start, glyphs) in rows.items():
        if len(glyphs) != 16:
            raise ValueError(f'row {start:#04x} has {len(glyphs)} glyphs')
        for (offset, glyph) in enumerate(glyphs):
            table[start + offset] = glyph
    return table


MAIN = _table(_MAIN_ROWS)  # 0xC0-0xFF are field attributes in the main area
STATUS = _table({**_MAIN_ROWS, **_OIA_ROWS})

# The firmware draws these codes with 3270font glyphs that have no Unicode
# character, by glyph name (tools/sim/bake_font.py, #26). Matched against the
# close-ups in captures/photos-20261004/ (closeup-status-d0-df.jpg and
# closeup-status-f0-ff.jpg), and confirmed by CoffeeMuse on Oct 4, 2026.
# A named glyph wins over STATUS's character. 3270font's c0-cf and e0-ee are
# empty, so the frame symbols (C0-CB, E0-EB) stay boxes, as do the struck
# wedges D9 and F9, and D7 (▭, which 3270font lacks).
NAMED_GLYPHS = {
    0x9E: 'fm', 0x9F: 'dup',
    0xD2: 'boxA', 0xD3: 'insert', 0xD4: 'boxB', 0xD5: 'box6', 0xD8: 'rightarrow',
    0xDA: 'upshift', 0xDB: 'human', 0xDC: 'underB', 0xDD: 'downshift', 0xDE: 'boxquestion', 0xDF: 'boxsolid',
    0xF0: 'badcommhi', 0xF1: 'commhi', 0xF2: 'commjag', 0xF3: 'commlo',
    0xF4: 'clockleft', 0xF5: 'clockright', 0xF6: 'lock', 0xF8: 'leftarrow',
    0xFA: 'keyleft', 0xFB: 'keyright', 0xFC: 'box4', 0xFD: 'underA', 0xFE: 'magcard', 0xFF: 'boxhuman',
}
