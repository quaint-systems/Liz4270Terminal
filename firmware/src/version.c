// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: ISC

// The build's version and commit (#132), from the header firmware/version.cmake writes at every build. This
// is the one file that includes it, so a new commit recompiles it alone. picotool info reads them from the
// binary info.

#include "pico/binary_info.h"

#include "liz_version.h"
#include "version.h"

const char liz_version[] = LIZ_VERSION;
const char liz_commit[] = LIZ_COMMIT;

bi_decl(bi_program_version_string(LIZ_VERSION))
bi_decl(bi_program_build_attribute("commit " LIZ_COMMIT))
