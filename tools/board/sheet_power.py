# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The power sheet: USB-C (power and the console), its protection, the 3.3 V LDO, the power LED, test points
and mounting holes (spec, "Power"). interface2's fuse and ferrite sat on its USB input too.

The live circuit is drawn: J6 on the left, VBUS up from it to a rail along the top, through the fuse, the TVS,
the ferrite and the bulk capacitors to +5V, then the LDO, its capacitors and the power LED on +3V3. CC1 and CC2
rise beside VBUS to their 5.1 k pull-downs under the rail. D+ and D- run straight through the USBLC6, turned
180 so that its channels meet them in the connector's order; its GND pin then points up and its VBUS pin down,
and short wires take them to upright symbols. The USBLC6 splits each data line in two, so each half carries
its global label. Every net keeps its name, so the netlist is the one the listed sheet gave."""

import parts as P


def build(project):
    s = project.sheet('power.kicad_sch', 'Power', 'USB-C in, 3.3 V, LED, test points')

    d = s.drawing('USB-C in: 5.1 k on each CC, ESD on D+/D-; fuse, TVS, ferrite and bulk to +5V; 3.3 V LDO; LED')

    # The connector: VBUS rises to the rail; its four GND pins and the shield share one ground
    d.add(P.USB_C, 'J6', {'VBUS': 'VBUS', 'GND': 'GND', 'CC1': 'CC1', 'CC2': 'CC2', 'D+': 'USBC_DP', 'D-': 'USBC_DM',
                          'SHIELD': 'GND'}, nc=['SBU1', 'SBU2'], at=(0, 0))
    d.wire('J6.SH', (-7.62, 25.4), (0, 25.4), 'J6.A1')
    d.label('GND', (0, 25.4), 'down')

    # CC: each pin rises beside VBUS to its 5.1 k, so any source supplies 5 V
    d.add(P.R5K1, 'R41', {'1': 'CC2', '2': 'GND'}, at=(25.4, -16.51))
    d.add(P.R5K1, 'R40', {'1': 'CC1', '2': 'GND'}, at=(35.56, -16.51))
    d.wire('J6.B5', (20.32, -7.62), (20.32, -20.32), 'R41.1')
    d.wire('J6.A5', (17.78, -10.16), (17.78, -25.4), (35.56, -25.4), 'R40.1')
    d.label('CC2', (20.32, -20.32), 'right')
    d.label('CC1', (22.86, -25.4), 'right')

    # D+ and D-: each pair joined at the connector and run through the USBLC6, turned 180 so its I/O2 (D-) is on
    # top as the connector's D- is
    d.add(P.USBLC6, 'U11', {'I/O1': 'USBC_DP', 'I/O2': 'USBC_DM', 'GND': 'GND', 'VBUS': 'VBUS'}, rot=180,
          at=(60.96, 2.54))
    d.wire('J6.B7', 'U11.4')
    d.wire('J6.A7', (17.78, -2.54), (17.78, 0))
    d.label('USBC_DM', (17.78, -2.54), 'right')
    d.wire('J6.A6', 'U11.6')
    d.wire('J6.B6', (17.78, 5.08), (17.78, 2.54))
    d.label('USBC_DP', (17.78, 5.08), 'right')
    d.wire('U11.3', (68.58, 0))
    d.label('USBC_DM', (68.58, 0), 'right')
    d.wire('U11.1', (73.66, 2.54))
    d.label('USBC_DP', (73.66, 2.54), 'right')
    d.wire('U11.2', (60.96, -7.62), (66.04, -7.62))
    d.label('GND', (66.04, -7.62), 'down')
    d.wire('U11.5', (60.96, 10.16), (66.04, 10.16))
    d.label('VBUS', (66.04, 10.16), 'up')

    # The rail: resettable fuse, 5 V TVS (cathode on the rail), ferrite, bulk
    d.wire('J6.A4', (15.24, -30.48), 'F1.1')
    d.label('VBUS', (15.24, -30.48), 'up')
    d.add(P.PTC, 'F1', {'1': 'VBUS', '2': 'VBUS_F'}, rot=90, at=(45.72, -30.48))
    d.add(P.TVS_5V, 'D4', {'K': 'VBUS_F', 'A': 'GND'}, rot=270, at=(55.88, -26.67))
    d.add(P.FERRITE, 'FB1', {'1': 'VBUS_F', '2': '+5V'}, rot=90, at=(76.2, -30.48))
    d.wire('F1.2', 'D4.1', 'FB1.1')
    d.label('VBUS_F', (60.96, -30.48), 'right')
    d.add(P.C22U, 'C40', {'1': '+5V', '2': 'GND'}, at=(86.36, -26.67))
    d.add(P.C100N, 'C41', {'1': '+5V', '2': 'GND'}, at=(99.06, -26.67))

    # 3.3 V: AP7361C, 1 A LDO in SOT-223 (about 0.25 W at 150 mA), with 10 u in and 10 u + 100 n out
    d.add(P.C10U, 'C42', {'1': '+5V', '2': 'GND'}, at=(111.76, -26.67))
    d.add(P.AP7361C_33, 'U12', {'VI': '+5V', 'GND': 'GND', 'VO': '+3V3'}, at=(127, -30.48))
    d.wire('FB1.2', 'C40.1', 'C41.1', 'C42.1', 'U12.1')
    d.label('+5V', (86.36, -30.48), 'up')
    d.add(P.C10U, 'C43', {'1': '+3V3', '2': 'GND'}, at=(139.7, -26.67))
    d.add(P.C100N, 'C44', {'1': '+3V3', '2': 'GND'}, at=(152.4, -26.67))

    # The power LED, lit from +3V3 through 1 k
    d.add(P.R1K, 'R42', {'1': '+3V3', '2': 'LED_PWR_A'}, at=(165.1, -26.67))
    d.add(P.LED_RED, 'D5', {'A': 'LED_PWR_A', 'K': 'GND'}, rot=90, at=(165.1, -13.97))
    d.wire('U12.3', 'C43.1', 'C44.1', 'R42.1')
    d.label('+3V3', (165.1, -30.48), 'up')
    d.wire('R42.2', 'D5.2')
    d.label('LED_PWR_A', (165.1, -20.32), 'right')

    s.flag('VBUS')                        # the connector feeds it, and its pins are passive
    s.flag('+5V')
    s.flag('GND')

    g = s.group('Test points (bare pads), mounting holes (H4 unplated, by the BNC)')
    for (ref, net) in (('TP1', '+5V'), ('TP2', '+3V3'), ('TP3', '+1V8'), ('TP4', '+1V1'), ('TP5', 'GND')):
        g.add(P.TESTPOINT, ref, {'1': net})
    for ref in ('H1', 'H2', 'H3'):
        g.add(P.HOLE_PLATED, ref, {'1': 'GND'})
    g.add(P.HOLE, 'H4')
