// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: CERN-OHL-P-2.0

// What the base and the lid both cut away, and the plugs' bodies the tests keep them clear of.

include <dims.scad>

// A slot through the back wall, from bottom to top. One that reaches below the base's rim notches the base too;
// the rest start just above it, below the lid's lower edge, so the lid's slot is open there.
module slot(x, w, bottom, top) {
    b = bottom < Z_RIM ? bottom : Z_RIM + 0.01;
    translate([x - w / 2, Y0 - 1, b]) cube([w, -BOARD_H - (Y0 - 1), top - b]);
}

// Each plug's opening: its body with CLEAR round it. USB-A's and HDMI's overlap, so they make one.
module back_openings() {
    for (p = PLUGS) slot(p[0], p[2] + 2 * CLEAR, p[1] - p[3] / 2 - CLEAR, p[1] + p[3] / 2 + CLEAR);
    slot(BNC_X, BNC_W + 2 * CLEAR, BNC_BOTTOM - CLEAR, BNC_TOP + CLEAR);
}

// The Debug Probe's notch in the front wall, from the base's rim up PROBE_H past the lid's lower edge
module probe_notch() translate([PROBE_X - PROBE_W / 2, FRONT_IN - 0.5, Z_RIM + 0.01])
    cube([PROBE_W, Y1 + 1 - (FRONT_IN - 0.5), Z_SEAM + PROBE_H - (Z_RIM + 0.01)]);

// The plugs' bodies, out from their mouths, and the BNC plug's coupling ring: nothing of the case may touch them
module plug_keepouts() {
    for (p = PLUGS) translate([p[0] - p[2] / 2, -BOARD_H - PLUG_OUT, p[1] - p[3] / 2]) cube([p[2], PLUG_OUT, p[3]]);
    translate([BNC_X, BNC_TIP_Y, BNC_Z]) rotate([-90, 0, 0]) cylinder(d = BNC_RING_D, h = BNC_RING_L, $fn = 64);
}
