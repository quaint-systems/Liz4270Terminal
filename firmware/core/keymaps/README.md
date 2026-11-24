# Keymaps

A keymap says which 3483-V key each USB key sends. It's pure data: the
translator (`../keyboard.c`) takes care of the 3270 modifiers, releases,
typematic and the status queue, and the 3483-V's own codes, releases and
repeat classes live in `../keys3483.c`, taken from captures of a real 3483-V.
A keymap can't get any of those wrong.

## The format

`../keymap.h` defines it. Each keymap is a `keymap_t` with its own entries:

    {usage, when, key, mods}

- **usage:** a USB usage, by its `U_*` name (`../usb_usage.h`). The modifier
  byte's Ctrl and GUI bits are usages too (`U_LCTRL`, `U_RGUI`, …). The PC's
  Shift and Alt are not: they are always the 3483-V's own Shift and Alt.
- **when:**
  - `KM_ANY` for the usage's base entry.
  - An exact chord of `KM_SHIFT`, `KM_ALT` and `KM_CTRL` for a chord entry.
  - `KM_CTRL` matches only when Ctrl arrives in the same USB report as the
    key, as some keyboards send their extra keys. A person pressing Ctrl first
    always gets Ctrl's own entry.
- **key:** the 3483-V key to send, by its `K_*` name (`../keys3483.h`).
  - `K_NOTHING` sends nothing.
  - `K_SETUP` is the local SetUp function.
  - Never a 3270 modifier (`K_LSHIFT` and the like): use `mods`.
- **mods:**
  - `KM_KEEP` passes the PC's Shift and Alt through: Shift+A is a capital,
    and Alt+Delete is the 3483-V's DelWd.
  - Anything else is exact: `KM_NONE`, `KM_SHIFT`, `KM_ALT`, or both. The
    translator lifts or adds Shift and Alt for that key, then puts the PC's
    back when it is let go.

A press is looked up by the PC's Shift and Alt: an exact chord entry if
there is one, else the base entry.

**Overlays.** A keymap may name a `base` map and list only what it changes.
Lookup finds a chord entry anywhere in the chain before it falls back to any
base entry, so an overlay that replaces a key's base entry still inherits its
base map's chords for that key. To drop one, list the chord with `K_NOTHING`.

**Devices.** `devices` lists the `VID << 16 | PID` values a keymap claims,
ending in 0. Keyboards that no keymap claims get the default, `us104`.

## Adding one

1. Write `<name>.c` here, after `us104.c`, with `title`, `status` and
   `devices`. Its `name` must be unique.
2. Add `&keymap_<name>` to `maps[]` in `../keymap.c`, and its file to
   `../CMakeLists.txt`.
3. Run `python tools/sim/keymap_doc.py` to write `docs/keymaps/<name>.md`,
   and read it: every row shows what oec reads from the press.
4. Run the sim tests (`python -m unittest discover -s tools/sim`). Every
   registered map must pass `test_keymaps.py`: codes that exist, chords that
   leave nothing down, one sender per make/break key, and an up-to-date page.

## Status

- **bench-tested: <keyboard>** means the project typed with this keymap,
  on that keyboard, into a host through a controller.
- **contributed, not tested by the project** means it passes the tests, but
  nobody here has the keyboard.
