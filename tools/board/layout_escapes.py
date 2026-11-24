# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Pins Freerouting can't get out of: each takes a via of its own beside it (pcb.Layout.fanout), and Freerouting
joins the vias. Its power classes route 0.5 mm wide, which no 0.4 or 0.5 mm pitch pin lets out, and U1's corners
are crowded besides (U14's sides are scripted by hand, in layout_audio). Runs after every block's copper, so that
each via keeps clear of all of it, and before layout_planes' fan-out to the planes. Each run of Freerouting may find
another way out for a pin, so L.escapes lists them, and pcb_build drops the ones its routes don't meet."""

import layout_planes

# (net, its pads, whether to try under the part first)
ESCAPES = [
    ('I2C_SDA', {('U1', '20')}, False),             # U1's top right corner, above HSTX's D2 pair
    ('QSPI_SS', {('U1', '75')}, True),              # inside the pad ring, as Task 6 had it: to U2's far row by B.Cu
    ('QSPI_SD0', {('U1', '72')}, True),             # likewise, after a run that left it unrouted
    ('RUN', {('U1', '35')}, True),                  # inside the pad ring, as Task 6 had it
    ('COAX_RX', {('U1', '52')}, False),             # U1's coax side, behind its decoupling, after a run left it
    # the pocket under HSTX's clock pair, and the flash's side of U1: the pins Freerouting left there
    ('USBH_FAULT', {('U1', '3')}, True),
    ('HPD_SENSE', {('U1', '4')}, True),
    ('UART_TX', {('U1', '6')}, True),
    ('UART_RX', {('U1', '7')}, True),
    ('+3V3', {('U1', '69')}, True),                 # boxed in by the console USB and the QSPI pins
    ('Net-(D2-K)', {('U8', '21')}, False),          # the hub's LED pin, between its supply pins
]


def route(L):
    for (net, pads, inward) in ESCAPES:
        (tracks, vias) = (len(L.tracks), len(L.vias))
        L.fanout(net, hole=layout_planes.hole, only=pads, inward=inward)
        L.escapes += zip(L.vias[vias:], L.tracks[tracks:])      # fanout lays each pad's stub, then its via
