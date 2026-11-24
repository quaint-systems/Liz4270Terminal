# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The video sheet: HSTX DVI through 220 R to the HDMI connector, the TPD13S523 at the connector, the DDC
level shifter (shared with the DAC on I2C0, as on the Fruit Jam) and hot-plug detect (spec, "Video").

The circuit is drawn around J4. The HSTX lines come in at the top left through their resistors and fan in to its
pins, the DDC shifters sit below them, one row per line, and hot-plug drops from its pin to the divider. U6 sits
above J4 on the right, turned so that its 5 V output runs straight to pin 18.

U6's thirteen clamps keep their labels. Its symbol and the connector's list the lines in the same order down their
left sides, so no drawing joins every line to both without crossings: that takes a mirrored symbol, and even
mirrored, the resistors would have to tee onto the lines between U6 and J4."""

import parts as P

# HSTX line -> HDMI connector pin. The N line of each pair is on the even GPIO, as on the Fruit Jam.
LINES = (('CKN', '12'), ('CKP', '10'), ('D0N', '9'), ('D0P', '7'), ('D1N', '6'), ('D1P', '4'), ('D2N', '3'), ('D2P', '1'))


def build(project):
    s = project.sheet('video.kicad_sch', 'Video', 'HDMI: HSTX DVI, ESD, DDC, hot-plug')

    d = s.drawing('HSTX through 220 R to HDMI, each pair 100 R differential; DDC shifter on I2C0; hot-plug to GPIO7')

    # The connector, a right-angle Type A with through-hole shell pegs, at the origin; its grounds joined below it
    j4 = {pin: f'HDMI_{line}' for (line, pin) in LINES}
    j4.update({'2': 'GND', '5': 'GND', '8': 'GND', '11': 'GND', '17': 'GND', 'SH': 'GND', '13': 'HDMI_CEC',
               '14': 'HDMI_UTILITY', '15': 'DDC_SCL', '16': 'DDC_SDA', '18': 'HDMI_5V', '19': 'HDMI_HPD'})
    d.add(P.HDMI, 'J4', j4, at=(0, 0))
    d.wire('J4.2', (-5.08, 30.48), (7.62, 30.48), 'J4.SH')
    for (pin, x) in (('5', -2.54), ('8', 0), ('11', 2.54), ('17', 5.08)):
        d.wire(f'J4.{pin}', (x, 30.48))
    d.label('GND', (0, 30.48), 'down')

    # HSTX: a column of 220 R as on the Fruit Jam, in the connector's order, fanning in to its pins. CKN runs
    # straight; each line above it turns down a step further right, so none crosses another.
    for (i, (line, pin)) in enumerate(LINES):
        ref = f'R{20 + i}'
        y = -2.54 - 7.62 * i
        d.add(P.R220, ref, {'1': f'HSTX_{line}', '2': f'HDMI_{line}'}, rot=90, at=(-53.34, y))
        if i == 0:
            d.wire(f'{ref}.2', f'J4.{pin}')
        else:
            x = -38.1 + 2.54 * i
            d.wire(f'{ref}.2', (x, y), (x, -2.54 - 2.54 * i), f'J4.{pin}')
        d.label(f'HDMI_{line}', (-48.26, y), 'right')

    # The TPD13S523, turned so that its current-limited 5 V output faces pin 18; C31 on the output, C30 at the input.
    # On the board its clamps take the lines in the connector's order, so every line runs straight past its clamp
    # (TI SLVSBC5D, Figure 14): TI's D0 clamps take HDMI's Data2 and its D2 clamps Data0, and CTRL1-5 (all alike)
    # take CEC, UTILITY, SCL, SDA and HPD.
    d.add(P.TPD13S523, 'U6', {
        'CTRL1': 'HDMI_CEC', 'CTRL2': 'HDMI_UTILITY', 'CTRL3': 'DDC_SCL', 'CTRL4': 'DDC_SDA', 'CTRL5': 'HDMI_HPD',
        '5V_SUPPLY': '+5V', '5V_OUT': 'HDMI_5V', 'GND': 'GND',
        'D0+': 'HDMI_D2P', 'D0-': 'HDMI_D2N', 'D1+': 'HDMI_D1P', 'D1-': 'HDMI_D1N',
        'D2+': 'HDMI_D0P', 'D2-': 'HDMI_D0N', 'D3+': 'HDMI_CKP', 'D3-': 'HDMI_CKN'}, rot=180, at=(40.64, -50.8))
    d.add(P.C100N, 'C31', {'1': 'HDMI_5V', '2': 'GND'}, at=(10.16, -39.37))
    d.add(P.C100N, 'C30', {'1': '+5V', '2': 'GND'}, at=(27.94, -26.67))
    d.wire('U6.6', 'C31.1', (0, -43.18), 'J4.18')
    d.label('HDMI_5V', (2.54, -43.18), 'right')
    d.wire('U6.5', (22.86, -40.64), (22.86, -30.48), 'C30.1')
    d.label('+5V', (27.94, -30.48), 'up')

    # DDC: a BSS138 per line, 10 k to 3.3 V on I2C0's side (shared with the DAC) and 2 k to the connector's 5 V.
    # 2 k, not the Fruit Jam's 10 k: HDMI 1.4 wants 1.5-2.0 k at a source, and on rising edges the BSS138 joins the
    # cable's capacitance to I2C0. 5 V / 2 k + 3.3 V / 10 k is 2.8 mA, inside I2C's 3 mA.
    # Each line leaves J4, turns down to its row (SDA's further right, so they don't cross) and runs left to its
    # shifter.
    for (n, (line, pin, pin_y, row, turn)) in enumerate((('SCL', '15', 7.62, 22.86, -50.8),
                                                         ('SDA', '16', 10.16, 50.8, -48.26))):
        q, r_i2c, r_ddc = f'Q{1 + n}', f'R{28 + n}', f'R{30 + n}'
        d.add(P.BSS138, q, {'G': '+3V3', 'S': f'I2C_{line}', 'D': f'DDC_{line}'}, rot=270, at=(-66.04, row - 2.54))
        d.add(P.R10K, r_i2c, {'1': '+3V3', '2': f'I2C_{line}'}, at=(-83.82, row - 3.81))
        d.add(P.R2K, r_ddc, {'1': 'HDMI_5V', '2': f'DDC_{line}'}, at=(-58.42, row - 3.81))
        d.wire((-88.9, row), f'{r_i2c}.2', f'{q}.2')
        d.label(f'I2C_{line}', (-88.9, row), 'left')
        d.wire(f'{q}.3', f'{r_ddc}.2', (turn, row), (turn, pin_y), f'J4.{pin}')
    d.label('DDC_SCL', (-45.72, 7.62), 'right')
    d.label('DDC_SDA', (-22.86, 10.16), 'right')

    # Hot-plug: 220 R in from the connector, 4.7 k down (RP2350-E9), to GPIO7, a 5 V-tolerant pad (RP2350
    # datasheet, Table 1673)
    d.add(P.R220, 'R32', {'1': 'HDMI_HPD', '2': 'HPD_SENSE'}, at=(-25.4, 31.75))
    d.add(P.R4K7, 'R33', {'1': 'HPD_SENSE', '2': 'GND'}, at=(-25.4, 44.45))
    d.wire('J4.19', (-12.7, 17.78), (-12.7, 25.4), (-25.4, 25.4), 'R32.1')
    d.label('HDMI_HPD', (-24.13, 25.4), 'right')
    d.wire('R32.2', (-25.4, 38.1), 'R33.1')
    d.wire((-25.4, 38.1), (-30.48, 38.1))
    d.label('HPD_SENSE', (-30.48, 38.1), 'left')
