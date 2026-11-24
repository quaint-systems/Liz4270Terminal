# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""SetUp's screens and keys (firmware/core/setup_ui.c, #102), against the 3483-V as captured on Oct 6 and 11
(captures/README.md)."""

import ctypes
import unittest

import bake_about
import core
import screen
from display_codes import MAIN

UI = core.constants('setup_ui.h', 'SETUP_UI_')
OFF, MENU, PAGE1, PAGE4 = UI['OFF'], UI['MENU'], UI['PAGE1'], UI['PAGE4']
NONE, ALARM, CHANGED, CLOSED, PREVIEW = UI['NONE'], UI['ALARM'], UI['CHANGED'], UI['CLOSED'], UI['PREVIEW']
PASSWORD, PASSWORD_SET, PASSWORD_CLEARED = UI['PASSWORD'], UI['PASSWORD_SET'], UI['PASSWORD_CLEARED']
LOCK = UI['LOCK']
ABOUT, OFFLINE_MENU, CUSTOMIZE = UI['ABOUT'], UI['OFFLINE_MENU'], UI['CUSTOMIZE']
LICENSE_PAGES = core.constants('about_text.h', 'ABOUT_')['PAGES']
ABC = ('A', 'B', 'C')
INVALID = 'Invalid password. Password has not been changed.'


def place(address):
    """(row, column) counted from 1, of a screen address."""
    (row, col) = divmod(address - 80, 80)
    return (row + 1, col + 1)


# The menu's items and each page's choices, (row, column), in reading order, as the spec's tables place them.
MENU_ITEMS = [(6, 3), (8, 3), (10, 3), (12, 3), (14, 3), (20, 3)]
PAGE_CHOICES = {
    1: [(7, 33), (7, 47), (7, 61), (7, 75), (8, 33), (8, 47), (9, 33), (9, 47), (11, 33), (11, 47),
        (14, 33), (14, 47), (15, 33), (15, 47), (17, 33), (17, 47), (18, 33), (18, 47), (18, 61), (19, 33), (19, 47)],
    2: [(7, 46), (7, 60), (8, 46), (8, 60), (8, 73), (11, 46), (11, 60), (12, 46), (12, 60), (12, 73),
        (13, 46), (13, 60), (13, 73), (14, 46), (14, 60), (14, 73), (15, 46), (15, 60), (15, 73),
        (17, 46), (17, 60), (19, 46), (19, 60)],
    3: [(r + d, c) for r in (8, 11, 14, 17) for (d, c) in ((0, 33), (0, 45), (0, 57), (0, 69), (1, 33), (1, 45), (1, 57))],
    4: [(7, 33), (7, 47)],
}
PINK_CHOICES = {1: [], 2: [(17, 46), (17, 60)], 3: [], 4: []}  # Trim border; page 1's Lock sessions is live (#122)


def on_page(n, settings=None):
    """A SetupUi opened, then on page n."""
    ui = core.SetupUi(settings)
    ui.open()
    ui.key('DOWN')
    ui.key('ENTER')
    for _ in range(n - 1):
        ui.key('PF8')
    return ui


def move_to(ui, row, col):
    """Right until the selector is on (row, col)."""
    for _ in range(40):
        if place(ui.selector_at) == (row, col):
            return
        ui.key('RIGHT')
    raise AssertionError(f'no choice at {(row, col)}')


class TestMenu(unittest.TestCase):
    def test_off_until_opened(self):
        ui = core.SetupUi()
        self.assertEqual((ui.screen, ui.selector_at), (OFF, 0))
        self.assertEqual(ui.key('DOWN'), NONE)
        self.assertEqual((ui.screen, ui.stats()['keys']), (OFF, 0))

    def test_it_opens_on_lock_sessions(self):
        # photos-20261011/setup-6-menu-opens-on-lock-sessions.jpg
        ui = core.SetupUi()
        ui.open()
        self.assertEqual((ui.screen, place(ui.selector_at)), (MENU, (6, 3)))

    def test_down_and_right_go_round_the_items(self):
        for key in ('DOWN', 'RIGHT'):
            ui = core.SetupUi()
            ui.open()
            seen = []
            for _ in range(6):
                self.assertEqual(ui.key(key), NONE)
                seen.append(place(ui.selector_at))
            self.assertEqual(seen, MENU_ITEMS[1:] + MENU_ITEMS[:1], key)

    def test_up_and_left_go_round_backwards(self):
        for key in ('UP', 'LEFT'):
            ui = core.SetupUi()
            ui.open()
            seen = []
            for _ in range(6):
                ui.key(key)
                seen.append(place(ui.selector_at))
            self.assertEqual(seen, list(reversed(MENU_ITEMS)), key)

    def test_enter_on_setup_display_opens_page_1_on_its_first_choice(self):
        ui = core.SetupUi()
        ui.open()
        ui.key('DOWN')
        self.assertEqual(ui.key('ENTER'), NONE)
        self.assertEqual((ui.screen, place(ui.selector_at)), (PAGE1, (7, 33)))

    def test_enter_on_the_other_items_sounds_the_alarm(self):
        # Lock sessions and Set password open theirs (#122); Go to offline setup has its warning (#110).
        for item in (2, 4):
            ui = core.SetupUi()
            ui.open()
            for _ in range(item):
                ui.key('DOWN')
            self.assertEqual(ui.key('ENTER'), ALARM, item)
            self.assertEqual((ui.screen, place(ui.selector_at)), (MENU, MENU_ITEMS[item]))

    def test_f3_closes_it(self):
        ui = core.SetupUi()
        ui.open()
        self.assertEqual(ui.key('PF3'), CLOSED)
        self.assertEqual(ui.screen, OFF)

    def test_every_other_key_sounds_the_alarm(self):
        for key in ('SPACE', 'PF7', 'PF8', 'TAB', 'BACKTAB', 'NEWLINE', 'A', 'SETUP', 'PF15', 'NOTHING'):
            ui = core.SetupUi()
            ui.open()
            self.assertEqual(ui.key(key), ALARM, key)
            self.assertEqual((ui.screen, place(ui.selector_at)), (MENU, (6, 3)), key)


def column_order(choices):
    return sorted(choices, key=lambda rc: (rc[1], rc[0]))


class TestPages(unittest.TestCase):
    def walk(self, ui, key, n):
        seen = []
        for _ in range(n):
            self.assertEqual(ui.key(key), NONE)
            seen.append(place(ui.selector_at))
        return seen

    def test_each_page_starts_top_left(self):
        for (n, choices) in PAGE_CHOICES.items():
            self.assertEqual(place(on_page(n).selector_at), choices[0], n)

    def test_down_walks_by_column_then_row(self):
        for (n, choices) in PAGE_CHOICES.items():
            order = column_order(choices)
            self.assertEqual(order[0], choices[0], n)  # the top-left choice heads both walks
            self.assertEqual(self.walk(on_page(n), 'DOWN', len(order)), order[1:] + order[:1], n)

    def test_up_walks_it_backwards(self):
        # Up from Horizontal is None (CoffeeMuse, Oct 11).
        for (n, choices) in PAGE_CHOICES.items():
            order = column_order(choices)
            self.assertEqual(self.walk(on_page(n), 'UP', len(order)), list(reversed(order)), n)
        self.assertEqual(self.walk(on_page(1), 'UP', 1), [(7, 75)])

    def test_right_and_left_walk_in_reading_order(self):
        for (n, choices) in PAGE_CHOICES.items():
            self.assertEqual(self.walk(on_page(n), 'RIGHT', len(choices)), choices[1:] + choices[:1], n)
            self.assertEqual(self.walk(on_page(n), 'LEFT', len(choices)), list(reversed(choices)), n)

    def test_f8_and_f7_between_pages_and_the_alarm_at_the_ends(self):
        ui = on_page(1)
        self.assertEqual(ui.key('PF7'), ALARM)
        for n in range(2, 5):
            ui.key('RIGHT')
            self.assertEqual(ui.key('PF8'), NONE)
            self.assertEqual((ui.screen, place(ui.selector_at)), (PAGE1 + n - 1, PAGE_CHOICES[n][0]))
        self.assertEqual(ui.key('PF8'), ALARM)
        self.assertEqual(ui.screen, PAGE4)
        for n in range(3, 0, -1):
            self.assertEqual(ui.key('PF7'), NONE)
            self.assertEqual((ui.screen, place(ui.selector_at)), (PAGE1 + n - 1, PAGE_CHOICES[n][0]))

    def test_f3_goes_back_to_the_menu_on_lock_sessions(self):
        ui = on_page(3)
        self.assertEqual(ui.key('PF3'), NONE)
        self.assertEqual((ui.screen, place(ui.selector_at)), (MENU, (6, 3)))

    def test_every_other_key_sounds_the_alarm(self):
        # Tab, Back Tab, Home, New Line, Enter and letters: the alarm, nothing moves (CoffeeMuse, Oct 11).
        for key in ('TAB', 'BACKTAB', 'NEWLINE', 'ENTER', 'A', 'SETUP', 'PF15', 'RULE', 'NOTHING'):
            ui = on_page(1)
            ui.key('RIGHT')
            self.assertEqual(ui.key(key), ALARM, key)
            self.assertEqual((ui.screen, place(ui.selector_at)), (PAGE1, (7, 47)), key)


YES_NO = ((33, True), (47, False))
# Page 3's seven colours as (line of the row, column, code): Red, Pink, Green, Yellow, then Blue, Turquoise, White.
COLOUR_PLACES = ((0, 33, 2), (0, 45, 3), (0, 57, 4), (0, 69, 6), (1, 33, 1), (1, 45, 5), (1, 57, 7))


class TestSpace(unittest.TestCase):
    # (page, the choice, the field, the value Space gives it): every live choice, as the spec's tables give them.
    LIVE = ([(1, (7, col), 'ruler_style', value) for (col, value) in ((33, 0), (47, 1), (61, 2), (75, 3))]
            + [(1, (8, 33), 'ruler_colour', 7), (1, (8, 47), 'ruler_colour', 4)]
            + [(1, (row, col), field, value)
               for (row, field) in ((9, 'ruler_follows'), (11, 'indicator'), (15, 'cursor_blink'), (17, 'auto_dim'))
               for (col, value) in YES_NO]
            + [(1, (14, 33), 'cursor', 0), (1, (14, 47), 'cursor', 1)]
            + [(1, (18, col), 'dim_minutes', value) for (col, value) in ((33, 5), (47, 10), (61, 20))]
            + [(3, (row + line, col), field, value)
               for (row, field) in ((8, 'colour_input'), (11, 'colour_input_hi'), (14, 'colour_protected'),
                                    (17, 'colour_protected_hi'))
               for (line, col, value) in COLOUR_PLACES]
            + [(4, (7, col), 'mono', value) for (col, value) in YES_NO]
            + [(2, (7, 46), 'typematic_rate', 0), (2, (7, 60), 'typematic_rate', 1)]
            + [(2, (8, col), 'typematic_delay', value) for (col, value) in ((46, 0), (60, 1), (73, 2))]
            + [(2, (11, col), 'click', value) for (col, value) in ((46, True), (60, False))]
            + [(2, (row + line, col), field, value)
               for (row, field) in ((12, 'click_volume'), (14, 'alarm_volume'))
               for (line, col, value) in ((0, 46, 0), (0, 60, 1), (0, 73, 2), (1, 46, 3), (1, 60, 4), (1, 73, 5))]
            + [(2, (19, col), 'mono_case', value) for (col, value) in ((46, True), (60, False))]
            + [(1, (19, col), 'lock_sessions', value) for (col, value) in YES_NO])

    def test_the_table_is_every_choice_that_isnt_pink(self):
        self.assertEqual(len(self.LIVE), 72)
        self.assertEqual({(page, choice) for (page, choice, _, _) in self.LIVE},
                         {(page, choice) for page in (1, 2, 3, 4) for choice in PAGE_CHOICES[page]
                          if choice not in PINK_CHOICES[page]})

    def test_space_sets_each_live_rows_field_to_a_value_settings_valid_takes(self):
        values = {}
        for (_, _, field, value) in self.LIVE:
            values.setdefault(field, []).append(value)
        for (page, (row, col), field, value) in self.LIVE:
            with self.subTest(page=page, choice=(row, col)):
                ui = on_page(page)
                ui.set(**{field: next(other for other in values[field] if other != value)})  # so Space changes it
                move_to(ui, row, col)
                self.assertEqual(ui.key('SPACE'), PREVIEW if field == 'alarm_volume' else CHANGED)
                self.assertEqual(ui.settings[field], value)
                self.assertTrue(core.settings_valid(**ui.settings))

    def test_space_on_a_pink_row_sounds_the_alarm_and_changes_nothing(self):
        for page in (1, 2):
            for (row, col) in PINK_CHOICES[page]:
                ui = on_page(page)
                before = ui.settings
                move_to(ui, row, col)
                self.assertEqual(ui.key('SPACE'), ALARM, (page, row, col))
                self.assertEqual(ui.settings, before)

    def test_page_2_follows_the_settings(self):
        ui = on_page(2, screen.Settings(typematic_rate=1, click_volume=5, mono_case=True))
        image = Drawn(ui)
        self.assertEqual(image.colour(7, 60), YELLOW)   # Fast
        self.assertEqual(image.colour(13, 73), YELLOW)  # High
        self.assertEqual(image.colour(19, 46), YELLOW)  # Mono case Yes


class TestStats(unittest.TestCase):
    def test_opens_keys_and_alarms(self):
        ui = core.SetupUi()
        ui.key('DOWN')            # off: not counted
        ui.open()
        ui.key('DOWN')
        ui.key('ENTER')
        ui.key('PF7')             # the alarm on page 1
        ui.key('PF3')
        ui.key('PF3')
        ui.open()
        self.assertEqual(ui.stats(), {'opens': 2, 'keys': 5, 'alarms': 1})


BLUE, PINK, GREEN, YELLOW, WHITE = 1, 3, 4, 6, 7  # EAB colour codes (settings_colour_t)
REVERSE = 2
ATTR_NORMAL, ATTR_BRIGHT = 0xE0, 0xE8


def at(row, col):
    return 80 + (row - 1) * 80 + (col - 1)


class Drawn:
    """A SetupUi's front image, read by row and column."""

    def __init__(self, ui):
        ui.draw()
        (self.regen, self.eab) = (ui.regen(), ui.eab())

    def text(self, row, col, n):
        return ''.join(MAIN[c] for c in self.regen[at(row, col):at(row, col) + n])

    def colour(self, row, col):
        return self.eab[at(row, col)] >> 3 & 7

    def highlight(self, row, col):
        return self.eab[at(row, col)] >> 6

    def says(self, row, col, text, colour, highlight=0):
        """text at (row, col), every cell in colour with highlight."""
        return (self.text(row, col, len(text)) == text
                and all(self.colour(row, col + i) == colour and self.highlight(row, col + i) == highlight
                        for i in range(len(text))))


