# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""USB host (spec, "USB host"): the AP2171W port switch, the CH334F hub with its crystal between U1's GPIO 1/2 and
the stacked USB-A, and a USBLC6 on each port, the lines passing straight through it. The pairs, the hub's crystal
and its regulator's capacitors are routed here (route)."""

import board_setup
import pcb

# ref -> (x, y, rotation): a first cut from plan 2, Task 9; the tests decide
PLACES = {
    # CH334F right of the flash, its downstream pins (9-12) toward J5, port 2's left of port 1's
    'U8': (57.75, 50.0, 0),
    'Y2': (52.95, 50.0, 90),          # at XI/XO (pins 4, 3), between the flash and the hub, its silk clear of U8's
    'C33': (56.5, 45.1, 90),          # VDD33 (pin 20)
    'C34': (58.5, 45.4, 90),
    'C36': (60.25, 45.4, 90),         # V5 (pin 19)
    'C35': (62.25, 45.1, 90),
    # the ports' switch: +5V in at its top left, USBH_5V out to the hub and J5
    'U7': (53.35, 44.6, 90),
    'C32': (52.9, 40.9, 0),
    'R34': (56.6, 41.4, 0),           # EN pull-down
    'R35': (59.85, 41.4, 0),          # FLG pull-up
    # each port's USBLC6 above J5, its pair passing straight through: DM left, DP right as J5 has them
    'U9': (49.5, 59.5, 270),          # port 1, J5's upper row
    'U10': (53.5, 59.5, 270),         # port 2, J5's lower row
    'C37': (45.0, 59.0, 90),          # 100 uF at J5's VBUS
    'C38': (42.4, 59.0, 90),
    # the hub's LEDs, right of it, far enough out that the upstream pair (pins 14, 15, on that side) can turn or drop
    # to vias between them and the hub, and still short of the TMDS lines' way down (x 65-72) (gate 2)
    'D2': (64.0, 48.3, 0),
    'D3': (64.0, 50.05, 0),
    'R36': (64.0, 51.8, 0),
}


# ref -> (dx, dy, rotation): designators moved off their footprints' spots, clear of the other silkscreen
DESIGNATORS = {'U8': (-1.85, 3.3, 0),          # below-left of the hub, off C33's and C34's pads
               'Y2': (0.0, 3.1, 0), 'U7': (2.25, -1.6, 0), 'D2': (2.6, 0.0, 0), 'D3': (2.6, 0.0, 0),
               'U9': (-2.5, 0.0, 90), 'U10': (2.6, 0.0, 90)}

def place(L):
    for (ref, at) in PLACES.items():
        L.place(ref, *at)
    for (ref, at) in DESIGNATORS.items():
        L.label(ref, *at)


VIA = (0.45, 0.2)       # size, drill: the USB pairs' vias, small enough to sit side by side at the QFNs


def route(L):
    _upstream(L)
    _crystal(L)
    _regulator(L)
    _ports(L)


def _via(L, net, at):
    L.via(net, at, size=VIA[0], drill=VIA[1])


def _upstream(L):
    """USBH, U1's pins 78 and 79 to the hub's 15 and 14. QSPI's lines run under U1 between these pins and the hub
    (Task 6), so the pair drops to B.Cu inside U1's pad ring, runs down-right under the hub's corner, and comes up
    beside pins 15 and 14."""
    (w, g) = board_setup.USB
    (dp, dm) = ('USBH_DP', 'USBH_DM')
    (dp_u1, dm_u1, dp_u8, dm_u8) = ((45.45, 35.45), (45.6, 36.15), (61.6, 49.2), (60.75, 51.15))
    L.track(dp, 'F.Cu', 0.2, 'U1.78', (45.0, 35.9), dp_u1)
    L.track(dm, 'F.Cu', 0.2, 'U1.79', (45.4, 36.35), dm_u1)
    L.track(dp, 'F.Cu', 0.2, 'U8.15', (60.55, 50.25), dp_u8)
    L.track(dm, 'F.Cu', 0.2, 'U8.14', (60.35, 50.75), dm_u8)
    for (net, at) in ((dp, dp_u1), (dm, dm_u1), (dp, dp_u8), (dm, dm_u8)):
        _via(L, net, at)
    # walking from U1 to the hub, D+ on the left: north of D- leaving U1, then north-east, then east going down; the
    # pair leaves its two vias across its own direction, so that neither line runs beside the other's via
    L.pair(dp, dm, 'B.Cu', w, g, dp_u1, dm_u1,
           [(46.1, 35.8), (46.6, 35.8), (55.3, 44.5), (59.9, 44.5), (61.4, 46.0), (61.4, 48.4)], dp_u8, (60.75, 48.85))
    L.track(dm, 'B.Cu', w, (60.75, 48.85), dm_u8)


def _crystal(L):
    """The hub's 12 MHz crystal, Y2, left of its XI and XO (pins 4 and 3): XI straight into Y2 pin 1, XO up and over
    Y2's ground pad into pin 3; the grounds by vias, pin 2's between Y2's pad rows."""
    w = 0.2
    L.track('HUB_XI', 'F.Cu', w, 'U8.4', (55.1, 50.25), (54.25, 51.1), 'Y2.1')
    L.track('HUB_XO', 'F.Cu', w, 'U8.3', (55.0, 49.75), (55.0, 47.9), (52.45, 47.9), (52.1, 48.25), 'Y2.3')
    for (pad, at) in (('Y2.2', (53.8, 50.0)), ('Y2.4', (52.1, 52.45))):
        L.track('GND', 'F.Cu', 0.3, pad, at)
        L.via('GND', at, size=0.45, drill=0.2)


