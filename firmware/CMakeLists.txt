# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

cmake_minimum_required(VERSION 3.25)

# Both boards share the pin map from the SDK's adafruit_fruit_jam definition.
# CMakePresets.json sets PICO_BOARD.
if(NOT PICO_BOARD STREQUAL "adafruit_fruit_jam")
    message(FATAL_ERROR
        "PICO_BOARD is '${PICO_BOARD}'. Liz4270 builds for adafruit_fruit_jam.\n"
        "Configure with the preset from firmware/: cmake --preset liz4270")
endif()

# The SDK is the submodule beside this file, unless PICO_SDK_PATH points elsewhere.
if(DEFINED PICO_SDK_PATH)
    set(LIZ_SDK_DIR ${PICO_SDK_PATH})
elseif(DEFINED ENV{PICO_SDK_PATH})
    set(LIZ_SDK_DIR $ENV{PICO_SDK_PATH})
else()
    set(PICO_SDK_PATH ${CMAKE_CURRENT_LIST_DIR}/pico-sdk)
    set(LIZ_SDK_DIR ${PICO_SDK_PATH})
endif()
if(NOT EXISTS ${LIZ_SDK_DIR}/pico_sdk_init.cmake OR NOT EXISTS ${LIZ_SDK_DIR}/lib/tinyusb/src/tusb.h)
    message(FATAL_ERROR
        "pico-sdk or its TinyUSB submodule is missing at ${LIZ_SDK_DIR}. From the repo root:\n"
        "  git submodule update --init firmware/pico-sdk\n"
        "  git -C firmware/pico-sdk submodule update --init lib/tinyusb")
endif()

# Pico-PIO-USB, the Fruit Jam's USB host (#14), is a submodule beside the SDK.
# TinyUSB fetches its own copy with a script, at 0.6.1, which predates the
# RP2350-E9 workaround. The SDK builds tinyusb_pico_pio_usb from this path.
set(PICO_PIO_USB_PATH ${CMAKE_CURRENT_LIST_DIR}/Pico-PIO-USB)
if(NOT EXISTS ${PICO_PIO_USB_PATH}/src/pio_usb.c)
    message(FATAL_ERROR
        "Pico-PIO-USB is missing at ${PICO_PIO_USB_PATH}. From the repo root:\n"
        "  git submodule update --init firmware/Pico-PIO-USB")
endif()

include(pico_sdk_import.cmake)

