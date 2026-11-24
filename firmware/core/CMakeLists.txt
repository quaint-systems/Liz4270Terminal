# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

# The terminal core: plain C11 with no Pico headers, shared with the host
# simulator in tools/sim (#5).
add_library(liz_core STATIC term.c regen.c manchester.c font_3270.c pixels.c render.c splash.c display_text.c keys3483.c
            keymap.c keyboard.c keymaps/us104.c settings.c dim.c beep.c board_id.c usb_fault.c ruler.c setup_ui.c
            model_change.c lock.c about_text.c)
target_include_directories(liz_core PUBLIC ${CMAKE_CURRENT_LIST_DIR})
# The core includes no SDK headers, so a warning here is ours: fail on it.
target_compile_options(liz_core PRIVATE -Wall -Wextra -Werror)