class TestImages(unittest.TestCase):
    def test_the_status_line_says_setup(self):
        ui = core.SetupUi()
        ui.open()
        image = Drawn(ui)
        self.assertEqual(''.join(MAIN[c] for c in image.regen[0:5]), 'SETUP')
        self.assertEqual(set(image.regen[5:80]), {0})

    def test_the_menu(self):
        ui = core.SetupUi()
        ui.open()
        image = Drawn(ui)
        self.assertTrue(image.says(1, 29, 'Online Setup and Utility', BLUE))
        self.assertTrue(image.says(3, 1, 'Move cursor to desired selection and press ENTER.', GREEN))
        self.assertTrue(image.says(6, 3, 'Lock sessions', YELLOW, REVERSE))   # the selector
        for (row, text) in ((8, 'Setup display'), (10, 'Setup local functions'), (12, 'Set password'),
                            (14, 'Setup color palette'), (20, 'Go to offline setup')):
            self.assertTrue(image.says(row, 3, text, WHITE), text)
        self.assertTrue(image.says(24, 1, 'F3=Exit', BLUE))

    def test_each_pages_title_more_instruction_and_legend(self):
        more = {1: ' +', 2: '-+', 3: '-+', 4: '- '}
        legends = {1: ((1, 'F3=Exit'), (29, 'F8=Forward')),
                   2: ((1, 'F3=Exit'), (13, 'F7=Backward'), (29, 'F8=Forward')),
                   3: ((1, 'F3=Exit'), (13, 'F7=Backward'), (29, 'F8=Forward')),
                   4: ((1, 'F3=Exit'), (13, 'F7=Backward'))}
        for n in range(1, 5):
            image = Drawn(on_page(n))
            with self.subTest(page=n):
                self.assertTrue(image.says(1, 34, 'Display Setup', BLUE))
                self.assertTrue(image.says(1, 72, 'More:', WHITE))
                self.assertEqual(image.text(1, 78, 2), more[n])
                self.assertTrue(image.says(3, 1, 'Move cursor to desired choice, then press SPACEBAR to select.',
                                           GREEN))
                for (col, text) in legends[n]:
                    self.assertTrue(image.says(24, col, text, BLUE), text)

    def test_page_1s_labels_and_dot_leaders(self):
        image = Drawn(on_page(1))
        for (row, col, text, colour) in ((6, 3, 'Rule line', BLUE), (7, 5, 'Style', GREEN), (8, 5, 'Color', GREEN),
                                         (9, 5, 'Follows cursor', GREEN), (11, 3, 'Row/column indicator', GREEN),
                                         (13, 3, 'Cursor', BLUE), (14, 5, 'Style', GREEN), (15, 5, 'Blink', GREEN),
                                         (17, 3, 'Auto dim', GREEN), (18, 5, 'Delay (minutes)', GREEN),
                                         (19, 5, 'Lock sessions', GREEN)):
            self.assertTrue(image.says(row, col, text, colour), text)
        # Style ends at column 9: dots on the even columns 12-30, in green, and nothing between.
        self.assertEqual(image.text(7, 10, 21), '  . . . . . . . . . .')
        self.assertEqual({image.colour(7, c) for c in range(12, 31, 2)}, {GREEN})
        self.assertEqual(image.text(6, 13, 18).strip(), '')   # a heading has none

    def test_page_2s_dots_end_at_43(self):
        image = Drawn(on_page(2))
        self.assertEqual(image.text(7, 5, 4), 'Rate')
        self.assertEqual(image.text(7, 9, 35), '  ' + '. ' * 16 + '.')
        self.assertEqual(image.text(7, 44, 1), ' ')                 # then 45, Normal's attribute
        self.assertEqual(image.regen[at(7, 45)], ATTR_BRIGHT)

    def test_set_choices_yellow_others_white_and_pink_rows_pink(self):
        image = Drawn(on_page(1))
        self.assertTrue(image.says(7, 33, 'Horizontal', YELLOW, REVERSE))   # set, and the selector
        self.assertTrue(image.says(7, 47, 'Vertical', WHITE))
        self.assertTrue(image.says(15, 33, 'Yes', WHITE))
        self.assertTrue(image.says(15, 47, 'No', YELLOW))                  # Blink No, the default
        self.assertTrue(image.says(18, 47, '10', YELLOW))
        self.assertTrue(image.says(19, 33, 'Yes', WHITE))                  # Lock sessions: live since #122
        self.assertTrue(image.says(19, 47, 'No', YELLOW))                  # its default
        image = Drawn(on_page(2))
        for (row, col, text) in ((7, 46, 'Normal'), (8, 60, 'Normal'), (11, 46, 'Yes'), (13, 46, '3'),
                                 (15, 46, '3'), (17, 46, 'White'), (19, 60, 'No')):
            self.assertEqual(image.colour(row, col), YELLOW, (row, col, text))
            self.assertEqual(image.text(row, col, len(text)), text)
        for (row, col, text) in ((7, 60, 'Fast'), (8, 73, 'Long'), (12, 73, '2'), (13, 73, 'High'),
                                 (19, 46, 'Yes')):
            self.assertTrue(image.says(row, col, text, WHITE), (row, col, text))  # live since #107
        self.assertTrue(image.says(17, 60, 'Green', PINK))                       # Trim border stays pink

    def test_page_3_and_page_4(self):
        image = Drawn(on_page(3))
        self.assertTrue(image.says(6, 3, 'Four base color mapping', BLUE))
        self.assertTrue(image.says(8, 33, 'Red', WHITE, REVERSE))
        self.assertTrue(image.says(8, 57, 'Green', YELLOW))        # Input: green as itself
        self.assertTrue(image.says(12, 33, 'Blue', WHITE))
        self.assertTrue(image.says(11, 33, 'Red', YELLOW))         # Intensified input: red
        self.assertTrue(image.says(15, 33, 'Blue', YELLOW))        # Protected: blue
        self.assertTrue(image.says(18, 57, 'White', YELLOW))       # Intensified protected: white
        self.assertTrue(image.says(9, 45, 'Turquoise', WHITE))
        image = Drawn(on_page(4))
        self.assertTrue(image.says(6, 3, 'Liz4270', BLUE))
        self.assertTrue(image.says(7, 5, 'Monochrome', GREEN))
        self.assertTrue(image.says(7, 33, 'Yes', WHITE, REVERSE))
        self.assertTrue(image.says(7, 47, 'No', YELLOW))

    def test_the_selector_moves_and_space_moves_the_yellow(self):
        ui = on_page(1)
        ui.key('RIGHT')
        image = Drawn(ui)
        self.assertTrue(image.says(7, 33, 'Horizontal', YELLOW))
        self.assertTrue(image.says(7, 47, 'Vertical', WHITE, REVERSE))
        ui.key('SPACE')
        image = Drawn(ui)
        self.assertTrue(image.says(7, 33, 'Horizontal', WHITE))
        self.assertTrue(image.says(7, 47, 'Vertical', YELLOW, REVERSE))

    def test_set_choices_sit_in_an_intensified_field_for_monochrome(self):
        image = Drawn(on_page(1))
        self.assertEqual(image.regen[at(7, 32)], ATTR_BRIGHT)    # before Horizontal, set
        self.assertEqual(image.regen[at(7, 43)], ATTR_NORMAL)    # after it
        self.assertEqual(image.regen[at(7, 46)], ATTR_NORMAL)    # before Vertical
        self.assertEqual(image.regen[at(7, 4)], ATTR_NORMAL)     # before the label
        self.assertEqual(image.regen[at(1, 1)], ATTR_NORMAL)
        self.assertEqual(image.eab[at(7, 32)], 0)

    def test_every_character_has_a_display_code(self):
        ui = core.SetupUi()
        ui.open()
        self.assertNotIn(0x18, Drawn(ui).regen)
        for n in range(1, 5):
            self.assertNotIn(0x18, Drawn(on_page(n)).regen, n)

    def test_a_draw_builds_the_other_image_and_leaves_the_front_alone(self):
        ui = on_page(1)
        ui.draw()
        first = ui.front
        before = ui.regen() + ui.eab()
        ui.key('RIGHT')
        ui.draw()
        self.assertNotEqual(ui.front, first)
        self.assertEqual(ctypes.string_at(first, 2000), before[:2000])   # the old front, untouched
        ui.draw()
        self.assertEqual(ui.front, first)


