// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: CERN-OHL-P-2.0

// Written by tools/board/make_exports.py from hardware/board/liz4270.kicad_pcb: don't edit.
// The frame of `kicad-cli pcb export stl --drill-origin`: x to the right and y up (the board's y
// negated), in mm from the outline's top-left corner.

BOARD_W = 100.0;
BOARD_H = 80.0;
BOARD_CORNER = 1.0;

H1 = [4.0, -4.0];
H2 = [96.0, -4.0];
H3 = [96.0, -66.0];
H4 = [4.0, -46.0];
HOLES = [H1, H2, H3, H4];

D1 = [32.0, -24.3];
D5 = [29.25, -46.5];
J1 = [32.4, -19.0];
J3 = [10.0, -67.3];
J4 = [71.0, -72.97];
J5 = [46.0, -64.39];
J6 = [30.0, -76.35];
J7 = [92.0, -12.0];
SW1 = [87.25, -76.15];
SW2 = [96.85, -76.15];

LABELS = [["COAX", 10.0], ["USB-C 5V", 30.0], ["USB", 49.5], ["HDMI", 71.0], ["BOOT", 85.0], ["RESET", 94.6]];
