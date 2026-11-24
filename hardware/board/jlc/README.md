# Ordering the Liz4270 board, revision A, from JLCPCB

JLC makes the four-layer board and, with Standard PCBA, fits every part on it but T1, including the through-hole
parts (spec, "Assembly and sourcing"). T1 is fitted by hand on spin 1, because the 786J has had no stock at LCSC or JLC.

## Files

| File | Use |
| --- | --- |
| `liz4270-revA-gerbers.zip` | PCB order: Gerbers plus Excellon drill files (PTH and NPTH separate), no job file |
| `liz4270-revA-bom.csv` | PCBA BOM, one line per LCSC part |
| `liz4270-revA-cpl.csv` | PCBA placement file, top side |

`tools/board/make_jlc.py` writes all three from the board and the schematic's fields, which come from
`tools/board/parts.py`. A part change is a schematic rebuild, then a board rebuild, then this:

```bash
$PY tools/board/make_jlc.py           # write them
$PY tools/board/make_jlc.py --check   # exit 1 if a committed file differs from a fresh run
```

The script stops if a fitted part in the BOM has no LCSC number, or if a part JLC fits is missing from the placement
export. `--check` compares the Gerbers by content, their dates aside, so a board change that the order files didn't
follow shows. `tools/board/test_jlc.py` checks the files against the spec's assembly decisions, and that the planes
are filled in the plots (the board is saved with its zones unfilled). Never hand-edit the CSVs.

## PCB options

| Option | Setting |
| --- | --- |
| Layers | 4 |
| Size | 100 x 80 mm (JLC reads it from the Gerbers) |
| Thickness | 1.6 mm |
| Impedance control | **Yes, JLC04161H-7628.** The pairs' widths come from JLC's calculator for it: TMDS 0.225/0.2 mm (100 Ω), USB 0.25/0.15 mm (90 Ω) |
| Surface finish | **ENIG recommended**: it's flat for the RP2350B's 0.4 mm QFN-80, and HASL can dome the exposed pads' open vias. HASL lead-free is acceptable. CoffeeMuse decides at gate 4 |
| Via covering | Tented |
| Min via hole size/diameter | **0.2 mm/(0.3/0.35 mm) or finer**, not the default: 176 vias are 0.2 mm drills in 0.45 mm pads, and the exposed pads' 27 thermal holes are 0.2 mm |
| Min track/spacing | **4/4 mil or finer**: the narrowest tracks are 0.12 mm (4.7 mil), the minimal design's regulator's; copper gaps are at least 0.15 mm, the net classes' |
| Mark on PCB | "Specify position": the `JLCJLCJLCJLC` text on the back silkscreen, at x 50, y 13 from the board's top-left corner |

KiCad names the inner layers' Gerbers after the layers' user names: `liz4270-GND.g1` (In1) and `liz4270-+3V3.g2`
(In2). JLC goes by the `.g1` and `.g2` extensions. If its uploader misreads the layer count, rename the user names in
`tools/board/board_setup.py`'s header to `In1.GND` and `In2.3V3`, rebuild and regenerate.

### The exposed pads' vias

U1, U8 and U14 use KiCad's ThermalVias footprints: the vias are open in the pad, masked behind, and the paste is kept
off them, by CoffeeMuse's choice on Oct 9, 2026. No via-in-pad option is needed. JLC's filled-and-capped vias are free only
from six layers, and these chips dissipate under 0.5 W.

## Assembly options

| Option | Setting |
| --- | --- |
| Type | Standard, top side |
| Upload | `liz4270-revA-bom.csv` and `liz4270-revA-cpl.csv` (121 parts) |
| Through-hole | JLC fits J3 (BNC), J5 (USB-A pair), J7 (speaker), SW1 and SW2, and J4's and J6's shell pegs |

Not placed, so not in either CSV:

| Ref | Why |
| --- | --- |
| T1 | 786J transformer, hand-fitted from CoffeeMuse's stock: a J-lead on a 2.54 mm pitch, line pins (1, 6) toward the BNC |
| J2 | the bench header (BOOMELE 2.54-2*7P, C71397), for the logic analyzer |
| R3 | QSPI_SS pull-up, only for another flash |
| U5, C26 | coax ESD; bring-up step 7 decides |
| C61 | 100 n on RUN, at the chip, for a board that resets by itself; bring-up decides |
| TP1–TP5, H1–H4 | bare test pads and mounting holes |

## Sourcing at BOM matching

Stock moves daily, so note each part's stock on the day of the order. The thin ones, at JLC on Oct 10, 2026:

| Part | LCSC | Stock | If short |
| --- | --- | --- | --- |
| U1, RP2350B | C42415655 | 2,925 | Global Sourcing |
| L1, AOTA-B201610S3R3-101-T | C42411119 | 114 | Global Sourcing |
| Y1, Y2, ABM8-272-T3 | C20625731 | 9,536 | Global Sourcing |
| U4, DS34LV87TM/NOPB | C1543778 | 95 | C2672589, the DS34LV87TMX/NOPB reel part (56); an AM26LV31E also drops in, since pin 12 is high |
| U6, TPD13S523PWR | C2865622 | 200 | one maker; two 4-channel ESD arrays plus a diode and fuse on pin 18 (spec) |
| J5, Würth 61400826021 | C5366339 | 70 | enough for spin 1; none on Nov 22, see below |
| T1, Murata 78602/8JC | C7040198 | 0 | already hand-fitted; check Global Sourcing once more, and if it offers the part, take T1 out of `HAND` in `make_jlc.py` and regenerate |

Two parts chosen for spin 1 (plan 2, Task 16): J1 is FG's 1.0-3PWT (C2763613, 8,817), a clone of JST's
SM03B-SRSS-TB, which had none, whose drawing's land pattern is KiCad's footprint. F1 stays the Bourns MF-MSMF150-2
(C89648, 7,218).

Two parts changed for the reorder (Nov 22, 2026), when JLC had none of either; neither changes the board:

- **FB1** is TDK's MPZ2012S221AT000 (C76818, 233,332) in place of Murata's BLM21PG221SN1D (C85840): the same 0805
  and 220 Ω at 100 MHz, rated 3 A and 40 mΩ to the Murata's 2 A and 45 mΩ.
- **J5** is Molex's 67298-3091 (C588409, 1,202; $1.05 to the Würth's $13.80), black with 30 µin gold; the white
  67298-4091 is C503681. Würth's part is a copy of Molex's: SD-67298-008 rev D's recommended layout is KiCad's Würth
  footprint to the hundredth, so the footprint stays. Molex numbers the front row, the lower port, 1–4 and the rear
  1'–4', the other way round from Würth, so each hole keeps its signal. The body is 14.00 wide, 15.59 high and 17.30
  deep, 0.3 mm deeper at the back; J5's 3D model covers both, so boards from spin 1 and the reorder fit the case.
  CUI's UJ2-ADH-1-TH (C3197848, 240) has the same layout, its drawing checked too, but is rated 1.0 A.

## Check the placement preview

Before paying, check in JLC's preview:

- **L1:** the dot on pad 1, the +1V1 side toward COUT.
- **The QFNs:** pin 1 of U1, U8 and U14.
- **The SOICs and TSSOP:** U3 and U4 (SOIC-16, with the 270° fix below), U2 (SOIC-8), U6 (TSSOP-16).
- **The small packages:** U12's tab; U7 and U13 (SOT-23-5); U9–U11 (SOT-23-6); Q1 and Q2.
- **The diodes:** the cathodes of D1–D3 and D5 (LEDs), and D4's band on VBUS_F.
- **The crystals:** pin 1 of Y1 and Y2.
- **J1:** its opening toward the board's top edge.
- **J4 (HDMI):** turned 270°, its 19 signal pads at a 0.5 mm pitch on their pads and its four shell pegs in their
  holes.
- **The through-hole parts on their holes:** KiCad places J3, J5, J6, J7, SW1 and SW2 by a footprint origin that isn't
  the middle of their pads (J3 3.7 mm off it, J5 4.3, J6 1.5, J7 1.0, SW1 and SW2 2.6). Check that each sits on its
  holes, and J6's leads on their pads.

A part that shows turned gets a `ROTATION_FIX` entry in `make_jlc.py`, in degrees counter-clockwise, with the date,
and one that shows shifted an `OFFSET_FIX` entry, in board millimetres (x right, y down), measured in the preview and
dated; then regenerate and commit before ordering. Never hand-edit the CSV. Confirm the PCB options' exact choices on
JLC's form at gate 4, since it names them itself.

The fixes so far:

- **U3 and U4, 270°:** on the Liz 4174 (Sept 26, 2026), JLC's preview drew its SOIC-16s lying down with pin 1 at the
  bottom left.
- **From this board's first preview (Oct 10, 2026):** U2, U6, U7, U8, U9, U10, U11 and U14 by 270°; U12, U13, L1,
  Q1, Q2, SW1 and SW2 by 180°; J4 by 90°. J6 moves 1.6 mm into the board: JLC drew its body that far toward the edge,
  its leads off their pads.

Tick JLC's "Confirm Parts Placement" too, as a backstop for the through-hole parts' positions.
