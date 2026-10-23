# EPS 2S2P — Claude Code starter kit for KiCad

## Setup (5 minutes)

1. Copy **everything in this folder** into the root of your KiCad project folder (next to the
   `.kicad_pro`). If you don't have a project yet, create an empty one in KiCad called
   `EPS_2S2P`, close KiCad, then copy this in.
2. Put your downloaded parts in `libs/`:
   - `libs/symbols/` → `.kicad_sym` files
   - `libs/footprints/` → `.pretty` folders
   - `libs/3d/` → `.step` / `.wrl` files
   - Vendor zips (SnapEDA, Ultra Librarian, SamacSys): drop them in `libs/_downloads/` and
     Claude Code will unpack them.
3. Put datasheet PDFs in `datasheets/` (list and links in `datasheets/README.md`). The more
   datasheets are there, the fewer parts Claude Code has to leave unconnected.
4. **Close KiCad.**
5. Open a terminal in the project folder and run `claude`.

## Running it

Type the phases one at a time and review each result before moving on:

```
/inventory          # read-only look at what you have
/link-libraries     # symbol → footprint → 3D, writes LINK_REPORT.md and MISSING_PARTS.md
/build-schematic    # generates the hierarchical schematic, one sheet at a time
/check              # ERC, netlist check, BOM, PDF
```

Every phase ends with a git commit, so you can `git diff` what changed or roll back.

## What's in here

| Path | For |
|---|---|
| `CLAUDE.md` | Instructions Claude Code reads automatically |
| `docs/` | Design spec, net list by sheet, linking rules, KiCad gotchas, parts list, open questions |
| `images/` | Power tree and battery protection topology (PNG + SVG) |
| `scripts/audit_libs.py` | Checks every symbol → footprint → 3D link and pin/pad numbers. Run it yourself anytime |
| `scripts/check_netlist.py` | Compares the exported netlist to the intended connections |
| `templates/` | `MISSING_PARTS.md` layout, `.gitignore` |
| `.claude/commands/` | The four phase commands |
| `.claude/settings.json` | Lets Claude run `kicad-cli`, the scripts and git without asking each time; blocks `rm -rf` and `git push` |

## Before you trust the result

- Open the schematic in KiCad and look at each sheet. The generator places labels directly on
  pins: electrically correct, visually crowded. Tidy the drawing yourself.
- Check every value marked `TBD` (list in `docs/06_open_questions.md`).
- Look at each part in the 3D viewer. Vendor models are often rotated or offset.
- Re-check the battery sheet against the S-8252 and BQ29209 datasheet application circuits.
  That's the sheet where a mistake costs the most.
