#!/usr/bin/env python3
# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Writes the case's STLs into hardware/case/stl/, each part as it lies on the print bed (#134):

    base.stl         the base, on its floor
    lid.stl          the lid, upside down: alone for one colour, or with inlay.stl for two
    inlay.stl        the name and the LEDs' labels, which fill the lid's text in a second colour
    light-pipe.stl   one light pipe, standing on its collar: print two in clear filament

    make_case.py           write them
    make_case.py --check   list the ones that differ from a fresh build; exit 1 if any do

Both need the OpenSCAD the STLs are built with (paths.OPENSCAD_VERSION); another is named, and nothing is built.
"""

import argparse
import os
import sys
import tempfile

import paths
import scad

PARTS = {'base.stl': 'base', 'lid.stl': 'lid', 'inlay.stl': 'inlay', 'light-pipe.stl': 'light_pipe'}


def build(name, directory):
    out = os.path.join(directory, name)
    r = scad.run(['--hardwarnings', '-o', out, '--export-format', 'binstl', '-D', f'part="{PARTS[name]}"',
                  os.path.join(paths.CASE, 'case.scad')])
    if r.returncode != 0:
        raise RuntimeError(f'{name}: {r.stderr}')
    return out


def write(directory):
    os.makedirs(directory, exist_ok=True)
    for name in PARTS:
        build(name, directory)


def stale():
    with tempfile.TemporaryDirectory() as tmp:
        write(tmp)
        out = []
        for name in PARTS:
            try:
                with open(os.path.join(tmp, name), 'rb') as fresh, open(os.path.join(paths.STL, name), 'rb') as old:
                    if fresh.read() == old.read():
                        continue
            except FileNotFoundError:
                pass
            out.append(name)
        return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    found = scad.version()
    if found != paths.OPENSCAD_VERSION:
        print(f'OpenSCAD {found or "is missing"}: the STLs are built with {paths.OPENSCAD_VERSION} '
              '(brew install --cask openscad@snapshot, or set $OPENSCAD)')
        return 1
    if args.check:
        names = stale()
        for name in names:
            print(f'stale: {name}')
        return 1 if names else 0
    write(paths.STL)
    print(f'wrote {", ".join(PARTS)} into {paths.STL}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
