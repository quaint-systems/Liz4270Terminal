# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The coax sheet: the Liz 4174's port 1 (liz4174-v1, interface3's port 0), with the spec's changes
("Coax front end"): TX_ACTIVE's pull-down, the unused channels held, the driver's pin 12 high, unfitted ESD.

The live circuit is drawn: T1 in the middle, the line side on its right, the receiver's channel B above-left
facing it, and the two driver channels below-left, each output through its resistor to a TX_P or TX_N bus.
Both drivers' OUT- go to TX_P and both OUT+ to TX_N, so one crossing (no junction) is unavoidable."""

import parts as P


def build(project):
    s = project.sheet('coax.kicad_sch', 'Coax', 'Coax front end (interface3 port 0)')

    d = s.drawing('Line, transformer, receiver and summed drive. The line side floats: keep other copper away')

    # The line: BNC, 120 R, T1's line winding, and the unfitted shell capacitor
    d.add(P.T786J, 'T1', {'1': 'LINE_C', '6': 'LINE_S', '2': 'RX_P', '5': 'RX_N', '3': 'TX_P', '4': 'TX_N'},
          at=(0, 0))
    d.add(P.R120, 'R10', {'1': 'LINE_C', '2': 'LINE_S'}, at=(15.24, 0))
    d.add(P.BNC, 'J3', {'1': 'LINE_C', '2': 'LINE_S'}, at=(30.48, -5.08))
    d.add(P.C1N_2KV, 'C26', {'1': 'LINE_S', '2': 'GND'}, dnp=True, at=(22.86, 8.89))
    d.wire('T1.1', (15.24, -5.08), 'J3.1')
    d.wire('R10.1', (15.24, -5.08))
    d.wire('T1.6', (15.24, 5.08), 'C26.1', (30.48, 5.08), 'J3.2')
    d.wire('R10.2', (15.24, 5.08))
    d.label('LINE_C', (6.35, -5.08), 'right')
    d.label('LINE_S', (6.35, 5.08), 'right')

    # Receive: DS34LV86T channel B, turned to face the RX winding; channels A, C and D sit with the unused ones
    d.add(P.DS34LV86T, 'U3', {
        '6': 'RX_P', '7': 'RX_N', '5': 'COAX_RX', '4': '+3V3',                 # B, always enabled
        '2': '+3V3', '1': 'GND',                                               # A: IN+ high, IN- low
        '10': '+3V3', '9': 'GND', '14': '+3V3', '15': 'GND', '12': 'GND',      # C and D
        '8': 'GND', '16': '+3V3'}, nc=['3', '11', '13'],
        rot={1: 0, 2: 180, 3: 0, 4: 0}, at={2: (-35.56, -22.86)})
    d.wire('T1.2', (-10.16, -12.7), (-10.16, -25.4), 'U3.6')
    d.wire('T1.5', (-15.24, -2.54), (-15.24, -20.32), 'U3.7')
    d.label('RX_P', (-20.32, -25.4), 'right')
    d.label('RX_N', (-13.97, -2.54), 'right')
    # Turned, its GND pin points up and its VCC pin down: short wires take them to upright power symbols
    d.wire('U3.8', (-33.02, -35.56), (-25.4, -35.56))
    d.label('GND', (-25.4, -35.56), 'down')
    d.wire('U3.16', (-33.02, -11.43), (-50.8, -11.43))
    d.label('+3V3', (-50.8, -11.43), 'up')

    # Transmit: DS34LV87T channel B (main drive, 33 R) above channel A (delayed drive, 150 R), each output fanned
    # out to its resistor, then the two buses to the TX winding, with the 510 R bridge across it
    # The DRV_ nets join each output to its resistor alone. The wires show them, so they carry no label and KiCad
    # names them; the writer still checks every wire against them.
    d.add(P.DS34LV87T, 'U4', {
        '1': 'COAX_TX_DELAY', '2': 'DRV_A_P', '3': 'DRV_A_N',
        '7': 'COAX_TX', '6': 'DRV_B_P', '5': 'DRV_B_N',
        '4': 'COAX_TX_ACTIVE', '9': 'GND', '15': 'GND', '8': 'GND', '16': '+3V3',
        '12': '+3V3'},        # DS34LV87T: C and D on, idle; an AM26LV31E's G-bar, off, so pin 4 alone enables it
        nc=['10', '11', '13', '14'], at={2: (-55.88, 5.08), 1: (-55.88, 40.64)})
    d.add(P.R33, 'R13', {'1': 'DRV_B_N', '2': 'TX_P'}, rot=90, at=(-34.29, 0))
    d.add(P.R33, 'R14', {'1': 'DRV_B_P', '2': 'TX_N'}, rot=90, at=(-34.29, 10.16))
    d.add(P.R150, 'R11', {'1': 'DRV_A_N', '2': 'TX_P'}, rot=90, at=(-34.29, 35.56))
    d.add(P.R150, 'R12', {'1': 'DRV_A_P', '2': 'TX_N'}, rot=90, at=(-34.29, 45.72))
    d.add(P.R510, 'R15', {'1': 'TX_P', '2': 'TX_N'}, at=(-15.24, 7.62))
    d.wire('U4.5', (-40.64, 2.54), (-40.64, 0), 'R13.1')
    d.wire('U4.6', (-40.64, 7.62), (-40.64, 10.16), 'R14.1')
    d.wire('U4.3', (-40.64, 38.1), (-40.64, 35.56), 'R11.1')
    d.wire('U4.2', (-40.64, 43.18), (-40.64, 45.72), 'R12.1')
    d.wire('R13.2', (-25.4, 0), (-25.4, 35.56), 'R11.2')                    # TX_P
    d.wire((-25.4, 2.54), 'T1.3')
    d.wire('R15.1', (-15.24, 2.54))
    d.wire('R14.2', (-20.32, 10.16), (-20.32, 45.72), 'R12.2')              # TX_N, crossing TX_P once
    d.wire((-20.32, 12.7), 'T1.4')
    d.wire('R15.2', (-15.24, 12.7))
    d.label('TX_P', (-12.7, 2.54), 'right')
    d.label('TX_N', (-12.7, 12.7), 'right')

    # TX_ACTIVE: held low through reset (RP2350-E9) by R16 at channel A's enable
    d.add(P.R4K7, 'R16', {'1': 'COAX_TX_ACTIVE', '2': 'GND'}, at=(-48.26, 60.96))
    d.wire('U4.4@2', (-55.88, 22.86), (-63.5, 22.86))
    d.label('COAX_TX_ACTIVE', (-63.5, 22.86), 'left')
    d.wire('U4.4@1', (-55.88, 57.15), 'R16.1')
    d.wire((-55.88, 57.15), (-63.5, 57.15))
    d.label('COAX_TX_ACTIVE', (-63.5, 57.15), 'left')

    g = s.group('Unused channels, held at a defined level: receiver A, C, D; driver C, D')
    g.take('U3', [1, 3, 4])
    g.take('U4', [3, 4])

    g = s.group('Decoupling at U3 and U4')
    g.add(P.C100N, 'C22', {'1': '+3V3', '2': 'GND'})
    g.add(P.C10N, 'C23', {'1': '+3V3', '2': 'GND'})
    g.add(P.C100N, 'C24', {'1': '+3V3', '2': 'GND'})
    g.add(P.C10N, 'C25', {'1': '+3V3', '2': 'GND'})

    g = s.group('ESD on the windings, not fitted on rev A (bring-up step 7 decides)')
    g.add(P.SRV05_4, 'U5', {'1': 'TX_P', '3': 'TX_N', '4': 'RX_P', '6': 'RX_N', '2': 'GND', '5': '+3V3'}, dnp=True)
