// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// Liz4270 firmware: an IBM 3483-V on the coax.
//
// Core 1 runs the coax link (coax_link.c): recv_term's words into the
// terminal core, its answers out through xmit_serial. Core 0 holds the line
// driver off from reset, reports the build over USB serial each time a host
// opens the port, and blinks a heartbeat LED. It also draws the screen over
// DVI (video.c), runs the USB host for the keyboard (usb_host.c), and sounds
// the alarm and the key click through the DAC (audio.c).

#include <stdio.h>

#include "pico/stdlib.h"
#include "pico/stdio_usb.h"
#include "pico/binary_info.h"
#include "pico/multicore.h"
#include "hardware/clocks.h"
#include "hardware/pio.h"
#include "tusb.h"

#include "board.h"
#include "board_detect.h"
#include "clocks.h"
#include "coax.pio.h"
#include "coax_link.h"
#include "coax_term.pio.h"
#include "console.h"
#include "term.h"
#include "setup.h"
#include "video.h"
#include "usb_host.h"
#include "audio.h"
#include "version.h"

#define HEARTBEAT_MS 500

bi_decl(bi_4pins_with_names(LIZ_COAX_RX_PIN, "coax RX",
                            LIZ_COAX_TX_PIN, "coax TX",
                            LIZ_COAX_TX_ACTIVE_PIN, "coax TX_ACTIVE",
                            LIZ_COAX_TX_DELAY_PIN, "coax TX_DELAY"));
bi_decl(bi_1pin_with_name(LIZ_HEARTBEAT_LED_PIN, "heartbeat LED"));

static term_t term;  // the terminal core; core 1 owns it once it starts

// TX_ACTIVE enables the line driver. Drive it low, with TX and TX_DELAY,
// before anything else: the Liz 4174 has no pull-down on it. gpio_init
// leaves each pin an input with its output latch at 0, so enabling the
// output can't glitch it high.
static void coax_pins_safe(void) {
    static const uint outputs[] = {
        LIZ_COAX_TX_ACTIVE_PIN, LIZ_COAX_TX_PIN, LIZ_COAX_TX_DELAY_PIN,
    };
    for (size_t i = 0; i < count_of(outputs); i++) {
        gpio_init(outputs[i]);
        gpio_set_dir(outputs[i], GPIO_OUT);
    }
    gpio_init(LIZ_COAX_RX_PIN);
}

// Set on each rising DTR, which is each time a host opens the serial port.
// A poll of stdio_usb_connected() would miss a close and reopen that falls
// between two polls.
static volatile bool banner_due;

// TinyUSB calls this from the SDK's USB background task on every change.
void tud_cdc_line_state_cb(uint8_t itf, bool dtr, bool rts) {
    static bool dtr_was;

    (void)itf;
    (void)rts;
    if (dtr && !dtr_was)
        banner_due = true;
    dtr_was = dtr;
}

