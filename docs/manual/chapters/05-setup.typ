// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: CC-BY-4.0

#import "../style.typ": *
#import "../setup-rows.typ": setup-rows, check-prose, setup-table, menu-table, unavailable

// What each of SetUp's rows does, by "screen / heading / label" as tools/manual/setup_walk.py finds them.
// The build stops if a row has no entry here, an entry names a row the firmware doesn't have, or a row
// is marked unavailable (pressing it sounds the alarm) where the firmware acts on it, or the other way.
#let prose = (
  "Online Setup and Utility / Lock sessions": [Locks the display station at once, if a password is set
    (@locking). With none set, it opens Password Set first.],
  "Online Setup and Utility / Setup display": [Display Setup's four pages (@display-setup).],
  "Online Setup and Utility / Setup local functions": unavailable[Not available on Liz4270: the alarm sounds.],
  "Online Setup and Utility / Set password": [Password Set, to set or clear the password that unlocks the
    display station (@locking).],
  "Online Setup and Utility / Setup color palette": unavailable[Not available in this version: the alarm sounds.],
  "Online Setup and Utility / Go to offline setup": [Offline setup, for the screen size the host sees. Going
    there ends the host's sessions (@offline).],

  "Display Setup, page 1 / Rule line / Style": [The line the #key("Rule") key turns on and off: along the
    cursor's row, down its column, or both.],
  "Display Setup, page 1 / Rule line / Color": [The rule line's colour.],
  "Display Setup, page 1 / Rule line / Follows cursor": [No leaves the rule line where it is while the
    cursor moves.],
  "Display Setup, page 1 / Row/column indicator": [The cursor's row and column, at the right of the status
    line.],
  "Display Setup, page 1 / Cursor / Style": [An underline or a block.],
  "Display Setup, page 1 / Cursor / Blink": [Yes makes the cursor blink.],
  "Display Setup, page 1 / Auto dim": [Yes blanks the screen when no key has been pressed and the host has
    written nothing for the delay below. Any key brings the screen back, and that key is not sent to the
    host.],
  "Display Setup, page 1 / Auto dim / Delay (minutes)": [How long auto dim waits.],
  "Display Setup, page 1 / Auto dim / Lock sessions": [Yes makes auto dim lock the display station instead
    of blanking it, once a password is set (@locking).],

  "Display Setup, page 2 / Typematic / Rate": [How fast a held key repeats.#ix[typematic]],
  "Display Setup, page 2 / Typematic / Delay": [How long a key is held before it starts to repeat.],
  "Display Setup, page 2 / Clicker / Click": [Yes makes each key click while the host has the clicker turned
    on. In SetUp, keys click whatever this says.],
  "Display Setup, page 2 / Clicker / Volume": [How loud the click is. Off silences it, in SetUp too.],
  "Display Setup, page 2 / Alarm volume": [How loud the alarm is. Choosing a level sounds the alarm at it.
    At Off the screen flashes instead, but for the power-on alarm, which always sounds.],
  "Display Setup, page 2 / Trim border": unavailable[On the 3483-V, the frame of a trim print. Liz4270 has
    no local printing, so the space bar sounds the alarm.],
  "Display Setup, page 2 / Mono case": [Yes shows the host's lower-case letters as capitals.],

  "Display Setup, page 3 / Four base color mapping / Input": [Drawn wherever the host asks for green, as it
    does for input fields.],
  "Display Setup, page 3 / Four base color mapping / Intensified input": [Drawn wherever the host asks for
    red, as it does for intensified input fields.],
  "Display Setup, page 3 / Four base color mapping / Protected": [Drawn wherever the host asks for blue, as
    it does for protected fields.],
  "Display Setup, page 3 / Four base color mapping / Intensified protected": [Drawn wherever the host asks
    for white, as it does for intensified protected fields.],

  "Display Setup, page 4 / Liz4270 / Monochrome": [Yes draws everything in green, brighter in intensified
    fields, as a monochrome display station would. Page 3’s colours then don't apply.],

  "Offline Setup / Customize display station": [Customization (@customization).#ix[Customization]],
  "Offline Setup / Set printer definition utility": unavailable[Not available on Liz4270: the alarm sounds.],
  "Offline Setup / Update serial number": unavailable[Not available in this version: the alarm sounds.],
  "Offline Setup / Test display station": unavailable[Not available in this version: the alarm sounds.],

  "Customization / Screen rows x columns": [The screen size#ix[screen size] the host sees: 24 × 80 is a
    Model 2, 32 × 80 a Model 3 and 43 × 80 a Model 4. It takes effect as you leave offline setup.],
  "Customization / Keyboard layout": unavailable[Not used on Liz4270: the space bar sounds the alarm.],
  "Customization / Numeric lock": unavailable[Not used on Liz4270: the space bar sounds the alarm.],
  "Customization / Underscore style": unavailable[Not used on Liz4270: the space bar sounds the alarm.],
  "Customization / Unprotected field / Markup": unavailable[Not used on Liz4270: the space bar sounds the alarm.],
  "Customization / Black-On-White emulation": unavailable[Not used on Liz4270: the space bar sounds the alarm.],
)
#check-prose(setup-rows, prose)

= Using SetUp <setup>

SetUp#ix[SetUp] is the display station's own set of menus. With it you choose how the screen looks, how the
keyboard and the sound behave, and the screen size the host sees, and you set a password to lock the display
station. SetUp works without the host: while it is on the screen, the keys you press go to SetUp, and anything
the host writes waits behind it until SetUp closes.

== Opening and closing SetUp

+ Hold down #keys("Shift", "Alt") and press #key("X"). The Online Setup and Utility menu appears
  (@fig-menu).#ix("SetUp", sub: "opening")
+ Move to an item with the arrow keys, and press #key("Enter").
+ To close SetUp, press #key("F3") on the menu. Your settings are saved, and they stay through a power
  cycle.#ix("SetUp", sub: "closing")#ix("settings", sub: "saving")

#note[On an IBM 3483-V, the same function is #keys("Alt", "ExSel"). The US keymap puts ExSel on
#keys("Alt", "X"), so SetUp takes #keys("Shift", "Alt", "X").]

#figure(placement: auto, screen-image("setup-menu"), caption: [Online Setup and Utility menu]) <fig-menu>

== Moving around SetUp

On every SetUp screen a reversed block, the selector#ix[selector], marks the item or choice you're on.
#key("Down") and #key("Up") move it down and up a column, and #key("Right") and #key("Left") along a row; from
the last, it wraps around to the first. A key SetUp can't use sounds the
alarm.#ix("SetUp", sub: "moving around")

On a menu, #key("Enter") opens the item the selector is on. On a page of settings, the space bar selects
the choice: it takes effect at once, and the choice now set is shown in yellow. In this chapter's tables,
each setting's default is in bold. #key("F7") and #key("F8")
page back and forward, and #key("F3") goes back to the menu.

#figure(kind: table, caption: [Online Setup and Utility menu],
  menu-table(setup-rows, prose, "Online Setup and Utility")) <tab-menu>

== Display Setup <display-setup>

Display Setup#ix[Display Setup] has four pages. The first three are the 3483-V's own; the fourth is Liz4270’s.

#figure(placement: auto, screen-image("setup-page1"), caption: [Display Setup, page 1]) <fig-page1>

#figure(kind: table, caption: [Display Setup, page 1],
  setup-table(setup-rows, prose, "Display Setup, page 1")) <tab-page1>

#figure(placement: auto, screen-image("setup-page2"), caption: [Display Setup, page 2]) <fig-page2>

#figure(kind: table, caption: [Display Setup, page 2],
  setup-table(setup-rows, prose, "Display Setup, page 2")) <tab-page2>

A host that uses base colour draws each field in one of four colours, by its kind: input fields green,
intensified input fields red, protected fields blue and intensified protected fields white. Page 3 changes
those four colours: wherever the host asks for one of them, the colour chosen here is drawn instead.

#figure(placement: auto, screen-image("setup-page3"), caption: [Display Setup, page 3]) <fig-page3>

#figure(kind: table, caption: [Display Setup, page 3],
  setup-table(setup-rows, prose, "Display Setup, page 3")) <tab-page3>

#figure(kind: table, caption: [Display Setup, page 4],
  setup-table(setup-rows, prose, "Display Setup, page 4")) <tab-page4>

== Locking the display station <locking>

A password#ix[password] keeps the keyboard to you while you're away. The host's sessions go on behind the
lock.#ix[lock]

=== Setting a password

+ On the menu, choose Set password. Password Set#ix[Password Set] appears (@fig-password).
+ Type the password in the first field, up to ten characters, and press #key("Enter"). At the tenth
  character the cursor moves on to the second field by itself, so there you don't press #key("Enter"). Each
  character shows as an asterisk. Capitals and small letters count as different. Letters, digits and
  punctuation from the main keys type into it; the keypad, Space, Tab, Backspace and the arrows sound the
  alarm.
+ Type it again in the second field, and press #key("Enter"). If the two match, the password is saved at
  once and #on-screen[Password has been changed.] appears. If they don't, or nothing was typed,
  #on-screen[Invalid password. Password has not been changed.] appears, and the fields are cleared to try
  again.

To clear the password, press #key("F11") on Password Set: #on-screen[Password has been cleared.] appears.

#figure(placement: auto, screen-image("setup-password"), caption: [Password Set]) <fig-password>

=== Locking and unlocking

Choose Lock sessions on the menu. With no password set, Password Set opens first; set one, and
#key("F3") locks the display station. Display Setup's Lock sessions makes auto dim lock it too (@tab-page1).

While it is locked, the screen is black but for the cursor, and the status line shows the lock
(@fig-lock). The host can still write to the screen, and you see what it wrote when the display station
unlocks.

To unlock it, press any key but Shift or Alt: Enter password appears on the status line. Type the password and
press #key("Enter"). A wrong password sounds the alarm. Switching the display station off and on also unlocks
it, and the password stays set.

#figure(placement: auto, screen-image("lock-prompt"), caption: [The lock, with three characters of the
password typed]) <fig-lock>

