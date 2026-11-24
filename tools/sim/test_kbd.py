# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The keyboard translator (firmware/core/keyboard.c), against its rules.
The keymap is us104 unless a test builds its own."""

import random
import unittest

import chords
import core

U = core.usages()
K = core.scan_codes()
LCTRL, LSHIFT, LALT, RCTRL, RSHIFT, RALT = 0x01, 0x02, 0x04, 0x10, 0x20, 0x40
BREAK = 240


class KbdTest(unittest.TestCase):
    def setUp(self):
        self.kb = core.Keyboard()

    def send(self, mods=0, *names, src=0, ms=0):
        """One report from src: the modifier byte and usages by name; the codes it queued."""
        return self.kb.report(mods, [U[name] for name in names], src=src, ms=ms)


class TestReports(KbdTest):
    def test_a_key_sends_its_make_only(self):
        self.assertEqual(self.send(0, 'A'), [K['A']])
        self.assertEqual(self.send(), [])

    def test_shift_passes_through_with_its_release(self):
        self.assertEqual(self.send(LSHIFT), [18])
        self.assertEqual(self.send(LSHIFT, 'A'), [K['A']])
        self.assertEqual(self.send(LSHIFT), [])
        self.assertEqual(self.send(), [BREAK, 18])

    def test_each_side_keeps_its_own_code(self):
        for (bit, code) in ((RSHIFT, 89), (LALT, 25), (RALT, 57)):
            self.assertEqual(self.send(bit), [code])
            self.assertEqual(self.send(), [BREAK, code])

    def test_shift_and_alt_together(self):
        self.assertEqual(self.send(LSHIFT | LALT), [18, 25])
        self.assertEqual(self.send(), [BREAK, 18, BREAK, 25])

    def test_the_spec_example(self):
        # Hold Shift, type ! then {, release Shift ("The translator").
        self.assertEqual(self.send(LSHIFT), [18])
        self.assertEqual(self.send(LSHIFT, '1'), [84])
        self.assertEqual(self.send(LSHIFT), [])
        self.assertEqual(self.send(LSHIFT, 'LBRACKET'), [BREAK, 18, 83])
        self.assertEqual(self.send(LSHIFT), [18])
        self.assertEqual(self.send(), [BREAK, 18])

    def test_an_exact_modifier_is_added_and_taken_away(self):
        self.assertEqual(self.send(0, 'HOME'), [25, K['RULE']])
        self.assertEqual(self.send(), [BREAK, 25])

    def test_an_exact_target_keeps_the_side_already_down(self):
        self.assertEqual(self.send(RSHIFT), [89])
        self.assertEqual(self.send(RSHIFT, '1'), [84])
        self.assertEqual(self.send(RSHIFT), [])
        self.assertEqual(self.send(), [BREAK, 89])

    def test_make_break_keys_release_when_let_go(self):
        self.assertEqual(self.send(LCTRL), [K['RESET']])
        self.assertEqual(self.send(), [BREAK, K['RESET']])
        self.assertEqual(self.send(0, 'CAPS_LOCK'), [K['CAPS']])
        self.assertEqual(self.send(), [BREAK, K['CAPS']])

    def test_right_ctrl_is_enter(self):
        self.assertEqual(self.send(RCTRL), [K['ENTER']])
        self.assertEqual(self.send(), [])

    def test_a_modifier_and_its_chord_in_one_report(self):
        # The Unicomp's top row: Left Shift + F1 in one report is a bare PF13.
        self.assertEqual(self.send(LSHIFT, 'F1'), [K['PF13']])
        self.assertEqual(self.send(), [])

    def test_releases_come_before_presses(self):
        self.assertEqual(self.send(LCTRL), [K['RESET']])
        self.assertEqual(self.send(0, 'A'), [BREAK, K['RESET'], K['A']])

    def test_a_key_moving_slots_is_still_held(self):
        self.assertEqual(self.send(0, 'A'), [K['A']])
        self.assertEqual(self.send(0, 'B', 'A'), [K['B']])
        self.assertEqual(self.send(0, 'A'), [])

    def test_a_modifier_usage_in_the_key_array_is_left_to_the_modifier_byte(self):
        # A keyboard that lists Right Ctrl there too would send two Enters (#62's M1).
        self.assertEqual(self.send(RCTRL, 'RCTRL'), [K['ENTER']])
        self.assertEqual(self.send(), [])
        self.assertEqual(self.send(LCTRL, 'LCTRL'), [K['RESET']])
        self.assertEqual(self.send(), [BREAK, K['RESET']])
        self.assertEqual(self.kb.stats()['presses'], 2)

    def test_shift_in_the_key_array_does_not_end_a_repeat(self):
        self.send(0, 'A', ms=0)
        self.assertEqual(self.send(LSHIFT, 'A', 'LSHIFT', ms=10), [18])
        self.kb.terminal.take_keys()
        self.kb.tick(100000)
        self.assertEqual(self.kb.terminal.take_keys(), [K['A']])
        self.assertEqual(self.kb.stats()['presses'], 1)

    def test_error_rollover_keeps_the_last_state(self):
        self.assertEqual(self.send(0, 'A'), [K['A']])
        self.assertEqual(self.kb.report(0, [U['ROLLOVER']] * 6), [])
        self.assertEqual(self.send(0, 'A'), [])
        self.assertEqual(self.send(), [])

    def test_alt_passes_through_for_the_3483_vs_own_alt_functions(self):
        self.assertEqual(self.send(LALT), [25])
        self.assertEqual(self.send(LALT, 'DELETE'), [K['DELETE']])  # DelWd
        self.assertEqual(self.send(LALT), [])
        self.assertEqual(self.send(), [BREAK, 25])

    def test_nothing_and_local_keys_send_nothing(self):
        self.assertEqual(self.send(0, 'RBRACKET'), [])
        self.assertEqual(self.send(), [])
        self.assertEqual(self.send(LSHIFT | LALT), [18, 25])
        self.assertEqual(self.send(LSHIFT | LALT, 'X'), [])  # SetUp
        self.assertEqual(self.send(LSHIFT | LALT), [])
        self.assertEqual(self.kb.stats()['local'], 1)


class TestReviewFocus(KbdTest):
    def test_rollover_past_a_remapped_key_gets_the_real_shift(self):
        self.assertEqual(self.send(LSHIFT), [18])
        self.assertEqual(self.send(LSHIFT, 'LBRACKET'), [BREAK, 18, 83])
        self.assertEqual(self.send(LSHIFT, 'LBRACKET', 'A'), [18, K['A']])
        self.assertEqual(self.send(LSHIFT, 'A'), [])
        self.assertEqual(self.send(LSHIFT), [])
        self.assertEqual(self.send(), [BREAK, 18])

    def test_two_sources_share_shift(self):
        self.kb.attach(1)
        self.assertEqual(self.send(LSHIFT, src=0), [18])
        self.assertEqual(self.send(LSHIFT, src=1), [])
        self.assertEqual(self.send(0, src=0), [])
        self.assertEqual(self.send(0, 'A', src=0), [K['A']])  # still capital: source 1 holds Shift
        self.assertEqual(self.send(0, src=1), [BREAK, 18])

    def test_modifier_changes_wait_for_an_exact_key(self):
        self.assertEqual(self.send(LSHIFT), [18])
        self.assertEqual(self.send(LSHIFT, 'LBRACKET'), [BREAK, 18, 83])
        self.assertEqual(self.send(LSHIFT | LALT, 'LBRACKET'), [])
        self.assertEqual(self.send(LSHIFT | LALT), [18, 25])
        self.assertEqual(self.send(), [BREAK, 18, BREAK, 25])


class TestSources(KbdTest):
    def test_release_all_lets_go_of_everything_on_its_source(self):
        self.assertEqual(self.send(LSHIFT), [18])
        self.assertEqual(self.send(LSHIFT | LCTRL, 'A'), [K['RESET'], K['A']])
        self.kb.release_all(0)
        self.assertEqual(self.kb.terminal.take_keys(), [18, K['RESET'], K['A'], BREAK, K['RESET'], BREAK, 18])
        self.assertEqual(self.send(LSHIFT, 'A'), [18, K['A']])  # a fresh start, still attached

    def test_detach_forgets_the_source(self):
        self.assertEqual(self.send(LSHIFT), [18])
        self.kb.detach(0)
        self.assertEqual(self.kb.terminal.take_keys(), [18, BREAK, 18])
        self.assertEqual(self.send(LSHIFT, 'A'), [])

    def test_an_unattached_source_is_ignored(self):
        self.assertEqual(self.send(0, 'A', src=2), [])
        self.assertEqual(self.send(0, 'A', src=9), [])

    def test_forgetting_a_source_stops_its_repeat(self):
        # usb_host.c forgets an unplugged keyboard this way while a console
        # reset is pending: its held key must not repeat on.
        self.send(0, 'A', ms=0)
        self.kb.terminal.take_keys()
        core.library().kbd_attach(self.kb._state, 0, None)
        self.kb.tick(100000)
        self.assertEqual(self.kb.terminal.take_keys(), [])


class TestSharedKeys(KbdTest):
    """A make/break key goes down once, however many held keys send it, and up when the last of them is
    let go (#62's M4)."""

    def test_two_keyboards_holding_caps_lock(self):
        self.kb.attach(1)
        self.assertEqual(self.send(0, 'CAPS_LOCK', src=0), [K['CAPS']])
        self.assertEqual(self.send(0, 'CAPS_LOCK', src=1), [])
        self.assertEqual(self.send(src=0), [])
        self.assertEqual(self.send(src=1), [BREAK, K['CAPS']])

    def test_two_keyboards_holding_left_ctrl(self):
        self.kb.attach(1)
        self.assertEqual(self.send(LCTRL, src=0), [K['RESET']])
        self.assertEqual(self.send(LCTRL, src=1), [])
        self.assertEqual(self.send(src=1), [])
        self.assertEqual(self.send(src=0), [BREAK, K['RESET']])

    def test_two_keys_on_one_keyboard(self):
        km = core.km()
        overlay = core.build_keymap([(U['F2'], km['ANY'], K['CAPS'], km['KEEP'])],
                                    base=core.keymap_named('us104'), name='two-caps')
        self.kb = core.Keyboard(keymap=overlay)
        self.assertEqual(self.send(0, 'CAPS_LOCK'), [K['CAPS']])
        self.assertEqual(self.send(0, 'CAPS_LOCK', 'F2'), [])
        self.assertEqual(self.send(0, 'F2'), [])
        self.assertEqual(self.send(), [BREAK, K['CAPS']])

    def test_a_keyboard_unplugged_leaves_it_to_the_other(self):
        self.kb.attach(1)
        self.send(0, 'CAPS_LOCK', src=0)
        self.send(0, 'CAPS_LOCK', src=1)
        self.kb.detach(0)
        self.assertEqual(self.kb.terminal.take_keys(), [K['CAPS']])
        self.assertEqual(self.send(src=1), [BREAK, K['CAPS']])

    def test_a_dropped_press_leaves_the_make_to_the_next(self):
        self.kb.attach(1)
        for letter in 'ABDEFGHIJKLMN':  # 13 queued
            self.send(0, letter)
            self.send()
        self.send(0, 'O')  # 14 queued
        self.assertEqual(self.send(0, 'CAPS_LOCK', src=0), [])  # one more would leave 17 free
        self.kb.terminal.take_keys()
        self.assertEqual(self.send(0, 'CAPS_LOCK', src=1), [K['CAPS']])
        self.assertEqual(self.send(src=1), [BREAK, K['CAPS']])
        self.assertEqual(self.send(src=0), [])


class TestResync(KbdTest):
    """kbd_resync releases only the modifiers the controller may hold down: one made since the queue was last
    seen empty, or down then. A reset with nothing typed queues nothing, as the 3483-V does (the rig replays)."""

    def reset(self):
        self.kb.terminal.reset()
        self.kb.terminal.take_keys()  # the power-on reset
        self.kb.resync()
        return self.kb.terminal.take_keys()

    def delivered(self):
        """The controller takes everything queued, and the main loop ticks."""
        self.kb.terminal.take_keys()
        self.kb.tick(0)

    def test_a_reset_with_nothing_typed_queues_nothing(self):
        self.assertEqual(self.reset(), [])

    def test_a_shift_make_the_reset_wiped_goes_in_again(self):
        self.assertEqual(self.send(LSHIFT), [18])
        self.assertEqual(self.reset(), [BREAK, 18, 18])
        self.assertEqual(self.send(LSHIFT, 'A'), [K['A']])

    def test_a_shift_release_the_reset_wiped_goes_in_again(self):
        self.send(LSHIFT)
        self.kb.terminal.take_keys()  # the controller holds Shift
        self.assertEqual(self.send(), [BREAK, 18])
        self.assertEqual(self.reset(), [BREAK, 18])

    def test_a_shift_the_controller_holds_is_released_and_made_again(self):
        self.send(LSHIFT)
        self.delivered()
        self.assertEqual(self.reset(), [BREAK, 18, 18])

    def test_modifiers_the_controller_has_let_go_are_not_released_again(self):
        self.send(LSHIFT | LALT)
        self.send(LSHIFT | LALT, 'A')
        self.send()
        self.delivered()
        self.assertEqual(self.reset(), [])

    def test_a_tick_with_codes_still_queued_forgets_nothing(self):
        self.send(LSHIFT)
        self.kb.terminal.take_keys()
        self.send()  # Shift's release waits
        self.kb.tick(0)
        self.assertEqual(self.reset(), [BREAK, 18])

    def test_a_resync_the_next_reset_wiped_goes_in_again(self):
        self.send(RALT)
        self.delivered()
        self.send()
        self.assertEqual(self.reset(), [BREAK, 57])
        self.kb.terminal.reset()  # wipes the resync's release before the controller takes it
        self.kb.terminal.take_keys()
        self.kb.resync()
        self.assertEqual(self.kb.terminal.take_keys(), [BREAK, 57])


class TestStats(KbdTest):
    def test_counts(self):
        self.send(LSHIFT)
        self.send(LSHIFT, 'A')
        self.send()
        self.assertEqual(self.kb.stats(), {'presses': 1, 'repeats': 0, 'drops': 0, 'local': 0, 'codes': 4,
                                           'lost': 0})
        self.kb.clear_stats()
        self.assertEqual(self.kb.stats(), {'presses': 0, 'repeats': 0, 'drops': 0, 'local': 0, 'codes': 0,
                                           'lost': 0})

    def test_the_count_goes_beyond_the_callers_buffer(self):
        self.send(LSHIFT)
        self.assertEqual(self.kb.report(LSHIFT, [U['LBRACKET']], sent_max=1), [BREAK])
        self.assertEqual(self.kb.last_count, 3)
        self.assertEqual(self.kb.terminal.take_keys(), [18, BREAK, 18, 83])

    def test_keystrokes_count_presses_and_repeats_not_shift_or_alt(self):
        self.send(LSHIFT)
        self.send(LALT)
        self.send()
        self.assertEqual(self.kb.keystrokes, 0)
        self.send(0, 'A', ms=1000)
        self.kb.terminal.take_keys()
        (delay, _) = core.typematic_timing()[core.keys3483()[K['A']]['repeat']]
        self.kb.tick(1000 + delay)
        self.assertEqual(self.kb.stats()['repeats'], 1)
        self.assertEqual(self.kb.keystrokes, 2)

    def test_keys_that_send_nothing_are_keystrokes_too(self):
        self.send(0, 'RBRACKET')  # no code in us104
        self.send()
        self.send(LSHIFT | LALT)
        self.send(LSHIFT | LALT, 'X')  # SetUp, a local function
        self.assertEqual(self.kb.keystrokes, 2)

    def test_reset_and_caps_lock_click_no_more_than_shift_and_alt(self):
        # The 3483-V clicks for no key that sends a release (#18).
        self.send(LCTRL)  # Reset
        self.send()
        self.send(0, 'CAPS_LOCK')
        self.send()
        self.send(RSHIFT | RALT)
        self.send()
        self.assertEqual(self.kb.keystrokes, 0)
        self.send(RCTRL)  # Enter
        self.assertEqual(self.kb.keystrokes, 1)

    def test_keystrokes_survive_clear_stats(self):
        self.send(0, 'A')
        self.send()
        self.send(0, 'B')
        self.kb.clear_stats()
        self.assertEqual(self.kb.keystrokes, 2)
        self.send()
        self.send(0, 'C')
        self.assertEqual((self.kb.stats()['presses'], self.kb.keystrokes), (1, 3))


class TestRulePresses(KbdTest):
    """Bare Rule presses, which turn the ruler on and off (#51). On the 3483-V only Rule does it; Alt+Rule is
    Home to oec."""

    def test_shift_home_is_rule_and_counts(self):
        self.assertEqual(self.send(LSHIFT), [18])
        self.assertEqual(self.send(LSHIFT, 'HOME'), [BREAK, 18, K['RULE']])
        self.assertEqual(self.kb.rule_presses, 1)

    def test_home_is_alt_rule_and_doesnt(self):
        self.assertEqual(self.send(0, 'HOME'), [25, K['RULE']])
        self.assertEqual(self.kb.rule_presses, 0)

    def test_shift_doesnt_matter_and_alt_does(self):
        km = core.km()
        # Both chords named: an exact chord finds the overlay's entry before us104's (Shift+F2 is PF14 there).
        keeps = core.build_keymap([(U['F2'], km['SHIFT'], K['RULE'], km['KEEP']),
                                   (U['F2'], km['ALT'], K['RULE'], km['KEEP'])],
                                  base=core.keymap_named('us104'), name='rule-keeps')
        self.kb = core.Keyboard(keymap=keeps)
        self.send(LSHIFT)
        self.assertEqual(self.send(LSHIFT, 'F2'), [K['RULE']])  # Shift kept, Alt up
        self.assertEqual(self.kb.rule_presses, 1)
        self.send(LSHIFT)
        self.send()
        self.send(LALT)
        self.assertEqual(self.send(LALT, 'F2'), [K['RULE']])  # Alt kept: Home to oec
        self.assertEqual(self.kb.rule_presses, 1)

    def test_a_press_dropped_for_a_full_queue_still_counts(self):
        for letter in 'ABCDEFGHIJKLMN':  # 14 queued: a press now would leave fewer than 18 free
            self.send(0, letter)
            self.send()
        self.assertEqual(self.send(LSHIFT, 'HOME'), [])
        self.assertEqual(self.kb.stats()['drops'], 1)
        self.assertEqual(self.kb.rule_presses, 1)

    def test_a_press_that_wakes_auto_dim_is_swallowed_and_doesnt(self):
        dim = core.Dim()
        dim.now()
        (mods, usages) = dim.report(LSHIFT, [U['HOME']])
        self.assertTrue(dim.took)
        self.kb.report(mods, usages)
        self.assertEqual(self.kb.rule_presses, 0)

    def test_each_press_counts_once_and_clear_stats_leaves_them(self):
        for _ in range(3):
            self.send(LSHIFT, 'HOME')
            self.send(LSHIFT)
        self.kb.clear_stats()
        self.assertEqual(self.kb.rule_presses, 3)


class TestTypematic(KbdTest):
    def setUp(self):
        super().setUp()
        self.keys = core.keys3483()
        self.timing = core.typematic_timing()
        self.none = core.repeat_classes()['NONE']

    def timing_of(self, code):
        cls = self.keys[code]['repeat']
        if cls == self.none:
            self.fail(f"{self.keys[code]['label']} doesn't repeat in the capture")
        return self.timing[cls]

    def take(self):
        return self.kb.terminal.take_keys()

    def test_a_held_key_repeats_after_its_delay_then_each_period(self):
        (delay, period) = self.timing_of(K['A'])
        self.send(0, 'A', ms=1000)
        self.assertEqual(self.take(), [K['A']])
        self.kb.tick(1000 + delay - 1)
        self.assertEqual(self.take(), [])
        self.kb.tick(1000 + delay)
        self.assertEqual(self.take(), [K['A']])
        self.kb.tick(1000 + delay + period - 1)
        self.assertEqual(self.take(), [])
        self.kb.tick(1000 + delay + period)
        self.assertEqual(self.take(), [K['A']])
        self.assertEqual(self.kb.stats()['repeats'], 2)

    def test_letting_go_stops_it(self):
        (delay, _) = self.timing_of(K['A'])
        self.send(0, 'A', ms=0)
        self.send(ms=10)
        self.take()
        self.kb.tick(delay * 10)
        self.assertEqual(self.take(), [])

    def test_a_new_press_takes_over_and_nothing_resumes(self):
        (delay, _) = self.timing_of(K['B'])
        self.send(0, 'A', ms=0)
        self.send(0, 'A', 'B', ms=100)
        self.take()
        self.kb.tick(100 + delay)
        self.assertEqual(self.take(), [K['B']])
        self.send(0, 'A', ms=200)
        self.kb.tick(100000)
        self.assertEqual(self.take(), [])

    def test_shift_does_not_interrupt_it(self):
        (delay, _) = self.timing_of(K['A'])
        self.send(0, 'A', ms=0)
        self.assertEqual(self.send(LSHIFT, 'A', ms=10), [18])
        self.take()
        self.kb.tick(delay)
        self.assertEqual(self.take(), [K['A']])

    def test_a_repeat_waits_while_two_statuses_are_queued(self):
        (delay, period) = self.timing_of(K['A'])
        self.kb.terminal.key(K['B'])
        self.send(0, 'A', ms=0)  # its make is still queued, behind B
        self.kb.tick(delay)
        self.assertEqual(self.take(), [K['B'], K['A']])  # no repeat behind them
        self.kb.tick(delay + 1)  # it goes in as soon as there is room
        self.assertEqual(self.take(), [K['A']])
        self.kb.tick(delay + period)
        self.assertEqual(self.take(), [])
        self.kb.tick(delay + 1 + period)
        self.assertEqual(self.take(), [K['A']])

    def test_the_right_arrow_keeps_its_rate_under_oecs_polls(self):
        # oec POLLs every 1/15 s, up to three deep. Into an empty queue only,
        # the right arrow repeated 15 times a second, not 20.
        (delay, period) = self.timing_of(K['RIGHT'])
        self.send(0, 'RIGHT', ms=0)
        (codes, next_poll) = ([], 0.0)
        for ms in range(3000):
            self.kb.tick(ms)
            if ms >= next_poll:
                next_poll += 1000 / 15
                codes += self.kb.terminal.take_keys(3)
        codes += self.take()
        self.assertEqual(len(codes) - 1, (2999 - delay) // period + 1)

    def test_a_late_tick_sends_one_repeat(self):
        (delay, period) = self.timing_of(K['A'])
        self.send(0, 'A', ms=0)
        self.take()
        late = delay + 10 * period
        self.kb.tick(late)
        self.assertEqual(self.take(), [K['A']])
        self.kb.tick(late + period - 1)
        self.assertEqual(self.take(), [])
        self.kb.tick(late + period)
        self.assertEqual(self.take(), [K['A']])

    def test_a_key_that_never_repeats(self):
        self.assertEqual(self.keys[K['PRINT']]['repeat'], self.none)  # no hold: never repeats
        self.send(0, 'PRINT_SCREEN', ms=0)
        self.take()
        self.kb.tick(100000)
        self.assertEqual(self.take(), [])

    def test_a_remapped_key_repeats_its_bare_make_with_shift_still_lifted(self):
        (delay, _) = self.timing_of(K['BRACE'])
        self.send(LSHIFT)
        self.send(LSHIFT, 'LBRACKET', ms=0)
        self.take()
        self.kb.tick(delay)
        self.assertEqual(self.take(), [K['BRACE']])
        self.assertEqual(self.send(LSHIFT, ms=delay + 1), [18])

    def test_a_repeat_brings_back_a_refused_shift(self):
        # A Shift make refused while a key repeats goes in before the next repeat.
        (delay, _) = self.timing_of(K['A'])
        for letter in 'BCDEFGHIJKLMN':  # 13 queued
            self.send(0, letter)
            self.send()
        self.send(0, 'A', ms=0)  # 14 queued
        self.assertEqual(self.send(LSHIFT, 'A', ms=10), [])  # one more would leave 17 free
        self.take()
        self.kb.tick(delay)
        self.assertEqual(self.take(), [18, K['A']])
        self.assertEqual(self.send(0, 'A', ms=delay + 1), [BREAK, 18])

    def test_the_right_arrow_uses_its_own_class(self):
        (delay, period) = self.timing_of(K['RIGHT'])
        self.send(0, 'RIGHT', ms=0)
        self.take()
        self.kb.tick(delay)
        self.kb.terminal.take_keys()
        self.kb.tick(delay + period)
        self.assertEqual(self.take(), [K['RIGHT']])


class TestTypematicSettings(KbdTest):
    """SetUp's Typematic Rate and Delay (#107): the first repeat by Delay, the period by Rate."""

    def take(self):
        return self.kb.terminal.take_keys()

    def check_hold(self, key, first, period, start=0):
        self.send(0, key, ms=start)
        self.assertEqual(self.take(), [K[key]])
        for (ms, codes) in ((start + first - 1, []), (start + first, [K[key]]),
                            (start + first + period - 1, []), (start + first + period, [K[key]])):
            self.kb.tick(ms)
            self.assertEqual(self.take(), codes, (key, ms))
        self.send(ms=start + first + period + 1)

    def test_it_starts_at_normal_and_normal(self):
        (first, period) = core.typematic_timing()[core.keys3483()[K['A']]['repeat']]
        self.assertEqual(core.typematic_timing(), core.typematic_timing(0, 1))
        self.check_hold('A', first, period)

    def test_each_rate_and_delay(self):
        for rate in range(2):
            for delay in range(3):
                for key in ('A', 'UP', 'RIGHT'):
                    with self.subTest(rate=rate, delay=delay, key=key):
                        self.kb = core.Keyboard()
                        self.kb.typematic(rate, delay)
                        (first, period) = core.typematic_timing(rate, delay)[core.keys3483()[K[key]]['repeat']]
                        self.check_hold(key, first, period)

    def test_a_change_mid_hold_waits_for_the_next_press(self):
        normal = core.typematic_timing(0, 1)[core.keys3483()[K['A']]['repeat']]
        fast_short = core.typematic_timing(1, 0)[core.keys3483()[K['A']]['repeat']]
        self.send(0, 'A', ms=0)
        self.take()
        self.kb.typematic(1, 0)  # Fast and Short while A is held
        self.kb.tick(normal[0])
        self.assertEqual(self.take(), [K['A']])
        self.kb.tick(normal[0] + normal[1] - 1)
        self.assertEqual(self.take(), [])
        self.kb.tick(normal[0] + normal[1])
        self.assertEqual(self.take(), [K['A']])
        self.send(ms=5000)
        self.check_hold('A', *fast_short, start=6000)

    def test_it_says_what_it_times_by(self):
        # u's kbd line reads them back (#107), so the bench can see SetUp's change reach the translator.
        self.assertEqual((self.kb.rate, self.kb.delay), (0, 1))
        self.kb.typematic(1, 2)
        self.assertEqual((self.kb.rate, self.kb.delay), (1, 2))
        self.kb.typematic(2, 3)
        self.assertEqual((self.kb.rate, self.kb.delay), (1, 2))

    def test_a_value_setup_doesnt_offer_changes_nothing(self):
        self.kb.typematic(2, 3)
        self.check_hold('A', *core.typematic_timing(0, 1)[core.keys3483()[K['A']]['repeat']])


class TestReserve(KbdTest):
    LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

    def test_presses_stop_short_of_the_reserve_and_a_release_still_goes_in(self):
        self.assertEqual(self.send(LSHIFT), [18])  # 1 queued
        sent = []
        for letter in self.LETTERS[:14]:
            sent.append(self.send(LSHIFT, letter))
            self.send(LSHIFT)
        self.assertEqual(sent[:13], [[K[letter]] for letter in self.LETTERS[:13]])
        self.assertEqual(sent[13], [])  # 14 queued: one more would leave 17 free
        self.assertEqual(self.kb.stats()['drops'], 1)
        self.assertEqual(self.send(), [BREAK, 18])
        self.assertEqual(self.kb.terminal.queued, 16)

    def test_a_refused_shift_does_not_spend_the_reserve(self):
        # The final review's reproduction: a Shift make refused as a press went
        # in on the next report as a restore, three reserve slots a round,
        # until a release no longer fitted and Shift stayed down.
        self.send(LSHIFT)
        for letter in self.LETTERS[:13]:
            self.send(LSHIFT, letter)
            self.send(LSHIFT)
        self.send()  # 16 queued
        for _ in range(6):
            self.send(LSHIFT)
            self.send(LSHIFT, 'A')
            self.send(0, 'A')
            self.send()
        self.assertEqual(chords.problems(self.kb.terminal.take_keys()), [])

    def test_a_press_is_queued_whole_or_not_at_all(self):
        for letter in self.LETTERS[:12]:
            self.send(0, letter)
            self.send()
        self.assertEqual(self.send(LSHIFT), [18])  # 13 queued, 19 free
        self.assertEqual(self.send(LSHIFT, 'LBRACKET'), [])  # needs 3: would leave 16
        self.assertEqual(self.kb.terminal.queued, 13)
        self.assertEqual(self.send(LSHIFT), [])  # nothing to restore: nothing was sent
        self.assertEqual(self.kb.stats()['drops'], 1)

    def test_releases_fit_after_the_queue_fills(self):
        everything = LSHIFT | RSHIFT | LALT | RALT
        held = everything | LCTRL
        self.assertEqual(self.send(everything), [18, 89, 25, 57])
        self.assertEqual(self.send(held), [K['RESET']])
        self.assertEqual(self.send(held, 'CAPS_LOCK'), [K['CAPS']])  # 6 queued, every make/break key down
        sent = []
        for letter in 'ABDEFGHIJ':  # not C or X, which have Alt chords
            sent.append(self.send(held, 'CAPS_LOCK', letter))
            self.send(held, 'CAPS_LOCK')
        self.assertEqual(sent[:8], [[K[letter]] for letter in 'ABDEFGHI'])
        self.assertEqual(sent[8], [])  # 14 queued: one more would leave 17 free
        self.assertEqual(self.kb.stats()['drops'], 1)
        self.assertEqual(self.send(), [BREAK, K['CAPS'], BREAK, K['RESET'], BREAK, 18, BREAK, 89, BREAK, 25,
                                       BREAK, 57])
        self.assertEqual(self.kb.terminal.queued, 26)


class TestLost(KbdTest):
    def test_three_keyboards_holding_the_same_keys_lose_no_release(self):
        # Each holds Caps Lock and Left Ctrl (Reset), but each key is down once,
        # so the reserve holds every release. Before #62's M4 these three needed
        # 20 slots, and one release was lost.
        self.kb = core.Keyboard(sources=(0, 1, 2))
        everything = LSHIFT | RSHIFT | LALT | RALT
        self.send(everything)
        for src in range(3):
            mods = everything if src == 0 else 0
            self.send(mods, 'CAPS_LOCK', src=src)
            self.send(mods | LCTRL, 'CAPS_LOCK', src=src)
        for letter in 'ABDEFGHIJ':  # not C or X, which have Alt chords
            self.send(everything | LCTRL, 'CAPS_LOCK', letter)
            self.send(everything | LCTRL, 'CAPS_LOCK')
        self.assertEqual((self.kb.terminal.queued, self.kb.stats()['drops']), (14, 1))
        for src in range(3):
            self.send(src=src)
        self.assertEqual(self.kb.terminal.queued, 26)
        self.assertEqual(self.kb.stats()['lost'], 0)
        self.assertEqual(chords.problems(self.kb.terminal.take_keys()), [])

    def test_a_release_that_does_not_fit_is_counted(self):
        # Only statuses queued past the translator can fill the reserve now.
        self.send(0, 'CAPS_LOCK')
        while self.kb.terminal.key(K['A']):
            pass
        self.send()
        self.assertEqual(self.kb.stats()['lost'], 1)


class TestReserveProperty(unittest.TestCase):
    """Random typing on three keyboards while polling stops and starts: whatever
    the controller got, nothing may be made twice or left down once every key
    is let go, and no release lost. Every keyboard has every modifier, Caps
    Lock among its keys, and Left Ctrl for Reset, since each make/break key is
    down once however many hold it (#62's M4)."""

    MODS = (0x01, 0x02, 0x04, 0x10, 0x20, 0x40)
    KEYS = {0: ('A', 'B', 'LBRACKET', 'HOME', 'F1', 'CAPS_LOCK', '1', 'END'),
            1: ('A', 'C', 'LBRACKET', 'CAPS_LOCK', '1'),
            2: ('B', 'HOME', 'CAPS_LOCK', 'END')}

    def run_seed(self, seed):
        rng = random.Random(seed)
        kb = core.Keyboard(sources=(0, 1, 2))
        state = {src: [0, set()] for src in range(3)}
        (stream, polling, ms) = ([], True, 0)
        for _ in range(80):
            src = rng.randrange(3)
            (mods, keys) = state[src]
            roll = rng.random()
            if roll < 0.35:
                mods ^= rng.choice(self.MODS)
            elif roll < 0.7 and len(keys) < 6:
                keys.add(U[rng.choice(self.KEYS[src])])
            elif keys:
                keys.discard(rng.choice(sorted(keys)))
            state[src] = [mods, keys]
            ms += rng.randrange(1, 300)
            kb.report(mods, sorted(keys), src=src, ms=ms)
            kb.tick(ms)
            if rng.random() < 0.15:
                polling = not polling
            if polling:
                stream += kb.terminal.take_keys(rng.randrange(1, 4))
        for src in range(3):
            kb.report(0, (), src=src, ms=ms)
        lost = kb.stats()['lost']
        return chords.problems(stream + kb.terminal.take_keys()) + ([f'lost={lost}'] if lost else [])

    def test_random_typing_leaves_nothing_down(self):
        failures = [(seed, found) for seed in range(400) for found in [self.run_seed(seed)] if found]
        self.assertEqual(failures[:3], [], f'{len(failures)} of 400 seeds')


class TestCtrlChords(KbdTest):
    def setUp(self):
        km = core.km()
        overlay = core.build_keymap([(U['F2'], km['CTRL'], K['CRSEL'], km['NONE'])],
                                    base=core.keymap_named('us104'), name='ctrl-overlay')
        self.kb = core.Keyboard(keymap=overlay)

    def test_ctrl_in_the_same_report_is_part_of_the_chord(self):
        self.assertEqual(self.send(LCTRL, 'F2'), [K['CRSEL']])
        self.assertEqual(self.send(), [])
        self.assertEqual(self.kb.stats()['presses'], 1)

    def test_ctrl_pressed_first_is_reset(self):
        self.assertEqual(self.send(LCTRL), [K['RESET']])
        self.assertEqual(self.send(LCTRL, 'F2'), [K['PF2']])
        self.assertEqual(self.send(LCTRL), [])
        self.assertEqual(self.send(), [BREAK, K['RESET']])

    def test_ctrl_with_a_key_that_has_no_ctrl_chord_is_reset(self):
        self.assertEqual(self.send(LCTRL, 'A'), [K['RESET'], K['A']])
        self.assertEqual(self.send(), [BREAK, K['RESET']])

    def test_us104_has_no_ctrl_chords(self):
        kb = core.Keyboard()
        self.assertEqual(kb.report(LCTRL, [U['F2']]), [K['RESET'], K['PF2']])


class TestLocalMode(KbdTest):
    """SetUp's local mode (#102): every key but Shift and Alt to SetUp, nothing to the controller, as the 3483-V's
    SetUp sends only Shift's and Alt's makes and releases (captured Oct 11)."""

    def test_setup_turns_it_on_in_the_same_report(self):
        self.assertEqual(self.send(LSHIFT | LALT), [18, 25])
        self.assertEqual(self.send(LSHIFT | LALT, 'X', 'A'), [])  # A straight after SetUp, in the same report
        self.assertTrue(self.kb.local_on)
        self.assertEqual(self.kb.local_keys(), [K['SETUP'], K['A']])
        self.assertEqual(self.kb.stats()['local'], 1)

    def test_shift_and_alt_still_reach_the_controller(self):
        self.send(LSHIFT | LALT)
        self.send(LSHIFT | LALT, 'X')
        self.assertEqual(self.send(LSHIFT | LALT), [])
        self.assertEqual(self.send(), [BREAK, 18, BREAK, 25])
        self.assertEqual(self.send(LALT), [25])
        self.assertEqual(self.send(), [BREAK, 25])

    def test_keys_go_to_setup_and_nothing_to_the_queue(self):
        self.kb.local(True)
        for name in ('DOWN', 'SPACE', 'F3', 'ENTER'):
            self.assertEqual(self.send(0, name), [])
            self.assertEqual(self.send(), [])
        self.assertEqual(self.kb.local_keys(), [K['DOWN'], K['SPACE'], K['PF3'], K['ENTER']])
        self.assertEqual(self.kb.terminal.take_keys(), [])

    def test_the_keys_that_send_a_release_send_none(self):
        self.kb.local(True)
        self.assertEqual(self.send(LCTRL), [])   # Reset
        self.assertEqual(self.send(), [])
        self.assertEqual(self.send(0, 'CAPS_LOCK'), [])
        self.assertEqual(self.send(), [])
        self.assertEqual(self.kb.local_keys(), [K['RESET'], K['CAPS']])

    def test_an_unmapped_key_reaches_setup_as_nothing(self):
        self.kb.local(True)
        self.send(0, 'RBRACKET')   # no code in us104
        self.assertEqual(self.kb.local_keys(), [K['NOTHING']])

    def test_rule_doesnt_toggle_the_ruler(self):
        self.kb.local(True)
        self.send(LSHIFT, 'HOME')  # us104's bare Rule
        self.assertEqual(self.kb.rule_presses, 0)
        self.assertEqual(self.kb.local_keys(), [K['RULE']])

    def test_in_local_mode_a_logged_report_loses_its_keys(self):
        # The console's u log and u's last= show each report (#122): what's typed into Password Set or at the
        # lock's prompt mustn't show there. The modifiers stay: Shift and Alt reach the controller anyway.
        self.kb.local(True)
        self.assertEqual(self.kb.redact(LSHIFT, ['A', 'B']), (LSHIFT, [0] * 6))

    def test_out_of_local_mode_a_logged_report_is_as_it_came(self):
        self.assertEqual(self.kb.redact(LSHIFT, ['A', 'B']), (LSHIFT, [U['A'], U['B'], 0, 0, 0, 0]))

    def test_each_key_carries_shift_as_the_3483v_would_send_it(self):
        # Password Set and the lock count case (#122), so a local key keeps its Shift.
        self.kb.local(True)
        self.send(0, 'A')
        self.send()
        self.send(LSHIFT)
        self.send(LSHIFT, 'A')
        self.send(LSHIFT)
        self.send()
        self.assertEqual(self.kb.local_entries(), [(K['A'], False), (K['A'], True)])

    def test_a_keymap_entrys_own_shift_wins_over_the_pcs(self):
        km = core.km()
        keymap = core.build_keymap([(U['A'], 0, K['A'], km['SHIFT']), (U['A'], km['SHIFT'], K['A'], 0)],
                                   base=core.keymap_named('us104'))
        kb = core.Keyboard(keymap)
        kb.local(True)
        kb.report(0, [U['A']])
        kb.report()
        kb.report(LSHIFT)
        kb.report(LSHIFT, [U['A']])
        kb.report()
        self.assertEqual(kb.local_entries(), [(K['A'], True), (K['A'], False)])

    def test_a_repeat_keeps_the_shift_of_its_press(self):
        (delay, _) = core.typematic_timing()[core.keys3483()[K['A']]['repeat']]
        self.kb.local(True)
        self.send(LSHIFT)
        self.send(LSHIFT, 'A', ms=0)
        self.send(0, 'A', ms=10)  # Shift let go, A still held
        self.kb.tick(delay)
        self.assertEqual(self.kb.local_entries(), [(K['A'], True), (K['A'], True)])

    def test_keys_still_click(self):
        self.kb.local(True)
        self.send(0, 'DOWN')
        self.send()
        self.assertEqual(self.kb.keystrokes, 1)

    def test_setups_keystrokes_are_counted_apart(self):
        # The click rules need SetUp's keys apart from the host's (#107): SetUp's click whatever Click says.
        self.send(0, 'A')
        self.send()
        self.kb.local(True)
        self.send(0, 'DOWN', ms=0)
        (delay, _) = core.typematic_timing()[core.keys3483()[K['DOWN']]['repeat']]
        self.kb.tick(delay)
        self.send(ms=delay + 1)
        self.assertEqual((self.kb.keystrokes, self.kb.local_keystrokes), (3, 2))

    def test_keys_after_setup_closes_are_the_hosts(self):
        self.kb.local(True)
        self.send(0, 'DOWN')
        self.send()
        self.kb.local(False)
        self.send(0, 'A')
        self.send()
        self.assertEqual((self.kb.keystrokes, self.kb.local_keystrokes), (2, 1))

    def test_the_setup_key_itself_is_setups(self):
        self.send(LSHIFT | LALT, 'X')  # us104's SetUp
        self.assertEqual(self.kb.local_keystrokes, 1)

    def test_a_held_key_repeats_into_setup(self):
        (delay, period) = core.typematic_timing()[core.keys3483()[K['DOWN']]['repeat']]
        self.kb.local(True)
        self.send(0, 'DOWN', ms=0)
        self.kb.tick(delay)
        self.assertEqual(self.kb.local_keys(), [K['DOWN'], K['DOWN']])
        self.kb.tick(delay + period)
        self.assertEqual(self.kb.local_keys(), [K['DOWN']])
        self.assertEqual(self.kb.terminal.take_keys(), [])
        self.assertEqual(self.kb.stats()['repeats'], 2)

    def test_repeats_wait_while_setup_hasnt_taken_two(self):
        # setup.c's loop may be held up by a save's erase (45 ms): a held arrow mustn't build a backlog.
        (delay, period) = core.typematic_timing()[core.keys3483()[K['DOWN']]['repeat']]
        self.kb.local(True)
        self.send(0, 'DOWN', ms=0)
        for n in range(10):
            self.kb.tick(delay + n * period)
        self.assertEqual(self.kb.local_keys(), [K['DOWN'], K['DOWN']])

    def test_a_full_ring_drops_the_key(self):
        self.kb.local(True)
        for _ in range(17):
            self.send(0, 'A')
            self.send()
        self.assertEqual(len(self.kb.local_keys()), 16)
        self.assertEqual(self.kb.stats()['drops'], 1)

    def test_a_press_dropped_for_a_full_ring_doesnt_repeat(self):
        (delay, _) = core.typematic_timing()[core.keys3483()[K['DOWN']]['repeat']]
        self.kb.local(True)
        for _ in range(16):
            self.send(0, 'A')
            self.send()
        self.send(0, 'DOWN', ms=0)  # held, and dropped
        self.assertEqual(self.kb.local_keys(), [K['A']] * 16)
        self.kb.tick(delay)
        self.assertEqual(self.kb.local_keys(), [])
        self.assertEqual(self.kb.stats()['repeats'], 0)
        self.assertEqual(self.send(), [])  # its release: nothing

    def test_off_empties_the_ring_and_ends_the_repeat(self):
        (delay, _) = core.typematic_timing()[core.keys3483()[K['DOWN']]['repeat']]
        self.kb.local(True)
        self.send(0, 'DOWN', ms=0)
        self.kb.local(False)
        self.assertFalse(self.kb.local_on)
        self.assertEqual(self.kb.local_keys(), [])
        self.kb.tick(delay)
        self.assertEqual(self.kb.terminal.take_keys(), [])
        self.assertEqual(self.send(), [])                 # Down's release: nothing
        self.assertEqual(self.send(0, 'A'), [K['A']])     # out of local mode, as before

    def test_on_ends_the_repeat_of_a_key_held_for_the_controller(self):
        # Auto dim's lock turns local mode on under a held key (#122): it mustn't repeat into the ring.
        (delay, _) = core.typematic_timing()[core.keys3483()[K['DOWN']]['repeat']]
        self.assertEqual(self.send(0, 'DOWN', ms=0), [K['DOWN']])
        self.kb.local(True)
        self.kb.tick(delay)
        self.assertEqual(self.kb.local_keys(), [])
        self.assertEqual(self.kb.terminal.take_keys(), [K['DOWN']])  # only the press
        self.assertEqual(self.send(), [])                            # Down's release: nothing

    def test_unplugging_keeps_local_mode_and_stops_the_repeat(self):
        (delay, _) = core.typematic_timing()[core.keys3483()[K['DOWN']]['repeat']]
        self.kb.local(True)
        self.send(0, 'DOWN', ms=0)
        self.kb.local_keys()
        self.kb.detach()
        self.kb.attach()
        self.kb.tick(delay)
        self.assertEqual(self.kb.local_keys(), [])
        self.assertTrue(self.kb.local_on)
        self.send(0, 'UP')
        self.assertEqual(self.kb.local_keys(), [K['UP']])


if __name__ == '__main__':
    unittest.main()
