# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The coax front end (spec, "Coax front end"): the Liz 4174's port 1, with its line side behind an isolation gap.

The line side is the BNC, R10, C26's line pad and T1's line pins 1 and 6. It fills the BNC corner, and a 1.5 mm band
on every copper layer wraps it: no track, via or pour crosses it, so the transformer's 1000 Vrms isolation isn't
defeated by a nearby plane. 1.5 mm is what T1 itself keeps between its line pins and its RX pins. The line side's
own copper is drawn here, since the keep-outs bar Freerouting from it. The drive, from U4 through R11-R14 to the TX
winding with R15 across it, is laid out symmetric: the waveform is the sum of its two halves."""

import pcb

LINE_SIDE = pcb.rect(0.0, 59.02, 19.5, 80.0)
BAND_POLYGON = ((0.0, 57.52), (21.0, 57.52), (21.0, 80.0), (19.5, 80.0), (19.5, 59.02), (0.0, 59.02))

# ref -> (x, y, rotation): a first cut from plan 2, Task 7; the tests decide
PLACES = {
    'T1': (10.0, 57.0, 180),          # line pins 1 and 6 nearest the BNC
    'R10': (10.0, 63.2, 180),         # 120 R across the line: pad 1 (LINE_C) right, pad 2 (LINE_S) left
    'C26': (20.5, 63.2, 0),           # 1 nF 2 kV, not fitted: LINE_S pad inside, GND pad beyond the band
    'U4': (10.0, 38.0, 90),           # driver, above T1, its outputs (pins 1-8) toward it
    'R16': (9.35, 42.7, 0),           # TX_ACTIVE's pull-down at U4 pin 4
    # the drive, mirrored about T1's centre line, clear of H4: the delayed pair (150 R) by the driver, the main pair
    # (33 R) by T1, each standing with its driver pad up, P (to TX_P, T1's right) right and N left; R15 across them
    # on the centre line, just past T1's body on its TX side, as on the Liz 4174
    'R12': (9.12, 45.2, 270),
    'R11': (10.88, 45.2, 270),
    'R14': (9.12, 48.65, 270),
    'R13': (10.88, 48.65, 270),
    'R15': (10.0, 51.15, 180),
    # receiver, beside the driver: RX_P leaves T1's right column, RX_N passes beneath T1 between its TX and RX rows
    'U3': (20.7, 38.0, 90),
    'U5': (20.3, 51.0, 0),            # ESD array on TX and RX at T1's IC side, not fitted
    'C24': (5.6, 32.55, 90),          # U4's +3V3 (pin 16)
    'C25': (7.35, 32.55, 90),
    'C22': (16.3, 32.55, 90),         # U3's +3V3 (pin 16)
    'C23': (18.05, 32.55, 90),
}


# ref -> (dx, dy, rotation): designators moved off their footprints' spots, clear of the other silkscreen
DESIGNATORS = {'T1': (0.0, 0.0, 0), 'U3': (0.0, 0.0, 0)}       # on their bodies, off J3's and U4's outlines

def place(L):
    for (ref, at) in PLACES.items():
        L.place(ref, *at)
    for (ref, at) in DESIGNATORS.items():
        L.label(ref, *at)
    L.keepout('Coax line side', pcb.COPPER, LINE_SIDE)
    L.keepout('Coax isolation band', pcb.COPPER, BAND_POLYGON, tracks=True, vias=True)
    # the line side's outline along the middle of the band, and a warning beside the BNC: its shell is the line's
    # shield, not ground (gate-2 review, finding 8); the band's upright strip holds the text, and the line breaks
    # for C26 and for it
    L.line('F.SilkS', 0.15, (0.4, 58.27), (20.25, 58.27), (20.25, 62.0))
    L.line('F.SilkS', 0.15, (20.25, 74.6), (20.25, 79.6))
    L.text('LINE: NOT GND', 20.25, 69.6, size=0.8, rot=90)


# J3's three pads named 2 (KiCad doesn't count same-numbered pads as joined, so each gets copper): the left and right
# shell pegs and the small pin beside the centre
J3_SHELL_LEFT = (4.92, 72.38)
J3_SHELL_RIGHT = (15.08, 72.38)
J3_PIN = (12.54, 67.3)


def route(L):
    """The line side's copper, 0.4 mm (CoaxLine), on F.Cu inside LINE_SIDE."""
    w = 0.4
    # LINE_C: the BNC's centre pin, R10, then T1's line pin 1
    L.track('LINE_C', 'F.Cu', w, 'J3.1', (10.0, 64.025), 'R10.1')
    L.track('LINE_C', 'F.Cu', w, 'R10.1', (12.67, 63.2), 'T1.1')
    # LINE_S: the left shell up the left side to T1's line pin 6, with R10 off it
    L.track('LINE_S', 'F.Cu', w, J3_SHELL_LEFT, (4.92, 60.79), 'T1.6')
    L.track('LINE_S', 'F.Cu', w, (4.92, 63.2), 'R10.2')
    # the shells joined beneath the centre pin, and the small pin down onto that
    L.track('LINE_S', 'F.Cu', w, (4.92, 70.5), (15.08, 70.5))
    L.track('LINE_S', 'F.Cu', w, J3_PIN, (12.54, 70.5))
    # on to C26, the shell's capacitor to ground across the band
    L.track('LINE_S', 'F.Cu', w, J3_SHELL_RIGHT, (15.08, 68.9), (19.025, 64.955), 'C26.1')
    _drive(L)
    _receive(L)


