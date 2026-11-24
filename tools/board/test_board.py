# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The schematic against the board's design (#90).

kicad-cli reads hardware/board/liz4270.kicad_sch as KiCad will and reports the netlist and ERC. The tables
here restate the spec on purpose instead of importing the sheets: a slip in a sheet must not slip past its test.
"""

import os
import unittest

import netlist
import paths
import symlib

SCHEMATIC = os.path.join(paths.BOARD, 'liz4270.kicad_sch')
HAVE = os.path.exists(paths.KICAD_CLI) and os.path.exists(SCHEMATIC)

# The spec's "Pin map": GPIO -> net. Every other GPIO is unconnected.
PIN_MAP = {
    1: 'USBH_DP', 2: 'USBH_DM', 4: 'BOARD_ID0', 5: 'BOARD_ID1', 6: 'USBH_FAULT', 7: 'HPD_SENSE',
    8: 'UART_TX', 9: 'UART_RX', 11: 'USBH_EN',
    12: 'HSTX_CKN', 13: 'HSTX_CKP', 14: 'HSTX_D0N', 15: 'HSTX_D0P',
    16: 'HSTX_D1N', 17: 'HSTX_D1P', 18: 'HSTX_D2N', 19: 'HSTX_D2P',
    20: 'I2C_SDA', 21: 'I2C_SCL', 22: 'DAC_RESET', 24: 'I2S_DIN', 25: 'I2S_MCLK', 26: 'I2S_BCLK', 27: 'I2S_WCLK',
    29: 'LED_HEARTBEAT', 41: 'COAX_RX', 42: 'COAX_TX', 43: 'COAX_TX_ACTIVE', 44: 'COAX_TX_DELAY',
}
# HSTX line -> HDMI connector pin (Fruit Jam: clock N/P on GPIO 12/13, D0 on 14/15, D1 on 16/17, D2 on 18/19)
HDMI_PIN = {'CKN': '12', 'CKP': '10', 'D0N': '9', 'D0P': '7', 'D1N': '6', 'D1P': '4', 'D2N': '3', 'D2P': '1'}

_rp2350b = []


def rp(name):
    """The RP2350B's pin numbers called name."""
    if not _rp2350b:
        _rp2350b.append(symlib.lookup('MCU_RaspberryPi:RP2350B'))
    numbers = sorted({p.number for p in _rp2350b[0].pins if p.name == name})
    assert numbers, name
    return numbers


def gpio(n):
    (number,) = rp(f'GPIO{n}/ADC{n - 40}' if n >= 40 else f'GPIO{n}')
    return number


_exported = []


def exported():
    if not _exported:
        _exported.append(netlist.export(SCHEMATIC))
    return _exported[0]


@unittest.skipUnless(HAVE, 'needs kicad-cli and hardware/board/liz4270.kicad_sch')
class BoardCase(unittest.TestCase):
    def setUp(self):
        self.n = exported()

    def net(self, ref, pin):
        return self.n.net(ref, str(pin))

    def assertNets(self, ref, table):
        for (pin, want) in table.items():
            with self.subTest(ref=ref, pin=pin):
                self.assertEqual(self.net(ref, pin), want)

    def assertAlone(self, ref, pins):
        for pin in pins:
            with self.subTest(ref=ref, pin=pin):
                self.assertIsNone(self.net(ref, pin))

    def assertBetween(self, ref, a, b, value=None):
        """Two-pin part ref sits between nets a and b, either way round."""
        self.assertEqual({self.net(ref, 1), self.net(ref, 2)}, {a, b}, ref)
        if value is not None:
            self.assertEqual(self.n.parts[ref].value, value, ref)


class TestPinMap(BoardCase):
    def test_every_gpio_in_the_pin_map(self):
        for (n, want) in PIN_MAP.items():
            with self.subTest(gpio=n):
                self.assertEqual(self.net('U1', gpio(n)), want)

    def test_every_other_gpio_is_unconnected(self):
        self.assertAlone('U1', [gpio(n) for n in range(48) if n not in PIN_MAP])


