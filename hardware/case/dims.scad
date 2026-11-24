// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: CERN-OHL-P-2.0

// The case's constants and outlines (docs/superpowers/specs/2026-10-14-case-design.md). Lengths in mm, in the
// frame of the board's STL export: x to the right, y up (the board's y negated), z up from the board's underside.
// Included by each part's file, never twice in one scope.

include <../board/export/liz4270-board.scad>

// From the board's 3D model (kicad-cli pcb export stl, Oct 14, 2026)
BOARD_T = 1.6;                  // the stackup
TALLEST_Z = 17.55;              // the USB-A stack's top
LED_TOP_Z = 2.70;               // D1 and D5, 0603
ACTUATOR_Z = 5.1;               // BOOTSEL's and RESET's actuators' centres
ACTUATOR_TIP_Y = -79.9;         // and their tips
FRONT_SW = 2.25;                // a button's actuator is this far left of its footprint's origin (test_layout.FRONT)
FRONT_J5 = 3.5;                 // the USB-A stack's centre is this far right of its origin

// The case
WALL = 3.0;                     // walls, floor and top
GAP = 0.5;                      // round the board
STANDOFF = 5.0;                 // the board's underside above the floor
AIR = 2.0;                      // over the tallest part
SEAM = 0.3;                     // the base's rim stops this far below the board's top face
LIP_H = 2.0;                    // the base's lip, which rises into the lid's rebate
LIP_T = 1.3;
LIP_FIT = 0.2;                  // the rebate is this much wider than the lip
CORNER_R = 2.0;                 // the outside's vertical edges
CLEAR = 0.5;                    // round each plug body in its opening

Z_FLOOR = -STANDOFF - WALL;             // -8.0, the floor's underside
Z_RIM = BOARD_T - SEAM;                 // 1.3, the top of the base's rim
Z_SEAM = BOARD_T;                       // 1.6, the lid's lower edge, on the board's top face
Z_INNER = TALLEST_Z + AIR;              // 19.55, the top's inner face
Z_TOP = Z_INNER + WALL;                 // 22.55
Z_REBATE = Z_RIM + LIP_H + SEAM;        // 3.6, the rebate's top, SEAM above the lip's

X0 = -GAP - WALL;                       // -3.5
X1 = BOARD_W + GAP + WALL;              // 103.5
Y0 = -BOARD_H - GAP - WALL;             // -83.5, the back face
Y1 = GAP + WALL;                        // 3.5, the front face
BACK_IN = -BOARD_H - GAP;               // -80.5, the back wall's inner face
FRONT_IN = GAP;                         // 0.5, the front wall's

// The screws: 3 mm self-tapping for plastic, pan head, 16 mm (ISO 7049 ST2.9 x 16)
BOSS_D = 8.0;                   // the lid's bosses and the base's standoffs
PILOT_D = 2.5;                  // for self-tapping; 4.0 takes a 5.7 mm M3 heat-set insert
PILOT_DEPTH = 10.0;
SCREW_D = 3.4;                  // through the standoff
HEAD_D = 6.2;                   // the counterbore
HEAD_DEPTH = 2.6;

// The plugs' bodies, out from the mouths at y = -BOARD_H: [x, z of the centre, width, height]
USBC_PLUG = [J6[0], 3.23, 12.35, 6.5];                  // USB-C's maximum overmould
USBA_PLUG = [J5[0] + FRONT_J5, 9.25, 20.0, 18.5];       // both plugs, z 0.0 to 18.5
HDMI_PLUG = [J4[0], 5.0, 22.0, 12.0];
PLUGS = [USBC_PLUG, USBA_PLUG, HDMI_PLUG];
PLUG_OUT = 30.0;                // how far out a plug's keep-out reaches
// The BNC: its barrel with the bayonet studs, and the plug's coupling ring
BNC_X = J3[0];
BNC_Z = 8.29;                   // the barrel's axis
BNC_W = 11.2;                   // across the studs
BNC_BOTTOM = 2.35;
BNC_TOP = 14.23;
BNC_TIP_Y = -100.78;
BNC_RING_D = 15.0;
BNC_RING_L = 12.0;              // the ring reaches this far back from the barrel's tip

