# Liz4270 board, revision A

The revision A board combines an RP2350B, a 3270 coax interface, DVI output, USB keyboard host, and audio.

## The schematic is generated

`liz4270.kicad_sch` and its six sheets are written by `tools/board/build_schematic.py` from `tools/board/sheet_*.py`.
**Don't edit them in KiCad**: change the sheet modules and rebuild, or the next build overwrites the edit, and
`tools/board/test_board.py` fails while the two disagree.

A sheet lists each part with its nets, as labels on short stubs, or draws a circuit with wires: `Sheet.drawing()` in
`tools/board/schematic.py`. Every sheet is drawn, with its decoupling banks and the like still listed.

```bash
python3 tools/board/build_schematic.py
python3 -m unittest discover -s tools/board -p 'test_*.py'
```

The tests need KiCad 10 (`kicad-cli`). They check the netlist against the board pin map and topology, every
supply pin's rail, which parts are fitted, every part's LCSC number, and ERC.

## Sheets

| Sheet | What |
| --- | --- |
| MCU | RP2350B on the Fruit Jam's pin map; core regulator and crystal as Raspberry Pi's minimal design; flash; BOOTSEL and RESET; SWD; the bench header; drawn as a circuit, with BOOTSEL, SWD and the bench header beside it and the decoupling listed |
| Coax | the Liz 4174's port 1 (interface3 port 0), with TX_ACTIVE's pull-down and the unused channels held; drawn as a circuit |
| Video | HSTX DVI through 220 R; TPD13S523; DDC level shifter; hot-plug to GPIO7; drawn as a circuit, with the TPD13S523's clamps by label |
| USB host | AP2171W port switch; CH334F hub; stacked dual USB-A with ESD on each port; drawn as a circuit |
| Audio | TLV320DAC3100 and its 1.8 V; speaker connector; drawn as circuits, the decoupling listed |
| Power | USB-C input and protection, 3.3 V LDO and power LED, drawn as a circuit; test points and mounting holes, bare copper that JLC's order leaves out |

## The board is generated

`liz4270.kicad_pcb`, `liz4270.kicad_pro` and `liz4270.kicad_dru` are written by `tools/board/build_board.py`, from
the schematic's netlist and `tools/board/layout.py`. **Don't save the board from KiCad**: a review that does is undone
with `git checkout hardware/board/`, and `test_layout.py` fails while the files and the generator disagree.
`build_board.py --check` builds it in a scratch directory and lists what differs.

- **The layout is Python.** `layout.py` draws the outline and runs one `layout_<block>.py` per block, in order: edge,
  MCU (with `regulator.py`, Raspberry Pi's minimal design moved onto U1), coax, video, USB host, power, audio, then
  the escapes and the planes. Each block places its parts and may add scripted copper, by pad name (`'U1.63'`) or by
  point. `pcb_build.py` runs it in KiCad's own Python (3.9, the one with `pcbnew`).
- **Coordinates** are board millimetres from the outline's top-left corner, x to the right, y down; angles turn
  counter-clockwise, as KiCad shows them. The board sits at (20, 20) on KiCad's page with the grid and drill origins
  there, so the GUI reads the same numbers as the code.
- **The floorplan,** 100 x 80 mm, four layers (In1 ground, In2 +3V3). The connector edge is the bottom, y = 80: the
  BNC (J3, x 10), USB-C (J6, x 30), the USB-A pair (J5, x 49.5), HDMI (J4, x 71), BOOTSEL behind its pinhole (SW1,
  x 85) and RESET in the corner (SW2, x 94.6).

  | Block | Where |
  | --- | --- |
  | MCU | U1 at (42, 32), turned 180°: its coax pins face left, HSTX right, the regulator, QSPI and USB down; Y1, J1 (SWD) and J2 (bench header) above it |
  | Coax | U3 and U4 at x 10–21, y 38; T1 at (10, 57); the line side, x 0–19.5 below y 59, with the BNC, inside a 1.5 mm band no copper crosses on any layer |
  | Video | R20–R27 right of U1; U6 at (75.5, 61) behind HDMI |
  | USB host | U8 at (57.75, 50), Y2, U7, and U9/U10 at the USB-A pair |
  | Power | U12 at (29, 52), U11, F1, D4 and FB1 behind USB-C |
  | Audio | U14 at (78, 16), U13 and J7 (speaker) in the top right |

- **Routing** is partly scripted and partly Freerouting's. The blocks script what must not move: TMDS and USB pairs
  matched in length, the crystals, the regulator, the coax drive and the line side, the power spines.
  `tools/board/autoroute.py` routes the rest with Freerouting 2.4.1 (a few minutes) and keeps its session beside the
  board: `liz4270.ses`, with `liz4270.route.json`, a fingerprint of everything the routes were made from (layout,
  net classes, rules, footprints). `build_board.py` takes the session in only while the fingerprint matches;
  otherwise it builds the board unrouted and says so, and `TestRouted.test_the_session_is_current` fails. A rerun
  reshuffles all of Freerouting's copper and can leave a pin or two unconnected, which an escape in
  `layout_escapes.py` fixes; check DRC after each.
- **The zones are saved unfilled.** KiCad's filler doesn't give the same polygons from one run to the next, so a
  filled board couldn't be checked byte for byte. DRC, the plots and the tests fill them; in the GUI, press B.

The other generators, each with `--check` where it writes committed files:

- `render_board.py`: PNG renders of layers, crops, or the 3D view, for looking at a layout.
- `make_models.py`: plain-body STEP models, through FreeCAD, for the footprints KiCad 10.0.6 has no model for.
- `make_exports.py`: `export/`, the outline DXF, the holes, fronts, inside parts and labels as JSON, and the same
  as an OpenSCAD include for the case (`hardware/case/`, #134); and its STEP and STL (made, not committed).
- `make_jlc.py`: `jlc/`, the Gerbers, BOM and placement file for JLC; `jlc/README.md` gives the order's options.

## Not fitted on revision A

R3 (QSPI_SS pull-up, only for another flash), U5 and C26 (coax ESD, bring-up step 7 decides), C61 (100 n on RUN, for a
board that resets by itself), J2 (bench header). None of them is on JLC's order, and neither is T1, fitted by hand
on spin 1 (`jlc/README.md`).

## Bring-up notes

- About 50 µF sits on +5V with no inrush limit, as on the Fruit Jam.
- Scope +5V while plugging in a short USB-C cable. SPKVDD and the TPD13S523 are rated only to 6.0 V, and the SMAJ5.0A
  starts clamping at 6.4 V. If +5V overshoots, add damped bulk.
- When GPIO11 goes high, the AP2171 charges about 210 µF at its current limit for about 1 ms. Check that the console
  doesn't drop.
- T1 is fitted by hand: a J-lead on a 2.54 mm pitch, line pins (1, 6) toward the BNC.

## License

CERN-OHL-P v2 (`hardware/LICENSE`, the text from
https://gitlab.com/ohwr/project/cernohl/-/wikis/uploads/3eff4154d05e7a0459f3ddbf0674cae4/cern_ohl_p_v2.txt,
where https://ohwr.org/cern_ohl_p_v2.txt redirects). The coax front end is interface3's (ISC, Hans Hübner), and the
core regulator follows Raspberry Pi's RP2350 minimal design (MIT); `NOTICE` lists both.
