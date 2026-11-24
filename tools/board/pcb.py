# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The board's layout as data.

Board millimetres: the origin is the outline's top-left corner, x runs right, y runs down, and an angle turns
counter-clockwise as KiCad shows it. layout.py fills a Layout; pcb_build.py makes the KiCad board from it in KiCad's
own Python, 3.9, so nothing here may need a later one; the tests read both.

Nets go by the schematic's short names ('GND', 'HSTX_CKN', 'LINE_C'). A point is (x, y), or 'REF.PAD' for the centre
of that pad once REF is placed.
"""

import hashlib
import json
import math
from collections import namedtuple

import footprint

ORIGIN = (20.0, 20.0)          # the board's top-left corner on KiCad's page; the grid and drill origins sit there
COPPER = ('F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu')

Track = namedtuple('Track', 'net layer width points')
Via = namedtuple('Via', 'net x y size drill')
Zone = namedtuple('Zone', 'net layer polygon priority clearance min_width connect')     # connect: thermal|solid|none
Keepout = namedtuple('Keepout', 'name layers polygon tracks vias pours')                # True: kept out of the area
Text = namedtuple('Text', 'text layer x y size rot')
Line = namedtuple('Line', 'layer width points')


def rect(x0, y0, x1, y1):
    """A rectangle's corners, clockwise on the screen from the top-left."""
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def inside(point, polygon):
    """Whether point lies inside polygon (even-odd rule; a point on an edge may go either way)."""
    (x, y) = point
    polygon = tuple(polygon)
    hit = False
    for (a, b) in zip(polygon, polygon[1:] + polygon[:1]):
        if (a[1] > y) != (b[1] > y) and x < a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]):
            hit = not hit
    return hit


def length(points):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for (a, b) in zip(points, points[1:]))


def to_segment(p, a, b):
    """The distance from point p to the segment from a to b."""
    (dx, dy) = (b[0] - a[0], b[1] - a[1])
    n = dx * dx + dy * dy
    t = 0.0 if n == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / n))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def clip(a, b, box):
    """The part of the segment a-b inside box (x0, y0, x1, y1), or None if none of it is (Liang and Barsky)."""
    (t0, t1) = (0.0, 1.0)
    (dx, dy) = (b[0] - a[0], b[1] - a[1])
    for (p, q) in ((-dx, a[0] - box[0]), (dx, box[2] - a[0]), (-dy, a[1] - box[1]), (dy, box[3] - a[1])):
        if p == 0:
            if q < 0:
                return None
            continue
        t = q / p
        if p < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return None
    return ((round(a[0] + t0 * dx, 6), round(a[1] + t0 * dy, 6)), (round(a[0] + t1 * dx, 6), round(a[1] + t1 * dy, 6)))


def _in_box(p, box):
    return box[0] - 1e-6 <= p[0] <= box[2] + 1e-6 and box[1] - 1e-6 <= p[1] <= box[3] + 1e-6


def _box_distance(p, box):
    """From point p to the rectangle (x0, y0, x1, y1); 0 inside it."""
    return math.hypot(max(box[0] - p[0], 0.0, p[0] - box[2]), max(box[1] - p[1], 0.0, p[1] - box[3]))


def _crosses(a, b, c, d):
    def side(p, q, s):
        return (q[0] - p[0]) * (s[1] - p[1]) - (q[1] - p[1]) * (s[0] - p[0])
    return side(a, b, c) * side(a, b, d) < 0 and side(c, d, a) * side(c, d, b) < 0


def _segment_distance(a, b, c, d):
    """Between the segments a-b and c-d; 0 where they cross."""
    if _crosses(a, b, c, d):
        return 0.0
    return min(to_segment(a, c, d), to_segment(b, c, d), to_segment(c, a, b), to_segment(d, a, b))