OFFLINE_MENU, CUSTOMIZE = UI['OFFLINE_MENU'], UI['CUSTOMIZE']
LEFT_OFFLINE = UI['LEFT_OFFLINE']
# Offline setup (#110), as photographed: captures/photos-20261012/offline-setup-1 to 3.
OFFLINE_ITEMS = [(6, 3), (8, 3), (10, 3), (12, 3)]
CUSTOMIZATION = [(6, 34), (6, 47), (6, 60), (9, 34), (9, 47), (9, 60), (9, 73), (10, 34), (10, 47), (10, 60),
                 (10, 73), (12, 34), (12, 47), (14, 34), (14, 47), (17, 34), (17, 47), (20, 34), (20, 47)]
CUSTOMIZATION_PINK = CUSTOMIZATION[3:]  # all but Screen rows x columns
WARNING = 'Sessions will be terminated, press Enter to continue or any other key to quit.'


def on_password(settings=None):
    """A SetupUi opened, then Enter on Set password, the fourth item (#122)."""
    ui = core.SetupUi(settings)
    ui.open()
    for _ in range(3):
        ui.key('DOWN')
    ui.key('ENTER')
    return ui


def typed(ui, keys, shift=False):
    return [ui.key(key, shift) for key in keys]


def set_abc(ui):
    """A, B, C, Enter, the same, Enter: the password set."""
    typed(ui, ABC)
    ui.key('ENTER')
    typed(ui, ABC)
    return ui.key('ENTER')


