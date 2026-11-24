#!/usr/bin/env python3
# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Writes hardware/board/lib/liz4270.kicad_sym: the symbols KiCad doesn't ship.

TLV320DAC3100 and TPD13S523 are drawn here from their datasheets' pin tables
(TI SLAS671C and SLVSBC5D, "Pin Functions"). Murata_78602 is interface3's
symbol (quaint-systems/coax-tcp, interface3/pcb, ISC, Hans Hübner), imported
once with --import-78602 and kept as it is.

    make_library.py                                write the two TI symbols, keeping the others
    make_library.py --import-78602 SCHEMATIC       also copy Murata_78602 out of interface3's pcb.kicad_sch
    make_library.py --check                        list the generated symbols that differ; exit 1 if any do
"""

import argparse
import os
import sys

import paths
import sexp
from sexp import Q

LIB_FILE = os.path.join(paths.LIB, 'liz4270.kicad_sym')
TI = 'https://www.ti.com/lit/ds/symlink/'

# (number, name, electrical type), top to bottom; None leaves a gap. SPKP and SPKM are passive: each is two
# pins of one output, and ERC would call two outputs on one net a conflict.
TLV320DAC3100 = dict(
    footprint='Package_DFN_QFN:QFN-32-1EP_5x5mm_P0.5mm_EP3.45x3.45mm_ThermalVias',
    datasheet=TI + 'tlv320dac3100.pdf',
    description='Mono audio DAC with class-D speaker driver and beep generator, I2C control, VQFN-32 (RHB)',
    left=[('31', '~{RESET}', 'input'), ('9', 'SDA', 'bidirectional'), ('10', 'SCL', 'input'), None,
          ('8', 'MCLK', 'input'), ('7', 'BCLK', 'bidirectional'), ('6', 'WCLK', 'bidirectional'),
          ('5', 'DIN', 'input'), ('32', 'GPIO1', 'bidirectional'), None,
          ('13', 'AIN1', 'input'), ('14', 'AIN2', 'input'), ('11', 'VOL/MICDET', 'input'), ('12', 'MICBIAS', 'output'),
          None, ('4', 'NC', 'no_connect'), ('15', 'NC', 'no_connect')],
    right=[('2', 'IOVDD', 'power_in'), ('3', 'DVDD', 'power_in'), ('17', 'AVDD', 'power_in'),
           ('28', 'HPVDD', 'power_in'), ('21', 'SPKVDD', 'power_in'), ('24', 'SPKVDD', 'power_in'), None,
           ('22', 'SPKP', 'passive'), ('26', 'SPKP', 'passive'), ('19', 'SPKM', 'passive'), ('23', 'SPKM', 'passive'),
           ('27', 'HPL', 'output'), ('30', 'HPR', 'output'), None,
           ('1', 'IOVSS', 'power_in'), ('18', 'DVSS', 'power_in'), ('16', 'AVSS', 'power_in'),
           ('29', 'HPVSS', 'power_in'), ('20', 'SPKVSS', 'power_in'), ('25', 'SPKVSS', 'power_in'),
           ('33', 'EP', 'power_in')])

TPD13S523 = dict(
    footprint='Package_SO:TSSOP-16_4.4x5mm_P0.65mm', datasheet=TI + 'tpd13s523.pdf',
    description='HDMI transmitter port protection: 13 ESD clamps and a current-limited 5 V load switch, TSSOP-16',
    left=[('16', 'D0+', 'passive'), ('15', 'D0-', 'passive'), ('14', 'D1+', 'passive'), ('13', 'D1-', 'passive'),
          ('12', 'D2+', 'passive'), ('11', 'D2-', 'passive'), ('10', 'D3+', 'passive'), ('9', 'D3-', 'passive')],
    right=[('5', '5V_SUPPLY', 'power_in'), ('6', '5V_OUT', 'power_out'), None,
           ('1', 'CTRL1', 'passive'), ('2', 'CTRL2', 'passive'), ('3', 'CTRL3', 'passive'), ('4', 'CTRL4', 'passive'),
           ('7', 'CTRL5', 'passive'), None, ('8', 'GND', 'power_in')])

GENERATED = {'TLV320DAC3100': TLV320DAC3100, 'TPD13S523': TPD13S523}


def _font():
    return ['effects', ['font', ['size', 1.27, 1.27]]]


def _prop(key, value, x, y, hidden=False):
    effects = _font() + ([['hide', 'yes']] if hidden else [])
    return ['property', Q(key), Q(value), ['at', x, y, 0], effects]


def box_symbol(name, footprint, datasheet, description, left, right, ref='U', half_width=12.7):
    """A rectangle with pins down its left and right sides, 2.54 mm apart, on the grid."""
    rows = max(len(left), len(right))
    top = round(((rows - 1) // 2) * 2.54, 4)
    pins = []
    for (column, x, angle) in ((left, -half_width - 2.54, 0), (right, half_width + 2.54, 180)):
        for (i, row) in enumerate(column):
            if row is not None:
                (number, pname, etype) = row
                pins.append(['pin', etype, 'line', ['at', x, round(top - i * 2.54, 4), angle], ['length', 2.54],
                             ['name', Q(pname), _font()], ['number', Q(number), _font()]])
    bottom = round(top - (rows - 1) * 2.54, 4)
    body = ['rectangle', ['start', -half_width, top + 2.54], ['end', half_width, bottom - 2.54],
            ['stroke', ['width', 0.254], ['type', 'default']], ['fill', ['type', 'background']]]
    return ['symbol', Q(name), ['pin_names', ['offset', 1.016]], ['exclude_from_sim', 'no'], ['in_bom', 'yes'],
            ['on_board', 'yes'],
            _prop('Reference', ref, 0, top + 5.08), _prop('Value', name, 0, bottom - 5.08),
            _prop('Footprint', footprint, 0, bottom - 7.62, True), _prop('Datasheet', datasheet, 0, bottom - 10.16, True),
            _prop('Description', description, 0, bottom - 12.7, True),
            ['symbol', Q(f'{name}_0_1'), body], ['symbol', Q(f'{name}_1_1')] + pins]


def generated():
    return {name: box_symbol(name, **spec) for (name, spec) in GENERATED.items()}


def _read():
    if not os.path.exists(LIB_FILE):
        return {}
    with open(LIB_FILE, encoding='utf-8') as stream:
        lib = sexp.parse(stream.read())
    return {str(s[1]): s for s in sexp.find_all(lib, 'symbol')}


def import_78602(schematic):
    """interface3's Murata_78602 symbol from its pcb.kicad_sch, named for this library."""
    with open(schematic, encoding='utf-8') as stream:
        sch = sexp.parse(stream.read())
    (symbol,) = [s for s in sexp.find_all(sexp.find(sch, 'lib_symbols'), 'symbol') if s[1] == 'library:Murata_78602']
    symbol[1] = Q('Murata_78602')
    for prop in sexp.find_all(symbol, 'property'):
        if prop[1] == 'Footprint':
            prop[2] = Q('liz4270:Murata_786J')
    return symbol


def write(extra=()):
    symbols = _read()
    symbols.update(generated())
    for symbol in extra:
        symbols[str(symbol[1])] = symbol
    lib = ['kicad_symbol_lib', ['version', 20241209], ['generator', Q('liz4270_make_library')],
           ['generator_version', Q('1.0')]] + [symbols[k] for k in sorted(symbols)]
    os.makedirs(os.path.dirname(LIB_FILE), exist_ok=True)
    with open(LIB_FILE, 'w', encoding='utf-8', newline='\n') as stream:
        stream.write(sexp.dump(lib) + '\n')


def stale():
    have = _read()
    return [name for (name, symbol) in generated().items()
            if name not in have or sexp.dump(have[name]) != sexp.dump(sexp.parse(sexp.dump(symbol)))]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--import-78602', metavar='SCHEMATIC')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    if args.check:
        names = stale()
        for name in names:
            print(f'stale: {name}')
        return 1 if names else 0
    write([import_78602(args.import_78602)] if args.import_78602 else [])
    print(f'wrote {LIB_FILE}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
