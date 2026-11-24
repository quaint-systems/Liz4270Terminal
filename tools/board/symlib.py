# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Symbols from KiCad symbol libraries: their pins, and their definitions flattened for a schematic.

A library has y up and a schematic has y down. A symbol placed at rotation rot
(0, 90, 180 or 270, counter-clockwise as drawn) puts library offset (x, y) at
sheet_xy(x, y, rot) from its origin: rotated, then y negated. kicad-cli
confirmed it on Oct 8, 2026: Device:R at rotation 90 has pin 1 on the left.
A mirrored symbol (KiCad's mirror y) is then flipped left to right on the sheet.
"""

import copy
import os
from dataclasses import dataclass

import paths
import sexp
from sexp import Q

_ROTATE = {0: lambda x, y: (x, y), 90: lambda x, y: (-y, x), 180: lambda x, y: (-x, -y), 270: lambda x, y: (y, -x)}
_UNIT = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}  # library angle -> library unit vector


def sheet_xy(x, y, rot, mirror=False):
    """Library offset (x, y) as a sheet offset, for a symbol at rotation rot, mirrored or not."""
    rx, ry = _ROTATE[rot](x, y)
    return ((-rx if mirror else rx) + 0.0, -ry + 0.0)  # + 0.0 turns -0.0 into 0.0


@dataclass(frozen=True)
class Pin:
    number: str
    name: str
    etype: str
    x: float
    y: float
    angle: int      # library direction from the pin's free end into the body
    unit: int       # 0: the pin is in every unit

    def end(self, at, rot, mirror=False):
        """The pin's free end on the sheet, for a symbol at at with rotation rot, mirrored or not."""
        dx, dy = sheet_xy(self.x, self.y, rot, mirror)
        return (round(at[0] + dx, 4), round(at[1] + dy, 4))

    def outward(self, rot, mirror=False):
        """The sheet direction away from the body, as (dx, dy) with one of them 0."""
        return sheet_xy(*_UNIT[(self.angle + 180) % 360], rot, mirror)


class Symbol:
    """One library symbol, flattened: expr is ready to embed in a schematic's lib_symbols, named lib_id."""

    def __init__(self, lib_id, expr):
        self.lib_id = lib_id
        self.expr = expr
        self.pins = _pins(expr)
        self.units = sorted({p.unit for p in self.pins if p.unit}) or [1]
        self.bbox = _bbox(expr)

    def unit_pins(self, unit):
        return [p for p in self.pins if p.unit in (0, unit)]

    def box(self, rot, mirror=False):
        """The body and pins' box around the origin, on the sheet at rotation rot, mirrored or not: (x0, y0, x1, y1)."""
        corners = [sheet_xy(x, y, rot, mirror) for x in (self.bbox[0], self.bbox[2]) for y in (self.bbox[1], self.bbox[3])]
        return (min(c[0] for c in corners), min(c[1] for c in corners),
                max(c[0] for c in corners), max(c[1] for c in corners))

    def property(self, key):
        return next((str(p[2]) for p in sexp.find_all(self.expr, 'property') if p[1] == key), '')


def _pins(expr):
    pins = []
    for sub in sexp.find_all(expr, 'symbol'):
        _, unit, style = str(sub[1]).rsplit('_', 2)
        if int(style) > 1:            # De Morgan alternates repeat the same pins
            continue
        for pin in sexp.find_all(sub, 'pin'):
            at = sexp.find(pin, 'at')
            pins.append(Pin(number=str(sexp.find(pin, 'number')[1]), name=str(sexp.find(pin, 'name')[1]),
                            etype=str(pin[1]), x=float(at[1]), y=float(at[2]),
                            angle=int(float(at[3])) % 360, unit=int(unit)))
    return pins


def _bbox(expr):
    """(xmin, ymin, xmax, ymax) of the drawing and the pins, in library coordinates."""
    xs, ys = [0.0], [0.0]

    def visit(node):
        if not isinstance(node, list) or not node or node[0] == 'property':
            return
        if node[0] == 'pin':
            at = sexp.find(node, 'at')
            ux, uy = _UNIT[int(float(at[3])) % 360]
            length = float(sexp.find(node, 'length')[1])
            for t in (0.0, length):
                xs.append(float(at[1]) + ux * t)
                ys.append(float(at[2]) + uy * t)
            return
        if node[0] == 'circle':           # its points are the centre; the radius is the reach
            center, radius = sexp.find(node, 'center'), float(sexp.find(node, 'radius')[1])
            for s in (-1, 1):
                xs.append(float(center[1]) + s * radius)
                ys.append(float(center[2]) + s * radius)
            return
        if node[0] in ('start', 'end', 'mid', 'center', 'xy') and len(node) == 3:
            xs.append(float(node[1]))
            ys.append(float(node[2]))
        for child in node[1:]:
            visit(child)

    visit(expr)
    return (min(xs), min(ys), max(xs), max(ys))


class Library:
    """A .kicad_sym file; nickname is its name in lib_ids."""

    _parsed = {}

    def __init__(self, nickname, path):
        self.nickname = nickname
        self.path = path
        if path not in Library._parsed:
            with open(path, encoding='utf-8') as stream:
                Library._parsed[path] = sexp.parse(stream.read())
        self.expr = Library._parsed[path]

    def names(self):
        return [str(item[1]) for item in sexp.find_all(self.expr, 'symbol')]

    def symbol(self, name):
        flat = self._flat(name)
        flat[1] = Q(f'{self.nickname}:{name}')
        return Symbol(f'{self.nickname}:{name}', flat)

    def _raw(self, name):
        for item in sexp.find_all(self.expr, 'symbol'):
            if item[1] == name:
                return item
        raise KeyError(f'{name} is not in {self.path}')

    def _flat(self, name):
        """name's definition with any (extends PARENT) resolved: the parent's drawing, name's properties."""
        own = copy.deepcopy(self._raw(name))
        extends = sexp.find(own, 'extends')
        if extends is None:
            return own
        parent = self._flat(str(extends[1]))
        props = {str(p[1]): p for p in sexp.find_all(own, 'property')}
        flat = [own[0], Q(name)]
        for item in parent[2:]:
            if isinstance(item, list) and item[0] == 'property' and str(item[1]) in props:
                flat.append(props.pop(str(item[1])))
            elif isinstance(item, list) and item[0] == 'symbol':
                flat.append([item[0], Q(name + str(item[1])[len(str(parent[1])):])] + item[2:])
            else:
                flat.append(item)
        first = next(i for (i, x) in enumerate(flat) if isinstance(x, list) and x[0] == 'symbol')
        flat[first:first] = list(props.values())
        return flat


def lookup(lib_id):
    """The symbol for lib_id: liz4270:* from the board's own library, anything else from KiCad's."""
    nickname, name = lib_id.split(':', 1)
    if nickname == 'liz4270':
        path = os.path.join(paths.LIB, 'liz4270.kicad_sym')
    else:
        path = os.path.join(paths.STOCK_SYMBOLS, f'{nickname}.kicad_sym')
    return Library(nickname, path).symbol(name)
