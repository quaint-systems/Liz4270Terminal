# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The alarm and key click (firmware/core/beep.c, #18): the beep generator's numbers, checked against the
TLV320DAC3100 datasheet's own example (SLAS671C, Table 6-23), and the rules for when to sound."""

import os
import re
import unittest

import core
import screen
import paths

B = core.constants('beep.h', 'BEEP_')
NONE, CLICK, ALARM, FLASH = B['NONE'], B['CLICK'], B['ALARM'], B['FLASH']


class TestTone(unittest.TestCase):
    def test_the_datasheets_1_khz_example(self):
        self.assertEqual(core.beep_tone(1000, 48000), (0x10B5, 0x7EE8))

    def test_the_3483_vs_tone(self):
        self.assertEqual((B['HZ'], B['FS']), (3493, 31250))
        self.assertEqual(core.beep_tone(B['HZ'], B['FS']), (0x52B0, 0x61B6))

    def test_a_quarter_of_the_sample_rate_or_more_is_refused(self):
        self.assertIsNone(core.beep_tone(12000, 48000))
        self.assertIsNone(core.beep_tone(40000, 48000))
        self.assertIsNotNone(core.beep_tone(11999, 48000))

    def test_no_tone_at_0_hz(self):
        self.assertIsNone(core.beep_tone(0, 31250))

    def test_cos_stays_within_15_bits_at_the_lowest_tone(self):
        self.assertEqual(core.beep_tone(1, 31250), (7, 32767))


class TestSamples(unittest.TestCase):
    def test_the_datasheets_five_cycles(self):
        # Table 6-23: five cycles of 1 kHz at 48 kHz are 0xF0 samples.
        self.assertEqual(core.beep_samples(5, 48000), 0xF0)

    def test_the_starting_lengths(self):
        self.assertEqual(core.beep_samples(10, 31250), 312)
        self.assertEqual(core.beep_samples(500, 31250), 15625)

    def test_a_length_past_24_bits_is_held_at_the_most(self):
        self.assertEqual(B['LENGTH_MAX'], 0xFFFFFF)
        self.assertEqual(core.beep_samples(600000, 31250), 0xFFFFFF)
        self.assertEqual(core.beep_samples(0xFFFFFFFF, 48000), 0xFFFFFF)  # no overflow on the way


class TestLevel(unittest.TestCase):
    def test_register_71s_codes(self):
        self.assertEqual([core.beep_level_code(db) for db in (2, 1, 0, -1, -20, -60, -61)],
                         [0, 1, 2, 3, 22, 62, 63])

    def test_a_level_outside_the_range_is_held_to_its_end(self):
        self.assertEqual(core.beep_level_code(10), 0)
        self.assertEqual(core.beep_level_code(-100), 63)


class TestVolumes(unittest.TestCase):
    def test_the_ladder(self):
        # 10 dB a step, 3 today's -20 dB, High 0 dB (#107); Off isn't sounded.
        self.assertEqual([core.beep_volume_db(v) for v in range(1, 6)], [-40, -30, -20, -10, 0])
        self.assertEqual(core.beep_volume_db(0), -61)  # BEEP_LEVEL_MIN_DB, which constants() can't read: (-61)
        self.assertEqual(core.beep_volume_db(6), -61)

    def test_the_power_on_alarm_at_each_alarm_volume(self):
        for volume in range(1, 6):
            self.assertEqual(core.beep_power_on_volume(screen.Settings(alarm_volume=volume)), volume)
        self.assertEqual(core.beep_power_on_volume(screen.Settings(alarm_volume=0)), B['POWER_ON_VOLUME'])
        self.assertEqual(B['POWER_ON_VOLUME'], 3)

    def test_off_resolves_the_same_for_the_rules_and_b(self):
        # One copy of the Off rules (#107), which beep_poll and the console's b both take.
        self.assertEqual([core.beep_resolve(s) for s in (NONE, CLICK, ALARM, FLASH)], [NONE, CLICK, ALARM, FLASH])
        off = screen.Settings(click_volume=0, alarm_volume=0)
        self.assertEqual([core.beep_resolve(s, off) for s in (NONE, CLICK, ALARM, FLASH)], [NONE, NONE, FLASH, FLASH])

    def test_each_sound_at_its_own_volume(self):
        settings = screen.Settings(click_volume=1, alarm_volume=5)
        self.assertEqual((core.beep_sound_db(CLICK, settings), core.beep_sound_db(ALARM, settings)), (-40, 0))
        self.assertEqual((core.beep_sound_db(NONE, settings), core.beep_sound_db(FLASH, settings)), (-61, -61))


