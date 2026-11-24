# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""What the 3483-V shows for a regen buffer, as text and as PNG.

The screen is addresses 80-1999, 24 rows of 80. The status line is 0-79, and
the terminal draws it at the bottom under a rule (captured Oct 3, 2026).
Field attributes are codes 0xC0-0xFF in the screen area: each shows as a
blank and governs the cells after it, wrapping from 1999 back to 80.
"""

import functools
import os
from typing import NamedTuple

from display_codes import MAIN, OVERBARRED, PLACEHOLDER, STATUS

COLS = 80
ROWS = 24
SCREEN_START = 80
SCREEN_END = 2000
RULE = '─' * COLS


class Geometry(NamedTuple):
    """A model's layout on the Fruit Jam (render.h's render_geometry_t, #110): rows of cell_h lines from line top,
    a 5-line gap that holds the 2-line rule, then a status line one cell tall at the bottom. The spare lines of
    a shorter screen are a blank band at the top."""
    rows: int
    cell_h: int
    top: int
    cursor_lines: tuple  # the underscore cursor's lines in a cell, and the horizontal ruler's: the last two, or
                         # the last one at 10 lines, where line 7 holds the letters' bottom row

    @property
    def screen_end(self):
        return SCREEN_START + self.rows * COLS

    @property
    def gap_y(self):
        return self.top + self.rows * self.cell_h

    @property
    def rule_lines(self):
        return (self.gap_y + 1, self.gap_y + 2)

    @property
    def status_y(self):
        return self.gap_y + 5

    @property
    def underscore_line(self):
        """An EAB underscore's line in a cell: the one above the cursor's."""
        return self.cursor_lines[0] - 1


MODELS = {2: Geometry(24, 19, 0, (17, 18)), 3: Geometry(32, 14, 13, (12, 13)), 4: Geometry(43, 10, 35, (9,))}


def geometry(model):
    """A model's layout: 3's and 4's, anything else Model 2's, as render.c's render_geometry."""
    return MODELS.get(model, MODELS[2])

# Display bits 3-2 of an attribute (oec writes 0xC0 | (attr & 0x2C)).
NORMAL = 0b00
PEN_DETECTABLE = 0b01
INTENSIFIED = 0b10
NON_DISPLAY = 0b11


class Field(NamedTuple):
    protected: bool
    display: int


UNFORMATTED = Field(protected=False, display=NORMAL)


def is_attribute(code):
    return code >= 0xC0


def field_of_attribute(attribute):
    return Field(protected=bool(attribute & 0x20), display=(attribute >> 2) & 0b11)


def fields(regen, model=2):
    """The field governing each screen cell at the model's size (#110), indexed by address.

    None for the status line and for the attribute cells themselves.
    """
    end = geometry(model).screen_end
    attributes = [a for a in range(SCREEN_START, end) if is_attribute(regen[a])]
    current = field_of_attribute(regen[attributes[-1]]) if attributes else UNFORMATTED
    governing = [None] * end
    for address in range(SCREEN_START, end):
        if is_attribute(regen[address]):
            current = field_of_attribute(regen[address])
        else:
            governing[address] = current
    return governing


def visible(field):
    return field is not None and field.display != NON_DISPLAY


def fold_case(code):
    """Mono case (#107): a code as the 3483-V draws it with Mono case Yes, 40-5F as 60-7F and 80-9F as A0-BF."""
    return code | 0x20 if (code & 0xE0) in (0x40, 0x80) else code


class Look(NamedTuple):
    code: int        # the display code drawn: 0x00 when blanked or blinked out
    colour: tuple    # RGB
    highlight: int   # HIGHLIGHT_NONE, HIGHLIGHT_REVERSE or HIGHLIGHT_UNDERSCORE: blink is worked out already


