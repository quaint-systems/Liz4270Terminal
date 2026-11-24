// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: CC-BY-4.0

// SetUp's rows as tools/manual/setup_walk.py found them in the firmware, and the check that each one
// has its description, each description a row, and each row the firmware doesn't act on a description
// that says so (#136).

#import "style.typ": meta, sans-sb

#let setup-rows = json(meta.build + "/data/setup.json")

// "Display Setup, page 1 / Rule line / Style": the screen, the heading it sits under if any, and its label.
#let row-key(r) = (r.screen, ..if r.parent != "" { (r.parent,) } else { () }, r.label).join(" / ")

// The description of a row the firmware doesn't act on, where pressing it sounds the alarm:
// unavailable[Not available on Liz4270: the alarm sounds.]
#let unavailable(body) = (unavailable: true, body: body)
#let marked-unavailable(p) = type(p) == dictionary
#let described(p) = if marked-unavailable(p) { p.body } else { p }

#let check-prose(rows, prose) = {
  let keys = rows.map(row-key)
  let missing = keys.filter(k => k not in prose)
  let extra = prose.keys().filter(k => k not in keys)
  if missing.len() > 0 { panic("SetUp rows with no description: " + missing.join("; ")) }
  if extra.len() > 0 { panic("descriptions of SetUp rows the firmware doesn't have: " + extra.join("; ")) }
  let wrong(acted) = rows.filter(r => r.acted == acted and marked-unavailable(prose.at(row-key(r))) == acted)
  let acted = wrong(true).map(row-key)
  let alarm = wrong(false).map(row-key)
  if acted.len() > 0 { panic("SetUp rows the firmware acts on, described as unavailable: " + acted.join("; ")) }
  if alarm.len() > 0 { panic("SetUp rows that sound the alarm, described as working: " + alarm.join("; ")) }
}

#let choices-cell(r) = r.choices.map(c => if c == r.at("default") { strong(c) } else { c }).join(", ")

// One screen's settings: a heading row for each group, its rows indented under it, the default in bold.
#let setup-table(rows, prose, screen) = {
  let mine = rows.filter(r => r.screen == screen)
  let labels = mine.map(r => r.label)
  let cells = ()
  let group = ""
  for r in mine {
    if r.parent != "" and r.parent != group and r.parent not in labels {
      cells.push(table.cell(colspan: 3, inset: (top: 7pt, bottom: 3pt, x: 5pt), text(font: sans-sb, r.parent)))
    }
    group = r.parent
    let label = if r.parent != "" { pad(left: 0.8em, r.label) } else { r.label }
    cells += (label, choices-cell(r), described(prose.at(row-key(r))))
  }
  table(columns: (1.5in, 1.4in, 1fr),
    table.header(
      table.hline(stroke: 0.5pt),
      [Setting], [Choices], [What it does],
      table.hline(stroke: 0.5pt)),
    ..cells,
    table.hline(stroke: 0.5pt))
}

// A menu's items and what each does.
#let menu-table(rows, prose, screen) = table(columns: (2.2in, 1fr),
  table.header(
    table.hline(stroke: 0.5pt),
    [Item], [What it does],
    table.hline(stroke: 0.5pt)),
  ..rows.filter(r => r.screen == screen).map(r => (r.label, described(prose.at(row-key(r))))).flatten(),
  table.hline(stroke: 0.5pt))