class TestPasswordSet(unittest.TestCase):
    """Password Set (#122), as captured on Oct 13 (captures/photos-20261013/password-*.jpg)."""

    def test_set_password_opens_it_blank_the_cursor_in_the_first_field(self):
        ui = on_password()
        self.assertEqual((ui.screen, place(ui.cursor_at), ui.selector_at), (PASSWORD, (7, 41), 0))

    def test_each_key_moves_the_cursor_on(self):
        ui = on_password()
        self.assertEqual(typed(ui, ABC), [NONE] * 3)
        self.assertEqual(place(ui.cursor_at), (7, 44))

    def test_enter_to_the_second_field_then_enter_sets_it(self):
        ui = on_password()
        typed(ui, ABC)
        self.assertEqual(ui.key('ENTER'), NONE)
        self.assertEqual(place(ui.cursor_at), (9, 41))
        typed(ui, ABC)
        self.assertEqual(ui.key('ENTER'), PASSWORD_SET)
        self.assertEqual(ui.settings['password'], core.lock_hash([(core.scan_codes()[k], False) for k in ABC]))
        self.assertEqual(place(ui.cursor_at), (9, 44))  # after the asterisks, which stay (password-6)

    def test_a_mismatch_clears_both_fields(self):
        ui = on_password()
        typed(ui, ABC)
        ui.key('ENTER')
        typed(ui, ('A', 'B', 'D'))
        self.assertEqual(ui.key('ENTER'), NONE)
        self.assertEqual((ui.settings['password'], place(ui.cursor_at)), (0, (7, 41)))
        self.assertEqual(Drawn(ui).text(22, 2, len(INVALID)), INVALID)

    def test_case_counts(self):
        ui = on_password()
        typed(ui, ABC)
        ui.key('ENTER')
        typed(ui, ABC, shift=True)
        self.assertEqual(ui.key('ENTER'), NONE)
        self.assertEqual(ui.settings['password'], 0)

    def test_enter_on_an_empty_first_field_is_invalid(self):
        ui = on_password()
        self.assertEqual(ui.key('ENTER'), NONE)
        self.assertEqual((ui.settings['password'], place(ui.cursor_at)), (0, (7, 41)))
        self.assertEqual(Drawn(ui).text(22, 2, len(INVALID)), INVALID)

    def test_the_eleventh_key_goes_into_the_second_field(self):
        ui = on_password()
        typed(ui, 'ABCDEFGHIJ')
        self.assertEqual(place(ui.cursor_at), (9, 41))
        ui.key('K')
        self.assertEqual(place(ui.cursor_at), (9, 42))

    def test_ten_keys_then_enter_submits_with_the_second_field_empty(self):
        ui = on_password()
        typed(ui, 'ABCDEFGHIJ')
        self.assertEqual(ui.key('ENTER'), NONE)
        self.assertEqual((ui.settings['password'], place(ui.cursor_at)), (0, (7, 41)))

    def test_the_second_field_full_sounds_the_alarm(self):
        ui = on_password()
        typed(ui, 'ABCDEFGHIJ')
        typed(ui, 'ABCDEFGHIJ')
        self.assertEqual(place(ui.cursor_at), (9, 50))  # a full field keeps the cursor on its last cell
        self.assertEqual(ui.key('K'), ALARM)
        self.assertEqual(ui.key('ENTER'), PASSWORD_SET)
        self.assertEqual(place(ui.cursor_at), (9, 50))  # and after the change, not on the attribute at 51

    def test_keys_that_type_nothing_sound_the_alarm_and_change_nothing(self):
        for key in ('TAB', 'BACKSPACE', 'LEFT', 'RIGHT', 'UP', 'DOWN', 'SPACE', 'PF7', 'KP_1', 'CAPS', 'SETUP'):
            ui = on_password()
            ui.key('A')
            self.assertEqual(ui.key(key), ALARM, key)
            self.assertEqual(place(ui.cursor_at), (7, 42), key)

    def test_after_a_change_keys_and_enter_sound_the_alarm(self):
        ui = on_password()
        set_abc(ui)
        self.assertEqual((ui.key('A'), ui.key('ENTER')), (ALARM, ALARM))

    def test_f11_clears_the_password(self):
        ui = on_password(screen.Settings(password=1234))
        ui.key('A')
        self.assertEqual(ui.key('PF11'), PASSWORD_CLEARED)
        self.assertEqual((ui.settings['password'], place(ui.cursor_at)), (0, (7, 41)))
        self.assertEqual(Drawn(ui).text(22, 2, 26), 'Password has been cleared.')

    def test_f3_goes_back_to_the_menu_on_set_password(self):
        ui = on_password()
        self.assertEqual(ui.key('PF3'), NONE)
        self.assertEqual((ui.screen, place(ui.selector_at), ui.cursor_at), (MENU, (12, 3), 0))

    def test_reopened_it_is_blank(self):
        ui = on_password()
        typed(ui, ABC)
        ui.key('PF3')
        ui.key('ENTER')
        image = Drawn(ui)
        self.assertEqual((image.text(7, 41, 10), image.text(9, 41, 10), image.text(22, 2, 10)),
                         ('_' * 10, '_' * 10, ' ' * 10))
        self.assertEqual(place(ui.cursor_at), (7, 41))


