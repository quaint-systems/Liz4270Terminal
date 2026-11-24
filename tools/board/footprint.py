# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Footprint geometry from the .kicad_mod files: each pad's centre and the courtyard's box in the footprint's own
frame, and turn(), which takes a point into the board's frame as KiCad turns a footprint. Python 3.9: pcb_build.py
imports it in KiCad's own interpreter."""

import math
import os
from collections import namedtuple

import paths
import sexp

Pad = namedtuple('Pad', 'number kind x y w h')               # kind: smd, thru_hole or np_thru_hole
Footprint = namedtuple('Footprint', 'fpid pads courtyard')     # courtyard: (x0, y0, x1, y1) on F.CrtYd, or None

_cache = {}


def path(fpid):
    """The .kicad_mod file of 'Lib:Name': ours from hardware/board/lib, the rest from KiCad's stock libraries."""
    (lib, name) = fpid.split(':')
    if lib == 'liz4270':
        folder = os.path.join(paths.LIB, 'liz4270.pretty')
    else:
        folder = os.path.join(paths.STOCK_FOOTPRINTS, lib + '.pretty')
    return os.path.join(folder, name + '.kicad_mod')


def turn(x, y, rot):
    """(x, y) turned rot degrees as KiCad turns a footprint: counter-clockwise on the screen, where y points down."""
    r = math.radians(rot)
    (c, s) = (math.cos(r), math.sin(r))
    return (round(x * c + y * s, 6) + 0.0, round(-x * s + y * c, 6) + 0.0)


def _corners(item):
    """The points that bound one graphic item: a circle by its centre and radius, the rest by their points."""
    if item[0] == 'fp_circle':
        (c, e) = (sexp.find(item, 'center'), sexp.find(item, 'end'))
        (cx, cy) = (float(c[1]), float(c[2]))
        r = math.hypot(float(e[1]) - cx, float(e[2]) - cy)
        return [(cx - r, cy - r), (cx + r, cy + r)]
    out = []
    for key in ('start', 'end', 'mid'):
        p = sexp.find(item, key)
        if p:
            out.append((float(p[1]), float(p[2])))
    pts = sexp.find(item, 'pts')
    if pts:
        out += [(float(xy[1]), float(xy[2])) for xy in sexp.find_all(pts, 'xy')]
    return out


def load(fpid):
    if fpid not in _cache:
        with open(path(fpid), encoding='utf-8') as stream:
            expr = sexp.parse(stream.read())
        pads = []
        for item in sexp.find_all(expr, 'pad'):
            (at, size) = (sexp.find(item, 'at'), sexp.find(item, 'size'))
            pads.append(Pad(str(item[1]), str(item[2]), float(at[1]), float(at[2]), float(size[1]), float(size[2])))
        corners = []
        for item in expr[1:]:
            if isinstance(item, list) and item and str(item[0]).startswith('fp_'):
                layer = sexp.find(item, 'layer')
                if layer and layer[1] == 'F.CrtYd':
                    corners += _corners(item)
        courtyard = None
        if corners:
            courtyard = (min(p[0] for p in corners), min(p[1] for p in corners),
                         max(p[0] for p in corners), max(p[1] for p in corners))
        _cache[fpid] = Footprint(fpid, pads, courtyard)
    return _cache[fpid]


def pad(fpid, number):
    """The first pad of fpid called number."""
    for p in load(fpid).pads:
        if p.number == str(number):
            return p
    raise KeyError(f'{fpid} has no pad {number}')