def _segment_box_distance(a, b, box):
    if _in_box(a, box) or _in_box(b, box):
        return 0.0
    corners = ((box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3]))
    return min(_segment_distance(a, b, p, q) for (p, q) in zip(corners, corners[1:] + corners[:1]))


def parallel(points, d):
    """The polyline d mm to the left of points as you walk along them (y down, so left of a walk to the right is
    up), mitred at each bend: the other line of a pair."""
    normals = []
    for (a, b) in zip(points, points[1:]):
        (dx, dy) = (b[0] - a[0], b[1] - a[1])
        n = math.hypot(dx, dy)
        if n == 0:
            raise ValueError(f'repeated point {a}')
        normals.append((dy / n, -dx / n))
    out = [(points[0][0] + d * normals[0][0], points[0][1] + d * normals[0][1])]
    for (i, p) in enumerate(points[1:-1]):
        (n1, n2) = (normals[i], normals[i + 1])
        (mx, my) = (n1[0] + n2[0], n1[1] + n2[1])
        m = math.hypot(mx, my)
        if m < 1e-9:
            raise ValueError(f'the path doubles back at {p}')
        (mx, my) = (mx / m, my / m)
        k = d / (mx * n1[0] + my * n1[1])
        out.append((p[0] + k * mx, p[1] + k * my))
    out.append((points[-1][0] + d * normals[-1][0], points[-1][1] + d * normals[-1][1]))
    return [(round(x, 6) + 0.0, round(y, 6) + 0.0) for (x, y) in out]


