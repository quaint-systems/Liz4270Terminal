# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The host screens the manual composes (#136), for what no host shows on cue: every colour and highlight side
by side, a Model 3 and a Model 4 layout, and the status line's symbols.

Each is a screen_fixture.Fixture, as a recorded screen is, so screens.py draws both alike through the firmware's
renderer. The status line is the one oec master writes, made by oec's own StatusLine and message-area code, with
no host name: the recorded screens ran oec with --no-hostname-status, and these match them. Field attributes and
EAB bytes are as oec writes them (docs/upstream-review.md, "Display codes and attributes").
"""

import functools
import ssl
from types import SimpleNamespace

import manual_paths  # noqa: F401  (tools/sim on the path)
import core
import screen
from screen_fixture import Fixture

COMPOSED = {'when': '', 'host': 'none', 'how': 'tools/manual/compose.py'}

# Field attributes as oec writes them, 0xC0 | (attr & 0x2C): bit 5 protected, bits 3-2 display.
INPUT, INPUT_HI, PROTECTED, PROTECTED_HI = 0xC0, 0xC8, 0xE0, 0xE8
# EAB bytes: the colour in bits 5-3, the highlight in bits 7-6.
COLOURS = {'Blue': 1, 'Red': 2, 'Pink': 3, 'Green': 4, 'Turquoise': 5, 'Yellow': 6, 'White': 7}
HIGHLIGHTS = {'Blink': 1, 'Reverse': 2, 'Underscore': 3}
WHITE = 7


def eab(colour=0, highlight=0):
    return highlight << 6 | colour << 3


def oec_status(message=None, shift=False, insert=False, secure=False):
    """The 80 display codes oec master's status line holds: OEC, the message area (None, 'wait', 'system',
    'protected' or 'overflow'), the connection's security, and the shift and insert indicators."""
    from oec.display import StatusLine
    from oec.keyboard import KeyboardModifiers
    from oec.tn3270 import TN3270Session
    from tn3270 import FieldOverflowOperatorError, ProtectedCellOperatorError

    line = bytearray(screen.COLS)

    def write(data, eab_data, address, restore_original_address):
        line[address:address + len(data)] = data

    status = StatusLine(SimpleNamespace(dimensions=SimpleNamespace(columns=screen.COLS), write=write))
    status.write_string(0, 'OEC'.ljust(screen.COLS))  # oec/terminal.py, as the terminal attaches
    socket = ssl.SSLSocket.__new__(ssl.SSLSocket) if secure else object()
    TN3270Session._write_security_status(SimpleNamespace(
        telnet=SimpleNamespace(socket=socket), terminal=SimpleNamespace(display=SimpleNamespace(status_line=status))))
    errors = {'protected': ProtectedCellOperatorError, 'overflow': FieldOverflowOperatorError}
    session = SimpleNamespace(
        waiting_on_host=message == 'wait',
        operator_error=errors[message].__new__(errors[message]) if message in errors else None,
        emulator=SimpleNamespace(keyboard_locked=message == 'system'))
    status.write(8, TN3270Session._format_message_area(session))
    status.write_keyboard_modifiers(KeyboardModifiers.LEFT_SHIFT if shift else KeyboardModifiers.NONE)
    status.write_keyboard_insert(insert)
    return bytes(line)


def _text(string):
    return bytes(core.display_text_code(ch) for ch in string)


class _Screen:
    """A Model's buffer being composed: regen and EAB, the status line oec's."""

    def __init__(self, model=2):
        self.model = model
        size = screen.geometry(model).screen_end
        self.regen = bytearray(size)
        self.eab = bytearray(size)
        self.regen[:screen.COLS] = oec_status()

    def at(self, row, col):
        """The address of a row and column, both counted from 1."""
        return screen.SCREEN_START + (row - 1) * screen.COLS + (col - 1)

    def put(self, row, col, string):
        start = self.at(row, col)
        self.regen[start:start + len(string)] = _text(string)

    def field(self, row, col, attribute, label, eab_byte=0):
        """label as a field of its own: its attribute in the cell before it, ended by a plain protected one, so
        a highlight runs no further than the label."""
        start = self.at(row, col)
        (self.regen[start - 1], self.eab[start - 1]) = (attribute, eab_byte)
        self.put(row, col, label)
        self.regen[start + len(label)] = PROTECTED

    def fixture(self, ac, eab_on=True):
        return Fixture(self.model, ac, 0, bytes(self.regen), bytes(self.eab) if eab_on else None, dict(COMPOSED))


def colours():
    """Model 2 with EAB: the four base colours by field kind on the left, the seven EAB colours on the right,
    and the three highlights in white below."""
    s = _Screen()
    s.field(2, 3, PROTECTED_HI, 'Base colours')
    s.field(2, 43, PROTECTED_HI, 'Extended colours')
    for (row, (attribute, label)) in zip((4, 6, 8, 10), ((INPUT, 'Input'), (INPUT_HI, 'Intensified input'),
                                                         (PROTECTED, 'Protected'),
                                                         (PROTECTED_HI, 'Intensified protected'))):
        s.field(row, 3, attribute, label)
    for (row, (label, colour)) in zip(range(4, 18, 2), COLOURS.items()):
        s.field(row, 43, PROTECTED, label, eab(colour))
    s.field(19, 3, PROTECTED_HI, 'Highlights')
    for (col, (label, highlight)) in zip((3, 23, 43), HIGHLIGHTS.items()):
        s.field(21, col, PROTECTED, label, eab(WHITE, highlight))
    return s.fixture(s.at(4, 3))


def layout(model):
    """Model 3 or 4, unformatted: a column scale on row 1 and each later row numbered."""
    s = _Screen(model)
    s.put(1, 1, ''.join(f'----+----{n % 10}' for n in range(1, 9)))
    for row in range(2, screen.geometry(model).rows + 1):
        s.put(row, 1, f'Row {row}')
    return s.fixture(s.at(1, 1), eab_on=False)


SCREENS = {'colours': colours, 'model3': functools.partial(layout, 3), 'model4': functools.partial(layout, 4)}

# The status line's symbols, as Chapter 3's table lists them: name -> (the status line, its first and last
# column, whether it's drawn dimmed). indicator and dim are the renderer's own, over oec's line.
STATUS_SYMBOLS = {
    'oec': (oec_status(), 0, 2, False),
    'wait': (oec_status('wait'), 8, 11, False),
    'system': (oec_status('system'), 8, 15, False),
    'protected': (oec_status('protected'), 8, 12, False),
    'overflow': (oec_status('overflow'), 8, 11, False),
    'security': (oec_status(), 20, 30, False),
    'shift': (oec_status(shift=True), 35, 35, False),
    'insert': (oec_status(insert=True), 45, 45, False),
    'indicator': (oec_status(), 72, 79, False),
    'dim': (oec_status(), 71, 71, True),
}
