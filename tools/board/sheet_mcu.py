# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The MCU sheet: the RP2350B on the Fruit Jam's pin map, its core regulator, crystal, flash, buttons and debug
(spec, "Core" and "Pin map"; Raspberry Pi's Hardware design with RP2350, sections 2 to 4).

The RP2350B is drawn at the middle. Its 3.3 V pins rise to one rail and the core regulator runs right from
VREG_LX through L1 to +1V1. On its left, RUN goes up to RESET, the console USB lines go out through their 27 R,
the six QSPI lines run straight to the flash, mirrored so its pins face them, and the crystal sits below them.
On its right, UART1's names, the board ID pull-downs and the heartbeat LED sit past the labels of the GPIOs that
leave the sheet. BOOTSEL, the SWD connector and the bench header are small drawings of their own, joined to it by
labels: the SWD connector's ground pin sits between SC and SD, and U1's SWD pins have no room around them to wire
it cleanly."""

import parts as P

# The spec's pin map: GPIO -> net. Every other GPIO is no-connect.
PIN_MAP = {
    1: 'USBH_DP', 2: 'USBH_DM', 4: 'BOARD_ID0', 5: 'BOARD_ID1', 6: 'USBH_FAULT', 7: 'HPD_SENSE',
    8: 'UART_TX', 9: 'UART_RX', 11: 'USBH_EN',
    12: 'HSTX_CKN', 13: 'HSTX_CKP', 14: 'HSTX_D0N', 15: 'HSTX_D0P',
    16: 'HSTX_D1N', 17: 'HSTX_D1P', 18: 'HSTX_D2N', 19: 'HSTX_D2P',
    20: 'I2C_SDA', 21: 'I2C_SCL', 22: 'DAC_RESET', 24: 'I2S_DIN', 25: 'I2S_MCLK', 26: 'I2S_BCLK', 27: 'I2S_WCLK',
    29: 'LED_HEARTBEAT', 41: 'COAX_RX', 42: 'COAX_TX', 43: 'COAX_TX_ACTIVE', 44: 'COAX_TX_DELAY',
}


def gpio(n):
    """The RP2350B symbol's name for GPIO n."""
    return f'GPIO{n}/ADC{n - 40}' if n >= 40 else f'GPIO{n}'


def build(project):
    s = project.sheet('mcu.kicad_sch', 'MCU', 'RP2350B, flash, buttons, debug')

    u1 = {gpio(n): net for (n, net) in PIN_MAP.items()}
    u1.update({'IOVDD': '+3V3', 'QSPI_IOVDD': '+3V3', 'USB_OTP_VDD': '+3V3', 'ADC_AVDD': '+3V3', 'VREG_VIN': '+3V3',
               'DVDD': '+1V1', 'VREG_FB': '+1V1', 'VREG_AVDD': 'VREG_AVDD', 'VREG_LX': 'VREG_LX',
               'VREG_PGND': 'GND', 'GND': 'GND', 'XIN': 'XIN', 'XOUT': 'XOUT', 'RUN': 'RUN',
               'SWCLK': 'SWCLK', 'SWDIO': 'SWDIO', 'USB_DP': 'RP_USB_DP', 'USB_DM': 'RP_USB_DM',
               '~{QSPI_SS}': 'QSPI_SS', 'QSPI_SCLK': 'QSPI_SCLK', 'QSPI_SD0': 'QSPI_SD0', 'QSPI_SD1': 'QSPI_SD1',
               'QSPI_SD2': 'QSPI_SD2', 'QSPI_SD3': 'QSPI_SD3'})
    d = s.drawing('RP2350B on the Fruit Jam\'s pin map, with its core regulator (HDG 2.1), flash, crystal (HDG 4), '
                  'console USB (27 R at the chip), RESET (finger), board ID (rev A reads 00) and heartbeat LED')
    d.add(P.RP2350B, 'U1', u1, nc=[gpio(n) for n in range(48) if n not in PIN_MAP], at=(0, 0))

    # 3.3 V: every 3.3 V pin rises to one rail, with CIN (C1) where it comes in; VREG_VIN joins IOVDD, leaving
    # room beside VREG_LX for its name
    d.add(P.C4U7_0402_WIDE, 'C1', {'1': '+3V3', '2': 'GND'}, at=(-60.96, -72.39))
    d.wire('C1.1', (-2.54, -76.2))
    d.label('+3V3', (-60.96, -76.2), 'up')
    for (pin, x) in (('68', -12.7), ('59', -10.16), ('69', -5.08), ('5', -2.54)):   # OTP, ADC, QSPI, IO
        d.wire(f'U1.{pin}', (x, -76.2))
    d.wire('U1.64', (2.54, -58.42), (-2.54, -58.42))

    # VREG_AVDD: 33 R from the rail, 4.7 uF to ground
    d.add(P.R33_0402, 'R1', {'1': '+3V3', '2': 'VREG_AVDD'}, at=(-25.4, -72.39))
    d.add(P.C4U7_0402, 'C4', {'1': 'VREG_AVDD', '2': 'GND'}, at=(-48.26, -59.69))
    d.wire('U1.61', (-17.78, -63.5), (-25.4, -63.5), 'C4.1')
    d.wire('R1.1', (-25.4, -76.2))
    d.wire('R1.2', (-25.4, -63.5))
    d.label('VREG_AVDD', (-45.72, -63.5), 'right')

    # The core regulator: VREG_LX through the polarity-marked 3.3 uH (pin 1 on +1V1) to DVDD, sensed at VREG_FB;
    # COUT and the datasheet's second 4.7 uF on DVDD (6.3.8.1)
    d.add(P.L_AOTA, 'L1', {'1': '+1V1', '2': 'VREG_LX'}, rot=270, at=(8.89, -68.58))
    d.add(P.C4U7_0402_WIDE, 'C2', {'1': '+1V1', '2': 'GND'}, at=(27.94, -64.77))
    d.add(P.C4U7_0402, 'C3', {'1': '+1V1', '2': 'GND'}, at=(40.64, -64.77))
    d.wire('U1.63', 'L1.2')
    d.label('VREG_LX', (5.08, -60.96), 'up')
    d.wire('U1.10', 'L1.1')
    d.wire('U1.65', (7.62, -60.96), (12.7, -60.96))
    d.wire('L1.1', 'C2.1', 'C3.1')
    d.label('+1V1', (20.32, -68.58), 'up')

    # Both grounds to one symbol
    d.wire('U1.62', (-2.54, 60.96), (0, 60.96))
    d.wire('U1.81', (0, 63.5))
    d.label('GND', (0, 63.5), 'down')

    # RESET: RUN to ground (RUN has the chip's own pull-up); its metal frame (SH) to ground too, where fingers touch
    d.add(P.SW_RESET, 'SW2', {'1': 'RUN', '2': 'GND', 'SH': 'GND'}, rot=90, at=(-33.02, -43.18))
    d.wire('U1.35', (-33.02, -33.02), 'SW2.1')
    d.label('RUN', (-31.75, -33.02), 'right')
    d.wire('SW2.2', (-33.02, -50.8), (-25.4, -50.8), (-25.4, -43.18))
    d.wire('SW2.SH', (-25.4, -43.18))
    d.label('GND', (-25.4, -43.18), 'down')
    # RUN runs 60-90 mm to its button on that pull-up alone: 100 n at the pin, not fitted, for a board that resets by
    # itself (gate 2)
    d.add(P.C100N, 'C61', {'1': 'RUN', '2': 'GND'}, dnp=True, rot=180, at=(-43.18, -38.1))
    d.wire('C61.1', (-43.18, -33.02), (-33.02, -33.02))
    d.wire('C61.2', (-43.18, -44.45), (-48.26, -44.45))
    d.label('GND', (-48.26, -44.45), 'down')

    # Console USB: 27 R at the chip, D- stepping up so that the two resistors' texts clear the other line
    d.add(P.R27, 'R6', {'1': 'RP_USB_DM', '2': 'USBC_DM'}, rot=270, at=(-33.02, -27.94))
    d.add(P.R27, 'R5', {'1': 'RP_USB_DP', '2': 'USBC_DP'}, rot=270, at=(-40.64, -22.86))
    d.wire('U1.66', (-27.94, -27.94), 'R6.1')
    d.wire('R6.2', (-48.26, -27.94))
    d.label('USBC_DM', (-48.26, -27.94), 'left')
    d.wire('U1.67', 'R5.1')
    d.wire('R5.2', (-48.26, -22.86))
    d.label('USBC_DP', (-48.26, -22.86), 'left')

    # The flash, mirrored so that its pins face U1's in the same order: six straight lines
    d.add(P.W25Q128, 'U2', {'1': 'QSPI_SS', '2': 'QSPI_SD1', '3': 'QSPI_SD2', '4': 'GND', '5': 'QSPI_SD0',
                            '6': 'QSPI_SCLK', '7': 'QSPI_SD3', '8': '+3V3'}, mirror=True, at=(-76.2, -7.62))
    for (rp, flash, net, y) in (('75', '1', 'QSPI_SS', -15.24), ('71', '6', 'QSPI_SCLK', -12.7),
                                ('72', '5', 'QSPI_SD0', -10.16), ('74', '2', 'QSPI_SD1', -7.62),
                                ('73', '3', 'QSPI_SD2', -5.08), ('70', '7', 'QSPI_SD3', -2.54)):
        d.wire(f'U1.{rp}', f'U2.{flash}')
        d.label(net, (-63.5, y), 'right')

    # The crystal (ABM8-272-T3): 15 pF each side, 1 k on XOUT. XOUT_X runs down and round so that the crystal's
    # ground and C19's can drop between the lines.
    d.add(P.R1K, 'R2', {'1': 'XOUT', '2': 'XOUT_X'}, rot=270, at=(-35.56, 15.24))
    d.add(P.XTAL_12M, 'Y1', {'1': 'XIN', '3': 'XOUT_X', '2': 'GND', '4': 'GND'}, rot=270, mirror=True,
          at=(-55.88, 10.16))
    d.add(P.C15P, 'C19', {'1': 'XIN', '2': 'GND'}, at=(-45.72, 8.89))
    d.add(P.C15P, 'C20', {'1': 'XOUT_X', '2': 'GND'}, at=(-50.8, 26.67))
    d.wire('U1.30', 'C19.1', (-55.88, 5.08), 'Y1.1')
    d.label('XIN', (-33.02, 5.08), 'right')
    d.wire('U1.31', 'R2.1')
    d.label('XOUT', (-31.75, 15.24), 'right')
    d.wire('R2.2', (-41.91, 15.24), (-41.91, 22.86), 'C20.1', (-55.88, 22.86), 'Y1.3')
    d.wire('Y1.2', (-50.8, 12.7), 'C19.2')
    d.wire('C19.2', (-45.72, 15.24))
    d.label('GND', (-45.72, 15.24), 'down')

    # UART1, to the bench header: named past the column of labels, so that their names, which sit above their
    # lines, stay clear of the flags of the lines above them
    d.wire('U1.6', (53.34, -27.94))
    d.label('UART_TX', (53.34, -27.94), 'right')
    d.wire('U1.7', (53.34, -25.4))
    d.label('UART_RX', (53.34, -25.4), 'right')

    # Board ID: each GPIO pulled down past the labels, so rev A reads 00
    d.add(P.R4K7, 'R7', {'1': 'BOARD_ID0', '2': 'GND'}, at=(78.74, -34.29))
    d.add(P.R4K7, 'R8', {'1': 'BOARD_ID1', '2': 'GND'}, at=(68.58, -31.75))
    d.wire('U1.1', 'R7.1')
    d.wire('U1.2', 'R8.1')
    d.label('BOARD_ID0', (27.94, -38.1), 'right')
    d.label('BOARD_ID1', (27.94, -35.56), 'right')

    # Heartbeat: lit while GPIO29 is low
    d.add(P.LED_RED, 'D1', {'A': 'LED_HB_A', 'K': 'LED_HEARTBEAT'}, at=(52.07, 25.4))
    d.add(P.R1K, 'R9', {'1': '+3V3', '2': 'LED_HB_A'}, rot=270, at=(66.04, 25.4))
    d.wire('U1.37', 'D1.1')
    d.label('LED_HEARTBEAT', (27.94, 25.4), 'right')
    d.wire('D1.2', 'R9.2')
    d.wire('R9.1', (72.39, 25.4), (72.39, 20.32))
    d.label('+3V3', (72.39, 20.32), 'up')
    s.flag('+1V1')
    s.flag('VREG_AVDD')

    # BOOTSEL: the HDG's 1 k from the flash's chip select to ground; R3 is for a flash that needs a pull-up
    b = s.drawing('BOOTSEL (pinhole): 1 k from QSPI_SS to ground, as the HDG draws it; R3 only for another flash')
    b.add(P.R1K, 'R4', {'1': 'QSPI_SS', '2': 'BOOTSEL_SW'}, rot=90, at=(3.81, 0))
    b.add(P.SW_BOOTSEL, 'SW1', {'1': 'BOOTSEL_SW', '2': 'GND', 'SH': 'GND'}, at=(17.78, 0))
    b.add(P.R10K, 'R3', {'1': '+3V3', '2': 'QSPI_SS'}, dnp=True, at=(-7.62, -3.81))
    b.wire((-12.7, 0), 'R3.2', 'R4.1')
    b.label('QSPI_SS', (-12.7, 0), 'left')
    b.wire('R4.2', 'SW1.1')
    b.wire('SW1.2', (25.4, 0), (25.4, 6.35))
    b.wire('SW1.SH', (17.78, 6.35), (25.4, 6.35))          # the frame, as on RESET
    b.label('GND', (25.4, 6.35), 'down')

    # Raspberry Pi's 3-pin debug connector (RP-003139-SP): 1 SC, 2 GND, 3 SD, and the 100 R it recommends at the
    # target's pins, for slew, shorts and ESD on a connector a builder handles
    w = s.drawing('SWD: Raspberry Pi\'s 3-pin debug connector, 100 R at the chip')
    w.add(P.JST_SH3, 'J1', {'1': 'SWD_SC', '2': 'GND', '3': 'SWD_SD'}, rot=90, at=(0, 0))
    w.add(P.R100, 'R44', {'1': 'SWCLK', '2': 'SWD_SC'}, rot=90, at=(-12.7, 10.16))
    w.add(P.R100, 'R45', {'1': 'SWDIO', '2': 'SWD_SD'}, rot=270, at=(12.7, 10.16))
    w.wire('J1.1', (-2.54, 10.16), 'R44.2')
    w.wire('R44.1', (-22.86, 10.16))
    w.label('SWCLK', (-22.86, 10.16), 'left')
    w.wire('J1.3', (2.54, 10.16), 'R45.2')
    w.wire('R45.1', (22.86, 10.16))
    w.label('SWDIO', (22.86, 10.16), 'right')
    w.wire('J1.2', (0, 12.7))
    w.label('GND', (0, 12.7), 'down')

    g = s.group('100 nF at each supply pin: 11 on 3.3 V, 3 on DVDD, and the flash\'s')
    for i in range(5, 16):
        g.add(P.C100N, f'C{i}', {'1': '+3V3', '2': 'GND'})
    for i in range(16, 19):
        g.add(P.C100N, f'C{i}', {'1': '+1V1', '2': 'GND'})
    g.add(P.C100N, 'C21', {'1': '+3V3', '2': 'GND'})

    # The bench header: its grounds joined, and UART1 named past the coax flags, as on U1
    h = s.drawing('Bench header (not fitted): coax and UART1, each beside a ground')
    bench = {'1': 'COAX_RX', '3': 'COAX_TX', '5': 'COAX_TX_ACTIVE', '7': 'COAX_TX_DELAY', '9': 'UART_TX',
             '11': 'UART_RX', '13': '+3V3'}
    bench.update({str(n): 'GND' for n in range(2, 15, 2)})
    h.add(P.HEADER_2X7, 'J2', bench, dnp=True, at=(0, 0))
    h.wire('J2.2', (10.16, -7.62), (10.16, 10.16))
    for (n, y) in ((4, -5.08), (6, -2.54), (8, 0), (10, 2.54), (12, 5.08), (14, 7.62)):
        h.wire(f'J2.{n}', (10.16, y))
    h.label('GND', (10.16, 10.16), 'down')
    h.wire('J2.9', (-33.02, 2.54))
    h.label('UART_TX', (-33.02, 2.54), 'left')
    h.wire('J2.11', (-33.02, 5.08))
    h.label('UART_RX', (-33.02, 5.08), 'left')
