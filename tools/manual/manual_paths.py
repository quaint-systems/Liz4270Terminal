# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Where the manual's sources, the sim and the build's output are, and tools/sim on the path (#136).

tools/sim is appended, not put first, so a module of tools/manual's own wins a name the two share.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
MANUAL = os.path.join(ROOT, 'docs', 'manual')
OUT = os.path.join(ROOT, 'build', 'manual')
TESTS_OUT = os.path.join(OUT, 'tests')  # where tests build, inside the checkout so Typst can read it
SIM = os.path.join(ROOT, 'tools', 'sim')
FONT_PATHS = (os.path.join(MANUAL, 'fonts'), os.path.join(SIM, 'fonts'))

if SIM not in sys.path:
    sys.path.append(SIM)
