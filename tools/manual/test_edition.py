# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

import datetime
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import manual_paths
import edition
import version_cmake

WHEN = '2026-10-14T12:00:00+00:00'
# The scratch repos' commits, by CoffeeMuse at WHEN, with no git config but each repo's own: a global or system
# one that signs commits or tags would break them.
ENV = {**os.environ, 'GIT_AUTHOR_NAME': 'CoffeeMuse', 'GIT_AUTHOR_EMAIL': 'coffeemuse@example.invalid',
       'GIT_COMMITTER_NAME': 'CoffeeMuse', 'GIT_COMMITTER_EMAIL': 'coffeemuse@example.invalid',
       'GIT_AUTHOR_DATE': WHEN, 'GIT_COMMITTER_DATE': WHEN, 'GIT_CONFIG_GLOBAL': os.devnull,
       'GIT_CONFIG_NOSYSTEM': '1'}
UNDECLARED = 'number = ""\nname = ""\nfirmware = ""\n'
DECLARED = 'number = "00"\nname = "First Edition (October 2026)"\nfirmware = "0.6.0"\n'
SIGNS = '[commit]\n\tgpgSign = true\n[tag]\n\tgpgSign = true\n[gpg]\n\tprogram = false\n'


class Repo:
    """A scratch git repository shaped like this one, as far as edition.py looks."""

    def __init__(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = self.dir.name
        self.git('init', '-q', '-b', 'main')
        self.write('firmware/CMakeLists.txt', 'project(liz4270 VERSION 0.6.0 LANGUAGES C CXX ASM)\n')
        self.write(edition.EDITION_FILE, UNDECLARED)
        self.write('docs/manual/manual.typ', 'Hello\n')
        self.commit('start')

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.root, env=ENV, check=True, capture_output=True,
                              text=True).stdout.strip()

    def write(self, path, text):
        full = os.path.join(self.root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, 'w', encoding='utf-8') as stream:
            stream.write(text)

    def commit(self, message):
        self.git('add', '-A')
        self.git('commit', '-q', '-m', message)

    def declare(self):
        self.write(edition.EDITION_FILE, DECLARED)
        self.commit('declare the first edition')

    def tag(self, name):
        """An annotated tag at HEAD, as a release is tagged (#132)."""
        self.git('tag', '-a', name, '-m', name)


class ScratchTest(unittest.TestCase):
    """A test on a fresh Repo, with edition.py's git under ENV too: a config that reached edition.py's side of
    a comparison and not Repo's or version.cmake's (core.abbrev, say) would fail it whatever edition.py did."""

    def setUp(self):
        self.repo = Repo()
        self.addCleanup(self.repo.dir.cleanup)
        self.enterContext(mock.patch.dict(os.environ, ENV))


class TestRepo(unittest.TestCase):

    def test_a_git_config_that_signs_never_reaches_a_scratch_repo(self):
        # A global or system config that signs commits or tags would break every test here. ENV is made as the
        # module loads, so a fresh Python loads it under such a config, as a machine set up so would.
        with tempfile.TemporaryDirectory() as scratch:
            config = os.path.join(scratch, 'gitconfig')
            with open(config, 'w', encoding='utf-8') as stream:
                stream.write(SIGNS)
            for variable in ('GIT_CONFIG_GLOBAL', 'GIT_CONFIG_SYSTEM'):
                with self.subTest(variable):
                    result = subprocess.run([sys.executable, '-c', 'import test_edition; '
                                             'test_edition.Repo().git("tag", "v0.6.0")'], cwd=manual_paths.HERE,
                                            env={**os.environ, variable: config}, capture_output=True, text=True,
                                            timeout=60)
                    self.assertEqual(result.returncode, 0, result.stderr[-400:])

    def test_a_git_config_that_abbreviates_otherwise_reaches_neither_side(self):
        # The tests read a scratch repo through edition.py and through Repo or version.cmake, and compare the two:
        # a config reaching only one side, with core.abbrev set, would give the hashes different lengths.
        with tempfile.TemporaryDirectory() as scratch:
            config = os.path.join(scratch, 'gitconfig')
            with open(config, 'w', encoding='utf-8') as stream:
                stream.write('[core]\n\tabbrev = 12\n')
            for variable in ('GIT_CONFIG_GLOBAL', 'GIT_CONFIG_SYSTEM'):
                with self.subTest(variable):
                    result = subprocess.run([sys.executable, '-m', 'unittest',
                                             'test_edition.TestFacts.test_the_facts_come_from_the_tree_and_head',
                                             'test_edition.TestTheFirmwareAgrees.test_untagged'],
                                            cwd=manual_paths.HERE, env={**os.environ, variable: config},
                                            capture_output=True, text=True, timeout=120)
                    self.assertEqual(result.returncode, 0, result.stderr[-600:])


