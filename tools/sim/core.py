# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The terminal core (firmware/core), loaded into Python with ctypes.

The core is the firmware's own C. build() compiles it into a shared library
under tools/sim/build/ whenever a source, or this file with its compiler
settings, is newer than the library, so the tests and the simulator always run
the current code.
"""

import ctypes
import functools
import glob
import os
import re
import subprocess
import sys

from paths import HERE, ROOT

CORE_DIR = os.path.join(ROOT, 'firmware', 'core')
BUILD_DIR = os.path.join(HERE, 'build')
LIBRARY = os.path.join(BUILD_DIR, 'liblizcore' + ('.dylib' if sys.platform == 'darwin' else '.so'))

# -Werror, as the firmware builds liz_core; -std=c11 where the firmware has gnu11.
CFLAGS = ['-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC']

REGEN_SIZE = 8192
TX_MAX = 32
FONT_GLYPHS = 256
FONT_ROWS = 19
FONT_HEIGHTS = (19, 14, 10)  # Model 2's cells, Model 3's and Model 4's (#110)


class _Config(ctypes.Structure):
    _fields_ = [('eab', ctypes.c_bool), ('model', ctypes.c_uint8)]


class _Layout(ctypes.Structure):
    _fields_ = [('width', ctypes.c_uint16), ('cell_w', ctypes.c_uint8)]


class _Key3483(ctypes.Structure):
    _fields_ = [('label', ctypes.c_char_p), ('repeat_from', ctypes.c_char_p),
                ('make_break', ctypes.c_uint8), ('repeat', ctypes.c_uint8)]


class _Entry(ctypes.Structure):
    _fields_ = [('usage', ctypes.c_uint8), ('when', ctypes.c_uint8), ('key', ctypes.c_uint8),
                ('mods', ctypes.c_uint8)]


class _Keymap(ctypes.Structure):
    pass


_Keymap._fields_ = [('name', ctypes.c_char_p), ('title', ctypes.c_char_p), ('status', ctypes.c_char_p),
                    ('base', ctypes.POINTER(_Keymap)), ('devices', ctypes.POINTER(ctypes.c_uint32)),
                    ('entries', ctypes.POINTER(_Entry)), ('count', ctypes.c_uint16)]


class _KbdStats(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint32) for name in ('presses', 'repeats', 'drops', 'local', 'codes', 'lost')]


class _Tone(ctypes.Structure):
    _fields_ = [('sin', ctypes.c_uint16), ('cos', ctypes.c_uint16)]


class _LockKey(ctypes.Structure):
    _fields_ = [('code', ctypes.c_uint8), ('shift', ctypes.c_bool)]


class _LockLine(ctypes.Structure):
    _fields_ = [('codes', ctypes.c_uint8 * 80), ('cursor', ctypes.c_int8), ('bar', ctypes.c_bool)]


class _LockStats(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint32) for name in ('locks', 'unlocks', 'wrong')]


class _Settings(ctypes.Structure):
    _fields_ = [('cursor', ctypes.c_uint8), ('cursor_blink', ctypes.c_bool), ('indicator', ctypes.c_bool),
                ('auto_dim', ctypes.c_bool), ('dim_minutes', ctypes.c_uint8), ('colour_input', ctypes.c_uint8),
                ('colour_input_hi', ctypes.c_uint8), ('colour_protected', ctypes.c_uint8),
                ('colour_protected_hi', ctypes.c_uint8), ('mono', ctypes.c_bool), ('ruler_style', ctypes.c_uint8),
                ('ruler_colour', ctypes.c_uint8), ('ruler_follows', ctypes.c_bool),
                ('typematic_rate', ctypes.c_uint8), ('typematic_delay', ctypes.c_uint8), ('click', ctypes.c_bool),
                ('click_volume', ctypes.c_uint8), ('alarm_volume', ctypes.c_uint8), ('mono_case', ctypes.c_bool),
                ('model', ctypes.c_uint8), ('lock_sessions', ctypes.c_bool), ('password', ctypes.c_uint64)]


SETTINGS_PAGE = 256  # a record is written as one flash page (settings.h)
_PAGE = ctypes.c_uint8 * SETTINGS_PAGE


class _Frame(ctypes.Structure):
    _fields_ = [('regen', ctypes.POINTER(ctypes.c_uint8)), ('eab', ctypes.POINTER(ctypes.c_uint8)),
                ('ac', ctypes.c_uint16), ('control', ctypes.c_uint8),
                ('settings', ctypes.POINTER(_Settings)), ('frame', ctypes.c_uint32), ('dimmed', ctypes.c_bool),
                ('ruler', ctypes.c_uint16), ('setup', ctypes.c_bool), ('flash', ctypes.c_bool),
                ('model', ctypes.c_uint8), ('setup_cursor', ctypes.c_uint16), ('locked', ctypes.c_bool),
                ('status', ctypes.POINTER(ctypes.c_uint8)), ('status_cursor', ctypes.c_int8),
                ('status_bar', ctypes.c_bool)]


class _Geometry(ctypes.Structure):
    _fields_ = [('rows', ctypes.c_uint8), ('cell_h', ctypes.c_uint8), ('top', ctypes.c_uint16),
                ('gap_y', ctypes.c_uint16), ('rule_y', ctypes.c_uint16), ('status_y', ctypes.c_uint16),
                ('screen_end', ctypes.c_uint16), ('underscore_line', ctypes.c_uint8), ('cursor_first', ctypes.c_uint8),
                ('nine', ctypes.c_void_p), ('eight', ctypes.c_void_p), ('ink', ctypes.c_void_p)]


_GEOMETRY = ('rows', 'cell_h', 'top', 'gap_y', 'rule_y', 'status_y', 'screen_end', 'underscore_line',
             'cursor_first')


class _Ruler(ctypes.Structure):
    _fields_ = [('at', ctypes.c_uint16), ('presses', ctypes.c_uint32)]


RULER_OFF = 0xFFFF  # ruler.h: the ruler is off


class _SetupUiStats(ctypes.Structure):
    _fields_ = [('opens', ctypes.c_uint32), ('keys', ctypes.c_uint32), ('alarms', ctypes.c_uint32)]


SETUP_UI_CELLS = 2000  # setup_ui.h: an image is the status line and the 24 rows, RENDER_SCREEN_END bytes


LINES = 480
_LAYOUTS = {640: 'render_640x480', 720: 'render_720x480'}


def build():
    """Compile the core if a source, a header or this file is newer than the library."""
    sources = sorted(glob.glob(os.path.join(CORE_DIR, '**', '*.c'), recursive=True))
    if not sources:
        raise FileNotFoundError(f'no C sources in {CORE_DIR}')
    headers = glob.glob(os.path.join(CORE_DIR, '**', '*.h'), recursive=True)
    inputs = sources + headers + [os.path.abspath(__file__)]  # this file holds CFLAGS
    if os.path.exists(LIBRARY) and os.path.getmtime(LIBRARY) >= max(map(os.path.getmtime, inputs)):
        return
    os.makedirs(BUILD_DIR, exist_ok=True)
    subprocess.run([os.environ.get('CC', 'cc'), *CFLAGS, '-I', CORE_DIR, '-o', LIBRARY, *sources], check=True)


_STATE = ctypes.c_void_p
_SIGNATURES = {
    'term_sizeof': ([], ctypes.c_size_t),
    'term_init': ([_STATE, ctypes.POINTER(_Config)], None),
    'term_rx_word': ([_STATE, ctypes.c_uint16], None),
    'term_rx_end': ([_STATE, ctypes.POINTER(ctypes.c_uint16), ctypes.c_size_t], ctypes.c_size_t),
    'term_rx_abort': ([_STATE], None),
    'term_key': ([_STATE, ctypes.c_uint8], ctypes.c_bool),
    'term_queued': ([_STATE], ctypes.c_uint),
    'term_display_gen': ([_STATE], ctypes.c_uint32),
    'term_written': ([_STATE], ctypes.c_bool),
    'term_writes': ([_STATE], ctypes.c_uint32),
    'term_regen': ([_STATE], ctypes.POINTER(ctypes.c_uint8)),
    'term_eab': ([_STATE], ctypes.POINTER(ctypes.c_uint8)),
    'term_ac': ([_STATE], ctypes.c_uint16),
    'term_control': ([_STATE], ctypes.c_uint8),
    'term_secondary': ([_STATE], ctypes.c_uint8),
    'term_clicker': ([_STATE], ctypes.c_bool),
    'term_alarms': ([_STATE], ctypes.c_uint32),
    'term_unknown': ([_STATE], ctypes.c_uint32),
    'term_last_unknown': ([_STATE], ctypes.c_uint16),
    'term_no_feature': ([_STATE], ctypes.c_uint32),
    'term_last_no_feature': ([_STATE], ctypes.c_uint16),
    'render_sizeof': ([], ctypes.c_size_t),
    'render_frame_begin': ([_STATE, ctypes.POINTER(_Layout), ctypes.POINTER(_Frame)], None),
    'render_line': ([_STATE, ctypes.c_uint, ctypes.POINTER(ctypes.c_uint32)], None),
    'render_place': ([ctypes.c_uint16, ctypes.c_uint8], ctypes.c_uint16),
    'render_geometry': ([ctypes.c_uint8], ctypes.POINTER(_Geometry)),
    'splash_sizeof': ([], ctypes.c_size_t),
    'splash_init': ([_STATE, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint32], None),
    'splash_showing': ([_STATE, ctypes.c_uint32, ctypes.c_bool], ctypes.c_bool),
    'splash_dismiss': ([_STATE], None),
    'splash_colour': ([ctypes.POINTER(_Settings)], ctypes.c_uint16),
    'splash_line': ([_STATE, ctypes.POINTER(_Layout), ctypes.c_uint, ctypes.c_uint16, ctypes.POINTER(ctypes.c_uint32)],
                    None),
    'keys3483_key': ([ctypes.c_uint], ctypes.POINTER(_Key3483)),
    'keymap_count': ([], ctypes.c_uint),
    'keymap_at': ([ctypes.c_uint], ctypes.POINTER(_Keymap)),
    'keymap_for': ([ctypes.c_uint16, ctypes.c_uint16], ctypes.POINTER(_Keymap)),
    'keymap_lookup': ([ctypes.POINTER(_Keymap), ctypes.c_uint8, ctypes.c_uint8], ctypes.POINTER(_Entry)),
    'keymap_lookup_exact': ([ctypes.POINTER(_Keymap), ctypes.c_uint8, ctypes.c_uint8], ctypes.POINTER(_Entry)),
    'kbd_sizeof': ([], ctypes.c_size_t),
    'kbd_init': ([_STATE, _STATE], None),
    'kbd_attach': ([_STATE, ctypes.c_uint, ctypes.POINTER(_Keymap)], None),
    'kbd_release_all': ([_STATE, ctypes.c_uint], None),
    'kbd_detach': ([_STATE, ctypes.c_uint], None),
    'kbd_report': ([_STATE, ctypes.c_uint, ctypes.POINTER(ctypes.c_uint8), ctypes.c_uint32,
                    ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t], ctypes.c_size_t),
    'kbd_stats': ([_STATE, ctypes.POINTER(_KbdStats)], None),
    'kbd_clear_stats': ([_STATE], None),
    'kbd_keystrokes': ([_STATE], ctypes.c_uint32),
    'kbd_local_keystrokes': ([_STATE], ctypes.c_uint32),
    'kbd_rule_presses': ([_STATE], ctypes.c_uint32),
    'kbd_local': ([_STATE, ctypes.c_bool], None),
    'kbd_local_on': ([_STATE], ctypes.c_bool),
    'kbd_local_key': ([_STATE, ctypes.POINTER(ctypes.c_uint8), ctypes.POINTER(ctypes.c_bool)], ctypes.c_bool),
    'kbd_tick': ([_STATE, ctypes.c_uint32], None),
    'kbd_redact': ([_STATE, ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t], None),
    'kbd_typematic': ([_STATE, ctypes.c_uint8, ctypes.c_uint8], None),
    'kbd_rate': ([_STATE], ctypes.c_uint8),
    'kbd_delay': ([_STATE], ctypes.c_uint8),
    'kbd_resync': ([_STATE], None),
    'settings_defaults': ([ctypes.POINTER(_Settings)], None),
    'settings_valid': ([ctypes.POINTER(_Settings)], ctypes.c_bool),
    'settings_pack': ([ctypes.POINTER(_Settings), ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint8)],
                      ctypes.c_size_t),
    'settings_unpack': ([ctypes.POINTER(_Settings), ctypes.POINTER(ctypes.c_uint32),
                         ctypes.POINTER(ctypes.c_uint8)], ctypes.c_bool),
    'settings_load': ([ctypes.POINTER(_Settings), ctypes.POINTER(ctypes.c_uint32),
                       ctypes.POINTER(ctypes.POINTER(ctypes.c_uint8)), ctypes.c_uint], ctypes.c_int),
    'settings_equal': ([ctypes.POINTER(_Settings), ctypes.POINTER(_Settings)], ctypes.c_bool),
    'settings_crc32': ([ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t], ctypes.c_uint32),
    'dim_sizeof': ([], ctypes.c_size_t),
    'dim_init': ([_STATE, ctypes.c_uint32, ctypes.c_uint32], None),
    'dim_tick': ([_STATE, ctypes.POINTER(_Settings), ctypes.c_uint32, ctypes.c_uint32], None),
    'dim_due': ([_STATE, ctypes.POINTER(_Settings), ctypes.c_uint32, ctypes.c_uint32], ctypes.c_bool),
    'dim_report': ([_STATE, ctypes.c_uint, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint8),
                    ctypes.POINTER(ctypes.c_uint8)], ctypes.c_bool),
    'dim_activity': ([_STATE, ctypes.c_uint32], None),
    'dim_forget': ([_STATE, ctypes.c_uint], None),
    'dim_now': ([_STATE], None),
    'dim_on': ([_STATE], ctypes.c_bool),
    'beep_tone': ([ctypes.c_uint32, ctypes.c_uint32, ctypes.POINTER(_Tone)], ctypes.c_bool),
    'beep_samples': ([ctypes.c_uint32, ctypes.c_uint32], ctypes.c_uint32),
    'beep_level_code': ([ctypes.c_int], ctypes.c_uint8),
    'beep_sizeof': ([], ctypes.c_size_t),
    'beep_init': ([_STATE, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32], None),
    'beep_poll': ([_STATE, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_bool,
                   ctypes.POINTER(_Settings)], ctypes.c_int),
    'beep_volume_db': ([ctypes.c_uint8], ctypes.c_int),
    'beep_power_on_volume': ([ctypes.POINTER(_Settings)], ctypes.c_uint8),
    'beep_resolve': ([ctypes.c_int, ctypes.POINTER(_Settings)], ctypes.c_int),
    'beep_sound_db': ([ctypes.c_int, ctypes.POINTER(_Settings)], ctypes.c_int),
    'beep_start': ([_STATE, ctypes.c_uint32, ctypes.c_int], None),
    'beep_cancel': ([_STATE], None),
    'beep_preview': ([_STATE], None),
    'beep_length': ([_STATE, ctypes.c_int], ctypes.c_uint32),
    'beep_set_length': ([_STATE, ctypes.c_int, ctypes.c_uint32], None),
    'beep_swallowed': ([_STATE], ctypes.c_uint32),
    'board_from_id': ([ctypes.c_bool, ctypes.c_bool], ctypes.c_int),
    'board_name': ([ctypes.c_int], ctypes.c_char_p),
    'board_has_usb_fault': ([ctypes.c_int], ctypes.c_bool),
    'board_has_hpd': ([ctypes.c_int], ctypes.c_bool),
    'usb_fault_sizeof': ([], ctypes.c_size_t),
    'usb_fault_init': ([_STATE], None),
    'usb_fault_poll': ([_STATE, ctypes.c_uint32, ctypes.c_bool, ctypes.c_bool], None),
    'usb_fault_trips': ([_STATE], ctypes.c_uint32),
    'model_change_sizeof': ([], ctypes.c_size_t),
    'model_change_init': ([_STATE], None),
    'model_change_poll': ([_STATE, ctypes.c_uint32, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_bool, ctypes.c_bool,
                           ctypes.c_bool], ctypes.c_int),
    'model_change_power_ons': ([_STATE], ctypes.c_uint32),
    'ruler_init': ([ctypes.POINTER(_Ruler), ctypes.c_uint32], None),
    'ruler_toggle': ([ctypes.POINTER(_Ruler), ctypes.c_uint16], None),
    'ruler_poll': ([ctypes.POINTER(_Ruler), ctypes.c_uint32, ctypes.c_uint16, ctypes.c_bool, ctypes.c_uint8], None),
    'ruler_address': ([ctypes.c_uint16, ctypes.c_uint16, ctypes.c_bool], ctypes.c_uint16),
    'setup_ui_sizeof': ([], ctypes.c_size_t),
    'setup_ui_init': ([_STATE], None),
    'setup_ui_open': ([_STATE], None),
    'setup_ui_identify': ([_STATE, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p], None),
    'setup_ui_key': ([_STATE, ctypes.c_uint8, ctypes.c_bool, ctypes.POINTER(_Settings)], ctypes.c_int),
    'setup_ui_cursor_at': ([_STATE], ctypes.c_uint16),
    'setup_ui_cursor': ([_STATE], ctypes.c_uint16),
    'setup_ui_screen': ([_STATE], ctypes.c_int),
    'setup_ui_offline': ([_STATE], ctypes.c_bool),
    'setup_ui_selector_at': ([_STATE], ctypes.c_uint16),
    'setup_ui_stats': ([_STATE, ctypes.POINTER(_SetupUiStats)], None),
    'setup_ui_draw': ([_STATE, ctypes.POINTER(_Settings)], None),
    'setup_ui_regen': ([_STATE], ctypes.POINTER(ctypes.c_uint8)),
    'setup_ui_eab': ([_STATE], ctypes.POINTER(ctypes.c_uint8)),
    'coax_manchester_encode': ([ctypes.c_uint16], ctypes.c_uint32),
    'display_text_code': ([ctypes.c_ubyte], ctypes.c_uint8),
    'lock_hash': ([ctypes.POINTER(_LockKey), ctypes.c_uint], ctypes.c_uint64),
    'lock_character': ([ctypes.c_uint8], ctypes.c_bool),
    'lock_sizeof': ([], ctypes.c_size_t),
    'lock_clear': ([_STATE], None),
    'lock_engage': ([_STATE], None),
    'lock_state': ([_STATE], ctypes.c_int),
    'lock_key': ([_STATE, ctypes.c_uint8, ctypes.c_bool, ctypes.c_uint64], ctypes.c_int),
    'lock_status_line': ([_STATE, ctypes.POINTER(_LockLine)], None),
    'lock_dim_due': ([ctypes.POINTER(_Settings), ctypes.c_bool], ctypes.c_int),
    'lock_stats': ([_STATE, ctypes.POINTER(_LockStats)], None),
}

_library = None


def library():
    """The core, built if needed and loaded once per process."""
    global _library
    if _library is None:
        build()
        lib = ctypes.CDLL(LIBRARY)
        for (name, (argtypes, restype)) in _SIGNATURES.items():
            function = getattr(lib, name)
            function.argtypes = argtypes
            function.restype = restype
        _library = lib
    return _library


def manchester_encode(value):
    """One word as xmit_serial shifts it out (firmware/core/manchester.c)."""
    return library().coax_manchester_encode(value)


def display_text_code(ch):
    """The display code that shows ch, a Latin-1 character (firmware/core/display_text.c); 0x18 ('?') if none."""
    return library().display_text_code(ord(ch))


def lock_hash(keys):
    """The password's hash (firmware/core/lock.c, #122) for keys, a list of (code, shift)."""
    array = (_LockKey * max(len(keys), 1))(*(_LockKey(code, shift) for (code, shift) in keys))
    return library().lock_hash(array, len(keys))


