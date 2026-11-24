#!/usr/bin/env python3
# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Renders the board to PNG so a layout can be looked at: layers through kicad-cli's PDF plot and pdftoppm
(Homebrew poppler), or the 3D view through kicad-cli's renderer.

    render_board.py OUT_DIR                          the top: F.Cu, F.SilkS, F.Fab, F.CrtYd and Edge.Cuts, 300 dpi
    render_board.py OUT_DIR --layers B.Cu,Edge.Cuts  any layers
    render_board.py OUT_DIR --crop X Y W H           a crop, in board mm from the outline's corner, at 600 dpi
    render_board.py OUT_DIR --3d top|bottom|front    the 3D view; front looks at the connector edge

Prints each PNG's path, for the Read tool. The layer plots fill the zones first; the 3D view shows them unfilled
(pcb_build.py says why), which is what it's for: the parts.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

import layout
import paths
import pcb

BOARD = os.path.join(paths.BOARD, 'liz4270.kicad_pcb')
TOP = 'F.Cu,F.SilkS,F.Fab,F.CrtYd,Edge.Cuts'


def layers(out_dir, names, crop=None, dpi=None):
    if shutil.which('pdftoppm') is None:
        sys.exit('pdftoppm not found: brew install poppler')
    dpi = dpi or (600 if crop else 300)
    (x, y, w, h) = crop or (-2, -2, layout.WIDTH + 4, layout.HEIGHT + 4)
    with tempfile.TemporaryDirectory() as tmp:
        pdf = os.path.join(tmp, 'board.pdf')
        result = subprocess.run([paths.KICAD_CLI, 'pcb', 'export', 'pdf', '--mode-single', '--check-zones',
                                 '--layers', names, '-o', pdf, BOARD], capture_output=True, text=True)
        if result.returncode != 0:
            sys.exit(f'kicad-cli failed:\n{result.stdout}{result.stderr}')
        name = names.replace(',', '+').replace('.', '')
        if crop:
            name += '-crop-' + '-'.join(f'{v:g}' for v in crop)
        target = os.path.join(out_dir, name)
        (px, py, pw, ph) = (round((v / 25.4) * dpi) for v in (x + pcb.ORIGIN[0], y + pcb.ORIGIN[1], w, h))
        subprocess.run(['pdftoppm', '-r', str(dpi), '-png', '-singlefile', '-x', str(px), '-y', str(py),
                        '-W', str(pw), '-H', str(ph), pdf, target], check=True)
    return target + '.png'


def view(out_dir, side):
    """The 3D view from above or below, or from the front at 60 degrees, looking at the connector edge."""
    target = os.path.join(out_dir, f'3d-{side}.png')
    angle = ['--side', 'top', '--rotate', '-60,0,0', '--perspective'] if side == 'front' else ['--side', side]
    result = subprocess.run([paths.KICAD_CLI, 'pcb', 'render', *angle, '--quality', 'high', '--width', '1800',
                             '--height', '1400', '--background', 'opaque', '-o', target, BOARD],
                            capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f'kicad-cli failed:\n{result.stdout}{result.stderr}')
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('out_dir')
    parser.add_argument('--layers', default=TOP)
    parser.add_argument('--crop', nargs=4, type=float, metavar=('X', 'Y', 'W', 'H'))
    parser.add_argument('--dpi', type=int)
    parser.add_argument('--3d', dest='side', choices=('top', 'bottom', 'front'))
    args = parser.parse_args(argv)
    os.makedirs(args.out_dir, exist_ok=True)
    print(view(args.out_dir, args.side) if args.side else layers(args.out_dir, args.layers, args.crop, args.dpi))
    return 0


if __name__ == '__main__':
    sys.exit(main())
