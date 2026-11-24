# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Every part kind on the board: symbol, footprint, value, MPN and LCSC number
(docs/superpowers/specs/2026-10-08-unified-board-design.md, "Assembly and sourcing").

Checked on lcsc.com and JLC's library on Oct 8, 2026. Each part's comment gives its stock on the day as
LCSC / JLC; one figure means the two were close. Stock moves daily: plan 2 rechecks it at order time.
Passives are JLC Basic parts unless a comment says otherwise.
"""

from schematic import Spec

_METRIC = {'0402': '1005', '0603': '1608', '0805': '2012', '1206': '3216'}


def _r(value, lcsc, size='0603'):
    return Spec('Device:R', value, f'Resistor_SMD:R_{size}_{_METRIC[size]}Metric', lcsc=lcsc)


def _c(value, lcsc, size='0603'):
    return Spec('Device:C', value, f'Capacitor_SMD:C_{size}_{_METRIC[size]}Metric', lcsc=lcsc)


# Resistors, 1%, UNI-ROYAL, Basic
R27 = _r('27', 'C25190')                  # 1,200 / 73,847, Oct 8, 2026; Preferred Extended, not Basic
R33 = _r('33', 'C23140')                  # 3.38 M, Oct 8, 2026; the coax main drive (Liz 4174 R5, R6)
R33_0402 = _r('33', 'C25105', '0402')     # 0 / 1.8 M, Oct 8, 2026; the core regulator's VREG_AVDD filter (HDG 2.1)
R100 = _r('100', 'C22775')                # 3.02 M / 11.0 M, Oct 8, 2026; SWD at the chip (Raspberry Pi RP-003139-SP)
R120 = _r('120', 'C22787')                # 231 k, Oct 8, 2026
R150 = _r('150', 'C22808')                # 145 k, Oct 8, 2026
R220 = _r('220', 'C22962')                # 380 k, Oct 8, 2026
R510 = _r('510', 'C23193')                # 1.86 M, Oct 8, 2026
R1K = _r('1k', 'C21190')                  # 3,800 / 20.4 M, Oct 8, 2026
R2K = _r('2k', 'C22975')                  # 7.89 M / 13.2 M, Oct 8, 2026; DDC's pull-ups (HDMI 1.4: 1.5-2.0 k at a source)
R4K7 = _r('4.7k', 'C23162')               # 10.7 M, Oct 8, 2026
R5K1 = _r('5.1k', 'C23186')               # 20.5 M, Oct 8, 2026
R10K = _r('10k', 'C25804')                # 0 / 28.3 M, Oct 8, 2026

# Capacitors, Basic
C15P = _c('15p', 'C1644')                 # 298,600 / 1.0 M, Oct 8, 2026; C0G
C10N = _c('10n', 'C57112')                # 1.2 M / 6.4 M, Oct 8, 2026
C100N = _c('100n', 'C14663')              # 1.67 M / 59.8 M, Oct 8, 2026
C1U = _c('1u', 'C15849')                  # 2.67 M / 9.2 M, Oct 8, 2026
# 1.2 M / 2.2 M, Oct 8, 2026; the core regulator's CIN, COUT and VREG_AVDD (HDG 2.1)
C4U7_0402 = _c('4.7u', 'C23733', '0402')
# The same part on the minimal design's narrower land (0.47 mm pads, 0.56 mm apart), so that VREG_LX's copper passes
# between CIN's and COUT's pads as Raspberry Pi drew it (plan 2, Task 6)
C4U7_0402_WIDE = Spec('Device:C', '4.7u', 'liz4270:RPi_C_1005_Wide', lcsc='C23733')
C10U = _c('10u', 'C15850', '0805')        # 13,820 / 4.68 M, Oct 8, 2026
C22U = _c('22u', 'C45783', '0805')        # 626,840 / 3.84 M, Oct 8, 2026
# 1.28 M / 1.90 M, Oct 8, 2026; 6.3 V X5R, a USB-A port's bulk, as on the Fruit Jam
C100U = _c('100u', 'C15008', '1206')
C1N_2KV = _c('1n 2kV', 'C9196', '1206')   # 1.55 M / 2.77 M, Oct 8, 2026; BNC shell to ground, not fitted on rev A

# Semiconductors
# 3,214 / 3,214, Oct 8, 2026. The exposed pad is its only ground, so it carries vias (test_parts)
RP2350B = Spec('MCU_RaspberryPi:RP2350B', 'RP2350B',
               'Package_DFN_QFN:QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm_ThermalVias', 'RP2350B', 'C42415655')
# 0 / 55,476, Oct 8, 2026; Basic
W25Q128 = Spec('Memory_Flash:W25Q128JVS', 'W25Q128JVSIQ', 'Package_SO:SOIC-8_5.3x5.3mm_P1.27mm',
               'W25Q128JVSIQ', 'C97521')
# 2,527 / 2,527, Oct 8, 2026
DS34LV86T = Spec('Interface_LineDriver:MC3486N', 'DS34LV86TMX/NOPB', 'Package_SO:SOIC-16_3.9x9.9mm_P1.27mm',
                 'DS34LV86TMX/NOPB', 'C140249')
# 95 / 95, Oct 8, 2026; the reel part DS34LV87TMX/NOPB is C2672589 (54)
DS34LV87T = Spec('Interface_LineDriver:MC3487N', 'DS34LV87TM/NOPB', 'Package_SO:SOIC-16_3.9x9.9mm_P1.27mm',
                 'DS34LV87TM/NOPB', 'C1543778')
# 200 / 200, Oct 8, 2026
TPD13S523 = Spec('liz4270:TPD13S523', 'TPD13S523PWR', 'Package_SO:TSSOP-16_4.4x5mm_P0.65mm',
                 'TPD13S523PWR', 'C2865622')
# 2,162 / 2,162, Oct 8, 2026. Vias in the exposed pad, as TI's land pattern has
TLV320DAC3100 = Spec('liz4270:TLV320DAC3100', 'TLV320DAC3100IRHBR',
                     'Package_DFN_QFN:QFN-32-1EP_5x5mm_P0.5mm_EP3.45x3.45mm_ThermalVias', 'TLV320DAC3100IRHBR',
                     'C179677')
# 7,963 / 7,963, Oct 8, 2026. The exposed pad is its only ground, so it carries vias
CH334F = Spec('Interface_USB:CH334F', 'CH334F', 'Package_DFN_QFN:QFN-24-1EP_4x4mm_P0.5mm_EP2.7x2.7mm_ThermalVias',
              'CH334F', 'C5187527')
# 16,015 / 16,017, Oct 8, 2026; the Green part number; plain AP2171W-7 isn't listed anywhere
AP2171W = Spec('Power_Management:AP2171W', 'AP2171WG-7', 'Package_TO_SOT_SMD:SOT-23-5', 'AP2171WG-7',
               'C110466')
# 3,245 / 3,358, Oct 8, 2026; Diodes DS37274: E (SOT223) is 1 IN, 2 GND, 3 OUT; never the ER
AP7361C_33 = Spec('Regulator_Linear:AP7361C-33E', 'AP7361C-33E-13', 'Package_TO_SOT_SMD:SOT-223-3_TabPin2',
                  'AP7361C-33E-13', 'C500795')
# 34,525 / 35,550, Oct 8, 2026
AP2127K_18 = Spec('Regulator_Linear:AP2127K-1.8', 'AP2127K-1.8TRG1', 'Package_TO_SOT_SMD:SOT-23-5',
                  'AP2127K-1.8TRG1', 'C151375')
# 36,575 / 42,208, Oct 8, 2026
USBLC6 = Spec('Power_Protection:USBLC6-2SC6', 'USBLC6-2SC6', 'Package_TO_SOT_SMD:SOT-23-6', 'USBLC6-2SC6', 'C7519')
# 26,355 / 26,357, Oct 8, 2026; Semtech's own; not fitted on rev A
SRV05_4 = Spec('Power_Protection:SRV05-4', 'SRV05-4', 'Package_TO_SOT_SMD:SOT-23-6', 'SRV05-4.TCT',
               'C13612')
# 562,610 / 563,727, Oct 8, 2026; onsemi
BSS138 = Spec('Transistor_FET:BSS138', 'BSS138', 'Package_TO_SOT_SMD:SOT-23', 'BSS138LT1G', 'C82045')
# 573,320 / 580,677, Oct 8, 2026; MDD, unidirectional: K on VBUS
TVS_5V = Spec('Device:D_Zener', 'SMAJ5.0A', 'Diode_SMD:D_SMA', 'SMAJ5.0A', 'C113952')
# 4.65 M / 6.93 M, Oct 8, 2026; Basic, Vf about 2 V, so it lights through 5.1 k from the hub's 3.3 V
LED_RED = Spec('Device:LED', 'red', 'LED_SMD:LED_0603_1608Metric', 'KT-0603R', 'C2286')

# Magnetics, crystals, protection
# 0 / 0, Oct 8, 2026, and every SMD 78602 too: hand-fit from DigiKey stock (plan 2)
T786J = Spec('liz4270:Murata_78602', '78602/8JC', 'liz4270:Murata_786J', '78602/8JC',
             'C7040198')
# 5 / 529, Oct 8, 2026, none orderable: JLC global sourcing (plan 2)
L_AOTA = Spec('Device:L', '3.3u', 'liz4270:Abracon_AOTA-B201610S3R3-101-T', 'AOTA-B201610S3R3-101-T',
              'C42411119')
# 10,214 / 10,214, Oct 8, 2026
XTAL_12M = Spec('Device:Crystal_GND24', '12MHz', 'Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm', 'ABM8-272-T3',
                'C20625731')
# TDK's 220 ohm at 100 MHz, 3 A, 40 mohm, in place of Murata's BLM21PG221SN1D (C85840: 2 A, 45 mohm), which JLC
# had none of for the reorder. 233,332 at JLC, Nov 22, 2026
FERRITE = Spec('Device:FerriteBead', '220R 3A', 'Inductor_SMD:L_0805_2012Metric', 'MPZ2012S221AT000', 'C76818')
# 7,030 / 7,227, Oct 8, 2026; 7,010 / 7,218, Oct 10, 2026, so kept (plan 2, Task 16); 6 V, 1.5 A hold
PTC = Spec('Device:Polyfuse', '1.5A', 'Fuse:Fuse_1812_4532Metric', 'MF-MSMF150-2', 'C89648')

# Connectors, switches, mechanical
# 396,275 / 414,255, Oct 8, 2026
USB_C = Spec('Connector:USB_C_Receptacle_USB2.0_16P', 'USB-C', 'Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12',
             'TYPE-C-31-M-12', 'C165948')
# 4,079 / 4,079, Oct 8, 2026; through-hole shell pegs
HDMI = Spec('Connector:HDMI_A', 'HDMI', 'Connector_Video:HDMI_A_Molex_208658-1001_Horizontal', '2086581001',
            'C916313')
# Molex 67298-3091 (black, 30 uin gold), in place of Wuerth's 61400826021 (C5366339), which JLC had none of for the
# reorder and priced at $13.80. Wuerth's is a copy of Molex's: SD-67298-008 rev D's recommended layout is KiCad's
# Wuerth footprint to the hundredth (pegs 13.14 by 5.68, 3.07 out from pin 1, 5.33 behind the rear row; pins 2.50,
# 2.00, 2.50 in rows 2.62 apart; the front 10.28 from the front pegs), so the footprint stays. Molex numbers the front
# row, the lower port, 1-4 and the rear 1'-4'; Wuerth numbers the rear 1-4, so each hole keeps its signal. 1.5 A.
# 1,202 at JLC, $1.05, Nov 22, 2026
USB_A_STACKED = Spec('Connector:USB_A_Stacked', 'USB-A x2',
                     'Connector_USB:USB_A_Wuerth_61400826021_Horizontal_Stacked', '67298-3091',
                     'C588409')
# 915 / 915, Oct 8, 2026
BNC = Spec('Connector:Conn_Coaxial', 'BNC', 'Connector_Coaxial:BNC_Amphenol_B6252HB-NPP3G-50_Horizontal',
           'B6252HB-NPP3G-50', 'C22457552')
# The two buttons are one part, the angled PTS645VK392LFS (C285519): the 130 gf PTS645VL31 has none; this is 260 gf,
# with a 3.85 mm actuator. Each has its own Spec so its value names what it does. 6,523 at LCSC, Oct 8, 2026.
# Its metal frame comes down as two legs at the edge, where fingers touch it: the footprint of our own makes them pad
# SH, the shielded symbol's pin, so the frame goes to ground (gate 2).
SW_BOOTSEL = Spec('Switch:SW_Push_Shielded', 'BOOTSEL', 'liz4270:SW_CK_PTS645V_Angled', 'PTS645VK392LFS', 'C285519')
SW_RESET = Spec('Switch:SW_Push_Shielded', 'RESET', 'liz4270:SW_CK_PTS645V_Angled', 'PTS645VK392LFS', 'C285519')
# FG's clone of JST's SM03B-SRSS-TB, which had none (CoffeeMuse, Oct 9, 2026; 15 at LCSC on Oct 10). 8,815 / 8,817,
# Oct 10, 2026; Extended. Its drawing's land pattern is KiCad's footprint to the 0.05 mm it's drawn in: signal pads
# 0.60 x 1.55 at a 1.00 pitch, mounting pads 1.20 x 1.80, 5.55 over both rows, 4.0 from the signal pads' inner end to
# the mounting pads' outer end, 0.70 from a mounting pad to the nearest signal pad's centre. Its housing is SH's, mouth
# over the mounting pads, so the contact on pad 1 is JST's pin 1 and Raspberry Pi's debug cable mates the same way.
# (HDGC1002WR-S-3P failed the check: 2.0 mm mounting pads.)
JST_SH3 = Spec('Connector_Generic:Conn_01x03', 'SWD', 'Connector_JST:JST_SH_SM03B-SRSS-TB_1x03-1MP_P1.00mm_Horizontal',
               '1.0-3PWT', 'C2763613')
# 370,520 / 371,901, Oct 8, 2026
JST_PH2 = Spec('Connector_Generic:Conn_01x02', 'Speaker', 'Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical',
               'B2B-PH-K-S(LF)(SN)', 'C131337')
# BOOMELE's; 21,685 / 22,458, Oct 8, 2026; 21,155 at LCSC, Oct 10, 2026; not fitted on rev A
HEADER_2X7 = Spec('Connector_Generic:Conn_02x07_Odd_Even', 'Bench',
                  'Connector_PinHeader_2.54mm:PinHeader_2x07_P2.54mm_Vertical', '2.54-2*7P', 'C71397')
# Not bought: bare pads and holes in the board itself
TESTPOINT = Spec('Connector:TestPoint', 'TP', 'TestPoint:TestPoint_Pad_D1.5mm', bom=False)
HOLE_PLATED = Spec('Mechanical:MountingHole_Pad', 'M3', 'MountingHole:MountingHole_3.2mm_M3_Pad_Via', bom=False)
HOLE = Spec('Mechanical:MountingHole', 'M3', 'MountingHole:MountingHole_3.2mm_M3', bom=False)

ALL = {name: value for (name, value) in list(globals().items()) if isinstance(value, Spec)}
