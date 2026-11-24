# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Writes a KiCad schematic from a description: parts, and the net on each pin.

Every connected pin gets a wire and, at its far end, the net's name: a power
symbol for a power net, a global label for a net that reaches more than one
sheet, a local label otherwise. Along each side of a part the wires alternate,
2.54 mm and 7.62 mm, so neighbouring pins' names stagger instead of running
together. Nothing is wired pin to pin, so a sheet reads as parts with their
nets. Every pin must be connected or marked no-connect, or render() refuses.
A part's reference and value sit where no pin is: beside the body when its
pins all point up or down, above and below it when they all point sideways,
and outside its top-left corner when they point both ways.

A drawing is a group drawn as a circuit instead. Each unit sits where the
sheet module puts it, turned and, if it says so, mirrored left to right;
wires run between pin ends and points with square corners, and labels name
the wired nets that need it. A wired pin has no stub
and no name of its own, and the pins stacked on its end (a connector's VBUS
pins, say) are wired with it. A tee gets a junction. The writer refuses a wire
that joins two nets or touches a pin it doesn't list, an unwired pin whose end
or stub touches another's, and a wired net that leaves the drawing without a
label, so a slip in a drawing fails before KiCad sees it.

Parts sit in titled groups, laid out left to right and top to bottom, on the
smallest paper that holds them. A group's symbol origins are on the 2.54 mm
grid; a drawing's are on the 1.27 mm grid, and only its corner snaps to 2.54.
Either way every pin end lands on KiCad's 1.27 mm connection grid. UUIDs are
uuid5 of each item's name, so the same description always gives the same files.
"""

import json
import math
import os
import uuid
from dataclasses import dataclass

import sexp
import symlib
from sexp import Q

VERSION = 20250114        # KiCad 9's schematic format, which KiCad 10 reads
GRID = 2.54
FINE = 1.27               # KiCad's connection grid: every pin end and wire point sits on it
STUB = 2.54
LONG = 3 * STUB           # every other pin along a side, so neighbours' names stagger
GAP = 7.62
MARGIN = 25.4
TITLE_BLOCK = 38.1        # the strip at the paper's foot that the title block takes
ROW = 200.0               # how wide a group's row grows before it wraps
CHAR = 1.3                # a 1.27 mm font's advance, near enough
ASIDE = 3.175             # a sideways power symbol's name starts this far past its point
POWER = {'GND': 'power:GND', '+3V3': 'power:+3V3', '+5V': 'power:+5V', '+1V8': 'power:+1V8',
         '+1V1': 'power:+1V1', 'VBUS': 'power:VBUS'}
PAPERS = (('A4', 297.0, 210.0), ('A3', 420.0, 297.0), ('A2', 594.0, 420.0), ('A1', 841.0, 594.0))
NAMESPACE = uuid.UUID('6c697a34-3237-4000-8000-000000000000')
_LABEL = {(1, 0): (0, 'left'), (-1, 0): (180, 'right'), (0, -1): (90, 'left'), (0, 1): (270, 'right')}
_ANGLE = {(1, 0): 0, (0, -1): 90, (-1, 0): 180, (0, 1): 270}   # sheet direction -> library angle
_SIDES = {'right': (1, 0), 'left': (-1, 0), 'up': (0, -1), 'down': (0, 1)}


@dataclass(frozen=True)
class Spec:
    """What a part is and where it's bought."""
    lib_id: str
    value: str
    footprint: str
    mpn: str = ''
    lcsc: str = ''
    datasheet: str = ''
    bom: bool = True          # False: not bought or placed (test points, mounting holes, power flags)


FLAG = Spec('power:PWR_FLAG', 'PWR_FLAG', '', bom=False)


def snap(x):
    return round(round(x / GRID) * GRID, 4)


def _direction(d):
    return (round(d[0]), round(d[1]))


def _fine(xy, what):
    """xy, rounded, if it sits on the 1.27 mm connection grid."""
    if xy is None or len(xy) != 2:
        raise ValueError(f'{what}: no place given')
    out = (round(xy[0], 4), round(xy[1], 4))
    if any(abs(v / FINE - round(v / FINE)) > 1e-6 for v in out):
        raise ValueError(f'{what}: {xy} is off the 1.27 mm grid')
    return out


def _on(p, a, b):
    """p lies on the square-cornered segment a-b, ends included."""
    return ((a[0] == b[0] == p[0] and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])) or
            (a[1] == b[1] == p[1] and min(a[0], b[0]) <= p[0] <= max(a[0], b[0])))


def _reach(net, d):
    """How far net's name reaches past where it is attached, pointing d: a label's text and flag, a power symbol
    and the name standing beyond it, or a sideways power symbol's name running on past it."""
    if net not in POWER:
        return CHAR * len(net) + 3.0
    return ASIDE + CHAR * len(net) if d[0] else 5.08


def _effects(hidden=False, justify=None, size=1.27, bold=False):
    font = ['font', ['size', size, size]] + ([['bold', 'yes']] if bold else [])
    out = ['effects', font]
    if justify:
        out.append(['justify'] + list(justify))
    if hidden:
        out.append(['hide', 'yes'])
    return out


