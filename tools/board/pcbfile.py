# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The board file as the tests read it, in board millimetres (pcb.ORIGIN taken off): each footprint with its pads'
centres and nets, the tracks, vias, zones and keep-outs with their fills, the outline and the texts. Nets go by
netlist.leaf's short names."""

from collections import namedtuple

import footprint
import netlist
import pcb
import sexp

Pad = namedtuple('Pad', 'number kind x y w h net')
Part = namedtuple('Part', 'ref fpid x y rot dnp pads models')
Segment = namedtuple('Segment', 'net layer width start end')
Via = namedtuple('Via', 'net x y size drill')
Zone = namedtuple('Zone', 'net name layers polygon rule filled')    # rule: a keep-out's flags, or None
Text = namedtuple('Text', 'text layer x y')


def _xy(item, key='at'):
    a = sexp.find(item, key)
    return (round(float(a[1]) - pcb.ORIGIN[0], 6), round(float(a[2]) - pcb.ORIGIN[1], 6))


def _net(item):
    n = sexp.find(item, 'net')
    return netlist.leaf(str(n[-1])) if n and len(n) > 1 else ''


def _points(item):
    return tuple((round(float(xy[1]) - pcb.ORIGIN[0], 6), round(float(xy[2]) - pcb.ORIGIN[1], 6))
                 for xy in sexp.find_all(sexp.find(item, 'pts'), 'xy'))


class Board:
    def __init__(self, path):
        with open(path, encoding='utf-8') as stream:
            expr = sexp.parse(stream.read())
        self.parts = {}
        for fp in sexp.find_all(expr, 'footprint'):
            ref = next(str(p[2]) for p in sexp.find_all(fp, 'property') if p[1] == 'Reference')
            at = sexp.find(fp, 'at')
            (x, y) = _xy(fp)
            rot = float(at[3]) if len(at) > 3 else 0.0
            attr = sexp.find(fp, 'attr') or []
            dnp = 'dnp' in attr or (sexp.find(fp, 'dnp') or [None, 'no'])[1] == 'yes'
            pads = []
            for pad in sexp.find_all(fp, 'pad'):
                pa = sexp.find(pad, 'at')
                (dx, dy) = footprint.turn(float(pa[1]), float(pa[2]), rot)
                size = sexp.find(pad, 'size')
                pads.append(Pad(str(pad[1]), str(pad[2]), round(x + dx, 6), round(y + dy, 6), float(size[1]),
                                float(size[2]), _net(pad)))
            models = [str(m[1]) for m in sexp.find_all(fp, 'model')]
            self.parts[ref] = Part(ref, str(fp[1]), x, y, rot, dnp, pads, models)
        self.segments = [Segment(_net(s), str(sexp.find(s, 'layer')[1]), float(sexp.find(s, 'width')[1]),
                                 _xy(s, 'start'), _xy(s, 'end')) for s in sexp.find_all(expr, 'segment')]
        self.vias = [Via(_net(v), *_xy(v), float(sexp.find(v, 'size')[1]), float(sexp.find(v, 'drill')[1]))
                     for v in sexp.find_all(expr, 'via')]
        self.zones = []
        for z in sexp.find_all(expr, 'zone'):
            layers = sexp.find(z, 'layers') or sexp.find(z, 'layer')
            keepout = sexp.find(z, 'keepout')
            rule = None
            if keepout:
                rule = {str(k[0]): str(k[1]) == 'not_allowed' for k in keepout[1:] if isinstance(k, list)}
            name = sexp.find(z, 'name')
            filled = {}
            for f in sexp.find_all(z, 'filled_polygon'):
                filled.setdefault(str(sexp.find(f, 'layer')[1]), []).append(_points(f))
            self.zones.append(Zone(_net(z), str(name[1]) if name else '', tuple(str(l) for l in layers[1:]),
                                   _points(sexp.find(z, 'polygon')), rule, filled))
        self.edges = []
        for kind in ('gr_line', 'gr_arc', 'gr_rect'):
            for g in sexp.find_all(expr, kind):
                if str(sexp.find(g, 'layer')[1]) == 'Edge.Cuts':
                    self.edges += [_xy(g, k) for k in ('start', 'mid', 'end') if sexp.find(g, k)]
        self.texts = [Text(str(t[1]), str(sexp.find(t, 'layer')[1]), *_xy(t)) for t in sexp.find_all(expr, 'gr_text')]

    def pad(self, ref, number):
        return next(p for p in self.parts[ref].pads if p.number == str(number))

    def outline(self):
        """The outline's box: (x0, y0, x1, y1)."""
        xs = [p[0] for p in self.edges]
        ys = [p[1] for p in self.edges]
        return (min(xs), min(ys), max(xs), max(ys))

    def copper(self, net):
        return [s for s in self.segments if s.net == net]
