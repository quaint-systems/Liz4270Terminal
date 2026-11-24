# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

# The post-build check behind settings saves (#69): fails the build if the
# image leaves anything in flash that the firmware could read while it runs.
#
# A save takes XIP down while core 1, the video's DMA and every interrupt keep
# running (src/flash_store.h), so nothing may read flash then. With
# copy_to_ram, only .flashtext (crt0 and the default fault handlers),
# .binary_info, .ARM.exidx and .flash_end stay in flash. Any other section
# with bytes at an address in the XIP window (0x10000000-0x13FFFFFF) fails it:
# an __in_flash constant in .rodata, code placed in flash, data in the XIP
# cache's SRAM, or another binary type.
#
#   cmake -DOBJDUMP=arm-none-eabi-objdump -DELF=liz4270.elf -P check_flash_sections.cmake

cmake_minimum_required(VERSION 3.25)

execute_process(COMMAND ${OBJDUMP} -h ${ELF} OUTPUT_VARIABLE table RESULT_VARIABLE status)
if(NOT status EQUAL 0)
    message(FATAL_ERROR "check_flash_sections: '${OBJDUMP} -h ${ELF}' failed")
endif()

set(allowed .flashtext .binary_info .ARM.exidx .flash_end)
set(found_flashtext FALSE)
set(bad "")
string(REPLACE "\n" ";" lines "${table}")
foreach(line IN LISTS lines)
    # "  0 .flashtext    000001ec  10000000  10000000  00001000  2**2"
    if(line MATCHES "^ *[0-9]+ +([^ ]+) +([0-9a-f]+) +([0-9a-f]+) ")
        set(name ${CMAKE_MATCH_1})
        set(size ${CMAKE_MATCH_2})
        set(vma ${CMAKE_MATCH_3})
        # Found only at an address the check can read, so a table in another
        # format fails rather than passing with nothing checked.
        if(name STREQUAL ".flashtext" AND vma MATCHES "^1[0-3]......$")
            set(found_flashtext TRUE)
        endif()
        if(vma MATCHES "^1[0-3]......$" AND NOT size MATCHES "^0+$" AND NOT name IN_LIST allowed)
            list(APPEND bad "${name} (0x${size} bytes at 0x${vma})")
        endif()
    endif()
endforeach()

if(NOT found_flashtext)
    message(FATAL_ERROR "check_flash_sections: no .flashtext at a flash address in '${OBJDUMP} -h ${ELF}': "
                        "is it the firmware's ELF, and objdump's usual table?")
endif()
if(bad)
    string(REPLACE ";" ", " bad "${bad}")
    message(FATAL_ERROR "check_flash_sections: ${bad} in flash. A settings save (#69) takes flash away "
                        "while the firmware runs, so nothing it reads may stay there.")
endif()
