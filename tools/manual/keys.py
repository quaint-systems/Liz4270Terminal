# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Every keymap as the manual's data (#136): Appendix A's tables, Chapter 4's keys and their checks.

Each keymap's rows are tools/sim/keymap_doc.py's, the ones docs/keymaps/ prints. A row's local is the local
function it is: the keymap's own (SetUp), or one of TERMINAL_KEYS, the 3483-V keys the terminal acts on itself
besides sending them. A row that sends a 3483-V key oec reads nothing from, Caps Lock or the Copy key, has a
sends name instead, so it needs its description as any key does. oec_ignores names the keys oec master's TN3270
session does nothing with, so Chapter 4's mark for them can be checked as Chapter 5's unavailable[...] is.
"""

from unittest import mock

import manual_paths  # noqa: F401  (tools/sim on the path)
import core
import keymap_doc

# The 3483-V keys the terminal acts on itself: name -> (the keymap_doc.rows() flag that marks a press of it, the
# firmware fact behind it).
TERMINAL_KEYS = {
    'Rule': ('rule', 'firmware/core/keyboard.c counts each bare Rule press, and firmware/src/setup.c turns the '
                     'ruler on or off for each (#51)'),
}

# What oec master's controller acts on itself, before a session sees the key (oec/controller.py).
CONTROLLER_KEYS = ('CURSOR_BLINK', 'ALT_CURSOR', 'CLICKER')


def _oec_key(name):
    from oec.keyboard import Key
    return Key(ord(name)) if len(name) == 1 else Key[name]


def _acts_on(name):
    """Whether oec master does anything with the key: its controller, or a TN3270 session on a screen."""
    if name in CONTROLLER_KEYS:
        return True
    from oec.tn3270 import TN3270Session
    session = TN3270Session.__new__(TN3270Session)
    session.emulator = mock.Mock()
    session.terminal = mock.Mock()
    session.keyboard_insert = False
    session.character_encoding = 'ibm037'
    session.operator_error = None
    session.waiting_on_host = False
    session.handle_key(_oec_key(name), None, None)
    return bool(session.emulator.mock_calls) or session.keyboard_insert


def oec_ignores(names):
    """Those of names, in their order, that oec master does nothing with."""
    return [name for name in names if not _acts_on(name)]


def oec_keeps(codes):
    """Whether a press oec reads no key from changes nothing in oec's keyboard either: Caps Lock does."""
    from oec.keyboard import Keyboard
    from oec.keymap_ibm_typewriter import KEYMAP
    keyboard = Keyboard(KEYMAP)
    before = keyboard.modifiers
    for code in codes:
        keyboard.get_key(code)
    return keyboard.modifiers == before


def sends_name(row):
    """The 3483-V key a row sends, as its description is named, when oec reads no key from it and it is no
    local key: 'Caps Lock', 'Shift+Copy/Play/Test'. None otherwise."""
    if row['code'] is None or row['reads'] or row['local']:
        return None
    return row['label'] if row['modifiers'] in ('kept', 'none') else f"{row['modifiers']}+{row['label']}"


def keymap_rows(keymap):
    """keymap_doc.rows(), each row's local naming a terminal key where it is one."""
    found = keymap_doc.rows(keymap)
    for row in found:
        for (name, (flag, _)) in TERMINAL_KEYS.items():
            if row[flag]:
                row['local'] = name
        row['sends'] = sends_name(row)
    return found


def keymaps_data():
    """{'keymaps': each keymap's info and rows, the default first; 'oec_ignores': the readings oec ignores}."""
    maps = [{**keymap_doc.info(keymap), 'rows': keymap_rows(keymap)} for keymap in core.keymaps()]
    readings = sorted({name for m in maps for row in m['rows'] for name in row['reads']})
    silent = {row['sends'] for m in maps for row in m['rows'] if row['sends'] and oec_keeps(row['codes'])}
    return {'keymaps': maps, 'oec_ignores': sorted(set(oec_ignores(readings)) | silent)}
