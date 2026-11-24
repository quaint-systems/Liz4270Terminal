// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: CERN-OHL-P-2.0

// The Liz4270 case (#134). One part at a time, as it prints:
//     openscad -o lid.stl --export-format binstl -D 'part="lid"' case.scad
// or every STL with tools/case/make_case.py. part = "assembly" shows it all in place, with the board's model if
// tools/board/make_exports.py has written it.

include <dims.scad>
use <base.scad>
use <lid.scad>

part = "assembly";              // [assembly, base, lid, inlay, light_pipe]
debug_probe_hole = false;       // a notch in the front wall for the Debug Probe's SWD cable

// Each part as it lies on the print bed: the base on its floor, the lid and its inlay upside down
if (part == "base") translate([0, 0, -Z_FLOOR]) base(debug_probe_hole);
else if (part == "lid") translate([0, 0, Z_TOP]) rotate([180, 0, 0]) lid(debug_probe_hole);
else if (part == "inlay") translate([0, 0, Z_TOP]) rotate([180, 0, 0]) inlay();
else if (part == "light_pipe") light_pipe();
else if (part == "assembly") {
    base(debug_probe_hole);
    lid(debug_probe_hole);
    inlay();
    light_pipes_in_place();
    %import("../board/export/liz4270.stl");
}
else assert(false, str("no part called ", part));