class BeepTest(unittest.TestCase):
    def setUp(self):
        self.beep = core.Beep()
        self.alarms = 0
        self.keys = 0
        self.local = 0

    def poll(self, ms, alarm=False, key=False, clicker=True, local=False, settings=None):
        """One poll at ms, after one more alarm POLL, host keystroke or SetUp keystroke if asked."""
        self.alarms += alarm
        self.keys += key or local
        self.local += local
        return self.beep.poll(ms, self.alarms, self.keys, clicker, self.local, settings)


class TestPoll(BeepTest):
    def test_nothing_new_sounds_nothing(self):
        self.assertEqual(self.poll(0), NONE)
        self.assertEqual(self.poll(1000), NONE)

    def test_counts_already_seen_at_init_sound_nothing(self):
        beep = core.Beep(alarms=3, keystrokes=40)
        self.assertEqual(beep.poll(0, 3, 40, True), NONE)

    def test_an_alarm_sounds_on_a_new_count(self):
        self.assertEqual(self.poll(0, alarm=True), ALARM)

    def test_two_alarms_between_polls_sound_once(self):
        self.alarms += 1
        self.assertEqual(self.poll(0, alarm=True), ALARM)
        self.assertEqual(self.poll(1), NONE)

    def test_a_count_that_goes_back_sounds_nothing(self):
        # The console's r, or the controller's power-on reset, runs term_init: term_alarms goes back to 0.
        beep = core.Beep(alarms=5, keystrokes=0)
        self.assertEqual(beep.poll(0, 0, 0, True), NONE)
        self.assertEqual(beep.poll(1000, 1, 0, True), ALARM)

    def test_an_alarm_during_an_alarm_is_swallowed_and_one_after_it_sounds(self):
        self.assertEqual(self.poll(0, alarm=True), ALARM)
        self.assertEqual(self.poll(499, alarm=True), NONE)
        self.assertEqual(self.beep.swallowed, 1)
        self.assertEqual(self.poll(500, alarm=True), ALARM)

    def test_a_click_needs_the_clicker(self):
        self.assertEqual(self.poll(0, key=True, clicker=False), NONE)
        self.assertEqual(self.poll(1, key=True), CLICK)

    def test_keystrokes_with_the_clicker_off_leave_nothing_to_click_later(self):
        for ms in range(5):
            self.poll(ms, key=True, clicker=False)
        self.assertEqual(self.poll(10), NONE)
        self.assertEqual(self.beep.swallowed, 0)

    def test_a_click_during_an_alarm_is_swallowed(self):
        self.assertEqual(self.poll(0, alarm=True), ALARM)
        self.assertEqual(self.poll(100, key=True), NONE)
        self.assertEqual(self.beep.swallowed, 1)
        self.assertEqual(self.poll(500, key=True), CLICK)

    def test_an_alarm_cuts_a_click(self):
        self.assertEqual(self.poll(0, key=True), CLICK)
        self.assertEqual(self.poll(5, alarm=True), ALARM)

    def test_a_click_cuts_a_click(self):
        self.assertEqual(self.poll(0, key=True), CLICK)
        self.assertEqual(self.poll(5, key=True), CLICK)

    def test_both_at_once_give_the_alarm(self):
        self.assertEqual(self.poll(0, alarm=True, key=True), ALARM)
        self.assertEqual(self.beep.swallowed, 1)

    def test_the_alarms_end_holds_across_a_wrap_of_the_clock(self):
        # 0x100 ms to the wrap, then 500 - 0x100 = 244 more.
        self.assertEqual(self.poll(0xFFFFFF00, alarm=True), ALARM)
        self.assertEqual(self.poll(243, key=True), NONE)
        self.assertEqual(self.poll(244, key=True), CLICK)

    def test_a_quiet_spell_longer_than_half_the_clock_doesnt_silence_the_next_alarm(self):
        # 25 days with nothing to sound: past 2^31 ms the old alarm's end looks like the future again.
        self.assertEqual(self.poll(1000, alarm=True), ALARM)
        self.assertEqual(self.poll(1500), NONE)
        later = 1000 + 25 * 86400000
        self.assertEqual(self.poll(later, alarm=True), ALARM)
        self.assertEqual(self.poll(later + 600, key=True), CLICK)


