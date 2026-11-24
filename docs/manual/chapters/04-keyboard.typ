// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: CC-BY-4.0

#import "../style.typ": *
#import "../keymap-rows.typ": (keymap-data, keymaps, check-keys, keys-for, keys-for-rows,
  function-table, local-table, chord)
#import "../keys.typ": functions, local

// Every key the keymaps give has its description in keys.typ, and each key oec ignores is marked so: the build
// stops otherwise. Every chord here comes from the default keymap through keys-for, so none can drift from the
// firmware.
#check-keys(keymap-data, functions, local)
#let km = keymaps.first()

= The keyboard <keyboard>

Liz4270 takes a USB keyboard#ix[keyboard], the kind sold for a PC, and makes it type as an IBM 3483-V's keyboard
does: each key you press goes to the controller as the 3483-V key it stands for. This chapter says where the
3270 keys are, and which keys the display station keeps for itself.

== Your keyboard

// usb_host.c gives a keymap only to an interface whose boot protocol is keyboard.
Nearly any USB keyboard will do: the display station uses the USB boot keyboard interface, which almost every
wired keyboard offers (@no-keyboard). Each keyboard gets the keymap#ix[keymap] that claims it by its USB vendor
and product ID, and a keyboard that no keymap claims gets the default, #km.title. This chapter gives the default
keymap's keys; @keymaps lists every keymap, key by key.

== The 3270 keys <keys-3270>

A 3270 keyboard has keys a PC keyboard lacks, such as the PA keys and Erase EOF, and the keymap puts each on a
key or a chord. What a key does is up to the controller: these
tables#ix[3270 keys]#ix[PA keys]#ix[PF keys]#ix[editing keys]#ix[cursor keys] give what each means to a 3270
controller. oec does nothing with the keys marked †; a 3174 can act on them.

#figure(kind: table, caption: [Keys that send to the host],
  function-table(km, functions, "send", extra: (
    [PF1 to PF12], [#keys-for(km, "PF1") to #keys-for(km, "PF12")], functions.PF1.body,
    [PF13 to PF24], [#keys-for(km, "PF13") to #keys-for(km, "PF24")], [As PF1 to PF12.],
  ))) <tab-send>

PF7 and PF8, the keys most programs page back and forward with, are also on
#chord(keys-for-rows(km, "PF7").last()) and #chord(keys-for-rows(km, "PF8").last()).

#figure(kind: table, caption: [Editing keys], function-table(km, functions, "edit")) <tab-edit>

#figure(kind: table, caption: [Keys that move the cursor], function-table(km, functions, "move")) <tab-move>

#figure(kind: table, caption: [Other 3270 keys], function-table(km, functions, "other")) <tab-other>

== Shift, Alt and Caps Lock

Shift#ix[Shift] and Alt#ix[Alt] are the 3483-V's own. Hold either with another key and the controller sees it
held, as it would on a 3483-V; oec shows an upward arrow on the status line while Shift is down (@status-line).
Where a 3270 key needs a chord, the keymap sends the 3483-V's Shift and Alt as that key needs them, whatever you
hold.

Caps Lock#ix[Caps Lock] is the 3483-V's too, and the controller keeps it: under oec it makes the letters
capitals, and Shift with it gives small ones.

There are no Ctrl chords: the two Ctrl keys are keys of their own. #keys-for(km, "RESET") is Reset#ix[Reset],
and Enter is on #keys-for(km, "ENTER").

== Characters a PC keyboard lacks

A key types what its legend says, with a few exceptions for the 3483-V's own characters:

- ¢, the cent sign, is on #keys-for(km, "CENT").#ix("characters", sub: "cent sign") The 3483-V has no square
  brackets, so #key("]") types nothing; its braces are on #keys-for(km, "{") and #keys-for(km, "}").
- ¬, the not sign, is on #keys("Shift", "6"), as on the 3483-V.#ix("characters", sub: "not sign")
- ¦, the broken bar, is on #keys-for(km, "BROKEN_BAR").#ix("characters", sub: "broken bar")
- The 3483-V's centred dot is on #keys-for(km, "CENTER_PERIOD").#ix("characters", sub: "centred dot") oec can't
  show it, so the cell stays blank.

== The display station's own keys <local-keys>

#figure(kind: table, caption: [The display station’s own keys], local-table(km, local)) <tab-local>

On a 3483-V, SetUp is #keys("Alt", "ExSel"). The keymap already puts ExSel on #keys-for(km, "EXTEND_SELECT"),
so SetUp takes #keys-for(km, "SetUp").#ix("SetUp", sub: "opening")

While SetUp is on the screen, or the display station is locked (@locking), every key goes to it but Shift and
Alt, which still go to the controller. While auto dim has blanked the screen, the key that brings it back
goes nowhere (@auto-dim).

== Keys that send nothing <keys-nothing>

#km.rows.filter(r => r.label == none and r.local == none).map(chord).join(", ", last: " and ") send nothing.
Scroll Lock alone is the 3483-V's Play key, which plays back keys it has recorded; recording and playing back
aren't in this version. F13 to F24 send nothing either, so that a Windows keyboard's Copilot key, which sends
Windows, Shift and F23, sends no PF key.#ix[keys that send nothing]

== Holding a key down

Held down, the keys that type a character repeat, and so do Space, Backspace, Delete, Tab, Back Tab, New Line
and the arrows; other keys, such as Enter and the PF keys, don’t, as on the 3483-V. A key repeats#ix[typematic]
after the delay and at the rate that Display Setup's page 2 sets (@display-setup). The key click is in @sound.
