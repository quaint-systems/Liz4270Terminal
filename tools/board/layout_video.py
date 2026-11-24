# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Video (spec, "Video"): HSTX through 220 R to the HDMI connector, the TPD13S523 at the connector with every line
running straight over its clamp, the DDC level shifter and hot-plug. The TMDS pairs are routed here, on F.Cu over
In1's ground with no vias, as mitred pairs (pcb.Layout.pair): U1 to the 220 R column, and the column to J4 over
U6's clamps. J4's other pins leave backwards to vias, and F.Cu is kept clear under its shell."""

import board_setup
import pcb

# ref -> (x, y, rotation): a first cut from plan 2, Task 8; the tests decide
PLACES = {
    # turned 270 so that its D row (pins 9-16) faces J4 with pin 16 at the right, in J4's order. As in TI's layout
    # example (SLVSBC5D, Figure 14), the TMDS lines come in under the package from its left end, between the pad
    # rows, and each leaves over its own clamp pad toward J4. Set 2.75 mm right of J4's TMDS pins, and 2.75 mm up,
    # so that the strip below the lines' approach holds the DDC shifter
    'U6': (75.5, 61.0, 270),
    'C30': (75.2, 55.4, 90),         # U6's 5V_SUPPLY (pin 5)
    'C31': (73.45, 55.4, 90),        # U6's 5V_OUT (pin 6)
    # HSTX's 220 R in one column right of U1, in the connector's pair order (D2, D1, D0, clock), P above N, each pad
    # 1 toward U1
    'R27': (56.5, 25.0, 0),
    'R26': (56.5, 26.71, 0),
    'R25': (56.5, 28.42, 0),
    'R24': (56.5, 30.13, 0),
    'R23': (56.5, 31.84, 0),
    'R22': (56.5, 33.55, 0),
    'R21': (56.5, 35.26, 0),
    'R20': (56.5, 36.97, 0),
    # DDC: Q2 (SDA) and the 2 k at the connector in the strip between the TMDS lines and J4, and Q1 (SCL) above the
    # 2 k, its drain toward them, so that the strip behind J4's pins 13-19 holds their own vias (gate-3 review,
    # finding 1)
    'Q2': (60.05, 65.35, 90),
    'R31': (63.5, 64.2, 0),
    'R30': (63.5, 65.95, 0),
    'Q1': (64.4, 61.3, 270),
    # hot-plug and the I2C side's 10 k, left of where the TMDS lines come down
    'R32': (60.5, 61.4, 180),
    'R33': (60.5, 59.65, 180),
    'R28': (60.5, 57.9, 0),
    'R29': (60.5, 56.15, 0),
}


# ref -> (dx, dy, rotation): designators moved off their footprints' spots, clear of the other silkscreen
# and of pads (off R30's pads and J5's shield leg)
DESIGNATORS = {'Q1': (0.0, -2.4, 0), 'Q2': (0.0, -2.65, 0)}

def place(L):
    for (ref, at) in PLACES.items():
        L.place(ref, *at)
    for (ref, at) in DESIGNATORS.items():
        L.label(ref, *at)


# the four pairs in the connector's order, top to bottom at both ends of the column
PAIRS = ['D2', 'D1', 'D0', 'CK']
# U1's pins (P, N) and the 220 R's pads 1 (P, N)
HSTX = {'D2': ('U1.19', 'U1.18', 'R27.1', 'R26.1'), 'D1': ('U1.17', 'U1.16', 'R25.1', 'R24.1'),
        'D0': ('U1.14', 'U1.13', 'R23.1', 'R22.1'), 'CK': ('U1.12', 'U1.11', 'R21.1', 'R20.1')}
# the 220 R's pads 2, U6's clamp pads and J4's pads, each (P, N)
HDMI = {'D2': ('R27.2', 'R26.2', 'U6.16', 'U6.15', 'J4.1', 'J4.3'),
        'D1': ('R25.2', 'R24.2', 'U6.14', 'U6.13', 'J4.4', 'J4.6'),
        'D0': ('R23.2', 'R22.2', 'U6.12', 'U6.11', 'J4.7', 'J4.9'),
        'CK': ('R21.2', 'R20.2', 'U6.10', 'U6.9', 'J4.10', 'J4.12')}

NECK = 0.2          # the lines' width leaving the QFN's 0.4 mm pitch: each keeps 0.2 mm from the next pad
# HSTX: each pair's centre as it leaves U1, and its turns on the way to the column. D2 rises past C7 once clear of
# it, D1 jogs up, and D0 and CK dive right of C16, C6 and C5, CK first; every bend 45 degrees
HSTX_Y = {'D2': 28.8, 'D1': 29.7, 'D0': 30.7, 'CK': 31.6}
HSTX_TURNS = {'D2': [(50.85, 28.8)], 'D1': [(51.5, 29.7)], 'D0': [(52.6, 30.7)],
              'CK': [(52.0, 31.6), (52.6, 32.2), (52.6, 35.515)]}
# HDMI: the four pairs as one bundle, pair centres 1.025 mm apart (0.6 mm between the pairs' facing lines): from the
# column down-right (x - y = BUNDLE_SE), south along x = BUNDLE_X, and east between U6's pad rows at y = BUNDLE_Y,
# D2 on the bundle's left as it walks, so on top under U6
STEP = 1.025
OFFSET = {'D2': 1.5 * STEP, 'D1': 0.5 * STEP, 'D0': -0.5 * STEP, 'CK': -1.5 * STEP}
BUNDLE_SE = 33.6
BUNDLE_X = 69.0
BUNDLE_Y = 61.06
# each line turns down over its own clamp pad, then down-left to J4 from this y, just past U6's pads
UNDER_U6 = 64.7
# U6 makes each P about 0.93 mm longer than its N (its clamp is 0.65 mm further on, and P runs 0.425 mm above N); N
# makes it up at the column, where it necks into the pair from below with a dip of this depth first
DIP = {'D2': 0.48, 'D1': 0.48, 'D0': 0.48, 'CK': 0.48}


# J4's low-speed pins, 13 (CEC) to 19 (hot-plug), each straight back out of its pad to a via: the odd pins' vias in a
# row just behind the pads, the even pins' a row further back, their stubs passing between the odd pins' vias. The
# TMDS lines hold the backs of pins 1-12, and U6's clamps for these lines face away across them, so the lines go on
# by B.Cu; none leaves forwards, under the connector's shell (gate-3 review, finding 1)
CTRL_ROWS = (67.25, 66.25)          # y: the odd pins' vias, the even pins'
# F.Cu kept clear under J4's shell, between its legs, from the pins' tails to the edge, but for a notch in front of
# the TMDS pins that holds their ground pins' own vias
SHELL = [(64.5, 71.0), (69.75, 71.0), (69.75, 72.0), (75.5, 72.0), (75.5, 71.0), (77.5, 71.0)]


def route(L):
    _hstx(L)
    _hdmi(L)
    _ctrl(L)


def _hstx(L):
    (w, g) = board_setup.TMDS
    half = (w + g) / 2
    for name in PAIRS:
        (p_pin, n_pin, p_pad, n_pad) = HSTX[name]
        (p, n) = ('HSTX_' + name + 'P', 'HSTX_' + name + 'N')
        (a, b) = (L.point(p_pin), L.point(n_pin))
        y = HSTX_Y[name]
        # out of the pins as a narrow pair at their own pitch (0.2 mm lines, 0.2 mm apart), moved up or down to the
        # pair's level with a mitred 45 degree jog; then the lines spread to the pair's pitch over 0.5 mm, still
        # narrow, so that neither comes nearer its partner or the next pair than 0.2 mm
        (x, mid) = (a[0] + 0.65, (a[1] + b[1]) / 2)
        narrow = [(a[0] + 0.4, mid), (x, mid)] + _to_level((x, mid), y) + [(a[0] + 0.95, y)]
        start = (a[0] + 1.45, y)
        L.pair(p, n, 'F.Cu', NECK, NECK, p_pin, n_pin, narrow, (start[0], y - half), (start[0], y + half))
        split = _split(L, p_pad, n_pad, half)
        L.pair(p, n, 'F.Cu', w, g, (start[0], y - half), (start[0], y + half),
               [start] + HSTX_TURNS[name] + _to_level(HSTX_TURNS[name][-1], split[1]) + [split], p_pad, n_pad)


def _split(L, p_pad, n_pad, half):
    """Where a pair heading for two pads stacked one above the other (P on top) splits: its lines run 45 degrees
    into their pads' centres."""
    (a, b) = (L.point(p_pad), L.point(n_pad))
    reach = (b[1] - a[1]) / 2 - half
    return (round(a[0] - reach, 6), round((a[1] + b[1]) / 2, 6))