class TestPage2Rules(BeepTest):
    """Click, Click Volume and Alarm volume (#107), as captured on Oct 12."""

    def test_click_no_silences_the_host_not_setup(self):
        no = screen.Settings(click=False)
        self.assertEqual(self.poll(0, key=True, settings=no), NONE)
        self.assertEqual(self.poll(10, local=True, settings=no), CLICK)
        self.assertEqual(self.beep.swallowed, 0)

    def test_setups_keys_click_with_the_clicker_off(self):
        self.assertEqual(self.poll(0, local=True, clicker=False), CLICK)
        self.assertEqual(self.poll(10, key=True, clicker=False), NONE)

    def test_volume_off_silences_every_click(self):
        off = screen.Settings(click_volume=0)
        self.assertEqual(self.poll(0, key=True, settings=off), NONE)
        self.assertEqual(self.poll(10, local=True, settings=off), NONE)
        self.assertEqual(self.beep.swallowed, 0)

    def test_an_alarm_at_off_flashes(self):
        off = screen.Settings(alarm_volume=0)
        self.assertEqual(self.poll(0, alarm=True, settings=off), FLASH)

    def test_a_flash_swallows_its_click_and_a_second_flash_not_later_clicks(self):
        off = screen.Settings(alarm_volume=0)
        self.assertEqual(self.poll(0, alarm=True, key=True, settings=off), FLASH)
        self.assertEqual(self.beep.swallowed, 1)
        self.assertEqual(self.poll(50, alarm=True, settings=off), NONE)
        self.assertEqual(self.beep.swallowed, 2)
        self.assertEqual(self.poll(60, key=True, settings=off), CLICK)  # nothing is sounding

    def test_a_flash_ends_and_the_next_alarm_flashes_again(self):
        off = screen.Settings(alarm_volume=0)
        self.assertEqual(self.poll(0, alarm=True, settings=off), FLASH)
        self.assertEqual(self.poll(B['FLASH_MS'] - 1, alarm=True, settings=off), NONE)
        self.assertEqual(self.poll(B['FLASH_MS'] + 300, alarm=True, settings=off), FLASH)

    def test_an_alarm_during_a_flash_is_swallowed(self):
        self.assertEqual(self.poll(0, alarm=True, settings=screen.Settings(alarm_volume=0)), FLASH)
        self.assertEqual(self.poll(100, alarm=True), NONE)  # Alarm volume back to 3 meanwhile
        self.assertEqual(self.poll(B['FLASH_MS'], alarm=True), ALARM)

    def test_a_preview_cuts_the_alarm_still_sounding(self):
        # Space, Right, Space through Alarm volume (#107): each Space's preview is heard, not swallowed.
        self.assertEqual(self.poll(0, alarm=True), ALARM)
        self.beep.preview()
        self.assertEqual(self.poll(100, alarm=True), ALARM)
        self.assertEqual(self.beep.swallowed, 0)

    def test_a_preview_cuts_a_flash(self):
        self.assertEqual(self.poll(0, alarm=True, settings=screen.Settings(alarm_volume=0)), FLASH)
        self.beep.preview()
        self.assertEqual(self.poll(50, alarm=True), ALARM)

    def test_without_a_preview_an_alarm_still_waits(self):
        self.assertEqual(self.poll(0, alarm=True), ALARM)
        self.assertEqual(self.poll(100, alarm=True), NONE)

    def test_the_flash_length(self):
        self.assertEqual((self.beep.length(FLASH), B['FLASH_MS']), (200, 200))
        self.beep.set_length(FLASH, 50)
        self.assertEqual(self.beep.length(FLASH), 50)


