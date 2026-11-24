# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

import unittest

import setup_walk
import screen  # tools/sim, on the path through setup_walk


class TestSetupWalk(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.rows = setup_walk.walk()

    def screen(self, name):
        return [r for r in self.rows if r['screen'] == name]

    def test_every_screen_has_its_rows(self):
        counts = {name: len(self.screen(name)) for (name, _, _) in setup_walk.SCREENS}
        self.assertEqual(counts, {'Online Setup and Utility': 6, 'Display Setup, page 1': 9,
                                  'Display Setup, page 2': 7, 'Display Setup, page 3': 4,
                                  'Display Setup, page 4': 1, 'Offline Setup': 4, 'Customization': 6})

    def test_page_1_its_headings_defaults_and_settings(self):
        self.assertEqual([(r['parent'], r['label'], r['default'], r['field'])
                          for r in self.screen('Display Setup, page 1')], [
            ('Rule line', 'Style', 'Horizontal', 'ruler_style'),
            ('Rule line', 'Color', 'White', 'ruler_colour'),
            ('Rule line', 'Follows cursor', 'Yes', 'ruler_follows'),
            ('', 'Row/column indicator', 'On', 'indicator'),
            ('Cursor', 'Style', 'Underline', 'cursor'),
            ('Cursor', 'Blink', 'No', 'cursor_blink'),
            ('', 'Auto dim', 'Yes', 'auto_dim'),
            ('Auto dim', 'Delay (minutes)', '10', 'dim_minutes'),
            ('Auto dim', 'Lock sessions', 'No', 'lock_sessions'),
        ])

    def test_page_3_maps_the_four_base_colours_to_themselves(self):
        self.assertEqual([(r['label'], r['default']) for r in self.screen('Display Setup, page 3')], [
            ('Input', 'Green'), ('Intensified input', 'Red'), ('Protected', 'Blue'),
            ('Intensified protected', 'White')])

    def test_a_row_of_choices_with_no_label_continues_the_row_above(self):
        (volume,) = [r for r in self.screen('Display Setup, page 2') if r['label'] == 'Volume']
        self.assertEqual(volume['choices'], ['Off', '1', '2', '3', '4', 'High'])
        self.assertEqual((volume['parent'], volume['default']), ('Clicker', '3'))

    def test_a_choice_keeps_its_own_spaces(self):
        rows = {r['label']: r for r in self.screen('Customization')}
        self.assertEqual(rows['Screen rows x columns']['choices'], ['24 x 80', '32 x 80', '43 x 80'])
        self.assertEqual(rows['Screen rows x columns']['default'], '24 x 80')
        self.assertEqual(rows['Underscore style']['choices'], ['- - -', '_____'])

    def test_what_the_firmware_doesnt_act_on(self):
        self.assertEqual({(r['screen'], r['label']) for r in self.rows if not r['acted']}, {
            ('Online Setup and Utility', 'Setup local functions'),
            ('Online Setup and Utility', 'Setup color palette'),
            ('Display Setup, page 2', 'Trim border'),
            ('Offline Setup', 'Set printer definition utility'),
            ('Offline Setup', 'Update serial number'),
            ('Offline Setup', 'Test display station'),
            ('Customization', 'Keyboard layout'),
            ('Customization', 'Numeric lock'),
            ('Customization', 'Underscore style'),
            ('Customization', 'Markup'),
            ('Customization', 'Black-On-White emulation'),
        })

    def test_a_row_not_acted_on_has_no_default(self):
        for r in self.rows:
            if not r['acted']:
                self.assertEqual((r['default'], r['field']), (None, None), r['label'])

    def test_a_menus_items_have_no_choices(self):
        for name in ('Online Setup and Utility', 'Offline Setup'):
            for r in self.screen(name):
                self.assertEqual((r['parent'], r['choices']), ('', []), r['label'])

    def test_every_row_has_a_key_of_its_own(self):
        keys = [(r['screen'], r['parent'], r['label']) for r in self.rows]
        self.assertEqual(len(keys), len(set(keys)))

    def test_each_screen_is_read_as_the_manual_pictures_it(self):
        # The walk opens each screen by the keys screen.setup_screens draws its picture by: one table for both.
        images = screen.setup_screens()
        for (name, image, _) in setup_walk.SCREENS:
            self.assertEqual(setup_walk._open(screen.SETUP_KEYS[image]).regen(), images[image][0], name)

    def test_a_screen_with_another_title_is_refused(self):
        with self.assertRaisesRegex(setup_walk.WalkError, "expected 'Customization', found 'Display Setup, page 1'"):
            setup_walk.screen_rows('Customization', ('DOWN', 'ENTER'), 'choices')

    def test_a_page_of_display_setup_opened_by_the_wrong_keys_is_refused(self):
        # Pages 2 and 3 share their title and their More: mark; F7 back to page 1 tells them apart.
        with self.assertRaisesRegex(setup_walk.WalkError,
                                    "expected 'Display Setup, page 3', found 'Display Setup, page 2'"):
            setup_walk.screen_rows('Display Setup, page 3', ('DOWN', 'ENTER', 'PF8'), 'choices')

    def test_a_screen_with_one_page_is_named_by_its_title_alone(self):
        with self.assertRaisesRegex(setup_walk.WalkError, "expected 'Display Setup, page 1', found 'Customization'"):
            setup_walk.screen_rows('Display Setup, page 1', ('UP', 'ENTER', 'ENTER', 'ENTER'), 'choices')


if __name__ == '__main__':
    unittest.main()
