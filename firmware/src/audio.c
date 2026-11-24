// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// The alarm and the key click on the Fruit Jam (#18). See audio.h. The
// register numbers and values are TI SLAS671C's.

#include <assert.h>

#include "pico/binary_info.h"
#include "pico/stdlib.h"
#include "hardware/clocks.h"
#include "hardware/i2c.h"

#include "audio.h"
#include "board.h"
#include "setup.h"
#include "usb_host.h"
#include "video.h"

static_assert((uint64_t)BEEP_HZ * 4u < BEEP_FS, "the beep generator needs the tone below fs / 4");

#define DAC_ADDR 0x18u         // 001 1000 (6.3.1)
#define I2C_HZ 100000u         // standard mode: the bus is also the HDMI port's DDC (fruit_jam.h)
#define I2C_TIMEOUT_US 5000u   // a transfer, the IRQs that preempt it included: five bytes take about 0.5 ms
#define RESET_LOW_MS 1u        // the datasheet asks for 10 ns
#define RESET_SETTLE_MS 2u     // it initialises within 1 ms of !RESET rising (6.3.3)
#define BUS_CLEAR_CLOCKS 9u    // a bus clear's most clocks: one byte and its acknowledge
#define BUS_CLEAR_HALF_US 5u   // half a clock at 100 kHz
#define REST_MS 1000u          // after a sound fails, the loop starts no other for this long
#define LENGTH_UNSURE UINT32_MAX  // not a length registers 73-75 can hold

#define REG_PAGE 0x00u
#define REG_NDAC 0x0Bu         // page 0 register 11
#define REG_POWER 0x25u        // page 0 register 37: the DAC and driver power flags
#define REG_BEEP 0x47u         // page 0 register 71: start, and the left channel's level
#define REG_BEEP_LENGTH 0x49u  // page 0 registers 73-75
#define REG_BEEP_SIN 0x4Cu     // page 0 registers 76-79: sin, then cos
#define NDAC_ON 0x81u          // NDAC = 1, powered up
#define NDAC_OFF 0x01u
#define BEEP_GO 0x80u
#define POWER_MASK 0xBBu       // register 37's documented bits

bi_decl(bi_2pins_with_func(LIZ_AUDIO_SDA_PIN, LIZ_AUDIO_SCL_PIN, GPIO_FUNC_I2C));
bi_decl(bi_1pin_with_name(LIZ_AUDIO_MCLK_PIN, "DAC MCLK (12 MHz)"));
bi_decl(bi_1pin_with_name(LIZ_AUDIO_RESET_PIN, "DAC and ESP32-C6 reset"));

// Each step: its length, then that many bytes: a register, then what goes in
// it and in the ones after it (the DAC steps the register on through a
// transfer). The clocks: CODEC_CLKIN = MCLK = 12 MHz, NDAC 1, MDAC 3 and
// DOSR 128, so fs = 31.25 kHz (BEEP_FS), and PRB_P25's MDAC x DOSR / 32 = 12.
// The DAC is the I2S master, driving BCLK and WCLK itself (GPIO26 and 27,
// which the RP2350 leaves alone): as a slave with no bit clock coming, its
// processing never runs, so no beep ever starts or ends (#18's bench).
static const uint8_t setup_clocks[] = {
    2, REG_PAGE, 0x00,    // page 0
    2, 0x04, 0x00,        // CODEC_CLKIN = MCLK, PLL unused
    2, REG_NDAC, NDAC_ON, // NDAC = 1, powered
    2, 0x0C, 0x83,        // MDAC = 3, powered
    3, 0x0D, 0x00, 0x80,  // DOSR = 128: register 14 straight after 13
    2, 0x1E, 0x8C,        // BCLK = DAC_CLK / 12 = 1 MHz, 32 bits a frame at fs; powered
    2, 0x1B, 0x0C,        // BCLK and WCLK outputs: the DAC as I2S master
    2, 0x3C, 0x19,        // PRB_P25, the block with the beep generator
    2, 0x48, 0x80,        // the right channel's beep level follows the left's
};

// The outputs, at the values Adafruit's CircuitPython driver gives the Fruit
// Jam (NOTICE), then the DACs on with the play data muted: the beep mixes in
// after the mute (6.3.10.7).
static const uint8_t setup_outputs[] = {
    2, REG_PAGE, 0x01,    // page 1
    2, 0x1F, 0x14,        // headphone common mode 1.65 V, drivers still off
    2, 0x23, 0x44,        // DAC_L and DAC_R through the mixers
    3, 0x24, 0xA8, 0xA8,  // HPL and HPR analog volume -20.1 dB, routed
    2, 0x26, 0x94,        // speaker analog volume -10 dB, routed
    3, 0x28, 0x36, 0x36,  // HPL and HPR drivers +6 dB, unmuted
    2, 0x2A, 0x0C,        // class-D +12 dB, unmuted
    2, 0x1F, 0xD4,        // HPL and HPR on
    2, 0x20, 0x86,        // class-D on
    2, REG_PAGE, 0x00,    // page 0, where it stays
    2, 0x3F, 0xD4,        // both DACs on, normal data paths, soft-stepping
    2, 0x40, 0x0C,        // the play data muted
};