class TestMcu(BoardCase):
    def test_supplies(self):
        for (name, rail) in (('IOVDD', '+3V3'), ('QSPI_IOVDD', '+3V3'), ('USB_OTP_VDD', '+3V3'), ('ADC_AVDD', '+3V3'),
                             ('VREG_VIN', '+3V3'), ('DVDD', '+1V1'), ('VREG_FB', '+1V1'), ('VREG_PGND', 'GND'),
                             ('GND', 'GND'), ('VREG_AVDD', 'VREG_AVDD'), ('VREG_LX', 'VREG_LX')):
            for number in rp(name):
                with self.subTest(pin=name, number=number):
                    self.assertEqual(self.net('U1', number), rail)

    def test_core_regulator_as_raspberry_pi_draws_it(self):
        self.assertNets('L1', {'1': '+1V1', '2': 'VREG_LX'})
        self.assertEqual(self.n.parts['L1'].footprint, 'liz4270:Abracon_AOTA-B201610S3R3-101-T')
        self.assertBetween('R1', '+3V3', 'VREG_AVDD', '33')
        self.assertBetween('C1', '+3V3', 'GND', '4.7u')
        self.assertBetween('C2', '+1V1', 'GND', '4.7u')
        self.assertBetween('C3', '+1V1', 'GND', '4.7u')
        self.assertBetween('C4', 'VREG_AVDD', 'GND', '4.7u')

    def test_100n_at_each_supply_pin(self):
        for i in range(5, 16):
            self.assertBetween(f'C{i}', '+3V3', 'GND', '100n')
        for i in range(16, 19):
            self.assertBetween(f'C{i}', '+1V1', 'GND', '100n')

    def test_crystal(self):
        self.assertNets('Y1', {'1': 'XIN', '2': 'GND', '4': 'GND'})
        self.assertEqual(self.net('U1', rp('XIN')[0]), 'XIN')
        self.assertEqual(self.net('U1', rp('XOUT')[0]), 'XOUT')
        # XOUT reaches the crystal through R2. The crystal's side is drawn without a label: nothing else may be on it.
        self.assertEqual(self.net('R2', '1'), 'XOUT')
        self.assertEqual(self.n.on(self.net('R2', '2')), {('R2', '2'), ('Y1', '3'), ('C20', '1')})
        self.assertEqual(self.n.parts['R2'].value, '1k')
        self.assertBetween('C19', 'XIN', 'GND', '15p')
        self.assertEqual(self.net('C20', '2'), 'GND')
        self.assertEqual(self.n.parts['C20'].value, '15p')

    def test_flash_and_boot_straps(self):
        self.assertNets('U2', {'1': 'QSPI_SS', '2': 'QSPI_SD1', '3': 'QSPI_SD2', '4': 'GND', '5': 'QSPI_SD0',
                               '6': 'QSPI_SCLK', '7': 'QSPI_SD3', '8': '+3V3'})
        for (name, want) in (('~{QSPI_SS}', 'QSPI_SS'), ('QSPI_SCLK', 'QSPI_SCLK'), ('QSPI_SD0', 'QSPI_SD0'),
                             ('QSPI_SD1', 'QSPI_SD1'), ('QSPI_SD2', 'QSPI_SD2'), ('QSPI_SD3', 'QSPI_SD3')):
            self.assertEqual(self.net('U1', rp(name)[0]), want, name)
        self.assertBetween('C21', '+3V3', 'GND', '100n')                  # the flash's decoupling
        # BOOTSEL: 1 k from the chip select to the switch, a net drawn without a label, so nothing else is on it
        self.assertEqual(self.net('R4', '1'), 'QSPI_SS')
        self.assertEqual(self.n.on(self.net('R4', '2')), {('R4', '2'), ('SW1', '1')})
        self.assertEqual(self.n.parts['R4'].value, '1k')
        self.assertEqual(self.net('SW1', '2'), 'GND')
        self.assertBetween('SW2', 'RUN', 'GND')
        for ref in ('SW1', 'SW2'):                        # the switch's metal frame, where fingers touch (gate 2)
            self.assertEqual(self.net(ref, 'SH'), 'GND', ref)
        # RUN runs 60-90 mm to RESET on the chip's own pull-up: 100 n at its pin, not fitted, for a board that resets
        # by itself (gate 2)
        self.assertBetween('C61', 'RUN', 'GND', '100n')
        self.assertTrue(self.n.parts['C61'].dnp)
        self.assertEqual(self.net('U1', rp('RUN')[0]), 'RUN')
        self.assertBetween('R3', '+3V3', 'QSPI_SS', '10k')
        self.assertTrue(self.n.parts['R3'].dnp)

    def test_console_usb(self):
        # Each line goes straight from the chip to its 27 R, drawn without a label: nothing else may be on it
        for (name, r, usbc) in (('USB_DP', 'R5', 'USBC_DP'), ('USB_DM', 'R6', 'USBC_DM')):
            with self.subTest(pin=name):
                (number,) = rp(name)
                self.assertEqual(self.n.on(self.net('U1', number)), {('U1', number), (r, '1')})
                self.assertEqual(self.net(r, '2'), usbc)
                self.assertEqual(self.n.parts[r].value, '27')

    def test_board_id_reads_00(self):
        self.assertBetween('R7', 'BOARD_ID0', 'GND', '4.7k')
        self.assertBetween('R8', 'BOARD_ID1', 'GND', '4.7k')

    def test_heartbeat_lights_when_gpio29_is_low(self):
        self.assertEqual(self.net('D1', '1'), 'LED_HEARTBEAT')            # 1 is the cathode, 2 the anode
        self.assertEqual(self.n.on(self.net('D1', '2')), {('D1', '2'), ('R9', '2')})    # drawn without a label
        self.assertEqual(self.net('R9', '1'), '+3V3')
        self.assertEqual(self.n.parts['R9'].value, '1k')

    def test_swd_and_bench_header(self):
        # Raspberry Pi's 3-pin debug connector (RP-003139-SP): 1 SC, 2 GND, 3 SD, with 100 R at the target's pins
        # The connector's side of each resistor is drawn without a label: nothing else may be on it
        self.assertEqual(self.net('J1', '2'), 'GND')
        self.assertEqual(self.net('U1', rp('SWCLK')[0]), 'SWCLK')
        self.assertEqual(self.net('U1', rp('SWDIO')[0]), 'SWDIO')
        for (pin, r, chip) in (('1', 'R44', 'SWCLK'), ('3', 'R45', 'SWDIO')):
            with self.subTest(pin=pin):
                self.assertEqual(self.n.on(self.net('J1', pin)), {('J1', pin), (r, '2')})
                self.assertEqual(self.net(r, '1'), chip)
                self.assertEqual(self.n.parts[r].value, '100')
        self.assertNets('J2', {'1': 'COAX_RX', '3': 'COAX_TX', '5': 'COAX_TX_ACTIVE', '7': 'COAX_TX_DELAY',
                               '9': 'UART_TX', '11': 'UART_RX', '13': '+3V3'})
        self.assertNets('J2', {str(n): 'GND' for n in range(2, 15, 2)})
        self.assertTrue(self.n.parts['J2'].dnp)