class TestFacts(ScratchTest):

    def test_the_facts_come_from_the_tree_and_head(self):
        facts = edition.facts(self.repo.root)
        head = self.repo.git('rev-parse', '--short', 'HEAD')
        self.assertEqual(facts, edition.Facts('0.6.0+dev', head, 'October 14, 2026',
                                              int(datetime.datetime.fromisoformat(WHEN).timestamp())))

    def test_a_dirty_tree_says_so_and_keeps_heads_date(self):
        self.repo.write('docs/manual/manual.typ', 'Changed\n')
        facts = edition.facts(self.repo.root)
        self.assertTrue(facts.commit.endswith('-dirty'))
        self.assertEqual(facts.date, 'October 14, 2026')

    def test_at_its_annotated_tag_the_version_is_the_number(self):
        self.repo.tag('v0.6.0')
        facts = edition.facts(self.repo.root)
        self.assertEqual((facts.version, facts.commit), ('0.6.0', self.repo.git('rev-parse', '--short', 'HEAD')))

    def test_a_lightweight_tag_one_commit_past_or_an_edit_is_dev(self):
        self.repo.git('tag', 'v0.6.0')
        self.assertEqual(edition.facts(self.repo.root).version, '0.6.0+dev')
        self.repo.git('tag', '-d', 'v0.6.0')
        self.repo.tag('v0.6.0')
        self.repo.write('docs/manual/manual.typ', 'Changed\n')
        self.assertEqual(edition.facts(self.repo.root).version, '0.6.0+dev')
        self.repo.commit('next')
        self.assertEqual(edition.facts(self.repo.root).version, '0.6.0+dev')

    def test_a_tag_that_disagrees_with_project_stops_the_build(self):
        self.repo.tag('v0.6.1')
        with self.assertRaisesRegex(edition.BuildError, r'v0\.6\.1.*0\.6\.0'):
            edition.facts(self.repo.root)

    def test_raising_the_number_at_the_last_releases_tag_is_dev(self):
        # A release's PR sets project() to the new number while HEAD still carries the last release's tag: an
        # edited tree is never a release, so no tag can disagree with it.
        self.repo.tag('v0.6.0')
        self.repo.write('firmware/CMakeLists.txt', 'project(liz4270 VERSION 0.6.1 LANGUAGES C CXX ASM)\n')
        facts = edition.facts(self.repo.root)
        self.assertEqual((facts.version, facts.commit),
                         ('0.6.1+dev', self.repo.git('rev-parse', '--short', 'HEAD') + '-dirty'))

    def test_a_file_git_doesnt_know_makes_the_tree_dirty(self):
        # As firmware/version.cmake has it: describe --dirty sees only tracked files, but a build reads what's there.
        self.repo.tag('v0.6.0')
        self.repo.write('firmware/CMakeUserPresets.json', '{}\n')
        facts = edition.facts(self.repo.root)
        self.assertEqual((facts.version, facts.commit),
                         ('0.6.0+dev', self.repo.git('rev-parse', '--short', 'HEAD') + '-dirty'))

    def test_an_ignored_file_or_an_empty_directory_is_no_edit(self):
        self.repo.write('.gitignore', 'build/\n')
        self.repo.commit('ignore the build')
        self.repo.tag('v0.6.0')
        self.repo.write('build/manual/liz4270-letter.pdf', 'built\n')
        os.makedirs(os.path.join(self.repo.root, 'uf2'))
        facts = edition.facts(self.repo.root)
        self.assertEqual((facts.version, facts.commit), ('0.6.0', self.repo.git('rev-parse', '--short', 'HEAD')))

    def test_a_tree_inside_another_repository_is_refused(self):
        # Unpacked into another project's checkout, it would take that checkout's commit, tags and dates.
        self.repo.tag('v0.6.0')
        inner = os.path.join(self.repo.root, 'liz')
        os.makedirs(os.path.join(inner, 'firmware'))
        with open(os.path.join(inner, 'firmware', 'CMakeLists.txt'), 'w', encoding='utf-8') as stream:
            stream.write('project(liz4270 VERSION 0.6.0 LANGUAGES C CXX ASM)\n')
        with self.assertRaisesRegex(edition.BuildError, 'checkout of its own'):
            edition.facts(inner)

    def test_other_tags_are_never_read_as_versions(self):
        self.repo.tag('board-revA')
        self.assertEqual(edition.facts(self.repo.root).version, '0.6.0+dev')

    def test_this_checkout(self):
        facts = edition.facts(manual_paths.ROOT)
        self.assertRegex(facts.version, r'^\d+\.\d+\.\d+(\+dev)?$')
        self.assertRegex(facts.date, r'^[A-Z][a-z]+ \d{1,2}, \d{4}$')