// RESET's flexure and BOOTSEL's pinhole, in the back wall
BOOT_X = SW1[0] - FRONT_SW;     // 85.0
RESET_X = SW2[0] - FRONT_SW;    // 94.6
WELL_DEPTH = 1.8;               // the guard, leaving a 1.2 mm tongue
WELL_W = 8.8;
WELL_TOP_Z = 17.2;
TONGUE_W = 6.4;
TONGUE_TOP_Z = 16.6;            // its hinge
SLIT = 0.6;
NUB = 2.6;                      // square, centred on the actuator
NUB_GAP = 0.3;                  // short of the actuator's tip
PIN_D = 1.6;
PIN_SINK_D = 4.0;               // the countersink, 90 degrees

// The light pipes
PIPES = [D5, D1];               // power, heartbeat
PIPE_D = 3.0;
PIPE_HOLE = 3.2;                // tune for the press fit
COLLAR_D = 5.0;
COLLAR_H = 1.0;
COLLAR_HOLE = 5.3;
PIPE_FOOT_Z = LED_TOP_Z + 0.5;
SLEEVE_D = 5.0;
SLEEVE_FOOT_Z = LED_TOP_Z + 1.0;

// The speaker: the Adafruit 3923, an oval 30 x 20 x 4.8 (its datasheet; check against a real one)
SPK = [74.0, -14.0];
SPK_L = 30.0;
SPK_W = 20.0;
SPK_H = 4.8;
SPK_FIT = 0.3;
SPK_WALL = 1.5;
TAB_W = 6.0;                    // a snap tab, in the middle of each long side
TAB_THICK = 0.9;                // thinner than the wall, so the tab bends without cracking across its layers
TAB_FIT = 0.1;                  // from the speaker's side to the tab: closer than SPK_FIT, so the hooks reach over
TAB_HOOK = 0.4;                 // how far a tab's hook reaches in, over the frame's back
TAB_RAMP = 0.8;                 // the hook's lead-in, below its catch
TAB_CLEAR = 0.15;               // from the speaker's back down to the hook's catch
GRILLE_D = 2.0;
GRILLE_PITCH = 3.0;
GRILLE_INSET = 3.0;             // inside the speaker's outline

// The Debug Probe's notch (debug_probe_hole), in the front wall
PROBE_X = J1[0];
PROBE_W = 5.0;
PROBE_H = 3.0;

// Curves: every part draws them the same, so the inlay fills its pocket exactly
FA = 4;
FS = 0.25;

// Text, in 3270font (tools/sim/fonts/, OFL-1.1)
FONT = "IBM 3270:style=Regular";
CAP = 0.7603;                   // its cap height per unit of size
BOLD = 0.15;                    // each stroke grows this much a side: the font's strokes are 0.085 of its size
DEBOSS = 0.6;
LABEL_CAP = 2.5;
LABEL_Z = -4.25;                // the labels' middle, on the base's back face
LABEL_NUDGE = [["BOOT", -2.75]];        // clear of RESET
LABEL_GAP = 1.5;                // the least between two labels
NAME = "Liz4270";
NAME_CAP = 8.0;
NAME_AT = [31.0, -10.0];
LED_CAP = 3.0;
LED_LABELS = [["PWR", D5], ["RUN", D1]];
LED_LABEL_BACK = 5.0;           // behind its pipe, away from the front

// Feet: stick-on rubber bumpers, about 10 mm across, clear of the screw heads
FOOT_D = 10.5;
FOOT_DEPTH = 0.5;
FEET = [[14.0, -2.75], [86.0, -2.75], [2.75, -77.25], [96.75, -77.25]];

// A rounded rectangle from (x0, y0) to (x1, y1)
module rrect(x0, y0, x1, y1, r) translate([x0 + r, y0 + r]) offset(r = r) square([x1 - x0 - 2 * r, y1 - y0 - 2 * r]);

// The case's outside
module outline_outer() rrect(X0, Y0, X1, Y1, CORNER_R);

// The walls' inner faces, grown by grow
module outline_inner(grow = 0) rrect(-GAP - grow, -BOARD_H - GAP - grow, BOARD_W + GAP + grow, GAP + grow,
                                     BOARD_CORNER + GAP + grow);

// An oval l long (along x) and w wide, centred on the origin
module stadium(l, w) hull() for (s = [-1, 1]) translate([s * (l - w) / 2, 0]) circle(d = w);