== Offline setup <offline>

#attention[Going to offline setup ends every session on this display station. The host sees it leave, and
when it comes back you sign on again.]

+ On the menu, choose Go to offline setup#ix[offline setup]. A warning appears at the foot of the screen.
+ Press #key("Enter") to go on, or any other key to stay online. The Offline Setup menu appears.
+ Choose Customize display station, set what you need (@tab-customization), and press #key("F3") to go
  back to the Offline Setup menu.
+ Press #key("F3") again to leave SetUp. Your settings are saved, and the display station comes back, no sooner
  than a second after it went offline: the host finds it again, at the new screen size if you changed it, and
  the power-on alarm sounds.

#figure(kind: table, caption: [Offline Setup menu], menu-table(setup-rows, prose, "Offline Setup"))
<tab-offline>

=== Customization <customization>

#figure(placement: auto, screen-image("setup-customize"), caption: [Customization]) <fig-customization>

#figure(kind: table, caption: [Customization],
  setup-table(setup-rows, prose, "Customization")) <tab-customization>

== About Liz4270 <about>

Press #key("F10") on the menu to see which firmware#ix[firmware version]#ix[About Liz4270] the display station
runs: its version, the commit it was built from, and the board (@fig-about). Quote them when you ask for help.
#key("F8") pages through the licenses the firmware is under, and #key("F3") goes back to the menu.

#figure(placement: auto, screen-image("setup-about-1"), caption: [About Liz4270]) <fig-about>
