# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Typst, as the manual's build runs it (#136): the pinned version, the repo's fonts and no others, and
any warning taken as a failure, since Typst only warns when a font is missing."""

import json
import re
import shutil
import subprocess

import manual_paths
from edition import BuildError

VERSION = '0.15.1'
HOW = f'brew install typst, then brew pin typst so Homebrew keeps it at {VERSION}'


def found_version(exe='typst'):
    """The version exe reports, or None if there's no such program."""
    if not shutil.which(exe):
        return None
    result = subprocess.run([exe, '--version'], capture_output=True, text=True)
    if result.returncode:
        raise BuildError(f'typst --version failed (exit {result.returncode}): {result.stderr.strip()}')
    out = result.stdout
    match = re.match(r'typst (\S+)', out)
    return match.group(1) if match else out.strip()


def check_version(exe='typst'):
    found = found_version(exe)
    if found is None:
        raise BuildError(f'Typst {VERSION} is needed and none is installed: {HOW}')
    if found != VERSION:
        raise BuildError(f'Typst {VERSION} is needed, found {found}: {HOW}')


def _common(inputs):
    args = ['--root', manual_paths.ROOT, '--ignore-system-fonts', '--ignore-embedded-fonts']
    for path in manual_paths.FONT_PATHS:
        args += ['--font-path', path]
    for (name, value) in inputs.items():
        args += ['--input', f'{name}={value}']
    return args


def _run(args, exe):
    result = subprocess.run([exe, *args], capture_output=True, text=True)
    if result.returncode:
        raise BuildError(f'Typst failed:\n{result.stderr.strip()}')
    # "path:line:col: warning: ...", or a bare "warning: ..." for one with no place in the source.
    warnings = [line for line in result.stderr.splitlines() if re.match(r'(.*: )?warning:', line)]
    if warnings:
        raise BuildError('Typst warned, which the build takes as a failure:\n' + '\n'.join(warnings))
    return result.stdout


def compile_pdf(source, out, inputs, timestamp, exe='typst'):
    _run(['compile', *_common(inputs), '--creation-timestamp', str(timestamp), '--diagnostic-format', 'short',
          source, out], exe)


def eval_json(source, inputs, expression, exe='typst'):
    """expression's value, evaluated in the laid-out document: `typst eval EXPRESSION --in SOURCE`."""
    return json.loads(_run(['eval', expression, '--in', source, *_common(inputs), '--diagnostic-format', 'short'],
                           exe))


def placed(source, inputs, exe='typst'):
    """Every <placed> marker's value, in order: what was placed, and the page it landed on."""
    return eval_json(source, inputs, 'query(<placed>).map(it => it.value)', exe)