DRIVE = 0.25        # the drive's tracks: room for 0.15 mm beside the resistors' pads and U4's pins


def _drive(L):
    """U4's two drivers into T1's TX winding. Channel A (pins 2, 3; the 150 R by the driver) and channel B (pins 5,
    6; the 33 R by T1) alternate N, P, P, N along U4's pins, so pins 3 and 6 cross the others on B.Cu: each drops
    to a via beside its pin and comes up right above its resistor's pad 1 (R11's, and R14's between R12 and R14).
    TX_N joins its two resistors round the left of R14 and TX_P round the right of R14, through the middle; both
    run on through R15 and out to T1's pins 4 and 3, mirrored about x = 10. U5 (not fitted) hangs off TX_P beside
    it and off TX_N by a B.Cu branch, as gate 2 accepted."""
    w = DRIVE
    (a_p, a_n, b_n, b_p) = (L.net('U4.2'), L.net('U4.3'), L.net('U4.5'), L.net('U4.6'))
    # channel A: pin 2 (OUT+) to R12, pin 3 (OUT-) across to R11
    L.track(a_p, 'F.Cu', w, 'U4.2', (6.825, 43.6), (7.6, 44.375), 'R12.1')
    L.track(a_n, 'F.Cu', w, 'U4.3', (8.095, 41.8), (7.5, 42.395))
    L.track(a_n, 'B.Cu', w, (7.5, 42.395), (8.5, 43.395), (11.0, 43.395))
    L.track(a_n, 'F.Cu', w, (11.0, 43.395), 'R11.1')
    # channel B: pin 5 (OUT-) down the right of R11 to R13, pin 6 (OUT+) across to R14
    L.track(b_n, 'F.Cu', w, 'U4.5', (10.635, 41.65), (11.75, 42.765), (11.75, 46.955), 'R13.1')
    L.track(b_p, 'F.Cu', w, 'U4.6', (11.905, 41.8), (12.5, 42.395))
    L.track(b_p, 'B.Cu', w, (12.5, 42.395), (12.5, 44.0), (9.575, 46.925), (9.12, 46.925))
    L.track(b_p, 'F.Cu', w, (9.12, 46.925), 'R14.1')
    for (net, at, size) in ((a_n, (7.5, 42.395), 0.6), (a_n, (11.0, 43.395), 0.45), (b_p, (12.5, 42.395), 0.6),
                            (b_p, (9.12, 46.925), 0.45)):
        L.via(net, at, size=size, drill=0.3 if size > 0.5 else 0.2)
    # the sums: TX_N round the left of R14, TX_P down between R14 and R13; then R15 and out to T1
    L.track('TX_N', 'F.Cu', w, 'R12.2', (8.2, 46.025), (8.2, 49.475), 'R14.2')
    L.track('TX_P', 'F.Cu', w, 'R11.2', (10.0, 46.025), (10.0, 49.475), 'R13.2')
    L.track('TX_N', 'F.Cu', w, 'R14.2', 'R15.2', (7.4, 51.15), (4.6, 53.95), 'T1.4')
    L.track('TX_P', 'F.Cu', w, 'R13.2', 'R15.1', (12.6, 51.15), (15.4, 53.95), 'T1.3')
    # U5's TX pins: TX_P's beside it, TX_N's by B.Cu under TX_P
    L.track('TX_P', 'F.Cu', w, (12.6, 51.15), (13.7, 50.05), 'U5.1')
    L.track('TX_N', 'F.Cu', w, 'R15.2', (9.175, 52.3))
    L.track('TX_N', 'B.Cu', w, (9.175, 52.3), (18.0, 52.3))
    L.track('TX_N', 'F.Cu', w, (18.0, 52.3), (18.35, 51.95), 'U5.3')
    for at in ((9.175, 52.3), (18.0, 52.3)):
        L.via('TX_N', at)


def _receive(L):
    """T1's RX winding to U3's pins 6 and 7. RX_N leaves T1's left column under its body, between the TX and RX rows,
    and comes up the right of U5, far enough out for U5's +3V3 pin to have a via; RX_P leaves T1's right column,
    crosses under RX_N on B.Cu and comes up through U5's middle, so that each passes its own U5 pin (not fitted) and
    they reach U3 in its order."""
    w = 0.2
    L.track('RX_N', 'F.Cu', w, 'T1.5', (5.4, 57.0), (6.67, 55.73), (21.75, 55.73), (21.75, 54.15), (23.05, 52.85),
            (23.05, 44.0), (23.875, 43.175), 'U3.7')
    L.track('RX_N', 'F.Cu', w, (23.05, 50.05), 'U5.6')
    L.track('RX_P', 'F.Cu', w, 'T1.2', (20.3, 57.0))
    L.track('RX_P', 'B.Cu', w, (20.3, 57.0), (20.3, 54.8))
    L.track('RX_P', 'F.Cu', w, (20.3, 54.8), (20.3, 45.0), (22.605, 42.695), 'U3.6')
    L.track('RX_P', 'F.Cu', w, (20.3, 51.95), 'U5.4')
    for at in ((20.3, 57.0), (20.3, 54.8)):
        L.via('RX_P', at)
