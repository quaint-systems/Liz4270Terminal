# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Where the case's files are, and where OpenSCAD and KiCad are ($OPENSCAD, $KICAD_APP or $KICAD_CLI override
the defaults)."""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
CASE = os.path.join(ROOT, 'hardware', 'case')
STL = os.path.join(CASE, 'stl')
BOARD_PCB = os.path.join(ROOT, 'hardware', 'board', 'liz4270.kicad_pcb')
OPENSCAD = os.environ.get('OPENSCAD', '/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD')
OPENSCAD_VERSION = '2026.10.11'         # the snapshot the committed STLs are built with (hardware/case/README.md)
KICAD = os.environ.get('KICAD_APP', '/Applications/KiCad/KiCad.app')
KICAD_CLI = os.environ.get('KICAD_CLI', os.path.join(KICAD, 'Contents', 'MacOS', 'kicad-cli'))
