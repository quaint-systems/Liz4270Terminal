# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The manual's screens, drawn by the firmware's renderer through the sim (#136).

The terminal's own: SetUp's screens and the lock come from tools/sim/screen.py's writers, About showing
revision A with this build's version and commit in place of the sim's stand-in, and the splash shows the
build's version and commit, as the firmware's does (#132).

The host's: HOST_FIGURES, each a screen recorded by the sim's snap into docs/manual/screens/ or composed by
compose.py, drawn with the settings its figure asks for, and the status line's symbols cut from the status
line as compose.STATUS_SYMBOLS lays them out.

Every file is NAME-640.png, as style.typ's screen-image and cells-image ask for it.
"""

import os

from PIL import Image

import manual_paths
import compose
import core
import screen
import screen_fixture

FIXTURES = os.path.join(manual_paths.MANUAL, 'screens')

# Each host figure: name -> (its screen, a fixture's name in FIXTURES or one of compose.SCREENS; how it's drawn:
# 'settings', the screen.Settings fields to change, 'ruler', an address or 'cursor' for the screen's own, and
# 'dimmed').
HOST_FIGURES = {
    'colours': ('colours', {}),
    'model3': ('model3', {}),
    'model4': ('model4', {}),
    'dslist': ('dslist', {}),  # a dataset list of SYS1.* in RFE, recorded on MVS/CE (Oct 18)
    'dslist-ruler': ('dslist', {'settings': {'ruler_style': screen.RULER_CROSS}, 'ruler': 'cursor'}),
    'dslist-mono': ('dslist', {'settings': {'mono': True}}),
}

WIDTH = 640
REVISION_A = (0, 0)  # GPIO 4 and 5, read with the pull-ups on (firmware/core/board_id.c)


def board_label():
    """Revision A as firmware/src/board_detect.c names it: 'Liz4270 rev A (ID 00)'."""
    (gpio4, gpio5) = REVISION_A
    return f'{core.board_name(core.board_from_id(gpio4, gpio5))} (ID {gpio4}{gpio5})'


def identity(version, commit):
    """About's version, commit and board as revision A shows them, for screen.setup_screens."""
    return (version, commit, board_label())


def write_core_screens(out_dir, version, commit):
    """Every screen of the terminal's own that the manual uses, into out_dir. Returns the paths."""
    os.makedirs(out_dir, exist_ok=True)
    paths = screen.write_setup_pngs(out_dir, WIDTH, identity=identity(version, commit))
    paths += screen.write_lock_pngs(out_dir, WIDTH)
    splash = os.path.join(out_dir, f'splash-{WIDTH}.png')
    screen.write_splash_png(splash, WIDTH, version=version.encode('latin-1'), commit=commit.encode('latin-1'))
    return sorted(paths + [splash])


def host_screen(source):
    """A host figure's screen: a fixture recorded into docs/manual/screens/, or one compose.py makes."""
    if source in compose.SCREENS:
        return compose.SCREENS[source]()
    return screen_fixture.read(os.path.join(FIXTURES, f'{source}.json'))


def draw(fixture, path, settings=None, ruler=None, dimmed=False):
    """fixture as the Fruit Jam draws it at 640, with settings (screen.Settings fields to change), the ruler (an
    address, or 'cursor' for the fixture's own) and auto dim."""
    screen.write_video_png(path, fixture.regen, fixture.ac, fixture.control, WIDTH,
                           settings=screen.Settings()._replace(**(settings or {})), dimmed=dimmed, eab=fixture.eab,
                           model=fixture.model, ruler=fixture.ac if ruler == 'cursor' else ruler)


def write_status_symbols(out_dir):
    """Each of compose.STATUS_SYMBOLS as status-NAME-640.png: Model 2's status line, its own columns."""
    geometry = screen.geometry(2)
    paths = []
    for (name, (codes, first, last, dimmed)) in compose.STATUS_SYMBOLS.items():
        whole = os.path.join(out_dir, f'status-{name}-whole.png')
        regen = codes + bytes(geometry.screen_end - screen.COLS)
        screen.write_video_png(whole, regen, screen.SCREEN_START, 0, WIDTH, dimmed=dimmed)
        path = os.path.join(out_dir, f'status-{name}-{WIDTH}.png')
        cell = WIDTH // screen.COLS
        with Image.open(whole) as image:
            image.crop((first * cell, geometry.status_y, (last + 1) * cell,
                        geometry.status_y + geometry.cell_h)).save(path)
        os.remove(whole)
        paths.append(path)
    return paths


def write_host_screens(out_dir):
    """Every host figure as NAME-640.png and every status-line symbol as status-NAME-640.png, into out_dir."""
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for (name, (source, options)) in HOST_FIGURES.items():
        path = os.path.join(out_dir, f'{name}-{WIDTH}.png')
        draw(host_screen(source), path, **options)
        paths.append(path)
    return sorted(paths + write_status_symbols(out_dir))
