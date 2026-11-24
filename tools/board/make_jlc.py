#!/usr/bin/env python3
# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Writes JLC's order files for the board into hardware/board/jlc/ (spec, "Assembly and sourcing"):

    liz4270-revA-gerbers.zip   Gerbers and Excellon drill files for the PCB order
    liz4270-revA-bom.csv       the assembly BOM, one line per LCSC part
    liz4270-revA-cpl.csv       placements for the parts JLC fits

    make_jlc.py           write them
    make_jlc.py --check   list the order files that differ from a fresh run (the zip by its files' contents, their
                          dates aside); exit 1 if any do

Adapted from coax-tcp's interface3/pcb/jlc/make_jlc.py, the Liz 4174's (CoffeeMuse, ISC). The parts come from the
schematic's fields rather than a parts table: a part goes on the order when it is fitted, in the BOM, has an LCSC
number and isn't in HAND. Any other part that is fitted and in the BOM stops the run.
"""

import argparse
import csv
import io
import os
import re
import subprocess
import sys
import tempfile
import zipfile

import netlist
import paths

BOARD = os.path.join(paths.BOARD, 'liz4270.kicad_pcb')
SCHEMATIC = os.path.join(paths.BOARD, 'liz4270.kicad_sch')
OUT = os.path.join(paths.BOARD, 'jlc')
NAME = 'liz4270-revA'
GERBER_LAYERS = 'F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts'
# Fitted by hand on spin 1 (plan 2, CoffeeMuse, Oct 9, 2026): the 786J has had no stock at LCSC or JLC
HAND = {'T1'}
# JLC's library may hold a part at another zero orientation than KiCad's footprint: degrees counter-clockwise, added
# to KiCad's, each from JLC's placement preview and dated, never guessed.
ROTATION_FIX = {
    'U3': 270, 'U4': 270,      # SOIC-16: JLC draws it lying down, pin 1 bottom left (the Liz 4174's preview, Sept 26, 2026)
    # From this board's preview, Oct 10, 2026: what JLC drew, against the board's pin 1
    'U2': 270,                 # SOIC-8: leads down the sides, pin 1 at the right column's bottom (beside Y2)
    'U6': 270,                 # TSSOP-16: leads down the sides, pin 1 top left; the board's rows run across, pin 1 top right
    'U7': 270,                 # SOT-23-5: its three leads on the right; the board's three pads run along the bottom
    'U8': 270, 'U14': 270,     # QFN: pin 1 at the bottom-left corner; the board's is at the left side's top
    'U9': 270, 'U10': 270, 'U11': 270,  # SOT-23-6: leads down the sides, pin 1 top left; the board's rows run across
    'U12': 180,                # SOT-223: its tab over the three small pads
    'U13': 180,                # SOT-23-5: its three leads on the right, over the board's two pads
    'L1': 180,                 # the dot on pad 2 (VREG_LX); it belongs on pad 1 (+1V1)
    'Q1': 180, 'Q2': 180,      # SOT-23: its two leads over the board's one pad, pin 1 diagonally opposite
    'J4': 90,                  # HDMI: its body 12 mm along the edge and 15 deep, turned a quarter clockwise
    'SW1': 180, 'SW2': 180,    # the actuator pointing into the board, away from the edge
}
# Likewise a part whose model JLC centres elsewhere than KiCad's footprint origin: board millimetres (x right, y down)
# added to KiCad's position, each measured in JLC's placement preview and dated, never guessed.
OFFSET_FIX = {
    'J6': (0.0, -1.6),         # USB-C: its body drawn at y 74.36-81.61 against the footprint's 72.70-80.00, leads off
                               # their pads (Oct 10, 2026)
}
# The lines in a Gerber or drill file that carry the time it was written; the rest repeats from run to run, zone fills
# included (plotted with --check-zones), so a changed board shows as a changed file
DATED = re.compile(rb'^(G04 #@! TF\.CreationDate|G04 Created by KiCad|; DRILL file KiCad|; #@! TF\.CreationDate)')


def _natural(ref):
    head = ref.rstrip('0123456789')
    return (head, int(ref[len(head):] or 0))


def _cli(*args):
    result = subprocess.run([paths.KICAD_CLI, *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f'kicad-cli {" ".join(args)} failed:\n{result.stdout}{result.stderr}')


def order():
    """{ref: Part} for the parts JLC fits; stops on a fitted BOM part with no LCSC number that isn't hand-fitted."""
    parts = netlist.export(SCHEMATIC).parts
    out = {}
    for (ref, p) in parts.items():
        if p.dnp or not p.in_bom or ref in HAND:
            continue
        if not p.fields.get('LCSC'):
            raise SystemExit(f'{ref} is fitted and in the BOM but has no LCSC number')
        out[ref] = p
    return out


