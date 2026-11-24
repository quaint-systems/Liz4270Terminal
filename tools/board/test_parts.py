# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Every part kind: its footprint exists and has a pad for each of its symbol's pins (a footprint whose pads
don't match would leave a pin unconnected with every netlist test green), and every bought part has an LCSC number."""

import os
import unittest

import parts
import paths
import sexp
import symlib


def footprint_path(footprint):
    lib, name = footprint.split(':', 1)
    base = paths.LIB if lib == 'liz4270' else paths.STOCK_FOOTPRINTS
    return os.path.join(base, f'{lib}.pretty', f'{name}.kicad_mod')


def pad_forms(footprint):
    with open(footprint_path(footprint), encoding='utf-8') as stream:
        return sexp.find_all(sexp.parse(stream.read()), 'pad')


def pads(footprint):
    return {str(p[1]) for p in pad_forms(footprint)} - {''}


# Exposed pads that must reach the ground plane through vias: the RP2350B's and the CH334F's are their only ground
# (RP2350 datasheet, Table 1679; WCH's CH334 datasheet, Table 1-3), and TI puts five vias under the DAC's (SLAS671C).
EXPOSED_GROUND = {'RP2350B': '81', 'CH334F': '25', 'TLV320DAC3100': '33'}


@unittest.skipUnless(os.path.isdir(paths.STOCK_FOOTPRINTS), 'needs KiCad')
class TestParts(unittest.TestCase):
    def test_every_footprint_has_a_pad_for_every_pin(self):
        for (name, spec) in parts.ALL.items():
            with self.subTest(part=name, footprint=spec.footprint):
                pins = {p.number for p in symlib.lookup(spec.lib_id).pins}
                self.assertTrue(os.path.exists(footprint_path(spec.footprint)))
                self.assertLessEqual(pins, pads(spec.footprint))

    def test_exposed_ground_pads_have_vias(self):
        for (name, pad) in EXPOSED_GROUND.items():
            with self.subTest(part=name):
                vias = [p for p in pad_forms(parts.ALL[name].footprint) if str(p[1]) == pad and p[2] == 'thru_hole']
                self.assertGreaterEqual(len(vias), 5)

    def test_every_bought_part_has_an_lcsc_number(self):
        for (name, spec) in parts.ALL.items():
            if spec.bom:
                with self.subTest(part=name):
                    self.assertRegex(spec.lcsc, r'^C\d+$')
                    if spec.lib_id not in ('Device:R', 'Device:C'):
                        self.assertTrue(spec.mpn)

    def test_every_mpn_is_a_part_number(self):
        # the BOM's MPN column is what a buyer types into a distributor's search, so never a description
        for (name, spec) in parts.ALL.items():
            with self.subTest(part=name):
                self.assertNotRegex(spec.mpn, r'\s')


if __name__ == '__main__':
    unittest.main()