class TestStartAndLengths(BeepTest):
    def test_the_default_lengths(self):
        self.assertEqual((self.beep.length(CLICK), self.beep.length(ALARM), self.beep.length(NONE)),
                         (B['CLICK_MS'], B['ALARM_MS'], 0))

    def test_a_new_alarm_length_sets_when_the_next_alarm_ends(self):
        self.beep.set_length(ALARM, 50)
        self.assertEqual(self.poll(0, alarm=True), ALARM)
        self.assertEqual(self.poll(49, key=True), NONE)
        self.assertEqual(self.poll(50, key=True), CLICK)

    def test_a_click_length_leaves_the_alarm_alone(self):
        self.beep.set_length(CLICK, 25)
        self.assertEqual((self.beep.length(CLICK), self.beep.length(ALARM)), (25, B['ALARM_MS']))

    def test_an_alarm_started_elsewhere_swallows_clicks(self):
        self.beep.start(0, ALARM)
        self.assertEqual(self.poll(100, key=True), NONE)
        self.assertEqual(self.poll(B['ALARM_MS'], key=True), CLICK)

    def test_a_click_started_elsewhere_ends_the_alarm(self):
        self.assertEqual(self.poll(0, alarm=True), ALARM)
        self.beep.start(10, CLICK)
        self.assertEqual(self.poll(20, alarm=True), ALARM)

    def test_an_alarm_the_dac_failed_swallows_nothing(self):
        self.assertEqual(self.poll(0, alarm=True), ALARM)
        self.beep.cancel()
        self.assertEqual(self.poll(100, key=True), CLICK)
        self.assertEqual(self.poll(200, alarm=True), ALARM)
        self.assertEqual(self.beep.swallowed, 0)

    def test_setups_alarm_with_its_click_sounds_the_alarm(self):
        # audio.c adds SetUp's alarms to term_alarms (#102): a key SetUp can't use clicks and sounds the alarm
        # in the same poll, and the alarm sounds, the click swallowed. That holds on the Fruit Jam only while
        # main's loop runs setup_poll between usb_host_poll and audio_poll (test_setup_counts_its_alarm_...).
        beep = core.Beep()
        self.assertEqual(beep.poll(0, 1, 1, True), core.constants('beep.h', 'BEEP_')['ALARM'])
        self.assertEqual(beep.swallowed, 1)


class TestMainLoop(unittest.TestCase):
    def test_setup_counts_its_alarm_before_audio_polls_the_click(self):
        # The final review's I1 (#102): a key SetUp can't use raises kbd_keystrokes in usb_host_poll and SetUp's
        # alarm count in setup_poll. audio_poll must see both in one beep_poll, or the click sounds first and the
        # alarm ~3 ms later. So main's loop runs usb_host_poll, then setup_poll, then audio_poll.
        with open(os.path.join(paths.ROOT, 'firmware', 'src', 'main.c'), encoding='utf-8') as stream:
            source = stream.read()
        loop = source[source.index('for (;;) {'):]
        calls = [m.group(1) for m in re.finditer(r'\b(usb_host_poll|setup_poll|audio_poll)\(\);', loop)]
        self.assertEqual(calls, ['usb_host_poll', 'setup_poll', 'audio_poll'])


if __name__ == '__main__':
    unittest.main()
