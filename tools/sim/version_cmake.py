# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""firmware/version.cmake, run as the firmware's build runs it (#132), for the tests here and in tools/manual."""

import os
import re
import shutil
import subprocess
import tempfile

from paths import ROOT

SCRIPT = os.path.join(ROOT, 'firmware', 'version.cmake')
DEFINE = re.compile(r'^#define LIZ_(VERSION|COMMIT) "(.*)"$', re.MULTILINE)


class VersionError(Exception):
    """version.cmake stopped the build; the message is what it printed."""


def available():
    """Whether cmake and git are on the path, as the tests that run the script need."""
    return shutil.which('cmake') is not None and shutil.which('git') is not None


def run(source_dir, number, env=None, output=None, git='git'):
    """(version, commit) as version.cmake writes them for the tree at source_dir, project()'s number being
    number. output is the header it writes (a scratch file unless given); git is the program it runs, or ''
    for none, as a build without git has."""
    with tempfile.TemporaryDirectory() as scratch:
        path = output or os.path.join(scratch, 'generated', 'liz_version.h')
        program = (shutil.which(git) or git) if git else ''
        result = subprocess.run(['cmake', f'-DNUMBER={number}', f'-DGIT={program}', f'-DSOURCE_DIR={source_dir}',
                                 f'-DOUTPUT={path}', '-P', SCRIPT],
                                env=env, capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise VersionError(result.stderr.strip())
        with open(path, encoding='utf-8') as stream:
            found = dict(DEFINE.findall(stream.read()))
    return (found['VERSION'], found['COMMIT'])
