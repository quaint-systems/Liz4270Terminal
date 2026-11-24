// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: CC-BY-4.0

#import "../style.typ": *

// Figure 1-1: where the display station sits, drawn as a 1990s IBM book would, in black on white. Three
// columns of boxes and two rows, the display station in the middle of the lower row.
#let system-drawing() = {
  let unit(x, y, w, title, detail) = place(dx: x, dy: y, rect(width: w, height: 0.72in, stroke: 0.75pt,
    inset: 5pt, align(center + horizon, text(font: sans, size: 10pt,
      [#text(font: sans-sb, title)#if detail != none [ \ #detail]]))))
  let wire(from, to) = place(line(start: from, end: to, stroke: 0.75pt))
  let label(x, y, body) = place(dx: x, dy: y, text(font: sans, size: 10pt, body))
  box(width: 5.1in, height: 2.06in, {
    unit(0in, 0in, 1.3in, [Host], [a mainframe, real or emulated])
    unit(1.9in, 0in, 1.6in, [Controller], [an IBM 3174, or oec and a Liz 4174])
    unit(0in, 1.34in, 1.3in, [USB keyboard], none)
    unit(1.9in, 1.34in, 1.6in, [Liz4270], [display station])
    unit(4.1in, 1.34in, 1.0in, [Monitor], none)
    wire((1.3in, 0.36in), (1.9in, 0.36in))
    wire((2.7in, 0.72in), (2.7in, 1.34in))
    label(2.8in, 0.94in, [coax])
    wire((1.3in, 1.7in), (1.9in, 1.7in))
    label(1.42in, 1.46in, [USB])
    wire((3.5in, 1.7in), (4.1in, 1.7in))
    label(3.57in, 1.46in, [HDMI])
  })
}

= Introducing Liz4270 <introducing>

// What the device is: an IBM 3483-V in CUT mode, drawn over DVI, with a USB keyboard.
Liz4270#ix[Liz4270] is a display station#ix[display station] for IBM 3270#ix[3270] systems. It attaches to a
3270 controller by coax, shows the host's screens on an HDMI monitor, and takes a USB keyboard. To the
controller, it is an IBM 3483-V display station in CUT mode#ix[3483-V].

== A 3483-V in CUT mode <cut>

A 3270 display station can work in one of two ways. In CUT mode#ix[CUT], short for control unit terminal, the
controller#ix[controller] does the 3270 work: it talks to the host#ix[host], keeps track of the fields on the
screen, and decides what each key does. The display station keeps the screen the controller writes to it, its
regen buffer#ix[regen buffer], and draws it, and it sends each key you press when the controller asks for it.

// docs/upstream-review.md, "Identity: what to report as a 3483-V": the IDs and features a 3483-V answers.
Liz4270 identifies itself as a 3483-V does, so a controller that knows the 3483-V attaches it as one, with
nothing to set up. @fig-system shows where it sits.

== What you need <what-you-need>

// The test rig: a Liz 4174 runs interface3's firmware under oec, one oec per coax port, and oec reaches
// the host over TN3270.
- A 3270 controller with a coax#ix[coax] port for a CUT display station. That is either:
  - an IBM~3174 Establishment Controller;#ix[3174] or
  - oec#ix[oec], open-source software that does a controller's work on a computer and reaches the host over
    TN3270#ix[TN3270], with a Liz~4174#ix("Liz 4174") board between the computer and the coax.
// firmware/src/main.c starts the video at 640x480, 60 Hz; tools/testcard/README.md has the monitors tried.
- A monitor#ix[monitor] with an HDMI input, or a DVI input through an adapter, that shows 640 × 480 at 60 Hz.
  Most monitors do.
// usb_host.c gives a keymap only to an interface whose boot protocol is keyboard, which nearly every one has.
- A USB keyboard: nearly any will do (@keyboard).
- Power, as @setting-up says.

// In the text, not floated: a float landed between two of the list's items on both papers.
#figure(system-drawing(), caption: [A Liz4270 display station on a controller]) <fig-system>

== What it does

- *The screen* (@screen): three sizes, Models 2, 3 and 4; colour, with the seven colours and three highlights a
  host can choose, or monochrome; the status line, the cursor and the rule line; and auto dim, which blanks the
  screen while nobody is using it.
- *The keyboard* (@keyboard): nearly any USB keyboard, through a keymap that puts the 3270 keys on it
  (@keymaps).
- *SetUp* (@setup): the display station's own menus, for how the screen, the keyboard and the sound behave,
  the screen size the host sees, and a password that locks the keyboard while you're away.
- *Sound* (@sound): the alarm and the key click.

== What isn't there <not-there>

// concept.md: "Out of scope for v1: DFT mode, selector pen, magnetic stripe reader, printer emulation."
Some of what a 3483-V can do isn't in Liz4270:

- DFT mode#ix[DFT], short for distributed function terminal, in which a 3483-V runs the 3270 data stream itself
  and can hold several host sessions at once. Liz4270 has one session#ix[session], the one its controller
  gives it.
- The selector pen#ix[selector pen] and the magnetic stripe reader#ix[MSR].
- Printers#ix[printer]: a 3483-V can have a printer attached, for a copy of the screen. Liz4270 has no printer
  port.
// Chapter 4: Scroll Lock alone is the 3483-V’s Play key, and sends nothing.
- Recording keys and playing them back, with the 3483-V’s Play key (@keyboard).
- The items in SetUp that Liz4270 doesn't act on. Chapter 5’s tables mark them (@setup).

// One UF2 runs on both boards (firmware/src/board_detect.c); SetUp's About page names the board.
#note[Liz4270’s firmware also runs on an Adafruit Fruit Jam#ix[Fruit Jam] fitted with a coax front end. This
book applies to it too, but for Chapter 2, which describes the Liz4270 board. SetUp's About page names the
board a display station runs on (@about).]

@setting-up says how to set the display station up. If you know the 3483-V, @keyboard, @setup and @keymaps
are the quickest way to what is different.
