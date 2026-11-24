// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: CERN-OHL-P-2.0

// The base: the floor, the standoffs the board sits on, and the rim and lip round it. Built where it sits.

include <dims.scad>
use <cutters.scad>
use <labels.scad>

module base(debug_probe_hole = false) {
    $fa = FA;
    $fs = FS;
    difference() {
        union() {
            difference() {
                translate([0, 0, Z_FLOOR]) linear_extrude(Z_RIM - Z_FLOOR) outline_outer();
                translate([0, 0, Z_FLOOR + WALL]) linear_extrude(Z_RIM - Z_FLOOR) outline_inner();
            }
            translate([0, 0, Z_RIM - 0.01]) linear_extrude(LIP_H + 0.01) difference() {
                outline_inner(LIP_T);
                outline_inner();
            }
            for (h = HOLES) translate([h[0], h[1], Z_FLOOR + WALL - 0.01]) cylinder(d = BOSS_D, h = STANDOFF + 0.01);
        }
        for (h = HOLES) translate([h[0], h[1], Z_FLOOR - 1]) {
            cylinder(d = SCREW_D, h = -Z_FLOOR + 2);
            cylinder(d = HEAD_D, h = HEAD_DEPTH + 1);
        }
        back_openings();
        if (debug_probe_hole) probe_notch();
        back_labels();
        for (f = FEET) translate([f[0], f[1], Z_FLOOR - 1]) cylinder(d = FOOT_D, h = FOOT_DEPTH + 1);
    }
}
