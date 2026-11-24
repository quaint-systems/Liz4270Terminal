# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""SetUp's rows, read by walking SetUp in the sim as a user would (#136).

Each screen with choices or items is opened on a fresh SetUp and checked to be the one it's named for, by its
title and, on Display Setup, its page, counted back with F7. Then the selector is stepped (Right for
choices, Down for a menu's items) until it comes back, which gives every place it stops. A row's label is
the text before its first choice, less the dot leader; a row of choices with no label continues the row
above (Volume's second line); a row with text and no choices is a heading. A label indented more than two
cells belongs to the nearest one above indented two.

Then each choice is pressed on a fresh SetUp, Space for a choice and Enter for an item. The alarm means
the firmware doesn't act on it (the pink rows, and the items it doesn't have yet). Otherwise the setting
Space changed gives each choice's value, and the default is the choice whose value the core's defaults
hold.
"""

import re

import manual_paths  # noqa: F401  (tools/sim on the path)
import core
import display_codes
import screen

COLS = 80
FIRST_ROW = 4   # rows count from 1, as SetUp's do: 1 is the title and 3 the instruction
LAST_ROW = 22   # 23 is the offline warning's and 24 the legend's
ALARM = core.constants('setup_ui.h', 'SETUP_UI_')['ALARM']

# (name, its picture in screen.SETUP_KEYS, kind): every screen that has choices or items, opened by the keys
# its picture is drawn by.
SCREENS = (
    ('Online Setup and Utility', 'menu', 'items'),
    ('Display Setup, page 1', 'page1', 'choices'),
    ('Display Setup, page 2', 'page2', 'choices'),
    ('Display Setup, page 3', 'page3', 'choices'),
    ('Display Setup, page 4', 'page4', 'choices'),
    ('Offline Setup', 'offline', 'items'),
    ('Customization', 'customize', 'choices'),
)
STEP = {'choices': 'RIGHT', 'items': 'DOWN'}
PRESS = {'choices': 'SPACE', 'items': 'ENTER'}


class WalkError(Exception):
    pass


def row_text(regen, row):
    """SetUp's row (counting from 1) as text: display codes as characters, field attributes as blanks."""
    start = row * COLS
    return ''.join(display_codes.MAIN[c] if c < 0xC0 else ' ' for c in regen[start:start + COLS])


def _open(keys):
    ui = core.SetupUi()
    ui.open()
    for key in keys:
        ui.key(key)
    ui.draw()
    return ui


def stops(keys, kind):
    """Every address the selector stops at, in the order the step key visits them."""
    ui = _open(keys)
    start = ui.selector_at
    if not start:
        raise WalkError(f'no selector after {keys}')
    found = []
    while True:
        found.append(ui.selector_at)
        ui.key(STEP[kind])
        ui.draw()
        if ui.selector_at == start:
            return found
        if len(found) > 200:
            raise WalkError(f'the selector never came back after {keys}')


def _choice(text, col):
    return re.split(r' {2,}', text[col:].rstrip())[0]


def _title(regen):
    """The title row's title and its More: mark ('', '+', '-+' or '-')."""
    (title, _, more) = row_text(regen, 1).partition('More:')
    return (title.strip(), more.strip())


def screen_name(keys):
    """The screen keys open, named as SCREENS names it: its title, and its page if it has more than one. The page
    is counted by F7 back to the page whose More: mark has no -, since pages 2 and 3 share their mark."""
    ui = _open(keys)
    (title, more) = _title(ui.regen())
    if not more:
        return title
    page = 1
    while '-' in more:
        ui.key('PF7')
        ui.draw()
        (_, more) = _title(ui.regen())
        page += 1
        if page > 20:
            raise WalkError(f'F7 never reached the first page after {keys}')
    return f'{title}, page {page}'


def screen_rows(name, keys, kind):
    """The screen's rows in screen order: [{'parent', 'label', 'stops': [(address, text)]}]."""
    found = screen_name(keys)
    if found != name:
        raise WalkError(f'expected {name!r}, found {found!r}')
    regen = _open(keys).regen()
    by_row = {}
    for address in stops(keys, kind):
        by_row.setdefault(address // COLS, []).append(address % COLS)
    rows, parent, last = [], '', None
    for row in range(FIRST_ROW, LAST_ROW + 1):
        text = row_text(regen, row)
        if not text.strip():
            continue
        cols = sorted(by_row.get(row, ()))
        if kind == 'items':
            if cols:
                label = text[cols[0]:].strip()
                rows.append({'parent': '', 'label': label, 'stops': [(row * COLS + cols[0], label)]})
            continue
        lead = text[:cols[0]] if cols else text
        indent = len(lead) - len(lead.lstrip())
        label = re.sub(r'[ .]+$', '', lead).strip()
        found = [(row * COLS + c, _choice(text, c)) for c in cols]
        if not label:
            if last is None:
                raise WalkError(f'{name}: choices on row {row} with no label above them')
            last['stops'] += found
            continue
        if indent <= 2:
            parent = label
        if found:
            last = {'parent': parent if indent > 2 else '', 'label': label, 'stops': found}
            rows.append(last)
    return rows


def _press(keys, kind, order, address):
    """Step to address on a fresh SetUp and press it: (what SetUp answered, the settings after)."""
    ui = _open(keys)
    for _ in range(order.index(address)):
        ui.key(STEP[kind])
    ui.draw()
    if ui.selector_at != address:
        raise WalkError(f'stepped to {ui.selector_at}, wanted {address}')
    return (ui.key(PRESS[kind]), ui.settings)


def walk():
    """[{'screen', 'parent', 'label', 'choices', 'default', 'field', 'acted'}] for every row of every screen."""
    defaults = core.settings_defaults()
    out = []
    for (name, image, kind) in SCREENS:
        keys = screen.SETUP_KEYS[image]
        order = stops(keys, kind)
        for row in screen_rows(name, keys, kind):
            pressed = [_press(keys, kind, order, address) for (address, _) in row['stops']]
            entry = {'screen': name, 'parent': row['parent'], 'label': row['label'],
                     'choices': [text for (_, text) in row['stops']] if kind == 'choices' else [],
                     'default': None, 'field': None,
                     'acted': all(answer != ALARM for (answer, _) in pressed)}
            if kind == 'choices' and entry['acted']:
                fields = {f for (_, after) in pressed for f in after if after[f] != defaults[f]}
                if len(fields) != 1:
                    raise WalkError(f"{name} / {row['label']}: its choices set {sorted(fields) or 'nothing'}")
                entry['field'] = fields.pop()
                values = [after[entry['field']] for (_, after) in pressed]
                entry['default'] = entry['choices'][values.index(defaults[entry['field']])]
            out.append(entry)
    return out