def eab_blink_out(frame):
    """Whether EAB blink's glyphs are out on this frame: 16 frames in 64."""
    return (frame // BLINK_FRAMES) % 4 == EAB_BLINK_OUT


def cell_looks(regen, eab=None, frame=0, blank=False, settings=None, setup=False, model=2):
    """What each screen cell shows (#70), indexed by address; None below 80, the status line.

    The attribute in force carries its EAB byte: its colour and highlight cover the field, and a cell's own
    non-zero colour or highlight replaces the field's. An attribute cell is blank, in an unformatted
    screen's colour, as a block cursor shows it. Non-display, blank (display inhibit or auto dim) and blink's
    out frames blank the glyph and drop the highlight; the cell keeps its colour for a block cursor.

    Each cell's colour is cell_colour's, under the settings' mapping or in monochrome (#50). With Mono case and
    not SetUp's frame (#107), each code is fold_case's. The screen is the model's (#110).
    """
    end = geometry(model).screen_end
    eab = eab if eab is not None else bytes(end)
    attributes = [a for a in range(SCREEN_START, end) if is_attribute(regen[a])]
    at = attributes[-1] if attributes else None
    looks = [None] * end
    for address in range(SCREEN_START, end):
        if is_attribute(regen[address]):
            at = address
            looks[address] = Look(0x00, cell_colour(UNFORMATTED, 0, settings), HIGHLIGHT_NONE)
            continue
        (field, field_eab) = (field_of_attribute(regen[at]), eab[at]) if at is not None else (UNFORMATTED, 0)
        own = eab[address]
        colour = (own >> 3 & 7) or (field_eab >> 3 & 7)
        highlight = (own >> 6) or (field_eab >> 6)
        code = fold_case(regen[address]) if (settings or DEFAULT_SETTINGS).mono_case and not setup else regen[address]
        if blank or not visible(field):
            (code, highlight) = (0x00, HIGHLIGHT_NONE)
        elif highlight == HIGHLIGHT_BLINK:
            (code, highlight) = (0x00 if eab_blink_out(frame) else code, HIGHLIGHT_NONE)
        looks[address] = Look(code, cell_colour(field, colour, settings), highlight)
    return looks


def screen_rows(regen, model=2):
    geo = geometry(model)
    governing = fields(regen, model)
    cells = [MAIN.get(regen[a], PLACEHOLDER) if visible(governing[a]) else ' '
             for a in range(SCREEN_START, geo.screen_end)]
    return [''.join(cells[row * COLS:(row + 1) * COLS]) for row in range(geo.rows)]


def status_text(regen, fold=False):
    return ''.join(STATUS[fold_case(regen[a]) if fold else regen[a]] for a in range(COLS))


def cursor_position(ac, model=2):
    """(row, column) counted from 1, as the terminal shows them; None off the model's screen."""
    if SCREEN_START <= ac < geometry(model).screen_end:
        (row, col) = divmod(ac - SCREEN_START, COLS)
        return (row + 1, col + 1)
    return None


def cursor_indicator(ac, model=2):
    """The terminal's own position display at the right of its status line: 0023/017."""
    position = cursor_position(ac, model)
    return f'{position[0]:04d}/{position[1]:03d}' if position else None


OFFSCREEN_CURSOR = 1023  # where the 3483-V draws the cursor while the counter is off the screen (Oct 6, #49)
# Auto dim: the 24 rows blank, RRRR/CCC goes and display code 1F replaces status column 71 (Oct 5 and 6).
DIM_MARK = 0x1F
DIM_MARK_COL = 71


def cursor_place(ac, model=2):
    """The cell the cursor is drawn on: the counter while it's on the model's screen, else address 1023 (row
    12, column 64). There is never a cursor on the status line."""
    return ac if SCREEN_START <= ac < geometry(model).screen_end else OFFSCREEN_CURSOR


def cursor_look(control, settings=None, frame=0):
    """(shown, block): bit 1 toggles the Cursor Style setting and bit 0 its Blink, and a blinking cursor is
    out on the second BLINK_FRAMES of each two."""
    settings = settings or DEFAULT_SETTINGS
    block = (settings.cursor == BLOCK) != bool(control & REVERSE_CURSOR)
    blinking = settings.cursor_blink != bool(control & BLINK)
    out = blinking and (frame // BLINK_FRAMES) % 2 == 1
    return (not control & CURSOR_INHIBIT and not out, block)


def describe_cursor(ac, model=2):
    if cursor_indicator(ac, model):
        return f'cursor {cursor_indicator(ac, model)}'
    if ac < SCREEN_START:
        return f'cursor on the status line, column {ac + 1}'
    return f'cursor at {ac}, off the screen'


def text(regen, ac, model=2):
    return '\n'.join([*screen_rows(regen, model), RULE, status_text(regen), describe_cursor(ac, model)]) + '\n'


def write_text(path, regen, ac, model=2):
    with open(path, 'w', encoding='utf-8') as stream:
        stream.write(text(regen, ac, model))


# The PNG: Pillow and the vendored 3270font subset (fonts/, see subset_font.py).

FONTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
# Advance 9.7 px in a 10 x 20 cell. The ink runs from 16 px above the baseline
# (the accented capitals) to 5 below (the cedilla of ç), a row more than the
# cell, so the accents get the row and the cedilla's tip is cut.
FONT_SIZE = 18
CELL_WIDTH = 10
CELL_HEIGHT = 20
BASELINE = 16
RULE_GAP = 3
RULE_HEIGHT = 2
RULE_TOP = ROWS * CELL_HEIGHT + RULE_GAP
STATUS_TOP = RULE_TOP + RULE_HEIGHT + RULE_GAP
WIDTH = COLS * CELL_WIDTH
HEIGHT = STATUS_TOP + CELL_HEIGHT
EAB_UNDERSCORE = CELL_HEIGHT - 4  # the EAB underscore's line, one above the cursor's (#70)

# LizTerm's palette (concept.md).
GREEN = (0x50, 0xFF, 0x50)
RED = (0xFF, 0x50, 0x50)
BLUE = (0x5C, 0x8A, 0xFF)
WHITE = (0xF0, 0xF0, 0xF0)
BLACK = (0x00, 0x00, 0x00)
# The rule and the status line under it, in one colour as on the 3483-V (#95),
# which keeps it blue under any colour mapping (Oct 10, #50).
STATUS_COLOUR = BLUE

# EAB (#70, captured Oct 7: docs/upstream-review.md, "Display codes and
# attributes"). Pink, turquoise and yellow are LizTerm's too. EAB_COLOURS is by
# bits 5-3 of an EAB byte, and HIGHLIGHT_* are its bits 7-6; 0 in either takes
# the field's.
PINK = (0xFF, 0x70, 0xFF)
TURQUOISE = (0x50, 0xFF, 0xFF)
YELLOW = (0xFF, 0xFF, 0x50)
EAB_COLOURS = (None, BLUE, RED, PINK, GREEN, TURQUOISE, YELLOW, WHITE)
# The EAB colour codes by name: SetUp's colour mapping holds them (#50).
(EAB_BLUE, EAB_RED, EAB_PINK, EAB_GREEN, EAB_TURQUOISE, EAB_YELLOW, EAB_WHITE) = range(1, 8)
HIGHLIGHT_NONE = 0
HIGHLIGHT_BLINK = 1
HIGHLIGHT_REVERSE = 2
HIGHLIGHT_UNDERSCORE = 3
# Monochrome (#50): LizTerm's phosphor, and intensified text blended 35% toward
# white, as its Palette.cs Blend does (@ 4e4fada).
PHOSPHOR = (0x33, 0xFF, 0x33)
PHOSPHOR_BRIGHT = (0x7A, 0xFF, 0x7A)

# The terminal's local settings (firmware/core/settings.h): what the 3483-V's
# SetUp sets on its Display Setup pages, with this 3483-V's values as the
# defaults (captures/photos-20261006/setup-1-display-cursor-autodim.jpg,
# setup-3-display-colour-mapping.jpg), and monochrome, which it lacks (#50),
# and the Rule key's ruler (#51).
UNDERLINE = 0
BLOCK = 1
DIM_MINUTES = (5, 10, 20)
# SetUp's Rule line Style (#51), in its order (settings.h's settings_ruler_t).
(RULER_HORIZONTAL, RULER_VERTICAL, RULER_CROSS, RULER_NONE) = range(4)
# SetUp's Typematic Rate and Delay (#107), in its order (settings.h's settings_rate_t and settings_delay_t).
(RATE_NORMAL, RATE_FAST) = range(2)
(DELAY_SHORT, DELAY_NORMAL, DELAY_LONG) = range(3)
RULER_OFF = 0xFFFF  # ruler.h: the ruler is off
# The Fruit Jam's geometry, where the ruler is drawn (render.h), not this module's PNG cells.
VIDEO_CELL_H = 19                          # RENDER_CELL_H
VIDEO_SCREEN_LINES = ROWS * VIDEO_CELL_H   # 456: rows 1-24, above the gap
CURSOR_LINES = (17, 18)                    # the underline cursor's lines in a cell, and the horizontal ruler's
# SetUp (#102): its title rule is lines 9-10 of row 2 on the Fruit Jam (render.h's RENDER_TITLE_RULE_Y), in the
# status line's colour, and its status line is a bar reversed in white, the phosphor in mono; dimmed, the line
# is blank but for the mark (captured Oct 11).
TITLE_RULE_LINES = (VIDEO_CELL_H + 9, VIDEO_CELL_H + 10)
# Each of SetUp's screens and the keys that open it from the menu on a fresh SetUp: the pictures here, and the
# manual's walk of SetUp's rows (#136), open them by this one table.
SETUP_KEYS = {
    'menu': (),
    'page1': ('DOWN', 'ENTER'),                     # Setup display (#102)
    'page2': ('DOWN', 'ENTER', 'PF8'),
    'page3': ('DOWN', 'ENTER', 'PF8', 'PF8'),
    'page4': ('DOWN', 'ENTER', 'PF8', 'PF8', 'PF8'),
    'warning': ('UP', 'ENTER'),                     # Go to offline setup (#110)
    'offline': ('UP', 'ENTER', 'ENTER'),
    'customize': ('UP', 'ENTER', 'ENTER', 'ENTER'),
    'password': ('DOWN', 'DOWN', 'DOWN', 'ENTER'),  # Set password (#122)
    'about-1': ('PF10',),                           # About (#126), then F8 to the first license page
    'about-2': ('PF10', 'PF8'),
}
SETUP_SCREENS = tuple(SETUP_KEYS)
SIM_IDENTITY = ('0.0.0', 'sim', 'Fruit Jam (ID 11)')  # About's version, commit and board: the sim's stand-in (#126)


class Settings(NamedTuple):
    cursor: int = UNDERLINE    # Cursor Style
    cursor_blink: bool = False
    indicator: bool = True     # Row/column indicator: RRRR/CCC
    auto_dim: bool = True
    dim_minutes: int = 10      # one of DIM_MINUTES
    colour_input: int = EAB_GREEN         # Four base color mapping (#50): what green becomes
    colour_input_hi: int = EAB_RED        # what red becomes
    colour_protected: int = EAB_BLUE      # what blue becomes
    colour_protected_hi: int = EAB_WHITE  # what white becomes
    mono: bool = False                    # monochrome (#50)
    ruler_style: int = RULER_HORIZONTAL   # the Rule key's ruler (#51): Rule line Style
    ruler_colour: int = EAB_WHITE         # Color: EAB_WHITE or EAB_GREEN
    ruler_follows: bool = True            # Follows cursor
    typematic_rate: int = RATE_NORMAL     # Display Setup page 2 (#107): Typematic Rate
    typematic_delay: int = DELAY_NORMAL   # Typematic Delay
    click: bool = True                    # Clicker Click
    click_volume: int = 3                 # Clicker Volume: 0 Off, 1-4, 5 High
    alarm_volume: int = 3                 # Alarm volume
    mono_case: bool = False               # Mono case: the host's lower case drawn as capitals
    model: int = 2                        # offline setup's Screen rows x columns (#110): 2, 3 or 4
    lock_sessions: bool = False           # Display Setup page 1's Lock sessions (#122)
    password: int = 0                     # Password Set's hash (#122): 0 for none


DEFAULT_SETTINGS = Settings()

# SetUp's Four base color mapping (#50, captured Oct 10): each slot holds the
# colour one base colour is drawn as, wherever it comes from, a field
# attribute or an EAB byte. Pink, turquoise and yellow are drawn as sent.
SLOTS = {EAB_GREEN: 'colour_input', EAB_RED: 'colour_input_hi', EAB_BLUE: 'colour_protected',
         EAB_WHITE: 'colour_protected_hi'}


@functools.lru_cache
def palette(settings=None):
    """The RGB each EAB colour code is drawn as under the settings' mapping, by code; None at 0. Each colour
    is swapped once. A slot holding a colour SetUp doesn't offer keeps its own, as render.c does."""
    settings = settings or DEFAULT_SETTINGS
    colours = list(EAB_COLOURS)
    for (code, slot) in SLOTS.items():
        chosen = getattr(settings, slot)
        colours[code] = EAB_COLOURS[chosen if EAB_BLUE <= chosen <= EAB_WHITE else code]
    return tuple(colours)


def ruler_address(at, ac, follows):
    """ruler.c's ruler_address: the address counter the ruler goes by, ac when it follows the cursor and at
    (where it came on) when it doesn't, or RULER_OFF while it's off."""
    if at == RULER_OFF:
        return RULER_OFF
    return ac if follows else at


def ruler_place(ac, ruler, settings=None, model=2):
    """The cell the ruler goes through (#51), placed as the cursor is (cursor_place), or None while it's off or
    its Style draws nothing. ruler is RULER_OFF or the address counter when it came on."""
    settings = settings or DEFAULT_SETTINGS
    address = ruler_address(ruler, ac, settings.ruler_follows)
    if address == RULER_OFF or settings.ruler_style not in (RULER_HORIZONTAL, RULER_VERTICAL, RULER_CROSS):
        return None
    return cursor_place(address, model)


def ruler_colour(settings=None):
    """The ruler's RGB: the cursor's white, or for Green the field green before any mapping; the phosphor in
    monochrome (#50). A colour SetUp doesn't offer is white, as in render.c."""
    settings = settings or DEFAULT_SETTINGS
    if settings.mono:
        return PHOSPHOR
    return GREEN if settings.ruler_colour == EAB_GREEN else WHITE


def ruler_dots(ac, ruler, settings=None, width=640, control=0, frame=0, model=2):
    """The pixels (x, y) the ruler lights on the Fruit Jam's width x 480 screen (#51), as render.c draws it, at
    the model's layout (#110).

    Horizontal: the cursor's lines of its cell's row, where x mod 4 is 0 or 1, across the whole line. Vertical:
    the first pixel column of its cell, on even lines of the rows, never the band, the gap, the rule or the
    status line. Cross: both. While the cursor shows, its cell is left out on the lines it draws (the
    underscore's, or every line for the block), so the cursor shows whole over the ruler.
    """
    settings = settings or DEFAULT_SETTINGS
    geo = geometry(model)
    place = ruler_place(ac, ruler, settings, model)
    if place is None:
        return set()
    (row, col) = divmod(place - SCREEN_START, COLS)
    cell_w = 9 if width == 720 else 8
    dots = set()
    if settings.ruler_style in (RULER_HORIZONTAL, RULER_CROSS):
        dots |= {(x, geo.top + row * geo.cell_h + line) for line in geo.cursor_lines for x in range(width)
                 if x % 4 < 2}
    if settings.ruler_style in (RULER_VERTICAL, RULER_CROSS):
        dots |= {(col * cell_w, y) for y in range(geo.top, geo.gap_y) if y % 2 == 0}
    (shown, block) = cursor_look(control, settings, frame)
    if shown:
        (cursor_row, cursor_col) = divmod(cursor_place(ac, model) - SCREEN_START, COLS)
        lines = range(geo.cell_h) if block else geo.cursor_lines
        dots -= {(cursor_col * cell_w + x, geo.top + cursor_row * geo.cell_h + line) for x in range(cell_w)
                 for line in lines}
    return dots


def field_code(field):
    """A field's base colour as an EAB colour code: green, red, blue or white by protection and intensify."""
    if field is None:
        return EAB_GREEN
    intensified = field.display == INTENSIFIED
    if field.protected:
        return EAB_WHITE if intensified else EAB_BLUE
    return EAB_RED if intensified else EAB_GREEN


def phosphor(field):
    """Monochrome's colour for a cell in field: brighter in an intensified field, whatever its EAB colour."""
    return PHOSPHOR_BRIGHT if field is not None and field.display == INTENSIFIED else PHOSPHOR


def status_colour(settings=None):
    """The rule and the status line: blue under any mapping, as on the 3483-V (Oct 10); the phosphor in mono."""
    return PHOSPHOR if (settings or DEFAULT_SETTINGS).mono else STATUS_COLOUR


def cursor_colour(settings=None):
    """The cursor's underscore: white under any mapping, as on the 3483-V (Oct 10); the phosphor in mono."""
    return PHOSPHOR if (settings or DEFAULT_SETTINGS).mono else WHITE


def splash_colour(settings=None):
    """The splash's text and logo (firmware/core/splash.c): white, or the phosphor in mono (#50)."""
    return PHOSPHOR if (settings or DEFAULT_SETTINGS).mono else WHITE


def setup_bar_colour(settings=None):
    """SetUp's status line bar (#102): white, or the phosphor in mono."""
    return PHOSPHOR if (settings or DEFAULT_SETTINGS).mono else WHITE


def setup_screens(settings=None, identity=SIM_IDENTITY):
    """SetUp's eleven screens as setup_ui.c draws them (#102, #110, #122, #126), each as SETUP_KEYS opens it, its
    selector on its first choice: {name: (regen, eab, cursor)} in SETUP_SCREENS' order, cursor being the image's
    cursor cell (Password Set's, 0 on the rest). About shows identity, (version, commit, board) as
    setup_ui_identify takes them."""
    import core

    images = {}
    for (name, keys) in SETUP_KEYS.items():
        ui = core.SetupUi(settings)
        ui.identify(*identity)
        ui.open()
        for key in keys:
            ui.key(key)
        ui.draw()
        images[name] = (ui.regen(), ui.eab(), ui.cursor)
    return images


def setup_images(settings=None):
    """setup_screens without the cursors: {name: (regen, eab)}."""
    return {name: (regen, eab) for (name, (regen, eab, _)) in setup_screens(settings).items()}

# Control register bits (docs/upstream-review.md). Display inhibit blanks the
# 24 rows; the cursor, rule and status line stay, as on the 3483-V. Bit 1
# toggles the Cursor Style setting and bit 0 its Blink (captured Oct 6).
DISPLAY_INHIBIT = 0b1000
CURSOR_INHIBIT = 0b100
REVERSE_CURSOR = 0b010
BLINK = 0b001
BLINK_FRAMES = 16  # a blinking cursor: lit this many frames, then out as many (533 ms a cycle, Oct 5)
EAB_BLINK_OUT = 3  # EAB blink: out on the last BLINK_FRAMES of each 64 frames, in one of the cursor's out phases (Oct 7)

_font = None
_covered = None
_masks = {}


class PillowMissing(ImportError):
    pass


def check_pillow():
    """Raise PillowMissing, saying what to install, if the PNG can't be drawn.

    The PNG imports Pillow only when it first draws, so a tool checks first
    rather than fail at its first screen, or at the end of a replay.
    """
    try:
        import PIL  # noqa: F401
    except ImportError as error:
        raise PillowMissing('the PNG needs Pillow: pip install -r tools/sim/requirements.txt') from error


def covered():
    """The characters the font subset can draw; others get a box."""
    global _covered
    if _covered is None:
        with open(os.path.join(FONTS, 'covered.txt'), encoding='ascii') as stream:
            _covered = {chr(int(line, 16)) for line in stream if line.strip()}
    return _covered


def _load_font():
    global _font
    if _font is None:
        from PIL import ImageFont

        _font = ImageFont.truetype(os.path.join(FONTS, '3270-Regular.ttf'), FONT_SIZE)
    return _font


def cell_colour(field, code=0, settings=None):
    """A cell's colour from its field and its EAB colour code (0 for the field's), as render.c's cell_colour:
    the settings' palette, or in monochrome the phosphor, brighter in an intensified field whatever the
    code (#50). With a field alone, the field's base colour."""
    settings = settings or DEFAULT_SETTINGS
    if settings.mono:
        return phosphor(field)
    return palette(settings)[code or field_code(field)]


def _mask(glyph):
    """The glyph's coverage of one cell, cut to the cell; drawn once per glyph."""
    mask = _masks.get(glyph)
    if mask is None:
        from PIL import Image, ImageDraw

        mask = Image.new('L', (CELL_WIDTH, CELL_HEIGHT), 0)
        ImageDraw.Draw(mask).text((0, BASELINE), glyph, font=_load_font(), fill=255, anchor='ls')
        _masks[glyph] = mask
    return mask


def _cell(image, draw, x, y, glyph, colour, overbar=False, reverse=False):
    if reverse:
        draw.rectangle([x, y, x + CELL_WIDTH - 1, y + CELL_HEIGHT - 1], fill=colour)
        colour = BLACK
    if glyph == ' ':
        return
    if glyph not in covered():
        # A status line symbol with no glyph to draw: a box in its place.
        draw.rectangle([x + 2, y + 4, x + CELL_WIDTH - 3, y + CELL_HEIGHT - 5], outline=colour)
        return
    image.paste(colour, (x, y, x + CELL_WIDTH, y + CELL_HEIGHT), _mask(glyph))
    if overbar:
        draw.line([x + 1, y + 2, x + CELL_WIDTH - 2, y + 2], fill=colour)


def render(regen, ac, control=0, settings=None, frame=0, dimmed=False, eab=None, setup=False, flash=False, model=2):
    """The screen as the 3483-V draws it, as a Pillow image. With setup, SetUp's frame (#102): no cursor or
    indicator, the status line as its bar, and its title rule; the host's control register has no say in it.
    With flash, Alarm volume Off's flash (#107): every cell's reverse flipped; not while dimmed. The host's
    screen has the model's rows (#110); SetUp's is Model 2's."""
    from PIL import Image, ImageDraw

    settings = settings or DEFAULT_SETTINGS
    control = 0 if setup else control
    model = 2 if setup else model
    geo = geometry(model)
    rule_top = geo.rows * CELL_HEIGHT + RULE_GAP
    status_top = rule_top + RULE_HEIGHT + RULE_GAP
    image = Image.new('RGB', (WIDTH, status_top + CELL_HEIGHT), BLACK)
    draw = ImageDraw.Draw(image)
    place = cursor_place(ac, model)
    (shown, block) = cursor_look(control, settings, frame)
    cursor = place if shown and not setup else None
    inhibit = bool(control & DISPLAY_INHIBIT) or dimmed
    flash = flash and not dimmed
    looks = cell_looks(regen, eab, frame, inhibit, settings, setup, model)

    cursor_cell = None
    for address in range(SCREEN_START, geo.screen_end):
        (row, col) = divmod(address - SCREEN_START, COLS)
        (x, y) = (col * CELL_WIDTH, row * CELL_HEIGHT)
        look = looks[address]
        # A block cursor inverts the cell as drawn (#70): on a reverse cell, the two together draw it plain.
        inverted = ((look.highlight == HIGHLIGHT_REVERSE) != (block and address == cursor)) != flash
        _cell(image, draw, x, y, MAIN.get(look.code, PLACEHOLDER), look.colour,
              overbar=look.code in OVERBARRED, reverse=inverted)
        if look.highlight == HIGHLIGHT_UNDERSCORE:
            draw.line([x, y + EAB_UNDERSCORE, x + CELL_WIDTH - 1, y + EAB_UNDERSCORE],
                      fill=BLACK if inverted else look.colour)
        if address == cursor:
            cursor_cell = (x, y)

    draw.rectangle([0, rule_top, WIDTH - 1, rule_top + RULE_HEIGHT - 1], fill=status_colour(settings))

    fold = settings.mono_case and not setup
    status = list(status_text(regen, fold))
    indicator = cursor_indicator(place, model) if settings.indicator and not dimmed and not setup else None
    if indicator:
        status[COLS - len(indicator):] = indicator
    if setup and dimmed:
        status = [' '] * COLS
    if dimmed:
        status[DIM_MARK_COL] = STATUS[DIM_MARK]
    colour = setup_bar_colour(settings) if setup and not dimmed else status_colour(settings)
    for (col, glyph) in enumerate(status):
        from_regen = (not indicator or col < COLS - len(indicator)) and not (dimmed and col == DIM_MARK_COL)
        _cell(image, draw, col * CELL_WIDTH, status_top, glyph, colour,
              overbar=from_regen and (fold_case(regen[col]) if fold else regen[col]) in OVERBARRED,
              reverse=(setup and not dimmed) != flash)
    if setup and not dimmed:
        top = CELL_HEIGHT + CELL_HEIGHT // 2 - 1
        draw.rectangle([0, top, WIDTH - 1, top + RULE_HEIGHT - 1], fill=status_colour(settings))

    # The underscore is white in any field and under any mapping (captures/photos-20261004/exit-3483v-logon.jpg,
    # photos-20261010/mapping-eab-01-colours.jpg), or the phosphor in mono, below an EAB underscore (#70, #50).
    if cursor_cell and not block:
        (x, y) = cursor_cell
        draw.rectangle([x, y + CELL_HEIGHT - 3, x + CELL_WIDTH - 1, y + CELL_HEIGHT - 2], fill=cursor_colour(settings))
    return image


def write_png(path, regen, ac, control=0, settings=None, frame=0, dimmed=False, eab=None, setup=False, flash=False,
              model=2):
    render(regen, ac, control, settings, frame, dimmed, eab, setup, flash, model).save(path)


def write_video_png(path, regen, ac, control=0, width=640, settings=None, frame=0, dimmed=False, eab=None,
                    setup=False, flash=False, model=2, ruler=None):
    """The screen as the Fruit Jam draws it (firmware/core/render.c), at width x 480, with the Rule key's ruler
    (#51) if given: the address counter when it came on.

    RGB565 is widened to 8 bits with zeros, as HSTX does.
    """
    import core

    _save_rgb565(path, core.render(regen, ac, control, width, settings, frame, dimmed, eab, ruler, setup, flash,
                                   model=model), width)


def write_splash_png(path, width=640, version=SIM_IDENTITY[0].encode('latin-1'),
                     commit=SIM_IDENTITY[1].encode('latin-1'), settings=None):
    """The splash screen as the Fruit Jam draws it from power-on (firmware/core/splash.c), at width x 480, with
    version and commit as Latin-1 bytes: the sim's stand-in unless given."""
    import core

    _save_rgb565(path, core.splash(version, commit, width, settings), width)


def write_setup_pngs(out_dir, width=640, settings=None, identity=SIM_IDENTITY):
    """SetUp's screens as the Fruit Jam draws them (#102, #110, #122, #126), at width x 480, About with identity
    as setup_screens takes it: out_dir/setup-NAME-WIDTH.png for each of SETUP_SCREENS. Returns the paths."""
    import core

    paths = []
    for (name, (regen, eab, cursor)) in setup_screens(settings, identity).items():
        path = os.path.join(out_dir, f'setup-{name}-{width}.png')
        _save_rgb565(path, core.render(regen, SCREEN_START, 0, width, settings, 0, False, eab, None, True,
                                       setup_cursor=cursor), width)
        paths.append(path)
    return paths


def write_lock_pngs(out_dir, width=640, settings=None):
    """The lock as the Fruit Jam draws it (#122) over a blank host screen with the cursor at row 1, column 1, at
    width x 480: out_dir/lock-WIDTH.png locked, and lock-prompt-WIDTH.png with the prompt up and three keys typed.
    Returns the paths."""
    import core

    lock = core.Lock()
    lock.engage()
    lines = {'lock': lock.status_line()}
    lock.key('A')  # brings the prompt up, and is swallowed
    for key in ('A', 'B', 'C'):
        lock.key(key)
    lines['lock-prompt'] = lock.status_line()
    paths = []
    for (name, line) in lines.items():
        path = os.path.join(out_dir, f'{name}-{width}.png')
        _save_rgb565(path, core.render(bytes(80), SCREEN_START, 0, width, settings, lock=line), width)
        paths.append(path)
    return paths


def _save_rgb565(path, rows, width):
    """RGB565 widened to 8 bits with zeros, as HSTX does."""
    from PIL import Image

    image = Image.new('RGB', (width, len(rows)))
    image.putdata([(p >> 11 << 3, (p >> 5 & 0x3F) << 2, (p & 0x1F) << 3) for row in rows for p in row])
    image.save(path)
