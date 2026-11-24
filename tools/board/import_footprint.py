#!/usr/bin/env python3
# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Copies one placed footprint out of a KiCad board (.kicad_pcb, or a .zip holding one) into
hardware/board/lib/liz4270.pretty, unplaced and without nets. The footprint must sit unrotated on the top
side, so its pads' positions are already relative to its origin.

    import_footprint.py BOARD LIB_NAME NEW_NAME
    import_footprint.py Minimal-KiCAD.zip abracon_aota-b201610s3r3-101-t Abracon_AOTA-B201610S3R3-101-T
"""

import os
import sys
import zipfile

import paths
import sexp
from sexp import Q

DROP = ('at', 'path', 'sheetname', 'sheetfile', 'uuid', 'tstamp')


def extract(pcb_text, lib_name, new_name):
    board = sexp.parse(pcb_text)
    found = [fp for fp in sexp.find_all(board, 'footprint') if str(fp[1]).split(':')[-1].lower() == lib_name.lower()]
    if not found:
        raise ValueError(f'no footprint {lib_name} on the board')
    fp = found[0]
    at = sexp.find(fp, 'at')
    if (len(at) > 3 and float(at[3]) != 0) or str(sexp.find(fp, 'layer')[1]) != 'F.Cu':
        raise ValueError(f'{lib_name} is rotated or on the bottom; copy it by hand')
    out = ['footprint', Q(new_name), ['version', 20241229], ['generator', Q('liz4270_import_footprint')]]
    for item in fp[2:]:
        if isinstance(item, list) and item and item[0] in DROP:
            continue
        if isinstance(item, list) and item and item[0] == 'pad':
            item = [x for x in item if not (isinstance(x, list) and x and x[0] in ('net', 'uuid', 'tstamp'))]
        if isinstance(item, list) and item and item[0] == 'property' and item[1] == 'Reference':
            item = [item[0], item[1], Q('REF**')] + item[3:]
        out.append(item)
    return out


def main(argv):
    board, lib_name, new_name = argv
    if board.endswith('.zip'):
        with zipfile.ZipFile(board) as z:
            (member,) = [n for n in z.namelist() if n.endswith('.kicad_pcb')]
            text = z.read(member).decode('utf-8')
    else:
        with open(board, encoding='utf-8') as stream:
            text = stream.read()
    pretty = os.path.join(paths.LIB, 'liz4270.pretty')
    os.makedirs(pretty, exist_ok=True)
    path = os.path.join(pretty, f'{new_name}.kicad_mod')
    with open(path, 'w', encoding='utf-8', newline='\n') as stream:
        stream.write(sexp.dump(extract(text, lib_name, new_name)) + '\n')
    print(f'wrote {path}')


if __name__ == '__main__':
    main(sys.argv[1:])
