// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: CERN-OHL-P-2.0

// The case's text: the connector labels on the base's back face, and the name with the LEDs' labels on the lid's top.

include <dims.scad>
use <../../tools/sim/fonts/3270-Regular.ttf>

function size_for(cap) = cap / CAP;
function nudge(t) = let (m = [for (n = LABEL_NUDGE) if (n[0] == t) n[1]]) len(m) ? m[0] : 0;
function label_x(l) = l[1] + nudge(l[0]);
function advance(cap) = textmetrics("W", size = size_for(cap), font = FONT).advance.x;

// The words of t, each as [its first character's index, the word]. The repo's subset of 3270font has no space, and
// the font is monospaced, so word() draws each word by itself at its character's place.
function word_from(t, i) = (i >= len(t) || t[i] == " ") ? "" : str(t[i], word_from(t, i + 1));
function words(t) = [for (i = [0:len(t) - 1]) if (t[i] != " " && (i == 0 || t[i - 1] == " ")) [i, word_from(t, i)]];

// The left and right edges of t's ink, as word() draws it about the origin
function ink(t, cap) =
    let (a = advance(cap), ws = words(t), first = ws[0], last = ws[len(ws) - 1], x0 = -len(t) * a / 2,
         m0 = textmetrics(first[1], size = size_for(cap), font = FONT),
         m1 = textmetrics(last[1], size = size_for(cap), font = FONT))
    [x0 + first[0] * a + m0.position.x - BOLD, x0 + last[0] * a + m1.position.x + m1.size.x + BOLD];

// Without the font, OpenSCAD draws in another one and says nothing.
function font_loaded() =
    textmetrics("IIII", size = 10, font = FONT).advance.x == textmetrics("WWWW", size = 10, font = FONT).advance.x
    && abs(textmetrics("H", size = 10, font = FONT).size.y - 10 * CAP) < 0.01;
// A character the font lacks is drawn as its missing-glyph box: U+10FFFD is in no 3270font, so it draws that box.
function has_glyph(c) = textmetrics(c, size = 10, font = FONT).size != textmetrics(chr(1114109), size = 10, font = FONT).size;
function all_drawn(texts) = len([for (t = texts) for (w = words(t)) for (c = w[1]) if (!has_glyph(c)) 1]) == 0;
// The connector labels fit the flat of the back face, LABEL_GAP apart.
function labels_fit() =
    let (left = [for (l = LABELS) label_x(l) + ink(l[0], LABEL_CAP)[0]],
         right = [for (l = LABELS) label_x(l) + ink(l[0], LABEL_CAP)[1]])
    left[0] >= X0 + CORNER_R && right[len(LABELS) - 1] <= X1 - CORNER_R
    && min([for (i = [1:len(LABELS) - 1]) left[i] - right[i - 1]]) >= LABEL_GAP;

// A label, its advance centred on the origin and its capitals' middle on the x axis, word by word on one baseline,
// its strokes thickened so they print
module word(t, cap) {
    $fa = FA;
    $fs = FS;
    a = advance(cap);
    offset(delta = BOLD) for (w = words(t))
        translate([(w[0] - len(t) / 2) * a, -cap / 2]) text(w[1], size = size_for(cap), font = FONT);
}

// The connector labels, cut DEBOSS into the base's back face, read from behind
module back_labels() {
    assert(font_loaded(), "3270font didn't load: tools/sim/fonts/3270-Regular.ttf");
    assert(labels_fit(), "the connector labels run off the back face, or come closer than LABEL_GAP");
    assert(all_drawn([for (l = LABELS) l[0]]), "a connector label has a character 3270font's subset lacks");
    for (l = LABELS) translate([label_x(l), Y0 + DEBOSS, LABEL_Z]) rotate([90, 0, 0])
        linear_extrude(DEBOSS + 1) word(l[0], LABEL_CAP);
}

// The lid's top text in 2D, in place, read from the front: the name, and each LED's label behind its pipe
module top_text() {
    assert(font_loaded(), "3270font didn't load: tools/sim/fonts/3270-Regular.ttf");
    assert(all_drawn(concat([NAME], [for (l = LED_LABELS) l[0]])), "the lid's text has a character 3270font's subset lacks");
    translate(NAME_AT) rotate(180) word(NAME, NAME_CAP);
    for (l = LED_LABELS) translate([l[1][0], l[1][1] - LED_LABEL_BACK]) rotate(180) word(l[0], LED_CAP);
}
