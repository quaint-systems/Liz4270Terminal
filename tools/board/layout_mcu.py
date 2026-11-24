# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The core (spec, "Core" and "Pin map"): the RP2350B turned 180 degrees, so that its coax pins face the coax block
on the left, HSTX faces right toward HDMI, and the regulator, console USB, QSPI and USB host face the connector edge;
the regulator copied from Raspberry Pi's minimal design (regulator.py); flash, crystal, decoupling, SWD, board ID,
heartbeat LED and the bench header."""

import regulator

NECK = 0.15         # the console USB's lines under the regulator's copper, and the crystal's between Y1's pads

U1 = (42.0, 32.0, 180)

# ref -> (x, y, rotation): a first cut from plan 2, Task 6; the tests decide
PLACES = {
    # flash, below and right of the regulator: pins 8-5 (VCC, SD3, CLK, SD0) face U1's QSPI pins, in their order
    'U2': (48.2, 47.15, 90),
    'C21': (44.3, 44.5, 270),        # U2's VCC (pin 8, top left)
    'R4': (46.3, 53.55, 270),        # BOOTSEL's 1 k at U2's CS (pin 1), so SW1's trace hangs off the resistor
    'R3': (44.55, 53.55, 270),       # CS pull-up, not fitted
    # the bottom's 3.3 V pins 68, 69 and 76, just right of the regulator; SD3, CLK and SD0 pass between them
    'C13': (44.6, 40.75, 270),
    'C14': (46.35, 40.75, 270),
    'C15': (48.1, 40.75, 270),
    # right side, below HSTX: pins 10 (+1V1), 15 and 5, then the board ID's pull-downs at GPIO 4/5 (pins 1, 2),
    # below the HSTX lines' fan to their resistors
    'C16': (49.35, 32.95, 0),
    'C6': (49.35, 34.66, 0),
    'C5': (49.35, 36.37, 0),
    'R8': (49.35, 38.1, 0),
    'R7': (52.6, 38.1, 0),
    # top right, clear of the I2S and I2C lanes: pins 29 and 24
    'C8': (47.7, 25.25, 0),
    'C7': (49.35, 27.4, 0),
    # the crystal above XIN/XOUT: XIN runs straight up to Y1 pin 1, XOUT straight up into R2
    'Y1': (41.15, 20.1, 90),
    'R2': (41.7, 23.95, 90),
    'C19': (44.0, 19.4, 90),
    'C20': (37.95, 19.3, 270),
    # DVDD pin 32's 4.7 uF (6.3.8.1) and 100 n; SWD's 100 R, as RP-003139-SP asks: SWCLK turns up into R44, SWDIO
    # runs on beneath it to R45
    'C3': (40.25, 24.55, 90),
    'R44': (38.8, 23.95, 90),
    'R45': (36.3, 25.4, 180),
    'C17': (36.05, 23.3, 180),
    'J1': (32.4, 19.0, 180),         # SWD: its opening (the side of its tabs) toward the top edge, pads toward R44/R45
    # RUN's 100 n, not fitted: the nearest free 0603 to pin 35 that blocks no lane (C3 and the SWD lines cover the
    # pin, so RUN leaves it by a via and reaches this pad 1 by another); pad 1 (RUN) toward the pin (gate 2)
    'C61': (37.9, 21.7, 180),
    'D1': (32.0, 24.3, 180),         # heartbeat LED
    'R9': (32.0, 26.05, 180),
    # left side: pins 41, 50 and 51 above the coax pins, 59 and 60 below
    'C9': (34.65, 28.2, 180),
    'C10': (34.65, 29.95, 180),
    'C18': (34.65, 31.7, 180),
    'C11': (34.65, 34.9, 180),
    'C12': (34.65, 36.65, 180),
    'J2': (24.0, 14.0, 0),           # bench header, not fitted: pin 1 top left
}


# ref -> (dx, dy, rotation): designators moved off their footprints' spots, clear of the other silkscreen
DESIGNATORS = {'D1': (-2.4, 0.0, 0), 'J1': (-3.6, 0.0, 0),     # left of each, off R9 and D1
               'Y1': (-0.55, -2.8, 0)}                         # above the crystal, off C20's pads

# the bench header's odd pins named on their left, and its ground column on the right, for the logic analyzer
# (gate-2 review, finding 8): pin -> name
BENCH = {'1': 'RX', '3': 'TX', '5': 'TXA', '7': 'TXD', '9': 'UTX', '11': 'URX', '13': '3V3'}

def place(L):
    L.place('U1', *U1)
    regulator.place(L)
    for (ref, at) in PLACES.items():
        L.place(ref, *at)
    for (ref, at) in DESIGNATORS.items():
        L.label(ref, *at)
    for (pin, name) in BENCH.items():
        L.text(name, L.pad('J2', pin)[0] - 2.7, L.pad('J2', pin)[1], size=0.8)
    L.text('GND', L.pad('J2', '14')[0] + 2.7, L.pad('J2', '14')[1], size=0.8)


# (the pad and any corner to its via, the via, its size and drill): the 1.1 V's way down to the spine
DVDD_VIAS = [(['C16.1'], (48.575, 33.75), 0.45, 0.2), (['C18.1'], (36.2, 31.7), 0.45, 0.2),
             (['C3.1'], (40.25, 25.63), 0.45, 0.2), (['C17.1'], (37.6, 23.3), 0.45, 0.2),
             (['TP4.1', (34.5, 43.32)], (35.08, 42.74), 0.8, 0.4)]
# B.Cu, from the regulator's via at (40.5, 38.7) (regulator.VIAS)
DVDD_SPINE = [[(40.5, 38.7), (40.37, 38.57), (40.37, 34.6), (40.49, 34.48)],
              [(40.49, 34.48), (38.86, 32.85), (38.86, 26.87), (40.09, 25.63), (40.25, 25.63)],
              [(40.09, 25.63), (40.09, 25.38), (38.01, 23.3), (37.6, 23.3)],
              [(38.86, 31.05), (36.85, 31.05), (36.2, 31.7)],          # clear of pin 50's via to In2
              [(40.49, 34.48), (40.6, 34.36), (43.66, 34.36), (44.1, 33.92), (44.1, 33.57), (45.78, 31.89),
               (47.1, 31.89), (48.575, 33.365), (48.575, 33.75)],
              [(40.37, 38.57), (38.59, 40.35), (37.04, 40.35), (35.08, 42.31), (35.08, 42.74)]]


def route(L):
    regulator.route(L)
    _console_usb(L)
    _crystal(L)
    _dvdd(L)
    _bootsel(L)


def _dvdd(L):
    """Each DVDD pin to its capacitor on F.Cu: pin 10 to C16 down past pin 9, pin 51 to C18, pin 32 to C3. Each
    capacitor, and C17 and TP4, takes the 1.1 V on through a via of its own, and B.Cu joins them, 0.5 mm wide, to the
    regulator copy's two +1V1 vias beside L1: down x 40.4 from them under U1, west and north to C18, C3 and C17, east
    to C16, and south-west to TP4. Left to Freerouting, the rail went round by F.Cu and the vias hung unused (gate-3
    review); this is the spine Freerouting drew at gate 3, kept, its branch to C18 moved off U1 pin 50's via."""
    L.track('+1V1', 'F.Cu', 0.2, 'U1.10', (47.45, 32.2), (48.2, 32.95), 'C16.1')
    L.track('+1V1', 'F.Cu', 0.2, 'U1.51', (36.05, 32.2), (35.55, 31.7), 'C18.1')
    L.track('+1V1', 'F.Cu', 0.2, 'U1.32', (41.4, 26.18), (40.55, 25.33), 'C3.1')
    for (pad, at, size, drill) in DVDD_VIAS:
        L.track('+1V1', 'F.Cu', 0.25 if size < 0.8 else 0.5, *pad, at)
        L.via('+1V1', at, size=size, drill=drill)
    for points in DVDD_SPINE:
        L.track('+1V1', 'B.Cu', 0.5, *points)


