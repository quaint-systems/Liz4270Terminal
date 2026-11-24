#!/usr/bin/env python
# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Build the Liz4270 Display Station User's Guide (#136): docs/manual/ into build/manual/ as PDFs.

  $PY tools/manual/build.py                  a draft on US Letter and on A4
  $PY tools/manual/build.py --paper a4       a draft on A4 alone
  $PY tools/manual/build.py --release        the declared edition, from a clean tree at a release tag

It draws the terminal's screens through the firmware's renderer and walks SetUp for its rows, then runs
Typst once a paper, every paper at once. Both papers share one text area, so they break their pages alike;
built together, they're checked.
"""

import argparse
import json
import os
import re
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor

import manual_paths
import edition
import keys
import screens
import setup_walk
import typst_run
from edition import BuildError

PAPERS = ('us-letter', 'a4')
SHORT = {'us-letter': 'letter', 'a4': 'a4'}
SOURCE = os.path.join(manual_paths.MANUAL, 'manual.typ')


def pdf_name(stamp, paper):
    return f'liz4270-users-guide-{stamp.form}-{SHORT[paper]}.pdf'


def compare_placed(first, second):
    """Raise unless both papers put every heading and figure on the same page."""
    for (a, b) in zip(first, second):
        if a['what'] != b['what']:
            raise BuildError(f"US Letter and A4 paginate differently: the markers part at {a['what']} on one and "
                             f"{b['what']} on the other ({len(first)} markers against {len(second)})")
        if a['page'] != b['page']:
            raise BuildError(f"US Letter and A4 paginate differently: {a['what']} lands on page {a['page']} on "
                             f"one and page {b['page']} on the other")
    if len(first) != len(second):
        raise BuildError(f'US Letter and A4 paginate differently: {len(first)} markers against {len(second)}')


HEADING = re.compile(r'^(Chapter \S+|Appendix \S+|chapter|section|subsection) (.*)$', re.S)
FIGURE = re.compile(r'^((?:Figure|Table) \S+)')


def check_floats(marks):
    """Raise if a figure lands on the page of the heading it follows, but above it: a float placed at the top
    of the page, ahead of its own section."""
    heading = None
    for mark in marks:
        found = HEADING.match(mark['what'])
        if found:
            heading = (found.group(2), mark)
            continue
        figure = FIGURE.match(mark['what'])
        if figure and heading and heading[1]['page'] == mark['page'] and mark['y'] < heading[1]['y']:
            raise BuildError(f"{figure.group(1)} lands above its heading {heading[0]} on page {mark['page']}")


def clear_pdfs(out_dir):
    """An earlier build's PDFs, so a release's never sits beside a stale draft's."""
    for name in os.listdir(out_dir):
        if name.endswith('.pdf'):
            os.remove(os.path.join(out_dir, name))


def prepare(out_dir, facts):
    """The screens and data the book reads, written afresh, and no earlier PDF: nothing an earlier build left
    survives."""
    os.makedirs(out_dir, exist_ok=True)
    clear_pdfs(out_dir)
    for name in ('screens', 'data'):
        shutil.rmtree(os.path.join(out_dir, name), ignore_errors=True)
    screens.write_core_screens(os.path.join(out_dir, 'screens'), facts.version, facts.commit)
    screens.write_host_screens(os.path.join(out_dir, 'screens'))
    os.makedirs(os.path.join(out_dir, 'data'))
    for (name, data) in (('setup', setup_walk.walk()), ('keymaps', keys.keymaps_data())):
        with open(os.path.join(out_dir, 'data', f'{name}.json'), 'w', encoding='utf-8') as stream:
            json.dump(data, stream, indent=1, sort_keys=True)
            stream.write('\n')


def build(release=False, papers=PAPERS, out_dir=manual_paths.OUT, log=print):
    """Build the manual; returns the PDFs' paths."""
    root = manual_paths.ROOT
    out_dir = os.path.abspath(out_dir)
    if os.path.commonpath([out_dir, root]) != root:
        raise BuildError(f"{out_dir} is outside the checkout, where Typst can't read it")
    typst_run.check_version()
    facts = edition.facts(root)
    notes = []
    stamp = edition.decide(root, release, notes)
    for note in notes:
        log(note)
    prepare(out_dir, facts)
    inputs = {'version': facts.version, 'commit': facts.commit, 'date': facts.date,
              'draft': 'true' if stamp.draft else 'false', 'form': stamp.form, 'edition-name': stamp.name,
              'firmware': stamp.firmware, 'build': '/' + os.path.relpath(out_dir, root).replace(os.sep, '/')}
    pdfs = [os.path.join(out_dir, pdf_name(stamp, paper)) for paper in papers]
    # Each paper's PDF and its page markers need nothing from another, so Typst lays them all out at once. Each
    # PDF is still its own run's alone, so the bytes are as reproducible as before.
    with ThreadPoolExecutor(max_workers=2 * len(papers)) as pool:
        compiled = [pool.submit(typst_run.compile_pdf, SOURCE, pdf, {**inputs, 'paper': paper}, facts.timestamp)
                    for (paper, pdf) in zip(papers, pdfs)]
        placed = [pool.submit(typst_run.placed, SOURCE, {**inputs, 'paper': paper}) for paper in papers]
    for (pdf, run) in zip(pdfs, compiled):
        run.result()
        log(f'wrote {os.path.relpath(pdf, root)}')
    marks = [run.result() for run in placed]
    try:
        for paper_marks in marks:
            check_floats(paper_marks)
        if len(marks) == 2:
            compare_placed(*marks)
    except BuildError:
        clear_pdfs(out_dir)  # a book that paginates wrongly isn't fit to hand anyone
        raise
    if len(marks) == 2:
        log('both papers break their pages alike')
    return pdfs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--release', action='store_true', help='the declared edition, for a release')
    parser.add_argument('--paper', choices=('us-letter', 'a4', 'both'), default='both')
    parser.add_argument('--out', default=manual_paths.OUT, help='where to build, inside the checkout '
                        '(default build/manual)')
    args = parser.parse_args(argv)
    try:
        build(args.release, PAPERS if args.paper == 'both' else (args.paper,), args.out)
    except BuildError as error:
        print(f'build.py: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
