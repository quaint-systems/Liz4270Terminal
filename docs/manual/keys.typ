// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: CC-BY-4.0

// What each key the keymaps give does, for Chapter 4's tables and Appendix A's (#136). A 3270 key is named as
// tools/manual/keys.py reads it, the way oec's typewriter keymap does; oec: false marks the keys oec master does
// nothing with, which the build checks against oec itself. keymap-rows.typ's check-keys stops the build on a
// key with no entry here, or an entry for a key no keymap gives.

#import "style.typ": *

// group: "send" keys that send to the host, "pf" the PF keys, "edit", "move", "other", or "character".
#let functions = (
  "ENTER": (name: "Enter", group: "send", oec: true, body: [Sends the fields you changed to the host. The
    keyboard is locked until the host answers.]),
  "CLEAR": (name: "Clear", group: "send", oec: true, body: [Clears the screen and tells the host so. No field
    is sent.]),
  "PA1": (name: "PA1", group: "send", oec: true, body: [Program attention: tells the host the key was pressed,
    sending no field. What it does is up to the host’s program.]),
  "PA2": (name: "PA2", group: "send", oec: true, body: [As PA1.]),
  "PA3": (name: "PA3", group: "send", oec: true, body: [As PA1.]),
  "ATTN": (name: "Attn", group: "send", oec: false, body: [Interrupts the host’s program.]),
  "SYS_RQ": (name: "SysRq", group: "send", oec: false, body: [System request: switches between the host’s
    program and the host’s own services.]),
  ..range(1, 25).map(n => ("PF" + str(n), (name: "PF" + str(n), group: "pf", oec: true,
    body: [Program function keys: send the fields you changed to the host, with the key’s own code. The
    host’s program decides what each does; PF3 to leave a screen, and PF7 and PF8 to page back and forward, are
    common.]))).to-dict(),

  "INSERT": (name: "Insert", group: "edit", oec: true, body: [Turns insert mode on or off. In insert mode,
    what you type pushes the rest of the field to the right. A key that sends to the host turns it off.]),
  "DELETE": (name: "Delete", group: "edit", oec: true, body: [Deletes the character at the cursor. The rest of
    the field moves left.]),
  "BACKSPACE": (name: "Backspace", group: "edit", oec: true, body: [Deletes the character before the cursor.
    The rest of the field moves left.]),
  "ERASE_EOF": (name: "Erase EOF", group: "edit", oec: true, body: [Erases the field from the cursor to its
    end.]),
  "ERASE_INPUT": (name: "Erase Input", group: "edit", oec: true, body: [Erases every input field on the screen
    and moves the cursor to the first.]),
  "DUP": (name: "Dup", group: "edit", oec: true, body: [Types the duplicate character, which tells the host’s
    program to repeat the field above, and moves to the next input field. oec shows it as an asterisk.]),
  "FIELD_MARK": (name: "Field Mark", group: "edit", oec: true, body: [Types the field mark, which ends a part
    of a field for the host’s program. oec shows it as a semicolon.]),

  "TAB": (name: "Tab", group: "move", oec: true, body: [Moves the cursor to the next input field.]),
  "BACKTAB": (name: "Back Tab", group: "move", oec: true, body: [Moves the cursor to the start of the input
    field it is in, or of the one before.]),
  "NEWLINE": (name: "New Line", group: "move", oec: true, body: [Moves the cursor to the first input field on
    the next row, or after it.]),
  "HOME": (name: "Home", group: "move", oec: true, body: [Moves the cursor to the first input field on the
    screen.]),
  "UP": (name: "Up", group: "move", oec: true, body: [Moves the cursor up a row.]),
  "DOWN": (name: "Down", group: "move", oec: true, body: [Moves the cursor down a row.]),
  "LEFT": (name: "Left", group: "move", oec: true, body: [Moves the cursor left a column.]),
  "RIGHT": (name: "Right", group: "move", oec: true, body: [Moves the cursor right a column.]),
  "JUMP": (name: "Jump", group: "move", oec: false, body: [Moves to the next session, on a controller that
    gives the display station more than one.]),

  "Caps Lock": (name: "Caps Lock", group: "other", oec: true, body: [Locks the letters in capitals. Under oec,
    Shift with it gives small ones.]),
  "Shift+Copy/Play/Test": (name: "Copy", group: "other", oec: false, body: [The 3483-V's Copy. What it does is
    up to the controller.]),
  "RESET": (name: "Reset", group: "other", oec: false, body: [Unlocks the keyboard after an input error, and
    turns insert mode off.]),
  "CURSOR_SELECT": (name: "CrSel", group: "other", oec: false, body: [Cursor select: selects the field at the
    cursor, as a selector pen would.]),
  "EXTEND_SELECT": (name: "ExSel", group: "other", oec: false, body: [Extend select, the 3483-V’s ExSel key.
    What it does is up to the controller.]),
  "PRINT": (name: "Print", group: "other", oec: false, body: [Asks the controller to print the screen.]),
  "TEST": (name: "Test", group: "other", oec: false, body: [Asks the controller to test the display
    station.]),

  "SPACE": (name: "Space", group: "character", oec: true, body: [Types a space.]),
  "CENT": (name: "¢", group: "character", oec: true, body: [Types the cent sign.]),
  "BROKEN_BAR": (name: "¦", group: "character", oec: true, body: [Types the broken bar.]),
  "CENTER_PERIOD": (name: "Centre period", group: "character", oec: true, body: [The 3483-V’s centred dot.
    oec can’t show it, so the cell stays blank, as it does on a 3483-V under oec.]),
)

// The display station's own keys: the keymap's local SetUp, and the 3483-V keys it acts on itself
// (tools/manual/keys.py's TERMINAL_KEYS).
#let local = (
  "SetUp": [Opens SetUp, the display station’s own menus (@setup). The key itself goes nowhere: the
    controller sees only the Shift and Alt you hold.],
  "Rule": [Turns the rule line on or off (@rule-line). It also goes to the controller, as the 3483-V’s Rule key
    does, and oec does nothing with it.],
)
