// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: CC-BY-4.0

// The keymaps as tools/manual/keys.py found them in the firmware, Chapter 4's and Appendix A's tables, and the
// check that every key they give has its description, and that each key oec ignores is marked so (#136).

#import "style.typ": meta, keys

#let keymap-data = json(meta.build + "/data/keymaps.json")
#let keymaps = keymap-data.keymaps

// A reading that names a key, PA1 or ERASE_EOF, rather than typing a character.
#let named(reading) = reading.clusters().len() > 1

// The 3483-V key a row sends where oec reads no key from it: "Caps Lock", "Shift+Copy/Play/Test", or none.
#let sends(r) = r.at("sends", default: none)

// Every key the keymaps give that needs a description: what oec reads, and what it reads nothing from.
#let names-in(data) = data.keymaps.map(km => km.rows.map(r => r.reads.filter(named)
  + if sends(r) != none { (sends(r),) } else { () }).flatten()).flatten().dedup()
#let locals-in(data) = data.keymaps.map(km => km.rows.map(r => r.local)).flatten().filter(l => l != none).dedup()

// The groups Chapter 4 sets its tables by.
#let groups = ("send", "pf", "edit", "move", "other", "character")

#let check-keys(data, functions, local) = {
  let names = names-in(data)
  let astray = functions.pairs().filter(((_, f)) => f.group not in groups).map(((n, f)) => n + " (" + f.group + ")")
  if astray.len() > 0 { panic("keys in no group Chapter 4 sets: " + astray.join("; ")) }
  let missing = names.filter(n => n not in functions)
  let extra = functions.keys().filter(n => n not in names)
  if missing.len() > 0 { panic("keys with no description: " + missing.join("; ")) }
  if extra.len() > 0 { panic("descriptions of keys no keymap has: " + extra.join("; ")) }
  let working = names.filter(n => n in data.oec_ignores and functions.at(n).oec)
  let ignored = names.filter(n => n not in data.oec_ignores and not functions.at(n).oec)
  if working.len() > 0 { panic("keys oec ignores, described as working under oec: " + working.join("; ")) }
  if ignored.len() > 0 { panic("keys oec acts on, described as ignored by oec: " + ignored.join("; ")) }
  let locals = locals-in(data)
  let unsaid = locals.filter(l => l not in local)
  let unknown = local.keys().filter(l => l not in locals)
  if unsaid.len() > 0 { panic("local keys with no description: " + unsaid.join("; ")) }
  if unknown.len() > 0 { panic("descriptions of local keys no keymap has: " + unknown.join("; ")) }
}

// The firmware's USB names for keys a PC keyboard labels otherwise.
#let key-names = ("Left GUI": "Left Windows", "Right GUI": "Right Windows")

// A row's chord as keycaps: Shift + Alt + X. The names are strings, so none is read as markup.
#let chord(row) = keys(..row.chord, key-names.at(row.key, default: row.key))

// The rows of km that give name: a key it reads, or a local key.
#let keys-for-rows(km, name) = km.rows.filter(r => name in r.reads or r.local == name or sends(r) == name)

// Keys some keyboards send in another's place: Non-US # for \, which the keymap reads alike.
#let aliases = ("Non-US #": "\\")

// The rows of km a reader is shown for name: an alias's only where its key's own row doesn't give it too.
#let shown-rows(km, name) = {
  let found = keys-for-rows(km, name)
  found.filter(r => not (r.key in aliases
    and found.any(o => o.key == aliases.at(r.key) and o.chord == r.chord)))
}

// Every chord of km that gives name, as keycaps; the build stops if there's none.
#let keys-for(km, name) = {
  if keys-for-rows(km, name).len() == 0 { panic("no key in " + km.name + " gives " + name) }
  shown-rows(km, name).map(chord).join[ or ]
}

// Which keyboards a keymap is chosen for, and the keymap it overlays, by its title.
#let keymap-about(km) = {
  if km.devices.len() > 0 [Chosen for the keyboards with USB IDs #km.devices.join(", ").] else [Chosen for any
    keyboard that no other keymap claims.]
  if km.base != none [ An overlay on #keymaps.find(k => k.name == km.base).title.]
}

#let rule-hline = table.hline(stroke: 0.5pt)
#let key-table(columns, head, cells) = table(columns: columns,
  table.header(rule-hline, ..head, rule-hline),
  ..cells,
  rule-hline)

// A function's name, with † where oec does nothing with it.
#let function-name(f) = if f.oec { f.name } else [#f.name#super[†]]

// One group of Chapter 4's 3270 keys that km gives: the key, what to press, and what it does, then any extra
// rows' cells. A key only another keymap gives is described all the same, and Appendix A sets it.
#let function-table(km, functions, group, extra: ()) = key-table((1.25in, 1.5in, 1fr),
  ([Key], [Press], [What it does]),
  functions.pairs().filter(((name, f)) => f.group == group and keys-for-rows(km, name).len() > 0)
    .map(((name, f)) => (function-name(f), keys-for(km, name), f.body)).flatten() + extra)

// Chapter 4's local keys: the display station's own.
#let local-table(km, local) = key-table((1.25in, 1.5in, 1fr), ([Key], [Press], [What it does]),
  local.pairs().map(((name, body)) => (name, keys-for(km, name), body)).flatten())

// The 3483-V key a row sends, after the Shift and Alt it is sent with; none when it keeps the PC's own.
#let sent(row) = if row.label == none { [—] } else {
  let with = if row.modifiers in ("kept", "none") { () } else { row.modifiers.split("+") }
  (with.map(m => m + " + ") + (row.label,)).join()
}

// What the controller reads from a row's press, as oec does: a 3270 key, a character, or a local key.
#let does(row, functions) = if row.local != none { row.local } else if sends(row) != none {
  functions.at(sends(row)).name } else if row.reads.len() == 0 { [—] } else {
  row.reads.map(r => if named(r) { functions.at(r).name } else { r }).join(", ")
}

// Appendix A's table of a keymap: every key and chord it answers.
#let keymap-table(km, functions) = key-table((1.9in, 1.6in, 1fr), ([Key], [3483-V key], [Does]),
  km.rows.map(r => (chord(r), sent(r), does(r, functions))).flatten())