class Layout:
    def __init__(self, parts, width, height, corner=1.0, pins=None):
        self.parts = dict(parts)            # ref -> footprint id, as the netlist has them
        self.pins = dict(pins or {})        # (ref, pad) -> short net name, as netlist.leaf gives it
        self.width = float(width)
        self.height = float(height)
        self.corner = float(corner)         # the outline's corner radius
        self.places = {}                    # ref -> (x, y, rot)
        self.tracks = []
        self.vias = []
        self.escapes = []                   # (via, stub) laid for Freerouting (layout_escapes), both in vias and tracks
        self.zones = []
        self.keepouts = []
        self.pours = []                     # the outer layers' ground pours: added after Freerouting has routed
        self.texts = []
        self.lines = []                     # graphic polylines off copper: the silkscreen's outlines
        self.labels = {}                    # ref -> (dx, dy, rot): a reference designator moved off its default

    def place(self, ref, x, y, rot=0):
        if ref not in self.parts:
            raise KeyError(f'{ref} is not in the netlist')
        if ref in self.places:
            raise ValueError(f'{ref} is placed twice')
        self.places[ref] = (float(x), float(y), float(rot) % 360)

    def pad(self, ref, number):
        """Where the centre of ref's pad number lands on the board."""
        if ref not in self.places:
            raise KeyError(f'{ref} is not placed yet')
        (x, y, rot) = self.places[ref]
        p = footprint.pad(self.parts[ref], number)
        (dx, dy) = footprint.turn(p.x, p.y, rot)
        return (round(x + dx, 6) + 0.0, round(y + dy, 6) + 0.0)

    def point(self, p):
        if isinstance(p, str):
            (ref, number) = p.split('.', 1)
            return self.pad(ref, number)
        return (float(p[0]), float(p[1]))

    def net(self, p):
        """The net on pad 'REF.PAD': for the nets the schematic leaves to KiCad to name, like Net-(U4A-OUT+)."""
        (ref, number) = p.split('.', 1)
        return self.pins[(ref, number)]

    def track(self, net, layer, width, *points):
        if layer not in COPPER:
            raise ValueError(f'{layer} is not a copper layer')
        # a point given twice in a row (a neck ending where a pair's line begins) is one point, not a segment
        out = []
        for p in (self.point(p) for p in points):
            if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 1e-6:
                out.append(p)
        if len(out) < 2:
            raise ValueError('a track needs two points')
        self.tracks.append(Track(net, layer, float(width), tuple(out)))

    def pair(self, p_net, n_net, layer, width, gap, p_pad, n_pad, centre, p_end, n_end):
        """One pair along a centre line: P on its left as you walk the line, N on its right, width + gap apart
        centre to centre; each line necks from its pad onto the pair and off it again to its end pad."""
        half = (width + gap) / 2
        centre = [self.point(c) for c in centre]
        self.track(p_net, layer, width, p_pad, *parallel(centre, half), p_end)
        self.track(n_net, layer, width, n_pad, *parallel(centre, -half), n_end)

    def via(self, net, at, size=0.6, drill=0.3):
        (x, y) = self.point(at)
        self.vias.append(Via(net, x, y, float(size), float(drill)))

    def zone(self, net, layer, polygon, priority=0, clearance=0.2, min_width=0.2, connect='thermal'):
        if layer not in COPPER:
            raise ValueError(f'{layer} is not a copper layer')
        if connect not in ('thermal', 'solid', 'none'):
            raise ValueError(f'connect is thermal, solid or none, not {connect}')
        self.zones.append(Zone(net, layer, tuple(self.point(p) for p in polygon), int(priority), float(clearance),
                               float(min_width), connect))

    def pour(self, net, layer, polygon, priority=0, clearance=0.25, min_width=0.25, connect='thermal'):
        """A ground pour on an outer layer. Freerouting never sees it: it would take the pour's outline for copper
        that joins every pad inside, which the fill may not."""
        if layer not in ('F.Cu', 'B.Cu'):
            raise ValueError('pours are for the outer layers; In1 and In2 are planes, given by zone()')
        self.pours.append(Zone(net, layer, tuple(self.point(p) for p in polygon), int(priority), float(clearance),
                               float(min_width), connect))

    def keepout(self, name, layers, polygon, tracks=False, vias=False, pours=True):
        for layer in layers:
            if layer not in COPPER:
                raise ValueError(f'{layer} is not a copper layer')
        self.keepouts.append(Keepout(name, tuple(layers), tuple(self.point(p) for p in polygon), tracks, vias, pours))

    def text(self, text, x, y, layer='F.SilkS', size=1.0, rot=0):
        self.texts.append(Text(text, layer, float(x), float(y), float(size), float(rot)))

    def label(self, ref, dx, dy, rot=0):
        """Moves ref's designator by (dx, dy) from where its footprint puts it, turned to rot."""
        if ref in self.labels:
            raise ValueError(f'{ref} is labelled twice')
        self.labels[ref] = (float(dx), float(dy), float(rot))

    def line(self, layer, width, *points):
        """A graphic polyline on a layer that isn't copper."""
        if layer in COPPER:
            raise ValueError(f'{layer} is copper: draw copper with track()')
        if len(points) < 2:
            raise ValueError('a line needs two points')
        self.lines.append(Line(layer, float(width), tuple(self.point(p) for p in points)))

    def box(self, ref):
        """ref's courtyard on the board, as (x0, y0, x1, y1)."""
        (x, y, rot) = self.places[ref]
        (cx0, cy0, cx1, cy1) = footprint.load(self.parts[ref]).courtyard
        corners = [footprint.turn(cx, cy, rot) for (cx, cy) in ((cx0, cy0), (cx1, cy0), (cx1, cy1), (cx0, cy1))]
        return (x + min(c[0] for c in corners), y + min(c[1] for c in corners),
                x + max(c[0] for c in corners), y + max(c[1] for c in corners))

    def stitch(self, net, points, clearance=0.5, size=0.6, drill=0.3):
        """A via on net at each point that keeps clearance from every placed courtyard, scripted track and via, lies
        in no outer-layer zone of another net, and lies outside every keep-out (the coax line side among them):
        ground stitching on a grid, without hunting for the gaps by hand."""
        boxes = [self.box(ref) for ref in self.places if footprint.load(self.parts[ref]).courtyard]
        for p in points:
            (x, y) = self.point(p)
            if any(x0 - clearance <= x <= x1 + clearance and y0 - clearance <= y <= y1 + clearance
                   for (x0, y0, x1, y1) in boxes):
                continue
            if any(inside((x, y), k.polygon) for k in self.keepouts):
                continue
            if any(z.layer in ('F.Cu', 'B.Cu') and z.net != net and inside((x, y), z.polygon) for z in self.zones):
                continue
            if any(to_segment((x, y), a, b) < t.width / 2 + size / 2 + clearance
                   for t in self.tracks for (a, b) in zip(t.points, t.points[1:])):
                continue
            if any(math.hypot(x - v.x, y - v.y) < (v.size + size) / 2 + clearance for v in self.vias):
                continue
            self.vias.append(Via(net, x, y, float(size), float(drill)))

    def copper_pads(self):
        """Every placed pad as (ref, number, kind, net, (x0, y0, x1, y1)) on the board, its net as self.pins has it
        (None for a pad on no net). Parts turn by multiples of 90 degrees and no footprint here turns its pads."""
        out = []
        for (ref, (x, y, rot)) in self.places.items():
            for p in footprint.load(self.parts[ref]).pads:
                (dx, dy) = footprint.turn(p.x, p.y, rot)
                (w, h) = (p.h, p.w) if round(rot) % 180 == 90 else (p.w, p.h)
                (cx, cy) = (x + dx, y + dy)
                out.append((ref, p.number, p.kind, self.pins.get((ref, p.number)),
                            (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)))
        return out

    def fanout(self, net, size=0.45, drill=0.2, width=0.25, clearance=None, hole=None, skip=(), only=None,
               inward=False):
        """A via beside each surface-mount pad on net, joined to it by a short track: the way a pad reaches its
        plane (In1 for GND, In2 for +3V3). Each via goes the first place that keeps clear of every other net's pad,
        track and via, of the outline and of every keep-out, trying the direction away from its part's centre first
        and then the others round it. A pad that already has a track or via of its own, and an exposed pad with
        vias in it, is left as it is. clearance(other net) gives the mm a track keeps from that net's copper (0.2
        if not given), and hole(other net) what a via keeps (clearance if not given). only, a set of (ref, pad),
        takes just those pads, copper of their own or not: the way out for a pin the autorouter can't escape.
        inward tries toward the part's centre first: under a QFN, inside its ring of pads. Returns the (ref, pad)
        of each pad it found no room for."""
        clearance = clearance or (lambda other: 0.2)
        hole = hole or clearance
        (r, gap) = (size / 2, 0.1)                       # gap: kept between a via and any pad of its own net
        pads = self.copper_pads()
        thermal = {(ref, num) for (ref, num, kind, _, _) in pads if kind == 'thru_hole'}
        missed = []
        for (ref, num, kind, pnet, box) in pads:
            if kind != 'smd' or pnet != net or ref in skip or (ref, num) in thermal or \
                    (only is not None and (ref, num) not in only):
                continue
            centre = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
            stub = round(min(width, box[2] - box[0], box[3] - box[1]), 4)    # no wider than the pad: fine pitches
            if only is None and (
                    any(t.net == net and any(_in_box(p, box) for p in (t.points[0], t.points[-1])) for t in self.tracks)
                    or any(v.net == net and _in_box((v.x, v.y), box) for v in self.vias)):
                continue
            near = [q for q in pads if q[4][0] < box[2] + 4 and q[4][2] > box[0] - 4 and
                    q[4][1] < box[3] + 4 and q[4][3] > box[1] - 4 and not (q[0] == ref and q[1] == num)]
            tracks = [(t, a, b) for t in self.tracks for (a, b) in zip(t.points, t.points[1:])
                      if t.net != net and min(a[0], b[0]) < box[2] + 4 and max(a[0], b[0]) > box[0] - 4 and
                      min(a[1], b[1]) < box[3] + 4 and max(a[1], b[1]) > box[1] - 4]
            vias = [v for v in self.vias if abs(v.x - centre[0]) < 5 and abs(v.y - centre[1]) < 5]
            (px, py, _) = self.places[ref]
            away = (centre[0] - px, centre[1] - py)
            dirs = [(math.cos(math.radians(a)), -math.sin(math.radians(a))) for a in range(0, 360, 45)]
            dirs.sort(key=lambda d: (d[0] * away[0] + d[1] * away[1]) * (1 if inward else -1))
            spot = None
            for d in dirs:
                reach = abs(d[0]) * (box[2] - box[0]) / 2 + abs(d[1]) * (box[3] - box[1]) / 2 + gap + r
                for i in range(31):
                    c = (centre[0] + d[0] * (reach + 0.05 * i), centre[1] + d[1] * (reach + 0.05 * i))
                    if self._via_fits(net, c, r, centre, stub, near, tracks, vias, clearance, hole, gap):
                        spot = (round(c[0], 4), round(c[1], 4))
                        break
                if spot:
                    break
            if spot is None:
                missed.append((ref, num))
                continue
            self.tracks.append(Track(net, 'F.Cu', float(stub), (centre, spot)))
            self.vias.append(Via(net, spot[0], spot[1], float(size), float(drill)))
        return missed

    def _via_fits(self, net, c, r, start, width, pads, tracks, vias, clearance, hole, gap):
        edge = 0.3 + r
        if not (edge <= c[0] <= self.width - edge and edge <= c[1] <= self.height - edge):
            return False
        eps = 1e-6
        for k in self.keepouts:
            poly = k.polygon
            if inside(c, poly) or min(to_segment(c, a, b) for (a, b) in zip(poly, poly[1:] + poly[:1])) < r:
                return False
        for z in self.zones:                             # another net's copper area on an outer layer
            if z.net != net and z.layer in ('F.Cu', 'B.Cu'):
                poly = z.polygon
                if inside(c, poly) or \
                        min(to_segment(c, a, b) for (a, b) in zip(poly, poly[1:] + poly[:1])) < r + hole(z.net) - eps:
                    return False
        for (_, _, _, pnet, box) in pads:
            if _box_distance(c, box) < r + (gap if pnet == net else hole(pnet)) - eps:
                return False
            if pnet != net and _segment_box_distance(start, c, box) < width / 2 + clearance(pnet) - eps:
                return False
        for (t, a, b) in tracks:
            if to_segment(c, a, b) < r + t.width / 2 + hole(t.net) - eps or \
                    _segment_distance(start, c, a, b) < width / 2 + t.width / 2 + clearance(t.net) - eps:
                return False
        for v in vias:
            if math.hypot(c[0] - v.x, c[1] - v.y) < r + v.size / 2 + (0.15 if v.net == net else hole(v.net)) - eps:
                return False
            if v.net != net and to_segment((v.x, v.y), start, c) < v.size / 2 + width / 2 + clearance(v.net) - eps:
                return False
        return True

    def unplaced(self):
        return sorted(set(self.parts) - set(self.places))


def fingerprint(layout, nets):
    """A hash of all that Freerouting's routes rest on: the nets, the outline, the places, the zones and keep-outs,
    and the scripted copper. autoroute.py keeps it beside the session, and build_board.py takes the session only
    while the layout still gives the same hash. The outer pours are left out: Freerouting never sees them."""
    data = {'nets': {name: [list(node) for node in nodes] for (name, nodes) in sorted(nets.items())},
            'outline': [layout.width, layout.height, layout.corner],
            'places': {ref: list(at) for (ref, at) in sorted(layout.places.items())},
            'tracks': layout.tracks, 'vias': layout.vias, 'zones': layout.zones, 'keepouts': layout.keepouts}
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode('utf-8')).hexdigest()
