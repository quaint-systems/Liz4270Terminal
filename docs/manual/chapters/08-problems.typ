// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: CC-BY-4.0

#import "../style.typ": *
#import "../keys.typ": functions

// The symptoms, in the chapter's order, for Table 8-1: each section's title and page, read from its heading, so
// no title is typed twice. test_chapter8.py checks the list against the headings.
#let symptoms = (<no-picture>, <splash-stays>, <lost>, <no-keyboard>, <keys-do-nothing>, <wrong-characters>,
  <screen-black>, <forgot-password>, <no-sound>, <settings-lost>)

#let symptom-table(labels) = context table(columns: (1fr, 0.6in), align: (left, right),
  table.header(table.hline(stroke: 0.5pt), [What you see], [Page], table.hline(stroke: 0.5pt)),
  ..labels.map(l => {
    let heading = query(l).first()
    let loc = heading.location()
    (link(loc, heading.body), link(loc, numbering(loc.page-numbering(), ..counter(page).at(loc))))
  }).flatten(),
  table.hline(stroke: 0.5pt))

// The keys oec master does nothing with, as keys.typ marks them and keys.py checks against oec itself.
#let ignored = functions.values().filter(f => not f.oec).map(f => f.name).join(", ", last: " and ")

= Problem solving <problems>

Most problems come down to a cable, a setting or the controller. Find what you see in @tab-symptoms, and go to
its page: each section says what to check, in order, and what each check tells you. If none of it helps, ask
for help (@help).

#figure(kind: table, caption: [Symptoms], symptom-table(symptoms)) <tab-symptoms>

== The screen stays dark <no-picture>

Check that the monitor#ix("monitor", sub: "no picture")#ix("screen", sub: "dark") is on and set to the input
the display station is plugged into, and that the HDMI cable is in at both ends.

// audio.c sounds the power-on alarm once the DAC answers, at any Alarm volume (beep_power_on_volume).
Listen as you switch the display station on. The one alarm it sounds means it has started, whatever Alarm
volume says (@alarm), so if you hear it, the trouble is between the display station and the monitor. If you
hear nothing either, check its power (@setting-up).

// main.c: video_init at 640x480, 60 Hz, at every power-on; video.c: DVI over the HDMI connector, no audio.
The display station sends 640 × 480 at 60 Hz, as DVI over the HDMI cable, with no sound. A monitor that can't
show that mode shows nothing, or says it has no signal: try another.

// No hot-plug test is recorded, so the book promises none.
If you connected the monitor after switching the display station on, switch the display station off and on with
the monitor connected.

== The splash screen stays <splash-stays>

// splash.c: at least SPLASH_MIN_MS (3 s), then until term_written.
The splash screen#ix("splash screen", sub: "stays") stays at least 3 seconds, then until the controller first
writes to the screen. If it stays, the controller hasn't attached the display station.

- Check the coax at both ends, that the controller is running, and that the display station is on a port the
  controller serves.
// oec master polls unattached addresses every 0.5 s (controller.py), and Terminal.setup writes OEC at status
// column 0 once it attaches one (terminal.py).
- Under oec, check that oec is running for the Liz~4174’s port the coax goes to. oec looks for the display
  station every half second, so it doesn't matter which you start first. When it attaches the display station,
  the status line shows #on-screen[OEC] at its left (@tab-status).

// splash.h: SetUp, or the lock, ends the splash for good; the regen buffer is zeroed at power-on.
Opening SetUp ends the splash screen, and leaves a blank screen until the controller writes to it.

== The screen stops changing <lost>

// No code in coax_link.c notices the POLLs stopping, and the status line is oec's to write (display.py).
If the coax comes out, or the controller stops, the display
station#ix("controller", sub: "lost")#ix("screen", sub: "stops changing") keeps the last screen and status line
it was given. Nothing on it says the controller has gone.

// oec master: _handle_device_lost ends the session; _handle_device_found reads the IDs again, Terminal.setup
// clears the screen and writes OEC, and a new TN3270 session starts.
Under oec, losing the display station ends its host session. When oec finds it again, it clears the screen,
shows #on-screen[OEC] on the status line and starts a new session, so you sign on again.

// model_change.c: the link stays off the coax until F3 leaves the Offline Setup menu, and a second at least.
Going to offline setup does the same, on purpose: the display station leaves the controller while offline setup is
up, for at least a second, and comes back as you leave it (@offline).

== The keyboard does nothing <no-keyboard>

// The board design: hub ports 1 and 2 to the USB-A jacks; the USB-C is power and the console.
- Plug the keyboard#ix("keyboard", sub: "does nothing") into one of the USB-A ports. The USB-C port is for
  power.