class TestDecide(ScratchTest):

    def setUp(self):
        super().setUp()
        self.root = self.repo.root

    def test_any_build_but_a_release_is_a_draft(self):
        stamp = edition.decide(self.root, False, [])
        self.assertEqual((stamp.draft, stamp.form), (True, 'LZ01-4270-XX'))

    def test_a_release_needs_a_clean_tree(self):
        self.repo.tag('v0.6.0')
        self.repo.write('docs/manual/manual.typ', 'Changed\n')
        with self.assertRaisesRegex(edition.BuildError, 'clean tree'):
            edition.decide(self.root, True, [])

    def test_a_release_needs_a_tag(self):
        with self.assertRaisesRegex(edition.BuildError, 'release tag'):
            edition.decide(self.root, True, [])

    def test_a_release_needs_the_annotated_tag_of_projects_number(self):
        self.repo.git('tag', 'v0.6.0')  # lightweight
        with self.assertRaisesRegex(edition.BuildError, r'release tag.*v0\.6\.0'):
            edition.decide(self.root, True, [])

    def test_a_release_with_no_edition_declared_is_a_draft_and_says_so(self):
        self.repo.tag('v0.6.0')
        notes = []
        self.assertTrue(edition.decide(self.root, True, notes).draft)
        self.assertEqual(notes, ['no edition is declared in docs/manual/edition.toml: the release gets a draft'])

    def test_a_release_prints_the_declared_edition(self):
        self.repo.declare()
        self.repo.tag('v0.6.0')
        stamp = edition.decide(self.root, True, [])
        self.assertEqual(stamp, edition.Stamp(False, '00', 'First Edition (October 2026)', '0.6.0'))
        self.assertEqual(stamp.form, 'LZ01-4270-00')

    def test_a_release_refuses_an_edition_the_book_changed_since(self):
        self.repo.declare()
        self.repo.write('docs/manual/manual.typ', 'A new paragraph\n')
        self.repo.commit('change the book')
        self.repo.tag('v0.6.0')
        with self.assertRaisesRegex(edition.BuildError, r'declare a new edition .*\(docs/manual/manual\.typ\)'):
            edition.decide(self.root, True, [])

    def test_changes_outside_the_book_leave_the_edition_alone(self):
        self.repo.declare()
        self.repo.write('tools/manual/build.py', '# how it is built\n')
        self.repo.write('firmware/core/setup_ui.c', '/* what the screens show */\n')
        self.repo.commit('change the tools and the firmware')
        self.repo.tag('v0.6.0')
        self.assertFalse(edition.decide(self.root, True, []).draft)

    def test_an_edition_number_is_two_digits(self):
        self.repo.write(edition.EDITION_FILE, 'number = "1"\nname = "First"\nfirmware = "0.6.0"\n')
        with self.assertRaisesRegex(edition.BuildError, 'two digits'):
            edition.read_edition(self.root)

    def test_an_edition_needs_its_name_and_firmware(self):
        self.repo.write(edition.EDITION_FILE, 'number = "00"\n')
        with self.assertRaisesRegex(edition.BuildError, 'name and firmware'):
            edition.read_edition(self.root)

    def test_a_malformed_edition_stops_a_draft_too(self):
        for text in ('number = 5\nname = "First"\nfirmware = "0.6.0"\n', 'number = \n'):
            with self.subTest(text=text):
                self.repo.write(edition.EDITION_FILE, text)
                with self.assertRaisesRegex(edition.BuildError, 'docs/manual/edition.toml'):
                    edition.decide(self.root, False, [])

    def test_this_checkout_declares_no_edition_yet(self):
        self.assertEqual(edition.read_edition(manual_paths.ROOT).number, '')


