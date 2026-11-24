# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Audio (spec, "Sound"): the TLV320DAC3100 and its 1.8 V LDO in the top-right corner, its I2S and I2C pins toward
U1's top edge, and the speaker connector J7 in the corner, away from the coax front end: the class-D output is
unfiltered and the firmware leaves it on (gate-1 review)."""

# ref -> (x, y, rotation): a first cut from plan 2, Task 10; the tests decide
PLACES = {
    'U14': (78.0, 16.0, 0),           # its I2S (pins 5-8, left) and I2C (9, 10, bottom) toward U1
    'J7': (92.0, 12.0, 0),            # the speaker's JST-PH, clear of H2
    # IOVDD (pin 2) and DVDD (pin 3) from the left, above where I2S comes in
    'C52': (73.1, 12.28, 180),
    'C53': (73.1, 14.0, 180),
    'C54': (75.85, 10.4, 90),
    'R43': (73.1, 10.55, 0),          # ~RESET's pull-up, pin 31
    'C57': (78.25, 10.9, 90),         # HPVDD (pin 28)
    # the 1.8 V LDO up and left, its output toward DVDD
    'U13': (68.0, 11.0, 0),
    'C50': (66.5, 7.55, 90),          # +5V in (pin 1)
    'C51': (68.25, 7.55, 90),         # +1V8 out (pin 5)
    # SPKVDD (pins 24, 21) and AVDD (17) on the right, toward J7
    'C59': (82.15, 11.35, 90),
    'C58': (83.2, 16.0, 0),
    'C60': (83.4, 18.0, 0),
    'C55': (81.6, 21.0, 270),
    'C56': (83.6, 21.0, 270),
}


# ref -> (dx, dy, rotation): designators moved off their footprints' spots, clear of the other silkscreen
# and of pads (below each, off C50, C51 and C57)
DESIGNATORS = {'U13': (0.0, 2.4, 0), 'U14': (0.0, 3.9, 0)}

def place(L):
    for (ref, at) in PLACES.items():
        L.place(ref, *at)
    for (ref, at) in DESIGNATORS.items():
        L.label(ref, *at)


def route(L):
    """U14's crowded sides, where Freerouting's 0.5 mm power tracks can't get between the 0.5 mm pitch pins. On the
    right, the +5V pins 24 and 21 run straight to C59 and C58, joined round the outside, and the speaker pins
    between them, 23 (SPK_N) and 22 (SPK_P), drop to vias in the room that leaves; on the left, pins 2 (+3V3) and 3
    (+1V8) take vias staggered out of each other's way. Freerouting joins the vias to J7, the other speaker pins and
    C53."""
    L.track('+5V', 'F.Cu', 0.25, 'U14.24', (80.95, 14.25), (82.15, 13.05), 'C59.1')
    L.track('+5V', 'F.Cu', 0.25, 'U14.21', (81.45, 15.75), (81.7, 16.0), 'C58.1')
    # the two capacitors joined round the speaker pins' vias
    L.track('+5V', 'F.Cu', 0.3, 'C59.1', (83.2, 12.12), (83.2, 15.25), (82.8, 15.65), 'C58.1')
    # and C58 straight down to SPKVDD's 10 u, C60 (a Freerouting run once left them apart)
    L.track('+5V', 'F.Cu', 0.4, 'C58.1', 'C60.1')
    for (net, points, via) in (('SPK_N', ['U14.23'], (81.65, 14.75)),
                               ('SPK_P', ['U14.22', (82.15, 15.25)], (82.45, 14.95)),
                               ('+3V3', ['U14.2'], (74.7, 14.6)), ('+1V8', ['U14.3'], (74.2, 15.5))):
        L.track(net, 'F.Cu', 0.2, *points, via)
        L.via(net, via, size=0.45, drill=0.2)
        L.escapes.append((L.vias[-1], L.tracks[-1]))    # for Freerouting: left out if its routes don't use it