def _property(key, value, at, hidden=False, justify=None, angle=0):
    return ['property', Q(key), Q(value), ['at', round(at[0], 4), round(at[1], 4), angle], _effects(hidden, justify)]


_MIRROR = {'left': 'right', 'right': 'left', 'top': 'bottom', 'bottom': 'top'}


def _upright(rot, justify, mirror=False):
    """A field's stored angle and justification, so that it reads across, justified as meant, on a symbol at
    rot, mirrored or not. KiCad turns a field with a symbol turned 90 or 270, and shows its justification
    mirrored, both ways, on one turned 90 or 180, then left to right again on a mirrored one (seen on kicad-cli's
    plots, Oct 9, 2026)."""
    flips = set(_MIRROR) if rot in (90, 180) else set()
    if mirror:
        flips ^= {'left', 'right'}
    if justify:
        justify = tuple(_MIRROR[j] if j in flips else j for j in justify)
    return (90 if rot in (90, 270) else 0), justify


def _natural(text):
    return (0, int(text), '') if text.isdigit() else (1, 0, text)


def _shelves(sizes, width, height):
    """Top-left corners for boxes of sizes, packed left to right in shelves; None if they don't fit."""
    spots, x, y, shelf = [], 0.0, 0.0, 0.0
    for (w, h) in sizes:
        if w > width:
            return None
        if x > 0 and x + w > width:
            x, y, shelf = 0.0, y + shelf + 2 * GAP, 0.0
        spots.append((x, y))
        x += w + 2 * GAP
        shelf = max(shelf, h)
    return spots if y + shelf <= height else None


class Part:
    def __init__(self, sheet, spec, ref, dnp, rot, mirror):
        self.sheet = sheet
        self.spec = spec
        self.ref = ref
        self.dnp = dnp
        self.rot = rot            # one rotation for every unit, or {unit: rotation}
        self.mirror = mirror      # True to flip every unit left to right after turning it, or {unit: True/False}
        self.symbol = symlib.lookup(spec.lib_id)
        self.nets = {}            # pin number -> net name, or None for no-connect
        self.homes = {}           # unit -> the group that places it

    def rotation(self, unit):
        return self.rot[unit] if isinstance(self.rot, dict) else self.rot

    def pose(self, unit):
        """(rotation, mirrored) of the unit."""
        return (self.rotation(unit), bool(self.mirror.get(unit) if isinstance(self.mirror, dict) else self.mirror))

    def numbers(self):
        return sorted({p.number for p in self.symbol.pins}, key=_natural)

    def resolve(self, pin):
        """The pin numbers meant by pin, given as a number or as a name (every pin of that name)."""
        pin = str(pin)
        if any(p.number == pin for p in self.symbol.pins):
            return [pin]
        named = sorted({p.number for p in self.symbol.pins if p.name == pin}, key=_natural)
        if not named:
            raise ValueError(f'{self.ref} ({self.spec.lib_id}) has no pin {pin!r}')
        return named


class Group:
    def __init__(self, sheet, title):
        self.sheet = sheet
        self.title = title
        self.units = []           # (part, unit), in the order they are laid out

    def add(self, spec, ref, pins=None, nc=(), dnp=False, rot=0, mirror=False):
        """Adds part ref, every unit of it here; pins maps a pin (number or name) to its net, nc lists the
        no-connect pins. rot turns every unit, or each unit its own way as {unit: rotation}; mirror then flips
        every unit left to right (KiCad's mirror y), or each one given as {unit: True}."""
        part = self._create(spec, ref, pins, nc, dnp, rot, mirror)
        self._home(part, part.symbol.units)
        return part

    def take(self, ref, units):
        """Places these units of a part that a drawing on the same sheet added without them."""
        part = self.sheet.project.parts[ref]
        if part.sheet is not self.sheet:
            raise ValueError(f'{ref} is on another sheet')
        self._home(part, units)

    def _create(self, spec, ref, pins, nc, dnp, rot, mirror):
        part = self.sheet.project._new_part(self.sheet, spec, ref, dnp, rot, mirror)
        for (pin, net) in (pins or {}).items():
            self.sheet.connect(ref, pin, net)
        self.sheet.nc(ref, *nc)
        return part

    def _home(self, part, units):
        for unit in units:
            if unit not in part.symbol.units:
                raise ValueError(f'{part.ref} has no unit {unit}')
            if unit in part.homes:
                raise ValueError(f'{part.ref}: unit {unit} is placed twice')
            part.homes[unit] = self
            self.units.append((part, unit))