@unittest.skipUnless(version_cmake.available(), 'needs cmake and git')
class TestTheFirmwareAgrees(ScratchTest):
    """edition.py names a build as firmware/version.cmake does (#132), so the manual's pictures show what that
    build's splash and About show."""

    def assert_agree(self):
        try:
            firmware = version_cmake.run(os.path.join(self.repo.root, 'firmware'),
                                         edition.project_version(self.repo.root), env=ENV)
        except version_cmake.VersionError:
            firmware = 'refused'
        try:
            facts = edition.facts(self.repo.root)
            manual = (facts.version, facts.commit)
        except edition.BuildError:
            manual = 'refused'
        self.assertEqual(manual, firmware)

    def test_untagged(self):
        self.assert_agree()

    def test_at_the_tag(self):
        self.repo.tag('v0.6.0')
        self.assert_agree()

    def test_at_the_tag_with_an_edit(self):
        self.repo.tag('v0.6.0')
        self.repo.write('docs/manual/manual.typ', 'Changed\n')
        self.assert_agree()

    def test_one_commit_past_the_tag(self):
        self.repo.tag('v0.6.0')
        self.repo.write('docs/manual/manual.typ', 'Changed\n')
        self.repo.commit('next')
        self.assert_agree()

    def test_at_a_lightweight_tag(self):
        self.repo.git('tag', 'v0.6.0')
        self.assert_agree()

    def test_at_a_tag_that_disagrees(self):
        self.repo.tag('v0.6.1')
        self.assert_agree()

    def test_at_another_projects_tag(self):
        self.repo.tag('liz4174-v1')
        self.assert_agree()

    def test_raising_the_number_at_the_last_releases_tag(self):
        self.repo.tag('v0.6.0')
        self.repo.write('firmware/CMakeLists.txt', 'project(liz4270 VERSION 0.6.1 LANGUAGES C CXX ASM)\n')
        self.assert_agree()

    def test_at_a_tag_that_disagrees_with_an_edit(self):
        self.repo.tag('v0.6.1')
        self.repo.write('docs/manual/manual.typ', 'Changed\n')
        self.assert_agree()

    def test_at_the_tag_with_a_file_git_doesnt_know(self):
        self.repo.tag('v0.6.0')
        self.repo.write('notes.txt', 'Mine\n')
        self.assert_agree()

    def test_at_the_tag_with_an_ignored_file_and_an_empty_directory(self):
        self.repo.write('.gitignore', 'build/\n')
        self.repo.commit('ignore the build')
        self.repo.tag('v0.6.0')
        self.repo.write('firmware/build/liz4270.uf2', 'built\n')
        os.makedirs(os.path.join(self.repo.root, 'uf2'))
        self.assert_agree()


if __name__ == '__main__':
    unittest.main()
