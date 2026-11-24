# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The audio sheet: the TLV320DAC3100's beep generator as #18 drives it (I2C0 at 0x18, MCLK on GPIO25, the DAC
the I2S master), speaker only (spec, "Sound"). DVDD is 1.8 V: its absolute maximum is 2.5 V (TI SLAS671C, 4.1).

Two small circuits are drawn. The 1.8 V regulator runs left to right from +5V to +1V8, EN tied to VIN. The DAC
takes its controls and clocks from the left, its reset pulled up there; on the right each supply pin steps out to
an upright rail symbol, the grounds share one wire, and each speaker output's two pins join on their way to J7."""

import parts as P


def build(project):
    s = project.sheet('audio.kicad_sch', 'Audio', 'TLV320DAC3100 and speaker')

    # TI's power-up order (SLAS671C, 6.3.1) is SPKVDD, IOVDD, DVDD, then AVDD and HPVDD. IOVDD shares 3.3 V with AVDD and
    # HPVDD, so no 1.8 V source meets it; TI calls the part tolerant of order (section 8), and the firmware resets it.
    d = s.drawing('1.8 V for the DAC core: AP2127K from 5 V, as on the Fruit Jam')
    d.add(P.AP2127K_18, 'U13', {'VIN': '+5V', 'GND': 'GND', 'EN': '+5V', 'VOUT': '+1V8'}, nc=['NC'], at=(0, 0))
    d.add(P.C1U, 'C50', {'1': '+5V', '2': 'GND'}, at=(-30.48, 1.27))       # clear of U13's part number
    d.add(P.C1U, 'C51', {'1': '+1V8', '2': 'GND'}, at=(17.78, 1.27))
    d.wire('U13.1', 'C50.1')
    d.wire('U13.3', (-12.7, 0), (-12.7, -2.54))
    d.label('+5V', (-30.48, -2.54), 'up')
    d.wire('U13.5', 'C51.1')
    d.label('+1V8', (17.78, -2.54), 'up')

    # AIN1 and AIN2 are left open: the DAC can bias them (page 1, register 50), so TI's engineers advise against
    # grounding them, and the firmware never routes them. VOL/MICDET is grounded; both its functions are off at reset.
    d = s.drawing('TLV320DAC3100 and the speaker (8 R, about 1 W, in the case behind a grille); AIN1, AIN2, MICBIAS, '
                  'the headphone outputs and GPIO1 open')
    d.add(P.TLV320DAC3100, 'U14', {
        'IOVSS': 'GND', 'IOVDD': '+3V3', 'DVDD': '+1V8', 'DIN': 'I2S_DIN', 'WCLK': 'I2S_WCLK', 'BCLK': 'I2S_BCLK',
        'MCLK': 'I2S_MCLK', 'SDA': 'I2C_SDA', 'SCL': 'I2C_SCL', 'VOL/MICDET': 'GND',
        'AVSS': 'GND', 'AVDD': '+3V3', 'DVSS': 'GND', 'SPKM': 'SPK_N', 'SPKVSS': 'GND', 'SPKVDD': '+5V',
        'SPKP': 'SPK_P', 'HPVDD': '+3V3', 'HPVSS': 'GND', '~{RESET}': 'DAC_RESET', 'EP': 'GND'},
        nc=['NC', 'AIN1', 'AIN2', 'MICBIAS', 'HPL', 'HPR', 'GPIO1'], at=(0, 0))

    # Reset, held by R43 until the firmware drives GPIO22
    d.add(P.R10K, 'R43', {'1': '+3V3', '2': 'DAC_RESET'}, at=(-22.86, -34.29))
    d.wire('U14.31', (-17.78, -25.4), (-17.78, -30.48), 'R43.2', (-30.48, -30.48))
    d.label('DAC_RESET', (-30.48, -30.48), 'left')
    d.wire('U14.11', (-20.32, 5.08))
    d.label('GND', (-20.32, 5.08), 'down')

    # Supplies, each a step further right so that its symbol stands clear of the wires above: IOVDD, DVDD, AVDD with
    # HPVDD, then both SPKVDD
    d.wire('U14.2', (20.32, -25.4))
    d.label('+3V3', (20.32, -25.4), 'up')
    d.wire('U14.3', (27.94, -22.86))
    d.label('+1V8', (27.94, -22.86), 'up')
    d.wire('U14.17', (35.56, -20.32))
    d.wire('U14.28', (35.56, -17.78), (35.56, -20.32))
    d.label('+3V3', (35.56, -20.32), 'up')
    d.wire('U14.21', (43.18, -15.24))
    d.wire('U14.24', (43.18, -12.7), (43.18, -15.24))
    d.label('+5V', (43.18, -15.24), 'up')

    # The speaker: each output is two pins, joined on the way to J7
    d.add(P.JST_PH2, 'J7', {'1': 'SPK_P', '2': 'SPK_N'}, at=(35.56, -5.08))
    d.wire('U14.26', 'J7.1')
    d.wire('U14.22', (17.78, -7.62), (17.78, -5.08))
    d.wire('U14.19', 'J7.2')
    d.wire('U14.23', (17.78, 0), (17.78, -2.54))
    d.label('SPK_P', (20.32, -5.08), 'right')
    d.label('SPK_N', (20.32, -2.54), 'right')

    # The grounds, joined
    d.wire('U14.1', (20.32, 10.16), (20.32, 30.48))
    for (pin, y) in (('18', 12.7), ('16', 15.24), ('29', 17.78), ('20', 20.32), ('25', 22.86), ('33', 25.4)):
        d.wire(f'U14.{pin}', (20.32, y))
    d.label('GND', (20.32, 30.48), 'down')

    g = s.group('Decoupling at each supply pin; 10 uF on DVDD, as on the Fruit Jam and in TI\'s typical circuit')
    for (ref, spec, net) in (('C52', P.C100N, '+3V3'), ('C53', P.C100N, '+1V8'), ('C54', P.C10U, '+1V8'),
                             ('C55', P.C100N, '+3V3'), ('C56', P.C10U, '+3V3'), ('C57', P.C100N, '+3V3'),
                             ('C58', P.C100N, '+5V'), ('C59', P.C100N, '+5V'), ('C60', P.C10U, '+5V')):
        g.add(spec, ref, {'1': net, '2': 'GND'})