def _regulator(L):
    """The hub's own 3.3 V regulator (VDD33, pin 20): its 10 u, C33, straight across to its 1 u, C34, which stands
    over the pin (gate-3 review, finding 3: left to Freerouting, C33 joined it by 19 mm and two vias). And the port
    switch's supply into its input capacitor."""
    L.track('HUB_V33', 'F.Cu', 0.25, 'C34.1', 'C33.1')
    # the port switch's input (pin 5) to its 10 u, C32: Freerouting's 0.5 mm +5V once failed to reach the pin
    L.track('+5V', 'F.Cu', 0.5, 'U7.5', (51.95, 43.0125), 'C32.1')


def _ports(L):
    """The hub's two downstream pairs. Port 2 (pins 9, 10) runs on F.Cu down to its USBLC6, U10, then through the
    1 mm between J5's pins 3 and 4 to the lower row (pins 6, 7). Port 1 (pins 11, 12), which would cross it, drops
    to B.Cu under it and comes up above its USBLC6, U9, which sits right over J5's upper row (pins 2, 3). Each
    USBLC6's GND (pin 2) and USBH_5V (pin 5), hemmed in by its pair, takes a via."""
    (w, g) = board_setup.USB
    # port 2: U8 to U10, down-left with D+ on the left (south-east); it splits over U10 round its pin 2. D- runs
    # 2 mm further at J5 (pin 6 is past pin 7) and round U10's pin 2, so D+ takes a 45 degree trombone out to the
    # south-east on the way (1.17 mm)
    (dp, dm) = ('USBA2_DP', 'USBA2_DM')
    half = (w + g) / 2
    (dp_line, dm_line) = (pcb.parallel([(57.75, 52.75), (57.75, 53.0), (53.8, 56.95)], s) for s in (half, -half))
    c = dp_line[-1][0] + dp_line[-1][1]        # D+'s line down-left is x + y = c: the trombone leaves and rejoins it
    (x, y) = (57.6, c - 57.6)
    L.track(dp, 'F.Cu', w, 'U8.10', *dp_line[:2], (x, y), (x, y + 2.0), (x - 0.424, y + 2.424),
            (x - 2.424, y + 2.424), dp_line[2], 'U10.1')
    L.track(dm, 'F.Cu', w, 'U8.9', *dm_line, (52.85, dm_line[2][1]), (52.55, dm_line[2][1] + 0.3), 'U10.3')
    # U10 to J5's lower row, between pins 3 and 4 and under the upper row
    L.track(dm, 'F.Cu', w, 'U10.4', (52.55, 61.6), (51.55, 62.6), (51.55, 65.2), (51.05, 65.7), (49.0, 65.7),
            (48.5, 66.2), 'J5.6')
    L.track(dp, 'F.Cu', w, 'U10.6', (54.45, 61.2), (51.95, 63.7), (51.95, 65.366), (50.5, 66.816), 'J5.7')
    # port 1: down from U8 to vias, on B.Cu under port 2 to vias over U9, split round its pin 2, then straight
    # through U9 into J5
    (dp, dm) = ('USBA1_DP', 'USBA1_DM')
    (dp_u8, dm_u8, dp_u9, dm_u9) = ((59.25, 53.4), (58.5, 53.4), (50.45, 56.75), (48.55, 56.75))
    L.track(dp, 'F.Cu', 0.2, 'U8.12', (59.0, 53.15), dp_u8)
    L.track(dm, 'F.Cu', 0.2, 'U8.11', dm_u8)
    L.track(dp, 'F.Cu', w, dp_u9, 'U9.1')
    L.track(dm, 'F.Cu', w, dm_u9, 'U9.3')
    for (net, at) in ((dp, dp_u8), (dm, dm_u8), (dp, dp_u9), (dm, dm_u9)):
        _via(L, net, at)
    L.pair(dp, dm, 'B.Cu', w, g, dp_u8, dm_u8,
           [(58.875, 53.85), (58.875, 54.6), (58.075, 55.4), (50.0, 55.4), (49.5, 55.9), (49.5, 56.0)], dp_u9, dm_u9)
    L.track(dp, 'F.Cu', w, 'U9.6', 'J5.3')
    L.track(dm, 'F.Cu', w, 'U9.4', 'J5.2')
    # through each USBLC6: each line straight across from the pin it enters by to the pin it leaves by
    for (u, dp, dm) in (('U9', 'USBA1_DP', 'USBA1_DM'), ('U10', 'USBA2_DP', 'USBA2_DM')):
        L.track(dp, 'F.Cu', w, u + '.1', u + '.6')
        L.track(dm, 'F.Cu', w, u + '.3', u + '.4')
    # each USBLC6's middle pins, hemmed in by its pair: vias between its pad rows, as at U11, and U9's pin 5 below
    for (net, pad, at) in (('GND', 'U10.2', (53.1, 59.5)), ('USBH_5V', 'U10.5', (53.9, 59.5)),
                           ('GND', 'U9.2', (49.5, 59.5)), ('USBH_5V', 'U9.5', (49.5, 62.3))):
        L.track(net, 'F.Cu', 0.2, pad, at)
        L.via(net, at, size=0.45, drill=0.2)
