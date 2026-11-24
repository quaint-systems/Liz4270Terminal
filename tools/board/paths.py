# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Where the board's files are, and where KiCad is ($KICAD_APP, $KICAD_CLI, $KICAD_PYTHON, $FREEROUTING_JAR or
$FREECAD_CMD override the defaults)."""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
BOARD = os.path.join(ROOT, 'hardware', 'board')
LIB = os.path.join(BOARD, 'lib')
KICAD = os.environ.get('KICAD_APP', '/Applications/KiCad/KiCad.app')
KICAD_CLI = os.environ.get('KICAD_CLI', os.path.join(KICAD, 'Contents', 'MacOS', 'kicad-cli'))
STOCK_SYMBOLS = os.path.join(KICAD, 'Contents', 'SharedSupport', 'symbols')
STOCK_FOOTPRINTS = os.path.join(KICAD, 'Contents', 'SharedSupport', 'footprints')
KICAD_PYTHON = os.environ.get('KICAD_PYTHON', os.path.join(KICAD, 'Contents', 'Frameworks', 'Python.framework',
                                                           'Versions', 'Current', 'bin', 'python3'))
FREEROUTING_JAR = os.environ.get('FREEROUTING_JAR',
                                 os.path.expanduser('~/.local/share/freerouting/freerouting-2.4.1.jar'))
FREECAD_CMD = os.environ.get('FREECAD_CMD', '/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd')
