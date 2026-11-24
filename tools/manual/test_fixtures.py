# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The host screens recorded for the manual, docs/manual/screens/*.json (#136): each reads, draws, is
CoffeeMuse's under CC BY 4.0, and shows no address of the network it was recorded on."""

import glob
import json
import os
import re
import tempfile
import unittest

from PIL import Image

import manual_paths
import screen
import screen_fixture
import screens


def licence_problems(path):
    """What's wrong with the copyright and license fields as the file holds them."""
    with open(path, encoding='utf-8') as stream:
        data = json.load(stream)  # the file's own fields: read() keeps neither
    problems = []
    if not re.fullmatch(r'Copyright \(c\) \d{4}, CoffeeMuse', data.get('copyright', '')):
        problems.append(f"copyright is {data.get('copyright')!r}")
    if data.get('license') != 'CC-BY-4.0':
        problems.append(f"license is {data.get('license')!r}")
    return problems


def looks_like_an_address(host):
    """Whether a recording's host label could be an address: an IP, a host name or a port. A label such as
    MVS/CE has none of their dots or colons."""
    return bool(re.search(r'[.:]', host))


def hidden_text(fixture):
    """The addresses of anything but a blank in a non-display field."""
    governing = screen.fields(fixture.regen, fixture.model)
    end = screen.geometry(fixture.model).screen_end
    return [a for a in range(screen.SCREEN_START, end) if fixture.regen[a] and not screen.is_attribute(fixture.regen[a])
            and not screen.visible(governing[a])]


def fixtures():
    return sorted(glob.glob(os.path.join(manual_paths.MANUAL, 'screens', '*.json')))


class TestFixtures(unittest.TestCase):

    def test_there_is_a_fixture(self):
        self.assertIn('dslist.json', [os.path.basename(path) for path in fixtures()])

    def test_every_fixture_reads_and_draws(self):
        with tempfile.TemporaryDirectory() as out:
            for path in fixtures():
                drawn = os.path.join(out, 'drawn.png')
                screens.draw(screen_fixture.read(path), drawn)
                with Image.open(drawn) as image:
                    self.assertEqual(image.size, (640, 480), path)

    def test_every_fixture_is_coffeemuses_under_cc_by(self):
        for path in fixtures():
            self.assertEqual(licence_problems(path), [], path)

    def test_a_fixture_under_another_licence_is_refused(self):
        with tempfile.TemporaryDirectory() as out:
            path = os.path.join(out, 'other.json')
            with open(fixtures()[0], encoding='utf-8') as stream:
                data = json.load(stream)
            data.update(copyright='Copyright (c) 2026, Someone Else', license='All rights reserved')
            with open(path, 'w', encoding='utf-8') as stream:
                json.dump(data, stream)
            self.assertEqual(len(licence_problems(path)), 2)

    def test_no_fixture_holds_text_in_a_hidden_field(self):
        # oec writes what's typed into a non-display field, a password among them, and the PNG and text a
        # recording is checked by don't show it: only the file would.
        for path in fixtures():
            self.assertEqual(hidden_text(screen_fixture.read(path)), [], path)

    def test_text_in_a_hidden_field_is_found(self):
        regen = bytearray(2000)
        (regen[100], regen[101:105]) = (0xCC, b'\xa0\xa1\xa2\xa3')  # a non-display field, then four letters
        regen[120] = 0xC0
        f = screen_fixture.Fixture(2, 80, 0, bytes(regen), None, {})
        self.assertEqual(hidden_text(f), [101, 102, 103, 104])

    def test_a_host_label_that_looks_like_an_address_is_refused(self):
        for host in ('10.42.37.209', 'mvs.example.org', 'fe80::1', 'mvsce:3270'):
            self.assertTrue(looks_like_an_address(host), host)
        for host in ('MVS/CE', 'unknown', 'Hercules TK5'):
            self.assertFalse(looks_like_an_address(host), host)

    def test_no_fixture_shows_a_host_address(self):
        # oec writes the host's address at the status line's columns 46-79 unless it runs with
        # --no-hostname-status, as the recordings do.
        for path in fixtures():
            f = screen_fixture.read(path)
            self.assertEqual(f.regen[46:screen.COLS], bytes(screen.COLS - 46), path)
            self.assertFalse(looks_like_an_address(f.recorded['host']), path)


if __name__ == '__main__':
    unittest.main()
