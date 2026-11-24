# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""A host's screen as a file (#136): what snap writes beside its PNG, and what the manual draws.

The file is JSON, so it can't hold a comment: its copyright and license are fields. The regen buffer and the
EAB plane are hex, one string for each 80 bytes, the status line (0-79) first, then the screen's rows, so a
diff shows which row changed. docs/superpowers/specs/2026-10-14-user-manual-design.md, "Screens", is the design.
"""

import json
from typing import NamedTuple, Optional

import screen

COLS = screen.COLS
LICENSE = 'CC-BY-4.0'


class Fixture(NamedTuple):
    model: int                # 2, 3 or 4
    ac: int                   # the address counter: the cursor
    control: int              # the control register (screen.BLINK, REVERSE_CURSOR, ...)
    regen: bytes              # the model's whole buffer: the status line, then the rows
    eab: Optional[bytes]      # as long as regen, or None without EAB
    recorded: dict            # when ('YYYY-MM-DD'), host, and how


def size(model):
    """The bytes a model's buffer holds, the status line's included."""
    return screen.geometry(model).screen_end


def from_terminal(terminal, recorded):
    """A core.Terminal's screen as it is now."""
    end = size(terminal.model)
    eab = terminal.eab()[:end] if terminal.has_eab else None
    return Fixture(terminal.model, terminal.ac, terminal.control, terminal.regen()[:end], eab, dict(recorded))


def _rows(data):
    return [data[i:i + COLS].hex() for i in range(0, len(data), COLS)]


def to_json(fixture):
    return {
        'copyright': f"Copyright (c) {fixture.recorded['when'][:4]}, CoffeeMuse",
        'license': LICENSE,
        'recorded': fixture.recorded,
        'model': fixture.model,
        'ac': fixture.ac,
        'control': fixture.control,
        'regen': _rows(fixture.regen),
        'eab': None if fixture.eab is None else _rows(fixture.eab),
    }


def write(path, fixture):
    with open(path, 'w', encoding='utf-8') as stream:
        json.dump(to_json(fixture), stream, indent=1, ensure_ascii=False)
        stream.write('\n')


def _plane(path, model, rows, what):
    if not isinstance(rows, list) or len(rows) != size(model) // COLS:
        raise ValueError(f'{path}: {what} needs {size(model) // COLS} rows at Model {model}')
    data = b''
    for (number, row) in enumerate(rows):
        if not isinstance(row, str) or len(row) != 2 * COLS:
            raise ValueError(f'{path}: {what} row {number} is not {2 * COLS} hex characters')
        try:
            data += bytes.fromhex(row)
        except ValueError:
            raise ValueError(f'{path}: {what} row {number} is not hex') from None
    return data


def read(path):
    """The fixture in path; ValueError, naming the file, if it isn't one."""
    with open(path, encoding='utf-8') as stream:
        try:
            data = json.load(stream)
        except json.JSONDecodeError as error:
            raise ValueError(f'{path}: not JSON: {error}') from None
    if not isinstance(data, dict):
        raise ValueError(f'{path}: not a fixture: a JSON object is needed')
    model = data.get('model')
    if model not in screen.MODELS:
        raise ValueError(f'{path}: model {model!r} is not 2, 3 or 4')
    regen = _plane(path, model, data.get('regen'), 'regen')
    eab = None if data.get('eab') is None else _plane(path, model, data['eab'], 'eab')
    ac = data.get('ac')
    if not isinstance(ac, int) or not 0 <= ac < size(model):
        raise ValueError(f'{path}: ac {ac!r} is outside Model {model}\'s buffer')
    control = data.get('control')
    if not isinstance(control, int):
        raise ValueError(f'{path}: control {control!r} is not a number')
    recorded = data.get('recorded')
    if not isinstance(recorded, dict):
        raise ValueError(f'{path}: recorded is missing')
    return Fixture(model, ac, control, regen, eab, recorded)
