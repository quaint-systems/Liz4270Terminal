# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The RP2350B's core regulator as Raspberry Pi's minimal design lays it out (RPI-RP2350A-MINIMAL_R4-S1, MIT;
RP2350 datasheet 6.3.8: "follow this layout as closely as possible"), moved onto our U1.

Every coordinate is in the chip's own frame, relative to the centre of its VREG_LX pad: x runs along the VREG side
the way its pin numbers fall (VREG_AVDD at +0.8, VREG_FB at -0.8), and y is negative away from the chip. The
RP2350A and RP2350B share that side's order and 0.4 mm pitch, so the minimal design's offsets carry over as they
are; to_board() turns them by U1's rotation. The console USB's 27 R sit beside the inductor, as the minimal
design's R7 and R8 do, spread for 0603 (theirs are 0402).
"""

import footprint

# ref -> (dx, dy, rotation in the chip's frame); the minimal design's reference in the comment
PARTS = {
    'L1': (0.0, -3.75, 0),        # L1, 3.3 uH: pad 1 (+1V1) at -0.7, pad 2 (VREG_LX) at +0.7
    'C1': (0.0, -1.16, 0),        # C6, CIN: pad 1 (+3V3) toward VREG_VIN
    'C2': (0.0, -2.10, 0),        # C7, COUT: pad 1 (+1V1)
    'C4': (2.2, -1.6, 270),       # C9, VREG_AVDD's 4.7 uF: pad 1 (VREG_AVDD) outwards
    'R1': (2.2, -3.45, 270),      # R3, 33 R: pad 1 (+3V3) outwards
    'R5': (-3.85, -4.3, 90),      # R7, 27 R on USB D+: pad 1 (the chip's side) toward the chip
    'R6': (-2.1, -4.3, 90),       # R8, 27 R on USB D-; 0.27 mm from L1's courtyard
}

# The minimal design's top-layer copper: (net, priority, outline)
ZONES = [
    ('VREG_LX', 5, [(-0.1, 0.3), (-0.1, -0.5), (-0.15, -0.55), (-0.15, -2.7), (0.35, -3.2), (0.35, -4.6),
                    (1.05, -4.6), (1.05, -2.9), (0.75, -2.6), (0.3, -2.6), (0.15, -2.45), (0.15, -0.55),
                    (0.1, -0.5), (0.1, 0.3)]),
    ('+1V1', 6, [(-0.35, -1.85), (-0.35, -3.225), (-0.35, -4.6), (-1.05, -4.6), (-1.05, -2.75), (-0.75, -2.45),
                 (-0.75, -2.3), (-0.95, -2.3), (-1.3, -2.65), (-1.5, -2.65), (-1.8, -2.35), (-1.8, -1.75),
                 (-1.5, -1.45), (-1.0, -1.45), (-1.0, -1.65), (-0.45, -1.65), (-0.45, -1.85)]),
    ('GND', 4, [(0.3, 0.3), (0.3, -1.4), (0.45, -1.4), (0.45, -1.85), (0.3, -1.85), (0.3, -2.35), (1.1, -2.35),
                (1.4, -2.05), (1.4, -1.3), (0.5, -0.4), (0.5, 0.3)]),
    ('+3V3', 7, [(-0.5, 0.75), (-0.5, -0.6), (-0.75, -0.85), (-0.75, -1.4), (-0.3, -1.4), (-0.3, 0.75)]),
]
# (net, width, points): VREG_FB fed from COUT's output, VREG_AVDD's RC filter, and CFILT's own ground
TRACKS = [
    ('+1V1', 0.15, [(-0.8, 0.0), (-0.825, -0.013), (-0.825, -0.675), (-1.075, -0.925), (-1.075, -1.675)]),
    ('VREG_AVDD', 0.15, [(0.8, 0.0), (0.8, -0.15), (1.64, -0.99), (1.64, -1.52), (2.2, -2.08), (2.2, -2.94)]),
    ('GND', 0.4, [(2.2, -1.12), (2.2, -0.75), (1.85, -0.4)]),
]
# (net, x, y): the high-current ground's two adjacent vias, CFILT's own (6.3.8.1), and +1V1 down to the DVDD pins
VIAS = [('GND', 1.1, -1.45), ('GND', 1.1, -2.05), ('GND', 1.85, -0.4), ('+1V1', -1.5, -1.75), ('+1V1', -1.5, -2.35)]
# No copper on In1 under VREG_LX (6.3.8.1, Figure 27), nor on top between L1's pads
CUT_IN1 = [(-0.4, 0.55), (1.3, 0.55), (1.3, -4.85), (-0.4, -4.85)]
CUT_TOP = [(-0.3, -2.8), (0.3, -2.8), (0.3, -4.7), (-0.3, -4.7)]


def to_board(L):
    """A function from the chip's frame to the board, and U1's rotation."""
    (lx, ly) = L.pad('U1', '63')                                       # VREG_LX
    rot = L.places['U1'][2]

    def f(p):
        (dx, dy) = footprint.turn(p[0], p[1], rot)
        return (round(lx + dx, 4), round(ly + dy, 4))
    return (f, rot)


def place(L):
    (f, rot) = to_board(L)
    for (ref, (dx, dy, r)) in PARTS.items():
        (x, y) = f((dx, dy))
        L.place(ref, x, y, r + rot)


def route(L):
    (f, _) = to_board(L)
    for (net, priority, outline) in ZONES:
        L.zone(net, 'F.Cu', [f(p) for p in outline], priority=priority, clearance=0.15, min_width=0.15,
               connect='solid')
    for (net, width, points) in TRACKS:
        L.track(net, 'F.Cu', width, *[f(p) for p in points])
    for (net, x, y) in VIAS:
        L.via(net, f((x, y)), size=0.6, drill=0.25)
    L.keepout('VREG_LX cut-out', ['In1.Cu'], [f(p) for p in CUT_IN1])
    L.keepout('Under L1', ['F.Cu'], [f(p) for p in CUT_TOP])
