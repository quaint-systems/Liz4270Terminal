# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

# What a build of the firmware calls itself (#132), worked out at every build, ahead of the link:
#
#   cmake -DNUMBER=X.Y.Z -DGIT=PATH -DSOURCE_DIR=DIR -DOUTPUT=FILE -P version.cmake
#
# FILE gets LIZ_VERSION and LIZ_COMMIT, and is rewritten only when they change, so nothing recompiles while
# they hold still. The version is NUMBER (project()'s) when HEAD carries the annotated tag vNUMBER and the
# tree is clean, and NUMBER+dev for any other build. From a clean tree, an annotated v[0-9]* tag at HEAD
# other than vNUMBER stops the build; an edited tree is never a release, so no tag disagrees with it. The
# commit is the abbreviated hash, with -dirty from an edited tree (a tracked file changed, or a file git
# neither tracks nor ignores), or unknown with no git (GIT empty) or no repository of its own: SOURCE_DIR
# must be the repository's firmware/, so a tree unpacked inside another checkout never takes that checkout's
# commit or tags. docs/versions.md has the scheme; tools/manual/edition.py names a build the same way, and
# tools/manual/test_edition.py checks that the two agree.

cmake_minimum_required(VERSION 3.25)

foreach(name NUMBER SOURCE_DIR OUTPUT)
    if("${${name}}" STREQUAL "")
        message(FATAL_ERROR "version.cmake needs -D${name}=")
    endif()
endforeach()

set(commit unknown)
set(tags "")
if(GIT)
    execute_process(
        COMMAND ${GIT} rev-parse --show-prefix
        WORKING_DIRECTORY ${SOURCE_DIR}
        RESULT_VARIABLE failed
        OUTPUT_VARIABLE prefix
        OUTPUT_STRIP_TRAILING_WHITESPACE
        ERROR_QUIET)
    if(NOT failed AND prefix STREQUAL "firmware/")
        # A commit under way holds index.lock; describe --dirty then answers without writing the index, so a
        # build never fails on one. It may refresh a stale index itself, taking the lock for a moment:
        # --no-optional-locks spares that only where git allows.
        execute_process(
            COMMAND ${GIT} --no-optional-locks describe --always --dirty --exclude=*
            WORKING_DIRECTORY ${SOURCE_DIR}
            RESULT_VARIABLE failed
            OUTPUT_VARIABLE described
            OUTPUT_STRIP_TRAILING_WHITESPACE
            ERROR_QUIET)
    endif()
    if(NOT failed AND NOT "${described}" STREQUAL "")
        set(commit ${described})
        # describe --dirty sees only tracked files, but a build reads whatever is there, such as a
        # CMakeUserPresets.json that CMake picks up by itself: a file git neither tracks nor ignores, anywhere in
        # the tree (:/), is an edit too. An empty directory isn't one.
        if(NOT commit MATCHES "-dirty$")
            execute_process(
                COMMAND ${GIT} --no-optional-locks ls-files --others --exclude-standard --directory
                    --no-empty-directory :/
                WORKING_DIRECTORY ${SOURCE_DIR}
                RESULT_VARIABLE unlisted
                OUTPUT_VARIABLE untracked
                OUTPUT_STRIP_TRAILING_WHITESPACE
                ERROR_QUIET)
            if(unlisted OR NOT "${untracked}" STREQUAL "")
                string(APPEND commit -dirty)
            endif()
        endif()
        execute_process(
            COMMAND ${GIT} --no-optional-locks for-each-ref --points-at=HEAD
                "--format=%(objecttype) %(refname:strip=2)" refs/tags/
            WORKING_DIRECTORY ${SOURCE_DIR}
            OUTPUT_VARIABLE refs
            OUTPUT_STRIP_TRAILING_WHITESPACE
            ERROR_QUIET)
        string(REPLACE "\n" ";" refs "${refs}")
        foreach(ref IN LISTS refs)
            # The object type is tag for an annotated tag, and commit for a lightweight one.
            if(ref MATCHES "^tag (v[0-9].*)$")
                list(APPEND tags ${CMAKE_MATCH_1})
            endif()
        endforeach()
    endif()
endif()

# Only a clean tree can be a release, and only one can disagree with its tag: a release's PR sets project() to
# the new number while HEAD still carries the last release's.
set(version ${NUMBER}+dev)
if(NOT commit MATCHES "-dirty$")
    foreach(tag IN LISTS tags)
        if(NOT tag STREQUAL "v${NUMBER}")
            message(FATAL_ERROR "HEAD is tagged ${tag}, but project() in firmware/CMakeLists.txt says ${NUMBER}: "
                                "a release's tag and its number must agree (docs/versions.md)")
        endif()
        set(version ${NUMBER})
    endforeach()
endif()

string(CONFIGURE [=[// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// Written by firmware/version.cmake at every build (#132): what this build calls itself.

#define LIZ_VERSION "@version@"
#define LIZ_COMMIT "@commit@"
]=] text @ONLY)
set(old "")
if(EXISTS ${OUTPUT})
    file(READ ${OUTPUT} old)
endif()
if(NOT old STREQUAL text)
    file(WRITE ${OUTPUT} "${text}")
endif()
