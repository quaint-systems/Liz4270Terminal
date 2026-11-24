# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The board's own library: two symbols drawn from TI's pin tables, and what is copied from interface3 and Raspberry Pi."""

import os
import unittest

import make_library
import paths
import sexp
import symlib

DAC = {'1': 'IOVSS', '2': 'IOVDD', '3': 'DVDD', '4': 'NC', '5': 'DIN', '6': 'WCLK', '7': 'BCLK', '8': 'MCLK',
       '9': 'SDA', '10': 'SCL', '11': 'VOL/MICDET', '12': 'MICBIAS', '13': 'AIN1', '14': 'AIN2', '15': 'NC',
       '16': 'AVSS', '17': 'AVDD', '18': 'DVSS', '19': 'SPKM', '20': 'SPKVSS', '21': 'SPKVDD', '22': 'SPKP',
       '23': 'SPKM', '24': 'SPKVDD', '25': 'SPKVSS', '26': 'SPKP', '27': 'HPL', '28': 'HPVDD', '29': 'HPVSS',
       '30': 'HPR', '31': '~{RESET}', '32': 'GPIO1', '33': 'EP'}            # TI SLAS671C, "Pin Functions"
TPD = {'1': 'CTRL1', '2': 'CTRL2', '3': 'CTRL3', '4': 'CTRL4', '5': '5V_SUPPLY', '6': '5V_OUT', '7': 'CTRL5',
       '8': 'GND', '9': 'D3-', '10': 'D3+', '11': 'D2-', '12': 'D2+', '13': 'D1-', '14': 'D1+', '15': 'D0-',
       '16': 'D0+'}                                                         # TI SLVSBC5D, "Pin Functions", TSSOP


def footprint(name):
    with open(os.path.join(paths.LIB, 'liz4270.pretty', f'{name}.kicad_mod'), encoding='utf-8') as stream:
        return sexp.parse(stream.read())


def pads(name):
    return {str(p[1]) for p in sexp.find_all(footprint(name), 'pad')} - {''}


def courtyard(fp):
    """(xmin, ymin, xmax, ymax) of the front courtyard's lines."""
    xs, ys = [], []
    for line in sexp.find_all(fp, 'fp_line'):
        if str(sexp.find(line, 'layer')[1]) == 'F.CrtYd':
            for key in ('start', 'end'):
                point = sexp.find(line, key)
                xs.append(float(point[1]))
                ys.append(float(point[2]))
    return (min(xs), min(ys), max(xs), max(ys))