static const term_t *term;
static beep_t beep;
static bool dac_ok;
static bool on_page0;  // the DAC is on register page 0, where sounds and b's read work
static uint32_t length_set = LENGTH_UNSURE;  // registers 73-75 as last written
static bool resting;   // a sound failed: audio_poll starts none until rest_end
static uint32_t rest_end;
static bool level_set;  // b level's override (#107): every sound at level_db until power-off or b level off
static int level_db;
static uint32_t errors, alarms, clicks, flashes;
static uint32_t previews_seen;  // setup_previews when last polled (#107)
static uint32_t power_ons_seen;  // setup_power_ons when last polled (#110)

static uint32_t now_ms(void) {
    return to_ms_since_boot(get_absolute_time());
}

static void start_i2c(void) {
    i2c_init(LIZ_AUDIO_I2C, I2C_HZ);
    gpio_set_function(LIZ_AUDIO_SDA_PIN, GPIO_FUNC_I2C);
    gpio_set_function(LIZ_AUDIO_SCL_PIN, GPIO_FUNC_I2C);
}

// After a failed transfer the DAC may be part-way through a byte it was
// sending, holding SDA low, and nothing but a reset would free it. So: the
// bus clear I2C defines (UM10204 3.1.16), up to nine clocks on SCL until SDA
// goes high, then a STOP; and the controller restarts, in case a timeout
// left it part-way through a transfer. The pins are driven low or let go,
// never driven high: the board's pull-ups make the highs.
static void bus_clear(void) {
    i2c_deinit(LIZ_AUDIO_I2C);
    gpio_init(LIZ_AUDIO_SDA_PIN);  // inputs, with their output latches at 0
    gpio_init(LIZ_AUDIO_SCL_PIN);
    for (unsigned i = 0; i < BUS_CLEAR_CLOCKS && !gpio_get(LIZ_AUDIO_SDA_PIN); i++) {
        gpio_set_dir(LIZ_AUDIO_SCL_PIN, GPIO_OUT);
        sleep_us(BUS_CLEAR_HALF_US);
        gpio_set_dir(LIZ_AUDIO_SCL_PIN, GPIO_IN);
        sleep_us(BUS_CLEAR_HALF_US);
    }
    // STOP: SDA down while SCL is low, then up while SCL is high.
    gpio_set_dir(LIZ_AUDIO_SCL_PIN, GPIO_OUT);
    sleep_us(BUS_CLEAR_HALF_US);
    gpio_set_dir(LIZ_AUDIO_SDA_PIN, GPIO_OUT);
    sleep_us(BUS_CLEAR_HALF_US);
    gpio_set_dir(LIZ_AUDIO_SCL_PIN, GPIO_IN);
    sleep_us(BUS_CLEAR_HALF_US);
    gpio_set_dir(LIZ_AUDIO_SDA_PIN, GPIO_IN);
    sleep_us(BUS_CLEAR_HALF_US);
    start_i2c();
}

static void failed(void) {
    errors++;
    bus_clear();
}

static bool write_bytes(const uint8_t *bytes, size_t len) {
    if (i2c_write_timeout_us(LIZ_AUDIO_I2C, DAC_ADDR, bytes, len, false, I2C_TIMEOUT_US) == (int)len)
        return true;
    failed();
    return false;
}

// One register on the page selected, into *value.
static bool read_byte(uint8_t reg, uint8_t *value) {
    if (i2c_write_timeout_us(LIZ_AUDIO_I2C, DAC_ADDR, &reg, 1, true, I2C_TIMEOUT_US) == 1
        && i2c_read_timeout_us(LIZ_AUDIO_I2C, DAC_ADDR, value, 1, false, I2C_TIMEOUT_US) == 1)
        return true;
    failed();
    return false;
}

// A table of steps, in order, stopping at the first that fails.
static bool write_steps(const uint8_t *steps, size_t size) {
    for (size_t at = 0; at < size; at += 1u + steps[at])
        if (!write_bytes(&steps[at + 1u], steps[at]))
            return false;
    return true;
}

// b reg's way to another page, and every way back to page 0.
static bool select_page(uint8_t page) {
    const uint8_t bytes[] = {REG_PAGE, page};
    bool ok = write_bytes(bytes, sizeof bytes);
    on_page0 = ok && page == 0u;
    return ok;
}

