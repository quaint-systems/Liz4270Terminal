#!/usr/bin/env python3
# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""Makes the board in KiCad's own Python (3.9, which has pcbnew). build_board.py runs it; it isn't run by hand.

    pcb_build.py DIR NETLIST_XML [--session FILE] [--no-pours]

DIR holds the header build_board.py wrote as liz4270.kicad_pcb, with the project file beside it. This adds every
footprint the netlist lists, with its fields, sheet path and pad nets as KiCad's Update PCB from Schematic would;
then, from layout.py, the places, outline, zones, keep-outs and text; Freerouting's routes when a session is given;
and the scripted copper, less any escape (layout_escapes) the routes don't use; a via of Freerouting's that its own
tracks meet on one layer only is left out too. KIIDs come from a fixed seed, so the same inputs write the same file.

The zones are saved unfilled. KiCad's filler doesn't give the same polygons from one run to the next (seen on
Oct 9, 2026, single-threaded too), so a filled board couldn't be checked byte for byte. The fills are made where
they're used: DRC (--refill-zones), the PDF and Gerber plots (--check-zones), and the tests' filled copy. In the GUI,
press B to fill them.
"""

import argparse
import math
import os
import sys

import pcbnew

import board_setup
import footprint
import layout
import netlist
import pcb

SEED = 4270
PARK = 10.0          # unplaced parts wait in rows this far below the board, 15 mm apart


def mm(v):
    return pcbnew.FromMM(v)


def at(p):
    return pcbnew.VECTOR2I(mm(p[0] + pcb.ORIGIN[0]), mm(p[1] + pcb.ORIGIN[1]))


def back(v):
    """A KiCad point back in board millimetres."""
    return (pcbnew.ToMM(v.x) - pcb.ORIGIN[0], pcbnew.ToMM(v.y) - pcb.ORIGIN[1])


def key(p):
    return (round(pcbnew.ToMM(p.x) - pcb.ORIGIN[0], 3), round(pcbnew.ToMM(p.y) - pcb.ORIGIN[1], 3))


class Builder:
    def __init__(self, directory, netlist_path):
        pcbnew.KIID.SeedGenerator(SEED)
        self.path = os.path.join(directory, 'liz4270.kicad_pcb')
        self.board = pcbnew.LoadBoard(self.path)
        (self.comps, nets) = netlist.board_netlist(netlist_path)
        self.nets = {}
        for name in sorted(nets):
            item = pcbnew.NETINFO_ITEM(self.board, name)
            self.board.Add(item)
            self.nets[name] = item
        self.by_pin = {node: name for (name, nodes) in nets.items() for node in nodes}
        self.by_leaf = {}
        for name in nets:
            self.by_leaf.setdefault(netlist.leaf(name), set()).add(name)
        self.layout = layout.layout({c['ref']: c['fpid'] for c in self.comps},
                                    {node: netlist.leaf(name) for (name, nodes) in nets.items() for node in nodes})
        self.footprints = {}
        self.unused = []            # escapes the session's routes don't meet: left out of copper()
        self.dead = []              # (net, at) of Freerouting's vias its tracks meet on one layer only: removed

    def net(self, name):
        """The board's net for one of layout.py's short names."""
        full = self.by_leaf.get(name, set())
        if len(full) != 1:
            raise KeyError(f'net {name!r} is {"ambiguous" if full else "not in the netlist"}: {sorted(full)}')
        return self.nets[next(iter(full))]

    def add_footprints(self):
        for c in self.comps:
            (lib, name) = c['fpid'].split(':')
            fp = pcbnew.FootprintLoad(os.path.dirname(footprint.path(c['fpid'])), name)
            if fp is None:
                raise RuntimeError(f'{c["ref"]}: no footprint {c["fpid"]}')
            fp.SetFPID(pcbnew.LIB_ID(lib, name))
            fp.SetReference(c['ref'])
            fp.SetValue(c['value'])
            for field in ('MPN', 'LCSC', 'Datasheet', 'Description'):
                fp.SetField(field, c['fields'].get(field, ''))
                fp.GetField(field).SetVisible(False)
                fp.GetField(field).SetLayer(pcbnew.F_Fab)
            if c['ref'].rstrip('0123456789') not in board_setup.SILK_REFS:
                fp.Reference().SetLayer(pcbnew.F_Fab)
            fp.SetPath(pcbnew.KIID_PATH(c['path']))
            fp.SetSheetname(c['props'].get('Sheetname', ''))
            fp.SetSheetfile(c['props'].get('Sheetfile', ''))
            fp.SetDNP('dnp' in c['props'])
            fp.SetExcludedFromBOM('exclude_from_bom' in c['props'])
            fp.SetExcludedFromPosFiles('dnp' in c['props'])
            for p in fp.Pads():
                name_ = self.by_pin.get((c['ref'], p.GetNumber()))
                if name_:
                    p.SetNet(self.nets[name_])
            if c['fpid'] in board_setup.MODELS:
                (path, offset) = board_setup.MODELS[c['fpid']]
                fp.Models().clear()
                model = pcbnew.FP_3DMODEL()
                model.m_Filename = path
                model.m_Offset = pcbnew.VECTOR3D(*offset)
                fp.Add3DModel(model)
            self.board.Add(fp)
            self.footprints[c['ref']] = fp

    def place(self):
        """Every footprint where layout.py puts it; a part it hasn't placed yet waits below the board."""
        parked = 0
        for c in self.comps:
            if c['ref'] in self.layout.places:
                (x, y, rot) = self.layout.places[c['ref']]
            else:
                (x, y, rot) = (8.0 + 15.0 * (parked % 7), self.layout.height + PARK + 15.0 * (parked // 7), 0.0)
                parked += 1
            fp = self.footprints[c['ref']]
            fp.SetOrientationDegrees(rot)
            fp.SetPosition(at((x, y)))
            if c['ref'] in self.layout.labels:
                (dx, dy, r) = self.layout.labels[c['ref']]
                ref = fp.Reference()
                ref.SetPosition(at((x + dx, y + dy)))
                ref.SetTextAngleDegrees(r)
        return parked

    def trim_silk(self):
        """Footprint silkscreen cut back to 0.1 mm inside the outline: the edge connectors' outlines run past it, the
        fab would clip them there anyway, and DRC calls them clipped."""
        m = 0.1
        box = (m, m, self.layout.width - m, self.layout.height - m)
        for fp in self.footprints.values():
            for item in list(fp.GraphicalItems()):
                if item.GetLayer() not in (pcbnew.F_SilkS, pcbnew.B_SilkS) or \
                        not isinstance(item, pcbnew.PCB_SHAPE) or item.GetShape() != pcbnew.SHAPE_T_SEGMENT:
                    continue
                (a, b) = (back(item.GetStart()), back(item.GetEnd()))
                cut = pcb.clip(a, b, box)
                if cut is None:
                    fp.Remove(item)
                elif max(abs(u - v) for (p, q) in zip(cut, (a, b)) for (u, v) in zip(p, q)) > 1e-6:
                    item.SetStart(at(cut[0]))
                    item.SetEnd(at(cut[1]))

    def outline(self):
        (w, h, r) = (self.layout.width, self.layout.height, self.layout.corner)
        for (a, b) in (((r, 0), (w - r, 0)), ((w, r), (w, h - r)), ((w - r, h), (r, h)), ((0, h - r), (0, r))):
            s = pcbnew.PCB_SHAPE(self.board)
            s.SetShape(pcbnew.SHAPE_T_SEGMENT)
            s.SetStart(at(a))
            s.SetEnd(at(b))
            s.SetLayer(pcbnew.Edge_Cuts)
            s.SetWidth(mm(0.1))
            self.board.Add(s)
        if r > 0:
            for (cx, cy, sx, sy) in ((r, r, 0, r), (w - r, r, w - r, 0), (w - r, h - r, w, h - r), (r, h - r, r, h)):
                s = pcbnew.PCB_SHAPE(self.board)
                s.SetShape(pcbnew.SHAPE_T_ARC)
                s.SetCenter(at((cx, cy)))
                s.SetStart(at((sx, sy)))
                s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T), True)
                s.SetLayer(pcbnew.Edge_Cuts)
                s.SetWidth(mm(0.1))
                self.board.Add(s)

    def _shape(self, zone, polygon):
        outline = zone.Outline()
        outline.NewOutline()
        for p in polygon:
            q = at(p)
            outline.Append(q.x, q.y)

    def zones(self, pours=True):
        connect = {'thermal': pcbnew.ZONE_CONNECTION_THT_THERMAL, 'solid': pcbnew.ZONE_CONNECTION_FULL,
                   'none': pcbnew.ZONE_CONNECTION_NONE}
        for z in self.layout.zones + (self.layout.pours if pours else []):
            zone = pcbnew.ZONE(self.board)
            zone.SetLayer(self.board.GetLayerID(z.layer))
            zone.SetNet(self.net(z.net))
            zone.SetAssignedPriority(z.priority)
            zone.SetLocalClearance(mm(z.clearance))
            zone.SetMinThickness(mm(z.min_width))
            zone.SetPadConnection(connect[z.connect])
            zone.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
            self._shape(zone, z.polygon)
            self.board.Add(zone)
        for k in self.layout.keepouts:
            zone = pcbnew.ZONE(self.board)
            zone.SetIsRuleArea(True)
            zone.SetZoneName(k.name)
            layers = pcbnew.LSET()
            for layer in k.layers:
                layers.AddLayer(self.board.GetLayerID(layer))
            zone.SetLayerSet(layers)
            zone.SetDoNotAllowTracks(k.tracks)
            zone.SetDoNotAllowVias(k.vias)
            zone.SetDoNotAllowZoneFills(k.pours)
            zone.SetDoNotAllowPads(False)
            zone.SetDoNotAllowFootprints(False)
            self._shape(zone, k.polygon)
            self.board.Add(zone)

    def texts(self):
        for t in self.layout.texts:
            text = pcbnew.PCB_TEXT(self.board)
            text.SetText(t.text)
            text.SetLayer(self.board.GetLayerID(t.layer))
            text.SetPosition(at((t.x, t.y)))
            text.SetTextSize(pcbnew.VECTOR2I(mm(t.size), mm(t.size)))
            text.SetTextThickness(mm(round(t.size * 0.15, 3)))
            text.SetTextAngleDegrees(t.rot)
            text.SetMirrored(t.layer.startswith('B.'))
            self.board.Add(text)

    def lines(self):
        for line in self.layout.lines:
            for (a, b) in zip(line.points, line.points[1:]):
                shape = pcbnew.PCB_SHAPE(self.board)
                shape.SetShape(pcbnew.SHAPE_T_SEGMENT)
                shape.SetStart(at(a))
                shape.SetEnd(at(b))
                shape.SetLayer(self.board.GetLayerID(line.layer))
                shape.SetWidth(mm(line.width))
                self.board.Add(shape)

    def _scripted(self):
        """The scripted copper as keys: tracks either way round, and vias, each with its net."""
        out = set()
        for t in self.layout.tracks:
            name = self.net(t.net).GetNetname()
            for (a, b) in zip(t.points, t.points[1:]):
                (a, b) = ((round(a[0], 3), round(a[1], 3)), (round(b[0], 3), round(b[1], 3)))
                out.add(('track', name, t.layer, min(a, b), max(a, b)))
        for v in self.layout.vias:
            out.add(('via', self.net(v.net).GetNetname(), (round(v.x, 3), round(v.y, 3))))
        return out

    def session(self, path):
        """Freerouting's routes. KiCad's import replaces every track and via; the session carries the scripted
        copper too, so its copies go, and copper() adds them back exactly as layout.py has them."""
        if not pcbnew.ImportSpecctraSES(self.board, path):
            raise RuntimeError(f'KiCad could not import {path}')
        scripted = self._scripted()
        for item in list(self.board.GetTracks()):
            if item.GetClass() == 'PCB_VIA':
                k = ('via', item.GetNetname(), key(item.GetPosition()))
            else:
                (a, b) = (key(item.GetStart()), key(item.GetEnd()))
                k = ('track', item.GetNetname(), self.board.GetLayerName(item.GetLayer()), min(a, b), max(a, b))
            if k in scripted:
                self.board.Remove(item)
        ends = [(item.GetNetname(), self.board.GetLayerName(item.GetLayer()), back(p))
                for item in self.board.GetTracks() if item.GetClass() == 'PCB_TRACK'
                for p in (item.GetStart(), item.GetEnd())]
        self.unused = self._unused_escapes(ends)

    @staticmethod
    def _met(ends, name, layer, at, size):
        """Whether a routed track of net name ends on layer within size / 2 of at."""
        return any(n == name and l == layer and math.hypot(p[0] - at[0], p[1] - at[1]) <= size / 2
                   for (n, l, p) in ends)

    def drop_dead_vias(self):
        """Removes Freerouting's vias that copper meets on one layer only, on a net with no zone and away from its
        pads: the tracks meet each other there, and the via would hang off them as dead copper (gate-3 review,
        finding 5). Runs once the scripted copper is in, which a routed via may meet."""
        zoned = {self.net(z.net).GetNetname() for z in self.layout.zones}
        scripted = {(self.net(v.net).GetNetname(), (round(v.x, 3), round(v.y, 3))) for v in self.layout.vias}
        tracks = [(t.GetNetname(), self.board.GetLayerName(t.GetLayer()), back(t.GetStart()), back(t.GetEnd()),
                   pcbnew.ToMM(t.GetWidth())) for t in self.board.GetTracks() if t.GetClass() == 'PCB_TRACK']
        for via in list(self.board.GetTracks()):
            if via.GetClass() != 'PCB_VIA' or via.GetNetname() in zoned:
                continue
            (name, at, r) = (via.GetNetname(), back(via.GetPosition()), pcbnew.ToMM(via.GetWidth(pcbnew.F_Cu)) / 2)
            if (name, (round(at[0], 3), round(at[1], 3))) in scripted:
                continue
            box = via.GetBoundingBox()
            if any(pad.GetNetname() == name and pad.GetBoundingBox().Intersects(box)
                   for fp in self.footprints.values() for pad in fp.Pads()):
                continue
            if not all(any(n == name and l == layer and pcb.to_segment(at, a, b) <= r + w / 2
                           for (n, l, a, b, w) in tracks) for layer in ('F.Cu', 'B.Cu')):
                self.dead.append((name, at))
                self.board.Remove(via)

    def _unused_escapes(self, ends):
        """The escapes the session's routes don't need, as (via, stub or None): a via that no routed track meets on
        B.Cu goes, and its stub with it if none meets that on F.Cu either. Freerouting found another way out for the pin,
        and they would hang off it as dead copper (gate-3 review, finding 5). An escape on a plane's net stays: its via
        is the way to the plane."""
        planes = {z.net for z in self.layout.zones if z.layer in ('In1.Cu', 'In2.Cu')}

        def met(via, layer):
            return self._met(ends, self.net(via.net).GetNetname(), layer, (via.x, via.y), via.size)
        return [(via, None if met(via, 'F.Cu') else stub) for (via, stub) in self.layout.escapes
                if via.net not in planes and not met(via, 'B.Cu')]

    def copper(self):
        (vias, stubs) = ({v for (v, _) in self.unused}, {t for (_, t) in self.unused if t})
        for t in self.layout.tracks:
            if t in stubs:
                continue
            for (a, b) in zip(t.points, t.points[1:]):
                track = pcbnew.PCB_TRACK(self.board)
                track.SetStart(at(a))
                track.SetEnd(at(b))
                track.SetWidth(mm(t.width))
                track.SetLayer(self.board.GetLayerID(t.layer))
                track.SetNet(self.net(t.net))
                track.SetLocked(True)
                self.board.Add(track)
        for v in self.layout.vias:
            if v in vias:
                continue
            via = pcbnew.PCB_VIA(self.board)
            via.SetPosition(at((v.x, v.y)))
            via.SetWidth(mm(v.size))
            via.SetDrill(mm(v.drill))
            via.SetNet(self.net(v.net))
            via.SetLocked(True)
            self.board.Add(via)

    def save(self):
        pcbnew.SaveBoard(self.path, self.board)


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('directory')
    parser.add_argument('netlist')
    parser.add_argument('--session')
    parser.add_argument('--no-pours', action='store_true')
    args = parser.parse_args(argv)
    b = Builder(args.directory, args.netlist)
    b.add_footprints()
    b.place()
    b.outline()
    b.zones(pours=not args.no_pours)
    b.texts()
    b.lines()
    if args.session:
        b.session(args.session)
        b.place()                   # the import may move parts by Freerouting's rounding; layout.py decides
    b.trim_silk()
    b.copper()
    if args.session:
        b.drop_dead_vias()
    b.save()
    for (net, (x, y)) in b.dead:
        print(f'via of {net} at ({x:.3f}, {y:.3f}): its tracks meet it on one layer only, so it is left out')
    for (via, stub) in b.unused:
        print(f'escape for {via.net} at ({via.x:g}, {via.y:g}): the routes leave its via unused'
              f'{" and its stub" if stub else ""}, so it is left out')
    parked = len(b.layout.unplaced())
    if parked:
        print(f'{parked} parts not placed yet: parked below the board')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