class TestLibrary(unittest.TestCase):
    def test_the_dac_follows_the_datasheet(self):
        s = symlib.lookup('liz4270:TLV320DAC3100')
        self.assertEqual({p.number: p.name for p in s.pins}, DAC)
        self.assertEqual(s.property('Footprint'), 'Package_DFN_QFN:QFN-32-1EP_5x5mm_P0.5mm_EP3.45x3.45mm_ThermalVias')

    def test_the_hdmi_protector_follows_the_datasheet(self):
        s = symlib.lookup('liz4270:TPD13S523')
        self.assertEqual({p.number: p.name for p in s.pins}, TPD)
        self.assertEqual({p.etype for p in s.pins if p.name == '5V_OUT'}, {'power_out'})

    def test_the_transformer_is_interface3s(self):
        s = symlib.lookup('liz4270:Murata_78602')
        self.assertEqual({p.number for p in s.pins}, {'1', '2', '3', '4', '5', '6'})
        self.assertEqual(s.property('Footprint'), 'liz4270:Murata_786J')

    def test_footprints(self):
        self.assertEqual(pads('Murata_786J'), {'1', '2', '3', '4', '5', '6'})
        self.assertEqual(pads('Abracon_AOTA-B201610S3R3-101-T'), {'1', '2'})

    def test_the_786j_courtyard_encloses_its_pads(self):
        fp = footprint('Murata_786J')
        (cx0, cy0, cx1, cy1) = courtyard(fp)
        for pad in sexp.find_all(fp, 'pad'):
            at, size = sexp.find(pad, 'at'), sexp.find(pad, 'size')
            (x, y, w, h) = (float(at[1]), float(at[2]), float(size[1]), float(size[2]))
            if len(at) > 3 and float(at[3]) % 180:
                (w, h) = (h, w)
            with self.subTest(pad=str(pad[1])):
                self.assertLessEqual(cx0, x - w / 2)
                self.assertLessEqual(cy0, y - h / 2)
                self.assertGreaterEqual(cx1, x + w / 2)
                self.assertGreaterEqual(cy1, y + h / 2)

    def test_the_786j_courtyard_holds_its_body(self):
        # Murata 786J datasheet (KMP_786JC_E01, p.3): 9.52 mm max across the lead rows, 9.0 along them
        (cx0, cy0, cx1, cy1) = courtyard(footprint('Murata_786J'))
        self.assertLessEqual((cx0, cy0), (-4.76, -4.5))
        self.assertGreaterEqual((cx1, cy1), (4.76, 4.5))
        self.assertLessEqual(cy0, -4.5 - 0.25)
        self.assertGreaterEqual(cy1, 4.5 + 0.25)

    def test_the_786j_marks_pin_1_outside_its_body(self):
        # Gate-2 review, finding 8: the body (+/-4.76 mm across the lead rows) hides the outline's corner tick
        fp = footprint('Murata_786J')
        dots = [sexp.find(c, 'center') for c in sexp.find_all(fp, 'fp_circle')
                if str(sexp.find(c, 'layer')[1]) == 'F.SilkS']
        self.assertTrue(any(float(d[1]) < -4.76 and float(d[2]) < -3.05 for d in dots))

    def test_the_pts645v_follows_the_datasheet(self):
        # C&K PTS645 Series, "Termination V, vertical", PCB layout (B-137, Apr 21): contacts 1 and 2 in 1.0 mm holes
        # 4.5 mm apart; the frame's legs in 1.3 mm holes 7 mm apart, centred on them and 2.55 mm behind, away from the
        # actuator. The legs are pad SH, so the frame can be grounded (gate 2).
        fp = footprint('SW_CK_PTS645V_Angled')
        holes = sorted((str(p[1]), float(sexp.find(p, 'at')[1]), float(sexp.find(p, 'at')[2]),
                        float(sexp.find(p, 'drill')[1])) for p in sexp.find_all(fp, 'pad'))
        self.assertEqual(holes, [('1', 0.0, 0.0, 1.0), ('2', 4.5, 0.0, 1.0),
                                 ('SH', -1.25, 2.55, 1.3), ('SH', 5.75, 2.55, 1.3)])
        (cx0, cy0, cx1, cy1) = courtyard(fp)
        for pad in sexp.find_all(fp, 'pad'):
            (x, y, d) = (float(sexp.find(pad, 'at')[1]), float(sexp.find(pad, 'at')[2]), float(sexp.find(pad, 'size')[1]))
            with self.subTest(pad=str(pad[1]), x=x):
                self.assertTrue(cx0 <= x - d / 2 and x + d / 2 <= cx1 and cy0 <= y - d / 2 and y + d / 2 <= cy1)

    def test_every_footprint_of_ours_is_in_notice(self):
        # Every reused file is recorded in NOTICE, which is also the clean-room audit trail
        with open(os.path.join(paths.ROOT, 'NOTICE'), encoding='utf-8') as stream:
            notice = stream.read()
        for name in sorted(os.listdir(os.path.join(paths.LIB, 'liz4270.pretty'))):
            with self.subTest(footprint=name):
                self.assertIn(name, notice)

    def test_the_generated_symbols_are_current(self):
        self.assertEqual(make_library.stale(), [])


if __name__ == '__main__':
    unittest.main()