def lock_character(code):
    """Whether a 3483-V key types a character into a password (#122)."""
    return library().lock_character(code)


def beep_volume_db(volume):
    """The volume ladder's dB for Click Volume or Alarm volume volume (firmware/core/beep.c, #107)."""
    return library().beep_volume_db(volume)


def beep_power_on_volume(settings=None):
    """The power-on alarm's volume under the settings (#107)."""
    return library().beep_power_on_volume(ctypes.byref(_settings(settings)))


def beep_resolve(sound, settings=None):
    """What beep.h's sound comes to under the settings (#107): a click nothing at Click Volume Off, the alarm
    the flash at Alarm volume Off."""
    return library().beep_resolve(sound, ctypes.byref(_settings(settings)))


def beep_sound_db(sound, settings=None):
    """The dB a click or the alarm sounds at under the settings (#107)."""
    return library().beep_sound_db(sound, ctypes.byref(_settings(settings)))


def _settings(settings=None):
    """A _Settings from anything with its fields (screen.Settings), or the core's defaults for None."""
    s = _Settings()
    library().settings_defaults(ctypes.byref(s))
    if settings is not None:
        for (name, _) in _Settings._fields_:
            setattr(s, name, getattr(settings, name))
    return s


def settings_defaults():
    """The core's default settings (firmware/core/settings.c), field by field."""
    s = _settings()
    return {name: getattr(s, name) for (name, _) in _Settings._fields_}


