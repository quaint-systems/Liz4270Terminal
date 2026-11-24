#!/usr/bin/env python
# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Check a firmware build's notices against SetUp's About pages (#126).

  python tools/sim/about_audit.py firmware/build/liz4270

What's linked comes from the build's link map, liz4270.elf.map: the object files it loads, and the archive
members it pulls in, each only if the image keeps some of it (#129). An object is kept if its memory map places an
input section of it, at a non-zero size, in an output section the image loads; one at address 0 holds debug
information, .comment or .ARM.attributes. --gc-sections drops the rest whole, and the audit counts them. The
files each kept object was built from, sources and headers, come from `ninja -t deps`. Each such
file under firmware/, but the build tree, names its licenses (SPDX identifiers, or the words of ISC, MIT or a BSD
license) and its copyright lines (those that start with "Copyright" once comment marks are stripped, or
NOTICE_LINES' for a file that words its notice otherwise). A file without one or the other takes its project's
license file's, and every project with a file linked brings its license file's lines too. A PIO header the build
generates, NAME.pio.h, stands for the .pio ninja builds it from, and GENERATED's files for the sources another
target compiles; BUILD_FILES, pico-sdk's configuration headers and the build's version header, hold nothing under a
notice. Any other file in the build tree, and any linked object ninja has no record of, is a problem: the audit
can't say what it holds. A line that reads like a notice but doesn't start "Copyright" ("(C) 2024 X", "Portions
Copyright", a (c) sign) is a problem too, unless NOTICE_LINES words its file's notice.

Each copyright line must be in a bake_about group for one of its file's licenses; every kept member of a
toolchain archive but libgcc's must be in a group's objects, and every object a group lists must be kept; the
toolchain's newlib must be the release those groups were read from (bake_about.NEWLIB_VERSION); every newlib
header the kept objects include that carries a notice must be in NEWLIB_HEADERS (its inline code under a
group's notice) or NEWLIB_DECLARATIONS (no code under its notice), and every header in NEWLIB_HEADERS must be
included; and every line a group without objects lists must turn up in what's kept. GCC's own headers and
libstdc++'s carry the GCC Runtime Library Exception, so the audit doesn't read them. Prints each problem and
exits 1, or the counts and ok.
"""

import argparse
import os
import re
import subprocess
import sys

import bake_about
from paths import ROOT

MAP_NAME = 'liz4270.elf.map'
# A project under firmware/, longest prefix first, and its license file, from the checkout's root.
PROJECTS = (
    ('pico-sdk/lib/tinyusb/', 'firmware/pico-sdk/lib/tinyusb/LICENSE'),
    ('pico-sdk/', 'firmware/pico-sdk/LICENSE.TXT'),
    ('Pico-PIO-USB/', 'firmware/Pico-PIO-USB/LICENSE'),
    ('vendor/coax-tcp/', 'firmware/vendor/coax-tcp/LICENSE'),
    ('vendor/', None),  # a vendored project of no entry above: its notice can't be the repository's own
    ('', 'LICENSE'),
)
# A file that words its notice other than as a line starting "Copyright", by its path under firmware/.
NOTICE_LINES = {
    'pico-sdk/src/rp2_common/pico_printf/printf.c':
        ('(c) Marco Paland (info@paland.com) 2014-2019, PALANDesign Hannover, Germany',),
    'pico-sdk/src/rp2_common/pico_printf/include/pico/printf.h':
        ('(c) Marco Paland (info@paland.com) 2014-2019, PALANDesign Hannover, Germany',),
}
# Files the build generates that hold nothing under a notice, by path from the build directory.
BUILD_FILES = ('generated/pico_base/pico/version.h', 'generated/pico_base/pico/config_autogen.h',
               'generated/liz_version.h')  # the build's version and commit, from firmware/version.cmake (#132)
# A file the build generates from sources another target compiles, by path from the build directory: that
# target's sources stand for it. Boot stage 2 is assembled, then padded and checksummed into a source of its own.
GENERATED = {
    'pico-sdk/src/rp2350/boot_stage2/bs2_default_padded.S':
        'pico-sdk/src/rp2350/boot_stage2/CMakeFiles/bs2_default.dir/compile_time_choice.S.o',
}
# newlib 4.6.0's headers that the linked objects include and that carry a notice (NOTICE), by path from newlib's
# include directory: those whose inline code compiles into the firmware, with the bake_about group of their
# notice, and those whose notice covers declarations, types and macros only.
NEWLIB_HEADERS = {
    'stdio.h': 'LicenseRef-newlib-UCB',
    'sys/time.h': 'LicenseRef-newlib-UCB-BSD',
}
NEWLIB_DECLARATIONS = (
    'inttypes.h', 'machine/_endian.h', 'stdint.h', 'strings.h', 'sys/_intsup.h', 'sys/_pthreadtypes.h',
    'sys/_sigset.h', 'sys/_stdint.h', 'sys/_timespec.h', 'sys/_timeval.h', 'sys/cdefs.h', 'sys/features.h',
    'sys/reent.h', 'sys/sched.h', 'sys/timespec.h',
)
NEWLIB_VERSION = re.compile(r'#define\s+_NEWLIB_VERSION\s+"([^"]+)"')
EXEMPT_ARCHIVES = ('libgcc.a',)  # the GCC Runtime Library Exception asks no notice of a binary
SPDX = re.compile(r'SPDX-License-Identifier:\s*([A-Za-z0-9.+-]+)')
LEADER = re.compile(r'^[\s/*#;!]+')
CLOSER = re.compile(r'\s*\*/\s*$')
LOAD = re.compile(r'^LOAD (\S+\.o)$', re.MULTILINE)
MEMBER = re.compile(r'^(\S+\.a)\(([^)]+)\)', re.MULTILINE)
# The memory map, after this line: an output section at column 0, its address and size on its line or the next;
# each input section in it a column in, its address, size and object on its line or the next.
MEMORY_MAP = 'Linker script and memory map'
OUTPUT = re.compile(r'^\.\S+(?:\s+0x([0-9a-f]+)\s+0x[0-9a-f]+)?')
INPUT = re.compile(r'^ [^\s*]\S*(?:\s+0x[0-9a-f]+\s+0x([0-9a-f]+)\s+(\S.*?))?\s*$')
WRAPPED = re.compile(r'^\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)(?:\s+(\S.*?))?\s*$')
# A line that reads like a notice: the word, or a (c) or copyright sign before a name or year; and the license
# wording that names copyright without being a notice.
NOTICE_WORDS = re.compile(r'(?i:\bcopyright\b)|\([cC]\)\s*(\d|[A-Z][a-z])|\u00a9')
BOILERPLATE = re.compile(r'copyright\s+(notice|holder|owner)|(above|all)\s+copyright\b|the\s+copyright\W*$',
                         re.IGNORECASE)


def kept(map_text):
    """The objects the image keeps some of, as the memory map names them (a path from the build directory, or
    ARCHIVE(MEMBER)): those with an input section of non-zero size in an output section at a non-zero address. An
    output section with its address on no line holds nothing, and a line at column 0 that isn't one ends it."""
    out = set()
    loaded = False   # whether the output section the lines are in is one the image loads
    pending = None   # 'output' or 'input' while a section's name stands alone, its address on the next line
    for line in map_text.partition(MEMORY_MAP)[2].splitlines():
        wrapped = WRAPPED.match(line) if pending else None
        (was, pending) = (pending, None)
        if wrapped:
            if was == 'output':
                loaded = int(wrapped.group(1), 16) != 0
            elif loaded and int(wrapped.group(2), 16) and wrapped.group(3):
                out.add(wrapped.group(3))
            continue
        if line[:1] not in ('', ' '):
            output = OUTPUT.match(line)
            loaded = bool(output and output.group(1) and int(output.group(1), 16))
            pending = 'output' if output and output.group(1) is None else None
            continue
        section = INPUT.match(line)
        if section and section.group(1) is None:
            pending = 'input'
        elif section and loaded and int(section.group(1), 16):
            out.add(section.group(2))
    return {path if path.endswith(')') else os.path.normpath(path) for path in out}


def linked(map_text):
    """(objects, members, dropped) from a link map: the object files it loads, by path from the build directory,
    and {archive: {member}} for the archive members it pulls in, from the lines that start with one, each only if
    the image keeps some of it; and dropped, (objects, members) as they were for those it drops whole."""
    keeps = kept(map_text)
    (members, dropped_members) = ({}, {})
    for (archive, member) in MEMBER.findall(map_text):
        into = members if f'{archive}({member})' in keeps else dropped_members
        into.setdefault(archive, set()).add(member)
    loads = {os.path.normpath(path) for path in LOAD.findall(map_text)}
    return (loads & keeps, members, (loads - keeps, dropped_members))


def deps(ninja_text):
    """{target: [path]} from `ninja -t deps`: a target's line, then its dependencies indented under it."""
    out = {}
    target = None
    for line in ninja_text.splitlines():
        if not line.strip():
            continue
        if line[0].isspace():
            out[target].append(line.strip())
        else:
            target = os.path.normpath(line.split(': #deps', 1)[0])
            out[target] = []
    return out


def licenses_in(text):
    """The licenses a file's text names: its SPDX identifiers, or the words of ISC, MIT or a BSD license."""
    found = set(SPDX.findall(text))
    if 'Permission is hereby granted, free of charge' in text:
        found.add('MIT')
    if 'Permission to use, copy, modify, and/or distribute' in text:
        found.add('ISC')
    if 'Redistribution and use in source and binary forms' in text:
        found.add('BSD-3-Clause' if 'Neither the name' in text else 'BSD-2-Clause')
    return found


def copyright_lines(text):
    """The lines that start with "Copyright" once comment marks are stripped, in order, each once."""
    out = []
    for raw in text.splitlines():
        line = CLOSER.sub('', LEADER.sub('', raw)).rstrip()
        if line.startswith('Copyright') and line not in out:
            out.append(line)
    return out


def unread_notices(text):
    """The lines that read like a notice but don't start with "Copyright" once comment marks are stripped, so
    copyright_lines doesn't take them: neither license wording nor a line with a string literal in it."""
    out = []
    for raw in text.splitlines():
        line = CLOSER.sub('', LEADER.sub('', raw)).rstrip()
        if (NOTICE_WORDS.search(line) and not line.startswith('Copyright') and not BOILERPLATE.search(line)
                and '"' not in line and line not in out):
            out.append(line)
    return out


def under(path, directory):
    return os.path.commonpath([path, directory]) == directory


def read(path):
    with open(path, encoding='utf-8', errors='replace') as stream:
        return stream.read()


def project(rel):
    """The license file, from the checkout's root, of the project a path under firmware/ belongs to, or None for a
    vendored project PROJECTS doesn't know."""
    return next(license_file for (prefix, license_file) in PROJECTS if rel.startswith(prefix))


def pio_source(query_text, build):
    """The .pio file a generated NAME.pio.h is built from, by `ninja -t query NAME.pio.h`'s inputs, or None if
    they name no .pio or more than one."""
    found = []
    reading = False
    for line in query_text.splitlines():
        if line.startswith('  ') and not line.startswith('    '):
            reading = line.strip().startswith('input:')
        elif reading:
            path = line.strip().lstrip('|').strip()
            if path.endswith('.pio'):
                found.append(os.path.normpath(os.path.join(build, path)))
    return found[0] if len(found) == 1 else None


def linked_files(map_text, deps_text, build, firmware, problems, query):
    """The files under firmware/ the kept objects were built from, how many objects, the kept archive members,
    the files outside firmware/ and the build tree they include (the toolchain's headers), and what linked()
    names dropped. A kept object ninja has no record of, or a file in the build tree the audit can't name the
    sources of, goes into problems, and so does a map whose memory map keeps none of what it loads. query gives
    `ninja -t query`'s text for a path from the build directory."""
    (objects, members, dropped) = linked(map_text)
    if not objects and dropped[0]:
        problems.append(f'{MAP_NAME}: its memory map keeps none of the objects it loads, so the audit misreads it')
    dep_map = deps(deps_text)
    targets = set()
    for obj in sorted(objects):
        if obj in dep_map:
            targets.add(obj)
        else:
            problems.append(f'{obj}: linked, but ninja has no record of its sources')
    for (archive, names) in sorted(members.items()):
        if os.path.isabs(archive):
            continue  # the toolchain's
        prefix = os.path.join(os.path.dirname(archive), '')  # '' for an archive at the build directory's top
        for name in sorted(names):
            found = {target for target in dep_map if target.startswith(prefix) and os.path.basename(target) == name}
            if not found:
                problems.append(f'{archive}({name}): linked, but ninja has no record of its sources')
            targets |= found
    files = set()
    outside = set()
    sources = {}  # each generated NAME.pio.h's .pio, as ninja names it
    followed = set(targets)
    pending = [path for target in sorted(targets) for path in dep_map[target]]
    while pending:
        path = pending.pop()
        path = os.path.normpath(path if os.path.isabs(path) else os.path.join(build, path))
        if under(path, build):
            rel = os.path.relpath(path, build)
            if rel in BUILD_FILES:
                continue
            if rel in GENERATED:
                target = GENERATED[rel]
                if target not in dep_map:
                    problems.append(f'{rel}: generated from {target}, which ninja has no record of')
                elif target not in followed:
                    followed.add(target)
                    pending += dep_map[target]
                continue
            if not rel.endswith('.pio.h'):
                problems.append(f"{rel}: generated in the build tree, from sources the audit can't name")
                continue
            if rel not in sources:
                sources[rel] = pio_source(query(rel), build)
                if sources[rel] is None:
                    problems.append(f'{rel}: ninja names no one .pio it is built from')
            if sources[rel] is None:
                continue
            path = sources[rel]
        if under(path, firmware):
            files.add(path)
        else:
            outside.add(path)
    return (files, len(targets), members, outside, dropped)


def newlib_include(members):
    """(archive, include) for the toolchain's newlib: one of its archives the map names, and the include
    directory over the lib directory it's in, where newlib's headers are; or None if no toolchain archive is
    linked."""
    archives = sorted(os.path.normpath(archive) for archive in members
                      if os.path.isabs(archive) and os.path.basename(archive) not in EXEMPT_ARCHIVES)
    if not archives:
        return None
    archive = archives[0]
    return (archive, os.path.join(archive[:archive.rfind(os.sep + 'lib' + os.sep)], 'include'))


def newlib_problems(members):
    """Whether the toolchain's newlib is the release bake_about's groups were read from: its version header sits
    beside the libraries, in newlib's include directory."""
    newlib = newlib_include(members)
    if newlib is None:
        return []
    (archive, include) = newlib
    header = os.path.join(include, '_newlib_version.h')
    if not os.path.exists(header):
        return [f"{header}: not found beside {archive}, so newlib's version is unknown"]
    found = NEWLIB_VERSION.search(read(header))
    version = found.group(1) if found else 'of no version'
    if version != bake_about.NEWLIB_VERSION:
        return [f'newlib {version} is linked, but its notices were audited at {bake_about.NEWLIB_VERSION}']
    return []


def newlib_header_problems(headers, members, groups, inline=NEWLIB_HEADERS):
    """Each of newlib's headers among headers (the files outside firmware/ the kept objects include) that
    carries a notice, but isn't in inline (NEWLIB_HEADERS) under one of groups or in NEWLIB_DECLARATIONS, and each
    of inline's that none of them is. libstdc++'s headers, in newlib's include directory's c++/, carry GCC's
    exception."""
    newlib = newlib_include(members)
    if newlib is None:
        return []
    (_, include) = newlib
    spdx = {group.spdx for group in groups}
    problems = []
    for path in sorted(headers):
        if not under(path, include) or under(path, os.path.join(include, 'c++')):
            continue
        rel = os.path.relpath(path, include)
        if inline.get(rel) in spdx or rel in NEWLIB_DECLARATIONS:
            continue
        text = read(path)
        if copyright_lines(text) or unread_notices(text):
            problems.append(f'newlib {rel}: carries a notice, but is in neither NEWLIB_HEADERS nor '
                            f'NEWLIB_DECLARATIONS')
    for rel in sorted(inline):
        if os.path.join(include, rel) not in headers:
            problems.append(f'newlib {rel}: in NEWLIB_HEADERS, but no kept object includes it')
    return problems


def audit(map_text, deps_text, build, root=ROOT, groups=bake_about.GROUPS, query=None, inline=NEWLIB_HEADERS):
    """(problems, counts) for a build: see the module's docstring. build is the build directory, root the
    checkout's. query gives `ninja -t query`'s text for a path from the build directory, and inline stands in
    for NEWLIB_HEADERS."""
    firmware = os.path.join(root, 'firmware')
    problems = []
    (files, objects, members, outside, dropped) = linked_files(map_text, deps_text, build, firmware, problems,
                                                               query)
    listed = {}
    for group in groups:
        listed.setdefault(group.spdx, set()).update(group.copyrights)
    found = set()

    def check(where, licenses, lines):
        for line in lines:
            matched = {spdx for spdx in licenses if line in listed.get(spdx, ())}
            found.update((spdx, line) for spdx in matched)
            if not matched:
                named = ', '.join(sorted(licenses)) or 'no license'
                problems.append(f'{where}: {line!r} ({named}) is on no page')

    projects = set()
    for path in sorted(files):
        rel = os.path.relpath(path, firmware)
        if project(rel) is None:
            problems.append(f'{rel}: in vendor/, in no project the audit knows')
            continue
        text = read(path)
        if rel not in NOTICE_LINES:
            problems += [f"{rel}: {line!r} reads like a notice, but doesn't start \"Copyright\": word its "
                         f'notice in NOTICE_LINES' for line in unread_notices(text)]
        (licenses, lines) = (licenses_in(text), list(NOTICE_LINES.get(rel, ())) or copyright_lines(text))
        projects.add(project(rel))
        if not licenses or not lines:
            text = read(os.path.join(root, project(rel)))
            (licenses, lines) = (licenses or licenses_in(text), lines or copyright_lines(text))
        check(rel, licenses, lines)
    for license_file in sorted(projects):
        text = read(os.path.join(root, license_file))
        check(license_file, licenses_in(text), copyright_lines(text))
    problems += newlib_problems(members)
    problems += newlib_header_problems(outside, members, groups, inline)
    covered = {member for group in groups for member in group.objects}

    def toolchain(members_):
        return {name for (archive, names) in members_.items() for name in names
                if os.path.isabs(archive) and os.path.basename(archive) not in EXEMPT_ARCHIVES}

    archived = toolchain(members)
    for (archive, names) in sorted(members.items()):
        if os.path.isabs(archive) and os.path.basename(archive) not in EXEMPT_ARCHIVES:
            problems += [f'{os.path.basename(archive)}({name}) is in no group' for name in sorted(names - covered)]
    for group in groups:
        problems += [f'{group.spdx}: {name} is listed, but the image keeps none of it'
                     for name in group.objects if name not in archived]
        if not group.objects:
            for line in group.copyrights:
                if (group.spdx, line) not in found:
                    problems.append(f'{group.spdx}: {line!r} is listed, but nothing kept holds it')
    (dropped_loads, dropped_members) = dropped
    dropped_objects = len(dropped_loads) + sum(len(names) for (archive, names) in dropped_members.items()
                                               if not os.path.isabs(archive))
    return (problems, {'objects': objects, 'files': len(files), 'archive members': len(archived),
                       'objects dropped': dropped_objects,
                       'archive members dropped': len(toolchain(dropped_members))})


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('build', help='the build directory, such as firmware/build/liz4270')
    args = parser.parse_args()
    build = os.path.abspath(args.build)
    map_text = read(os.path.join(build, MAP_NAME))
    deps_text = subprocess.run(['ninja', '-C', build, '-t', 'deps'], capture_output=True, text=True,
                               check=True).stdout

    def query(path):
        return subprocess.run(['ninja', '-C', build, '-t', 'query', path], capture_output=True, text=True,
                              check=True).stdout

    (problems, counts) = audit(map_text, deps_text, build, query=query)
    for problem in problems:
        print(problem)
    print(', '.join(f'{n} {name}' for (name, n) in counts.items()))
    print(f'{len(problems)} missing' if problems else 'ok')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