class Drawing(Group):
    """A group drawn as a circuit: units where the sheet module puts them, wires, and labels on the wires."""

    def __init__(self, sheet, title):
        super().__init__(sheet, title)
        self.places = {}          # (ref, unit) -> (x, y), in mm from the drawing's own origin
        self.wires = []           # each a list of points: ('pin', ref, unit or None, number) or ('xy', x, y)
        self.labels = []          # (net, (x, y), direction)

    def add(self, spec, ref, pins=None, nc=(), dnp=False, rot=0, mirror=False, at=None):
        """As Group.add, and at gives the unit's origin, or {unit: origin} for the units of a part with several
        that the drawing places; another group on the sheet takes the rest."""
        units = symlib.lookup(spec.lib_id).units
        places = at if isinstance(at, dict) else {units[0]: at} if len(units) == 1 else {}
        if not places or not set(places) <= set(units):
            raise ValueError(f'{ref}: a drawing places units of {units}, each given its own place')
        places = {unit: _fine(xy, ref) for (unit, xy) in sorted(places.items())}
        part = self._create(spec, ref, pins, nc, dnp, rot, mirror)
        self._home(part, list(places))
        for (unit, xy) in places.items():
            self.places[(ref, unit)] = xy
        return part

    def take(self, ref, units):
        """A drawing places a unit only with add(at=...): it draws nothing it holds without a place."""
        raise ValueError(f'{ref}: a drawing places units with add(at=...); take units {list(units)} in an '
                         f'ordinary group')

    def wire(self, *points):
        """A run of wire through points, each 'REF.PIN' ('REF.PIN@UNIT' for a pin that several units share) or
        (x, y). PIN is a number, or a name whose pins share one end. Between two points that aren't in line, the
        run goes along x first, then along y."""
        self.wires.append([self._point(p) for p in points])

    def label(self, net, at, side):
        """Names net where one of its wires passes at; the text runs toward side: right, left, up or down."""
        self.labels.append((net, _fine(at, f'label {net}'), _SIDES[side]))

    def _point(self, point):
        if isinstance(point, str):
            (ref, _, rest) = point.partition('.')
            (number, _, unit) = rest.partition('@')
            return ('pin', ref, int(unit) if unit else None, number)
        return ('xy',) + _fine(point, f'a wire in {self.title!r}')