class TestPasswordImage(unittest.TestCase):
    def test_the_screen_as_photographed(self):
        # captures/photos-20261013/password-1-set-screen.jpg
        image = Drawn(on_password())
        title = 'Password Set'
        self.assertTrue(image.says(1, (80 - len(title)) // 2 + 1, title, BLUE))
        self.assertTrue(image.says(3, 1, 'Specify password twice and press ENTER.', GREEN))
        self.assertTrue(image.says(6, 3, 'Lock sessions', BLUE))
        for row in (7, 9):
            self.assertTrue(image.says(row, 5, 'Password', GREEN))
            self.assertEqual(image.text(row, 13, 25), '  ' + '. ' * 11 + '.')  # dots on 15, 17, ... 37
            self.assertTrue(image.says(row, 41, '_' * 10, WHITE))
        self.assertTrue(image.says(24, 1, 'F3=Exit', BLUE))
        self.assertTrue(image.says(24, 43, 'F11=Clear password', BLUE))
        self.assertEqual(''.join(MAIN[c] for c in image.regen[0:5]), 'SETUP')

    def test_asterisks_for_the_keys_and_the_messages_in_yellow(self):
        ui = on_password()
        typed(ui, ABC)
        self.assertTrue(Drawn(ui).says(7, 41, '***' + '_' * 7, WHITE))
        ui.key('ENTER')
        typed(ui, ABC)
        ui.key('ENTER')
        image = Drawn(ui)
        self.assertTrue(image.says(9, 41, '***' + '_' * 7, WHITE))
        self.assertTrue(image.says(22, 2, 'Password has been changed.', YELLOW))

    def test_the_front_images_cursor_moves_with_its_draw(self):
        ui = on_password()
        ui.draw()
        self.assertEqual(place(ui.cursor), (7, 41))
        ui.key('A')
        self.assertEqual(place(ui.cursor), (7, 41))  # the front image is still the old one
        ui.draw()
        self.assertEqual(place(ui.cursor), (7, 42))


class TestLockSessions(unittest.TestCase):
    """The menu's Lock sessions (#122): with a password set it locks at once (lock-1); with none, Password Set
    first (lock-4), where F3 after a change locks and F3 with nothing set goes back to the menu."""

    def test_with_a_password_it_locks_at_once(self):
        ui = core.SetupUi(screen.Settings(password=1234))
        ui.open()
        self.assertEqual(ui.key('ENTER'), LOCK)
        self.assertEqual(ui.screen, OFF)

    def test_with_none_it_opens_password_set(self):
        ui = core.SetupUi()
        ui.open()
        self.assertEqual(ui.key('ENTER'), NONE)
        self.assertEqual((ui.screen, place(ui.cursor_at)), (PASSWORD, (7, 41)))

    def test_f3_after_a_change_locks(self):
        ui = core.SetupUi()
        ui.open()
        ui.key('ENTER')
        self.assertEqual(set_abc(ui), PASSWORD_SET)
        self.assertEqual(ui.key('PF3'), LOCK)
        self.assertEqual(ui.screen, OFF)

    def test_f3_with_nothing_set_goes_back_to_lock_sessions(self):
        ui = core.SetupUi()
        ui.open()
        ui.key('ENTER')
        self.assertEqual(ui.key('PF3'), NONE)
        self.assertEqual((ui.screen, place(ui.selector_at)), (MENU, (6, 3)))

    def test_set_then_cleared_f3_goes_back_to_the_menu(self):
        ui = core.SetupUi()
        ui.open()
        ui.key('ENTER')
        set_abc(ui)
        ui.key('PF11')
        self.assertEqual(ui.key('PF3'), NONE)
        self.assertEqual(ui.screen, MENU)

    def test_set_password_s_f3_never_locks(self):
        ui = on_password()
        set_abc(ui)
        self.assertEqual(ui.key('PF3'), NONE)
        self.assertEqual((ui.screen, place(ui.selector_at)), (MENU, (12, 3)))


def at_warning(settings=None):
    """A SetupUi opened, Up to Go to offline setup, Enter: the warning."""
    ui = core.SetupUi(settings)
    ui.open()
    ui.key('UP')
    ui.key('ENTER')
    return ui


def in_offline_setup(settings=None):
    ui = at_warning(settings)
    ui.key('ENTER')
    return ui


def customizing(settings=None):
    ui = in_offline_setup(settings)
    ui.key('ENTER')
    return ui


class TestOfflineSetup(unittest.TestCase):
    def test_enter_on_go_to_offline_setup_shows_the_warning(self):
        ui = core.SetupUi()
        ui.open()
        ui.key('UP')
        self.assertEqual(place(ui.selector_at), (20, 3))
        self.assertEqual(ui.key('ENTER'), NONE)
        self.assertEqual((ui.screen, place(ui.selector_at), ui.offline), (MENU, (20, 3), False))
        self.assertTrue(Drawn(ui).says(23, 2, WARNING, YELLOW))

    def test_enter_at_the_warning_goes_offline_on_customize_display_station(self):
        ui = at_warning()
        self.assertEqual(ui.key('ENTER'), NONE)
        self.assertEqual((ui.screen, place(ui.selector_at), ui.offline), (OFFLINE_MENU, (6, 3), True))

    def test_any_other_key_quits_the_warning_and_does_nothing_else(self):
        for key in ('DOWN', 'PF3', 'SPACE', 'TAB'):
            ui = at_warning()
            self.assertEqual(ui.key(key), NONE, key)
            self.assertEqual((ui.screen, place(ui.selector_at), ui.offline), (MENU, (20, 3), False), key)
            self.assertEqual(Drawn(ui).text(23, 2, len(WARNING)).strip(), '', key)

    def test_the_offline_menu_walks_round_and_its_other_items_sound_the_alarm(self):
        ui = in_offline_setup()
        seen = []
        for _ in range(4):
            self.assertEqual(ui.key('DOWN'), NONE)
            seen.append(place(ui.selector_at))
        self.assertEqual(seen, OFFLINE_ITEMS[1:] + OFFLINE_ITEMS[:1])
        for item in (1, 2, 3):
            ui = in_offline_setup()
            for _ in range(item):
                ui.key('DOWN')
            self.assertEqual(ui.key('ENTER'), ALARM, item)
            self.assertEqual(ui.screen, OFFLINE_MENU)

    def test_customize_display_station_opens_customization_top_left(self):
        ui = in_offline_setup()
        self.assertEqual(ui.key('ENTER'), NONE)
        self.assertEqual((ui.screen, place(ui.selector_at), ui.offline), (CUSTOMIZE, (6, 34), True))

    def test_customizations_choices_in_reading_order(self):
        ui = customizing()
        seen = [place(ui.selector_at)]
        for _ in range(len(CUSTOMIZATION) - 1):
            ui.key('RIGHT')
            seen.append(place(ui.selector_at))
        self.assertEqual(seen, CUSTOMIZATION)

    def test_space_on_a_size_sets_the_model(self):
        for (col, model) in ((34, 2), (47, 3), (60, 4)):
            ui = customizing(screen.Settings(model=3 if model != 3 else 2))
            move_to(ui, 6, col)
            self.assertEqual(ui.key('SPACE'), CHANGED, col)
            self.assertEqual(ui.settings['model'], model)
            self.assertTrue(Drawn(ui).says(6, col, ('24 x 80', '32 x 80', '43 x 80')[model - 2], YELLOW, REVERSE))

    def test_the_other_rows_are_pink_and_sound_the_alarm(self):
        for (row, col) in CUSTOMIZATION_PINK:
            ui = customizing()
            move_to(ui, row, col)
            before = ui.settings
            self.assertEqual(ui.key('SPACE'), ALARM, (row, col))
            self.assertEqual(ui.settings, before, (row, col))

    def test_f8_and_f7_sound_the_alarm(self):
        for key in ('PF8', 'PF7'):
            ui = customizing()
            self.assertEqual(ui.key(key), ALARM, key)
            self.assertEqual(ui.screen, CUSTOMIZE, key)

    def test_f3_on_customization_goes_back_to_the_offline_menu(self):
        ui = customizing()
        self.assertEqual(ui.key('PF3'), NONE)
        self.assertEqual((ui.screen, place(ui.selector_at), ui.offline), (OFFLINE_MENU, (6, 3), True))

    def test_f3_on_the_offline_menu_leaves(self):
        ui = in_offline_setup()
        self.assertEqual(ui.key('PF3'), LEFT_OFFLINE)
        self.assertEqual((ui.screen, ui.offline), (OFF, False))

    def test_opening_again_starts_on_the_menu_without_the_warning(self):
        ui = at_warning()
        ui.key('DOWN')  # quits it
        ui.key('PF3')
        ui.open()
        self.assertEqual((ui.screen, place(ui.selector_at)), (MENU, (6, 3)))
        self.assertEqual(Drawn(ui).text(23, 2, len(WARNING)).strip(), '')


class TestOfflineImages(unittest.TestCase):
    def test_the_offline_menu(self):
        image = Drawn(in_offline_setup())
        self.assertTrue(image.says(1, 34, 'Offline Setup', BLUE))
        self.assertTrue(image.says(3, 1, 'Move cursor to desired selection and press ENTER.', GREEN))
        self.assertTrue(image.says(6, 3, 'Customize display station', YELLOW, REVERSE))
        for (row, text) in ((8, 'Set printer definition utility'), (10, 'Update serial number'),
                            (12, 'Test display station')):
            self.assertTrue(image.says(row, 3, text, WHITE), text)
        self.assertTrue(image.says(24, 1, 'F3=Exit', BLUE))
        self.assertEqual(''.join(MAIN[c] for c in image.regen[0:5]), 'SETUP')

    def test_customization(self):
        image = Drawn(customizing())
        self.assertTrue(image.says(1, 34, 'Customization', BLUE))
        self.assertEqual(image.text(1, 72, 8).strip(), '')  # no More: marker, with no second page
        self.assertTrue(image.says(3, 1, 'Move cursor to desired choice, then press SPACEBAR to select.', GREEN))
        for (row, col, text, colour) in ((6, 3, 'Screen rows x columns', GREEN), (9, 3, 'Keyboard layout', GREEN),
                                         (12, 3, 'Numeric lock', GREEN), (14, 3, 'Underscore style', GREEN),
                                         (16, 3, 'Unprotected field', BLUE), (17, 5, 'Markup', GREEN),
                                         (20, 3, 'Black-On-White emulation', GREEN)):
            self.assertTrue(image.says(row, col, text, colour), text)
        self.assertTrue(image.says(6, 34, '24 x 80', YELLOW, REVERSE))  # the selector on the set size
        self.assertTrue(image.says(6, 47, '32 x 80', WHITE))
        for (row, col, text) in ((9, 34, 'Standard'), (12, 47, 'No'), (14, 47, '_____'), (17, 47, 'No'),
                                 (20, 47, 'No')):
            self.assertTrue(image.says(row, col, text, YELLOW), text)  # what the firmware does, as set
        for (row, col, text) in ((9, 47, 'APL'), (10, 73, 'User4'), (12, 34, 'Yes'), (14, 34, '- - -'),
                                 (17, 34, 'Yes'), (20, 34, 'Yes')):
            self.assertTrue(image.says(row, col, text, PINK), text)
        self.assertTrue(image.says(24, 1, 'F3=Exit', BLUE))
        self.assertEqual(image.text(24, 13, 30).strip(), '')  # no F7 or F8


def on_about(forward=0, version='0.0.0', commit='5eb8024', board='Fruit Jam (ID 11)'):
    """A SetupUi identified, opened, F10 to About, then F8 forward times."""
    ui = core.SetupUi()
    ui.identify(version, commit, board)
    ui.open()
    ui.key('PF10')
    for _ in range(forward):
        ui.key('PF8')
    return ui


def to_offline_menu(ui):
    """Up to Go to offline setup, Enter for the warning, Enter for the Offline Setup menu (#110)."""
    ui.open()
    ui.key('UP')
    ui.key('ENTER')
    ui.key('ENTER')


class TestAboutKeys(unittest.TestCase):
    def test_f10_on_the_menu_opens_page_1(self):
        ui = core.SetupUi()
        ui.open()
        self.assertEqual(ui.key('PF10'), NONE)
        self.assertEqual(ui.screen, ABOUT)
        self.assertEqual(ui.selector_at, 0)
        self.assertEqual(ui.cursor_at, 0)

    def test_f8_walks_to_the_last_page_then_sounds_the_alarm(self):
        ui = on_about()
        for _ in range(LICENSE_PAGES):
            self.assertEqual(ui.key('PF8'), NONE)
        self.assertEqual(ui.key('PF8'), ALARM)
        self.assertEqual(ui.screen, ABOUT)

    def test_f7_walks_back_to_page_1_then_sounds_the_alarm(self):
        ui = on_about(LICENSE_PAGES)
        for _ in range(LICENSE_PAGES):
            self.assertEqual(ui.key('PF7'), NONE)
        self.assertEqual(ui.key('PF7'), ALARM)
        self.assertEqual(Drawn(ui).text(3, 1, 30), 'Press F8 to read the licenses.')

    def test_f3_goes_back_with_the_selector_where_f10_left_it(self):
        for forward in (0, 1):
            with self.subTest(forward=forward):
                ui = core.SetupUi()
                ui.open()
                for _ in range(3):
                    ui.key('DOWN')  # Set password
                ui.key('PF10')
                for _ in range(forward):
                    ui.key('PF8')
                self.assertEqual(ui.key('PF3'), NONE)
                self.assertEqual(ui.screen, MENU)
                self.assertEqual(place(ui.selector_at), (12, 3))
                ui.key('ENTER')
                self.assertEqual(ui.screen, PASSWORD)  # the round trip leaves Set password as it was

    def test_every_other_key_sounds_the_alarm(self):
        for key in ('ENTER', 'SPACE', 'UP', 'DOWN', 'LEFT', 'RIGHT', 'PF10', 'PF11', 'A'):
            with self.subTest(key=key):
                ui = on_about()
                self.assertEqual(ui.key(key), ALARM)
                self.assertEqual(ui.screen, ABOUT)

    def test_f10_anywhere_else_sounds_the_alarm(self):
        ui = on_page(1)
        self.assertEqual(ui.key('PF10'), ALARM)
        ui = core.SetupUi()
        ui.open()
        for _ in range(3):
            ui.key('DOWN')
        ui.key('ENTER')
        self.assertEqual(ui.key('PF10'), ALARM)
        self.assertEqual(ui.screen, PASSWORD)
        ui = core.SetupUi()
        to_offline_menu(ui)
        self.assertEqual(ui.key('PF10'), ALARM)
        self.assertEqual(ui.screen, OFFLINE_MENU)
        ui.key('ENTER')
        self.assertEqual(ui.screen, CUSTOMIZE)
        self.assertEqual(ui.key('PF10'), ALARM)

    def test_f10_with_the_offline_warning_up_closes_it(self):
        ui = core.SetupUi()
        ui.open()
        ui.key('UP')
        ui.key('ENTER')
        self.assertEqual(ui.key('PF10'), NONE)
        self.assertEqual(ui.screen, MENU)
        self.assertEqual(Drawn(ui).text(23, 2, 8), ' ' * 8)


class TestAboutPages(unittest.TestCase):
    def test_the_menu_legend_offers_f10_online_only(self):
        ui = core.SetupUi()
        ui.open()
        self.assertTrue(Drawn(ui).says(24, 13, 'F10=About', BLUE))
        ui = core.SetupUi()
        to_offline_menu(ui)
        self.assertEqual(Drawn(ui).text(24, 13, 9), ' ' * 9)

    def test_page_1(self):
        image = Drawn(on_about())
        self.assertTrue(image.says(1, 34, 'About Liz4270', BLUE))
        self.assertEqual(image.text(1, 72, 8), 'More:  +')
        self.assertTrue(image.says(3, 1, 'Press F8 to read the licenses.', GREEN))
        self.assertTrue(image.says(6, 3, 'Firmware', BLUE))
        for (row, label, value) in ((7, 'Version', '0.0.0'), (8, 'Commit', '5eb8024'),
                                    (9, 'Board', 'Fruit Jam (ID 11)')):
            self.assertTrue(image.says(row, 5, label, GREEN), label)
            first = 5 + len(label) + 1
            first += first % 2  # on the last dot's parity: column 30's
            self.assertTrue(all(image.says(row, col, '.', GREEN) for col in range(first, 31, 2)), label)
            self.assertTrue(image.says(row, 33, value, WHITE), label)
        self.assertTrue(image.says(11, 3, 'Credits', BLUE))
        for (i, credit) in enumerate(bake_about.CREDITS):
            self.assertTrue(image.says(12 + i, 5, credit.component, WHITE), credit)
            self.assertTrue(image.says(12 + i, 25, credit.by, WHITE), credit)
            self.assertTrue(image.says(12 + i, 62, credit.license, WHITE), credit)
        self.assertTrue(image.says(21, 3, 'Named for Liz, the mainframe cat.', WHITE))
        self.assertTrue(image.says(24, 1, 'F3=Exit', BLUE))
        self.assertEqual(image.text(24, 13, 11), ' ' * 11)
        self.assertTrue(image.says(24, 29, 'F8=Forward', BLUE))

    def test_each_license_page(self):
        pages = bake_about.pages()
        self.assertEqual(len(pages), LICENSE_PAGES)
        for (n, page) in enumerate(pages, start=1):
            with self.subTest(page=n):
                image = Drawn(on_about(n))
                last = n == LICENSE_PAGES
                self.assertTrue(image.says(1, 34, 'About Liz4270', BLUE))
                self.assertEqual(image.text(1, 72, 8), 'More: -' + (' ' if last else '+'))
                self.assertTrue(image.says(3, 1, page.heading, GREEN))
                for (i, line) in enumerate(page.lines):
                    if line:
                        self.assertTrue(image.says(5 + i, 2, line, WHITE), line)
                self.assertEqual(image.text(5 + len(page.lines), 2, 78), ' ' * 78)
                self.assertTrue(image.says(24, 1, 'F3=Exit', BLUE))
                self.assertTrue(image.says(24, 13, 'F7=Backward', BLUE))
                if last:
                    self.assertEqual(image.text(24, 29, 10), ' ' * 10)
                else:
                    self.assertTrue(image.says(24, 29, 'F8=Forward', BLUE))

    def test_an_attribute_before_each_run_for_monochrome(self):
        image = Drawn(on_about())
        for (row, col) in ((6, 2), (7, 4), (7, 32), (11, 2), (12, 4), (21, 2)):
            self.assertGreaterEqual(image.regen[at(row, col)], 0xC0, (row, col))
        image = Drawn(on_about(1))
        self.assertGreaterEqual(image.regen[at(5, 1)], 0xC0)

    def test_the_identity_is_cut_to_its_fields(self):
        image = Drawn(on_about(version='0123456789abcdefXYZ', commit='0123456789abcdef-dirty-XYZ',
                               board='0123456789abcdef0123456789abcdefXYZ'))
        self.assertEqual(image.text(7, 33, 16), '0123456789abcde ')
        self.assertEqual(image.text(8, 33, 24), '0123456789abcdef-dirty- ')
        self.assertEqual(image.text(9, 33, 32), '0123456789abcdef0123456789abcde ')

    def test_a_dirty_or_unknown_commit_fits_whole(self):
        for commit in ('5eb8024-dirty', '5eb8024a1b2c-dirty', 'unknown'):
            with self.subTest(commit=commit):
                self.assertTrue(Drawn(on_about(commit=commit)).says(8, 33, commit, WHITE))

    def test_unidentified_values_are_blank(self):
        ui = core.SetupUi()
        ui.open()
        ui.key('PF10')
        self.assertEqual(Drawn(ui).text(7, 33, 20), ' ' * 20)


if __name__ == '__main__':
    unittest.main()
