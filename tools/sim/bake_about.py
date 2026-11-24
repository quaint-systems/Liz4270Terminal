#!/usr/bin/env python
# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Bake SetUp's About pages (#126) into firmware/core/about_text.c and about_text.h.

  python tools/sim/bake_about.py          write them
  python tools/sim/bake_about.py --check  exit 1 if either is out of date; write nothing

Page 1's credits are CREDITS. The pages after it come from GROUPS, in order, each license starting a new page:
its copyright lines (one longer than a page's 78 columns wrapped at a space, with a two-space indent), a blank
line, then LICENSES/<spdx>.txt line by line, as it's wrapped there. A page holds 18 lines (rows 5-22), and none
starts or ends with a blank one; row 3 names the license and what it covers, with " (continued)" after its first
page. Text is Latin-1, written to C with escapes for anything outside ASCII. A character with no display code,
or text wider than its columns, is refused.

GROUPS' copyright lines are verbatim from the files the image keeps code of: about_audit.py checks a build
against them, and NOTICE holds each one (test_about.py).
"""

import argparse
import os
import sys
import textwrap
from typing import NamedTuple

from display_codes import MAIN, PLACEHOLDER
from paths import ROOT

LICENSES_DIR = os.path.join(ROOT, 'LICENSES')
H_PATH = os.path.join(ROOT, 'firmware', 'core', 'about_text.h')
C_PATH = os.path.join(ROOT, 'firmware', 'core', 'about_text.c')
WIDTH = 78          # a license page's line: columns 2-79
PAGE_LINES = 18     # rows 5-22
HEADING_WIDTH = 80  # row 3
CREDIT_WIDTHS = (19, 36, 19)  # page 1's columns: component, by whom, license
HEADER = '// Copyright (c) 2026, CoffeeMuse\n// SPDX-License-Identifier: ISC\n'
GLYPHS = frozenset(glyph for (code, glyph) in MAIN.items() if code < 0xC0 and glyph != PLACEHOLDER)


class Credit(NamedTuple):
    component: str  # page 1, column 5, up to 19 columns
    by: str         # column 25, up to 36
    license: str    # column 62, up to 19


class Group(NamedTuple):
    spdx: str            # LICENSES/<spdx>.txt
    name: str            # row 3, before the colon
    covers: str          # row 3, after it
    copyrights: tuple    # verbatim, as the linked files carry them
    objects: tuple = ()  # newlib's: the toolchain archives' members this text covers (about_audit.py)


class Page(NamedTuple):
    heading: str  # row 3
    lines: tuple  # rows 5 on, from column 2


CREDITS = (
    Credit('Liz4270', 'CoffeeMuse', 'ISC'),
    Credit('coax, oec', 'Andrew Kay', 'ISC'),
    Credit('coax-tcp, oec-tcp', 'Hans Hübner', 'ISC'),
    Credit('3270font', 'Ricardo Banffy and others', 'OFL-1.1'),
    Credit('pico-sdk', 'Raspberry Pi', 'BSD-3-Clause'),
    Credit('TinyUSB', 'Ha Thach and others', 'MIT'),
    Credit('Pico-PIO-USB', 'sekigon-gonnoc', 'MIT'),
    Credit('newlib', 'Red Hat, UC Berkeley and others', 'BSD-style'),
)

GROUPS = (
    Group('ISC', 'ISC License', 'Liz4270, coax-tcp', (
        'Copyright (c) 2026, CoffeeMuse',
        'Copyright (c) 2019, Andrew Kay',
        'Copyright (c) 2025, Hans Hübner',
    )),
    Group('BSD-3-Clause', 'BSD 3-Clause License', 'pico-sdk, pico-examples', (
        'Copyright 2020 (c) 2020 Raspberry Pi (Trading) Ltd.',
        'Copyright (c) 2020 Raspberry Pi (Trading) Ltd.',
        'Copyright (c) 2021 Raspberry Pi (Trading) Ltd.',
        'Copyright (c) 2023 Raspberry Pi (Trading) Ltd.',
        'Copyright (c) 2024 Raspberry Pi (Trading) Ltd.',
        'Copyright (c) 2024 Raspberry Pi Ltd.',
        'Copyright (c) 2025 Raspberry Pi (Trading) Ltd.',
        'Copyright (c) 2026 Raspberry Pi (Trading) Ltd.',
        'Copyright (c) 2019 Keith Packard',
        'Copyright (c) 2024 Stephen Street (stephen@redrocketcomputing.com).',
        'Copyright (c) 2025 Dan Halbert for Adafruit Industries',
    )),
    Group('MIT', 'MIT License', 'TinyUSB, Pico-PIO-USB, parts of pico-sdk', (
        'Copyright (c) 2018, hathach (tinyusb.org)',
        'Copyright (c) 2019 Ha Thach (tinyusb.org)',
        'Copyright (c) 2021 Ha Thach (tinyusb.org)',
        'Copyright (c) 2021 Ha Thach (tinyusb.org) for Double Buffered',
        'Copyright (c) 2021, Ha Thach (tinyusb.org)',
        'Copyright (c) 2022, Ha Thach (tinyusb.org)',
        'Copyright (c) 2020 Raspberry Pi (Trading) Ltd.',
        '(c) Marco Paland (info@paland.com) 2014-2019, PALANDesign Hannover, Germany',
        'Copyright (c) 2019 Damien P. George',
        'Copyright (c) 2020 Reinhard Panhuber - rework to unmasked pointers',
        'Copyright (c) 2021 sekigon-gonnoc',
    )),
    Group('OFL-1.1', 'SIL Open Font License 1.1', '3270font', (
        'Copyright 2011-2021 The 3270font Project Authors (https://github.com/rbanffy/3270font)',
        'Copyright 2022 The 3270font Authors (https://github.com/rbanffy/3270font)',
    )),
)


# newlib 4.6.0, the toolchain's libg.a: each kept object's notices, read from its source in newlib-4.6.0.20260123
# (the Arm machine directory's taking precedence, and the files it includes), grouped by wording (#126). Only the
# objects the image keeps some of are listed, and only their lines (#129): about_audit.py reports any other.
NEWLIB_VERSION = '4.6.0'  # the release NEWLIB's notices were read from; about_audit.py checks the toolchain's
NEWLIB = (
    Group('LicenseRef-newlib-RedHat', "Red Hat's BSD License", 'newlib, the files with no notice of their own', (
        'Copyright (c) 1994-2009  Red Hat, Inc. All rights reserved.',
    ), (
        'libc_a-calloc.o', 'libc_a-callocr.o', 'libc_a-errno.o', 'libc_a-freer.o', 'libc_a-impure.o',
        'libc_a-lock.o', 'libc_a-malloc.o', 'libc_a-mallocr.o', 'libc_a-memcmp.o', 'libc_a-memset.o',
        'libc_a-mlock.o', 'libc_a-reent.o', 'libc_a-sbrkr.o', 'libc_a-strlen-stub.o', 'libc_a-strtok.o',
    )),
    Group('LicenseRef-newlib-UCB', 'Berkeley License', 'newlib, developed by the University of California, Berkeley', (
        'Copyright (c) 1990 The Regents of the University of California.',
        'All rights reserved.',
    ), (
        'libc_a-findfp.o',
    )),
    Group('LicenseRef-newlib-UCB-BSD', "BSD 3-Clause License, Berkeley's", 'newlib', (
        'Copyright (c) 1982, 1986, 1993 The Regents of the University of California.',
        'Copyright (c) 1988 Regents of the University of California.',
        'Copyright (c) 1989 The Regents of the University of California.',
        'Copyright (c) 1990 Regents of the University of California.',
        'Copyright (c) 1990 The Regents of the University of California.',
        'All rights reserved.',
    ), (
        'libc_a-ctype_.o', 'libc_a-strtok_r.o', 'libc_a-strtol.o', 'libc_a-strtoul.o',
    )),
    Group('LicenseRef-newlib-ARM', "BSD 3-Clause License, Arm's", 'newlib', (
        'Copyright (c) 2008-2015 ARM Ltd',
        'Copyright (c) 2009 ARM Ltd',
        'Copyright (c) 2012-2014 ARM Ltd',
        'Copyright (c) 2013 ARM Ltd',
        'Copyright (c) 2013-2015 ARM Ltd',
        'All rights reserved.',
    ), (
        'libc_a-memcpy.o', 'libc_a-strcmp.o', 'libc_a-strlen-stub.o',
    )),
    Group('LicenseRef-newlib-STMicro', 'STMicroelectronics License', "newlib's sysconf", (
        'Copyright 2020, STMicroelectronics',
        'All rights reserved.',
    ), (
        'libc_a-sysconf.o',
    )),
)
GROUPS += NEWLIB


def license_lines(spdx):
    """LICENSES/<spdx>.txt's lines, right-stripped, without blank lines at either end."""
    with open(os.path.join(LICENSES_DIR, f'{spdx}.txt'), encoding='utf-8') as stream:
        lines = [line.rstrip() for line in stream.read().splitlines()]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return lines


def displayable(text):
    """text, refused at the first character the 3483-V has no display code for, rather than drawn as one it has."""
    for ch in text:
        if ch not in GLYPHS:
            raise ValueError(f'U+{ord(ch):04X} ({ch}) has no 3483-V display code: {text!r}')
    return text


def fits(text, width):
    """text, refused if it's wider than width, rather than run on into the next row."""
    if len(text) > width:
        raise ValueError(f'{len(text)} columns, over {width}: {text!r}')
    return text


def group_lines(group, text=None):
    """A license's lines as its pages show them: its copyright lines, a blank, then text (or its file's)."""
    lines = []
    for line in group.copyrights:
        lines += textwrap.wrap(line, WIDTH, subsequent_indent='  ', break_long_words=False, break_on_hyphens=False)
    return lines + [''] + (license_lines(group.spdx) if text is None else list(text))


def pages(groups=GROUPS, texts=None):
    """The license pages, page 2 onward. texts, {spdx: lines}, stands in for LICENSES/ in a test."""
    out = []
    for group in groups:
        lines = group_lines(group, None if texts is None else texts[group.spdx])
        first = True
        while True:
            while lines and not lines[0]:
                lines.pop(0)
            if not lines:
                break
            (chunk, lines) = (lines[:PAGE_LINES], lines[PAGE_LINES:])
            while not chunk[-1]:
                chunk.pop()
            heading = f'{group.name}: {group.covers}' + ('' if first else ' (continued)')
            out.append(Page(displayable(fits(heading, HEADING_WIDTH)),
                            tuple(displayable(fits(line, WIDTH)) for line in chunk)))
            first = False
    return out


def c_string(text):
    """text as a C string literal in Latin-1: \\xNN for anything outside ASCII, the literal closed after it so a
    hex digit that follows can't join the escape."""
    out = ''
    for ch in text:
        if ord(ch) > 0xFF:
            raise ValueError(f'U+{ord(ch):04X} ({ch}) has no Latin-1 byte, so no display code: {text!r}')
        if ord(ch) >= 0x80:
            out += f'\\x{ord(ch):02x}" "'
        elif ch in '\\"':
            out += '\\' + ch
        else:
            out += ch
    return f'"{out}"'


def h_text(credits, pages_):
    return f'''{HEADER}
// SetUp's About pages (#126): page 1's credits, and the license pages after it. Generated by
// tools/sim/bake_about.py from LICENSES/ and its tables: don't edit this; change them and run it again.

#ifndef LIZ_ABOUT_TEXT_H
#define LIZ_ABOUT_TEXT_H

#include <stddef.h>
#include <stdint.h>

#define ABOUT_CREDITS {len(credits)}u
#define ABOUT_PAGES {len(pages_)}u  // the license pages: page 2 onward
#define ABOUT_PAGE_LINES {PAGE_LINES}u  // rows 5-22

typedef struct {{
    const char *component, *by, *license;
}} about_credit_t;

typedef struct {{
    const char *heading;  // row 3
    uint8_t count;        // lines; the rest are NULL
    const char *lines[ABOUT_PAGE_LINES];
}} about_page_t;

extern const about_credit_t about_credits[ABOUT_CREDITS];
extern const about_page_t about_pages[ABOUT_PAGES];

#endif
'''


def c_text(credits, pages_):
    out = [HEADER, "// SetUp's About pages (#126). Generated by tools/sim/bake_about.py: don't edit this.", '',
           '#include "about_text.h"', '', 'const about_credit_t about_credits[ABOUT_CREDITS] = {']
    for credit in credits:
        out.append(f'    {{{c_string(credit.component)}, {c_string(credit.by)}, {c_string(credit.license)}}},')
    out += ['};', '', 'const about_page_t about_pages[ABOUT_PAGES] = {']
    for page in pages_:
        out.append(f'    {{{c_string(page.heading)}, {len(page.lines)}u, {{')
        out += [f'        {c_string(line)},' for line in page.lines]
        out += ['        NULL,'] * (PAGE_LINES - len(page.lines))
        out.append('    }},')
    out += ['};', '']
    return '\n'.join(out)


def outputs():
    """{path: text} for about_text.h and about_text.c, from the tables and LICENSES/."""
    pages_ = pages()
    for credit in CREDITS:
        for (text, width) in zip(credit, CREDIT_WIDTHS):
            displayable(fits(text, width))
    return {H_PATH: h_text(CREDITS, pages_), C_PATH: c_text(CREDITS, pages_)}


def stale(texts=None):
    """The outputs whose file differs from texts (outputs(), by default), as paths from ROOT."""
    out = []
    for (path, text) in (outputs() if texts is None else texts).items():
        current = None
        if os.path.exists(path):
            with open(path, encoding='utf-8') as stream:
                current = stream.read()
        if current != text:
            out.append(os.path.relpath(path, ROOT))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--check', action='store_true', help='exit 1 if a file is out of date; write nothing')
    args = parser.parse_args()
    texts = outputs()
    out_of_date = stale(texts)
    if not args.check:
        for (path, text) in texts.items():
            with open(path, 'w', encoding='utf-8') as stream:
                stream.write(text)
    for path in out_of_date:
        print(('out of date: ' if args.check else 'wrote ') + path)
    return 1 if args.check and out_of_date else 0


if __name__ == '__main__':
    sys.exit(main())
