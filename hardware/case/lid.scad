// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: CERN-OHL-P-2.0

// The lid: the walls and top over the board, with every opening, RESET's flexure, BOOTSEL's pinhole, the light
// pipes' sleeves, the speaker's pocket and the bosses the screws bite into; and the inlay and the light pipes.
// Built where they sit.

include <dims.scad>
use <cutters.scad>
use <labels.scad>

module lid(debug_probe_hole = false) {
    $fa = FA;
    $fs = FS;
    assert((BOSS_D - 4.0) / 2 >= 1.9, "a boss is too thin to take an M3 heat-set insert later");
    difference() {
        union() {
            difference() {
                translate([0, 0, Z_SEAM]) linear_extrude(Z_TOP - Z_SEAM) outline_outer();
                translate([0, 0, Z_SEAM - 1]) linear_extrude(Z_INNER - Z_SEAM + 1) outline_inner();
                translate([0, 0, Z_SEAM - 1]) linear_extrude(Z_REBATE - Z_SEAM + 1) outline_inner(LIP_T + LIP_FIT);
            }
            for (h = HOLES) translate([h[0], h[1], Z_SEAM]) cylinder(d = BOSS_D, h = Z_INNER - Z_SEAM + 0.01);
            for (p = PIPES) translate([p[0], p[1], SLEEVE_FOOT_Z])
                cylinder(d = SLEEVE_D, h = Z_INNER - SLEEVE_FOOT_Z + 0.01);
            speaker_pocket();
            reset_nub();
        }
        for (h = HOLES) translate([h[0], h[1], Z_SEAM - 1]) cylinder(d = PILOT_D, h = PILOT_DEPTH + 1);
        for (p = PIPES) translate([p[0], p[1], 0]) {
            translate([0, 0, SLEEVE_FOOT_Z - 1]) cylinder(d = PIPE_HOLE, h = Z_TOP - SLEEVE_FOOT_Z + 2);
            translate([0, 0, Z_TOP - COLLAR_H]) cylinder(d = COLLAR_HOLE, h = COLLAR_H + 1);
        }
        grille();
        back_openings();
        if (debug_probe_hole) probe_notch();
        reset_cut();
        bootsel_pinhole();
        translate([0, 0, Z_TOP - DEBOSS]) linear_extrude(DEBOSS + 1) top_text();
    }
}

// The name and the LEDs' labels, which fill the lid's text in a second colour
module inlay() translate([0, 0, Z_TOP - DEBOSS]) linear_extrude(DEBOSS) top_text();

// One light pipe, standing on its collar as it prints
module light_pipe() {
    $fa = FA;
    $fs = FS;
    cylinder(d = COLLAR_D, h = COLLAR_H);
    cylinder(d = PIPE_D, h = Z_TOP - PIPE_FOOT_Z);
}

module light_pipes_in_place() for (p = PIPES) translate([p[0], p[1], Z_TOP]) mirror([0, 0, 1]) light_pipe();

// The speaker's pocket: a wall round its frame, with a snap tab in the middle of each long side. Each tab hangs
// from the top's inner face, slit either side and TAB_THICK thick, and hooks under the frame's back.
module speaker_pocket() {
    catch = Z_INNER - SPK_H - TAB_CLEAR;
    bottom = catch - TAB_RAMP;
    translate([SPK[0], SPK[1], 0]) {
        difference() {
            translate([0, 0, bottom]) linear_extrude(Z_INNER - bottom + 0.01) difference() {
                offset(r = SPK_FIT + SPK_WALL) stadium(SPK_L, SPK_W);
                offset(r = SPK_FIT) stadium(SPK_L, SPK_W);
            }
            for (m = [0, 1]) mirror([0, m, 0]) translate([-TAB_W / 2 - SLIT, SPK_W / 2, bottom - 1])
                cube([TAB_W + 2 * SLIT, SPK_FIT + SPK_WALL + 1, Z_INNER - bottom + 1]);
        }
        for (m = [0, 1]) mirror([0, m, 0]) {
            translate([-TAB_W / 2, SPK_W / 2 + TAB_FIT, bottom]) cube([TAB_W, TAB_THICK, Z_INNER - bottom + 0.01]);
            hull() {
                translate([-TAB_W / 2, SPK_W / 2 + TAB_FIT - TAB_HOOK, catch - 0.01]) cube([TAB_W, TAB_HOOK + 0.01, 0.01]);
                translate([-TAB_W / 2, SPK_W / 2 + TAB_FIT, bottom]) cube([TAB_W, 0.01, 0.01]);
            }
        }
    }
}

// A field of whole holes over the speaker's cone, GRILLE_INSET inside its outline
function in_stadium(p, l, w) = norm([max(abs(p[0]) - (l - w) / 2, 0), p[1]]) <= w / 2;

module grille() translate([SPK[0], SPK[1], Z_INNER - 1]) linear_extrude(WALL + 2)
    for (i = [-8:8], j = [-5:5])
        let (p = [i * GRILLE_PITCH + (abs(j) % 2) * GRILLE_PITCH / 2, j * GRILLE_PITCH * sqrt(3) / 2],
             inset = 2 * (GRILLE_INSET + GRILLE_D / 2))
            if (in_stadium(p, SPK_L - inset, SPK_W - inset)) translate(p) circle(d = GRILLE_D);

// RESET: a well in the back face, its guard, and a tongue cut free on three sides, hinged at its top
module reset_cut() {
    translate([RESET_X - WELL_W / 2, Y0 - 1, Z_RIM]) cube([WELL_W, 1 + WELL_DEPTH, WELL_TOP_Z - Z_RIM]);
    for (s = [-1, 1]) translate([RESET_X + s * (TONGUE_W + SLIT) / 2 - SLIT / 2, Y0 - 1, Z_RIM])
        cube([SLIT, WALL + 2, TONGUE_TOP_Z - Z_RIM]);
}

// The tongue's nub, NUB_GAP short of RESET's actuator
module reset_nub() translate([RESET_X - NUB / 2, BACK_IN - 0.1, ACTUATOR_Z - NUB / 2])
    cube([NUB, ACTUATOR_TIP_Y - NUB_GAP - (BACK_IN - 0.1), NUB]);

// BOOTSEL: a pinhole through the back wall, countersunk on the outside for a paper clip
module bootsel_pinhole() translate([BOOT_X, 0, ACTUATOR_Z]) rotate([90, 0, 0]) {
    translate([0, 0, -BACK_IN - 0.5]) cylinder(d = PIN_D, h = WALL + 1.5, $fn = 24);
    translate([0, 0, -Y0 - (PIN_SINK_D - PIN_D) / 2]) cylinder(d1 = PIN_D, d2 = PIN_SINK_D + 0.02,
                                                               h = (PIN_SINK_D - PIN_D) / 2 + 0.01, $fn = 24);
}
