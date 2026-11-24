# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Power (spec, "Power"): the USB-C input's ESD, fuse, TVS, ferrite and bulk, in that order from the connector; the
3.3 V LDO with copper round its tab for its quarter watt; the power LED; and the test points, each with room for a
probe. The console's USB pair runs from J6 through U11 to the 27 R by U1 (route)."""

import board_setup
import pcb

# ref -> (x, y, rotation): a first cut from plan 2, Task 9; the tests decide
PLACES = {
    'U11': (30.0, 68.5, 270),         # USBLC6, right behind J6's D+ and D- pins
    'R40': (26.4, 69.2, 90),          # 5.1 k at CC1 (A5)
    'R41': (33.6, 69.2, 90),          # 5.1 k at CC2 (B5)
    # VBUS up the left of J6, clear of the coax band: fuse, TVS, ferrite, then the 5 V rail's bulk
    'F1': (23.2, 67.8, 90),
    'D4': (23.2, 58.25, 90),
    'FB1': (26.6, 64.0, 90),
    'C40': (26.6, 60.2, 90),
    'C41': (28.6, 61.0, 90),
    # the 3.3 V LDO above, its pins down toward the 5 V rail, its tab (GND) up with room round it for copper
    'U12': (29.0, 51.9, 90),
    'C42': (24.15, 52.5, 90),         # +5V in (pin 1)
    'C43': (33.85, 53.5, 90),         # +3V3 out (pin 3)
    'C44': (31.3, 58.6, 270),
    'R42': (26.0, 46.5, 0),           # power LED
    'D5': (29.25, 46.5, 0),
    # test points, each by its rail with room for a probe
    'TP1': (29.5, 64.5, 0),           # +5V
    'TP2': (37.2, 53.5, 0),           # +3V3
    'TP3': (63.8, 11.0, 0),           # +1V8, by the DAC's LDO
    'TP4': (34.5, 44.0, 0),           # +1V1
    'TP5': (32.5, 63.5, 0),           # GND
}


# ref -> (dx, dy, rotation): designators moved off their footprints' spots, clear of the other silkscreen
DESIGNATORS = {'U12': (0.0, 0.5, 0),          # on the LDO's body, between its tab and its pins, off C42
               'D4': (0.0, 0.0, 0), 'F1': (0.0, 0.0, 0)}      # on their bodies, off the line side's outline

# what each test point carries, on the silkscreen below it, for bring-up's first step (gate-2 review, finding 8)
RAILS = [('+5V', 29.5, 66.1), ('GND', 32.5, 65.1), ('3V3', 37.2, 55.1), ('1V1', 34.5, 45.6), ('1V8', 63.8, 12.6)]

def place(L):
    for (ref, at) in PLACES.items():
        L.place(ref, *at)
    for (ref, at) in DESIGNATORS.items():
        L.label(ref, *at)
    for (text, x, y) in RAILS:
        L.text(text, x, y, size=0.8)


def route(L):
    _usb_c(L)


def _usb_c(L):
    """USB-C's D+ and D-: J6's B7 and B6 run straight up into U11's pins 4 and 6, in its order (D- left, D+
    right); A7 (D-) crosses to D- under U11's VBUS pin, and A6 (D+) reaches B6 on B.Cu through a via past each pad's
    far end, under the shell (D+ takes the crossing because D- takes the longer way into U11). From U11's pins 3
    and 1 the pair rises between TP1 and TP5, runs up-right past C44, TP2 and C43, and north to R6 and R5. U11's
    GND (pin 2) and VBUS (pin 5) pins, hemmed in by the pair, each take a via between its pad rows."""
    (w, g) = board_setup.USB
    (dp, dm) = ('USBC_DP', 'USBC_DM')
    # J6 to U11
    L.track(dm, 'F.Cu', w, 'J6.B7', (29.25, 71.2), (29.05, 71.0), 'U11.4')
    L.track(dp, 'F.Cu', w, 'J6.B6', (30.75, 71.2), (30.95, 71.0), 'U11.6')
    L.track(dm, 'F.Cu', w, 'J6.A7', (30.25, 71.2), (29.95, 70.9), (29.05, 70.9))
    for (pad, at) in (('J6.A6', (29.75, 73.5)), ('J6.B6', (30.75, 73.5))):
        L.track(dp, 'F.Cu', w, pad, at)
        L.via(dp, at)
    L.track(dp, 'B.Cu', w, (29.75, 73.5), (30.75, 73.5))
    # U11 to the 27 R: walking from R5/R6 down to U11, D+ on the left (east)
    L.pair(dp, dm, 'F.Cu', w, g, 'R5.2', 'R6.2', [(41.975, 42.75), (41.975, 51.525), (31.0, 62.5), (31.0, 66.0)],
           (31.2, 66.7), (30.45, 66.35))
    L.track(dp, 'F.Cu', w, (31.2, 66.7), 'U11.1')
    L.track(dm, 'F.Cu', w, (30.45, 66.35), (29.4, 66.35), (29.05, 66.7), 'U11.3')
    # through U11: each line straight across from the pin it enters by to the pin it leaves by
    L.track(dp, 'F.Cu', w, 'U11.6', 'U11.1')
    L.track(dm, 'F.Cu', w, 'U11.4', 'U11.3')
    # U11's GND and VBUS pins, between its rows
    for (net, pad, at) in (('GND', 'U11.2', (29.6, 68.5)), ('VBUS', 'U11.5', (30.4, 68.5))):
        L.track(net, 'F.Cu', 0.2, pad, at)
        L.via(net, at, size=0.45, drill=0.2)
    # J6's two VBUS pin pairs joined to each other and to U11's VBUS via on B.Cu, as Freerouting had them at gate 3 (a
    # later run left U11's via apart); Freerouting takes them on to F1
    L.track('VBUS', 'F.Cu', 0.5, 'J6.A4', (27.55, 70.07), (28.08, 70.07))
    L.via('VBUS', (28.08, 70.07), size=0.8, drill=0.4)
    L.track('VBUS', 'B.Cu', 0.5, (28.08, 70.07), (29.76, 70.07), (30.4, 69.43), (30.4, 68.5))
    L.track('VBUS', 'B.Cu', 0.5, (30.4, 69.43), (30.93, 69.43), (32.45, 70.95))
    L.via('VBUS', (32.45, 70.95), size=0.8, drill=0.4)
    L.track('VBUS', 'F.Cu', 0.5, (32.45, 70.95), 'J6.A9')
    # CC1 (A5) over the VBUS and GND pins to R40 by B.Cu, its via past the pad's end in line with the housing's posts,
    # as Freerouting had it at gate 3 (a later run left it unrouted)
    L.track('CC1', 'F.Cu', 0.2, 'J6.A5', (28.75, 73.235), (28.485, 73.5))
    L.via('CC1', (28.485, 73.5))
    L.track('CC1', 'B.Cu', 0.2, (28.485, 73.5), (25.7, 70.715))
    L.via('CC1', (25.7, 70.715))
    L.track('CC1', 'F.Cu', 0.2, (25.7, 70.715), 'R40.1')
    # past the posts of J6's housing its shell sits on the board: F.Cu kept clear there, between its legs, to the
    # edge (gate-3 review, finding 1)
    L.keepout("Under J6's shell", ['F.Cu'], pcb.rect(26.2, 74.1, 33.8, L.height), tracks=True, vias=True,
              pours=False)
