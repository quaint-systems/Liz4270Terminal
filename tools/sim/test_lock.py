# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The password's hash, the keys a password takes, and the lock (firmware/core/lock.c, #122), against the spec
(docs/superpowers/specs/2026-10-13-password-lock-design.md) and the 3483-V as captured on Oct 13
(captures/README.md)."""

import unittest

import core

K = core.scan_codes()
ABC = [(K['A'], False), (K['B'], False), (K['C'], False)]


def fnv1a64(data):
    """FNV-1a 64, written here from its definition."""
    h = 0xCBF29CE484222325
    for byte in data:
        h = ((h ^ byte) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


class TestHash(unittest.TestCase):
    def test_fnv1a64_is_the_published_one(self):
        self.assertEqual(fnv1a64(b'a'), 0xAF63DC4C8601EC8C)

    def test_the_length_then_each_key_and_its_shift(self):
        for keys in ([], ABC[:1], ABC, [(K['A'], True)] * 10, [(K['0'], False), (K['SLASH'], True)]):
            data = bytes([len(keys)]) + b''.join(bytes([code, int(shift)]) for (code, shift) in keys)
            self.assertEqual(core.lock_hash(keys), fnv1a64(data) or 1, keys)

    def test_fixed_vectors(self):
        self.assertEqual(core.lock_hash([]), 0xAF63BD4C8601B7DF)
        self.assertEqual(core.lock_hash(ABC), 0x8B25113279BBCE55)
        self.assertEqual(core.lock_hash([(K['A'], True)] + ABC[1:]), 0x17B7D87E4FDC64AA)

    def test_shift_order_and_length_each_count(self):
        (a, b) = ABC[:2]
        keys = ([a], [(K['A'], True)], [a, b], [b, a], [a, a], [a, a, a])
        self.assertEqual(len({core.lock_hash(k) for k in keys}), len(keys))


class TestCharacters(unittest.TestCase):
    LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    DIGITS = '0123456789'
    PUNCTUATION = ('BACKTICK', 'LESS', 'COMMA', 'PERIOD', 'SLASH', 'SEMICOLON', 'MINUS', 'QUOTE', 'BRACE', 'CENT',
                   'EQUALS', 'BACKSLASH')

    def names(self):
        return [*self.LETTERS, *self.DIGITS, *self.PUNCTUATION]

    def test_letters_digits_and_punctuation(self):
        for name in self.names():
            self.assertTrue(core.lock_character(K[name]), name)

    def test_nothing_else_space_and_the_keypad_included(self):
        taken = {K[name] for name in self.names()}
        for code in range(256):
            if code not in taken:
                self.assertFalse(core.lock_character(code), code)


LOCK = core.constants('lock.h', 'LOCK_')
OFF, BLACK, PROMPT = LOCK['OFF'], LOCK['BLACK'], LOCK['PROMPT']
NONE, REDRAW, ALARM, UNLOCKED = LOCK['NONE'], LOCK['REDRAW'], LOCK['ALARM'], LOCK['UNLOCKED']
DIM_BLANK, DIM_LOCK, DIM_NONE = LOCK['DIM_BLANK'], LOCK['DIM_LOCK'], LOCK['DIM_NONE']
PASSWORD = core.lock_hash(ABC)
PROMPT_TEXT = 'Enter password ===========>'  # lock-2-enter-password-prompt.jpg


def at_prompt():
    """A lock engaged, then a key: the prompt, empty."""
    lock = core.Lock()
    lock.engage()
    lock.key('A')
    return lock


def typed(lock, keys, shift=False):
    return [lock.key(key, shift, PASSWORD) for key in keys]


class TestLock(unittest.TestCase):
    """The lock (#122), as captured on Oct 13 (captures/photos-20261013/lock-*.jpg)."""

    def test_off_until_engaged(self):
        lock = core.Lock()
        self.assertEqual((lock.state, lock.key('A')), (OFF, NONE))

    def test_any_key_brings_up_the_prompt_and_is_swallowed(self):
        lock = core.Lock()
        lock.engage()
        self.assertEqual(lock.state, BLACK)
        self.assertEqual(lock.key('A', False, PASSWORD), REDRAW)
        self.assertEqual(lock.state, PROMPT)
        self.assertEqual(lock.status_line()[1], LOCK['INPUT_COL'])  # no asterisk: the A isn't counted

    def test_the_right_password_unlocks(self):
        lock = at_prompt()
        self.assertEqual(typed(lock, ('A', 'B', 'C')), [REDRAW] * 3)
        self.assertEqual(lock.key('ENTER', False, PASSWORD), UNLOCKED)
        self.assertEqual(lock.state, OFF)

    def test_a_wrong_password_sounds_the_alarm_and_goes_black(self):
        lock = at_prompt()
        typed(lock, ('A', 'B', 'D'))
        self.assertEqual(lock.key('ENTER', False, PASSWORD), ALARM)
        self.assertEqual(lock.state, BLACK)
        lock.key('A')
        self.assertEqual(lock.status_line()[1], LOCK['INPUT_COL'])  # the next prompt is empty

    def test_the_wrong_shift_is_a_wrong_password(self):
        lock = at_prompt()
        typed(lock, ('A', 'B', 'C'), shift=True)
        self.assertEqual(lock.key('ENTER', False, PASSWORD), ALARM)

    def test_enter_on_an_empty_prompt_is_wrong(self):
        lock = at_prompt()
        self.assertEqual(lock.key('ENTER', False, PASSWORD), ALARM)
        self.assertEqual(lock.state, BLACK)

    def test_with_no_password_set_enter_unlocks(self):
        # The console's set defaults can clear the password while locked: nothing to check, so no lock left that
        # only a power cycle opens.
        lock = at_prompt()
        self.assertEqual(lock.key('ENTER', False, 0), UNLOCKED)

    def test_keys_that_type_nothing_sound_the_alarm(self):
        for key in ('BACKSPACE', 'SPACE', 'TAB', 'LEFT', 'PF3', 'SETUP', 'KP_1'):
            lock = at_prompt()
            lock.key('A', False, PASSWORD)
            self.assertEqual(lock.key(key, False, PASSWORD), ALARM, key)
            self.assertEqual(lock.status_line()[1], LOCK['INPUT_COL'] + 1, key)

    def test_a_held_key_stops_at_ten(self):
        lock = at_prompt()
        results = typed(lock, 'A' * 12)
        self.assertEqual(results, [REDRAW] * 10 + [ALARM] * 2)
        (codes, cursor, _) = lock.status_line()
        self.assertEqual(cursor, LOCK['INPUT_COL'] + 10)
        self.assertEqual(codes[LOCK['INPUT_COL']:LOCK['INPUT_COL'] + 11],
                         bytes([core.display_text_code('*')] * 10 + [0]))

    def test_the_stats(self):
        lock = at_prompt()
        typed(lock, ('A', 'B', 'D'))
        lock.key('ENTER', False, PASSWORD)
        lock.key('A')
        typed(lock, ('A', 'B', 'C'))
        lock.key('ENTER', False, PASSWORD)
        lock.engage()
        self.assertEqual(lock.stats(), {'locks': 2, 'unlocks': 1, 'wrong': 1})


class TestStatusLine(unittest.TestCase):
    def test_black_shows_the_x_and_the_key(self):
        # lock-1-locked-blank.jpg: X at column 9, the key at 11 and 12, counted from 1.
        lock = core.Lock()
        lock.engage()
        (codes, cursor, bar) = lock.status_line()
        want = bytearray(80)
        (want[LOCK['X_COL']], want[LOCK['KEY_COL']], want[LOCK['KEY_COL'] + 1]) = (0xF6, 0xFA, 0xFB)
        self.assertEqual((codes, cursor, bar), (bytes(want), -1, False))

    def test_the_prompt_on_the_bar_with_an_asterisk_a_key(self):
        lock = at_prompt()
        typed(lock, ('A', 'B', 'C'))
        (codes, cursor, bar) = lock.status_line()
        text = bytes(core.display_text_code(ch) for ch in PROMPT_TEXT)
        star = core.display_text_code('*')
        self.assertEqual(codes[:len(text)], text)
        self.assertEqual(codes[len(text)], 0)
        self.assertEqual(codes[28:31], bytes([star] * 3))
        self.assertEqual(set(codes[31:]), {0})
        self.assertEqual((cursor, bar), (31, True))

    def test_off_is_blank(self):
        self.assertEqual(core.Lock().status_line(), (bytes(80), -1, False))


class TestDimRule(unittest.TestCase):
    def test_page_1s_lock_sessions_with_a_password_locks(self):
        import screen
        self.assertEqual(core.lock_dim_due(screen.Settings(lock_sessions=True, password=PASSWORD)), DIM_LOCK)

    def test_without_it_or_without_a_password_it_blanks(self):
        import screen
        for settings in (screen.Settings(), screen.Settings(password=PASSWORD), screen.Settings(lock_sessions=True)):
            self.assertEqual(core.lock_dim_due(settings), DIM_BLANK, settings)

    def test_locked_nothing(self):
        import screen
        self.assertEqual(core.lock_dim_due(screen.Settings(lock_sessions=True, password=PASSWORD), locked=True),
                         DIM_NONE)


if __name__ == '__main__':
    unittest.main()
