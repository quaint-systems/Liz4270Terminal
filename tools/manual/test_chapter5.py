# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""What Chapter 5 says where the firmware is easy to get wrong (#136's review)."""

import os
import unittest

import manual_paths


class TestChapter5(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(manual_paths.MANUAL, 'chapters', '05-setup.typ'), encoding='utf-8') as stream:
            cls.text = ' '.join(stream.read().split())

    def test_shift_and_alt_dont_wake_the_lock(self):
        # The keyboard's local mode hands the lock every key but Shift and Alt, which go to the controller.
        self.assertIn('press any key but Shift or Alt', self.text)
        self.assertNotIn('press any key:', self.text)

    def test_the_power_on_alarm_sounds_at_alarm_volume_off(self):
        # beep_power_on_volume: at Off, the power-on alarm sounds at level 3; only the host's alarms flash.
        self.assertIn('At Off the screen flashes instead, but for the power-on alarm, which always sounds.', self.text)


    def test_password_sets_characters_and_messages_are_given(self):
        # lock_character: letters, digits and the punctuation keys type into a password; any other key sounds
        # the alarm. setup_ui.c's three messages, as the screen shows them.
        self.assertIn('Letters, digits and punctuation from the main keys type into it; the keypad, Space, Tab, '
                      'Backspace and the arrows sound the alarm.', self.text)
        for message in ('Invalid password. Password has not been changed.', 'Password has been changed.',
                        'Password has been cleared.'):
            self.assertIn(f'#on-screen[{message}]', self.text)


    def test_a_ten_character_password_moves_on_by_itself(self):
        # password_key: the tenth character moves to the second field, where Enter on nothing is a mismatch.
        self.assertIn('At the tenth character the cursor moves on to the second field by itself', self.text)


    def test_offline_setup_comes_back_as_you_leave_it(self):
        # model_change.c: back with a power-on reset as F3 leaves the Offline Setup menu, a second at the soonest.
        self.assertIn('no sooner than a second after it went offline', self.text)

if __name__ == '__main__':
    unittest.main()