class TestCoax(BoardCase):
    def test_the_line_side_touches_nothing_else(self):
        self.assertNets('J3', {'1': 'LINE_C', '2': 'LINE_S'})
        self.assertNets('T1', {'1': 'LINE_C', '6': 'LINE_S', '2': 'RX_P', '5': 'RX_N', '3': 'TX_P', '4': 'TX_N'})
        self.assertBetween('R10', 'LINE_C', 'LINE_S', '120')
        self.assertEqual(self.n.on('LINE_C'), {('J3', '1'), ('T1', '1'), ('R10', '1')})
        self.assertEqual(self.n.on('LINE_S'), {('J3', '2'), ('T1', '6'), ('R10', '2'), ('C26', '1')})
        self.assertTrue(self.n.parts['C26'].dnp)
        self.assertBetween('C26', 'LINE_S', 'GND', '1n 2kV')

    def test_receiver_channel_b_and_the_rest_held(self):
        self.assertNets('U3', {'6': 'RX_P', '7': 'RX_N', '5': 'COAX_RX', '4': '+3V3',
                               '2': '+3V3', '1': 'GND', '10': '+3V3', '9': 'GND', '14': '+3V3', '15': 'GND',
                               '12': 'GND', '8': 'GND', '16': '+3V3'})
        self.assertAlone('U3', ['3', '11', '13'])

    def test_driver_channels_a_and_b(self):
        self.assertNets('U4', {'1': 'COAX_TX_DELAY', '7': 'COAX_TX', '4': 'COAX_TX_ACTIVE',
                               '9': 'GND', '15': 'GND', '8': 'GND', '16': '+3V3'})
        self.assertAlone('U4', ['10', '11', '13', '14'])

    def test_drive_network_as_the_liz_4174(self):
        # Each output reaches its end of the winding through its own resistor, nothing else on the way: both
        # channels' OUT- (3 and 5) go to TX_P and both OUT+ (2 and 6) to TX_N, A's through 150 R, B's through 33 R.
        for (out, r, value, end) in (('3', 'R11', '150', 'TX_P'), ('2', 'R12', '150', 'TX_N'),
                                     ('5', 'R13', '33', 'TX_P'), ('6', 'R14', '33', 'TX_N')):
            with self.subTest(out=out, r=r):
                self.assertEqual(self.n.on(self.net('U4', out)), {('U4', out), (r, '1')})
                self.assertEqual(self.net(r, '2'), end)
                self.assertEqual(self.n.parts[r].value, value)
        self.assertBetween('R15', 'TX_P', 'TX_N', '510')

    def test_tx_active_pull_down(self):
        self.assertBetween('R16', 'COAX_TX_ACTIVE', 'GND', '4.7k')

    def test_pin_12_high_suits_either_driver(self):
        # DS34LV87T: pin 12 enables channels C and D, whose inputs are grounded and outputs open (TI SNLS116D).
        # AM26LV31E: pin 12 is G-bar, so high leaves pin 4 in charge; low would hold it on (TI SLLS848C).
        self.assertEqual(self.net('U4', '12'), '+3V3')

    def test_esd_array_not_fitted(self):
        self.assertNets('U5', {'1': 'TX_P', '3': 'TX_N', '4': 'RX_P', '6': 'RX_N', '2': 'GND', '5': '+3V3'})
        self.assertTrue(self.n.parts['U5'].dnp)

    def test_decoupling(self):
        self.assertBetween('C22', '+3V3', 'GND', '100n')
        self.assertBetween('C23', '+3V3', 'GND', '10n')
        self.assertBetween('C24', '+3V3', 'GND', '100n')
        self.assertBetween('C25', '+3V3', 'GND', '10n')


