// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// Adafruit Fruit Jam (RP2350B). Coax is on header A1-A4 (JP3 pins 25, 23,
// 21, 19). PIO0 belongs to PIO-USB, so coax uses PIO1 and PIO2 with their
// GPIO base at 16. DVI is over HSTX on GPIO 12-19 (video.c). Pin names come
// from the SDK's boards/adafruit_fruit_jam.h.

#ifndef LIZ_BOARDS_FRUIT_JAM_H
#define LIZ_BOARDS_FRUIT_JAM_H

#define LIZ_COAX_RX_PIN        ADAFRUIT_FRUIT_JAM_A1_PIN // 41
#define LIZ_COAX_TX_PIN        ADAFRUIT_FRUIT_JAM_A2_PIN // 42
#define LIZ_COAX_TX_ACTIVE_PIN ADAFRUIT_FRUIT_JAM_A3_PIN // 43
#define LIZ_COAX_TX_DELAY_PIN  ADAFRUIT_FRUIT_JAM_A4_PIN // 44

#define LIZ_COAX_RX_PIO        pio1
#define LIZ_COAX_TX_PIO        pio2
#define LIZ_COAX_PIO_GPIO_BASE 16

// The red LED "L" between the microSD slot and the USB-C jack, on GPIO29.
// Its anode is on 3.3 V, so it lights when the pin is low.
#define LIZ_HEARTBEAT_LED_PIN  29

// USB host (#14): Pico-PIO-USB on PIO0, into the on-board hub's upstream
// port on GPIO 1 (D+) and 2 (D-). GPIO11 high powers the two USB-A ports.
#define LIZ_USB_HOST_DP_PIN    ADAFRUIT_FRUIT_JAM_USB_HOST_DATA_PLUS_PIN  // 1
#define LIZ_USB_HOST_DM_PIN    ADAFRUIT_FRUIT_JAM_USB_HOST_DATA_MINUS_PIN // 2
#define LIZ_USB_HOST_POWER_PIN ADAFRUIT_FRUIT_JAM_USB_HOST_5V_POWER_PIN   // 11

// The TLV320DAC3100's beep generator for the alarm and key click (#18): I2C0
// on GPIO 20 (SDA) and 21 (SCL), with the board's 10 kOhm pull-ups, MCLK from
// clk_gpout3 on GPIO25, and PERIPH_RST on GPIO22, which resets the ESP32-C6
// too. GPIO23 (the DAC's GPIO1, on the ESP32-C6's boot strap) is left alone.
// The bus is also the HDMI port's DDC, through a BSS138 level shifter (Q2),
// so it runs at DDC's 100 kHz. The DAC drives I2S BCLK and WCLK (GPIO26 and
// 27) itself, as the I2S master; the RP2350 leaves them, and I2S DIN (GPIO24), alone.
#define LIZ_AUDIO_I2C          i2c0
#define LIZ_AUDIO_SDA_PIN      PICO_DEFAULT_I2C_SDA_PIN             // 20
#define LIZ_AUDIO_SCL_PIN      PICO_DEFAULT_I2C_SCL_PIN             // 21
#define LIZ_AUDIO_MCLK_PIN     ADAFRUIT_FRUIT_JAM_I2S_MCLK_PIN      // 25
#define LIZ_AUDIO_RESET_PIN    ADAFRUIT_FRUIT_JAM_PERIPH_RESET_PIN  // 22

// Revision A's new pins (#97; the unified board spec, "Pin map"). The Liz4270
// board keeps this map and gives four pins the Fruit Jam build never used new
// jobs, so one UF2 runs on both. GPIO 4 and 5, buttons 2 and 3 on the Fruit
// Jam, carry the board ID (board_detect.c, board_id.h). On revision A, GPIO6
// is the USB-A load switch's open-drain fault flag (R35, 10 kOhm, pulls it
// up) and GPIO7 is HDMI hot-plug detect (220 Ohm in, 4.7 kOhm to ground). On
// the Fruit Jam those two are bare header pins, D6 and D7, so nothing reads
// them there. Nothing drives any of the four.
#define LIZ_BOARD_ID1_PIN      ADAFRUIT_FRUIT_JAM_BUTTON2_PIN  // 4, the ID's first digit
#define LIZ_BOARD_ID2_PIN      ADAFRUIT_FRUIT_JAM_BUTTON3_PIN  // 5, and its second
#define LIZ_USB_HOST_FAULT_PIN ADAFRUIT_FRUIT_JAM_D6_PIN       // 6
#define LIZ_HPD_PIN            ADAFRUIT_FRUIT_JAM_D7_PIN       // 7

#endif
