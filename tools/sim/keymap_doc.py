#!/usr/bin/env python
# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Reference pages for the keymaps (#17): docs/keymaps/<name>.md.

  python tools/sim/keymap_doc.py          rewrite every keymap's page
  python tools/sim/keymap_doc.py --check  exit 1 if a page is out of date

Each page lists every chord a keymap answers, its base map's included: the
3483-V key it sends, with which 3270 modifiers, and what oec's typewriter
keymap reads from the whole press (tools/sim/chords.py).
"""

import argparse
import os
import sys

import chords
import core
from paths import ROOT

DOCS = os.path.join(ROOT, 'docs', 'keymaps')

NAMES = {
    'GRAVE': '`', 'MINUS': '-', 'EQUALS': '=', 'LBRACKET': '[', 'RBRACKET': ']', 'BACKSLASH': '\\',
    'SEMICOLON': ';', 'QUOTE': "'", 'COMMA': ',', 'PERIOD': '.', 'SLASH': '/', 'ESC': 'Esc',
    'PRINT_SCREEN': 'PrtSc', 'SCROLL_LOCK': 'ScrLk', 'PAGE_UP': 'PgUp', 'PAGE_DOWN': 'PgDn',
    'CAPS_LOCK': 'Caps Lock', 'NUM_LOCK': 'Num Lock', 'KP_SLASH': 'Keypad /', 'KP_STAR': 'Keypad *',
    'KP_MINUS': 'Keypad -', 'KP_PLUS': 'Keypad +', 'KP_ENTER': 'Keypad Enter', 'KP_PERIOD': 'Keypad .',
    'LCTRL': 'Left Ctrl', 'RCTRL': 'Right Ctrl', 'LGUI': 'Left GUI', 'RGUI': 'Right GUI',
    'NONUS_HASH': 'Non-US #', 'NONUS_BACKSLASH': 'Non-US \\',
}

# Keys whose code was captured only inside a chord (plain Play and Pause are
# local and send nothing): the legends on their keycaps.
LEGENDS = {'Shift+Copy/Play': 'Copy/Play/Test', 'Left Alt+Pause (ErInp)': 'Pause/ErInp'}

# Characters that would break a table cell or start Markdown, as HTML entities.
ESCAPES = {'|': '&#124;', '\\': '&#92;', '`': '&#96;', '*': '&#42;', '<': '&lt;', '>': '&gt;',
           '[': '&#91;', ']': '&#93;'}


def cell(text):
    return ''.join(ESCAPES.get(ch, ch) for ch in text)


def usage_name(usage):
    name = {value: key for (key, value) in core.usages().items()}[usage]
    if name in NAMES:
        return NAMES[name]
    if name.startswith('KP_'):
        return 'Keypad ' + name[3:]
    if len(name) == 1 or (name[0] == 'F' and name[1:].isdigit()):
        return name  # A, 1, F13
    return name.replace('_', ' ').title()


def chord_names(when):
    """The PC modifiers of a chord, in this order: ['Shift', 'Alt'], or [] for a base entry."""
    km = core.km()
    if when == km['ANY']:
        return []
    return [name for (bit, name) in (('SHIFT', 'Shift'), ('ALT', 'Alt'), ('CTRL', 'Ctrl')) if when & km[bit]]


def mods_name(mods):
    km = core.km()
    if mods == km['KEEP']:
        return 'kept'
    return '+'.join(name for (bit, name) in (('SHIFT', 'Shift'), ('ALT', 'Alt')) if mods & km[bit]) or 'none'


def chords_of(keymap):
    """(usage, when) for every chord keymap answers, its bases' included, in usage order."""
    km = core.km()
    seen = set()
    m = keymap
    while m:
        seen |= {(usage, when) for (usage, when, _, _) in core.entries(m)}
        m = m.contents.base
    return sorted(seen, key=lambda chord: (chord[0], -1 if chord[1] == km['ANY'] else chord[1]))


def page_path(keymap):
    return os.path.join(DOCS, f'{keymap.contents.name.decode()}.md')


