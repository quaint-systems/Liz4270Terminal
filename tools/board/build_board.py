#!/usr/bin/env python3
# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Writes the board, hardware/board/liz4270.kicad_pcb, with its project and DRC rule files, from the schematic's
netlist and tools/board/layout.py. KiCad's own Python does the writing (pcb_build.py).

    build_board.py           write it
    build_board.py --check   build it in a scratch directory and list the files that differ; exit 1 if any do

Freerouting's session, hardware/board/liz4270.ses, comes in only while liz4270.route.json's fingerprint still
matches the layout; when it doesn't, the board is built unrouted and this says so (run autoroute.py).
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile

import board_setup
import footprint
import layout
import netlist
import paths
import pcb

FILES = ('liz4270.kicad_pcb', 'liz4270.kicad_pro', 'liz4270.kicad_dru')
SESSION = os.path.join(paths.BOARD, 'liz4270.ses')
ROUTE = os.path.join(paths.BOARD, 'liz4270.route.json')
HERE = os.path.dirname(os.path.abspath(__file__))


def fingerprint(xml):
    """A hash of everything Freerouting's session rests on: the layout (pcb.fingerprint), and what goes into the
    DSN beside it, the net classes, the DRC rules, each part's footprint and that footprint's file."""
    (comps, nets) = netlist.board_netlist(xml)
    pins = {node: netlist.leaf(name) for (name, nodes) in nets.items() for node in nodes}
    parts = {c['ref']: c['fpid'] for c in comps}
    feet = {}
    for fpid in sorted(set(parts.values())):
        with open(footprint.path(fpid), 'rb') as stream:
            feet[fpid] = hashlib.sha256(stream.read()).hexdigest()
    data = {'layout': pcb.fingerprint(layout.layout(parts, pins), nets), 'parts': parts, 'footprints': feet,
            'classes': board_setup.CLASSES, 'default': board_setup.DEFAULT, 'rules': board_setup.RULES,
            'dru': board_setup.DRU}
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode('utf-8')).hexdigest()


def current_session(print_=print):
    """The session file, if it was made from this layout; else None, with a note why."""
    if not os.path.exists(SESSION):
        return None
    with open(ROUTE, encoding='utf-8') as stream:
        route = json.load(stream)
    with tempfile.TemporaryDirectory() as tmp:
        xml = os.path.join(tmp, 'liz4270.xml')
        netlist.export_xml(os.path.join(paths.BOARD, 'liz4270.kicad_sch'), xml)
        if fingerprint(xml) == route['fingerprint']:
            return SESSION
    print_('the Freerouting session is stale (the layout, netlist, rules or a footprint changed): built unrouted; '
           'run autoroute.py')
    return None


def build(directory, session=None, pours=True):
    """Writes FILES into directory: with session, Freerouting's routes; without pours, no outer-layer pours (for
    autoroute.py's DSN)."""
    os.makedirs(directory, exist_ok=True)
    xml = os.path.join(directory, 'liz4270.xml')
    netlist.export_xml(os.path.join(paths.BOARD, 'liz4270.kicad_sch'), xml)
    for (name, text) in (('liz4270.kicad_pcb', board_setup.HEADER), ('liz4270.kicad_pro', board_setup.project_text()),
                         ('liz4270.kicad_dru', board_setup.DRU)):
        with open(os.path.join(directory, name), 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(text)
    args = [paths.KICAD_PYTHON, os.path.join(HERE, 'pcb_build.py'), directory, xml]
    args += (['--session', session] if session else []) + ([] if pours else ['--no-pours'])
    result = subprocess.run(args, capture_output=True, text=True, cwd=HERE)
    os.remove(xml)
    errors = '\n'.join(line for line in result.stderr.splitlines() if 'create wxApp' not in line)
    if result.returncode != 0:
        raise RuntimeError(f'pcb_build.py failed:\n{result.stdout}{errors}')
    return result.stdout


def stale():
    """The board's files that differ from a fresh build."""
    with tempfile.TemporaryDirectory() as tmp:
        build(tmp, current_session(print_=lambda _: None))
        out = []
        for name in FILES:
            with open(os.path.join(tmp, name), encoding='utf-8') as fresh:
                try:
                    with open(os.path.join(paths.BOARD, name), encoding='utf-8') as old:
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
    print(build(paths.BOARD, current_session()), end='')
    for name in FILES:
        print(f'wrote {name}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