class Sheet:
    def __init__(self, project, file, name, title):
        self.project = project
        self.file = file
        self.name = name
        self.title = title
        self.groups = []
        self.notes = []
        self.uuid = project._uuid(file, 'sheet')
        self.symbol_uuid = project._uuid(file, 'sheet-symbol')
        self._flags = None
        self._wired = set()       # (ref, unit, number) of every pin a drawing wires; they get no stub

    def group(self, title):
        group = Group(self, title)
        self.groups.append(group)
        return group

    def drawing(self, title):
        if any(isinstance(g, Drawing) and g.title == title for g in self.groups):
            raise ValueError(f'{self.file}: a second drawing titled {title!r} would share the first one\'s UUIDs')
        group = Drawing(self, title)
        self.groups.append(group)
        return group

    def connect(self, ref, pin, net):
        part = self.project.parts[ref]
        for number in part.resolve(pin):
            if number in part.nets and part.nets[number] != net:
                raise ValueError(f'{ref}.{number} is already on {part.nets[number]}, not {net}')
            part.nets[number] = net

    def nc(self, ref, *pins):
        for pin in pins:
            self.connect(ref, pin, None)

    def flag(self, net):
        """A PWR_FLAG on net, for ERC: it says net is driven, through a fuse, ferrite, inductor or resistor."""
        if self._flags is None:
            self._flags = self.group('Power flags (for ERC)')
        self._flags.add(FLAG, self.project._next('#FLG'), {'1': net})

    def note(self, text):
        self.notes.append(text)

    # Layout

    @staticmethod
    def _box(part, unit):
        """The symbol's box (body and pins) around its origin, on the sheet: (x0, y0, x1, y1)."""
        return part.symbol.box(*part.pose(unit))

    def _stubs(self, part, unit):
        """{pin number: its wire's length}. Along each side, the connected pin ends alternate short and long,
        in order along the edge, so neighbours' names stagger; pins stacked on one end count once. Pins a
        drawing wires have no stub."""
        sides = {}
        for pin in part.symbol.unit_pins(unit):
            if part.nets.get(pin.number) is None or (part.ref, unit, pin.number) in self._wired:
                continue
            d = _direction(pin.outward(*part.pose(unit)))
            end = pin.end((0.0, 0.0), *part.pose(unit))
            sides.setdefault(d, {}).setdefault(end, []).append(pin.number)
        stubs = {}
        for (d, ends) in sides.items():
            along = 1 if d[0] else 0          # a left or right side runs along y, a top or bottom side along x
            for (i, end) in enumerate(sorted(ends, key=lambda e: (e[along], e[1 - along]))):
                for number in ends[end]:
                    stubs[number] = LONG if i % 2 else STUB
        return stubs

    @staticmethod
    def _placing(part, unit):
        """Where the unit's reference and value go: 'beside' (pins only up and down), 'around' (pins only
        sideways) or 'corner' (both)."""
        dirs = {_direction(pin.outward(*part.pose(unit))) for pin in part.symbol.unit_pins(unit)}
        sideways = any(d[0] for d in dirs)
        upright = any(d[1] for d in dirs)
        return 'corner' if sideways and upright else 'around' if sideways else 'beside'

    def _extent(self, part, unit):
        """The unit's box around its origin, stubs, labels and texts included."""
        (bx0, by0, _, _) = box = self._box(part, unit)
        xs, ys = [box[0], box[2]], [box[1], box[3]]
        stubs = self._stubs(part, unit)
        for pin in part.symbol.unit_pins(unit):
            net = part.nets.get(pin.number)
            ex, ey = symlib.sheet_xy(pin.x, pin.y, *part.pose(unit))
            d = pin.outward(*part.pose(unit))
            if net is None or (part.ref, unit, pin.number) in self._wired:
                reach = 0.0
            else:
                reach = stubs[pin.number] + _reach(net, d)
            xs.append(ex + d[0] * reach)
            ys.append(ey + d[1] * reach)
        width = CHAR * max(len(part.ref), len(part.spec.value))
        placing = self._placing(part, unit)
        if placing == 'beside':
            xs.append(max(xs) + width + 2.54)
        elif placing == 'around':
            ys.extend([min(ys) - 3.81, max(ys) + 3.81])
        else:
            xs.append(bx0 - 1.27 - width)
            ys.append(by0 - 5.08)
        return (min(xs), min(ys), max(xs), max(ys))

    def _layout_group(self, group):
        """[(part, unit, offset from the group's corner)] and the group's (width, height)."""
        items, x, y, row, width = [], 0.0, 7.62, 0.0, CHAR * 1.6 * len(group.title)
        for (part, unit) in group.units:
            (x0, y0, x1, y1) = self._extent(part, unit)
            if x > 0 and x + (x1 - x0) > ROW:
                x, y, row = 0.0, y + row + GAP, 0.0
            items.append((part, unit, (x - x0, y - y0)))
            x += (x1 - x0) + GAP
            row = max(row, y1 - y0)
            width = max(width, x - GAP)
        return items, (width, y + row)

    def _pin_place(self, drawing, ref, unit, pin):
        """Where a drawing's pin REF.PIN ends, PIN a number or a name, and which unit and pin number it is."""
        part = self.project.parts.get(ref)
        if part is None or part.sheet is not self or not any(key[0] == ref for key in drawing.places):
            raise ValueError(f'{drawing.title!r}: a wire names {ref}, which is not in the drawing')
        numbers = part.resolve(pin)
        holders = [u for u in part.symbol.units if (ref, u) in drawing.places and
                   any(p.number in numbers for p in part.symbol.unit_pins(u))]
        if unit is None and len(holders) == 1:
            unit = holders[0]
        if unit not in holders:
            raise ValueError(f'{ref}.{pin}: name a unit the drawing places, one of {holders}, as {ref}.{pin}@UNIT')
        ends = {p.end(drawing.places[(ref, unit)], *part.pose(unit)): p.number
                for p in part.symbol.unit_pins(unit) if p.number in numbers}
        if len(ends) > 1:                         # a name on pins stacked on one end means that end
            raise ValueError(f'{ref}.{pin} is pins {", ".join(numbers)}, which end apart: name one by number')
        ((end, number),) = ends.items()
        if part.nets.get(number) is None:
            raise ValueError(f'{ref}.{pin} is no-connect, so no wire may reach it')
        return end, (ref, unit, number)

    def _layout_drawing(self, drawing):
        """A drawing's units (offsets from its corner), its size, and its wires, junctions and labels."""
        parts, title = self.project.parts, repr(drawing.title)
        runs, wired = [], {}                      # wired: (ref, unit, number) -> where its end is
        for wire in drawing.wires:
            points = []
            for point in wire:
                if point[0] == 'xy':
                    points.append(point[1:])
                    continue
                (xy, pin) = self._pin_place(drawing, *point[1:])
                points.append(xy)
                wired[pin] = xy
            runs.append(points)
        # Pins stacked on a wired pin's end (a connector's four VBUS pins, say) are wired with it.
        for ((ref, unit, number), xy) in list(wired.items()):
            part = parts[ref]
            for pin in part.symbol.unit_pins(unit):
                if (ref, unit, pin.number) in wired or pin.end(drawing.places[(ref, unit)], *part.pose(unit)) != xy:
                    continue
                if part.nets.get(pin.number) != part.nets[number]:
                    raise ValueError(f'{title}: {ref}.{pin.number}, stacked on {ref}.{number}, is on '
                                     f'{part.nets.get(pin.number)}, not {part.nets[number]}')
                wired[(ref, unit, pin.number)] = xy
        self._wired |= set(wired)
        segments = []                             # square corners: along x first, then along y
        for points in runs:
            for (a, b) in zip(points, points[1:]):
                bend = (b[0], a[1])
                for (p, q) in (((a, bend), (bend, b)) if a[0] != b[0] and a[1] != b[1] else ((a, b),)):
                    if p != q:
                        segments.append((p, q))
        # Split every segment where another one ends, a wired pin ends or a label sits, so that wires only ever
        # meet end to end; then each meeting of three or more is a junction. Runs that overlap split into the same
        # pieces, and each piece is drawn once, or its ends would count twice.
        stops = {p for seg in segments for p in seg} | set(wired.values()) | {xy for (_, xy, _) in drawing.labels}
        split = {}
        for (a, b) in segments:
            inner = sorted((p for p in stops if p not in (a, b) and _on(p, a, b)),
                           key=lambda p: abs(p[0] - a[0]) + abs(p[1] - a[1]))
            chain = [a] + inner + [b]
            for (p, q) in zip(chain, chain[1:]):
                split.setdefault(frozenset((p, q)), (p, q))
        segments = list(split.values())
        root = {}

        def find(x):
            while root.setdefault(x, x) != x:
                x = root[x]
            return x

        for (a, b) in segments:
            root[find(a)] = find(b)
        nets, pins = {}, {}                       # component -> nets on it, and (ref, number) pins on it
        for (pin, xy) in wired.items():
            if xy not in root:
                raise ValueError(f'{title}: the wire at {pin[0]}.{pin[2]} goes nowhere')
            nets.setdefault(find(xy), set()).add(parts[pin[0]].nets[pin[2]])
            pins.setdefault(find(xy), set()).add((pin[0], pin[2]))
        for (component, on) in nets.items():
            if len(on) > 1:
                raise ValueError(f'{title}: a wire joins {" and ".join(sorted(on))}')
        for x in {find(p) for seg in segments for p in seg} - set(nets):
            raise ValueError(f'{title}: a wire at {x} reaches no pin')
        # A wire may touch only the pins it lists, and an unwired pin's stub nothing at all. KiCad joins wire and pin
        # ends that meet, and a label anywhere along a wire, but a tee only at a junction (kicad-cli 10.0.6, Oct 9,
        # 2026); a touch it doesn't join still reads as joined, so every touch is refused.
        stubs = []                                # (REF.PIN, its end, its stub's tip), pins stacked on one end once
        for (ref, unit) in drawing.places:
            (part, ends) = (parts[ref], set())
            lengths = self._stubs(part, unit)
            for pin in part.symbol.unit_pins(unit):
                end = pin.end(drawing.places[(ref, unit)], *part.pose(unit))
                if (ref, unit, pin.number) in self._wired or end in ends:
                    continue
                ends.add(end)
                (d, reach) = (_direction(pin.outward(*part.pose(unit))), lengths.get(pin.number, 0.0))
                stubs.append((f'{ref}.{pin.number}', end, (round(end[0] + d[0] * reach, 4), round(end[1] + d[1] * reach, 4))))
        for (name, end, tip) in stubs:
            for (a, b) in segments:
                if _on(end, a, b) or _on(tip, a, b) or _on(a, end, tip) or _on(b, end, tip):
                    raise ValueError(f'{title}: a wire of {min(nets[find(a)])} touches {name}')
        for (i, (name, end, tip)) in enumerate(stubs):
            for (other, o_end, o_tip) in stubs[i + 1:]:
                if _on(o_end, end, tip) or _on(o_tip, end, tip) or _on(end, o_end, o_tip) or _on(tip, o_end, o_tip):
                    raise ValueError(f'{title}: {name} and {other} touch, so KiCad may join their nets')
        named = set()
        for (net, xy, _) in drawing.labels:
            if xy not in root or nets.get(find(xy)) != {net}:
                raise ValueError(f'{title}: label {net} at {xy} is not on a wire of {net}')
            named.add(find(xy))
        for (component, (net,)) in nets.items():
            everywhere = {(p.ref, number) for p in parts.values() for (number, n) in p.nets.items() if n == net}
            if component not in named and (net in POWER or everywhere - pins[component]):
                raise ValueError(f'{title}: {net} leaves the drawing, so its wires need a label')
        ends = {}
        for seg in segments:
            for p in seg:
                ends[p] = ends.get(p, 0) + 1
        for (_, _, xy) in {(ref, unit, xy) for ((ref, unit, _), xy) in wired.items()}:   # a stack is one end
            ends[xy] = ends.get(xy, 0) + 1
        junctions = sorted(p for (p, k) in ends.items() if k >= 3)
        # The drawing's box, its units' texts and stubs included, then a shift that puts it on the grid.
        xs, ys = [], []
        for ((ref, unit), (x, y)) in drawing.places.items():
            (x0, y0, x1, y1) = self._extent(parts[ref], unit)
            xs += [x + x0, x + x1]
            ys += [y + y0, y + y1]
        for (a, b) in segments:
            xs += [a[0], b[0]]
            ys += [a[1], b[1]]
        for (net, (x, y), d) in drawing.labels:
            reach = _reach(net, d)
            xs += [x, x + d[0] * reach]
            ys += [y, y + d[1] * reach - 1.27]
        sx = math.ceil(round(-min(xs) / GRID, 4)) * GRID
        sy = math.ceil(round((7.62 - min(ys)) / GRID, 4)) * GRID

        def moved(p):
            return (round(p[0] + sx, 4), round(p[1] + sy, 4))

        items = [(parts[ref], unit, moved(xy)) for ((ref, unit), xy) in drawing.places.items()]
        art = ([(moved(a), moved(b)) for (a, b) in segments], [moved(p) for p in junctions],
               [(net, moved(xy), d) for (net, xy, d) in drawing.labels])
        size = (max(max(xs) + sx, CHAR * 1.6 * len(drawing.title)), max(ys) + sy)
        return items, size, art

    def _layout(self):
        """The paper, every unit's origin, every text (group titles, then notes) with its place, and each
        drawing's wires, junctions and labels with its corner."""
        self._wired = set()
        laid = [(group, *self._layout_drawing(group)) if isinstance(group, Drawing)
                else (group, *self._layout_group(group), None) for group in self.groups]
        sizes = [size for (_, _, size, _) in laid]
        if self.notes:
            sizes.append((CHAR * max(len(n) for n in self.notes), 5.08 * (len(self.notes) + 1)))
        for (paper, width, height) in PAPERS:
            spots = _shelves(sizes, width - 2 * MARGIN, height - 2 * MARGIN - TITLE_BLOCK)
            if spots is not None:
                break
        else:
            raise ValueError(f'{self.file} does not fit on {PAPERS[-1][0]}')
        units, texts, drawn = [], [], []
        for ((group, items, _, art), (gx, gy)) in zip(laid, spots):
            ox, oy = MARGIN + gx, MARGIN + gy
            texts.append((group.title, (snap(ox), snap(oy + 5.08)), 2.0, True))
            if art is None:
                for (part, unit, (dx, dy)) in items:
                    units.append((part, unit, (snap(ox + dx), snap(oy + dy))))
                continue
            corner = (snap(ox), snap(oy))          # a drawing keeps its own spacing: only its corner snaps
            for (part, unit, (dx, dy)) in items:
                units.append((part, unit, (round(corner[0] + dx, 4), round(corner[1] + dy, 4))))
            drawn.append((group, corner, art))
        if self.notes:
            (nx, ny) = spots[-1]
            for (i, note) in enumerate(self.notes):
                texts.append((note, (snap(MARGIN + nx), snap(MARGIN + ny + 5.08 * (i + 1))), 1.27, False))
        return paper, units, texts, drawn

    # Output

    def _expr(self):
        paper, units, texts, drawn = self._layout()
        used, items = {}, []
        for (part, unit, at) in units:
            used[part.symbol.lib_id] = part.symbol
            items.extend(self._unit(part, unit, at, used))
        for (group, (cx, cy), (segments, junctions, labels)) in drawn:
            key = f'drawing:{group.title}'
            for (i, (a, b)) in enumerate(segments):
                items.append(['wire', ['pts', ['xy', round(cx + a[0], 4), round(cy + a[1], 4)],
                                       ['xy', round(cx + b[0], 4), round(cy + b[1], 4)]],
                              ['stroke', ['width', 0], ['type', 'default']],
                              ['uuid', Q(self.project._uuid(self.file, f'{key}:wire:{i}'))]])
            for (i, (x, y)) in enumerate(junctions):
                items.append(['junction', ['at', round(cx + x, 4), round(cy + y, 4)], ['diameter', 0],
                              ['color', 0, 0, 0, 0], ['uuid', Q(self.project._uuid(self.file, f'{key}:junction:{i}'))]])
            for (i, (net, (x, y), d)) in enumerate(labels):
                items.append(self._name(net, (round(cx + x, 4), round(cy + y, 4)), d, f'{key}:label:{i}', used))
        for (i, (text, at, size, bold)) in enumerate(texts):
            items.append(['text', Q(text), ['exclude_from_sim', 'no'], ['at', at[0], at[1], 0],
                          _effects(justify=('left', 'bottom'), size=size, bold=bold),
                          ['uuid', Q(self.project._uuid(self.file, f'text:{i}:{text}'))]])
        head = ['kicad_sch', ['version', VERSION], ['generator', Q('eeschema')], ['generator_version', Q('9.0')],
                ['uuid', Q(self.uuid)], ['paper', Q(paper)], self.project._title_block(self.title),
                ['lib_symbols'] + [used[k].expr for k in sorted(used)]]
        return head + items + [['embedded_fonts', 'no']]

    def _unit(self, part, unit, at, used):
        sym, (rot, mirror), spec = part.symbol, part.pose(unit), part.spec
        (bx0, by0, bx1, by1) = self._box(part, unit)
        placing = self._placing(part, unit)
        if placing == 'beside':       # pins only up and down: the texts go beside the body
            texts = ((at[0] + bx1 + 1.27, at[1] - 1.27), (at[0] + bx1 + 1.27, at[1] + 1.27), ('left',))
        elif placing == 'around':     # pins only sideways: above and below it
            texts = ((at[0] + (bx0 + bx1) / 2, at[1] + by0 - 1.27), (at[0] + (bx0 + bx1) / 2, at[1] + by1 + 1.27), None)
        else:                         # pins every way: outside the top-left corner, where no pin's wire goes
            texts = ((at[0] + bx0 - 1.27, at[1] + by0 - 3.81), (at[0] + bx0 - 1.27, at[1] + by0 - 1.27),
                     ('right', 'bottom'))
        stubs = self._stubs(part, unit)
        extra = [_property('MPN', spec.mpn, at, hidden=True), _property('LCSC', spec.lcsc, at, hidden=True)]
        items = [self._instance(sym, part.ref, spec.value, spec.footprint, spec.datasheet, unit, at, rot, part.dnp,
                                spec.bom, self.project._uuid(self.file, f'{part.ref}:{unit}'),
                                [p.number for p in sym.unit_pins(unit)], extra, texts, mirror)]
        ends = {}
        wired = {pin.end(at, rot, mirror) for pin in sym.unit_pins(unit) if (part.ref, unit, pin.number) in self._wired}
        for pin in sym.unit_pins(unit):
            end = pin.end(at, rot, mirror)
            if end in wired:
                continue                          # a drawing's wire meets it
            net = part.nets[pin.number]
            if end in ends:
                if ends[end] != net:
                    raise ValueError(f'{part.ref}: pins stacked at {end} are on {ends[end]} and {net}')
                continue
            ends[end] = net
            key = f'{part.ref}:{unit}:{pin.number}'
            if net is None:
                items.append(['no_connect', ['at', end[0], end[1]], ['uuid', Q(self.project._uuid(self.file, key + ':nc'))]])
                continue
            d = _direction(pin.outward(rot, mirror))
            stub = stubs[pin.number]
            tip = (round(end[0] + d[0] * stub, 4), round(end[1] + d[1] * stub, 4))
            items.append(['wire', ['pts', ['xy', end[0], end[1]], ['xy', tip[0], tip[1]]],
                          ['stroke', ['width', 0], ['type', 'default']],
                          ['uuid', Q(self.project._uuid(self.file, key + ':wire'))]])
            items.append(self._name(net, tip, d, key, used))
        return items

    def _name(self, net, tip, d, key, used):
        """What names net at a stub's tip: a power symbol, a global label or a local label."""
        if net in POWER:
            sym = symlib.lookup(POWER[net])
            used[sym.lib_id] = sym
            rot = (_ANGLE[d] - sym.pins[0].angle) % 360
            if d[0]:      # sideways: the name starts past the symbol's graphic and reads away from it
                (value_at, justify) = ((tip[0] + d[0] * ASIDE, tip[1]), ('left',) if d[0] > 0 else ('right',))
            else:         # up or down: the name sits centred beyond it
                (value_at, justify) = ((tip[0], tip[1] + d[1] * 3.81), None)
            return self._instance(sym, self.project._next('#PWR'), net, '', '', 1, tip, rot, False, False,
                                  self.project._uuid(self.file, key + ':power'), [sym.pins[0].number], [],
                                  (tip, value_at, justify))
        angle, justify = _LABEL[d]
        uid = Q(self.project._uuid(self.file, key + ':label'))
        if net in self.project.globals:
            return ['global_label', Q(net), ['shape', 'bidirectional'], ['at', tip[0], tip[1], angle],
                    ['fields_autoplaced', 'yes'], _effects(justify=(justify,)), ['uuid', uid],
                    ['property', Q('Intersheetrefs'), Q('${INTERSHEET_REFS}'), ['at', tip[0], tip[1], 0],
                     _effects(hidden=True)]]
        return ['label', Q(net), ['at', tip[0], tip[1], angle], ['fields_autoplaced', 'yes'],
                _effects(justify=(justify, 'bottom')), ['uuid', uid]]

    def _instance(self, sym, ref, value, footprint, datasheet, unit, at, rot, dnp, bom, uid, pins, extra, texts,
                  mirror=False):
        ref_at, value_at, justify = texts
        (angle, justify) = _upright(rot, justify, mirror)
        expr = ['symbol', ['lib_id', Q(sym.lib_id)], ['at', at[0], at[1], rot]]
        if mirror:
            expr.append(['mirror', 'y'])     # KiCad's flip left to right, after the turn
        expr += [['unit', unit],
                 ['exclude_from_sim', 'no'], ['in_bom', 'yes' if bom else 'no'], ['on_board', 'yes'],
                 ['dnp', 'yes' if dnp else 'no'], ['uuid', Q(uid)],
                 _property('Reference', ref, ref_at, hidden=ref.startswith('#'), justify=justify, angle=angle),
                 _property('Value', value, value_at, justify=justify, angle=angle),
                 _property('Footprint', footprint, at, hidden=True, angle=angle),
                 _property('Datasheet', datasheet, at, hidden=True, angle=angle),
                 _property('Description', '', at, hidden=True, angle=angle)] + extra
        for number in dict.fromkeys(pins):
            expr.append(['pin', Q(number), ['uuid', Q(self.project._uuid(self.file, f'{uid}:pin:{number}'))]])
        expr.append(['instances', ['project', Q(self.project.name),
                                   ['path', Q(f'/{self.project.root_uuid}/{self.symbol_uuid}'),
                                    ['reference', Q(ref)], ['unit', unit]]]])
        return expr


