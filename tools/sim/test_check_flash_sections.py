# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""firmware/check_flash_sections.cmake (#69) against objdump tables: the post-build check passes the
firmware's own table and fails anything else left in flash, or a table it can't read."""

import os
import re
import shutil
import subprocess
import tempfile
import unittest

from paths import ROOT

SCRIPT = os.path.join(ROOT, 'firmware', 'check_flash_sections.cmake')

# A Fruit Jam build's section table on Oct 6, 2026 (arm-none-eabi-objdump -h), cut after .data, plus one
# debug section.
GOOD = """
build/fruit-jam/liz4270.elf:     file format elf32-littlearm

Sections:
Idx Name          Size      VMA       LMA       File off  Algn
  0 .flashtext    000001ec  10000000  10000000  00001000  2**2
                  CONTENTS, ALLOC, LOAD, READONLY, CODE
  1 .rodata       00000000  100001ec  100001ec  0001de50  2**0
                  CONTENTS, ALLOC, LOAD, DATA
  2 .ARM.exidx    00000008  100001ec  100001ec  000011ec  2**2
                  CONTENTS, ALLOC, LOAD, READONLY, DATA
  3 .binary_info  0000003c  100001f4  100001f4  000011f4  2**2
                  CONTENTS, ALLOC, LOAD, READONLY, DATA
  4 .ram_vector_table 00000110  20000000  20000000  0001e000  2**2
                  ALLOC
  6 .text         000102cc  20000110  10000230  00002110  2**3
                  CONTENTS, ALLOC, LOAD, READONLY, CODE
  7 .psram_load   00000000  11000000  11000000  0001de50  2**0
                  CONTENTS
  9 .xip_ram      00000000  13ffc000  13ffc000  0001de50  2**0
                  CONTENTS
 10 .data         0000b940  200103e0  100104fc  000123e0  2**3
                  CONTENTS, ALLOC, LOAD, CODE
 25 .flash_end    00000014  1001be3c  1001be3c  0001de3c  2**2
                  CONTENTS, ALLOC, LOAD, READONLY, DATA
 26 .debug_info   0006fc29  00000000  00000000  0001de50  2**0
                  CONTENTS, READONLY, DEBUGGING, OCTETS
"""


def changed(old, new):
    """GOOD with old replaced by new; old must be there, so a test can't pass on a replace that missed."""
    assert old in GOOD, old
    return GOOD.replace(old, new)


def check(table):
    """The script run with a stand-in objdump that prints table: (passed, what it printed)."""
    with tempfile.TemporaryDirectory() as tmp:
        objdump = os.path.join(tmp, 'objdump')
        elf = os.path.join(tmp, 'liz4270.elf')
        with open(elf, 'w') as f:
            f.write(table)
        with open(objdump, 'w') as f:
            f.write('#!/bin/sh\ncat "$2"\n')  # called as: objdump -h ELF
        os.chmod(objdump, 0o755)
        run = subprocess.run(['cmake', f'-DOBJDUMP={objdump}', f'-DELF={elf}', '-P', SCRIPT],
                             capture_output=True, text=True)
        return (run.returncode == 0, run.stdout + run.stderr)


@unittest.skipUnless(shutil.which('cmake'), 'needs cmake')
class TestCheckFlashSections(unittest.TestCase):
    def test_the_firmwares_own_table_passes(self):
        (passed, output) = check(GOOD)
        self.assertTrue(passed, output)

    def test_constants_left_in_flash_fail(self):
        (passed, output) = check(changed('.rodata       00000000', '.rodata       00000004'))
        self.assertFalse(passed)
        self.assertIn('.rodata', output)

    def test_code_in_flash_fails(self):
        (passed, output) = check(changed('.text         000102cc  20000110', '.text         000102cc  10000230'))
        self.assertFalse(passed)
        self.assertIn('.text', output)

    def test_the_xip_caches_sram_with_contents_fails(self):
        (passed, output) = check(changed('.xip_ram      00000000', '.xip_ram      00000010'))
        self.assertFalse(passed)
        self.assertIn('.xip_ram', output)

    def test_a_table_with_no_flashtext_fails(self):
        for table in ('', 'objdump: liz4270.elf: file format not recognized\n',
                      changed('.flashtext', '.boot_text')):
            (passed, output) = check(table)
            self.assertFalse(passed, table[:40])

    def test_a_table_whose_addresses_it_cant_read_fails(self):
        # As a 64-bit objdump would print it: 16-digit addresses, with 0x400 bytes of .rodata in flash.
        wide = re.sub(r'^( *\d+ \S+ +[0-9a-f]+  )([0-9a-f]{8})  ([0-9a-f]{8})',
                      lambda m: f'{m[1]}00000000{m[2]}  00000000{m[3]}',
                      changed('.rodata       00000000', '.rodata       00000400'), flags=re.M)
        self.assertIn('0000000010000000', wide)
        (passed, output) = check(wide)
        self.assertFalse(passed, output)



class TestWhereItRuns(unittest.TestCase):
    def test_before_the_uf2_is_written(self):
        # POST_BUILD commands run in the order they're added, and pico_add_extra_outputs adds the one
        # that writes the UF2: a check after it would leave a failing image there, ready to load.
        with open(os.path.join(ROOT, 'firmware', 'CMakeLists.txt')) as f:
            text = f.read()
        self.assertLess(text.index('check_flash_sections.cmake'), text.index('pico_add_extra_outputs(liz4270)'))


if __name__ == '__main__':
    unittest.main()