class TestVideo(BoardCase):
    def test_each_hstx_line_reaches_its_connector_pin_through_220r(self):
        for (line, pin) in HDMI_PIN.items():
            with self.subTest(line=line):
                rs = [ref for (ref, _) in self.n.on(f'HSTX_{line}') if ref.startswith('R')]
                self.assertEqual(len(rs), 1)
                self.assertEqual(self.n.parts[rs[0]].value, '220')
                self.assertEqual({self.net(rs[0], 1), self.net(rs[0], 2)}, {f'HSTX_{line}', self.net('J4', pin)})
                self.assertEqual(self.net('J4', pin), f'HDMI_{line}')

    def test_connector(self):
        self.assertNets('J4', {'2': 'GND', '5': 'GND', '8': 'GND', '11': 'GND', '17': 'GND', 'SH': 'GND',
                               '13': 'HDMI_CEC', '14': 'HDMI_UTILITY', '15': 'DDC_SCL', '16': 'DDC_SDA',
                               '18': 'HDMI_5V', '19': 'HDMI_HPD'})

    def test_tpd13s523_takes_the_lines_in_the_connectors_order(self):
        # TI SLVSBC5D, Figure 14: the TMDS clamps, pins 16 down to 9, meet connector pins 1 to 12 in turn, so TI's
        # D0 clamps carry HDMI's Data2 and no pair crosses another. The control clamps (CTRL1-4 on pins 1-4, CTRL5 on
        # 7; all alike) meet pins 13-16 and 19 in the same order.
        in_order = {'16': '1', '15': '3', '14': '4', '13': '6', '12': '7', '11': '9', '10': '10', '9': '12',
                    '1': '13', '2': '14', '3': '15', '4': '16', '7': '19'}
        for (clamp, pin) in in_order.items():
            with self.subTest(clamp=clamp, pin=pin):
                self.assertIsNotNone(self.net('J4', pin))
                self.assertEqual(self.net('U6', clamp), self.net('J4', pin))
        self.assertNets('U6', {'5': '+5V', '6': 'HDMI_5V', '8': 'GND'})

    def test_ddc_level_shifter(self):
        self.assertNets('Q1', {'1': '+3V3', '2': 'I2C_SCL', '3': 'DDC_SCL'})
        self.assertNets('Q2', {'1': '+3V3', '2': 'I2C_SDA', '3': 'DDC_SDA'})
        self.assertBetween('R28', '+3V3', 'I2C_SCL', '10k')
        self.assertBetween('R29', '+3V3', 'I2C_SDA', '10k')
        self.assertBetween('R30', 'HDMI_5V', 'DDC_SCL', '2k')       # HDMI 1.4: 1.5-2.0 k at a source
        self.assertBetween('R31', 'HDMI_5V', 'DDC_SDA', '2k')

    def test_hot_plug_detect(self):
        self.assertBetween('R32', 'HDMI_HPD', 'HPD_SENSE', '220')
        self.assertBetween('R33', 'HPD_SENSE', 'GND', '4.7k')

    def test_decoupling(self):
        self.assertBetween('C30', '+5V', 'GND', '100n')
        self.assertBetween('C31', 'HDMI_5V', 'GND', '100n')


