// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: CC-BY-4.0

#import "../style.typ": *
#import "../keymap-rows.typ": keymaps, keys-for

#let km = keymaps.first()

= Sound <sound>

// firmware/core/beep.h: one tone, BEEP_HZ 3493 (the 3483-V's 3492.7 Hz by a phone tuner), BEEP_ALARM_MS 500 and
// BEEP_CLICK_MS 10; firmware/src/audio.c sounds both through the DAC's speaker amplifier.
The display station makes two sounds: the alarm#ix[alarm] and the key click#ix[key click]. They come from the
speaker#ix[speaker] inside its case. Both are one tone, the 3483-V's, of about 3.5 kHz: the alarm lasts half a
second, and the click a hundredth of one.

// beep.h's volume ladder is to be tuned to the case's speaker, so the book gives no levels.
Display Setup's page 2 sets how loud each is (@tab-page2): Alarm volume#ix("alarm", sub: "volume") for the
alarm, and the clicker's Volume#ix("key click", sub: "volume") for the click. Each is Off, 1 to 4, or High, each
louder than the last.

== The alarm <alarm>

The alarm tells you something needs your attention. @tab-alarm lists when it sounds.

// audio.c's power-on alarm; term_alarms, summed in audio_poll with SetUp's and the lock's; setup_ui.c's alarm();
// lock.c; SETUP_UI_PREVIEW and beep_preview; model_change.c; setup.c's save_fails.
#figure(kind: table, caption: [When the alarm sounds],
  table(columns: (2.15in, 1fr),
    table.header(table.hline(stroke: 0.5pt), [When], [What it tells you], table.hline(stroke: 0.5pt)),
    [You switch the display station on.], [It has started. It sounds once.],
    [The host sounds it.], [A program wants your attention. It sounds while SetUp is on the screen, or the
      display station is locked, too.],
    [You press a key SetUp can't use.], [The key does nothing there: #key("Enter") on an item that isn't
      available, the space bar on a row Liz4270 doesn't act on, #key("F7") before the first page or #key("F8")
      past the last, or a key the screen has no use for (@setup).],
    [In Password Set, you press a key that types nothing into a password, or type an eleventh character into the
      second field.],
      [The key was refused. So is any key but #key("F3") and #key("F11") once the password has changed
      (@locking).],
    [At the lock, you type a wrong password, press a key that types nothing into it, or type an eleventh
      character.], [The password, or the key, was refused (@locking).],
    [You choose an Alarm volume.], [You hear the volume you chose, or at Off see the flash. It cuts short an alarm
      already sounding.],
    [The display station comes back from offline setup.], [To the controller, it has just been switched on
      (@offline).],
    [SetUp closes, or Password Set saves a password.], [It couldn't be saved. Your settings are in use, but are
      lost when the display station is switched off: open SetUp and close it again, or set the password again.],
    table.hline(stroke: 0.5pt))) <tab-alarm>

// beep_poll: an alarm is swallowed while one sounds or a flash shows, and a click in the same poll gives way.
Alarms don't pile up: one that comes while another is sounding isn't sounded again. When a key's click and
an alarm come together, you hear the alarm.

=== Alarm volume Off

// beep_resolve makes the alarm the flash: BEEP_FLASH_MS 200, every cell's reverse flipped (video_flash). The
// 3483-V shows nothing at Off (Display Setup page 2's design, #107). render.c draws no flash while auto dim has
// the screen dark, and only the status line's while the lock is up.
At Alarm volume Off#ix("alarm", sub: "flash"), the alarm makes no sound. The screen flashes instead: every
character is reversed for a fifth of a second. This is Liz4270’s own; a 3483-V at Off shows nothing. While auto
dim has blanked the screen the flash isn't drawn, so an alarm then goes unseen, and while the display station is
locked only the status line flashes.

// beep_power_on_volume: BEEP_POWER_ON_VOLUME 3 when Alarm volume is Off.
The power-on alarm still sounds#ix("alarm", sub: "power-on"), at volume 3, so that you always know the display
station has started.

== The key click <key-click>

Each key you press clicks, as on a 3483-V, by these rules:

// beep_poll: click = (local_key || (host_key && clicker && Click)) && the clicker's Volume isn't Off. The lock's
// keys count as local (setup.c). oec master sets the clicker only with --clicker (args.py), sent at each attach
// (terminal.py), and no us104 chord gives oec's own CLICKER key.
- In SetUp and at the lock, every key clicks, whatever Click says.
- A key you press for the host clicks only when Click is Yes and the controller has turned the
  clicker on#ix[clicker]. oec turns it on when it is started with `--clicker`, each time it attaches the
  display station, and has no key that turns it off. A 3174 turns it on and off as its own documentation
  describes.
// keyboard.c counts every press and every typematic repeat, keys that send nothing included.
- A held key clicks each time it repeats, and keys that send nothing click too.
// keys3483.c's make_break; docs/upstream-review.md, "What sounds on the 3483-V".
- Shift, Alt, Reset (#keys-for(km, "RESET")) and Caps Lock never click, as on a 3483-V: they are the keys
  whose release it sends.
// dim_report takes the waking key out of the report before the keyboard translator sees it.
- The key that brings the screen back from auto dim doesn't click: it goes nowhere (@auto-dim).
// beep_resolve: Volume Off silences every click, SetUp's too.
- With the clicker's Volume at Off, nothing clicks, in SetUp either.

Alarm volume, Click and the clicker's Volume are kept when you leave SetUp with #key("F3") from its menu
(@setup).
