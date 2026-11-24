// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: CC-BY-4.0

#import "../style.typ": *

// The glossary (#136): style.typ's glossary() sorts the entries, marks each term in the index, and gives each
// expansion an index entry that sees its term. test_glossary.py checks that the book uses every term defined
// here. Each entry opens a line of its own, "TERM": (...), as that test reads them.

#unnumbered([Glossary]) <glossary>

This glossary defines the 3270 terms this book uses, and a few a reader meets beside it. A term in a
definition that has an entry of its own is named after "See also".

#glossary((
  "3174": (expands: "IBM 3174 Establishment Controller", body: [IBM's controller for 3270 display stations
    and printers: it attaches them by coax, and connects them to the host. Liz4270 attaches to one as a 3483-V
    does.],
    also: ("controller",)),
  "3270": (body: [IBM's family of display stations, printers and controllers for its mainframes, and the data
    stream the host's programs write to them.]),
  "3483-V": (body: [The IBM display station that Liz4270 behaves as: a 3270 display station that works in CUT
    mode or DFT mode.], also: ("CUT", "DFT")),
  "alarm": (body: [The display station's long tone, which the host, SetUp or the lock sounds to get your
    attention.], also: ("key click",)),
  "auto dim": (body: [Blanking the host's rows when no key has been pressed and the host has written nothing
    for a while, to spare the monitor.]),
  "base colour": (body: [One of the four colours a field is drawn in by its kind, when the host chooses none:
    green, red, blue and white.], also: ("field attribute",)),
  "coax": (body: [The coaxial cable that joins a display station to its controller.]),
  "controller": (body: [The device that attaches display stations to the host, and does the 3270 work for those
    in CUT mode: an IBM 3174, or oec with a Liz 4174.], also: ("3174", "oec")),
  "cursor": (body: [The mark on the screen that shows where what you type goes.]),
  "CUT": (expands: "control unit terminal", body: [The mode in which the controller handles the 3270 data
    stream, and the display station keeps the screen, draws it and sends the keys you press. Liz4270 works in
    CUT mode only.], also: ("DFT",)),
  "DFT": (expands: "distributed function terminal", body: [The mode in which a display station handles the 3270
    data stream itself, and can hold several sessions at once. Liz4270 doesn't have it.], also: ("CUT",)),
  "display station": (body: [IBM's name for a 3270 terminal: a screen and a keyboard, attached to a
    controller.]),
  "EAB": (expands: "extended attribute buffer", body: [A second buffer beside the regen buffer, holding each
    character's colour and highlighting as the host chooses them.], also: ("extended highlighting",
    "regen buffer")),
  "extended highlighting": (body: [Blinking, reversed or underscored characters, which the host chooses through
    the EAB.], also: ("EAB",)),
  "field": (body: [A part of the screen that the host defines, either for you to type into or protected from
    typing.], also: ("field attribute",)),
  "field attribute": (body: [The character position that starts a field and says its kind: protected or not,
    and intensified or not. It shows as a blank.], also: ("field",)),
  "host": (body: [The computer the sessions run on: a mainframe, real or emulated.]),
  "key click": (body: [The short tone a key makes as you press it.], also: ("alarm",)),
  "keymap": (body: [The table that says which 3483-V key each key on a USB keyboard sends.]),
  "Liz 4174": (body: [A board that joins a computer running oec to the coax. Its name is the IBM 3174’s, with
    1000 added, as Liz4270’s is the 3270’s.], also: ("oec",)),
  "Model 2": (body: [A screen of 24 rows of 80 columns for the host: the display station's size unless you
    choose another.]),
  "Model 3": (body: [A screen of 32 rows of 80 columns for the host.]),
  "Model 4": (body: [A screen of 43 rows of 80 columns for the host.]),
  "monochrome": (body: [Drawing everything in green, brighter in intensified fields, as a monochrome display
    station did.]),
  "mono case": (body: [Showing the host's small letters as capitals.]),
  "MSR": (expands: "magnetic stripe reader", body: [A card reader some 3270 display stations attach. Liz4270 has
    none.]),
  "oec": (body: [Open-source software that does a 3270 controller's work on a computer. It attaches display
    stations through a Liz 4174, and reaches the host over TN3270.], also: ("Liz 4174", "TN3270")),
  "OIA": (expands: "operator information area", body: [IBM's name for the status line.],
    also: ("status line",)),
  "PA keys": (expands: "program attention keys", body: [Keys that tell the host's program they were pressed,
    sending no field.], also: ("PF keys",)),
  "PF keys": (expands: "program function keys", body: [Keys that send the fields you changed to the host's
    program, with the key's own code. The program decides what each does.], also: ("PA keys",)),
  "regen buffer": (expands: "regeneration buffer", body: [The display station's memory of the screen, which the
    controller writes and the display station draws from, many times a second.], also: ("EAB",)),
  "rule line": (body: [A dotted line along the cursor's row, down its column, or both, to help you line things
    up.]),
  "selector": (body: [SetUp's reversed block, which marks the item or choice you're on. It has nothing to do with
    the selector pen.], also: ("selector pen",)),
  "selector pen": (body: [A light pen some 3270 display stations attach, for choosing a field by touching the
    screen with it. Liz4270 has none.], also: ("selector",)),
  "session": (body: [A connection between the display station and a program on the host, which the controller
    makes.]),
  "SetUp": (body: [The display station's own menus, for how it looks, sounds and behaves.]),
  "status line": (body: [The line at the foot of the screen that says what the controller and the display
    station are doing.], also: ("OIA",)),
  "TN3270": (body: [The protocol that carries 3270 sessions over a TCP/IP network. oec reaches the host with
    it.]),
  "typematic": (body: [A held key repeating, after the delay and at the rate that SetUp sets.]),
))
