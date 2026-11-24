#!/usr/bin/env python3
# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Writes what the case's spec needs from the board (spec, "For the case") into hardware/board/export/:

    liz4270-outline.dxf   the outline, in mm from the board's top-left corner (the drill origin)
    liz4270-case.json     the outline's size, the holes, each edge part's place, rotation and value, the parts
                          inside the case it reaches, and the connector labels
    liz4270-board.scad    the same numbers as OpenSCAD constants, for hardware/case/ (#134)
    liz4270.step          the assembled board in 3D, from the same corner (made here, not committed: too big)
    liz4270.stl           the same as a mesh, for the case's assembly view (not committed either)

    make_exports.py           write them
    make_exports.py --check   list the committed three that differ from a fresh run; exit 1 if any do
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile

import layout
import layout_edge
import paths
import pcbfile

BOARD = os.path.join(paths.BOARD, 'liz4270.kicad_pcb')
OUT = os.path.join(paths.BOARD, 'export')
COMMITTED = ('liz4270-outline.dxf', 'liz4270-case.json', 'liz4270-board.scad')
INSIDE = ('D1', 'D5', 'J1', 'J7')       # what the case reaches inside: the light pipes, the probe notch, the speaker


def case():
    b = pcbfile.Board(BOARD)
    holes = {ref: {'x': b.parts[ref].x, 'y': b.parts[ref].y, 'plated': ref != 'H4'} for ref in layout_edge.HOLES}
    edge = {ref: {'x': b.parts[ref].x, 'y': b.parts[ref].y, 'rot': b.parts[ref].rot,
                  'fpid': b.parts[ref].fpid} for ref in layout_edge.EDGE}
    inside = {ref: {'x': b.parts[ref].x, 'y': b.parts[ref].y} for ref in INSIDE}
    return {'outline': {'width': layout.WIDTH, 'height': layout.HEIGHT, 'corner': layout.CORNER},
            'holes': holes, 'edge': edge, 'inside': inside,
            'labels': [[text, x] for (text, x) in layout_edge.LABELS],
            'origin': 'the outline\'s top-left corner; x right, y down (towards the edge)'}


def num(v):
    """A length for OpenSCAD, rounded to 0.1 µm, never -0.0."""
    return repr(round(v, 4) + 0.0)


def scad(c):
    """c's numbers as OpenSCAD constants, in the frame of the board's STL export: y negated."""
    lines = ['// Copyright (c) 2026, CoffeeMuse', '// SPDX-License-Identifier: CERN-OHL-P-2.0', '',
             "// Written by tools/board/make_exports.py from hardware/board/liz4270.kicad_pcb: don't edit.",
             "// The frame of `kicad-cli pcb export stl --drill-origin`: x to the right and y up (the board's y",
             "// negated), in mm from the outline's top-left corner.", '',
             f'BOARD_W = {num(c["outline"]["width"])};',
             f'BOARD_H = {num(c["outline"]["height"])};',
             f'BOARD_CORNER = {num(c["outline"]["corner"])};', '']
    for (ref, h) in sorted(c['holes'].items()):
        lines.append(f'{ref} = [{num(h["x"])}, {num(-h["y"])}];')
    lines.append(f'HOLES = [{", ".join(sorted(c["holes"]))}];')
    lines.append('')
    for (ref, p) in sorted({**c['edge'], **c['inside']}.items()):
        lines.append(f'{ref} = [{num(p["x"])}, {num(-p["y"])}];')
    lines.append('')
    labels = ', '.join(f'["{text}", {num(x)}]' for (text, x) in c['labels'])
    lines.append(f'LABELS = [{labels}];')
    return '\n'.join(lines) + '\n'


def write(directory, models=True):
    os.makedirs(directory, exist_ok=True)
    subprocess.run([paths.KICAD_CLI, 'pcb', 'export', 'dxf', '--mode-single', '--layers', 'Edge.Cuts', '--ou', 'mm',
                    '--udo', '-o', os.path.join(directory, 'liz4270-outline.dxf'), BOARD],
                   check=True, capture_output=True)
    c = case()
    with open(os.path.join(directory, 'liz4270-case.json'), 'w', encoding='utf-8', newline='\n') as stream:
        json.dump(c, stream, indent=2, sort_keys=True)
        stream.write('\n')
    with open(os.path.join(directory, 'liz4270-board.scad'), 'w', encoding='utf-8', newline='\n') as stream:
        stream.write(scad(c))
    if models:
        for kind in ('step', 'stl'):
            subprocess.run([paths.KICAD_CLI, 'pcb', 'export', kind, '--drill-origin', '--subst-models', '-f',
                            '-o', os.path.join(directory, f'liz4270.{kind}'), BOARD], check=True, capture_output=True)


def stale():
    with tempfile.TemporaryDirectory() as tmp:
        write(tmp, models=False)
        out = []
        for name in COMMITTED:
            with open(os.path.join(tmp, name), encoding='utf-8') as fresh:
                try:
                    with open(os.path.join(OUT, name), encoding='utf-8') as old:
                        if old.read() == fresh.read():
                            continue
                except FileNotFoundError:
                    pass
            out.append(name)
        return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    if args.check:
        names = stale()
        for name in names:
            print(f'stale: {name}')
        return 1 if names else 0
    write(OUT)
    print(f'wrote {", ".join(COMMITTED)}, liz4270.step and liz4270.stl into {OUT}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
