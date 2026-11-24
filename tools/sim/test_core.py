# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The terminal core against the terminal-side contract (docs/upstream-review.md).

Each test sends the words oec sends and checks what the real 3483-V answered
in the Oct 3 and Oct 4, 2026 captures (the #29 probes are
captures/20261004-*-ids-defaults-*.jsonl). The few defaults for behaviour no
capture shows are marked as such.
"""

import unittest

from coax.protocol import pack_data_word, unpack_data_word

from core import REGEN_SIZE, Terminal

TT_AR = [0x000]
POWER_ON_RESET = [0x00A]

POLL = 0x005
POLL_ACK = 0x045
READ_STATUS = 0x035
READ_TERMINAL_ID = 0x025
READ_EXTENDED_ID = 0x01D
READ_AC_HI = 0x015
READ_AC_LO = 0x055
READ_DATA = 0x00D
READ_MULTIPLE = 0x02D
RESET = 0x009
LOAD_CONTROL = 0x029
LOAD_SECONDARY = 0x069
LOAD_AC_HI = 0x011
LOAD_AC_LO = 0x051
WRITE_DATA = 0x031
UNASSIGNED = (0x1F << 2) | 0b01  # base code 0x1F is no command
CLEAR = 0x019
FEATURE_ERROR = 0x001
UNASSIGNED_CODES = (0x00, 0x0F, 0x13, 0x17, 0x18, 0x19, 0x1B, 0x1D, 0x1E, 0x1F)  # captured Oct 13
EMPTY = 2  # a feature address with nothing at it on the 3483-V


def feature_command(address, code):
    return (address << 6) | (code << 2) | 0b01


def read_feature_id(address):
    return feature_command(address, 0x7)


EAB_LOAD_MASK = feature_command(7, 0x6)  # 0x1D9 in the traces
EAB_WRITE_ALTERNATE = feature_command(7, 0xA)  # 0x1E9 in the traces
EAB_READ_DATA = feature_command(7, 0x3)


def data(*values):
    return [pack_data_word(value) for value in values]


def keystroke(code):
    return [(code << 2) | 0b10]


class CoreTest(unittest.TestCase):
    eab = True

    def setUp(self):
        self.term = Terminal(eab=self.eab)

    def frame(self, *words):
        return self.term.frame(list(words))

    def acknowledge_power_on(self):
        self.assertEqual(self.frame(POLL), POWER_ON_RESET)
        self.assertEqual(self.frame(POLL_ACK), TT_AR)

    def load_ac(self, address):
        self.frame(LOAD_AC_HI, *data(address >> 8))
        self.frame(LOAD_AC_LO, *data(address & 0xFF))

    def read_ac(self):
        [hi] = self.frame(READ_AC_HI)
        [lo] = self.frame(READ_AC_LO)
        return (unpack_data_word(hi) << 8) | unpack_data_word(lo)

    def read_data(self, address):
        self.load_ac(address)
        [word] = self.frame(READ_DATA)
        return unpack_data_word(word)

    def write_at(self, address, *values):
        self.load_ac(address)
        self.frame(WRITE_DATA, *data(*values))

    def big(self, on):
        self.frame(LOAD_SECONDARY, *data(int(on)))


class TestPoll(CoreTest):
    def test_power_on_reset_is_held_until_acknowledged(self):
        # Captured: the first POLL after power-on answers 0x00A, and the
        # terminal holds it until POLL_ACK, however long that takes.
        self.assertEqual(self.frame(POLL), POWER_ON_RESET)
        self.assertEqual(self.frame(POLL), POWER_ON_RESET)
        self.assertEqual(self.frame(POLL_ACK), TT_AR)
        self.assertEqual(self.frame(POLL), TT_AR)

    def test_poll_ack_with_nothing_queued_answers_tt_ar(self):
        self.acknowledge_power_on()
        self.assertEqual(self.frame(POLL_ACK), TT_AR)
        self.assertEqual(self.frame(POLL), TT_AR)

    def test_keys_come_out_in_order_one_per_acknowledgement(self):
        self.acknowledge_power_on()
        for code in (18, 28, 0xF0, 18):  # Left Shift+A, as captured
            self.assertTrue(self.term.key(code))
        for code in (18, 28, 0xF0, 18):
            self.assertEqual(self.frame(POLL), keystroke(code))
            self.assertEqual(self.frame(POLL), keystroke(code))
            self.assertEqual(self.frame(POLL_ACK), TT_AR)
        self.assertEqual(self.frame(POLL), TT_AR)

    def test_break_prefix_is_a_status_like_any_other(self):
        self.acknowledge_power_on()
        self.term.key(0xF0)
        self.assertEqual(self.frame(POLL), [0x3C2])  # as in the oec traces

    def test_queue_holds_32_statuses(self):
        self.acknowledge_power_on()
        for code in range(32):
            self.assertTrue(self.term.key(40 + code))
        self.assertFalse(self.term.key(99))
        self.assertEqual(self.term.queued, 32)

    def test_power_on_reset_takes_a_slot(self):
        for code in range(31):
            self.assertTrue(self.term.key(40 + code))
        self.assertFalse(self.term.key(99))

    def test_queue_counters_wrap(self):
        self.acknowledge_power_on()
        for i in range(600):
            code = i % 256
            self.assertTrue(self.term.key(code))
            self.assertEqual(self.frame(POLL), keystroke(code))
            self.frame(POLL_ACK)
        self.assertEqual(self.term.queued, 0)

    def test_poll_actions(self):
        self.acknowledge_power_on()
        self.assertEqual(self.frame(0x305), TT_AR)  # clicker on
        self.assertTrue(self.term.clicker)
        self.assertEqual(self.frame(0x105), TT_AR)  # clicker off, oec's first POLL
        self.assertFalse(self.term.clicker)
        self.frame(0x205)  # alarm
        self.frame(0x205)
        self.assertEqual(self.term.alarms, 2)

    def test_poll_with_an_action_still_answers_the_status(self):
        self.assertEqual(self.frame(0x105), POWER_ON_RESET)


class TestFraming(CoreTest):
    def test_unknown_command_answers_tt_ar_and_is_counted(self):
        # Captured (#29): TT/AR to all ten unassigned base codes.
        self.assertEqual(self.frame(UNASSIGNED), TT_AR)
        self.assertEqual(self.term.unknown, 1)
        self.assertEqual(self.term.last_unknown, UNASSIGNED)

    def test_commands_the_core_doesnt_carry_out_answer_tt_ar(self):
        # oec never sends them; the core answers as for an unknown command.
        for word in (RESET, CLEAR):
            self.assertEqual(self.frame(word), TT_AR)
        self.assertEqual(self.term.unknown, 2)

    def test_empty_frame_gets_no_answer_and_is_not_counted(self):
        self.assertEqual(self.frame(), [])
        self.assertEqual(self.term.unknown, 0)

    def test_data_only_frame_with_no_command_before_it_is_ignored(self):
        self.acknowledge_power_on()
        self.assertEqual(self.frame(*data(0xA0, 0xA1)), TT_AR)
        self.assertEqual(self.term.regen()[:2], b'\x00\x00')

    def test_frames_dont_leak_into_each_other(self):
        self.assertEqual(self.frame(UNASSIGNED), TT_AR)
        self.assertEqual(self.frame(POLL), POWER_ON_RESET)

    def test_buffers_span_the_13_bit_counter(self):
        self.assertEqual(REGEN_SIZE, 8192)
        self.assertEqual(len(self.term.regen()), REGEN_SIZE)
        self.assertEqual(len(self.term.eab()), REGEN_SIZE)

    def test_an_answer_is_cut_to_the_space_given(self):
        self.assertEqual(self.term.frame([READ_EXTENDED_ID], tx_max=2), data(0xC1, 0x34))
        self.assertEqual(self.term.frame([POLL], tx_max=0), [])


class TestAbort(CoreTest):
    """term_rx_abort: the firmware drops a frame broken by a receive overrun."""

    def test_an_aborted_poll_ack_leaves_the_status(self):
        self.term.abort([POLL_ACK])
        self.assertEqual(self.frame(POLL), POWER_ON_RESET)

    def test_an_aborted_load_loads_nothing(self):
        self.load_ac(0x123)
        self.term.abort([LOAD_AC_LO, *data(0x45)])
        self.assertEqual(self.read_ac(), 0x123)

    def test_an_aborted_command_is_not_counted_unknown(self):
        self.term.abort([UNASSIGNED])
        self.assertEqual(self.frame(POLL), POWER_ON_RESET)
        self.assertEqual(self.term.unknown, 0)

    def test_data_after_an_aborted_write_is_not_a_continuation(self):
        # Words may be missing, so the write's place is lost. What arrived
        # before the abort stays written.
        self.load_ac(80)
        self.frame(WRITE_DATA, *data(1))
        self.term.abort(data(2))
        self.assertEqual(self.frame(*data(3)), TT_AR)
        self.assertEqual(self.term.regen()[80:83], bytes([1, 2, 0]))
        self.assertEqual(self.read_ac(), 82)

    def test_the_next_frame_starts_afresh(self):
        self.term.abort([WRITE_DATA, *data(1)])
        self.term.abort()
        self.assertEqual(self.frame(POLL), POWER_ON_RESET)


class TestIdentity(CoreTest):
    def test_terminal_id(self):
        # Captured: 0x04, CUT Model 2, which goes out as 0x010.
        self.assertEqual(self.frame(READ_TERMINAL_ID), [0x010])

    def test_terminal_id_by_model(self):
        # Captured Oct 12 (#110): 06 at 32 x 80, 0E at 43 x 80, each with its parity bit on the wire.
        for (model, word) in ((2, 0x010), (3, 0x01A), (4, 0x038)):
            self.assertEqual(Terminal(model=model).frame([READ_TERMINAL_ID]), [word], model)

    def test_an_unknown_model_answers_model_2(self):
        for model in (0, 1, 5, 255):
            self.assertEqual(Terminal(model=model).frame([READ_TERMINAL_ID]), [0x010], model)

    def test_the_rest_of_the_identity_is_the_same_at_every_model(self):
        # Captured Oct 12: the extended ID and the features don't change with the size.
        frames = [[READ_EXTENDED_ID], [READ_STATUS]] + [[read_feature_id(a)] for a in range(2, 16)]
        model_2 = Terminal(model=2)
        for model in (3, 4):
            other = Terminal(model=model)
            for words in frames:
                self.assertEqual(other.frame(words), model_2.frame(words), (model, words))

    def test_a_reset_takes_the_new_model(self):
        terminal = Terminal(model=2)
        terminal.reset(model=4)
        self.assertEqual((terminal.model, terminal.frame([READ_TERMINAL_ID])), (4, [0x038]))

    def test_extended_id(self):
        # Captured: the IBM 122-key typewriter keyboard.
        self.assertEqual(self.frame(READ_EXTENDED_ID), data(0xC1, 0x34, 0x83, 0x00))

    def test_status(self):
        self.assertEqual(self.frame(READ_STATUS), data(0x30))

    def test_data_words_carry_odd_parity(self):
        self.assertEqual(self.frame(READ_EXTENDED_ID)[3], 0x002)  # 0x00 has no ones

    def test_features_as_captured(self):
        for address in range(2, 16):
            expected = {6: data(0x66), 7: data(0x79)}.get(address, TT_AR)
            self.assertEqual(self.frame(read_feature_id(address)), expected, f'feature {address}')

    def test_commands_at_an_address_with_no_feature_answer_tt_ar(self):
        # Captured (#29): EAB_READ_DATA and EAB_READ_STATUS at f = 2. The core
        # carries them out as the 3483-V does, so they aren't unknown (#117).
        self.assertEqual(self.frame(feature_command(2, 0x3)), TT_AR)
        self.assertEqual(self.frame(feature_command(2, 0xD)), TT_AR)
        self.assertEqual(self.term.unknown, 0)


class TestIdentityWithoutEab(CoreTest):
    eab = False

    def test_no_features(self):
        for address in range(2, 16):
            self.assertEqual(self.frame(read_feature_id(address)), TT_AR, f'feature {address}')

    def test_ids_are_the_same(self):
        self.assertEqual(self.frame(READ_TERMINAL_ID), [0x010])
        self.assertEqual(self.frame(READ_EXTENDED_ID), data(0xC1, 0x34, 0x83, 0x00))


class TestFeatureError(CoreTest):
    """The Feature Error bit (#117), POLL's bit 0, as the 3483-V sets and clears it.

    Captured in captures/20261012-190816-feature-error-bisect.jsonl,
    20261012-190735-feature-error.jsonl and 20261013-062709-feature-error.jsonl.
    Decided Oct 13: a key pending under the bit goes with it on POLL_ACK, as
    on the 3483-V. The tests after the captured ones are the defaults no
    capture shows (docs/superpowers/specs/2026-10-18-feature-error-design.md).
    """

    def setUp(self):
        super().setUp()
        self.acknowledge_power_on()

    def set_it(self):
        self.assertEqual(self.frame(read_feature_id(EMPTY)), TT_AR)

    def clear_it(self):
        self.assertEqual(self.frame(READ_TERMINAL_ID), [0x010])

    def test_read_feature_id_at_an_empty_address_sets_it(self):
        for address in (2, 3, 4, 5, 8, 9, 10, 11, 12, 13, 14, 15):
            self.clear_it()
            self.assertEqual(self.frame(read_feature_id(address)), TT_AR, address)
            self.assertEqual(self.frame(POLL), [FEATURE_ERROR], address)

    def test_features_at_6_and_7_leave_it(self):
        self.assertEqual(self.frame(read_feature_id(6)), data(0x66))
        self.assertEqual(self.frame(read_feature_id(7)), data(0x79))
        self.assertEqual(self.frame(POLL), TT_AR)

    def test_every_feature_command_at_an_empty_address_sets_it(self):
        # Reads (EAB_READ_DATA, EAB_READ_STATUS, EAB_READ_MULTIPLE) and a write (EAB_LOAD_MASK ff).
        frames = ([feature_command(EMPTY, 0x3)], [feature_command(EMPTY, 0xD)], [feature_command(EMPTY, 0xB)],
                  [feature_command(EMPTY, 0x6), *data(0xFF)])
        for words in frames:
            self.clear_it()
            self.assertEqual(self.frame(*words), TT_AR, words)
            self.assertEqual(self.frame(POLL), [FEATURE_ERROR], words)

    def test_commands_at_6_and_7_the_core_doesnt_carry_out_leave_it(self):
        for word in (feature_command(6, 0xD), feature_command(6, 0x3), feature_command(7, 0xD)):
            self.assertEqual(self.frame(word), TT_AR, hex(word))
        self.assertEqual(self.frame(POLL), TT_AR)
        self.assertEqual(self.term.unknown, 3)

    def test_unassigned_base_commands_leave_it(self):
        for code in UNASSIGNED_CODES:
            self.assertEqual(self.frame((code << 2) | 0b01), TT_AR, hex(code))
            self.assertEqual(self.frame(POLL), TT_AR, hex(code))

    def test_poll_shows_it_and_keeps_it(self):
        self.set_it()
        self.assertEqual(self.frame(POLL), [FEATURE_ERROR])
        self.assertEqual(self.frame(POLL), [FEATURE_ERROR])

    def test_poll_ack_clears_it(self):
        self.set_it()
        self.assertEqual(self.frame(POLL), [FEATURE_ERROR])
        self.assertEqual(self.frame(POLL_ACK), TT_AR)
        self.assertEqual(self.frame(POLL), TT_AR)

    def test_read_terminal_id_clears_it(self):
        self.set_it()
        self.clear_it()
        self.assertEqual(self.frame(POLL), TT_AR)

    def test_other_reads_and_loads_neither_show_nor_clear_it(self):
        self.set_it()
        self.frame(LOAD_SECONDARY, *data(0))
        self.frame(LOAD_AC_LO, *data(0))
        self.assertEqual(self.frame(READ_EXTENDED_ID), data(0xC1, 0x34, 0x83, 0x00))
        self.assertEqual(self.frame(READ_STATUS), data(0x30))
        self.assertEqual(self.frame(LOAD_AC_LO, *data(0x50)), TT_AR)
        self.assertEqual(self.frame(POLL), [FEATURE_ERROR])

    def test_the_features_still_answer_while_it_is_set(self):
        self.set_it()
        self.assertEqual(self.frame(read_feature_id(7)), data(0x79))
        self.assertEqual(self.frame(read_feature_id(6)), data(0x66))
        self.assertEqual(self.frame(POLL), [FEATURE_ERROR])

    def test_a_keystroke_under_it_comes_with_bit_0_and_goes_with_it(self):
        # Captured Oct 13: an A, 072, came as 073, and POLL_ACK took both.
        self.term.key(0x1C)
        self.assertEqual(self.frame(POLL), [0x072])
        self.assertEqual(self.frame(POLL), [0x072])
        self.set_it()
        self.assertEqual(self.frame(POLL), [0x073])
        self.assertEqual(self.frame(POLL_ACK), TT_AR)
        self.assertEqual(self.frame(POLL), TT_AR)
        self.assertEqual(self.term.queued, 0)

    def test_oecs_attach(self):
        # oec's feature scan sets it, so its first POLL after the scan answers 0x001.
        term = Terminal()
        self.assertEqual(term.frame([POLL]), POWER_ON_RESET)
        term.frame([POLL_ACK])
        self.assertEqual(term.frame([READ_TERMINAL_ID]), [0x010])
        term.frame([LOAD_SECONDARY, *data(0)])
        term.frame([LOAD_AC_LO, *data(0)])
        term.frame([READ_EXTENDED_ID])
        for address in range(2, 16):
            term.frame([read_feature_id(address)])
        self.assertEqual(term.frame([0x105]), [FEATURE_ERROR])  # POLL, clicker off
        self.assertEqual(term.frame([POLL_ACK]), TT_AR)
        self.assertEqual(term.frame([POLL]), TT_AR)
        # What the console's s shows of it: 12 empty addresses, the last 15.
        self.assertEqual((term.no_feature, term.last_no_feature, term.unknown), (12, read_feature_id(15), 0))

    # The defaults, numbered as the spec's calls.

    def test_a_key_queued_after_an_empty_poll_survives_its_poll_ack(self):
        # 1: the POLL showed no key, so its POLL_ACK takes none.
        self.set_it()
        self.assertEqual(self.frame(POLL), [FEATURE_ERROR])
        self.term.key(0x1C)
        self.assertEqual(self.frame(POLL_ACK), TT_AR)
        self.assertEqual(self.frame(POLL), [0x072])

    def test_a_poll_ack_with_no_poll_before_it_still_takes_the_head(self):
        # 1: as before #117.
        self.term.key(0x1C)
        self.assertEqual(self.frame(POLL_ACK), TT_AR)
        self.assertEqual(self.frame(POLL), TT_AR)

    def test_an_empty_polls_hold_ends_at_its_poll_ack(self):
        # 1: only the POLL_ACK straight after the empty POLL leaves the queue; a bare one after it takes the head.
        self.set_it()
        self.assertEqual(self.frame(POLL), [FEATURE_ERROR])
        self.assertEqual(self.frame(POLL_ACK), TT_AR)
        self.term.key(0x1C)
        self.assertEqual(self.frame(POLL_ACK), TT_AR)
        self.assertEqual(self.frame(POLL), TT_AR)

    def test_the_power_on_reset_under_it(self):
        # 2: the decided rule for any pending status.
        term = Terminal()
        term.frame([read_feature_id(EMPTY)])
        self.assertEqual(term.frame([POLL]), [0x00B])
        self.assertEqual(term.frame([POLL_ACK]), TT_AR)
        self.assertEqual(term.frame([POLL]), TT_AR)
        self.assertEqual(term.queued, 0)

    def test_a_reset_clears_it(self):
        self.set_it()
        self.term.reset()
        self.assertEqual(self.frame(POLL), POWER_ON_RESET)
        self.assertEqual((self.term.no_feature, self.term.last_no_feature), (0, 0))

    def test_an_empty_feature_command_isnt_unknown(self):
        # 4: the core carries it out as the 3483-V does. It counts in no_feature instead, for the console's s.
        self.assertEqual(self.frame(feature_command(EMPTY, 0x3)), TT_AR)
        self.assertEqual(self.term.unknown, 0)
        self.assertEqual((self.term.no_feature, self.term.last_no_feature), (1, feature_command(EMPTY, 0x3)))

    def test_features_and_unknown_commands_dont_count_as_no_feature(self):
        self.frame(read_feature_id(6))
        self.frame(read_feature_id(7))
        self.frame(feature_command(6, 0xD))
        self.frame((0x1F << 2) | 0b01)
        self.assertEqual((self.term.no_feature, self.term.unknown), (0, 2))

    def test_data_after_a_write_at_an_empty_address_is_ignored(self):
        # Not a numbered call but the spec's Answers: nothing there takes it, and a data-only frame after it
        # carries nothing on.
        self.load_ac(80)
        self.assertEqual(self.frame(feature_command(EMPTY, 0xA), *data(0xA0)), TT_AR)
        self.assertEqual(self.frame(*data(0xA1)), TT_AR)
        self.assertEqual(self.term.regen()[80:82], b'\x00\x00')
        self.assertEqual(self.read_ac(), 80)


class TestFeatureErrorWithoutEab(CoreTest):
    """3: with the console's r base the core has no features, so 6 and 7 set it too."""

    eab = False

    def setUp(self):
        super().setUp()
        self.acknowledge_power_on()

    def test_every_feature_address_sets_it(self):
        for address in range(2, 16):
            self.assertEqual(self.frame(READ_TERMINAL_ID), [0x010])
            self.assertEqual(self.frame(read_feature_id(address)), TT_AR, address)
            self.assertEqual(self.frame(POLL), [FEATURE_ERROR], address)


class TestAddressCounter(CoreTest):
    def test_starts_at_zero(self):
        self.assertEqual(self.read_ac(), 0)

    def test_hi_keeps_its_low_five_bits(self):
        # Captured: LOAD 0xFFFF reads back 0x1FFF.
        self.assertEqual(self.frame(LOAD_AC_HI, *data(0xFF)), TT_AR)
        self.assertEqual(self.frame(LOAD_AC_LO, *data(0xFF)), TT_AR)
        self.assertEqual(self.read_ac(), 0x1FFF)

    def test_loading_lo_leaves_hi(self):
        # oec loads only the half that changed.
        self.load_ac(0x7D0)
        self.frame(LOAD_AC_LO, *data(0x10))
        self.assertEqual(self.read_ac(), 0x710)

    def test_loading_hi_leaves_lo(self):
        self.load_ac(0x7D0)
        self.frame(LOAD_AC_HI, *data(0x01))
        self.assertEqual(self.read_ac(), 0x1D0)

    def test_load_without_its_data_byte_changes_nothing(self):
        self.load_ac(0x123)
        self.assertEqual(self.frame(LOAD_AC_LO), TT_AR)
        self.assertEqual(self.read_ac(), 0x123)

    def test_a_load_takes_only_its_first_data_byte(self):
        self.assertEqual(self.frame(LOAD_AC_LO, *data(0x10, 0x20)), TT_AR)
        self.assertEqual(self.read_ac(), 0x010)
        self.frame(LOAD_CONTROL, *data(0x02, 0x04))
        self.assertEqual(self.term.control, 0x02)

    def test_read_data_steps_the_counter(self):
        # Captured (#29): a0 then a1 from 2000, and the counter at 2002.
        self.write_at(2000, 0xA0, 0xA1, 0xA2, 0xA3)
        self.load_ac(2000)
        self.assertEqual(self.frame(READ_DATA), data(0xA0))
        self.assertEqual(self.frame(READ_DATA), data(0xA1))
        self.assertEqual(self.read_ac(), 2002)


class TestBlockReads(CoreTest):
    """READ_EXTENDED_ID and READ_MULTIPLE answer from the counter to the end of
    its block, 4 bytes or 32 with "big", and leave the counter there
    (captured, #29)."""

    ID = (0xC1, 0x34, 0x83, 0x00)

    def test_extended_id_from_0(self):
        self.assertEqual(self.frame(READ_EXTENDED_ID), data(*self.ID))
        self.assertEqual(self.read_ac(), 4)

    def test_extended_id_from_inside_the_block(self):
        self.load_ac(1)
        self.assertEqual(self.frame(READ_EXTENDED_ID), data(0x34, 0x83, 0x00))
        self.assertEqual(self.read_ac(), 4)
        self.load_ac(2)
        self.assertEqual(self.frame(READ_EXTENDED_ID), data(0x83, 0x00))
        self.assertEqual(self.read_ac(), 4)

    def test_extended_id_repeats_every_4_bytes(self):
        self.load_ac(4)
        self.assertEqual(self.frame(READ_EXTENDED_ID), data(*self.ID))
        self.assertEqual(self.read_ac(), 8)
        self.load_ac(2000)
        self.assertEqual(self.frame(READ_EXTENDED_ID), data(*self.ID))
        self.assertEqual(self.read_ac(), 2004)

    def test_big_extended_id(self):
        self.big(True)
        self.load_ac(0x18)
        self.assertEqual(self.frame(READ_EXTENDED_ID), data(*self.ID * 2))
        self.assertEqual(self.read_ac(), 0x20)
        self.load_ac(1)
        self.assertEqual(self.frame(READ_EXTENDED_ID), data(*(self.ID * 8)[1:]))
        self.assertEqual(self.read_ac(), 0x20)

    def test_big_read_from_a_boundary_is_32_words(self):
        # The answer that hangs interface2.
        self.big(True)
        self.assertEqual(self.frame(READ_EXTENDED_ID), data(*self.ID * 8))

    def test_read_multiple(self):
        pattern = list(range(0xA0, 0xC8))
        self.write_at(2000, *pattern)
        self.load_ac(2008)
        self.assertEqual(self.frame(READ_MULTIPLE), data(*pattern[8:12]))
        self.assertEqual(self.read_ac(), 2012)
        self.big(True)
        self.load_ac(2008)
        self.assertEqual(self.frame(READ_MULTIPLE), data(*pattern[8:16]))
        self.assertEqual(self.read_ac(), 2016)

    def test_read_multiple_at_the_top_wraps_to_0(self):
        self.write_at(0x1FFE, 0x11, 0x22)
        self.load_ac(0x1FFE)
        self.assertEqual(self.frame(READ_MULTIPLE), data(0x11, 0x22))
        self.assertEqual(self.read_ac(), 0)


class TestWriteData(CoreTest):
    def test_write_answers_tt_ar_and_advances(self):
        self.load_ac(80)
        self.assertEqual(self.frame(WRITE_DATA, *data(0xA0, 0xA1, 0xA2)), TT_AR)
        self.assertEqual(self.read_ac(), 83)
        self.assertEqual(self.term.regen()[80:83], bytes([0xA0, 0xA1, 0xA2]))

    def test_write_carries_into_hi(self):
        self.load_ac(0x0FE)
        self.frame(WRITE_DATA, *data(1, 2, 3, 4))
        self.assertEqual(self.read_ac(), 0x102)
        self.assertEqual([self.read_data(a) for a in range(0x0FE, 0x102)], [1, 2, 3, 4])

    def test_write_ending_at_1999_leaves_the_counter_at_2000(self):
        # Captured: two bytes from 0x7CE, and the counter reads back 0x7D0.
        self.load_ac(0x7CE)
        self.frame(WRITE_DATA, *data(0xB6, 0xB1))
        self.assertEqual(self.read_ac(), 2000)

    def test_write_past_the_end_keeps_going_and_reads_back(self):
        # Captured: eight bytes from 0x7CC leave the counter at 2004; 2000-2003
        # read back the last four, and nothing reaches 0 or 80.
        self.load_ac(0x7CC)
        self.frame(WRITE_DATA, *data(0xB6, 0xB1, 0xA0, 0xAF, 0xB3, 0xA4, 0xB2, 0xB3))
        self.assertEqual(self.read_ac(), 2004)
        self.assertEqual([self.read_data(a) for a in range(2000, 2004)], [0xB3, 0xA4, 0xB2, 0xB3])
        self.assertEqual([self.read_data(a) for a in (0, 1, 2, 3, 80, 81, 82, 83)], [0] * 8)

    def test_counter_wraps_at_the_top(self):
        # Captured (#29): "WRAP" from 0x1FFE leaves the counter at 2, with "AP" at 0.
        self.write_at(0x1FFE, 0xB6, 0xB1, 0xA0, 0xAF)
        self.assertEqual(self.read_ac(), 2)
        regen = self.term.regen()
        self.assertEqual(regen[0x1FFE:], bytes([0xB6, 0xB1]))
        self.assertEqual(regen[:2], bytes([0xA0, 0xAF]))

    def test_data_only_frames_continue_the_write(self):
        # oec splits a write at 1024 words; the ids trace's clear is 1023 + 977.
        screen = bytes((i * 7) & 0xFF for i in range(2000))
        self.load_ac(0)
        self.assertEqual(self.frame(WRITE_DATA, *data(*screen[:1023])), TT_AR)
        self.assertEqual(self.frame(*data(*screen[1023:])), TT_AR)
        self.assertEqual(self.read_ac(), 2000)
        self.assertEqual(self.term.regen()[:2000], screen)

    def test_continuations_chain(self):
        self.load_ac(80)
        self.frame(WRITE_DATA, *data(1))
        self.frame(*data(2))
        self.frame(*data(3))
        self.assertEqual(self.term.regen()[80:83], bytes([1, 2, 3]))

    def test_data_only_frame_after_a_read_is_ignored(self):
        # Captured (#29): after READ_STATUS, the counter and the buffer stay.
        self.load_ac(80)
        self.frame(WRITE_DATA, *data(1))
        self.frame(READ_STATUS)
        self.assertEqual(self.frame(*data(2, 3)), TT_AR)
        self.assertEqual(self.read_ac(), 81)
        self.assertEqual(self.term.regen()[81], 0)

    def test_data_only_frame_after_a_load_loads_again(self):
        # Captured (#29): after LOAD_ADDRESS_COUNTER_LO(d0), data d4 makes it 0x7D4.
        self.load_ac(2000)
        self.assertEqual(self.frame(*data(0xD4)), TT_AR)
        self.assertEqual(self.read_ac(), 0x7D4)
        self.assertEqual(self.term.regen()[2000], 0)

    def test_each_continuation_of_a_load_takes_its_first_byte(self):
        self.frame(LOAD_CONTROL, *data(0x01))
        self.frame(*data(0x02, 0x04))
        self.assertEqual(self.term.control, 0x02)


class TestControl(CoreTest):
    def test_control_register(self):
        self.assertEqual(self.frame(LOAD_CONTROL, *data(0x03)), TT_AR)
        self.assertEqual(self.term.control, 0x03)

    def test_secondary_control(self):
        self.assertEqual(self.frame(LOAD_SECONDARY, *data(0x01)), TT_AR)
        self.assertEqual(self.term.secondary, 0x01)

    def test_step_inhibit_has_no_effect(self):
        # Captured (#29): bit 4 leaves both a write's and READ_DATA's step alone.
        self.frame(LOAD_CONTROL, *data(0x10))
        self.write_at(2000, 1, 2, 3)
        self.assertEqual(self.read_ac(), 2003)
        self.load_ac(2000)
        self.frame(READ_DATA)
        self.frame(READ_DATA)
        self.assertEqual(self.read_ac(), 2002)


class TestDisplayGeneration(CoreTest):
    def assertChanges(self, *words):
        before = self.term.display_gen
        self.frame(*words)
        self.assertNotEqual(self.term.display_gen, before, [hex(w) for w in words])

    def assertKeeps(self, *words):
        before = self.term.display_gen
        self.frame(*words)
        self.assertEqual(self.term.display_gen, before, [hex(w) for w in words])

    def test_changes_with_what_is_drawn(self):
        self.assertChanges(WRITE_DATA, *data(0xA0))
        self.assertChanges(LOAD_AC_LO, *data(0x50))  # the counter is the cursor
        self.assertChanges(LOAD_AC_HI, *data(0x01))
        self.assertChanges(LOAD_CONTROL, *data(0x02))

    def test_changes_when_a_read_moves_the_counter(self):
        for word in (READ_DATA, READ_MULTIPLE, READ_EXTENDED_ID):
            self.assertChanges(word)

    def test_keeps_on_other_reads_and_polls(self):
        for word in (POLL, POLL_ACK, READ_TERMINAL_ID, READ_AC_LO, READ_STATUS):
            self.assertKeeps(word)


class TestWritten(CoreTest):
    """Whether the controller has written the regen buffer: what ends the splash screen (#53)."""

    def test_not_at_power_on(self):
        self.assertFalse(self.term.written)

    def test_not_by_the_controllers_discovery(self):
        # oec's discovery and setup up to its first write: get_ids, get_features, then
        # Terminal.setup's control register load. The reads and loads move the display
        # generation (the counter is the cursor), but nothing is written yet.
        self.acknowledge_power_on()
        self.frame(READ_TERMINAL_ID)
        self.frame(LOAD_SECONDARY, *data(0x00))
        self.frame(LOAD_AC_LO, *data(0x00))
        self.frame(READ_EXTENDED_ID)
        for address in range(2, 16):
            self.frame(read_feature_id(address))
        self.frame(LOAD_CONTROL, *data(0x00))
        for word in (READ_DATA, READ_MULTIPLE, READ_STATUS, READ_AC_HI, READ_AC_LO):
            self.frame(word)
        self.load_ac(80)
        self.assertNotEqual(self.term.display_gen, 0)
        self.assertFalse(self.term.written)

    def test_a_write_counts(self):
        self.frame(WRITE_DATA, *data(0xA0))
        self.assertTrue(self.term.written)

    def test_a_write_with_no_data_doesnt(self):
        self.frame(WRITE_DATA)
        self.assertFalse(self.term.written)

    def test_a_write_alternate_counts(self):
        self.frame(EAB_WRITE_ALTERNATE, *data(0xA0, 0x11))
        self.assertTrue(self.term.written)


class TestEab(CoreTest):
    def test_load_mask_answers_tt_ar(self):
        self.assertEqual(self.frame(EAB_LOAD_MASK, *data(0xFF)), TT_AR)

    def test_write_alternate_pairs_characters_and_eab_bytes(self):
        self.load_ac(80)
        self.assertEqual(self.frame(EAB_WRITE_ALTERNATE, *data(0xA0, 0x11, 0xA1, 0x22)), TT_AR)
        self.assertEqual(self.read_ac(), 82)
        self.assertEqual(self.term.regen()[80:82], bytes([0xA0, 0xA1]))
        self.assertEqual(self.term.eab()[80:82], bytes([0x11, 0x22]))

    def test_an_odd_split_keeps_the_pairs(self):
        self.load_ac(80)
        self.frame(EAB_WRITE_ALTERNATE, *data(0xA0, 0x11, 0xA1))
        self.frame(*data(0x22, 0xA2, 0x33))
        self.assertEqual(self.read_ac(), 83)
        self.assertEqual(self.term.regen()[80:83], bytes([0xA0, 0xA1, 0xA2]))
        self.assertEqual(self.term.eab()[80:83], bytes([0x11, 0x22, 0x33]))

    def test_oec_clear_with_eab(self):
        # Captured in oec-direct: 4000 bytes in frames of 1022, 1024, 1024 and 930 data words.
        cells = [(0xA0 + i % 26, i & 0xFF) for i in range(2000)]
        stream = [byte for cell in cells for byte in cell]
        self.load_ac(0)
        self.frame(EAB_WRITE_ALTERNATE, *data(*stream[:1022]))
        self.frame(*data(*stream[1022:2046]))
        self.frame(*data(*stream[2046:3070]))
        self.frame(*data(*stream[3070:]))
        self.assertEqual(self.read_ac(), 2000)
        self.assertEqual(self.term.regen()[:2000], bytes(c for (c, _) in cells))
        self.assertEqual(self.term.eab()[:2000], bytes(e for (_, e) in cells))

    def test_a_new_write_alternate_starts_on_a_character(self):
        self.load_ac(80)
        self.frame(EAB_WRITE_ALTERNATE, *data(0xA0))
        self.frame(EAB_WRITE_ALTERNATE, *data(0xA1, 0x22))
        self.assertEqual(self.read_ac(), 81)
        self.assertEqual((self.term.regen()[80], self.term.eab()[80]), (0xA1, 0x22))

    def test_eab_commands_at_another_address_answer_tt_ar(self):
        self.assertEqual(self.frame(feature_command(6, 0xA), *data(1, 2)), TT_AR)
        self.assertEqual(self.term.unknown, 1)
        self.assertEqual(self.term.regen()[0], 0)

    def test_read_data_answers_the_eab_byte(self):
        # Captured (#29): the D7 probe reads back what it wrote.
        self.load_ac(2000)
        self.frame(EAB_WRITE_ALTERNATE, *data(0xA1, 0x55))
        self.load_ac(2000)
        self.assertEqual(self.frame(EAB_READ_DATA), data(0x55))

    def test_read_data_steps_the_counter(self):
        # A default: every capture loads the counter before EAB_READ_DATA. It
        # steps like READ_DATA.
        self.load_ac(2000)
        self.frame(EAB_READ_DATA)
        self.assertEqual(self.read_ac(), 2001)

    def test_the_mask_doesnt_govern_write_alternate(self):
        # Captured (#29): ff under a mask of 0f, over 55, reads back ff.
        self.load_ac(2000)
        self.frame(EAB_WRITE_ALTERNATE, *data(0xA1, 0x55))
        self.frame(EAB_LOAD_MASK, *data(0x0F))
        self.load_ac(2000)
        self.frame(EAB_WRITE_ALTERNATE, *data(0xA1, 0xFF))
        self.load_ac(2000)
        self.assertEqual(self.frame(EAB_READ_DATA), data(0xFF))


class TestEabOff(CoreTest):
    eab = False

    def test_eab_commands_answer_tt_ar_and_do_nothing(self):
        # With no feature at 7 they are feature commands at an empty address:
        # carried out as the 3483-V does, so not unknown (#117).
        self.assertEqual(self.frame(EAB_LOAD_MASK, *data(0xFF)), TT_AR)
        self.assertEqual(self.frame(EAB_WRITE_ALTERNATE, *data(0xA0, 0x11)), TT_AR)
        self.assertEqual(self.frame(EAB_READ_DATA), TT_AR)
        self.assertEqual(self.term.unknown, 0)
        self.assertEqual(self.term.regen()[0], 0)
        self.assertFalse(self.term.written)


class TestWrites(CoreTest):
    """term_writes counts the bytes written to the regen buffer: auto dim's activity (#49)."""

    def test_write_data_and_its_continuation_count_each_byte(self):
        self.load_ac(80)
        self.frame(WRITE_DATA, *data(0xA0, 0xA1))
        self.frame(*data(0xA2))  # a data-only frame carries the write on
        self.assertEqual(self.term.writes, 3)

    def test_eab_write_alternate_counts_each_byte(self):
        self.load_ac(80)
        self.frame(EAB_WRITE_ALTERNATE, *data(0xA0, 0x11))
        self.assertEqual(self.term.writes, 2)

    def test_loads_reads_and_polls_dont(self):
        self.acknowledge_power_on()
        self.load_ac(80)
        self.frame(LOAD_CONTROL, *data(0x02))
        self.frame(READ_DATA)
        self.frame(POLL)
        self.assertEqual(self.term.writes, 0)


if __name__ == '__main__':
    unittest.main()