def _with(fields):
    """A _Settings: the core's defaults with fields (a dict) changed."""
    s = _settings()
    for (name, value) in fields.items():
        setattr(s, name, value)
    return s


def _fields(s):
    return {name: getattr(s, name) for (name, _) in _Settings._fields_}


def _page(data):
    """A page: data, then 0xFF to SETTINGS_PAGE bytes."""
    return _PAGE.from_buffer_copy(data.ljust(SETTINGS_PAGE, b'\xff'))


def settings_valid(**fields):
    """settings_valid on the defaults with fields changed."""
    return library().settings_valid(ctypes.byref(_with(fields)))


def settings_pack(seq, **fields):
    """settings_pack on the defaults with fields changed: (the page, the record's length)."""
    page = _PAGE()
    length = library().settings_pack(ctypes.byref(_with(fields)), seq, page)
    return (bytes(page), length)


def settings_unpack(data, before=None):
    """settings_unpack on a page made from data: (accepted, fields, seq). The settings start as before (the
    defaults for None) and the sequence as 0xDEADBEEF, so a refusal shows whether they were left alone."""
    s = _with(before or {})
    seq = ctypes.c_uint32(0xDEADBEEF)
    accepted = library().settings_unpack(ctypes.byref(s), ctypes.byref(seq), _page(data))
    return (accepted, _fields(s), seq.value)


