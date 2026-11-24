// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: CC-BY-4.0

#import "../style.typ": *

= Updating the firmware <updating>

The display station's firmware#ix[firmware]#ix("updating the firmware") is one file, which you copy to it
from a computer over a USB cable. It needs no software on the computer.

== Before you start <before-updating>

// docs/versions.md: the splash and SetUp's About page show the version and the commit.
- *Find the version you have.* The splash screen shows it when you switch on, and so does SetUp's About page
  (@about).#ix("firmware version")
- *Get the new firmware.* Each release is published at #raw("github.com/quaint-systems/Liz4270Terminal/releases"),
  with what changed since the last. Download #raw("liz4270-vX.Y.Z.uf2")#ix[UF2 file], where #raw("X.Y.Z")
  is the version you want. To verify the download, compare its SHA-256 checksum with the one in #raw("SHA256SUMS")
  for that file.
- *Find a USB cable* from the computer to the display station's USB-C connector. It has to carry data: a cable
  made only for charging won't do.
- *Sign off from the host.* An update restarts the display station, which ends its host session, as switching
  it off does (@switching-off).

== Updating <update-steps>

During the update the computer powers the display station, through the same USB-C connector. The monitor,
the keyboard and the coax can stay connected.

+ Unplug the power cable from #on-case[USB-C 5V], and connect the display station to the computer there
  instead. It starts as usual.
// The board spec: BOOTSEL is a button from the flash's chip-select to ground, read as RUN rises.
+ Put the display station in update mode#ix("update mode"): push a paper clip into the #on-case[BOOT]
  pinhole until the button behind it clicks, and hold it there. Press and release #on-case[RESET]. Then take
  the paper clip out.
// The RP2350's boot ROM: a USB drive named RP2350; the firmware isn't running, so no video and no heartbeat.
+ The screen goes dark, #on-case[RUN] stops blinking, and a drive named #raw("RP2350") appears on the
  computer.
+ Copy the #raw(".uf2") file to that drive.
+ When the copy ends, the drive disappears and the display station restarts by itself: the alarm sounds, and
  the splash screen shows the new version.
+ Unplug the cable from the computer, and plug the power cable back in.

#note[As the drive disappears, the computer may say that a disk was removed without being ejected. That is
expected.]

== What an update keeps <update-keeps>

// flash_store.c keeps the settings record in its own sector near the top of flash, which no UF2 writes;
// settings.h: a record's layout version changes only for a layout an older record can't be read as.
An update keeps your settings#ix("settings", sub: "after an update") and your password: they are stored apart
from the firmware. A release whose notes say otherwise starts from the defaults, which Chapter 5’s tables
show in bold (@display-setup).

#to-confirm[That a display station with saved settings and a password still has both after an update, tried
on the Liz4270 board.]

== If it goes wrong <update-problems>

// BOOTSEL is in the RP2350's ROM, which nothing can write.
Update mode is built into the display station's processor and can't be erased, so an update that fails does
no lasting harm: start again from step 2.

- *No drive appears.* The cable may be one made only for charging: try another, or another port on the
  computer. Check that #on-case[BOOT] was still held as you let go of #on-case[RESET].
- *The display station starts as usual instead.* #on-case[BOOT] wasn't held: repeat step 2.
- *You want to leave update mode without updating.* Press #on-case[RESET] alone.
- *The splash screen shows the old version.* The copy didn't finish. Repeat the update, and wait for the
  drive to disappear by itself.

To go back to an earlier version, update with that version's file in the same way.