// Page 0 again if b reg left the DAC elsewhere: its way back failed.
static bool to_page0(void) {
    return on_page0 || select_page(0);
}

// Registers 73-75, unless they already hold n.
static bool write_length(uint32_t n) {
    if (n == length_set)
        return true;
    const uint8_t bytes[] = {REG_BEEP_LENGTH, (uint8_t)(n >> 16), (uint8_t)(n >> 8), (uint8_t)n};
    length_set = write_bytes(bytes, sizeof bytes) ? n : LENGTH_UNSURE;
    return length_set == n;
}

static bool write_tone(void) {
    beep_tone_t tone;
    beep_tone(BEEP_HZ, BEEP_FS, &tone);  // it can't refuse: see the static_assert
    const uint8_t bytes[] = {REG_BEEP_SIN, (uint8_t)(tone.sin >> 8), (uint8_t)tone.sin,
                             (uint8_t)(tone.cos >> 8), (uint8_t)tone.cos};
    return write_bytes(bytes, sizeof bytes);
}

static audio_result_t try_sound(beep_sound_t s, int db);

void audio_init(const term_t *t) {
    term = t;
    beep_init(&beep, term_alarms(t) + setup_alarms(), usb_host_keys(), usb_host_local_keystrokes());
    previews_seen = setup_previews();
    power_ons_seen = setup_power_ons();

    clock_gpio_init(LIZ_AUDIO_MCLK_PIN, CLOCKS_CLK_GPOUT3_CTRL_AUXSRC_VALUE_XOSC_CLKSRC, 1);
    // PERIPH_RST low, then let go: R7 and R13 pull it up, as at power-on, so
    // nothing else on the net (the ESP32-C6's EN, JP3 pin 24) ever meets a
    // driven high. gpio_init leaves the output latch at 0, so the pin goes
    // straight low.
    gpio_init(LIZ_AUDIO_RESET_PIN);
    gpio_disable_pulls(LIZ_AUDIO_RESET_PIN);
    gpio_set_dir(LIZ_AUDIO_RESET_PIN, GPIO_OUT);
    sleep_ms(RESET_LOW_MS);
    gpio_set_dir(LIZ_AUDIO_RESET_PIN, GPIO_IN);
    sleep_ms(RESET_SETTLE_MS);

    // The board's 10 kOhm pull-ups alone: the pads' reset pull-downs would
    // hold a high near 2.75 V.
    gpio_disable_pulls(LIZ_AUDIO_SDA_PIN);
    gpio_disable_pulls(LIZ_AUDIO_SCL_PIN);
    start_i2c();

    // A DAC that doesn't answer fails the first write, and nothing more is sent.
    dac_ok = write_steps(setup_clocks, sizeof setup_clocks) && write_tone()
             && write_steps(setup_outputs, sizeof setup_outputs);
    on_page0 = dac_ok;  // setup_outputs ends on page 0

    // The alarm, as the 3483-V sounds it at power-on whatever Alarm volume
    // says: at its level, or BEEP_POWER_ON_VOLUME's at Off (#107).
    if (dac_ok) {
        beep_start(&beep, now_ms(), BEEP_ALARM);
        try_sound(BEEP_ALARM, beep_volume_db(beep_power_on_volume(setup_settings())));
    }
}

static audio_result_t sound(beep_sound_t s, int db) {
    if (!dac_ok)
        return AUDIO_MISSING;
    if (!to_page0())
        return AUDIO_FAILED;
    uint8_t level = beep_level_code(level_set ? level_db : db);
    const uint8_t stop[] = {REG_BEEP, level};
    const uint8_t off[] = {REG_NDAC, NDAC_OFF};
    const uint8_t go[] = {REG_BEEP, (uint8_t)(BEEP_GO | level)};
    const uint8_t on[] = {REG_NDAC, NDAC_ON};
    // The datasheet's way to start a beep: NDAC down, start it, NDAC up
    // (6.3.10.7). First, any beep still sounding is stopped: one started over
    // it never ends, and its tone plays on (#18's bench).
    bool ok = write_bytes(stop, sizeof stop) && write_bytes(off, sizeof off)
              && write_length(beep_samples(beep_length(&beep, s), BEEP_FS)) && write_bytes(go, sizeof go);
    ok = write_bytes(on, sizeof on) && ok;  // NDAC back up, whatever else happened
    if (!ok)
        return AUDIO_FAILED;
    if (s == BEEP_ALARM)
        alarms++;
    else
        clicks++;
    return AUDIO_OK;
}

// A sound beep_poll or b started, or, if the DAC failed, nothing sounding.
static audio_result_t try_sound(beep_sound_t s, int db) {
    audio_result_t result = sound(s, db);
    if (result != AUDIO_OK)
        beep_cancel(&beep);
    return result;
}

