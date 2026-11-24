# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The planes and pours (spec, "Ground is one solid plane"). In1 is GND everywhere but the coax line side and the
cut-out under VREG_LX, which keep-outs carve from it; In2 is +3V3 everywhere but the line side. A through-hole pin
meets them by thermal spokes, as it meets the pours, so that a pin on a plane solders (gate-3 review, finding 2);
vias join them solid, as do the exposed pads' thermal vias (board_setup.DRU) and the plated mounting holes (their
footprints). F.Cu and B.Cu carry ground pours, added after Freerouting has routed (pcb.Layout.pour). Every +3V3 and
GND surface-mount pad reaches its plane by a via of its own (pcb.Layout.fanout): Freerouting doesn't drop vias to
planes, and a pad on its own via decouples better than one routed to its neighbour. Ground vias stitch the pours to
In1: a ring along the outline, a row outside the isolation band, and a grid, each via only where pcb.Layout.stitch
finds room."""

import fnmatch

import board_setup
import layout_coax
import pcb

RING = 5.0             # mm between the ring's vias
PAIRS = [p for c in board_setup.CLASSES if c[0] in ('TMDS', 'USB') for p in c[7]]
INSET = 1.6            # mm in from the outline
GRID = 8.0             # mm between the grid's vias


def route(L):
    whole = pcb.rect(0.0, 0.0, L.width, L.height)
    L.zone('GND', 'In1.Cu', whole)
    L.zone('+3V3', 'In2.Cu', whole)
    for layer in ('F.Cu', 'B.Cu'):
        L.pour('GND', layer, whole)
    for net in ('+3V3', 'GND'):
        L.fanout(net, hole=hole)
    (w, h) = (L.width, L.height)
    ring = [(x, INSET) for x in _steps(INSET, w - INSET, RING)] + [(x, h - INSET) for x in _steps(INSET, w - INSET, RING)]
    ring += [(INSET, y) for y in _steps(INSET, h - INSET, RING)] + [(w - INSET, y) for y in _steps(INSET, h - INSET, RING)]
    (top, right) = (layout_coax.BAND_POLYGON[0][1] - 1.0, layout_coax.BAND_POLYGON[1][0] + 1.0)
    band = [(x, top) for x in _steps(1.0, right, 2.5)] + [(right, y) for y in _steps(top, h - INSET, 2.5)]
    grid = [(x, y) for x in _steps(GRID, w - GRID, GRID) for y in _steps(GRID, h - GRID, GRID)]
    L.stitch('GND', ring + band + grid)


def hole(net):
    """What a fan-out via keeps from net's copper: from a pair, enough that its hole in the plane stays out from under
    the pair's lines (its track keeps the classes' 0.2 mm)."""
    if net and any(fnmatch.fnmatchcase(net, p) for p in PAIRS):
        return 0.45
    return 0.2


def _steps(a, b, step):
    out = []
    while a <= b + 1e-9:
        out.append(round(a, 3))
        a += step
    return out
