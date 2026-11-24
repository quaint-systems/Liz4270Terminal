#!/usr/bin/env python3
# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Writes the board's schematic, hardware/board/liz4270.kicad_sch and its sheets, from tools/board/sheet_*.py.

    build_schematic.py           write it
    build_schematic.py --check   list the files that differ from what would be written; exit 1 if any do
"""

import argparse
import sys

import board


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    project = board.project()
    if args.check:
        stale = project.stale()
        for name in stale:
            print(f'stale: {name}')
        return 1 if stale else 0
    for name in project.write():
        print(f'wrote {name}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
