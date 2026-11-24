# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The connector edge, the mounting holes and the silkscreen (spec, "The board and its edge"; plan 2's floorplan).

Every external connector sits on the bottom edge, y = layout.HEIGHT, left to right: BNC, USB-C, stacked USB-A,
HDMI, then BOOTSEL and RESET. Each is placed so that its front lies on the edge: the mouth, the BNC's panel line,
the HDMI footprint's PCB Edge line, a button's actuator tip. The spacing allows for plug bodies: HDMI and USB-A
overmoulds run about 20 mm wide, and the BNC's bayonet needs a finger's room. BOOTSEL, behind a pinhole, needs no
finger, so it sits beside the HDMI plug and RESET takes the corner, where a fingertip and the case's guard have room
(gate 2)."""

# ref -> (x, y, rotation)
EDGE = {
    'J3': (10.0, 67.3, 180),        # BNC: its panel line (footprint y -12.7) on the edge, the barrel out
    'J6': (30.0, 76.35, 0),         # USB-C: mouth (footprint y 3.65) on the edge
    'J5': (46.0, 64.39, 0),         # stacked USB-A: mouth (footprint y 15.61) on the edge; body centred at x 49.5
    'J4': (71.0, 72.97, 270),       # HDMI: KiCad's PCB Edge line (footprint x 7.03) on the edge
    'SW1': (87.25, 76.15, 180),     # BOOTSEL: actuator tip (footprint y -3.85) on the edge, centred at x 85; the case
                                    # puts a pinhole in front
    'SW2': (96.85, 76.15, 180),     # RESET: the same, centred at x 94.6
}
# M3 at the corners. The BNC takes the bottom-left one, so H4 moves up, clear of the coax line side: unplated and
# outside the isolation gap, nearest the BNC. H3 stays low, above RESET, to back the edge where the HDMI plug and
# RESET push (gate 2).
HOLES = {'H1': (4.0, 4.0), 'H2': (96.0, 4.0), 'H3': (96.0, 66.0), 'H4': (4.0, 46.0)}
# connector labels on the back, behind each body: (text, x)
LABELS = [('COAX', 10.0), ('USB-C 5V', 30.0), ('USB', 49.5), ('HDMI', 71.0), ('BOOT', 85.0), ('RESET', 94.6)]


# ref -> (dx, dy, rotation): designators moved off their footprints' spots, clear of the other silkscreen
DESIGNATORS = {'J3': (0.0, 8.7, 0),            # on the BNC's body, off T1's
               'J5': (3.5, 8.1, 0),            # on the USB-A's body, off U9's pads
               'J6': (0.0, 0.55, 0)}           # on the USB-C's body, off U11's pads

def place(L):
    for (ref, (x, y, rot)) in EDGE.items():
        L.place(ref, x, y, rot)
    for (ref, at) in DESIGNATORS.items():
        L.label(ref, *at)
    for (ref, (x, y)) in HOLES.items():
        L.place(ref, x, y)
    L.text('Liz4270 rev A', 50.0, 3.0, size=1.5)
    L.text('BOOT', 85.0, 70.5, size=0.8)         # the buttons' names on top too: the back's aren't seen
    L.text('RESET', 94.6, 70.5, size=0.8)        # on the bench (gate-2 review, finding 8)
    for (i, line) in enumerate(('Liz4270 rev A', '© 2026 CoffeeMuse', 'CERN-OHL-P-2.0')):
        L.text(line, 50.0, 6.0 + 2.0 * i, layer='B.SilkS')
    L.text('JLCJLCJLCJLC', 50.0, 13.0, layer='B.SilkS', size=0.8)    # where JLC prints its order number
    for (text, x) in LABELS:
        L.text(text, x, 61.0, layer='B.SilkS')