def settings_load(pages):
    """settings_load over a page made from each of pages: (the slot chosen or -1, fields, seq)."""
    buffers = [_page(data) for data in pages]
    slots = (ctypes.POINTER(ctypes.c_uint8) * len(buffers))(
        *[ctypes.cast(buffer, ctypes.POINTER(ctypes.c_uint8)) for buffer in buffers])
    s = _settings()
    seq = ctypes.c_uint32(0xDEADBEEF)
    slot = library().settings_load(ctypes.byref(s), ctypes.byref(seq), slots, len(buffers))
    return (slot, _fields(s), seq.value)


def settings_equal(a, b):
    """settings_equal on the defaults with a's fields changed, and with b's."""
    return library().settings_equal(ctypes.byref(_with(a)), ctypes.byref(_with(b)))


def settings_crc32(data):
    buffer = (ctypes.c_uint8 * len(data)).from_buffer_copy(data)
    return library().settings_crc32(buffer, len(data))


def dim_minutes_choices():
    """SetUp's Delay choices, in minutes (settings_dim_minutes)."""
    return list((ctypes.c_uint8 * 3).in_dll(library(), 'settings_dim_minutes'))


def beep_tone(hz, fs):
    """(sin, cos) as beep_tone gives them for registers 76-79, or None where it refuses."""
    tone = _Tone()
    return (tone.sin, tone.cos) if library().beep_tone(hz, fs, ctypes.byref(tone)) else None


def beep_samples(ms, fs):
    return library().beep_samples(ms, fs)


def beep_level_code(db):
    return library().beep_level_code(db)


def board_from_id(gpio4, gpio5):
    """board_id.h's board_t for GPIO 4 and 5 as read with the pull-ups on."""
    return library().board_from_id(gpio4, gpio5)


def board_name(board):
    return library().board_name(board).decode('ascii')


def board_has_usb_fault(board):
    """Whether the board has revision A's USB-A fault flag on GPIO6."""
    return library().board_has_usb_fault(board)


def board_has_hpd(board):
    """Whether the board has revision A's HDMI hot-plug detect on GPIO7."""
    return library().board_has_hpd(board)


def font_rows(columns, height=FONT_ROWS):
    """The firmware's font (firmware/core/font_3270.c): 256 glyphs of height rows, bit x for pixel x.

    columns is 9 for 720 x 480's cells or 8 for 640 x 480's; height is 19, or 14 or 10 for Model 3's and
    Model 4's cells (#110).
    """
    ctype = ctypes.c_uint16 if columns == 9 else ctypes.c_uint8
    table = (ctype * height * FONT_GLYPHS).in_dll(library(), f'font_3270_{columns}x{height}')
    return [list(glyph) for glyph in table]


