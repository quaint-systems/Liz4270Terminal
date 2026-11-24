#!/usr/bin/env python3
# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Routes, with Freerouting, what layout.py leaves unrouted, and keeps Freerouting's session beside the board.

    autoroute.py [--passes N]

It builds the board unrouted and without its outer pours in a scratch directory, exports a Specctra DSN there with
KiCad's Python, runs Freerouting without its GUI (paths.FREEROUTING_JAR; Java 21 or later), and writes
hardware/board/liz4270.ses with liz4270.route.json: the layout's fingerprint, Freerouting's version and the passes.
Then run build_board.py, which takes the session in while the fingerprint still matches.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

import build_board
import netlist
import paths

VERSION = '2.4.1'
EXPORT = ('import pcbnew, sys\n'
          'board = pcbnew.LoadBoard(sys.argv[1])\n'
          'sys.exit(0 if pcbnew.ExportSpecctraDSN(board, sys.argv[2]) else 1)\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--passes', type=int, default=100)
    args = parser.parse_args(argv)
    if not os.path.exists(paths.FREEROUTING_JAR):
        sys.exit(f'no Freerouting at {paths.FREEROUTING_JAR}: plan 2, Task 14, step 1')
    with tempfile.TemporaryDirectory() as tmp:
        build_board.build(tmp, pours=False)
        xml = os.path.join(tmp, 'liz4270.xml')
        netlist.export_xml(os.path.join(paths.BOARD, 'liz4270.kicad_sch'), xml)
        fingerprint = build_board.fingerprint(xml)
        (dsn, ses) = (os.path.join(tmp, 'liz4270.dsn'), os.path.join(tmp, 'liz4270.ses'))
        result = subprocess.run([paths.KICAD_PYTHON, '-c', EXPORT, os.path.join(tmp, 'liz4270.kicad_pcb'), dsn],
                                capture_output=True, text=True)
        if result.returncode != 0:
            sys.exit(f'the DSN export failed:\n{result.stdout}{result.stderr}')
        # fan-out takes SMD pins to the In1 and In2 planes by vias; without it Freerouting routes +3V3 and GND pin
        # to pin on the outer layers and never reaches the planes
        result = subprocess.run(['java', '-jar', paths.FREEROUTING_JAR, '-de', dsn, '-do', ses,
                                 '-mp', str(args.passes), '-mt', '1', '-da', '--gui.enabled=false',
                                 '--router.fanout.enabled=true',
                                 '--user_data_path=' + os.path.join(tmp, 'freerouting')],
                                capture_output=True, text=True, timeout=3600)
        if result.returncode != 0 or not os.path.exists(ses):
            sys.exit(f'Freerouting failed:\n{result.stdout[-4000:]}{result.stderr[-4000:]}')
        print('\n'.join((result.stdout + result.stderr).splitlines()[-15:]))
        shutil.copy(ses, build_board.SESSION)
    with open(build_board.ROUTE, 'w', encoding='utf-8', newline='\n') as stream:
        json.dump({'fingerprint': fingerprint, 'freerouting': VERSION, 'passes': args.passes}, stream, indent=2,
                  sort_keys=True)
        stream.write('\n')
    print(f'wrote {build_board.SESSION} and {build_board.ROUTE}: now run build_board.py')
    return 0


if __name__ == '__main__':
    sys.exit(main())
