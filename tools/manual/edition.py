# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""What a manual build is: the firmware it describes, the commit, and whether it's an edition or a draft (#136).

docs/manual/edition.toml declares the current edition. A release build (--release) needs a clean tree
with HEAD at the annotated tag of project()'s number (#132), and prints the declared edition; it refuses
one that anything else under docs/manual/ has changed since. Before any edition is declared, and for every
other build, the manual is a draft: LZ01-4270-XX with the commit and its date. Dates and times come from
HEAD's commit, never the clock, so a commit always builds the same PDF.
"""

import datetime
import os
import re
import subprocess
import tomllib
from typing import NamedTuple

FORM_PREFIX = 'LZ01-4270-'
DRAFT = 'XX'
MANUAL_DIR = 'docs/manual'
EDITION_FILE = 'docs/manual/edition.toml'
MONTHS = ('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
          'November', 'December')


class BuildError(Exception):
    pass


class Facts(NamedTuple):
    version: str    # what the firmware built at HEAD calls itself (#132), as its splash and About show it
    commit: str     # the hash, -dirty from an edited tree (firmware_commit), as the splash and About show it
    date: str       # HEAD's commit date: "October 14, 2026"
    timestamp: int  # HEAD's commit time, the PDF's creation date


class Edition(NamedTuple):
    number: str     # '' until one is declared, then '00', '01', ...
    name: str       # "First Edition (October 2026)"
    firmware: str   # the first firmware version it describes


class Stamp(NamedTuple):
    draft: bool
    suffix: str     # DRAFT, or the edition's number
    name: str
    firmware: str

    @property
    def form(self):
        return FORM_PREFIX + self.suffix


DRAFT_STAMP = Stamp(True, DRAFT, '', '')


def git(root, *args):
    result = subprocess.run(['git', *args], cwd=root, capture_output=True, text=True)
    if result.returncode:
        raise BuildError(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout.strip()


def project_version(root):
    with open(os.path.join(root, 'firmware', 'CMakeLists.txt'), encoding='utf-8') as stream:
        match = re.search(r'project\(liz4270 VERSION (\d+\.\d+\.\d+)', stream.read())
    if not match:
        raise BuildError("firmware/CMakeLists.txt's project() has no VERSION")
    return match.group(1)


RELEASE_TAG = re.compile(r'v[0-9]')


def release_tags(root):
    """The annotated tags at HEAD named as releases (v[0-9]*), as firmware/version.cmake reads them: a
    lightweight tag, or one named otherwise, is never a release."""
    found = git(root, 'for-each-ref', '--points-at=HEAD', '--format=%(objecttype) %(refname:strip=2)',
                'refs/tags/')
    return [name for (kind, _, name) in (line.partition(' ') for line in found.splitlines())
            if kind == 'tag' and RELEASE_TAG.match(name)]


def firmware_commit(root):
    """The abbreviated hash, with -dirty from an edited tree, as firmware/version.cmake names it (#132): a
    tracked file changed, or a file git neither tracks nor ignores, anywhere in the tree."""
    commit = git(root, 'describe', '--always', '--dirty', '--exclude=*')
    if not commit.endswith('-dirty') and git(root, 'ls-files', '--others', '--exclude-standard', '--directory',
                                             '--no-empty-directory', ':/'):
        commit += '-dirty'
    return commit


def firmware_version(number, tags, commit):
    """number at its own release tag from a clean tree, else number+dev, as firmware/version.cmake names a
    build (#132). From a clean tree, a release tag at HEAD other than vNUMBER is a BuildError, as it stops the
    firmware's build; an edited tree is never a release, so no tag disagrees with it."""
    if commit == 'unknown' or commit.endswith('-dirty'):
        return number + '+dev'
    for tag in tags:
        if tag != 'v' + number:
            raise BuildError(f'HEAD is tagged {tag}, but project() in firmware/CMakeLists.txt says {number}: '
                             "a release's tag and its number must agree (docs/versions.md)")
    return number if tags else number + '+dev'


def long_date(iso):
    """'2026-10-14' as 'October 14, 2026', in English whatever the locale."""
    day = datetime.date.fromisoformat(iso)
    return f'{MONTHS[day.month - 1]} {day.day}, {day.year}'


def facts(root):
    if git(root, 'rev-parse', '--show-prefix'):
        # As firmware/version.cmake reads only the repository whose firmware/ it is (#132).
        raise BuildError(f'{root} sits inside another git repository, not a checkout of its own: the manual is '
                         "named for its commit, and would take that repository's")
    commit = firmware_commit(root)
    return Facts(version=firmware_version(project_version(root), release_tags(root), commit),
                 commit=commit,
                 date=long_date(git(root, 'log', '-1', '--format=%cs')),
                 timestamp=int(git(root, 'log', '-1', '--format=%ct')))


def read_edition(root):
    with open(os.path.join(root, EDITION_FILE), 'rb') as stream:
        try:
            data = tomllib.load(stream)
        except tomllib.TOMLDecodeError as error:
            raise BuildError(f'{EDITION_FILE} is not TOML: {error}') from None
    edition = Edition(str(data.get('number', '')), str(data.get('name', '')), str(data.get('firmware', '')))
    if edition.number and not re.fullmatch(r'\d\d', edition.number):
        raise BuildError(f'{EDITION_FILE}: number must be two digits, such as "00", or empty')
    if edition.number and not (edition.name and edition.firmware):
        raise BuildError(f'{EDITION_FILE}: an edition needs its name and firmware too')
    return edition


def stale_paths(root):
    """Files under docs/manual/ changed since the commit that last changed edition.toml."""
    declared = git(root, 'log', '-1', '--format=%H', '--', EDITION_FILE)
    changed = git(root, 'diff', '--name-only', declared, 'HEAD', '--', MANUAL_DIR)
    return [path for path in changed.splitlines() if path != EDITION_FILE]


def decide(root, release, notes):
    """The build's Stamp. notes gets anything the person building should hear. edition.toml is read and checked
    for every build, so a draft can't hide a broken one until the release."""
    edition = read_edition(root)
    if not release:
        return DRAFT_STAMP
    if git(root, 'status', '--porcelain'):
        raise BuildError('a release build needs a clean tree: commit or set aside what git status lists')
    number = project_version(root)
    if 'v' + number not in release_tags(root):
        raise BuildError(f"a release build needs HEAD at the annotated release tag v{number}, project()'s number")
    if not edition.number:
        notes.append(f'no edition is declared in {EDITION_FILE}: the release gets a draft')
        return DRAFT_STAMP
    stale = stale_paths(root)
    if stale:
        raise BuildError(f'the manual changed since edition {edition.number} was declared: declare a new '
                         f"edition in {EDITION_FILE} ({', '.join(stale)})")
    return Stamp(False, edition.number, edition.name, edition.firmware)
