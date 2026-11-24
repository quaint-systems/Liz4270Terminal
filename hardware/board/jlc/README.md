# Ordering the Liz4270 board, revision A, from JLCPCB

The order files below are for a four-layer board with top-side Standard PCB Assembly (PCBA).
**Source the Murata 78602/8JC coax transformer (T1) before ordering.** The assembly files omit it so you can fit it
by hand. The [assembly table](#assembly-options) lists the other unpopulated positions.

## Files

| File | Use |
| --- | --- |
| [liz4270-revA-gerbers.zip](liz4270-revA-gerbers.zip) | Gerbers and separate plated and non-plated drill files |
| [liz4270-revA-bom.csv](liz4270-revA-bom.csv) | Assembly bill of materials, one line per LCSC part |
| [liz4270-revA-cpl.csv](liz4270-revA-cpl.csv) | Top-side component placement list |

## Place an order

1. Download all three files from the same repository revision. Upload the Gerber ZIP for the PCB quote and select the [PCB options](#pcb-options) below.
2. Enable PCB Assembly and select [Standard, top side](#assembly-options). Upload the BOM and CPL.
3. Confirm each matched part, including stock and the [parts listed below](#sourcing-at-bom-matching). Review [placement and orientation](#check-the-placement-preview) before paying.
4. When the boards arrive, fit T1 with its line pins (1 and 6) toward the BNC connector, then follow the [board bring-up notes](../README.md#bring-up-notes).

See [JLCPCB's PCBA ordering instructions](https://jlcpcb.com/help/article/how-do-i-place-a-pcba-order) for the quote form.

## PCB options

| Option | Setting |
| --- | --- |
| Layers | 4 |
| Size | 100 x 80 mm (JLC reads it from the Gerbers) |
| Thickness | 1.6 mm |
| Impedance control | **Yes, JLC04161H-7628.** The pairs' widths come from JLC's calculator for it: TMDS 0.225/0.2 mm (100 Ω), USB 0.25/0.15 mm (90 Ω) |
| Surface finish | **ENIG recommended** for flat pads under the RP2350B's 0.4 mm QFN-80. Lead-free HASL is also an option, though it can dome the exposed pads' open vias. |
| Via covering | Tented |
| Min via hole size/diameter | **0.2 mm/(0.3/0.35 mm) or finer**, not the default: 176 vias are 0.2 mm drills in 0.45 mm pads, and the exposed pads' 27 thermal holes are 0.2 mm |
| Min track/spacing | **4/4 mil or finer**: the narrowest tracks are 0.12 mm (4.7 mil), the minimal design's regulator's; copper gaps are at least 0.15 mm, the net classes' |
| Mark on PCB | "Specify position": the `JLCJLCJLCJLC` text on the back silkscreen, at x 50, y 13 from the board's top-left corner |

KiCad names the inner-layer Gerbers `liz4270-GND.g1` (In1) and `liz4270-+3V3.g2` (In2).
If the uploader misreads the layer count, confirm the four copper layers before placing the order. If you need to
change the layer names, set them to `In1.GND` and `In2.3V3` in `tools/board/board_setup.py`, then rebuild and regenerate.

### The exposed pads' vias

U1, U8 and U14 use KiCad's ThermalVias footprints. The vias are open in the pad and masked on the back, and the stencil
keeps paste off them. Leave the filled-and-capped via option off.

## Assembly options

| Option | Setting |
| --- | --- |
| Type | Standard, top side |
| Upload | `liz4270-revA-bom.csv` and `liz4270-revA-cpl.csv` (121 parts) |
| Through-hole | JLC fits J3 (BNC), J5 (USB-A pair), J7 (speaker), SW1 and SW2, and J4's and J6's shell pegs |

Not placed, so not in either CSV:

| Ref | Why |
| --- | --- |
| T1 | Murata 78602/8JC transformer, hand-fitted. It has J-leads on a 2.54 mm pitch. |
| J2 | the bench header (BOOMELE 2.54-2*7P, C71397), for the logic analyzer |
| R3 | QSPI_SS pull-up, only for another flash |
| U5, C26 | optional coax ESD protection |
| C61 | optional 100 nF on RUN for troubleshooting unexpected resets |
| TP1–TP5, H1–H4 | bare test pads and mounting holes |

## Sourcing at BOM matching

Check stock in the quote when you order. For parts supplied through Global Sourcing or consignment, confirm each
one on the component matching page. [JLCPCB component matching guide](https://jlcpcb.com/help/article/component-matching-guidelines-for-pcba-orders)

| Ref | Part | LCSC | Sourcing notes |
| --- | --- | --- | --- |
| U1 | RP2350B | C42415655 | Check Global Sourcing if out of stock. |
| L1 | AOTA-B201610S3R3-101-T | C42411119 | Check Global Sourcing if out of stock. |
| Y1, Y2 | ABM8-272-T3 | C20625731 | Check stock for both crystals. |
| U4 | DS34LV87TM/NOPB | C1543778 | DS34LV87TMX/NOPB (C2672589) is the reel part. AM26LV31E is also compatible because pin 12 is held high. |
| U6 | TPD13S523PWR | C2865622 | This device also protects HDMI pin 18. |
| J5 | Molex 67298-3091 | C588409 | The current BOM uses this part with the original Würth footprint. |
| FB1 | TDK MPZ2012S221AT000 | C76818 | The current BOM uses this 3 A bead in the original 0805 footprint. |
| T1 | Murata 78602/8JC | C7040198 | Source separately for hand assembly. |

The first spin used a Würth 61400826021 (C5366339) at J5 and a Murata BLM21PG221SN1D (C85840) at FB1.
The current BOM uses the replacements above on the same PCB layout. Molex and Würth number the two rows of J5
differently, so compare signals by pad position. The white Molex 67298-4091 (C503681) uses the same land pattern.
CUI's UJ2-ADH-1-TH (C3197848) also uses that pattern and is rated for 1.0 A.

If you substitute a part, check its pinout, land pattern, ratings, and enclosure clearance before regenerating the
order files.

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

If a part is turned or shifted in the preview, confirm the intended placement against the PCB and the part drawing.
Apply corrections in the generator as described below. Use JLC's placement confirmation option to review the final
assembly, including through-hole parts.

The fixes so far:

- **U3 and U4, 270°:** on the Liz 4174 (Sept 26, 2026), JLC's preview drew its SOIC-16s lying down with pin 1 at the
  bottom left.
- **From this board's first preview (Oct 10, 2026):** U2, U6, U7, U8, U9, U10, U11 and U14 by 270°; U12, U13, L1,
  Q1, Q2, SW1 and SW2 by 180°; J4 by 90°. J6 moves 1.6 mm into the board: JLC drew its body that far toward the edge,
  its leads off their pads.

## Regenerate the order files

The committed files are ready to upload for the listed parts. If you change a part, update
[`tools/board/parts.py`](../../../tools/board/parts.py) and rebuild the [schematic and PCB](../README.md) first.
For a placement correction, update `ROTATION_FIX` in
[`tools/board/make_jlc.py`](../../../tools/board/make_jlc.py) in degrees counterclockwise or `OFFSET_FIX` in board
millimetres (x right, y down). Include the date and the measurement from the preview.

With KiCad 10 and Python 3 installed, run these commands from the repository root. Set `KICAD_CLI` to the full path
to `kicad-cli` if you use a location other than the default macOS KiCad app.

```sh
python3 tools/board/make_jlc.py
python3 tools/board/make_jlc.py --check
```

Regenerate the CSVs from the source so the part data and placements stay in sync. The `--check` command compares the
committed files with a fresh export, ignoring timestamps in the Gerbers.
