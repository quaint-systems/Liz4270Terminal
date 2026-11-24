// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: CC-BY-4.0

#import "../style.typ": *

// The board's own export: the label the case prints over each opening in its back wall, and where along the
// 100 mm edge it sits (tools/board/make_exports.py writes it, and the case is cut from the same file).
#let case-export = json("/hardware/board/export/liz4270-case.json")

// Figure 2-1: the back of the case, in black on white, each opening at the board's own position and under
// the case's own label. x runs to the right as you face the back, as the export has it.
#let back-drawing() = {
  let board = case-export.outline.width
  let wide = 5.0in
  let at(mm) = mm / board * wide
  let mid = 0.42in
  let shapes = (
    "COAX": place(dx: -0.17in, dy: mid - 0.17in, circle(radius: 0.17in, stroke: 0.75pt,
      align(center + horizon, circle(radius: 0.035in, fill: black)))),
    "USB-C 5V": place(dx: -0.17in, dy: mid - 0.06in, rect(width: 0.34in, height: 0.12in, radius: 0.06in,
      stroke: 0.75pt)),
    "USB": {
      place(dx: -0.26in, dy: mid - 0.25in, rect(width: 0.52in, height: 0.2in, stroke: 0.75pt))
      place(dx: -0.26in, dy: mid + 0.05in, rect(width: 0.52in, height: 0.2in, stroke: 0.75pt))
    },
    "HDMI": place(dx: -0.28in, dy: mid - 0.09in, polygon(stroke: 0.75pt, (0in, 0in), (0.56in, 0in),
      (0.56in, 0.1in), (0.48in, 0.18in), (0.08in, 0.18in), (0in, 0.1in))),
    "BOOT": place(dx: -0.02in, dy: mid - 0.02in, circle(radius: 0.02in, fill: black)),
    "RESET": place(dx: -0.07in, dy: mid - 0.07in, rect(width: 0.14in, height: 0.14in, stroke: 0.75pt)),
  )
  box(width: wide, height: 1.14in, {
    place(rect(width: wide, height: 0.84in, radius: 4pt, stroke: 0.75pt))
    for (name, x) in case-export.labels {
      assert(name in shapes, message: "the case has an opening Figure 2-1 doesn't draw: " + name)
      place(dx: at(x), shapes.at(name))
      place(dx: at(x) - 0.5in, dy: 0.94in, box(width: 1in, align(center, text(font: sans, size: 9pt, name))))
    }
  })
}

= Setting up <setting-up>

This chapter says what is on the display station's case, what to plug in and in what order, and what you
should see and hear when you switch it on. It describes the Liz4270 board in its case.

== The back of the case <back-panel>

Every connector#ix[connectors] is on the back, each under its name (@fig-back).

#figure(back-drawing(), caption: [The back of the display station]) <fig-back>

// The labels are the case's own (hardware/board/export/liz4270-case.json); what each carries is the board
// spec's "Power", "USB host", "Video" and "The board and its edge".
/ COAX: The coax#ix[coax] to the controller, on a BNC#ix[BNC] connector (@coax-cable).
/ USB-C 5V: Power (@power). During a firmware update it also carries the new firmware from a computer
  (@updating).
/ USB: Two USB ports, one above the other, for the keyboard#ix("keyboard", sub: "connecting"). Either will do.
/ HDMI: The monitor#ix("monitor", sub: "connecting").
/ BOOT: A button behind a pinhole, pressed with a paper clip. It is used only to update the firmware
  (@updating).
// The board spec: RESET is a button from RUN to ground, so it restarts the RP2350 as a power-on does.
/ RESET: A button#ix[RESET button] you can press with a finger. It restarts the display station, as switching
  it off and on does.

== The top of the case <lights>

// hardware/case/dims.scad: LED_LABELS, PWR over D5 (red, on 3.3 V) and RUN over D1, the heartbeat on GPIO29;
// main.c toggles it every HEARTBEAT_MS (500 ms).
Two lights#ix[lights] show through the lid:

- #on-case[PWR] is lit while the display station has power.
- #on-case[RUN] blinks once a second while its firmware is running.

The speaker is under the grille in the lid. The alarm and the key click come from it (@sound).

== Power <power>

// The board spec, "Power": 5.1 kΩ on each CC pin, so any source supplies 5 V, and no PD controller.
The display station takes 5~V through its USB-C connector#ix[power]#ix[USB-C]. A #box[USB-C] charger, or a USB port
on a computer or a monitor, supplies it. It has no power switch#ix("switching on and off"): plugging the cable
in switches it on, and unplugging it switches it off.

// The board spec, "Power": the hub and both USB-A ports are fed through one current-limited load switch.
The keyboard takes its power through the display station, so the supply has to carry both. A keyboard with
backlighting#ix("keyboard", sub: "backlit") draws much more than a plain one, and isn't advised.

#to-confirm[The current the display station draws, to be measured on the Liz4270 board: on the splash
screen, with a plain keyboard, and with a backlit one. The design's estimate is 300 to 350~mA at 5~V with a
plain keyboard. Whether a 1~A charger is enough is untried.]

== The coax <coax-cable>

// concept.md and the board spec: the 3270 coax is 93 Ω, RG-62, on BNC connectors.
The display station attaches to the controller by 3270 coax: RG-62 cable#ix[RG-62], which is 93~Ω, with a BNC
plug at each end. Other coax with BNC plugs, such as the 50~Ω and 75~Ω cable made for radio and video, fits
the connectors but is the wrong cable.

- On an IBM~3174, use a port for a coax display station.
- On a Liz~4174, use the port its oec is running for (@splash-stays).

A BNC plug pushes on and turns a quarter turn clockwise to lock. Turn it back to take it off.

== Connecting it <connecting>

Connect everything else before the power, since the power cable is the switch:

// Chapter 8, "The screen stays dark": no hot-plug test is recorded, so the monitor goes in first.
+ Connect the monitor to #on-case[HDMI], and switch the monitor on. A monitor with only a DVI input takes an
  HDMI-to-DVI adapter or cable.
+ Plug the keyboard into either port marked #on-case[USB].
+ Connect the coax from the controller to #on-case[COAX].
+ Plug the power cable into #on-case[USB-C 5V].

The keyboard and the coax can also be connected, or changed, while the display station is on.

== Switching on <switching-on>

When you plug the power in:

+ #on-case[PWR] lights, and #on-case[RUN] begins to blink.
// audio.c sounds the power-on alarm once the DAC answers, at any Alarm volume.
+ The alarm sounds once (@alarm).
// splash.c: at least SPLASH_MIN_MS (3 s), then until term_written.
+ The splash screen#ix("splash screen") appears, with the version of the firmware (@fig-splash). It stays at
  least 3 seconds, and then until the controller first writes to the screen.
+ The controller's first screen replaces it. Under oec, the status line shows #on-screen[OEC] at its left
  (@tab-status), and then the host's first screen appears.

If one of these doesn't happen, see @problems.

The display station starts as a 24-row display, Model 2, or at the size it was last set to. To change the
size the host sees, see @customization. To choose how the screen, the keyboard and the sound behave, see
@setup.

== Switching off <switching-off>

// Chapter 8, "The screen stops changing": under oec, losing the display station ends its host session.
Unplug the power cable. Sign off from the host first: to the controller, a display station that is switched off
has gone, and under oec that ends its host session.

// setup.c saves only as SetUp closes from a menu; nothing is saved at power-off.
The display station keeps the settings SetUp has saved while it is off (@settings-lost). Changes made in SetUp
that aren't saved yet are lost.
