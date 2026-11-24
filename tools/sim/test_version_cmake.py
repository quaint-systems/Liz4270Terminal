# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""firmware/version.cmake (#132): what a build calls itself, at its tag and away from it, and a header that
holds still while nothing changes, so nothing recompiles."""

import os
import subprocess
import tempfile
import unittest

import version_cmake

# The scratch repos' commits and tags by CoffeeMuse, with no git config but each repo's own: a global or system
# one that signs commits or tags, or sets core.abbrev, would break them (as tools/manual/test_edition.py's).
ENV = {**os.environ, 'GIT_AUTHOR_NAME': 'CoffeeMuse', 'GIT_AUTHOR_EMAIL': 'coffeemuse@example.invalid',
       'GIT_COMMITTER_NAME': 'CoffeeMuse', 'GIT_COMMITTER_EMAIL': 'coffeemuse@example.invalid',
       'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1'}
NUMBER = '0.6.0'
OURS = '// Copyright (c) 2026, CoffeeMuse\n// SPDX-License-Identifier: ISC\n\n'


class Repo:
    """A scratch repository with one commit, firmware/ in it."""

    def __init__(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = self.dir.name
        self.git('init', '-q', '-b', 'main')
        self.write('firmware/main.c', 'int main(void) { return 0; }\n')
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
        self.git('commit', '-q', '--allow-empty', '-m', message)

    def tag(self, name):
        """An annotated tag at HEAD, as a release is tagged."""
        self.git('tag', '-a', name, '-m', name)

    def head(self):
        return self.git('rev-parse', '--short', 'HEAD')

    def name(self, number=NUMBER, **kwargs):
        return version_cmake.run(os.path.join(self.root, 'firmware'), number, env=ENV, **kwargs)


@unittest.skipUnless(version_cmake.available(), 'needs cmake and git')
class TestName(unittest.TestCase):

    def setUp(self):
        self.repo = Repo()
        self.addCleanup(self.repo.dir.cleanup)

    def test_before_any_tag_a_build_is_dev(self):
        self.assertEqual(self.repo.name(), ('0.6.0+dev', self.repo.head()))

    def test_at_its_annotated_tag_a_clean_build_is_the_release(self):
        self.repo.tag('v0.6.0')
        self.assertEqual(self.repo.name(), ('0.6.0', self.repo.head()))

    def test_at_the_tag_on_a_detached_head_it_is_still_the_release(self):
        # As a release build checks the tag out (#133).
        self.repo.tag('v0.6.0')
        self.repo.git('checkout', '-q', '--detach', 'v0.6.0')
        self.assertEqual(self.repo.name(), ('0.6.0', self.repo.head()))

    def test_one_commit_past_the_tag_is_dev(self):
        self.repo.tag('v0.6.0')
        self.repo.commit('next')
        self.assertEqual(self.repo.name(), ('0.6.0+dev', self.repo.head()))

    def test_an_edited_tree_at_the_tag_is_dev_and_dirty(self):
        self.repo.tag('v0.6.0')
        self.repo.write('firmware/main.c', 'int main(void) { return 1; }\n')
        self.assertEqual(self.repo.name(), ('0.6.0+dev', self.repo.head() + '-dirty'))

    def test_an_edited_tree_at_a_tag_that_disagrees_is_dev(self):
        # As when a release's PR sets project() to the new number while HEAD still carries the last release's tag:
        # an edited tree is never a release, so no tag can disagree with it.
        self.repo.tag('v0.6.0')
        self.repo.write('firmware/main.c', 'int main(void) { return 1; }\n')
        self.assertEqual(self.repo.name('0.6.1'), ('0.6.1+dev', self.repo.head() + '-dirty'))

    def test_a_file_git_doesnt_know_makes_the_tree_dirty(self):
        # describe --dirty sees only tracked files, but a build reads what's there: a CMakeUserPresets.json, say,
        # which CMake picks up by itself. Anywhere in the tree, as describe looks at all of it.
        self.repo.tag('v0.6.0')
        self.repo.write('notes.txt', 'Mine\n')
        self.assertEqual(self.repo.name(), ('0.6.0+dev', self.repo.head() + '-dirty'))
        os.remove(os.path.join(self.repo.root, 'notes.txt'))
        self.repo.write('firmware/CMakeUserPresets.json', '{}\n')
        self.assertEqual(self.repo.name(), ('0.6.0+dev', self.repo.head() + '-dirty'))

    def test_a_file_git_doesnt_know_at_a_tag_that_disagrees_is_dev(self):
        self.repo.tag('v0.6.1')
        self.repo.write('notes.txt', 'Mine\n')
        self.assertEqual(self.repo.name(), ('0.6.0+dev', self.repo.head() + '-dirty'))

    def test_an_ignored_file_or_an_empty_directory_is_no_edit(self):
        # The build's own output, and the empty directory CI makes for the UF2 before it builds.
        self.repo.write('.gitignore', 'build/\n')
        self.repo.commit('ignore the build')
        self.repo.tag('v0.6.0')
        self.repo.write('firmware/build/liz4270.uf2', 'built\n')
        os.makedirs(os.path.join(self.repo.root, 'uf2'))
        self.assertEqual(self.repo.name(), ('0.6.0', self.repo.head()))

    def test_a_lightweight_tag_is_no_release(self):
        self.repo.git('tag', 'v0.6.0')
        self.assertEqual(self.repo.name(), ('0.6.0+dev', self.repo.head()))

    def test_a_tag_that_disagrees_with_project_stops_the_build(self):
        self.repo.tag('v0.6.1')
        with self.assertRaisesRegex(version_cmake.VersionError, r'v0\.6\.1(.|\n)*0\.6\.0'):
            self.repo.name()

    def test_other_tags_are_never_read_as_versions(self):
        # A hardware release's tag (#133), or a name like coax-tcp's liz4174-v1.
        self.repo.tag('board-revA')
        self.repo.tag('liz4174-v1')
        self.assertEqual(self.repo.name(), ('0.6.0+dev', self.repo.head()))
        self.repo.tag('v0.6.0')
        self.assertEqual(self.repo.name(), ('0.6.0', self.repo.head()))

    def test_without_git_the_commit_is_unknown(self):
        self.assertEqual(self.repo.name(git=''), ('0.6.0+dev', 'unknown'))

    def test_without_git_as_cmake_reports_it_the_commit_is_unknown(self):
        # What firmware/CMakeLists.txt passes when find_package(Git) finds none.
        self.assertEqual(self.repo.name(git='GIT_EXECUTABLE-NOTFOUND'), ('0.6.0+dev', 'unknown'))

    def test_a_commit_under_way_never_stops_the_build(self):
        # A commit holds index.lock; describe --dirty still answers, without writing the index.
        lock = os.path.join(self.repo.root, '.git', 'index.lock')
        with open(lock, 'w', encoding='utf-8'):
            pass
        self.assertEqual(self.repo.name(), ('0.6.0+dev', self.repo.head()))
        self.assertTrue(os.path.exists(lock))

    def test_a_tree_outside_any_repository_is_unknown(self):
        # A zip of the source: no .git in it, and git kept from looking above it, wherever the scratch
        # directory is.
        with tempfile.TemporaryDirectory() as bare:
            env = {**ENV, 'GIT_CEILING_DIRECTORIES': os.path.realpath(os.path.dirname(bare))}
            self.assertEqual(version_cmake.run(bare, NUMBER, env=env), ('0.6.0+dev', 'unknown'))

    def test_a_tree_inside_another_repository_is_unknown(self):
        # Unpacked or vendored into another project's checkout: never that project's commit, or its tags, even an
        # annotated v tag at its HEAD.
        outer = Repo()
        self.addCleanup(outer.dir.cleanup)
        outer.tag('v9.9.9')
        tree = os.path.join(outer.root, 'liz', 'firmware')
        os.makedirs(tree)
        self.assertEqual(version_cmake.run(tree, NUMBER, env=ENV), ('0.6.0+dev', 'unknown'))

    def test_the_header_holds_still_until_the_name_changes(self):
        # Ninja recompiles what includes it only when its time moves.
        with tempfile.TemporaryDirectory() as out:
            header = os.path.join(out, 'liz_version.h')
            self.repo.name(output=header)
            older = os.stat(header).st_mtime_ns - 10 ** 9
            os.utime(header, ns=(older, older))  # a second back, so any rewrite shows
            self.repo.name(output=header)
            self.assertEqual(os.stat(header).st_mtime_ns, older)
            self.repo.commit('next')
            self.repo.name(output=header)
            self.assertNotEqual(os.stat(header).st_mtime_ns, older)

    def test_the_header_opens_with_ours(self):
        with tempfile.TemporaryDirectory() as out:
            header = os.path.join(out, 'liz_version.h')
            self.repo.name(output=header)
            with open(header, encoding='utf-8') as stream:
                self.assertTrue(stream.read().startswith(OURS))

    def test_a_missing_argument_stops_it(self):
        result = subprocess.run(['cmake', '-DNUMBER=0.6.0', '-P', version_cmake.SCRIPT], capture_output=True,
                                text=True, timeout=60)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('-DSOURCE_DIR=', result.stderr)


if __name__ == '__main__':
    unittest.main()
