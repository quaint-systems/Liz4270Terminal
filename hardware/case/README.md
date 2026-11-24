# The Liz4270 case

A desktop case for the Liz4270 board, revision A (#134), in two printed parts that split at the board's top face. The board drops into the base, and the lid lifts off with every cable still plugged in. The case is CERN-OHL-P v2, like the board (`hardware/LICENSE`).

## What to buy

- four 3 mm pan-head self-tapping screws for plastic, 16 mm long, sold as M3 × 16 self-tapping or ISO 7049 ST2.9 × 16;
- four stick-on rubber feet, about 10 mm across;
- the speaker, an Adafruit 3923, and a JST-PH pigtail (Adafruit 261), as the board's spec lists them.

## Printing

| STL | Filament | How |
| --- | --- | --- |
| `stl/base.stl` | PLA or PETG HF | on its floor |
| `stl/lid.stl` | PLA or PETG HF | upside down, as the file lies |
| `stl/inlay.stl` | a second colour | with the lid, for two colours |
| `stl/light-pipe.stl` | clear PLA or PETG | two of them, at 100% infill |

- 0.4 mm nozzle, 0.2 mm layers, no supports. Start at 4 wall loops and 25% infill.
- **Two colours (AMS):** in Bambu Studio, import `lid.stl` and `inlay.stl` together. Answer yes to loading them as one object with several parts, and give the inlay part the second filament.
- **One colour:** print `lid.stl` alone. The name and the LEDs' labels are cut 0.6 mm into its top.

## The Debug Probe's notch

The committed STLs have none. For a notch in the front wall, which the Debug Probe's SWD cable lies in with the lid on, build both parts with the switch, from this directory:

```bash
openscad -o base-probe.stl --export-format binstl -D 'part="base"' -D debug_probe_hole=true case.scad
```

```bash
openscad -o lid-probe.stl --export-format binstl -D 'part="lid"' -D debug_probe_hole=true case.scad
```

## Putting it together

1. Clip the speaker into its pocket under the lid, face first, and press the two light pipes in from the top.
2. Sit the board on the base's standoffs, and plug the speaker into J7.
3. Lower the lid straight on, and drive the four screws up through the base. Stop when they're snug: they cut their own thread.
4. Stick the feet into their recesses.


## Changing it

The source is OpenSCAD 2026.10.11, the `openscad@snapshot` cask (`brew install --cask openscad@snapshot`). The stable 2021.01 lacks `textmetrics`, which the labels need.

| File | What |
| --- | --- |
| `case.scad` | the entry point: `part` and the switch; `part = "assembly"` shows it all in place with the board |
| `dims.scad` | every constant: walls, clearances, the plugs, the screws, the speaker, the text |
| `base.scad`, `lid.scad` | one part each, built where it sits |
| `cutters.scad` | what both parts cut away, and the plugs' bodies the tests check |
| `labels.scad` | the text, in 3270font from `tools/sim/fonts/` |

- **Positions** come from `hardware/board/export/liz4270-board.scad`, which `tools/board/make_exports.py` writes from the board. Don't edit it. The same run writes the board's model, `liz4270.stl`, for the assembly view.
- **Coordinates** are the board's, in mm from its top-left corner, with y negated, and z up from the board's underside.
- **After a change,** run these from the repository root:
  - `python3 tools/case/make_case.py` rewrites the STLs;
  - `python3 -m unittest discover -s tools/case` checks every part against the board's own 3D model, the plugs' bodies and each feature.
  - Both run OpenSCAD with a scratch `HOME`, so a 3270font installed in `~/Library/Fonts` can't stand in for the repo's subset, which has the same family name. One installed for every user, in `/Library/Fonts`, still would.
- **For heat-set inserts** instead of self-tapping screws, `PILOT_D = 4.0` in `dims.scad` takes a 5.7 mm M3 insert and an M3 × 12 screw.