class Project:
    def __init__(self, name, directory, title, rev, date, company, comments=()):
        self.name = name
        self.directory = directory
        self.title = title
        self.rev = rev
        self.date = date
        self.company = company
        self.comments = list(comments)
        self.sheets = []
        self.parts = {}
        self.notes = []
        self.globals = set()
        self.root_uuid = self._uuid(f'{name}.kicad_sch', 'root')
        self._counters = {}

    def _uuid(self, file, key):
        return str(uuid.uuid5(NAMESPACE, f'{self.name}/{file}/{key}'))

    def _next(self, prefix):
        self._counters[prefix] = self._counters.get(prefix, 0) + 1
        return f'{prefix}{self._counters[prefix]:03d}'

    def sheet(self, file, name, title):
        sheet = Sheet(self, file, name, title)
        self.sheets.append(sheet)
        return sheet

    def note(self, text):
        self.notes.append(text)

    def _new_part(self, sheet, spec, ref, dnp, rot, mirror=False):
        if ref in self.parts:
            raise ValueError(f'{ref} is used twice')
        part = Part(sheet, spec, ref, dnp, rot, mirror)
        units = part.symbol.units
        if isinstance(rot, dict) and sorted(rot) != units:
            raise ValueError(f'{ref}: a rotation for each of units {units}, or one for all')
        if isinstance(mirror, dict) and not set(mirror) <= set(units):
            raise ValueError(f'{ref}: mirror names units of {units}')
        for unit in units:
            if part.rotation(unit) not in (0, 90, 180, 270):
                raise ValueError(f'{ref}: rotation {part.rotation(unit)} is not 0, 90, 180 or 270')
        self.parts[ref] = part
        return part

    def _check(self):
        problems = []
        for part in self.parts.values():
            missing = [n for n in part.numbers() if n not in part.nets]
            if missing:
                problems.append(f'{part.ref}: pins {", ".join(missing)} are neither connected nor no-connect')
            for unit in part.symbol.units:
                if unit not in part.homes:
                    problems.append(f'{part.ref}: unit {unit} is placed nowhere')
        if problems:
            raise ValueError('\n'.join(problems))

    def _global_nets(self):
        where = {}
        for part in self.parts.values():
            for net in part.nets.values():
                if net is not None and net not in POWER:
                    where.setdefault(net, set()).add(part.sheet.file)
        return {net for (net, files) in where.items() if len(files) > 1}

    def render(self):
        """{file name: text} for every sheet and the root sheet."""
        self._check()
        self.globals = self._global_nets()
        self._counters['#PWR'] = 0
        files = {sheet.file: sexp.dump(sheet._expr()) + '\n' for sheet in self.sheets}
        files[f'{self.name}.kicad_sch'] = sexp.dump(self._root()) + '\n'
        return dict(sorted(files.items()))

    def write(self):
        """Writes every file, and the project file if there isn't one; returns the schematic files' names."""
        files = self.render()
        os.makedirs(self.directory, exist_ok=True)
        for (name, text) in files.items():
            with open(os.path.join(self.directory, name), 'w', encoding='utf-8', newline='\n') as stream:
                stream.write(text)
        pro = os.path.join(self.directory, f'{self.name}.kicad_pro')
        if not os.path.exists(pro):
            with open(pro, 'w', encoding='utf-8', newline='\n') as stream:
                json.dump({'meta': {'filename': f'{self.name}.kicad_pro', 'version': 3}}, stream, indent=2)
                stream.write('\n')
        return list(files)

    def stale(self):
        """The schematic files whose text on disk differs from render()'s, then any .kicad_sch in the directory
        that no sheet writes (a sheet renamed or dropped leaves one behind)."""
        files = self.render()
        out = []
        for (name, text) in files.items():
            try:
                with open(os.path.join(self.directory, name), encoding='utf-8') as stream:
                    if stream.read() == text:
                        continue
            except FileNotFoundError:
                pass
            out.append(name)
        if os.path.isdir(self.directory):
            out += sorted(n for n in os.listdir(self.directory) if n.endswith('.kicad_sch') and n not in files)
        return out

    def _title_block(self, title):
        block = ['title_block', ['title', Q(f'{self.title}: {title}' if title else self.title)],
                 ['date', Q(self.date)], ['rev', Q(self.rev)], ['company', Q(self.company)]]
        for (i, text) in enumerate(self.comments, 1):
            block.append(['comment', i, Q(text)])
        return block

    def _root(self):
        root = ['kicad_sch', ['version', VERSION], ['generator', Q('eeschema')], ['generator_version', Q('9.0')],
                ['uuid', Q(self.root_uuid)], ['paper', Q('A4')], self._title_block(''), ['lib_symbols']]
        x, y = 25.4, 50.8
        for (page, sheet) in enumerate(self.sheets, 2):
            root.append(['sheet', ['at', x, y], ['size', 50.8, 12.7], ['exclude_from_sim', 'no'], ['in_bom', 'yes'],
                         ['on_board', 'yes'], ['dnp', 'no'], ['fields_autoplaced', 'yes'],
                         ['stroke', ['width', 0.1524], ['type', 'solid']], ['fill', ['color', 0, 0, 0, 0.0]],
                         ['uuid', Q(sheet.symbol_uuid)],
                         ['property', Q('Sheetname'), Q(sheet.name), ['at', x, round(y - 0.7, 4), 0],
                          _effects(justify=('left', 'bottom'))],
                         ['property', Q('Sheetfile'), Q(sheet.file), ['at', x, round(y + 13.3, 4), 0],
                          _effects(justify=('left', 'top'))],
                         ['instances', ['project', Q(self.name), ['path', Q(f'/{self.root_uuid}'), ['page', Q(str(page))]]]]])
            x = round(x + 63.5, 4)
            if x > 230:
                x, y = 25.4, round(y + 25.4, 4)
        for (i, text) in enumerate(self.notes):
            root.append(['text', Q(text), ['exclude_from_sim', 'no'], ['at', 25.4, round(25.4 + 5.08 * i, 4), 0],
                         _effects(justify=('left', 'bottom')), ['uuid', Q(self._uuid(f'{self.name}.kicad_sch', f'note:{i}'))]])
        root.append(['sheet_instances', ['path', Q('/'), ['page', Q('1')]]])
        root.append(['embedded_fonts', 'no'])
        return root
