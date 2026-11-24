# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""OpenSCAD for make_case.py and the tests: building a body that may use the case's modules, measuring what two
bodies share, and the assembled board's own 3D model to measure against (#134)."""

import os
import struct
import subprocess
import tempfile

import paths

# The case's files whose modules a body may use: base(), lid(), inlay(), light_pipes_in_place(), plug_keepouts(),
# back_labels(), top_text()
MODULES = ('base', 'lid', 'cutters', 'labels')
EMPTY = 'Current top level object is empty.'
UNKNOWN = 'WARNING: Ignoring unknown'       # a module, function or variable: OpenSCAD leaves it out and carries on
# OpenSCAD 2026.10.11 on macOS sometimes dies of SIGSEGV as it starts, before it reads any input: Qt's sandbox check
# formats a time on one thread while OpenSCAD's localization_init() is in setlocale() on the main one (Oct 14, 2026,
# about one run in forty). A run a signal killed is run again, up to ATTEMPTS in all.
ATTEMPTS = 3
_home = []


def home():
    """OpenSCAD's scratch HOME, one per process, so its font cache is built once; removed when the process ends."""
    if not _home:
        _home.append(tempfile.TemporaryDirectory())
    return _home[0].name


def run(args):
    """OpenSCAD with args, its output captured as text; run again if a signal killed it. It runs with a scratch HOME,
    so the user's own fonts and settings stay out: a 3270font in ~/Library/Fonts has the repo's subset's family name,
    and OpenSCAD would draw the labels in it instead. (One installed for every user, in /Library/Fonts, still would.)"""
    for _ in range(ATTEMPTS):
        r = subprocess.run([paths.OPENSCAD] + args, capture_output=True, text=True, env={**os.environ, 'HOME': home()})
        if r.returncode >= 0:
            break
    return r


def version():
    """The installed OpenSCAD's version, such as '2026.10.11', or None without one."""
    try:
        r = run(['--version'])
    except OSError:
        return None
    words = (r.stdout + r.stderr).split()
    return words[-1] if r.returncode == 0 and words else None


def build(body, out, hard=True):
    """Exports body, after a `use` of each case file there is, to the binary STL out; with hard, a warning fails it."""
    source = os.path.splitext(out)[0] + '.scad'
    with open(source, 'w', encoding='utf-8') as stream:
        for name in MODULES:
            path = os.path.join(paths.CASE, name + '.scad')
            if os.path.exists(path):
                stream.write(f'use <{path}>\n')
        stream.write(body + '\n')
    return run((['--hardwarnings'] if hard else []) + ['-o', out, '--export-format', 'binstl', source])


def triangles(stl):
    """A binary STL's triangles, each three (x, y, z) vertices."""
    with open(stl, 'rb') as stream:
        data = stream.read()
    (count,) = struct.unpack_from('<I', data, 80)
    return [tuple(struct.unpack_from('<3f', data, 84 + 50 * i + 12 + 12 * j) for j in range(3))
            for i in range(count)]


def volume(stl):
    """A closed binary STL's volume in mm^3: the sum of the tetrahedra its triangles make with the origin."""
    total = 0.0
    for (a, b, c) in triangles(stl):
        total += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0])
                  + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6
    return abs(total)


def bounds(stl):
    """A binary STL's ((least x, y, z), (most x, y, z))."""
    points = [p for t in triangles(stl) for p in t]
    return (tuple(min(p[i] for p in points) for i in range(3)), tuple(max(p[i] for p in points) for i in range(3)))


def overlap(a, b):
    """The volume in mm^3 that bodies a and b share. Bodies that only touch share next to none. A body OpenSCAD
    doesn't know is an error: left out, it would leave the intersection the other body whole."""
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, 'overlap.stl')
        r = build(f'intersection() {{ {a}; {b}; }}', out, hard=False)
        if UNKNOWN in r.stderr:
            raise RuntimeError(r.stderr)
        if r.returncode == 1 and EMPTY in r.stderr:
            return 0.0
        if r.returncode != 0:
            raise RuntimeError(r.stderr)
        return volume(out)


def board_stl(directory):
    """The assembled board, do-not-fit parts included, as an STL in directory, in the case's frame."""
    out = os.path.join(directory, 'board.stl')
    subprocess.run([paths.KICAD_CLI, 'pcb', 'export', 'stl', '--drill-origin', '--subst-models', '-f', '-o', out,
                    paths.BOARD_PCB], check=True, capture_output=True)
    return out