def _to_level(at, y):
    """The 45 degree run, right and up or down, from at to the level y."""
    if abs(at[1] - y) < 1e-9:
        return []
    return [(round(at[0] + abs(y - at[1]), 6), y)]


def _hdmi(L):
    (w, g) = board_setup.TMDS
    half = (w + g) / 2
    r2 = 2 ** 0.5
    for name in PAIRS:
        (p_pad, n_pad, p_clamp, n_clamp, p_j4, n_j4) = HDMI[name]
        (p, n) = ('HDMI_' + name + 'P', 'HDMI_' + name + 'N')
        (a, b) = (L.point(p_pad), L.point(n_pad))
        # P runs straight out of its pad; N dips, then rises at 45 degrees onto the pair below P
        y = a[1] + half
        dip = DIP[name]
        x = round(b[0] + 2 * dip + (b[1] - a[1] - 2 * half), 6)
        L.track(n, 'F.Cu', w, n_pad, (b[0] + dip, b[1] + dip), (x, y + half))
        # the bundle: down-right, south, then east under U6; this pair at its offset, joining from its own level
        d = OFFSET[name]
        bundle = [(BUNDLE_X - 20.0, BUNDLE_X - 20.0 - BUNDLE_SE), (BUNDLE_X, BUNDLE_X - BUNDLE_SE),
                  (BUNDLE_X, BUNDLE_Y - 1.5), (BUNDLE_X + 1.5, BUNDLE_Y), (BUNDLE_X + 3.0, BUNDLE_Y)]
        lane = pcb.parallel(bundle, d)
        join = (round(y + BUNDLE_SE + d * r2, 6), y)
        centre = [(x, y), join] + lane[1:]
        ends = []
        for (net, clamp, j4, line) in ((p, p_clamp, p_j4, BUNDLE_Y - d - half),
                                       (n, n_clamp, n_j4, BUNDLE_Y - d + half)):
            (c, j) = (L.point(clamp), L.point(j4))
            shift = c[0] - j[0]
            ends.append([(c[0] - 0.3, line), (c[0], line + 0.3), clamp, (c[0], UNDER_U6),
                         (j[0], round(UNDER_U6 + shift, 6)), j4])
        L.pair(p, n, 'F.Cu', w, g, p_pad, (x, y + half), centre, ends[0][0], ends[1][0])
        L.track(p, 'F.Cu', w, *ends[0])
        L.track(n, 'F.Cu', w, *ends[1])


def _ctrl(L):
    for pin in range(13, 20):
        pad = f'J4.{pin}'
        at = (L.point(pad)[0], CTRL_ROWS[(pin - 13) % 2])
        L.track(L.net(pad), 'F.Cu', 0.2, pad, at)
        L.via(L.net(pad), at, size=0.45, drill=0.2)
        L.escapes.append((L.vias[-1], L.tracks[-1]))    # a via the routes leave unused is left out (pcb_build)
    L.keepout("Under J4's shell", ['F.Cu'], SHELL + [(SHELL[-1][0], L.height), (SHELL[0][0], L.height)], tracks=True,
              vias=True, pours=False)