def gerbers(tmp):
    plots = os.path.join(tmp, 'gerbers')
    os.makedirs(plots)
    _cli('pcb', 'export', 'gerbers', '--output', plots, '--layers', GERBER_LAYERS, '--no-x2', '--no-netlist',
         '--subtract-soldermask', '--check-zones', BOARD)
    _cli('pcb', 'export', 'drill', '--output', plots, '--format', 'excellon', '--excellon-units', 'mm',
         '--excellon-zeros-format', 'decimal', '--excellon-oval-format', 'alternate', '--drill-origin', 'absolute',
         '--excellon-separate-th', BOARD)
    # only the layers and the drill files: with the job file in, JLC's uploader misread the Liz 4174's layer count
    return sorted(os.path.join(plots, n) for n in os.listdir(plots) if not n.endswith('.gbrjob'))


def placements(tmp):
    pos = os.path.join(tmp, 'pos.csv')
    _cli('pcb', 'export', 'pos', '--output', pos, '--format', 'csv', '--units', 'mm', '--side', 'front',
         '--exclude-dnp', BOARD)
    with open(pos, newline='', encoding='utf-8') as stream:
        return {row['Ref']: row for row in csv.DictReader(stream)}


def tables(fitted, pos):
    missing = sorted(set(fitted) - set(pos), key=_natural)
    if missing:
        raise SystemExit(f'parts JLC fits are missing from the placement export: {missing}')
    cpl = io.StringIO()
    w = csv.writer(cpl, lineterminator='\n')
    w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
    for ref in sorted(fitted, key=_natural):
        p = pos[ref]
        rot = (float(p['Rot']) + ROTATION_FIX.get(ref, 0)) % 360
        (x, y) = (p['PosX'], p['PosY'])
        if ref in OFFSET_FIX:
            (dx, dy) = OFFSET_FIX[ref]
            (x, y) = (f'{float(x) + dx:.6f}', f'{float(y) - dy:.6f}')     # the CPL's y runs up, the board's down
        w.writerow([ref, x, y, 'Top', f'{rot:g}'])
    groups = {}
    for (ref, part) in fitted.items():
        groups.setdefault(part.fields['LCSC'], (part, []))[1].append(ref)
    bom = io.StringIO()
    w = csv.writer(bom, lineterminator='\n')
    w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
    for (lcsc, (part, refs)) in sorted(groups.items(), key=lambda g: _natural(sorted(g[1][1], key=_natural)[0])):
        refs.sort(key=_natural)
        w.writerow([part.value, ','.join(refs), pos[refs[0]]['Package'], lcsc])
    return bom.getvalue(), cpl.getvalue()


def write(directory):
    os.makedirs(directory, exist_ok=True)
    fitted = order()
    with tempfile.TemporaryDirectory() as tmp:
        files = gerbers(tmp)
        (bom, cpl) = tables(fitted, placements(tmp))
        with zipfile.ZipFile(os.path.join(directory, f'{NAME}-gerbers.zip'), 'w', zipfile.ZIP_DEFLATED) as z:
            for f in files:
                z.write(f, os.path.basename(f))
    for (suffix, text) in (('bom', bom), ('cpl', cpl)):
        with open(os.path.join(directory, f'{NAME}-{suffix}.csv'), 'w', encoding='utf-8', newline='') as stream:
            stream.write(text)
    return [os.path.basename(f) for f in files], fitted


def _undated(data):
    return b'\n'.join(line for line in data.splitlines() if not DATED.match(line))


def stale(committed=OUT):
    with tempfile.TemporaryDirectory() as tmp:
        write(tmp)
        out = []
        for name in (f'{NAME}-bom.csv', f'{NAME}-cpl.csv'):
            with open(os.path.join(tmp, name), encoding='utf-8') as fresh:
                try:
                    with open(os.path.join(committed, name), encoding='utf-8') as old:
                        if old.read() == fresh.read():
                            continue
                except FileNotFoundError:
                    pass
            out.append(name)
        zname = f'{NAME}-gerbers.zip'
        try:
            with zipfile.ZipFile(os.path.join(tmp, zname)) as a, zipfile.ZipFile(os.path.join(committed, zname)) as b:
                if a.namelist() != b.namelist() or any(_undated(a.read(n)) != _undated(b.read(n))
                                                       for n in a.namelist()):
                    out.append(zname)
        except FileNotFoundError:
            out.append(zname)
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
    (files, fitted) = write(OUT)
    print(f'{NAME}-gerbers.zip: {len(files)} files: {" ".join(files)}')
    print(f'{NAME}-bom.csv and -cpl.csv: {len(fitted)} parts for JLC; by hand: {" ".join(sorted(HAND))}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
