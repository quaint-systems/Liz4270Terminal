# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Pressing keymap chords through the translator, and reading the result as oec does (#17).

test_keymaps.py and keymap_doc.py share these. A chord is (usage, when), as a
keymap entry names it: when is KM_ANY for the base entry, or the Shift, Alt and
Ctrl it is pressed with. Ctrl in a chord arrives in the same report as its key,
as the Unicomp sends it.
"""

import core

BREAK = 240
RM_LCTRL, RM_LSHIFT, RM_LALT = 0x01, 0x02, 0x04


def press(keyboard, usage, when):
    """Every code queued by holding when's Shift and Alt, pressing usage, and
    letting go of both, from an idle keyboard (core.Keyboard)."""
    km = core.km()
    chord = 0 if when == km['ANY'] else when
    held = (RM_LSHIFT if chord & km['SHIFT'] else 0) | (RM_LALT if chord & km['ALT'] else 0)
    if usage >= core.usages()['LCTRL']:  # a modifier bit, pressed as one
        steps = [(held, ()), (held | 1 << (usage - core.usages()['LCTRL']), ()), (held, ()), (0, ())]
    elif chord & km['CTRL']:
        steps = [(held, ()), (held | RM_LCTRL, (usage,)), (held, ()), (0, ())]
    else:
        steps = [(held, ()), (held, (usage,)), (held, ()), (0, ())]
    codes = []
    for (mods, usages) in steps:
        codes += keyboard.report(mods, usages)
    return codes


def oec_keys(codes):
    """The keys oec's typewriter keymap reads from codes, in order, modifier changes
    left out. The code after each 240 is a release: oec reads Reset's release as a
    second RESET, which does nothing new, so it is left out too."""
    from oec.keyboard import Keyboard
    from oec.keymap_ibm_typewriter import KEYMAP
    keyboard = Keyboard(KEYMAP)
    keys = []
    after_break = False
    for code in codes:
        (key, _, changed) = keyboard.get_key(code)
        if code == BREAK:
            after_break = True
        elif after_break:
            after_break = False
        elif key is not None and not changed:
            keys.append(key)
    return keys


def key_name(key):
    """oec's key as its character where it is printable ASCII, else its name: '!', PF1."""
    value = getattr(key, 'value', None)
    if isinstance(value, int) and 32 < value < 127:
        return chr(value)
    return key.name


def problems(codes):
    """What's wrong with a sequence the controller would get: [] if nothing. Every
    code must be a 3483-V key or 240, every 240 must release a make/break key that is
    down, none is made twice, and none is left down."""
    keys = core.keys3483()
    down = set()
    found = []
    i = 0
    while i < len(codes):
        code = codes[i]
        if code == BREAK:
            if i + 1 == len(codes):
                found.append('240 at the end')
                break
            released = codes[i + 1]
            if released not in down:
                found.append(f'a release of {released}, which is not down')
            down.discard(released)
            i += 2
            continue
        if code not in keys:
            found.append(f'{code} is no 3483-V key')
        elif keys[code]['make_break']:
            if code in down:
                found.append(f'{code} made twice')
            down.add(code)
        i += 1
    if down:
        found.append(f'still down at the end: {sorted(down)}')
    return found
