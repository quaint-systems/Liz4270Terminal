# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The settings record in flash (firmware/core/settings.c, #69): its bytes, checked against records Python
builds on its own with struct and zlib.crc32; what a reader refuses; and how a reader picks between slots."""

import itertools
import random
import struct
import unittest
import zlib

import core

PAGE = 256
NAMES = ('cursor', 'cursor_blink', 'indicator', 'auto_dim', 'dim_minutes', 'colour_input', 'colour_input_hi',
         'colour_protected', 'colour_protected_hi', 'mono', 'ruler_style', 'ruler_colour', 'ruler_follows',
         'typematic_rate', 'typematic_delay', 'click', 'click_volume', 'alarm_volume', 'mono_case', 'model',
         'lock_sessions')  # a byte each; the password's hash follows as eight (#122)
OLD_FIELDS = 5  # the payload before #50: cursor to dim_minutes
FIELDS_50 = 10  # the payload from #50 to #51: cursor to mono
FIELDS_51 = 13  # the payload from #51 to #107: cursor to ruler_follows
FIELDS_107 = 19  # the payload from #107 to #110: cursor to mono_case
FIELDS_110 = 20  # the payload from #110 to #122: cursor to model
PAYLOAD = 29     # #122's: 21 bytes, then the password's eight
SLOTS = NAMES[5:9]
DEFAULTS = {'cursor': 0, 'cursor_blink': False, 'indicator': True, 'auto_dim': True, 'dim_minutes': 10,
            'colour_input': 4, 'colour_input_hi': 2, 'colour_protected': 1, 'colour_protected_hi': 7, 'mono': False,
            'ruler_style': 0, 'ruler_colour': 7, 'ruler_follows': True, 'typematic_rate': 0, 'typematic_delay': 1,
            'click': True, 'click_volume': 3, 'alarm_volume': 3, 'mono_case': False, 'model': 2,
            'lock_sessions': False, 'password': 0}
# Every field different from the defaults: what a refused record must leave in place.
UNTOUCHED = {'cursor': 1, 'cursor_blink': True, 'indicator': False, 'auto_dim': False, 'dim_minutes': 20,
             'colour_input': 3, 'colour_input_hi': 6, 'colour_protected': 5, 'colour_protected_hi': 4, 'mono': True,
             'ruler_style': 2, 'ruler_colour': 4, 'ruler_follows': False, 'typematic_rate': 1, 'typematic_delay': 2,
             'click': False, 'click_volume': 5, 'alarm_volume': 0, 'mono_case': True, 'model': 4,
             'lock_sessions': True, 'password': 0x0123456789ABCDEF}
MARK = 0xDEADBEEF  # core.settings_unpack's sequence before the call


def payload(fields):
    """The payload: a byte a field, in settings_t's order, then the password's hash as eight bytes,
    little-endian (#122)."""
    return bytes([fields[name] for name in NAMES]) + fields['password'].to_bytes(8, 'little')


def record(body, seq=1, version=1, magic=b'LIZS', length=None):
    """A record laid out from the spec's table, not by the core."""
    head = magic + bytes([version, len(body) if length is None else length]) + struct.pack('<I', seq) + body
    return head + struct.pack('<I', zlib.crc32(head))


def page(data):
    return data.ljust(PAGE, b'\xff')


def every_choice():
    """Every combination of the #49 choices SetUp offers, with the later fields at their defaults: 48."""
    for (cursor, blink, indicator, auto_dim, minutes) in itertools.product(
            (0, 1), (False, True), (False, True), (False, True), (5, 10, 20)):
        yield {**DEFAULTS, 'cursor': cursor, 'cursor_blink': blink, 'indicator': indicator, 'auto_dim': auto_dim,
               'dim_minutes': minutes}


def every_mapping():
    """Each of SetUp's seven colours in each mapping slot, then monochrome on (#50): 29."""
    for slot in SLOTS:
        for colour in range(1, 8):
            yield {**DEFAULTS, slot: colour}
    yield {**DEFAULTS, 'mono': True}


def every_ruler():
    """Each of SetUp's Rule line choices (#51): four styles, white and green, following or not: 16."""
    for (style, colour, follows) in itertools.product(range(4), (7, 4), (False, True)):
        yield {**DEFAULTS, 'ruler_style': style, 'ruler_colour': colour, 'ruler_follows': follows}


class TestCrc(unittest.TestCase):
    def test_the_check_value(self):
        self.assertEqual(core.settings_crc32(b'123456789'), 0xCBF43926)

    def test_the_same_as_zlib(self):
        rng = random.Random(69)
        for length in (0, 1, 3, 4, 19, 255, 256):
            data = bytes(rng.randrange(256) for _ in range(length))
            self.assertEqual(core.settings_crc32(data), zlib.crc32(data), length)


def every_page2():
    """Each of page 2's choices (#107): Rate with Delay, Click, each volume, Mono case: 22."""
    for (rate, delay) in itertools.product(range(2), range(3)):
        yield {**DEFAULTS, 'typematic_rate': rate, 'typematic_delay': delay}
    for click in (False, True):
        yield {**DEFAULTS, 'click': click}
    for volume in range(6):
        yield {**DEFAULTS, 'click_volume': volume}
        yield {**DEFAULTS, 'alarm_volume': volume}
    for mono_case in (False, True):
        yield {**DEFAULTS, 'mono_case': mono_case}


def every_model():
    """Each of Customization's Screen rows x columns (#110): Model 2, 3 and 4."""
    for model in (2, 3, 4):
        yield {**DEFAULTS, 'model': model}


def every_lock():
    """Page 1's Lock sessions each way, with hashes at both ends and one in the middle (#122): 8."""
    for lock_sessions in (False, True):
        for password in (0, 1, 0x0123456789ABCDEF, 0xFFFFFFFFFFFFFFFF):
            yield {**DEFAULTS, 'lock_sessions': lock_sessions, 'password': password}


class TestPack(unittest.TestCase):
    def test_every_choice_as_the_spec_lays_it_out(self):
        for fields in itertools.chain(every_choice(), every_mapping(), every_ruler(), every_page2(), every_model(),
                                      every_lock()):
            self.assertEqual(core.settings_pack(7, **fields), (page(record(payload(fields), seq=7)), 43), fields)

    def test_a_round_trip(self):
        for fields in itertools.chain(every_choice(), every_mapping(), every_ruler(), every_page2(), every_model(),
                                      every_lock()):
            for seq in (1, 2, 0xFFFFFFFF):
                (packed, _) = core.settings_pack(seq, **fields)
                self.assertEqual(core.settings_unpack(packed), (True, fields, seq), (fields, seq))

    def test_the_first_five_bytes_keep_the_layout_from_before_50(self):
        # A build from before #50 reads these five and ignores the rest.
        (packed, _) = core.settings_pack(1, **UNTOUCHED)
        self.assertEqual(packed[10:15], bytes([1, 1, 0, 0, 20]))

    def test_the_first_ten_bytes_keep_the_layout_from_50(self):
        # A build from #50 reads these ten and ignores the ruler's three (#51).
        (packed, _) = core.settings_pack(1, **UNTOUCHED)
        self.assertEqual(packed[10:20], bytes([1, 1, 0, 0, 20, 3, 6, 5, 4, 1]))
        self.assertEqual(packed[20:23], bytes([2, 4, 0]))

    def test_the_first_thirteen_bytes_keep_the_layout_from_51(self):
        # A build from #51 reads these thirteen and ignores page 2's six (#107).
        (packed, _) = core.settings_pack(1, **UNTOUCHED)
        self.assertEqual(packed[20:23], bytes([2, 4, 0]))
        self.assertEqual(packed[23:29], bytes([1, 2, 0, 5, 0, 1]))

    def test_the_first_nineteen_bytes_keep_the_layout_from_107(self):
        # A build from #107 reads these nineteen and ignores the model (#110).
        (packed, _) = core.settings_pack(1, **UNTOUCHED)
        self.assertEqual(packed[23:29], bytes([1, 2, 0, 5, 0, 1]))
        self.assertEqual(packed[29], 4)

    def test_the_first_twenty_bytes_keep_the_layout_from_110(self):
        # A build from #110 reads these twenty and ignores the lock's nine (#122).
        (packed, _) = core.settings_pack(1, **UNTOUCHED)
        self.assertEqual(packed[29], 4)

    def test_lock_sessions_then_the_password_little_endian(self):
        (packed, length) = core.settings_pack(1, **UNTOUCHED)
        self.assertEqual(packed[30], 1)
        self.assertEqual(packed[31:39], bytes([0xEF, 0xCD, 0xAB, 0x89, 0x67, 0x45, 0x23, 0x01]))
        self.assertEqual(length, 10 + PAYLOAD + 4)


class TestRefused(unittest.TestCase):
    def assertRefused(self, data, why):
        self.assertEqual(core.settings_unpack(data, UNTOUCHED), (False, UNTOUCHED, MARK), why)

    def test_an_erased_page_and_a_page_of_zeros(self):
        self.assertRefused(b'\xff' * PAGE, 'erased')
        self.assertRefused(b'\x00' * PAGE, 'zeros')

    def test_another_magic_or_version(self):
        self.assertRefused(record(payload(DEFAULTS), magic=b'LIZT'), 'magic')
        for version in (0, 2, 255):
            self.assertRefused(record(payload(DEFAULTS), version=version), version)

    def test_every_bit_flipped(self):
        good = record(payload(DEFAULTS), seq=5)
        for bit in range(len(good) * 8):
            bad = bytearray(good)
            bad[bit // 8] ^= 1 << (bit % 8)
            self.assertRefused(bytes(bad), f'bit {bit}')

    def test_a_bool_of_two(self):
        # A C bool would read 2 as 1, so the byte itself is checked.
        for index in (1, 2, 3, 9, 12, 15, 18, 20):
            body = bytearray(payload(DEFAULTS))
            body[index] = 2
            self.assertRefused(record(bytes(body)), index)

    def test_values_setup_doesnt_offer(self):
        cases = [('cursor', 2), ('dim_minutes', 0), ('dim_minutes', 15)]
        cases += [(slot, colour) for slot in SLOTS for colour in (0, 8, 255)]
        cases += [('ruler_style', 4), ('ruler_style', 255), ('ruler_colour', 0), ('ruler_colour', 1),
                  ('ruler_colour', 8), ('ruler_colour', 255)]
        cases += [('typematic_rate', 2), ('typematic_delay', 3), ('click_volume', 6), ('alarm_volume', 6),
                  ('alarm_volume', 255)]
        cases += [('model', 0), ('model', 1), ('model', 5), ('model', 255)]
        for (name, value) in cases:
            self.assertRefused(record(payload({**DEFAULTS, name: value})), (name, value))


class TestLength(unittest.TestCase):
    def test_an_older_record_keeps_its_fields_and_defaults_the_rest(self):
        older = record(bytes([1, 1, 0]), seq=3)  # block, blink, no indicator
        self.assertEqual(core.settings_unpack(older),
                         (True, {**DEFAULTS, 'cursor': 1, 'cursor_blink': True, 'indicator': False}, 3))

    def test_a_record_from_before_50_keeps_its_settings_and_defaults_the_new_ones(self):
        # What the Fruit Jam holds when #50 lands: five fields.
        older = record(payload(UNTOUCHED)[:OLD_FIELDS], seq=8)
        kept = {name: UNTOUCHED[name] for name in NAMES[:OLD_FIELDS]}
        self.assertEqual(core.settings_unpack(older), (True, {**DEFAULTS, **kept}, 8))

    def test_a_record_from_50_keeps_its_settings_and_defaults_the_ruler(self):
        # What the Fruit Jam holds when #51 lands: ten fields.
        older = record(payload(UNTOUCHED)[:FIELDS_50], seq=11)
        kept = {name: UNTOUCHED[name] for name in NAMES[:FIELDS_50]}
        self.assertEqual(core.settings_unpack(older), (True, {**DEFAULTS, **kept}, 11))

    def test_a_record_from_51_keeps_its_settings_and_defaults_page_2(self):
        # What the Fruit Jam holds when #107 lands: thirteen fields.
        older = record(payload(UNTOUCHED)[:FIELDS_51], seq=12)
        kept = {name: UNTOUCHED[name] for name in NAMES[:FIELDS_51]}
        self.assertEqual(core.settings_unpack(older), (True, {**DEFAULTS, **kept}, 12))

    def test_a_record_from_107_keeps_its_settings_and_is_model_2(self):
        # What the Fruit Jam holds when #110 lands: nineteen fields.
        older = record(payload(UNTOUCHED)[:FIELDS_107], seq=13)
        kept = {name: UNTOUCHED[name] for name in NAMES[:FIELDS_107]}
        self.assertEqual(core.settings_unpack(older), (True, {**DEFAULTS, **kept}, 13))

    def test_a_record_from_110_has_lock_sessions_off_and_no_password(self):
        # What the Fruit Jam holds when #122 lands: twenty fields.
        older = record(payload(UNTOUCHED)[:FIELDS_110], seq=14)
        kept = {name: UNTOUCHED[name] for name in NAMES[:FIELDS_110]}
        self.assertEqual(core.settings_unpack(older), (True, {**DEFAULTS, **kept}, 14))

    def test_an_empty_payload_is_the_defaults(self):
        self.assertEqual(core.settings_unpack(record(b'', seq=4)), (True, DEFAULTS, 4))

    def test_a_newer_record_gives_the_fields_this_build_knows(self):
        fields = {**DEFAULTS, 'dim_minutes': 20}
        self.assertEqual(core.settings_unpack(record(payload(fields) + b'\xaa\x55', seq=9)), (True, fields, 9))

    def test_the_longest_payload_a_page_holds(self):
        longest = record(payload(DEFAULTS) + bytes(242 - len(payload(DEFAULTS))), seq=2)
        self.assertEqual(len(longest), PAGE)
        self.assertEqual(core.settings_unpack(longest), (True, DEFAULTS, 2))

    def test_a_length_past_the_page(self):
        # A length of 243 puts the CRC past the page, so the reader never looks for it.
        self.assertEqual(core.settings_unpack(record(payload(DEFAULTS), length=243), UNTOUCHED),
                         (False, UNTOUCHED, MARK))


class TestForeignBytes(unittest.TestCase):
    """Whatever the sector held before: CircuitPython's files on a Fruit Jam fresh from Adafruit."""

    def test_random_pages(self):
        rng = random.Random(4270)
        for _ in range(500):
            self.assertFalse(core.settings_unpack(bytes(rng.randrange(256) for _ in range(PAGE)))[0])

    def test_random_bytes_behind_our_magic_and_version(self):
        rng = random.Random(4174)
        for _ in range(500):
            data = b'LIZS\x01' + bytes(rng.randrange(256) for _ in range(PAGE - 5))
            self.assertFalse(core.settings_unpack(data)[0])


class TestLoad(unittest.TestCase):
    def good(self, seq, **changes):
        return page(record(payload({**DEFAULTS, **changes}), seq=seq))

    def test_one_slot(self):
        self.assertEqual(core.settings_load([self.good(3, cursor=1)]), (0, {**DEFAULTS, 'cursor': 1}, 3))

    def test_nothing_valid_gives_the_defaults(self):
        self.assertEqual(core.settings_load([b'\xff' * PAGE]), (-1, DEFAULTS, 0))
        self.assertEqual(core.settings_load([b'\xff' * PAGE, b'\x00' * PAGE]), (-1, DEFAULTS, 0))

    def test_the_higher_sequence_wins_from_either_slot(self):
        (older, newer) = (self.good(5, cursor=1), self.good(6, dim_minutes=5))
        self.assertEqual(core.settings_load([older, newer]), (1, {**DEFAULTS, 'dim_minutes': 5}, 6))
        self.assertEqual(core.settings_load([newer, older]), (0, {**DEFAULTS, 'dim_minutes': 5}, 6))

    def test_a_corrupt_slot_leaves_the_other(self):
        newer = bytearray(self.good(6))
        newer[12] ^= 1
        self.assertEqual(core.settings_load([self.good(5, cursor=1), bytes(newer)]),
                         (0, {**DEFAULTS, 'cursor': 1}, 5))

    def test_a_tie_goes_to_the_first_slot(self):
        self.assertEqual(core.settings_load([self.good(7, cursor=1), self.good(7)]),
                         (0, {**DEFAULTS, 'cursor': 1}, 7))


class TestEqual(unittest.TestCase):
    def test_the_same_settings(self):
        self.assertTrue(core.settings_equal(DEFAULTS, dict(DEFAULTS)))

    def test_each_field_on_its_own(self):
        for (name, value) in UNTOUCHED.items():
            self.assertFalse(core.settings_equal(DEFAULTS, {**DEFAULTS, name: value}), name)


if __name__ == '__main__':
    unittest.main()
