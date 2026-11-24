// Copyright (c) 2026, CoffeeMuse
// SPDX-License-Identifier: CC-BY-4.0

#import "../style.typ": *
#import "../keymap-rows.typ": keymaps, keymap-table, keymap-about
#import "../keys.typ": functions

= Keymaps <keymaps>

A keymap#ix[keymap] says which 3483-V key each key on a USB keyboard sends. Liz4270 chooses one for each
keyboard by its USB vendor and product ID, and gives a keyboard that no keymap claims the default,
#keymaps.first().title. A keymap can be an overlay on another, listing only the keys it
changes.#ix("keymap", sub: "overlay")

Each keymap's table lists every key and chord it answers, in the order of the keys' USB codes:

- *Key* is the key or chord on the USB keyboard.
- *3483-V key* is the key Liz4270 sends, as a 3483-V would, after the Shift or Alt it sends it with where
  that isn't your own.
- *Does* is what the controller reads from the whole press, as oec reads it: a 3270 key (@keys-3270), the
  character typed, or the display station's own key (@local-keys). A dash means the key sends nothing.

#key("Non-US #") is the key some keyboards send for #key("\\"), and the keymap reads it as #key("\\").

#for km in keymaps [
  == #km.title

  #keymap-about(km)

  #figure(kind: table, caption: [#km.title], keymap-table(km, functions))
]