// usb_host.c gives a keymap only to an interface whose boot protocol is keyboard.
- The display station uses the USB boot keyboard interface, which nearly every wired keyboard offers. A
  keyboard without it types nothing.
// tusb_config.h: CFG_TUH_HUB 1, which the on-board hub takes; CFG_TUH_HID 4 interfaces in all.
- Plug the keyboard in directly: the display station can use no hub but its own, so a keyboard plugged into a
  separate hub, or one with a hub of its own, doesn't work. Unplug other USB devices and try the keyboard alone.
// usb_host.c remounts a keyboard with its keymap when it comes back.
- A keyboard can be unplugged and plugged in again at any time, and types again by itself.

If SetUp is on the screen, the keys go to SetUp (@setup). If the screen is black but for the cursor, and the
status line shows the lock, the display station is locked (@locking). If the status line shows that the host has
locked the keyboard, wait for the host (@tab-status).

== Some keys do nothing <keys-do-nothing>

// tools/manual/keys.py runs every key through oec master's TN3270 session; these are the ones it ignores.
Under oec, #ignored do nothing#ix("oec", sub: "keys it ignores"). They are the keys marked † in Chapter 4
(@keys-3270), and a 3174 can act on them.

// oec master locks no keyboard for an input error: the render after each key clears operator_error (tn3270.py),
// and its TN3270 session has no branch for Reset, so Reset clears the symbol and does nothing else.
Under oec, an input error doesn't lock the keyboard: the next key you press clears its symbol from the status
line (@tab-status). Reset is the one to press, since under oec it does nothing else.

Some keys send nothing at all, on purpose (@keys-nothing).

== The wrong characters appear <wrong-characters>

Each keyboard gets the keymap#ix("keymap", sub: "wrong characters") that claims it by its USB vendor and product
ID, and any other keyboard gets the default, the US 104-key keymap. A keyboard laid out for another country
types as a US one unless a keymap claims it. Appendix A lists each keymap and the keyboards it is chosen for
(@keymaps).

== The screen goes black <screen-black>

Auto dim#ix[auto dim]#ix("screen", sub: "goes black") has blanked it: the status line shows its mark, and any
key brings the screen back without being sent to the host (@auto-dim). Or the display station is
locked#ix[lock]: the status line shows the lock, and the password unlocks it (@locking).

== You forgot the password <forgot-password>

// setup_init calls lock_clear, and the password stays in flash; Password Set's F11 asks for no old password
// (setup_ui.c, Oct 13), and setup.c saves the change at once.
+ Switch the display station off and on: it starts unlocked, and the password is still
  set.#ix("password", sub: "forgotten")
+ Open SetUp, choose Set password, and press #key("F11") on Password Set. The password is cleared at once.

== There's no sound <no-sound>

- At Alarm volume Off, the screen flashes in place of the alarm#ix("alarm", sub: "not heard") (@alarm).
// beep_poll: Volume Off silences every click; Click No only the host's keys.
- With the clicker's Volume at Off, no key clicks;#ix("key click", sub: "not heard") with Click at No, keys you
  press for the host don't (@tab-page2).
// oec master sets the clicker only when started with --clicker.
- Keys you press for the host click only while the controller has the clicker on. Under oec, start oec with
  `--clicker` (@key-click).

== Settings aren't kept <settings-lost>

// setup.c: F3 on the Online menu, or on the Offline menu, closes SetUp and saves, and so does the lock from the
// Online menu's Lock sessions (SETUP_UI_LOCK); F3 on a page goes back to its menu; a password is saved when it is
// set; a failed save sounds the alarm.
- SetUp saves your settings#ix("settings", sub: "saving") when you leave it with #key("F3") from the Online
  Setup and Utility menu, or from the Offline Setup menu, and when Lock sessions on the Online Setup and Utility
  menu locks the display station. #key("F3") on a page of settings only goes back to the menu.
- Switching off with SetUp open loses that visit's changes. A password is saved as soon as it is set.
- If the alarm sounds as SetUp closes, your settings couldn't be saved. Open SetUp and close it again, and if it
  keeps happening, ask for help (@help).
- SetUp has no item that restores every default. Each setting's default is in bold in Chapter 5’s tables
  (@display-setup).

== Asking for help <help>

When you ask for help#ix("help, asking for"), say:

- the firmware's version#ix("firmware version") and commit, from the splash screen when you switch on, or from
  SetUp's About page (#key("F10") on the menu), which also names the board (@about);
- the controller, a 3174 or oec, and how you started oec;
- the keyboard's make and model;
- what you did, and what you saw.

Open an issue at #raw("github.com/quaint-systems/Liz4270Terminal/issues").