class TestUsbHost(BoardCase):
    def test_load_switch(self):
        self.assertNets('U7', {'5': '+5V', '2': 'GND', '4': 'USBH_EN', '3': 'USBH_FAULT', '1': 'USBH_5V'})
        self.assertBetween('R34', 'USBH_EN', 'GND', '4.7k')
        self.assertBetween('R35', '+3V3', 'USBH_FAULT', '10k')

    def test_hub_as_on_the_fruit_jam(self):
        self.assertNets('U8', {'15': 'USBH_DP', '14': 'USBH_DM', '12': 'USBA1_DP', '11': 'USBA1_DM',
                               '10': 'USBA2_DP', '9': 'USBA2_DM', '19': 'USBH_5V', '20': 'HUB_V33', '25': 'GND',
                               '4': 'HUB_XI', '3': 'HUB_XO'})
        self.assertAlone('U8', ['1', '2', '5', '6', '7', '8', '13', '16', '17', '18', '22', '24'])
        self.assertNets('Y2', {'1': 'HUB_XI', '3': 'HUB_XO', '2': 'GND', '4': 'GND'})

    def test_status_leds(self):
        # LED2 reaches D2's anode and D3's cathode through R36, and LED4/SDA the other two ends, so D2 and D3 sit
        # anti-parallel and light in turn. The three nets are drawn without labels: nothing else may be on them.
        self.assertEqual(self.n.on(self.net('U8', '23')), {('U8', '23'), ('R36', '1')})
        self.assertEqual(self.n.on(self.net('R36', '2')), {('R36', '2'), ('D2', '2'), ('D3', '1')})
        self.assertEqual(self.n.on(self.net('U8', '21')), {('U8', '21'), ('D2', '1'), ('D3', '2')})
        self.assertEqual(self.n.parts['R36'].value, '5.1k')

    def test_ports_and_their_esd(self):
        self.assertNets('J5', {'1': 'USBH_5V', '2': 'USBA1_DM', '3': 'USBA1_DP', '4': 'GND',
                               '5': 'USBH_5V', '6': 'USBA2_DM', '7': 'USBA2_DP', '8': 'GND', 'SH': 'GND'})
        self.assertNets('U9', {'1': 'USBA1_DP', '6': 'USBA1_DP', '3': 'USBA1_DM', '4': 'USBA1_DM', '2': 'GND', '5': 'USBH_5V'})
        self.assertNets('U10', {'1': 'USBA2_DP', '6': 'USBA2_DP', '3': 'USBA2_DM', '4': 'USBA2_DM', '2': 'GND', '5': 'USBH_5V'})
        self.assertBetween('C37', 'USBH_5V', 'GND', '100u')
        self.assertBetween('C38', 'USBH_5V', 'GND', '100u')

    def test_decoupling(self):
        self.assertBetween('C32', '+5V', 'GND', '10u')
        self.assertBetween('C33', 'HUB_V33', 'GND', '10u')
        self.assertBetween('C34', 'HUB_V33', 'GND', '1u')
        self.assertBetween('C35', 'USBH_5V', 'GND', '10u')
        self.assertBetween('C36', 'USBH_5V', 'GND', '100n')