def info(keymap):
    """The keymap itself: its name, title, status, base map's name and the devices it claims."""
    m = keymap.contents
    devices = []
    i = 0
    while m.devices and m.devices[i]:
        devices.append(f'{m.devices[i] >> 16:04x}:{m.devices[i] & 0xFFFF:04x}')
        i += 1
    return {'name': m.name.decode(), 'title': m.title.decode(), 'status': m.status.decode(),
            'base': m.base.contents.name.decode() if m.base else None, 'devices': devices}


def rows(keymap):
    """One row for every chord keymap answers, in chords_of's order: the PC's chord and key, the 3483-V key it
    sends (label, code and the 3270 modifiers it goes with), the codes the whole press queues, what oec reads
    from them, the local function it is (SetUp), and whether it is a bare Rule, which turns the terminal's ruler
    on and off (#51)."""
    km = core.km()
    keys = core.keys3483()
    setup = core.scan_codes()['SETUP']
    found = []
    for (usage, when) in chords_of(keymap):
        if when == km['ANY']:
            (key, mods) = core.lookup(keymap, usage, 0)
        else:
            (key, mods) = core.lookup(keymap, usage, when, exact=True)
        if key in keys:
            label = keys[key]['label']
            (label, code, modifiers) = (LEGENDS.get(label, label), key, mods_name(mods))
        else:
            (label, code, modifiers) = (None, None, None)
        keyboard = core.Keyboard(keymap=keymap)
        codes = chords.press(keyboard, usage, when)
        reads = [chords.key_name(k) for k in chords.oec_keys(codes)]
        found.append({'chord': chord_names(when), 'key': usage_name(usage), 'label': label, 'code': code,
                      'modifiers': modifiers, 'codes': codes, 'reads': reads,
                      'local': 'SetUp' if key == setup else None, 'rule': keyboard.rule_presses > 0})
    return found


def render(keymap):
    about = info(keymap)
    name = about['name']
    lines = [f'# {about["title"]} (`{name}`)', '', f'Status: {about["status"]}.', '']
    if about['base']:
        lines += [f'An overlay on `{about["base"]}`: its entries replace that map\'s, one by one.', '']
    devices = [f'`{device}`' for device in about['devices']]
    lines += ['Chosen for ' + ', '.join(devices) + '.' if devices else
              'Chosen for any keyboard that no other keymap claims.', '']
    lines += [f'Generated by `tools/sim/keymap_doc.py` from `firmware/core/keymaps/{name}.c`; rerun it rather '
              'than editing this page.', '',
              'Each row is a key or chord on the USB keyboard. **3483-V key** and **Code** are what the terminal '
              'sends, as captured from a real 3483-V. **3270 modifiers** are the Shift and Alt it sends the key '
              'with: *kept* means the PC\'s own. **oec reads** is what oec\'s typewriter keymap makes of the whole '
              'press, as a cross-check. A Ctrl chord is Ctrl arriving in the same USB report as its key.', '',
              '| USB | 3483-V key | Code | 3270 modifiers | oec reads |',
              '|---|---|---|---|---|']
    for row in rows(keymap):
        if row['label'] is not None:
            (label, code, modifiers) = (row['label'], str(row['code']), row['modifiers'])
        else:
            (label, code, modifiers) = ('none (local SetUp)' if row['local'] else 'none', '—', '—')
        reads = ' '.join(row['reads']) or '—'
        if row['rule']:
            reads += ' (ruler on/off)'  # a bare Rule: the terminal's own ruler (#51)
        if row['local']:
            reads += ' (SetUp opens; the Shift and Alt held still go out)'  # local mode (#102)
        usb = ''.join(f'{m}+' for m in row['chord']) + row['key']
        lines.append(f'| {cell(usb)} | {cell(label)} | {code} | {modifiers} | {cell(reads)} |')
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--check', action='store_true', help='exit 1 if a page is out of date; write nothing')
    args = parser.parse_args()
    stale = []
    for keymap in core.keymaps():
        (path, text) = (page_path(keymap), render(keymap))
        current = open(path, encoding='utf-8').read() if os.path.exists(path) else None
        if current == text:
            continue
        stale.append(path)
        if not args.check:
            os.makedirs(DOCS, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as stream:
                stream.write(text)
    for path in stale:
        print(('out of date: ' if args.check else 'wrote ') + os.path.relpath(path, ROOT))
    return 1 if args.check and stale else 0


if __name__ == '__main__':
    sys.exit(main())
