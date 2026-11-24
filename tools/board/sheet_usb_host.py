# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The USB host sheet: a current-limited switch on GPIO11, the CH334F hub wired as on the Fruit Jam (the
firmware's hub handling was proven on it, #14), and a stacked dual USB-A with ESD on each port (spec, "USB host").

The circuit is drawn: the switch at the top left, its output a rail along the top to the hub's V5 and the ports'
VBUS, so the hub is plainly on the switched side. The hub sits in the middle with its upstream port, status LEDs
and crystal on the left. Its two downstream ports run right, turn up and come back left into J5, through a USBLC6
each. The U-turn is what lets J5 and both ESD chips stand upright with no crossing. U10's VBUS is a label, not a
wire: a USBLC6's VBUS is on its DP side, and port 2's DP faces port 1, so from between the two pairs no wire
reaches the rail without crossing one."""

import parts as P


def build(project):
    s = project.sheet('usb_host.kicad_sch', 'USB host', 'USB host: switch, hub, stacked USB-A')

    d = s.drawing('Port power, held off through reset (RP2350-E9); CH334F as on the Fruit Jam; USB-A pair with ESD')

    # The hub, at the origin
    d.add(P.CH334F, 'U8', {
        'V5': 'USBH_5V', 'VDD33_{LDO}': 'HUB_V33', 'GND': 'GND', 'XI': 'HUB_XI', 'XO': 'HUB_XO',
        'DPU+': 'USBH_DP', 'DMU-': 'USBH_DM', 'DP1+': 'USBA1_DP', 'DM1-': 'USBA1_DM',
        'DP2+': 'USBA2_DP', 'DM2-': 'USBA2_DM', 'LED2': 'HUB_LED2', 'LED4/SDA': 'HUB_LED4'},
        nc=['~{OVCUR}', 'NC', 'DP3+', 'DM3-', 'DP4+', 'DM4-', 'LED3/SCL', '~{RESET}/CDP', 'PSELF', 'LED1', '~{PWREN}'],
        at=(0, 0))
    d.wire('U8.15', (-15.24, -15.24), (-15.24, -17.78), (-22.86, -17.78))      # D+ steps up, so the labels clear
    d.label('USBH_DP', (-22.86, -17.78), 'left')
    d.wire('U8.14', (-22.86, -12.7))
    d.label('USBH_DM', (-22.86, -12.7), 'left')

    # Port power: AP2171W, about 1 A, on while GPIO11 is high; R34 holds it off through reset (RP2350-E9)
    d.add(P.AP2171W, 'U7', {'IN': '+5V', 'GND': 'GND', 'EN': 'USBH_EN', '~{FLG}': 'USBH_FAULT', 'OUT': 'USBH_5V'},
          at=(-68.58, -33.02))
    d.add(P.C10U, 'C32', {'1': '+5V', '2': 'GND'}, at=(-91.44, -31.75))     # application circuit: 10 uF at IN
    d.add(P.R4K7, 'R34', {'1': 'USBH_EN', '2': 'GND'}, at=(-86.36, -13.97))
    d.add(P.R10K, 'R35', {'1': '+3V3', '2': 'USBH_FAULT'}, at=(-50.8, -34.29))
    d.add(P.C100U, 'C37', {'1': 'USBH_5V', '2': 'GND'}, at=(-40.64, -49.53))
    d.add(P.C100U, 'C38', {'1': 'USBH_5V', '2': 'GND'}, at=(-27.94, -49.53))
    d.wire('U7.5', 'C32.1', (-99.06, -35.56))
    d.label('+5V', (-99.06, -35.56), 'up')
    d.wire('U7.4', (-81.28, -30.48), (-81.28, -17.78), 'R34.1', (-106.68, -17.78))
    d.label('USBH_EN', (-106.68, -17.78), 'left')
    d.wire('U7.3', 'R35.2', (-40.64, -30.48))
    d.label('USBH_FAULT', (-40.64, -30.48), 'right')

    # The switched rail, USBH_5V: the bulk capacitors, the hub's V5, and both ports' VBUS
    d.wire('U7.1', (-55.88, -35.56), (-55.88, -53.34), 'C37.1', 'C38.1', (2.54, -53.34), (43.18, -53.34))
    d.wire('U8.19', (2.54, -53.34))
    d.label('USBH_5V', (7.62, -53.34), 'right')

    # Status LEDs for ports 1 and 2: WCH's pair on LED2 and LED4 (CH334 datasheet, Figure 3-3-3), not a strap. With no
    # EEPROM and PSELF open, the hub keeps WCH's defaults and reports itself self-powered.
    # The three HUB_LED nets stay on this little loop. The wires show them, so they carry no label and KiCad names
    # them; the writer still checks every wire against them.
    d.add(P.R5K1, 'R36', {'1': 'HUB_LED2', '2': 'HUB_LEDM'}, rot=270, at=(-20.32, -2.54))
    d.add(P.LED_RED, 'D3', {'A': 'HUB_LED4', 'K': 'HUB_LEDM'}, rot=90, at=(-38.1, -3.81))
    d.add(P.LED_RED, 'D2', {'A': 'HUB_LEDM', 'K': 'HUB_LED4'}, rot=270, at=(-50.8, -3.81))
    d.wire('U8.23', 'R36.1')
    d.wire('U8.21', 'D3.2', 'D2.1')
    # The lower wire runs a step below the LEDs' ends, clear of D3's light arrows
    d.wire('R36.2', (-26.67, -2.54), (-26.67, 2.54), (-50.8, 2.54), 'D2.2')
    d.wire('D3.1', (-38.1, 2.54))

    # The crystal, above its two wires, with its ground between them
    d.add(P.XTAL_12M, 'Y2', {'1': 'HUB_XI', '3': 'HUB_XO', '2': 'GND', '4': 'GND'}, at=(-33.02, 15.24))
    d.wire('U8.3', (-26.67, 17.78), (-26.67, 15.24), 'Y2.3')
    d.label('HUB_XO', (-15.24, 17.78), 'left')
    d.wire('U8.4', (-15.24, 22.86), (-15.24, 30.48), (-39.37, 30.48), (-39.37, 15.24), 'Y2.1')
    d.label('HUB_XI', (-17.78, 30.48), 'left')

    # The ports. Each line passes through its USBLC6, so its two sides are separate wires that carry its name.
    d.add(P.USB_A_STACKED, 'J5', {'VBUS1': 'USBH_5V', 'D1-': 'USBA1_DM', 'D1+': 'USBA1_DP', 'GND1': 'GND',
                                  'VBUS2': 'USBH_5V', 'D2-': 'USBA2_DM', 'D2+': 'USBA2_DP', 'GND2': 'GND',
                                  'Shield': 'GND'}, at=(30.48, -30.48))
    d.add(P.USBLC6, 'U9', {'I/O1': 'USBA1_DP', 'I/O2': 'USBA1_DM', 'GND': 'GND', 'VBUS': 'USBH_5V'},
          at=(91.44, -33.02))
    d.add(P.USBLC6, 'U10', {'I/O1': 'USBA2_DP', 'I/O2': 'USBA2_DM', 'GND': 'GND', 'VBUS': 'USBH_5V'},
          at=(71.12, -17.78))
    # From the hub: right, up, and back left into the ESD chips
    d.wire('U8.9', (81.28, 2.54), (81.28, -15.24), 'U10.4')
    d.wire('U8.10', (83.82, 5.08), (83.82, -17.78), 'U10.6')
    d.wire('U8.11', (101.6, 10.16), (101.6, -30.48), 'U9.4')
    d.wire('U8.12', (104.14, 12.7), (104.14, -33.02), 'U9.6')
    d.label('USBA2_DM', (15.24, 2.54), 'right')
    d.label('USBA2_DP', (20.32, 5.08), 'right')
    d.label('USBA1_DM', (15.24, 10.16), 'right')
    d.label('USBA1_DP', (20.32, 12.7), 'right')
    # From the ESD chips to J5; port 2's pair steps up to its pins
    d.wire('J5.3', 'U9.1')
    d.wire('J5.2', 'U9.3')
    d.wire('J5.7', (45.72, -27.94), (45.72, -17.78), 'U10.1')
    d.wire('J5.6', (43.18, -25.4), (43.18, -15.24), 'U10.3')
    d.label('USBA1_DP', (43.18, -33.02), 'right')
    d.label('USBA1_DM', (48.26, -30.48), 'right')
    d.label('USBA2_DP', (48.26, -17.78), 'right')
    d.label('USBA2_DM', (53.34, -15.24), 'right')
    # VBUS: both of J5's up to the rail, and U9's on the way; U10's is a label (see above)
    d.wire('J5.5', (43.18, -38.1), 'U9.5')
    d.wire((43.18, -38.1), (43.18, -53.34))
    d.wire('J5.1', (43.18, -40.64))
    d.wire('U10.5', (71.12, -25.4), (76.2, -25.4))
    d.label('USBH_5V', (76.2, -25.4), 'right')
    # J5's grounds, joined
    d.wire('J5.SH', (27.94, -12.7), (30.48, -12.7), (33.02, -12.7), 'J5.8')
    d.wire('J5.4', (30.48, -10.16))
    d.label('GND', (30.48, -10.16), 'down')

    g = s.group("Decoupling at U8: V5, and its 3.3 V regulator's output")
    g.add(P.C10U, 'C33', {'1': 'HUB_V33', '2': 'GND'})
    g.add(P.C1U, 'C34', {'1': 'HUB_V33', '2': 'GND'})
    g.add(P.C10U, 'C35', {'1': 'USBH_5V', '2': 'GND'})
    g.add(P.C100N, 'C36', {'1': 'USBH_5V', '2': 'GND'})