static void print_banner(void) {
    uint32_t sys_hz = clock_get_hz(clk_sys);

    printf("\nLiz4270 %s\n", liz_version);
    printf("commit    %s\n", liz_commit);
    char board[64];
    board_describe(board, sizeof board, ", PICO_BOARD " LIZ_PICO_BOARD);
    printf("board     %s\n", board);
    printf("clk_sys   %lu Hz\n", (unsigned long)sys_hz);
    printf("clk_usb   %lu Hz (pll_sys / 3)\n", (unsigned long)clock_get_hz(clk_usb));
    printf("coax      RX %d, TX %d, TX_ACTIVE %d, TX_DELAY %d\n",
           LIZ_COAX_RX_PIN, LIZ_COAX_TX_PIN, LIZ_COAX_TX_ACTIVE_PIN, LIZ_COAX_TX_DELAY_PIN);
    printf("pio       RX on PIO%u, TX on PIO%u, GPIO base %d\n",
           pio_get_index(LIZ_COAX_RX_PIO), pio_get_index(LIZ_COAX_TX_PIO), LIZ_COAX_PIO_GPIO_BASE);
    printf("programs  recv_term %u, xmit_serial %u, xmit_serial_delay %u instructions\n",
           recv_term_program.length, xmit_serial_program.length, xmit_serial_delay_program.length);
    printf("divider   %.4f (clk_sys / %d)\n", (double)sys_hz / COAX_PIO_FREQ, COAX_PIO_FREQ);
    printf("link      core 1, answer guard %u us, EAB %s\n", COAX_TURNAROUND_US,
           coax_link_eab() ? "on" : "off");
    video_stats_t video;
    video_stats(&video);
    printf("video     %s, clk_hstx %lu kHz from pll_usb\n", video.mode, (unsigned long)video.clk_hstx_khz);
    usb_host_stats_t usb;
    usb_host_stats(&usb);
    printf("usb       host on PIO0 (D+ GPIO%d, D- GPIO%d), DMA %u, frame timer alarm %u, ports powered (GPIO%d)\n",
           LIZ_USB_HOST_DP_PIN, LIZ_USB_HOST_DM_PIN, usb.dma_channel, usb.alarm, LIZ_USB_HOST_POWER_PIN);
    printf("audio     TLV320DAC3100 on I2C0 (SDA %d, SCL %d), MCLK 12 MHz on GPIO%d, %u Hz at %u Hz, DAC %s\n",
           LIZ_AUDIO_SDA_PIN, LIZ_AUDIO_SCL_PIN, LIZ_AUDIO_MCLK_PIN, BEEP_HZ, BEEP_FS,
           audio_dac_ok() ? "ok" : "missing");
    puts("console   s | k CODE | r [eab|base] | d | v [640|720|dim|stall|rule|hold MS]"
         " | set [save|defaults|NAME VALUE] | u [clear|log]"
         " | b [click [MS]|alarm [MS]|flash [MS]|level DB|level off|reg PPRR[=VV]] | setup [key NAME]");
}

int main(void) {
    coax_pins_safe();
    clocks_init_liz();  // before USB starts: pll_usb is the video clock's (#26)
    board_detect();     // before the USB host and the video, which ask which board it is (#97)

    usb_host_init(&term);  // before stdio: USB serial expects TinyUSB running (#14)
    stdio_init_all();
    gpio_init(LIZ_HEARTBEAT_LED_PIN);
    gpio_set_dir(LIZ_HEARTBEAT_LED_PIN, GPIO_OUT);

    // EAB at feature address 7 from power-on, as the 3483-V reports it (#70);
    // the console's r base turns it off until the next power-on. The model is
    // the one flash's record holds (#110).
    const term_config_t config = {.eab = true, .model = setup_saved_model()};
    coax_link_init(&term, &config);
    multicore_launch_core1(coax_link_run);
    setup_init(&term);  // after the USB host: the ruler counts its Rule presses (#51)
    video_init(&term, VIDEO_640X480);
    audio_init(&term);  // after the USB host: the clicker counts its keystrokes

    absolute_time_t next_beat = make_timeout_time_ms(HEARTBEAT_MS);
    absolute_time_t banner_at = nil_time;
    for (;;) {
        // Hosts can drop what arrives just after they raise DTR (pyserial
        // flushes its input as it opens the port), so wait as the SDK does.
        // The loop keeps running meanwhile: it is what runs tud_task, and the
        // host's open only completes while it does (#14).
        if (banner_due) {
            banner_due = false;
            banner_at = make_timeout_time_ms(PICO_STDIO_USB_POST_CONNECT_WAIT_DELAY_MS);
        }
        if (!is_nil_time(banner_at) && time_reached(banner_at)) {
            banner_at = nil_time;
            print_banner();
        }

        tud_task();  // linking the host stack stops the SDK running this itself
        usb_host_poll();
        // SetUp (#102) takes the keys usb_host_poll just translated, so a key
        // it sounds the alarm for is counted before audio_poll sees the key's
        // click: the alarm sounds and the click is swallowed (beep.h).
        setup_poll();
        audio_poll();
        console_poll(&term);

        if (time_reached(next_beat)) {
            gpio_put(LIZ_HEARTBEAT_LED_PIN, !gpio_get_out_level(LIZ_HEARTBEAT_LED_PIN));
            next_beat = delayed_by_ms(next_beat, HEARTBEAT_MS);
        }
        video_poll();
        sleep_ms(1);
    }
}