class TestAudio(BoardCase):
    def test_dac(self):
        self.assertNets('U14', {'1': 'GND', '2': '+3V3', '3': '+1V8', '5': 'I2S_DIN', '6': 'I2S_WCLK', '7': 'I2S_BCLK',
                                '8': 'I2S_MCLK', '9': 'I2C_SDA', '10': 'I2C_SCL', '11': 'GND',
                                '16': 'GND', '17': '+3V3', '18': 'GND', '19': 'SPK_N', '20': 'GND', '21': '+5V',
                                '22': 'SPK_P', '23': 'SPK_N', '24': '+5V', '25': 'GND', '26': 'SPK_P', '28': '+3V3',
                                '29': 'GND', '31': 'DAC_RESET', '33': 'GND'})
        # AIN1 and AIN2 (13, 14) open: the DAC can bias them, so TI's engineers advise against grounding them
        self.assertAlone('U14', ['4', '12', '13', '14', '15', '27', '30', '32'])
        self.assertBetween('R43', '+3V3', 'DAC_RESET', '10k')

    def test_its_1v8(self):
        self.assertNets('U13', {'1': '+5V', '2': 'GND', '3': '+5V', '5': '+1V8'})      # from 5 V, as on the Fruit Jam
        self.assertAlone('U13', ['4'])

    def test_speaker(self):
        self.assertNets('J7', {'1': 'SPK_P', '2': 'SPK_N'})

    def test_decoupling(self):
        self.assertBetween('C50', '+5V', 'GND', '1u')
        self.assertBetween('C51', '+1V8', 'GND', '1u')
        self.assertBetween('C52', '+3V3', 'GND', '100n')
        self.assertBetween('C53', '+1V8', 'GND', '100n')
        self.assertBetween('C54', '+1V8', 'GND', '10u')         # DVDD's bulk, as on the Fruit Jam and in TI's circuit
        self.assertBetween('C55', '+3V3', 'GND', '100n')
        self.assertBetween('C56', '+3V3', 'GND', '10u')
        self.assertBetween('C57', '+3V3', 'GND', '100n')
        self.assertBetween('C58', '+5V', 'GND', '100n')
        self.assertBetween('C59', '+5V', 'GND', '100n')
        self.assertBetween('C60', '+5V', 'GND', '10u')