def font_ink(height=FONT_ROWS):
    """Each glyph's lines with ink at this height, bit n for line n, as baked into font_3270.c."""
    name = 'font_3270_ink' if height == FONT_ROWS else f'font_3270_ink{height}'
    return list((ctypes.c_uint32 * FONT_GLYPHS).in_dll(library(), name))


def constants(header, prefix):
    """{NAME: value} for each prefix + NAME given a number in firmware/core/<header>:
    enum members and #defines alike."""
    with open(os.path.join(CORE_DIR, header), encoding='utf-8') as stream:
        text = stream.read()
    pattern = rf'\b{prefix}(\w+)\s*(?:=\s*)?(0x[0-9A-Fa-f]+|\d+)u?\b'
    return {name: int(value, 0) for (name, value) in re.findall(pattern, text)}


@functools.cache
def usages():
    """USB usages by name, from usb_usage.h: usages()['A'] == 0x04."""
    return constants('usb_usage.h', 'U_')


@functools.cache
def scan_codes():
    """The 3483-V's scan codes by name, from keys3483.h: scan_codes()['PA1'] == 103."""
    return constants('keys3483.h', 'K_')


@functools.cache
def repeat_classes():
    """Typematic classes by name, from keys3483.h:
    {'NONE': 0, 'NORMAL': 1, 'FAST': 2, 'EARLY': 3, 'CLASSES': 4}."""
    return constants('keys3483.h', 'KR_')


def keys3483():
    """{code: {'label', 'repeat_from', 'make_break', 'repeat'}} for each key in firmware/core/keys3483.c."""
    lib = library()
    out = {}
    for code in range(256):
        found = lib.keys3483_key(code)
        if found:
            key = found.contents
            out[code] = {'label': key.label.decode('utf-8'),
                         'repeat_from': key.repeat_from.decode('utf-8') if key.repeat_from else None,
                         'make_break': bool(key.make_break), 'repeat': key.repeat}
    return out


def typematic_timing(rate=0, delay=1):
    """keys3483_delay_ms and keys3483_period_ms at SetUp's Typematic Rate and Delay (settings.h's order; Normal
    and Normal by default): [(delay_ms, period_ms)], indexed by class."""
    classes = repeat_classes()['CLASSES']
    delays = ((ctypes.c_uint16 * classes) * 3).in_dll(library(), 'keys3483_delay_ms')
    periods = ((ctypes.c_uint16 * classes) * 2).in_dll(library(), 'keys3483_period_ms')
    return [(delays[delay][c], periods[rate][c]) for c in range(classes)]


@functools.cache
def km():
    """The keymap constants, from keymap.h: km()['SHIFT'] == 1, km()['KEEP'] == 0x80."""
    return constants('keymap.h', 'KM_')


def keymaps():
    """Every registered keymap, the default first, as POINTER(_Keymap)."""
    lib = library()
    return [lib.keymap_at(i) for i in range(lib.keymap_count())]


def keymap_named(name):
    for keymap in keymaps():
        if keymap.contents.name.decode() == name:
            return keymap
    raise KeyError(name)


def entries(keymap):
    """A keymap's own entries, not its base's, as (usage, when, key, mods)."""
    m = keymap.contents
    return [(e.usage, e.when, e.key, e.mods) for e in m.entries[:m.count]]


_BUILT = []  # keymaps made by build_keymap, kept alive for the C side


def build_keymap(entries, base=None, name='test', devices=()):
    """A keymap made here, for tests: entries are (usage, when, key, mods); base is
    POINTER(_Keymap) or None."""
    array = (_Entry * len(entries))(*(_Entry(*e) for e in entries))
    ids = (ctypes.c_uint32 * (len(devices) + 1))(*devices, 0)
    keymap = _Keymap(name.encode(), b'test keymap', b'test', base, ids, array, len(entries))
    _BUILT.append((array, ids, keymap))
    return ctypes.pointer(keymap)


def lookup(keymap, usage, chord, exact=False):
    """(key, mods) of the entry keymap_lookup (or keymap_lookup_exact) finds, or None."""
    lib = library()
    found = (lib.keymap_lookup_exact if exact else lib.keymap_lookup)(keymap, usage, chord)
    return (found.contents.key, found.contents.mods) if found else None


class Terminal:
    """One terminal core: the words of a frame in, the answer out."""

    def __init__(self, eab=True, model=2):
        self._lib = library()
        self._state = ctypes.create_string_buffer(self._lib.term_sizeof())
        self.model = model
        self.has_eab = eab
        self._lib.term_init(self._state, ctypes.byref(_Config(eab, model)))

    def frame(self, words, tx_max=TX_MAX):
        """Feed one frame; return the answer words, or [] when the terminal stays silent."""
        for word in words:
            self._lib.term_rx_word(self._state, word)
        answer = (ctypes.c_uint16 * TX_MAX)()
        count = self._lib.term_rx_end(self._state, answer, min(tx_max, TX_MAX))
        return list(answer[:count])

    def abort(self, words=()):
        """Feed the start of a frame, then drop it, as the firmware does after a receive overrun."""
        for word in words:
            self._lib.term_rx_word(self._state, word)
        self._lib.term_rx_abort(self._state)

    def reset(self, eab=True, model=None):
        """A power-on reset, as the console's r does: the queue wiped, then the power-on reset status. With a
        model, at that model, as a model change's reset does (#110)."""
        self.model = self.model if model is None else model
        self.has_eab = eab
        self._lib.term_init(self._state, ctypes.byref(_Config(eab, self.model)))

    def key(self, code):
        """Queue a scan code; False when the status queue is full."""
        return self._lib.term_key(self._state, code)

    def take_keys(self, limit=None):
        """POLL and POLL_ACK until the queue is empty, or for at most limit statuses:
        the scan codes, in order. A power-on reset is acknowledged and left out."""
        codes = []
        taken = 0
        while self.queued and (limit is None or taken < limit):
            taken += 1
            [status] = self.frame([0x005])  # POLL
            self.frame([0x045])  # POLL_ACK
            if status != 0x00A and status & 0b11 == 0b10:
                codes.append(status >> 2)
        return codes

    def regen(self):
        return ctypes.string_at(self._lib.term_regen(self._state), REGEN_SIZE)

    def eab(self):
        return ctypes.string_at(self._lib.term_eab(self._state), REGEN_SIZE)

    def _get(name):
        return property(lambda self: getattr(self._lib, f'term_{name}')(self._state))

    queued = _get('queued')
    display_gen = _get('display_gen')
    written = _get('written')
    writes = _get('writes')
    ac = _get('ac')
    control = _get('control')
    secondary = _get('secondary')
    clicker = _get('clicker')
    alarms = _get('alarms')
    unknown = _get('unknown')
    last_unknown = _get('last_unknown')
    no_feature = _get('no_feature')
    last_no_feature = _get('last_no_feature')
    del _get


