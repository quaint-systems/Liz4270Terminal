#!/usr/bin/env python3
# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Writes plain-body 3D models (STEP) for the footprints whose stock model KiCad 10.0.6 doesn't ship, into
hardware/board/lib/liz4270.3dshapes, with FreeCAD's command line (paths.FREECAD_CMD). Each is a box at the part's
body outline and height: enough for the 3D view and the case's STEP export, and ours to publish.

    make_models.py           write them
    make_models.py --check   list the models that are missing or describe another body; exit 1 if any do
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile

import paths

OUT = os.path.join(paths.LIB, 'liz4270.3dshapes')

# name -> boxes, each (x0, y0, z0, x1, y1, z1) in mm in the footprint's frame (y down, as KiCad draws it), z up
BODIES = {
    'QFN-80_10x10mm': [(-5.0, -5.0, 0.0, 5.0, 5.0, 0.85)],                    # RP2350 datasheet, QFN-80 package
    # Wuerth 61400826021 (rev 001.001), p.1: 14.5 x 17 body, 15.34 high; its front flange, 0.3 mm sheet about 11.3 mm
    # wide, stands 15.5 tall from 0.45 mm up, so 15.95 at its top (measured from the drawing's lines). Spin 1 has the
    # Wuerth and the reorder Molex's 67298-3091 (parts.py), so this is both: Molex's SD-67298-008 rev D is 14.00 wide,
    # 15.59 high and 17.30 deep to the same front, which puts its back 0.3 mm behind Wuerth's, at -1.69
    'USB_A_Wuerth_61400826021': [(-3.75, -1.69, 0.0, 10.75, 15.31, 15.34),
                                 (-2.14, 15.31, 0.45, 9.14, 15.61, 15.95)],
    'USB_C_HRO_TYPE-C-31-M-12': [(-4.47, -3.7, 0.0, 4.47, 3.65, 3.26)],        # HRO TYPE-C-31-M-12 (rev A): 8.94 x 7.35
    'Fuse_1812': [(-2.365, -1.705, 0.0, 2.365, 1.705, 0.85)],                  # Bourns MF-MSMF (rev O) p.2: 1812, max
    # Murata KMP_786JC_E01 p.3: 9.52 x 9.0 max, 6.35 high +/- 0.25
    'Murata_786J': [(-4.76, -4.5, 0.0, 4.76, 4.5, 6.6)],
    'Inductor_AOTA_2016': [(-1.0, -0.8, 0.0, 1.0, 0.8, 1.0)],                  # Abracon AOTA-B201610 p.4, max
}

SCRIPT = '''
import json, FreeCAD, Part, Import
for (name, boxes) in json.load(open({spec!r})).items():
    doc = FreeCAD.newDocument(name.replace('-', '_').replace('.', '_'))
    shape = None
    for (x0, y0, z0, x1, y1, z1) in boxes:
        box = Part.makeBox(x1 - x0, y1 - y0, z1 - z0, FreeCAD.Vector(x0, -y1, z0))
        shape = box if shape is None else shape.fuse(box)
    body = doc.addObject('Part::Feature', 'body')
    body.Shape = shape
    Import.export([body], {out!r} + '/' + name + '.step')
'''


def write(directory):
    """Every model into directory, in one FreeCAD run. y flips: a footprint's y points down, STEP's up."""
    os.makedirs(directory, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        spec = os.path.join(tmp, 'bodies.json')
        with open(spec, 'w', encoding='utf-8') as stream:
            json.dump(BODIES, stream)
        script = os.path.join(tmp, 'models.py')
        with open(script, 'w', encoding='utf-8') as stream:
            stream.write(SCRIPT.format(spec=spec, out=directory))
        result = subprocess.run([paths.FREECAD_CMD, script], capture_output=True, text=True, timeout=300)
        missing = [n for n in BODIES if not os.path.exists(os.path.join(directory, n + '.step'))]
        if result.returncode != 0 or missing:
            raise RuntimeError(f'FreeCAD wrote no {missing}:\n{result.stdout}{result.stderr}')


def body(text):
    """A STEP file from its data on: the header's FILE_NAME carries the time it was written."""
    return text[text.index('DATA;'):]


def stale():
    with tempfile.TemporaryDirectory() as tmp:
        write(tmp)
        out = []
        for name in BODIES:
            with open(os.path.join(tmp, name + '.step'), encoding='utf-8') as fresh:
                try:
                    with open(os.path.join(OUT, name + '.step'), encoding='utf-8') as old:
                        if body(old.read()) == body(fresh.read()):
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
            print(f'stale: {name}.step')
        return 1 if names else 0
    write(OUT)
    for name in BODIES:
        print(f'wrote {name}.step')
    return 0


if __name__ == '__main__':
    sys.exit(main())
