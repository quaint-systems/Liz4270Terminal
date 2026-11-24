# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""The board as KiCad sees it: kicad-cli's netlist, ERC and DRC, as Python objects."""

import json
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import paths


@dataclass
class Part:
    ref: str
    value: str
    footprint: str
    fields: dict
    dnp: bool
    in_bom: bool


class Netlist:
    def __init__(self, parts, nets):
        self.parts = parts            # ref -> Part
        self.nets = nets              # net name, sheet path dropped -> {(ref, pin)}
        self._by_pin = {node: name for (name, nodes) in nets.items() for node in nodes}

    def net(self, ref, pin):
        """The net on ref's pin, or None if the pin is alone (unconnected or no-connect)."""
        return self._by_pin.get((ref, str(pin)))

    def on(self, net):
        return self.nets.get(net, set())


def short(name):
    """'/Coax/RX_P' -> 'RX_P'; '+3V3' -> '+3V3'; a pin alone on its net ('unconnected-(...)') -> None."""
    if name.startswith('unconnected-'):
        return None
    return name.rsplit('/', 1)[-1]


def _cli(*args):
    result = subprocess.run([paths.KICAD_CLI, *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f'kicad-cli {" ".join(args)} failed:\n{result.stdout}{result.stderr}')


def _merge(named_nodes):
    """{short name: {(ref, pin)}} from (full name, nodes) pairs. Two different full names that shorten to one
    name are refused, so a clash between sheet-local nets can't hide inside one merged net."""
    nets, full = {}, {}
    for name, nodes in named_nodes:
        short_name = short(name)
        if short_name is None:
            continue
        if short_name in full and full[short_name] != name:
            raise ValueError(f'nets {full[short_name]!r} and {name!r} both shorten to {short_name!r}')
        full[short_name] = name
        nets.setdefault(short_name, set()).update(nodes)
    return nets


def export(schematic):
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, 'net.xml')
        _cli('sch', 'export', 'netlist', '--format', 'kicadxml', '-o', out, schematic)
        root = ET.parse(out).getroot()
    parts = {}
    for comp in root.iter('comp'):
        fields = {f.get('name'): (f.text or '') for f in comp.iter('field')}
        props = {p.get('name') for p in comp.iter('property')}
        parts[comp.get('ref')] = Part(ref=comp.get('ref'), value=comp.findtext('value') or '',
                                      footprint=comp.findtext('footprint') or '', fields=fields,
                                      dnp='dnp' in props, in_bom='exclude_from_bom' not in props)
    named = [(net.get('name'), {(n.get('ref'), n.get('pin')) for n in net.iter('node')}) for net in root.iter('net')]
    return Netlist(parts, _merge(named))


def erc(schematic):
    """Every ERC violation as (severity, type, description, item descriptions)."""
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, 'erc.json')
        _cli('sch', 'erc', '--format', 'json', '--severity-all', '-o', out, schematic)
        with open(out, encoding='utf-8') as stream:
            report = json.load(stream)
    return [(v['severity'], v['type'], v['description'], tuple(i.get('description', '') for i in v.get('items', [])))
            for sheet in report.get('sheets', []) for v in sheet.get('violations', [])]


def export_xml(schematic, out):
    """Writes kicad-cli's XML netlist of schematic to out."""
    _cli('sch', 'export', 'netlist', '--format', 'kicadxml', '-o', out, schematic)


def kicad_name(name):
    """A net's name as the board holds it. The XML netlist unescapes the slash in a pin's name ('GPIO40/ADC0'); the
    schematic and the board keep it as {slash}, and DRC's parity check compares those."""
    for head in ('unconnected-(', 'Net-('):
        if name.startswith(head):
            return head + name[len(head):].replace('/', '{slash}')
    return name


def leaf(name):
    """A board net's short name: '/Coax/LINE_C' -> 'LINE_C'; 'Net-(U1-USB_DM)' and 'unconnected-(...)' stay whole."""
    return name if name.startswith(('unconnected-(', 'Net-(')) else name.rsplit('/', 1)[-1]


def _natural(ref):
    head = ref.rstrip('0123456789')
    return (head, int(ref[len(head):] or 0))


def board_netlist(xml_path):
    """What the board needs from an XML netlist: the components, in reference order, as dicts (ref, value, fpid,
    fields, props, path), and {net name as the board holds it: [(ref, pin)]}."""
    root = ET.parse(xml_path).getroot()
    comps = []
    for c in root.iter('comp'):
        sheet = c.find('sheetpath')
        comps.append({'ref': c.get('ref'), 'value': c.findtext('value') or '', 'fpid': c.findtext('footprint'),
                      'fields': {f.get('name'): f.text or '' for f in c.iter('field')},
                      'props': {p.get('name'): p.get('value') for p in c.iter('property')},
                      'path': sheet.get('tstamps') + c.findtext('tstamps')})
    nets = {kicad_name(n.get('name')): sorted((node.get('ref'), node.get('pin')) for node in n.iter('node'))
            for n in root.iter('net')}
    return sorted(comps, key=lambda c: _natural(c['ref'])), nets


def drc(board, parity=True):
    """kicad-cli's DRC of a board file: (violations, unconnected items, parity issues), each a list of
    (severity, type, description, item descriptions) as erc() gives them. The zones are filled first: the board file
    keeps them unfilled (pcb_build.py)."""
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, 'drc.json')
        _cli('pcb', 'drc', '--format', 'json', '--severity-all', '--refill-zones',
             *(['--schematic-parity'] if parity else []), '-o', out, board)
        with open(out, encoding='utf-8') as stream:
            report = json.load(stream)

    def rows(key):
        return [(v['severity'], v['type'], v['description'], tuple(i.get('description', '') for i in v.get('items', [])))
                for v in report.get(key, [])]
    return rows('violations'), rows('unconnected_items'), rows('schematic_parity')
