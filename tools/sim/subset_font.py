#!/usr/bin/env python
# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Rebuild tools/sim/fonts/ from the 3270font release (issue #5).

  curl -sSfL -o /tmp/3270.zip https://github.com/rbanffy/3270font/releases/download/v3.0.1/3270_fonts_d916271.zip
  curl -sSfL -o /tmp/OFL.txt https://openfontlicense.org/documents/OFL.txt
  python3 -m venv /tmp/fontvenv && /tmp/fontvenv/bin/pip install fonttools==4.66.1
  /tmp/fontvenv/bin/python tools/sim/subset_font.py /tmp/3270.zip /tmp/OFL.txt

It checks both downloads' sha256, subsets 3270-Regular.ttf to the characters
display_codes.py uses (plus the digits and slash of the cursor indicator),
marks its version string "(Liz4270 subset)", and writes the font, the
release's LICENSE.txt, the OFL text the font's own name table points to, and
covered.txt: the code points the subset can draw.

The full font also carries logo glyphs under other terms (see LICENSE.txt).
They sit in the private use area, which the subset leaves out. Run this again
whenever display_codes.py changes; the same inputs and fontTools version give
the same bytes, so the font's diff shows only what changed.
"""

import hashlib
import io
import os
import sys
import zipfile

from fontTools import subset
from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, 'fonts')
RELEASE_SHA256 = '623fb815b16d6c4940b5014a21c5474ef6cddb02c325d03f153341b676b4cffa'  # v3.0.1
OFL_SHA256 = '1d361a8f8e8ce6e68457dcd93fb56e162e6baa3bbb7e7573a290d44399f6b57e'
OFL_TEMPLATE_LINES = 5  # the template's copyright lines, replaced by the font's own


def _read_checked(path, sha256):
    with open(path, 'rb') as stream:
        data = stream.read()
    if hashlib.sha256(data).hexdigest() != sha256:
        sys.exit(f'{path}: unexpected sha256; is it the right download?')
    return data


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    release = zipfile.ZipFile(io.BytesIO(_read_checked(sys.argv[1], RELEASE_SHA256)))
    ofl = _read_checked(sys.argv[2], OFL_SHA256).decode('utf-8')

    sys.path.insert(0, HERE)
    import display_codes

    wanted = set(display_codes.MAIN.values()) | set(display_codes.STATUS.values()) | set('0123456789/')
    wanted -= {' ', display_codes.PLACEHOLDER}

    # Keep upstream's modified date rather than stamping today's.
    font = TTFont(io.BytesIO(release.read('3270-Regular.ttf')), recalcTimestamp=False)
    copyright_line = font['name'].getDebugName(0)
    options = subset.Options()
    options.name_IDs = ['*']  # keep the copyright and license records
    options.notdef_outline = True
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=sorted(ord(c) for c in wanted))
    subsetter.subset(font)
    # Tell the subset from the full font. 3270font reserves no font name, so
    # the OFL asks for no rename.
    for record in font['name'].names:
        if record.nameID == 5:  # version
            record.string = f'{record.toUnicode().rstrip()} (Liz4270 subset)'

    os.makedirs(FONTS, exist_ok=True)
    font.save(os.path.join(FONTS, '3270-Regular.ttf'))
    covered = sorted(font.getBestCmap())
    with open(os.path.join(FONTS, 'covered.txt'), 'w', encoding='ascii') as stream:
        stream.writelines(f'{code:04X}\n' for code in covered)
    with open(os.path.join(FONTS, 'LICENSE.txt'), 'wb') as stream:
        stream.write(release.read('LICENSE.txt'))
    with open(os.path.join(FONTS, 'OFL.txt'), 'w', encoding='utf-8') as stream:
        body = ofl.split('\n', OFL_TEMPLATE_LINES)[OFL_TEMPLATE_LINES]
        stream.write(f'{copyright_line}\n{body}')

    missing = ''.join(sorted(wanted - {chr(code) for code in covered}))
    print(f'{len(covered)} code points kept; not in the font, drawn as a box: {missing or "none"}')


if __name__ == '__main__':
    main()