class TestPower(BoardCase):
    def test_usb_c(self):
        self.assertNets('J6', {'A4': 'VBUS', 'A9': 'VBUS', 'B4': 'VBUS', 'B9': 'VBUS', 'A1': 'GND', 'A12': 'GND',
                               'B1': 'GND', 'B12': 'GND', 'A5': 'CC1', 'B5': 'CC2', 'A6': 'USBC_DP', 'B6': 'USBC_DP',
                               'A7': 'USBC_DM', 'B7': 'USBC_DM', 'SH': 'GND'})
        self.assertAlone('J6', ['A8', 'B8'])
        self.assertBetween('R40', 'CC1', 'GND', '5.1k')
        self.assertBetween('R41', 'CC2', 'GND', '5.1k')
        self.assertNets('U11', {'1': 'USBC_DP', '6': 'USBC_DP', '3': 'USBC_DM', '4': 'USBC_DM', '2': 'GND', '5': 'VBUS'})

    def test_input_protection_in_order(self):
        self.assertBetween('F1', 'VBUS', 'VBUS_F')
        self.assertNets('D4', {'1': 'VBUS_F', '2': 'GND'})          # cathode on the rail
        self.assertBetween('FB1', 'VBUS_F', '+5V')

    def test_ldo(self):
        self.assertNets('U12', {'1': '+5V', '2': 'GND', '3': '+3V3'})

    def test_every_supply_pin_on_its_rail(self):
        table = {('U14', '3'): '+1V8', ('U14', '2'): '+3V3', ('U14', '17'): '+3V3', ('U14', '28'): '+3V3',
                 ('U14', '21'): '+5V', ('U14', '24'): '+5V', ('U13', '1'): '+5V', ('U13', '5'): '+1V8',
                 ('U3', '16'): '+3V3', ('U4', '16'): '+3V3', ('U2', '8'): '+3V3', ('U8', '19'): 'USBH_5V',
                 ('U6', '5'): '+5V', ('U7', '5'): '+5V', ('U12', '1'): '+5V', ('U12', '3'): '+3V3',
                 ('U5', '5'): '+3V3'}
        for ((ref, pin), rail) in table.items():
            with self.subTest(ref=ref, pin=pin):
                self.assertEqual(self.net(ref, pin), rail)

    def test_power_led_test_points_and_holes(self):
        self.assertNets('D5', {'2': 'LED_PWR_A', '1': 'GND'})
        self.assertBetween('R42', '+3V3', 'LED_PWR_A', '1k')
        for (ref, net) in (('TP1', '+5V'), ('TP2', '+3V3'), ('TP3', '+1V8'), ('TP4', '+1V1'), ('TP5', 'GND')):
            self.assertEqual(self.net(ref, 1), net, ref)
        for ref in ('H1', 'H2', 'H3'):
            self.assertEqual(self.net(ref, 1), 'GND', ref)
        self.assertIn('H4', self.n.parts)

    def test_decoupling(self):
        self.assertBetween('C40', '+5V', 'GND', '22u')
        self.assertBetween('C41', '+5V', 'GND', '100n')
        self.assertBetween('C42', '+5V', 'GND', '10u')
        self.assertBetween('C43', '+3V3', 'GND', '10u')
        self.assertBetween('C44', '+3V3', 'GND', '100n')


# Every part that isn't a plain R or C: ref -> (value, MPN, LCSC), as tools/board/parts.py chose them on Oct 8, 2026.
# Written out, not imported: a part swapped in a sheet or a Spec edited by mistake must fail here.
IDENTITY = {
    'U1': ('RP2350B', 'RP2350B', 'C42415655'),
    'U2': ('W25Q128JVSIQ', 'W25Q128JVSIQ', 'C97521'),
    'U3': ('DS34LV86TMX/NOPB', 'DS34LV86TMX/NOPB', 'C140249'),
    'U4': ('DS34LV87TM/NOPB', 'DS34LV87TM/NOPB', 'C1543778'),
    'U5': ('SRV05-4', 'SRV05-4.TCT', 'C13612'),
    'U6': ('TPD13S523PWR', 'TPD13S523PWR', 'C2865622'),
    'U7': ('AP2171WG-7', 'AP2171WG-7', 'C110466'),
    'U8': ('CH334F', 'CH334F', 'C5187527'),
    'U9': ('USBLC6-2SC6', 'USBLC6-2SC6', 'C7519'),
    'U10': ('USBLC6-2SC6', 'USBLC6-2SC6', 'C7519'),
    'U11': ('USBLC6-2SC6', 'USBLC6-2SC6', 'C7519'),
    'U12': ('AP7361C-33E-13', 'AP7361C-33E-13', 'C500795'),
    'U13': ('AP2127K-1.8TRG1', 'AP2127K-1.8TRG1', 'C151375'),
    'U14': ('TLV320DAC3100IRHBR', 'TLV320DAC3100IRHBR', 'C179677'),
    'Y1': ('12MHz', 'ABM8-272-T3', 'C20625731'),
    'Y2': ('12MHz', 'ABM8-272-T3', 'C20625731'),
    'L1': ('3.3u', 'AOTA-B201610S3R3-101-T', 'C42411119'),
    'T1': ('78602/8JC', '78602/8JC', 'C7040198'),
    'D1': ('red', 'KT-0603R', 'C2286'),
    'D2': ('red', 'KT-0603R', 'C2286'),
    'D3': ('red', 'KT-0603R', 'C2286'),
    'D4': ('SMAJ5.0A', 'SMAJ5.0A', 'C113952'),
    'D5': ('red', 'KT-0603R', 'C2286'),
    'Q1': ('BSS138', 'BSS138LT1G', 'C82045'),
    'Q2': ('BSS138', 'BSS138LT1G', 'C82045'),
    'F1': ('1.5A', 'MF-MSMF150-2', 'C89648'),
    'FB1': ('220R 3A', 'MPZ2012S221AT000', 'C76818'),
    'J1': ('SWD', '1.0-3PWT', 'C2763613'),
    'J2': ('Bench', '2.54-2*7P', 'C71397'),
    'J3': ('BNC', 'B6252HB-NPP3G-50', 'C22457552'),
    'J4': ('HDMI', '2086581001', 'C916313'),
    'J5': ('USB-A x2', '67298-3091', 'C588409'),
    'J6': ('USB-C', 'TYPE-C-31-M-12', 'C165948'),
    'J7': ('Speaker', 'B2B-PH-K-S(LF)(SN)', 'C131337'),
    'SW1': ('BOOTSEL', 'PTS645VK392LFS', 'C285519'),
    'SW2': ('RESET', 'PTS645VK392LFS', 'C285519'),
}


