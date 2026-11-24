# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The board's layout (plan 2, docs/superpowers/plans/2026-10-09-unified-board-layout.md): the outline, then each
block's places and scripted copper from its layout_*.py. Python 3.9: pcb_build.py imports it in KiCad's Python.

Every block's place() runs first, in BLOCKS' order, so that any block's route() may name any part's pads."""

import layout_audio
import layout_coax
import layout_edge
import layout_escapes
import layout_mcu
import layout_planes
import layout_power
import layout_usb_host
import layout_video
import pcb

WIDTH = 100.0
HEIGHT = 80.0
CORNER = 1.0
# the layout_*.py modules; each task appends its own
BLOCKS = [layout_edge, layout_mcu, layout_coax, layout_video, layout_usb_host, layout_power, layout_audio,
          layout_escapes, layout_planes]


def layout(parts, pins=None):
    """The layout, given {ref: footprint id} and {(ref, pad): net} from the netlist."""
    L = pcb.Layout(parts, WIDTH, HEIGHT, CORNER, pins)
    for block in BLOCKS:
        if hasattr(block, 'place'):
            block.place(L)
    for block in BLOCKS:
        if hasattr(block, 'route'):
            block.route(L)
    return L
