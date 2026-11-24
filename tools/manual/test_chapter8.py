# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""What Chapter 8 says about problems, where the firmware or oec is easy to get wrong (#136)."""

import os
import re
import unittest

import manual_paths


class TestChapter8(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(manual_paths.MANUAL, 'chapters', '08-problems.typ'), encoding='utf-8') as stream:
            cls.raw = stream.read()
        cls.text = ' '.join(cls.raw.split())

    def test_the_version_is_quoted_from_the_splash_or_about(self):
        # splash.c draws the version and the commit; SetUp's About page adds the board (#126, #132).
        self.assertIn("from the splash screen when you switch on, or from SetUp's About page", self.text)

    def test_the_splash_stays_until_the_controller_writes(self):
        # splash.c: at least SPLASH_MIN_MS, then until term_written (#53).
        self.assertIn('then until the controller first writes to the screen', self.text)

    def test_a_lost_controller_leaves_the_last_screen(self):
        # Nothing in coax_link.c notices the POLLs stopping, and the status line is oec's to write.
        self.assertIn('keeps the last screen and status line it was given', self.text)

    def test_under_oec_the_dagger_keys_do_nothing(self):
        # The list comes from keys.typ, whose oec marks keys.py checks against oec's own TN3270 session.
        self.assertIn('not f.oec', self.raw)
        self.assertIn('marked † in Chapter 4', self.text)

    def test_reset_clears_an_input_error_under_oec(self):
        # oec master locks no keyboard for an input error: the render after each key clears operator_error
        # (tn3270.py), and Reset, which its TN3270 session has no branch for, is a key that does nothing else.
        self.assertIn('Under oec, an input error doesn\'t lock the keyboard: the next key you press clears its symbol',
                      self.text)
        self.assertIn('Reset is the one to press', self.text)
        self.assertNotIn("so it doesn't unlock the keyboard", self.text)

    def test_offline_setup_lasts_while_it_is_up(self):
        # model_change.c: the link stays off the coax until F3 leaves the Offline Setup menu, a second at least.
        self.assertIn('leaves the controller while offline setup is up, for at least a second', self.text)
        self.assertNotIn('for about a second', self.text)

    def test_click_no_leaves_setups_keys_clicking(self):
        # beep_poll: a local keystroke clicks whatever Click says; Volume Off silences every click.
        self.assertIn("with Click at No, keys you press for the host don't", self.text)

    def test_a_failed_save_means_opening_setup_again(self):
        self.assertIn('Open SetUp and close it again', self.text)

    def test_lock_sessions_on_the_menu_saves_too(self):
        # setup.c: SETUP_UI_LOCK engages the lock, then close_setup saves as F3 does, with a password set or
        # through Password Set's F3.
        self.assertIn('and when Lock sessions on the Online Setup and Utility menu locks the display station',
                      self.text)

    def test_a_second_hub_doesnt_work(self):
        # tusb_config.h: CFG_TUH_HUB 1, and the on-board hub takes it.
        self.assertIn("a keyboard plugged into a separate hub, or one with a hub of its own, doesn't work", self.text)
        self.assertNotIn('may not work', self.text)

    def test_the_screen_symptoms_mark_the_screen(self):
        # The index's "screen" entry, a sub-entry for each symptom (PR 3's review).
        for label in ('no-picture', 'lost', 'screen-black'):
            section = re.search(rf'<{label}>\s*$(.*?)^== ', self.raw, re.M | re.S)
            self.assertIsNotNone(section, label)
            self.assertIn('#ix("screen", sub: ', section.group(1), label)

    def test_a_power_cycle_unlocks_and_f11_clears(self):
        # setup_init clears the lock; Password Set's F11 asks for no old password (setup_ui.c, Oct 13).
        self.assertIn('it starts unlocked, and the password is still set', self.text)
        self.assertIn('#key("F11")', self.text)

    def test_every_symptom_is_in_table_8_1(self):
        sections = re.findall(r'^== .*? <([\w-]+)>\s*$', self.raw, re.M)
        listed = re.search(r'#let symptoms = \(([^)]*)\)', self.raw)
        self.assertIsNotNone(listed, 'Chapter 8 lists its symptoms for Table 8-1')
        self.assertEqual(re.findall(r'<([\w-]+)>', listed.group(1)), [s for s in sections if s != 'help'])


if __name__ == '__main__':
    unittest.main()