class TestPartIdentity(BoardCase):
    def test_every_part_but_the_passives_is_the_one_chosen(self):
        for (ref, (value, mpn, lcsc)) in IDENTITY.items():
            with self.subTest(ref=ref):
                part = self.n.parts[ref]
                self.assertEqual((part.value, part.fields.get('MPN'), part.fields.get('LCSC')), (value, mpn, lcsc))

    def test_mounting_holes(self):
        for ref in ('H1', 'H2', 'H3'):
            self.assertEqual(self.n.parts[ref].footprint, 'MountingHole:MountingHole_3.2mm_M3_Pad_Via', ref)
        self.assertEqual(self.n.parts['H4'].footprint, 'MountingHole:MountingHole_3.2mm_M3')    # unplated, by the BNC


class TestBom(BoardCase):
    def test_only_the_bench_aids_and_options_are_left_off(self):
        self.assertEqual({ref for (ref, p) in self.n.parts.items() if p.dnp}, {'R3', 'U5', 'C26', 'J2', 'C61'})

    def test_test_points_and_holes_are_not_bought(self):
        self.assertEqual({ref for (ref, p) in self.n.parts.items() if not p.in_bom},
                         {'TP1', 'TP2', 'TP3', 'TP4', 'TP5', 'H1', 'H2', 'H3', 'H4'})

    def test_every_bought_part_has_an_lcsc_number_and_a_footprint(self):
        for (ref, p) in self.n.parts.items():
            if p.in_bom:
                with self.subTest(ref=ref):
                    self.assertRegex(p.fields.get('LCSC', ''), r'^C\d+$')
                    self.assertTrue(p.footprint)


class TestErc(BoardCase):
    WIRING = {'endpoint_off_grid', 'pin_not_connected', 'label_dangling', 'isolated_pin_label',
              'global_label_dangling', 'multiple_net_names', 'unconnected_wire_endpoint', 'wire_dangling',
              'no_connect_connected', 'no_connect_dangling', 'pin_to_pin', 'power_pin_not_driven',
              'single_global_label'}

    def test_no_errors(self):
        self.assertEqual([v for v in netlist.erc(SCHEMATIC) if v[0] == 'error'], [])

    def test_no_wiring_warnings(self):
        self.assertEqual([v for v in netlist.erc(SCHEMATIC) if v[1] in self.WIRING], [])


class TestGenerated(unittest.TestCase):
    def test_the_files_match_the_generator(self):
        import board
        self.assertEqual(board.project().stale(), [])


if __name__ == '__main__':
    unittest.main()