// Stops any beep still sounding: a preview of Off mustn't leave the last
// level's alarm playing under its flash (#107). A sound needs none: sound()
// stops the last beep itself.
static void silence(void) {
    const uint8_t stop[] = {REG_BEEP, beep_level_code(BEEP_LEVEL_MIN_DB)};
    if (dac_ok && !resting && to_page0())
        write_bytes(stop, sizeof stop);
}

static void flash(void) {
    video_flash(beep_length(&beep, BEEP_FLASH));
    flashes++;
}

void audio_poll(void) {
    uint32_t ms = now_ms();
    if (resting && (int32_t)(ms - rest_end) >= 0)
        resting = false;
    // Alarm volume's preview (#107) cuts the alarm or flash before it, the
    // screen's flash included, so each Space is heard however quick the next.
    uint32_t p = setup_previews();
    bool preview = p != previews_seen;
    if (preview) {
        previews_seen = p;
        beep_preview(&beep);
        video_flash(0u);
    }
    // A model change's power-on reset (#110): the power-on alarm, as at boot,
    // at its level whatever Alarm volume says.
    uint32_t power_ons = setup_power_ons();
    if (power_ons != power_ons_seen) {
        power_ons_seen = power_ons;
        beep_start(&beep, ms, BEEP_ALARM);
        if (!resting)
            try_sound(BEEP_ALARM, beep_volume_db(beep_power_on_volume(setup_settings())));
        return;
    }
    // SetUp's alarms (#102) sound as the host's do; its keystrokes click whatever Click says (#107).
    const settings_t *set = setup_settings();
    beep_sound_t s = beep_poll(&beep, ms, term_alarms(term) + setup_alarms(), usb_host_keys(),
                               usb_host_local_keystrokes(), term_clicker(term), set);
    if (s == BEEP_NONE)
        return;
    if (s == BEEP_FLASH) {
        if (preview)
            silence();
        flash();
        return;
    }
    // A bus that fails each transfer, after its timeout, would hold the loop
    // up for every keystroke: after a failure, one try a second at most.
    if (resting) {
        beep_cancel(&beep);
    } else if (try_sound(s, beep_sound_db(s, set)) == AUDIO_FAILED) {
        resting = true;
        rest_end = ms + REST_MS;
    }
}

bool audio_dac_ok(void) {
    return dac_ok;
}

void audio_stats(audio_stats_t *out) {
    int power = -1;
    uint8_t value = 0;
    if (dac_ok && to_page0() && read_byte(REG_POWER, &value))
        power = value & POWER_MASK;
    *out = (audio_stats_t){
        .dac_ok = dac_ok,
        .errors = errors,
        .alarms = alarms,
        .clicks = clicks,
        .swallowed = beep_swallowed(&beep),
        .flashes = flashes,
        .level_set = level_set,
        .level_db = level_db,
        .click_ms = beep_length(&beep, BEEP_CLICK),
        .alarm_ms = beep_length(&beep, BEEP_ALARM),
        .flash_ms = beep_length(&beep, BEEP_FLASH),
        .power = power,
    };
}

audio_result_t audio_sound(beep_sound_t s) {
    // As beep_poll has them (#107): a click at Click Volume Off is silent,
    // and nothing for beep_poll to see; the alarm at Alarm volume Off flashes.
    const settings_t *set = setup_settings();
    s = beep_resolve(s, set);
    if (s == BEEP_NONE)
        return AUDIO_OK;
    beep_start(&beep, now_ms(), s);
    if (s == BEEP_FLASH) {
        flash();
        return AUDIO_OK;
    }
    audio_result_t result = try_sound(s, beep_sound_db(s, set));
    if (result == AUDIO_OK)
        resting = false;
    return result;
}

void audio_set_length(beep_sound_t s, uint32_t ms) {
    beep_set_length(&beep, s, ms);
}

void audio_set_level(int db) {
    level_set = true;
    level_db = db;
}

void audio_level_off(void) {
    level_set = false;
}

int audio_reg_read(uint8_t page, uint8_t reg) {
    if (!dac_ok || !select_page(page))
        return -1;
    uint8_t value = 0;
    bool ok = read_byte(reg, &value);
    ok = select_page(0) && ok;
    return ok ? value : -1;
}

bool audio_reg_write(uint8_t page, uint8_t reg, uint8_t value) {
    const uint8_t bytes[] = {reg, value};
    if (!dac_ok || !select_page(page))
        return false;
    length_set = LENGTH_UNSURE;  // it may be one of them
    bool ok = write_bytes(bytes, sizeof bytes);
    return select_page(0) && ok;
}