def _plane(data):
    """REGEN_SIZE bytes for the renderer: data padded with zeros, or all zeros for None."""
    data = bytes(data) if data is not None else b''
    return (ctypes.c_uint8 * REGEN_SIZE).from_buffer_copy(data.ljust(REGEN_SIZE, b'\0'))


class Renderer:
    """The firmware's renderer (firmware/core/render.c) on one frame of a regen buffer."""

    def __init__(self, regen, ac, control=0, width=640, settings=None, frame=0, dimmed=False, eab=None, ruler=None,
                 setup=False, flash=False, model=2, setup_cursor=0, lock=None):
        self._lib = library()
        self._layout = _Layout.in_dll(self._lib, _LAYOUTS[width])
        self._state = ctypes.create_string_buffer(self._lib.render_sizeof())
        self._pairs = (ctypes.c_uint32 * (width // 2))()
        self.begin(regen, ac, control, settings, frame, dimmed, eab, ruler, setup, flash, model, setup_cursor, lock)

    def begin(self, regen, ac, control=0, settings=None, frame=0, dimmed=False, eab=None, ruler=None, setup=False,
              flash=False, model=2, setup_cursor=0, lock=None):
        """The next frame on the same renderer, as video.c begins each: whatever the last frame left in it
        mustn't show."""
        self._regen = _plane(regen)
        self._eab = _plane(eab)  # all zeros with no EAB: base colours, as the firmware draws them
        self._settings = _settings(settings)
        u8 = ctypes.POINTER(ctypes.c_uint8)
        (codes, cursor, bar) = lock if lock is not None else (bytes(80), -1, False)
        self._status = (ctypes.c_uint8 * 80).from_buffer_copy(codes)
        inputs = _Frame(ctypes.cast(self._regen, u8), ctypes.cast(self._eab, u8), ac, control,
                        ctypes.pointer(self._settings), frame, dimmed, RULER_OFF if ruler is None else ruler, setup,
                        flash, model, setup_cursor, lock is not None, ctypes.cast(self._status, u8), cursor, bar)
        self._lib.render_frame_begin(self._state, ctypes.byref(self._layout), ctypes.byref(inputs))

    def line(self, y):
        """Line y (0-479) as RGB565 pixels, left to right."""
        self._lib.render_line(self._state, y, self._pairs)
        pixels = []
        for pair in self._pairs:
            pixels += (pair & 0xFFFF, pair >> 16)
        return pixels


def render(regen, ac, control=0, width=640, settings=None, frame=0, dimmed=False, eab=None, ruler=None, setup=False,
           flash=False, model=2, setup_cursor=0, lock=None):
    """The screen as the Fruit Jam draws it: 480 lines of RGB565 pixels. ruler is the Rule key's (#51): None
    (off), or the address counter when it came on. setup is a SetUp frame (#102); flash, Alarm volume Off's
    (#107); model, the host's (#110); setup_cursor, a SetUp frame's cursor cell, and lock, the lock's status line
    as core.Lock.status_line gives it, for a locked frame (#122)."""
    renderer = Renderer(regen, ac, control, width, settings, frame, dimmed, eab, ruler, setup, flash, model,
                        setup_cursor, lock)
    return [renderer.line(y) for y in range(LINES)]


def render_place(ac, model=2):
    """The cell the cursor, and the ruler, are drawn on for address counter ac at the model (render_place)."""
    return library().render_place(ac, model)


def geometry(model):
    """render_geometry(model)'s layout (#110), its numbers by name."""
    found = library().render_geometry(model).contents
    return {name: getattr(found, name) for name in _GEOMETRY}


class Splash:
    """The firmware's splash screen (firmware/core/splash.c), from power-on.

    version and commit are bytes in Latin-1, as the firmware passes liz_version and liz_commit (#132).
    """

    def __init__(self, version=b'test', commit=b'test', now_ms=0):
        self._lib = library()
        self._state = ctypes.create_string_buffer(self._lib.splash_sizeof())
        self._lib.splash_init(self._state, version, commit, now_ms)

    def showing(self, now_ms, written):
        """Whether it still shows; written is the terminal's (Terminal.written)."""
        return self._lib.splash_showing(self._state, now_ms, written)

    def dismiss(self):
        self._lib.splash_dismiss(self._state)

    def line(self, y, width=640, settings=None):
        """Line y (0-479) as RGB565 pixels, left to right, in the settings' splash_colour (#50)."""
        layout = _Layout.in_dll(self._lib, _LAYOUTS[width])
        pairs = (ctypes.c_uint32 * (width // 2))()
        self._lib.splash_line(self._state, ctypes.byref(layout), y, splash_colour(settings), pairs)
        pixels = []
        for pair in pairs:
            pixels += (pair & 0xFFFF, pair >> 16)
        return pixels


def splash_colour(settings=None):
    """The splash's RGB565 colour under the settings (anything with screen.Settings' fields), as video.c picks it
    (firmware/core/splash.c): white, or the phosphor in monochrome (#50)."""
    return library().splash_colour(ctypes.byref(_settings(settings)))


def splash(version=b'test', commit=b'test', width=640, settings=None):
    """The splash screen as the Fruit Jam draws it under the settings: 480 lines of RGB565 pixels."""
    screen = Splash(version, commit)
    return [screen.line(y, width, settings) for y in range(LINES)]


class Keyboard:
    """The keyboard translator (firmware/core/keyboard.c), queueing into a terminal
    core of its own. The terminal's power-on reset is acknowledged at once, so the
    queue starts empty."""

    def __init__(self, keymap=None, sources=(0,)):
        self._lib = library()
        self.terminal = Terminal()
        self.terminal.take_keys()
        self._state = ctypes.create_string_buffer(self._lib.kbd_sizeof())
        self._lib.kbd_init(self._state, self.terminal._state)
        self.last_count = 0
        for src in sources:
            self.attach(src, keymap)

    def attach(self, src=0, keymap=None):
        """keymap: POINTER(_Keymap) from keymap_named or build_keymap; None for the default."""
        self._lib.kbd_attach(self._state, src, keymap if keymap is not None else self._lib.keymap_for(0, 0))

    def report(self, mods=0, usages=(), src=0, ms=0, sent_max=64):
        """One boot report; the codes it queued, up to sent_max (last_count has them all)."""
        data = (ctypes.c_uint8 * 8)(mods, 0, *usages)
        out = (ctypes.c_uint8 * max(sent_max, 1))()
        self.last_count = self._lib.kbd_report(self._state, src, data, ms, out, sent_max)
        return list(out[:min(self.last_count, sent_max)])

    def tick(self, ms):
        self._lib.kbd_tick(self._state, ms)

    def typematic(self, rate, delay):
        """SetUp's Typematic Rate and Delay (#107), as settings.h numbers them."""
        self._lib.kbd_typematic(self._state, rate, delay)

    @property
    def rate(self):
        """The Typematic Rate the next press takes (#107)."""
        return self._lib.kbd_rate(self._state)

    @property
    def delay(self):
        """And its Delay."""
        return self._lib.kbd_delay(self._state)

    def resync(self):
        self._lib.kbd_resync(self._state)

    def release_all(self, src=0):
        self._lib.kbd_release_all(self._state, src)

    def detach(self, src=0):
        self._lib.kbd_detach(self._state, src)

    def stats(self):
        stats = _KbdStats()
        self._lib.kbd_stats(self._state, ctypes.byref(stats))
        return {name: getattr(stats, name) for (name, _) in _KbdStats._fields_}

    def clear_stats(self):
        self._lib.kbd_clear_stats(self._state)

    @property
    def keystrokes(self):
        return self._lib.kbd_keystrokes(self._state)

    @property
    def local_keystrokes(self):
        """The keystrokes that went to SetUp (#107), counted in keystrokes too."""
        return self._lib.kbd_local_keystrokes(self._state)

    @property
    def rule_presses(self):
        """Bare Rule presses, which turn the ruler on and off (#51)."""
        return self._lib.kbd_rule_presses(self._state)

    def local(self, on):
        """SetUp's local mode (#102) on or off."""
        self._lib.kbd_local(self._state, on)

    @property
    def local_on(self):
        return self._lib.kbd_local_on(self._state)

    def local_entries(self):
        """The keys waiting for SetUp, oldest first, taking them: (code, shift) each (#122)."""
        entries = []
        (key, shift) = (ctypes.c_uint8(), ctypes.c_bool())
        while self._lib.kbd_local_key(self._state, ctypes.byref(key), ctypes.byref(shift)):
            entries.append((key.value, shift.value))
        return entries

    def local_keys(self):
        """The keys waiting for SetUp, oldest first, taking them."""
        return [code for (code, _) in self.local_entries()]

    def redact(self, mods=0, names=()):
        """A boot report as the console's u log keeps it (kbd_redact, #122): (mods, the six key bytes)."""
        data = (ctypes.c_uint8 * 8)(mods, 0, *(usages()[name] for name in names))
        self._lib.kbd_redact(self._state, data, 8)
        return (data[0], list(data[2:]))


class Dim:
    """Auto dim (firmware/core/dim.c): off, its timer from ms, with term_writes at writes."""

    def __init__(self, ms=0, writes=0):
        self._lib = library()
        self._state = ctypes.create_string_buffer(self._lib.dim_sizeof())
        self._lib.dim_init(self._state, ms, writes)
        self.took = False

    def tick(self, ms, writes=0, settings=None):
        s = _settings(settings)
        self._lib.dim_tick(self._state, ctypes.byref(s), ms, writes)

    def due(self, ms, writes=0, settings=None):
        """Whether tick would turn it on now (#122)."""
        s = _settings(settings)
        return self._lib.dim_due(self._state, ctypes.byref(s), ms, writes)

    def report(self, mods=0, usages=(), src=0, ms=0):
        """One boot report: (mods, usages) as the translator gets it, with the keys masked to wake auto
        dim taken out. took says whether any were."""
        data = (ctypes.c_uint8 * 8)(mods, 0, *usages)
        out = (ctypes.c_uint8 * 8)()
        self.took = self._lib.dim_report(self._state, src, ms, data, out)
        return (out[0], [usage for usage in out[2:] if usage])

    def activity(self, ms):
        self._lib.dim_activity(self._state, ms)

    def forget(self, src=0):
        self._lib.dim_forget(self._state, src)

    def now(self):
        self._lib.dim_now(self._state)

    @property
    def on(self):
        return self._lib.dim_on(self._state)


class Beep:
    """When to sound (firmware/core/beep.c), with the counts last seen starting at alarms, keystrokes and local."""

    def __init__(self, alarms=0, keystrokes=0, local=0):
        self._lib = library()
        self._state = ctypes.create_string_buffer(self._lib.beep_sizeof())
        self._lib.beep_init(self._state, alarms, keystrokes, local)

    def poll(self, ms, alarms, keystrokes, clicker, local=0, settings=None):
        """What to sound at ms: beep.h's BEEP_NONE, BEEP_CLICK, BEEP_ALARM or BEEP_FLASH. keystrokes is every
        keystroke, local SetUp's among them; settings is a screen.Settings, the defaults for None."""
        s = _settings(settings)
        return self._lib.beep_poll(self._state, ms, alarms, keystrokes, local, clicker, ctypes.byref(s))

    def start(self, ms, sound):
        self._lib.beep_start(self._state, ms, sound)

    def cancel(self):
        self._lib.beep_cancel(self._state)

    def preview(self):
        """SetUp's Alarm volume preview (#107): the next alarm starts whatever sounds or shows."""
        self._lib.beep_preview(self._state)

    def length(self, sound):
        return self._lib.beep_length(self._state, sound)

    def set_length(self, sound, ms):
        self._lib.beep_set_length(self._state, sound, ms)

    @property
    def swallowed(self):
        return self._lib.beep_swallowed(self._state)


class UsbFault:
    """Revision A's USB fault flag (firmware/core/usb_fault.c): trips counted, none yet."""

    def __init__(self):
        self._lib = library()
        self._state = ctypes.create_string_buffer(self._lib.usb_fault_sizeof())
        self._lib.usb_fault_init(self._state)

    def poll(self, ms, low=False, fell=False):
        """The flag at ms: low now, and whether its pin fell since the last poll."""
        self._lib.usb_fault_poll(self._state, ms, low, fell)

    @property
    def trips(self):
        return self._lib.usb_fault_trips(self._state)


class ModelChange:
    """A model change on the coax (firmware/core/model_change.c, #110): none under way."""

    def __init__(self):
        self._lib = library()
        self._state = ctypes.create_string_buffer(self._lib.model_change_sizeof())
        self._lib.model_change_init(self._state)

    def poll(self, ms, live, link, offline=False, held=False, pending=False):
        """What to post at ms (model_change.h's MODEL_CHANGE_NONE, _OFFLINE or _ONLINE): the live record's
        model, the link's, whether the link is offline, whether offline setup holds it offline, and whether a
        request is still on its way to core 1."""
        return self._lib.model_change_poll(self._state, ms, live, link, offline, held, pending)

    @property
    def power_ons(self):
        return self._lib.model_change_power_ons(self._state)


class Ruler:
    """The Rule key's ruler (firmware/core/ruler.c, #51): off, with presses seen."""

    def __init__(self, presses=0):
        self._lib = library()
        self._state = _Ruler()
        self._lib.ruler_init(ctypes.byref(self._state), presses)

    def toggle(self, ac):
        self._lib.ruler_toggle(ctypes.byref(self._state), ac)

    def poll(self, presses, ac, follows=False, model=2):
        """One toggle for each press since the last poll, at ac; while it follows, it keeps up with ac. model is
        the screen the controller drives (#110)."""
        self._lib.ruler_poll(ctypes.byref(self._state), presses, ac, follows, model)

    @property
    def at(self):
        """RULER_OFF, or the address counter when it came on."""
        return self._state.at


def ruler_address(at, ac, follows):
    """The address counter the ruler goes by (ruler_address), or RULER_OFF."""
    return library().ruler_address(at, ac, follows)


class SetupUi:
    """SetUp's screens and keys (firmware/core/setup_ui.c, #102), with live settings of their own (anything with
    screen.Settings' fields, or the core's defaults): off at first."""

    def __init__(self, settings=None):
        self._lib = library()
        self._state = ctypes.create_string_buffer(self._lib.setup_ui_sizeof())
        self._lib.setup_ui_init(self._state)
        self._settings = _settings(settings)

    def open(self):
        self._lib.setup_ui_open(self._state)

    def identify(self, version, commit, board):
        """About's page 1 (#126): the version, commit and board, each cut to fit its field by the core."""
        self._lib.setup_ui_identify(self._state, version.encode('latin-1'), commit.encode('latin-1'),
                                    board.encode('latin-1'))

    def key(self, key, shift=False):
        """One key, a 3483-V code or its keys3483.h name ('DOWN', 'PF3'), with Shift or not (#122): SETUP_UI_NONE,
        _ALARM, _CHANGED, _CLOSED, _PREVIEW, _LEFT_OFFLINE, _PASSWORD_SET or _PASSWORD_CLEARED."""
        code = scan_codes()[key] if isinstance(key, str) else key
        return self._lib.setup_ui_key(self._state, code, shift, ctypes.byref(self._settings))

    @property
    def cursor_at(self):
        """Password Set's cursor cell, or 0 on any other screen (#122)."""
        return self._lib.setup_ui_cursor_at(self._state)

    @property
    def cursor(self):
        """The front image's cursor cell, as the last draw left it."""
        return self._lib.setup_ui_cursor(self._state)

    @property
    def screen(self):
        return self._lib.setup_ui_screen(self._state)

    @property
    def offline(self):
        """Whether offline setup is up (#110): its menu or Customization."""
        return self._lib.setup_ui_offline(self._state)

    @property
    def selector_at(self):
        """The address of the selected item's or choice's first cell; 0 while it's off."""
        return self._lib.setup_ui_selector_at(self._state)

    @property
    def settings(self):
        """The live settings, field by field."""
        return _fields(self._settings)

    def set(self, **fields):
        for (name, value) in fields.items():
            setattr(self._settings, name, value)

    def stats(self):
        stats = _SetupUiStats()
        self._lib.setup_ui_stats(self._state, ctypes.byref(stats))
        return {name: getattr(stats, name) for (name, _) in _SetupUiStats._fields_}

    def draw(self):
        self._lib.setup_ui_draw(self._state, ctypes.byref(self._settings))

    def regen(self):
        """The front image's display codes: the status line at 0-79, the rows from 80."""
        return ctypes.string_at(self._lib.setup_ui_regen(self._state), SETUP_UI_CELLS)

    def eab(self):
        return ctypes.string_at(self._lib.setup_ui_eab(self._state), SETUP_UI_CELLS)

    @property
    def front(self):
        """The front image's address, so a test can see a draw leave it alone."""
        return ctypes.cast(self._lib.setup_ui_regen(self._state), ctypes.c_void_p).value


class Lock:
    """Lock sessions (firmware/core/lock.c, #122): off at first."""

    def __init__(self):
        self._lib = library()
        self._state = ctypes.create_string_buffer(self._lib.lock_sizeof())
        self._lib.lock_clear(self._state)

    def engage(self):
        self._lib.lock_engage(self._state)

    @property
    def state(self):
        """LOCK_OFF, LOCK_BLACK or LOCK_PROMPT."""
        return self._lib.lock_state(self._state)

    def key(self, key, shift=False, password=0):
        """One key, a 3483-V code or its keys3483.h name, against password (the live record's hash): LOCK_NONE,
        _REDRAW, _ALARM or _UNLOCKED."""
        code = scan_codes()[key] if isinstance(key, str) else key
        return self._lib.lock_key(self._state, code, shift, password)

    def status_line(self):
        """(codes, cursor, bar): the 80 display codes the status line shows, the prompt's cursor column or -1, and
        whether it's SetUp's white bar."""
        line = _LockLine()
        self._lib.lock_status_line(self._state, ctypes.byref(line))
        return (bytes(line.codes), line.cursor, line.bar)

    def stats(self):
        stats = _LockStats()
        self._lib.lock_stats(self._state, ctypes.byref(stats))
        return {name: getattr(stats, name) for (name, _) in _LockStats._fields_}


def lock_dim_due(settings=None, locked=False):
    """What auto dim's delay means under the settings (#122): LOCK_DIM_BLANK, _LOCK or _NONE."""
    return library().lock_dim_due(ctypes.byref(_settings(settings)), locked)