project(liz4270 VERSION 0.6.0 LANGUAGES C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

pico_sdk_init()

# The terminal core, shared with the host simulator (tools/sim).
add_subdirectory(core)

# What a build calls itself (#132): the number above, or the number+dev for anything but its own annotated
# v tag from a clean tree, and the commit. version.cmake works them out at every build, ahead of the link, so
# a new commit needs no reconfigure, and writes them into generated/liz_version.h, which only src/version.c
# includes. docs/versions.md has the scheme.
find_package(Git QUIET)
set(LIZ_VERSION_HEADER ${CMAKE_BINARY_DIR}/generated/liz_version.h)
add_custom_target(liz_version ALL
    COMMAND ${CMAKE_COMMAND} -DNUMBER=${PROJECT_VERSION} -DGIT=${GIT_EXECUTABLE}
        -DSOURCE_DIR=${CMAKE_CURRENT_LIST_DIR} -DOUTPUT=${LIZ_VERSION_HEADER}
        -P ${CMAKE_CURRENT_LIST_DIR}/version.cmake
    BYPRODUCTS ${LIZ_VERSION_HEADER}
    COMMENT "Naming the build"
    VERBATIM)

add_executable(liz4270 src/main.c src/clocks.c src/coax_link.c src/console.c
    src/video.c src/usb_host.c src/setup.c src/flash_store.c src/audio.c src/board_detect.c src/version.c)

pico_generate_pio_header(liz4270 ${CMAKE_CURRENT_LIST_DIR}/vendor/coax-tcp/coax.pio)
pico_generate_pio_header(liz4270 ${CMAKE_CURRENT_LIST_DIR}/src/coax_term.pio)

target_include_directories(liz4270 PRIVATE src ${CMAKE_BINARY_DIR}/generated)
add_dependencies(liz4270 liz_version)
target_compile_definitions(liz4270 PRIVATE
    LIZ_PICO_BOARD="${PICO_BOARD}")

# Every build runs clk_sys at 144 MHz from pll_sys (1440 MHz / 5 / 2): a
# multiple of 12 MHz for PIO-USB. clocks.c moves clk_usb and clk_adc onto
# pll_sys / 3, which leaves pll_usb for the Fruit Jam's video (#16, #26).
# The SDK's start-up code compiles into this target, so it sees these too.
target_compile_definitions(liz4270 PRIVATE
    SYS_CLK_HZ=144000000
    PLL_SYS_VCO_FREQ_HZ=1440000000
    PLL_SYS_POSTDIV1=5
    PLL_SYS_POSTDIV2=2)

# Warnings for our sources only: the SDK's sources compile into this target too.
set_source_files_properties(src/main.c src/clocks.c src/coax_link.c src/console.c
    src/video.c src/usb_host.c src/setup.c src/flash_store.c src/audio.c src/board_detect.c src/version.c
    PROPERTIES COMPILE_OPTIONS "-Wall;-Wextra")

# TinyUSB's configuration for both roles, ahead of pico_stdio_usb's own.
target_include_directories(liz4270 BEFORE PRIVATE src/tinyusb)
# Linking TinyUSB switches off what pico_stdio_usb does for an application
# that doesn't: its descriptors, and the reset interface that picotool's
# -f and the 1200-baud reset use. Keep them, so the port behaves as before.
target_compile_definitions(liz4270 PRIVATE
    PICO_STDIO_USB_USE_DEFAULT_DESCRIPTORS=1
    PICO_ENABLE_USB_RESET_VIA_VENDOR_INTERFACE=1
    PICO_ENABLE_USB_RESET_VIA_BAUD_RATE=1
    PICO_USB_RESET_SUPPORT_MS_OS_20_DESCRIPTOR=1
    PICO_USB_RESET_MS_OS_20_DESCRIPTOR_ITF=2)

if(NOT TARGET tinyusb_pico_pio_usb)
    message(FATAL_ERROR "the SDK made no tinyusb_pico_pio_usb target from ${PICO_PIO_USB_PATH}")
endif()
target_link_libraries(liz4270 pico_stdlib pico_multicore hardware_dma hardware_pio hardware_clocks liz_core
    hardware_pll hardware_irq hardware_resets hardware_flash hardware_i2c
    tinyusb_device tinyusb_host tinyusb_pico_pio_usb)

# USB serial only: UART stdio would claim header pins.
pico_enable_stdio_usb(liz4270 1)
pico_enable_stdio_uart(liz4270 0)

pico_set_program_name(liz4270 "Liz4270")
pico_set_program_description(liz4270 "IBM 3270 CUT terminal (3483-V)")

# Run from SRAM: core 1 answers the controller within microseconds, and a
# miss in the XIP flash cache (16 KB, shared by both cores) costs up to
# 25 us on a code path's first run (measured on a Pico 2, #12).
pico_set_binary_type(liz4270 copy_to_ram)

# Nothing the firmware reads while it runs may stay in flash: a settings save
# (#69) takes flash away from both cores, and pauses neither. Added before
# pico_add_extra_outputs, so it runs before the UF2 is written: a build it
# fails never writes a UF2 of the image it refused.
add_custom_command(TARGET liz4270 POST_BUILD
    COMMAND ${CMAKE_COMMAND} -DOBJDUMP=${CMAKE_OBJDUMP} -DELF=$<TARGET_FILE:liz4270>
            -P ${CMAKE_CURRENT_LIST_DIR}/check_flash_sections.cmake
    VERBATIM)

pico_add_extra_outputs(liz4270)