def _bootsel(L):
    """BOOTSEL, from R4 by the flash to SW1 in the far corner, on B.Cu: between J5's left shield leg and its pin 1,
    under J5 and J4 between their shield legs, and into SW1 from below."""
    net = L.net('R4.2')
    L.track(net, 'F.Cu', 0.2, 'R4.2', (46.3, 55.35))
    L.via(net, (46.3, 55.35), size=0.45, drill=0.2)
    L.track(net, 'B.Cu', 0.25, (46.3, 55.35), (44.84, 56.81), (44.84, 72.9), (45.44, 73.5), (79.325, 73.5),
            (79.925, 74.1), (79.925, 77.7), (80.525, 78.3), (86.65, 78.3), (87.25, 77.7), 'SW1.1')


def _console_usb(L):
    """USB D- and D+ from pins 66 and 67 to the 27 R. VREG_FB's track and the +1V1 vias of the regulator's copy sit
    right below the pins, and QSPI_SD3 comes down from pin 70, so the pair leaves at 45 degrees to the right, runs
    down between the +1V1 copper (x 40.8) and pin 70, and splits to R6 and R5: 3 mm at 0.15 mm (USB's gap, the
    most that fits), which full speed doesn't see."""
    L.track('Net-(U1-USB_DM)', 'F.Cu', NECK, 'U1.66', (40.2, 37.45), (41.1, 38.35), 'R6.1')
    L.track('Net-(U1-USB_DP)', 'F.Cu', NECK, 'U1.67', (40.6, 37.4), (41.4, 38.2), (41.4, 38.975), 'R5.1')


def _crystal(L):
    """The 12 MHz crystal (Y1 above the chip's top side): XIN up past R2 into Y1 pin 1, then to its load capacitor
    C19; XOUT straight into R2; R2 up between Y1's pads 4 and 1 and into pin 3, then to C20. Y1's, C19's and C20's
    grounds each take a via of their own to In1."""
    w = 0.2
    L.track('XIN', 'F.Cu', w, 'U1.30', (42.2, 26.3), (42.5, 26.0), (42.5, 21.7), 'Y1.1')
    L.track('XIN', 'F.Cu', w, 'Y1.1', (42.975, 21.2), 'C19.1')
    L.track('XOUT', 'F.Cu', w, 'U1.31', (41.8, 24.875), 'R2.1')
    load = L.net('Y1.3')
    L.track(load, 'F.Cu', NECK, 'R2.2', (41.7, 22.7), (41.15, 22.15), (41.15, 20.1), (40.3, 20.1), 'Y1.3')
    L.track(load, 'F.Cu', w, 'Y1.3', (38.425, 19.0), 'C20.1')
    for (pad, via) in (('Y1.2', (42.0, 17.55)), ('C19.2', (44.0, 17.45)), ('Y1.4', (40.3, 22.65)),
                       ('C20.2', (36.85, 20.075))):
        L.track('GND', 'F.Cu', 0.3, pad, via)
        L.via('GND', via)
