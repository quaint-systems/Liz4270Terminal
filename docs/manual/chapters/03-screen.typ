// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: CC-BY-4.0

#import "../style.typ": *
#import "../keymap-rows.typ": keymaps, keys-for

#let km = keymaps.first()

= The screen <screen>

This chapter is about what the display station shows: the host's screen, at one of three sizes, the status
line under it, the cursor and the rule line, colour and monochrome, and auto dim, which blanks the screen
while nobody is using it. Every screen in it was drawn by the display station's own firmware.

== When you switch on

For a few seconds after it is switched on, the display station shows its own screen, the splash
screen#ix[splash screen] (@fig-splash), with the version of its firmware#ix[firmware version]. It stays at
least 3 seconds, and then until the controller first writes to the screen.

#figure(placement: auto, screen-image("splash"), caption: [The display station switched on]) <fig-splash>

== The parts of the screen

Most of the screen is the host's: what the host's program writes, and the fields#ix[field] you type into
(@fig-dslist). Under it is a blue rule, and under that the status line#ix[status line], which says what the
controller and the display station are doing (@status-line).

#figure(placement: auto, screen-image("dslist"), caption: [A host’s screen: a list of data sets])
<fig-dslist>

== Screen sizes <screen-sizes>

The display station can be a Model 2#ix[Model 2], with 24 rows of 80 columns for the host, a
Model 3#ix[Model 3], with 32 rows, or a Model 4#ix[Model 4], with 43 (@fig-model3 and @fig-model4). The
picture stays the same size: the rows get shorter to fit, and the status line keeps to the foot of the screen.
The host sees the size#ix[screen size], and a program that knows how can fill the extra rows.

You choose the size in offline setup#ix[offline setup] (@customization). SetUp and the splash screen keep Model
2’s layout whatever the size.

#figure(placement: auto, screen-image("model3"), caption: [A Model 3: 32 rows]) <fig-model3>

#figure(placement: auto, screen-image("model4"), caption: [A Model 4: 43 rows]) <fig-model4>

== The status line <status-line>

The controller writes most of the status line, which IBM calls the operator information area, or
OIA#ix[OIA]. The display station draws its right end itself: the cursor's
row and column, and the mark auto dim leaves. While it is locked, the lock takes the whole status line, with
its own symbols at the left (@locking).

@tab-status gives the symbols#ix("status line", sub: "symbols") oec writes#ix("oec", sub: "status line"). A
3174#ix[3174] writes IBM's own, which its documentation describes; the
display station's own at the right end are the same under either.

#figure(kind: table, caption: [The status line under oec],
  table(columns: (1.5in, 1fr),
    table.header(table.hline(stroke: 0.5pt), [Symbol], [What it means], table.hline(stroke: 0.5pt)),
    cells-image("status-oec", 3), [oec is the controller, and the display station is attached to it.],
    cells-image("status-wait", 4), [The host hasn't answered what you sent yet. Wait.],
    cells-image("status-system", 8), [The host has locked the keyboard. Wait for it to unlock.],
    cells-image("status-protected", 5), [You typed where you can't: into a protected field. Move the cursor
      to an input field. The symbol goes at the next key.],
    cells-image("status-overflow", 4), [The field is full, and what you typed didn't fit. The symbol goes at
      the next key.],
    cells-image("status-security", 11), [Whether oec's connection to the host is encrypted.],
    cells-image("status-shift", 1), [Shift is held down.],
    cells-image("status-insert", 1), [Insert mode is on (@tab-edit).],
    cells-image("status-indicator", 8), [The cursor's row and column, drawn by the display station.
      Display Setup's Row/column indicator turns it off (@tab-page1).],
    cells-image("status-dim", 1), [Auto dim has blanked the screen, drawn by the display station
      (@auto-dim).],
    table.hline(stroke: 0.5pt))) <tab-status>

== The cursor

The cursor#ix[cursor] shows where what you type goes; the host decides where it starts. It is an underline or a
block, steady or blinking, as Display Setup's page 1 sets it (@tab-page1), and the cursor is white, whatever the
colour of the field it is in, and green in monochrome.

== The rule line <rule-line>

The rule line#ix[rule line] helps you line things up: a dotted line along the cursor's row, down its column, or
both (@fig-rule). #keys-for(km, "Rule")#ix("Rule key", see: "rule line") turns it on and off. Display Setup's
page 1 sets which lines it draws, whether they are white or green, and whether they follow the cursor or stay
put (@tab-page1).

The rule line is off when the display station is switched on, and whether it is on is never saved. It isn't
drawn over SetUp, and is back when SetUp closes.

#figure(placement: bottom, screen-image("dslist-ruler"), caption: [The rule line, both lines, at the cursor])
<fig-rule>

== Colour <colour>

Unless the host chooses otherwise, each field is drawn in one of four colours, by its kind, which its field
attribute sets#ix[field attribute]: input fields green, intensified input fields red, protected fields blue
and intensified protected fields white (@fig-colours). These are the base
colours#ix("colour", sub: "base colours")#ix[base colour].
The rule and the status line are blue.

A host can also choose a field's colour#ix[colour] itself, from seven, and highlight it: blinking, reversed or
underscored. This extended highlighting#ix[extended highlighting], and the host's own colours, are kept in the
display station's extended attribute buffer, or EAB#ix[EAB]. The display station tells the controller it can
show these, as a 3483-V does.

Display Setup's page 3 changes those four colours#ix("colour", sub: "mapping") wherever they are drawn,
whether a field’s kind or the host chose them (@display-setup).

#figure(placement: auto, screen-image("colours"), caption: [The colours and highlights]) <fig-colours>

== Monochrome

At Monochrome Yes, on Display Setup’s page 4 (@tab-page4), the display station draws everything#ix[monochrome]
in green,
brighter in intensified fields, as a monochrome display station would (@fig-mono). Page 3’s colours then
don't apply.

#figure(placement: auto, screen-image("dslist-mono"), caption: [The same screen in monochrome]) <fig-mono>

== Mono case

Mono case#ix[mono case] Yes, on Display Setup’s page 2 (@tab-page2), shows the host's small letters as capitals,
in colour or in monochrome.

== Auto dim <auto-dim>

When no key has been pressed and the host has written nothing for a while, auto dim#ix[auto dim] blanks the
host's
rows to spare the monitor. The rule, the status line and the cursor stay; on the status line, the cursor's
row and column go, and auto dim's mark appears (@tab-status). Display Setup's page 1 turns auto dim on or
off and sets how long it waits: 5, 10 or 20 minutes (@tab-page1).

Any key brings the screen back, and that key is not sent to the host. So does anything the host writes.

If a password is set, page 1’s Lock sessions makes auto dim lock the display station#ix[lock] instead
(@locking).
