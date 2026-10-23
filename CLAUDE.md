# CLAUDE.md — LOBOSAT EPS 2S2P (KiCad)

You are helping set up the KiCad project for the **LOBOSAT Electrical Power System (EPS)**
redesign: a solar-charged 2S2P Li-ion board for the UNM Student Satellite Group.

The owner (Julien) is an EE student. They want to **learn from the work**, so explain what you
changed and why in short notes, and never hide a guess.

## Your job (in priority order)

1. **Link the libraries.** Every symbol → correct footprint → correct 3D model, using the
   parts already downloaded into `libs/`.
2. **Report what's missing.** Anything not found or not linkable goes in `MISSING_PARTS.md`
   (template: `templates/MISSING_PARTS.md`). Do not invent parts to fill gaps.
3. **Hook up the schematic.** Build the schematic (one flat sheet, Julien's preference) and connect every net described
   in `docs/02_connections.md`.
4. **Prove it.** ERC clean (or every remaining warning explained), netlist matches the intended
   connections, BOM matches `docs/05_parts_list.csv`.

PCB layout is **out of scope** unless Julien asks. Footprint assignment is in scope.

## Read these first (in this order)

| File | What it gives you |
|---|---|
| `images/power_tree.png` | The whole system in one picture |
| `images/battery_protection_topology.png` | How the 2S2P pack, protection ICs and cutoff FETs connect |
| `docs/01_design_spec.md` | Blocks, rails, key values, design decisions you must respect |
| `docs/02_connections.md` | **The source of truth for nets.** Sheet by sheet, net by net |
| `docs/03_library_linking.md` | How symbol/footprint/3D linking works and the rules for this project |
| `docs/04_kicad_workflow.md` | File-format gotchas, `kicad-cli` commands, how to generate schematics safely |
| `docs/05_parts_list.csv` | Every part, its block, ref prefix, expected package and quantity |
| `docs/06_open_questions.md` | Things NOT decided yet. Do not decide them yourself |

## Hard rules

- **Never guess a pinout.** Pin numbers and pin functions come from the symbol you were given
  and the datasheet in `datasheets/`. If the symbol and datasheet disagree, stop and write it in
  `MISSING_PARTS.md` under "Library problems".
- **Never substitute a part.** If `S-8252AAC-M6T1U` is missing, do not use the AAJ or a DW01A.
  Report it.
- **Pin numbers must match pad numbers.** A symbol pin "3" must land on footprint pad "3".
  `scripts/audit_libs.py` checks this. Exposed/thermal pads (e.g. BQ29209, LT3652, LMZM33602)
  must be connected to the net the datasheet says (usually GND), not left floating.
- **Project-local libraries only.** All library tables use `${KIPRJMOD}` paths. No absolute
  paths to `C:\Users\...` or `/home/...`, so the project works on every teammate's machine.
- **Don't touch values marked TBD** in `docs/06_open_questions.md` (rail voltages, VIN_REG
  divider, solar string size). Put a placeholder value `TBD` on the symbol and list it in your
  final summary.
- **Back up before editing.** Run `git status` first. If the project isn't a git repo, `git init`
  and commit the original state before you change anything. Commit after each phase with a clear
  message so Julien can review diffs.
- **Make edits reproducible.** Prefer writing a Python generator/editor script in `scripts/`
  and running it, over hand-editing large `.kicad_sch` files. Re-running the script should
  produce the same result.
- **Verify with tools, not by reading.** After every phase run the checks in
  `docs/04_kicad_workflow.md`. A file that "looks right" is not proof.
- KiCad must be **closed** while you edit project files, or it will overwrite your changes.
  Remind Julien of this before you start editing.

## Phases (do them in order, stop and report after each)

Use the slash commands in `.claude/commands/` — they contain the detailed checklist for each phase.

| Phase | Command | Output |
|---|---|---|
| 0. Inventory | `/inventory` | `LIB_AUDIT.md`: what's in `libs/`, KiCad version, project state |
| 1. Link libraries | `/link-libraries` | Updated lib tables, symbol Footprint fields, footprint 3D paths, `LINK_REPORT.md` |
| 2. Missing parts | (part of phase 1) | `MISSING_PARTS.md` |
| 3. Build schematic | `/build-schematic` | Single flat `.kicad_sch`, generator script |
| 4. Check | `/check` | ERC report, netlist diff, BOM, short summary for Julien |

Stop after each phase, summarize in under 15 lines, and wait for Julien's OK before the next one.

## Current state (2026-10-23)

Phases 0–4 have been run once. ERC 0 violations, netlist matches `expected_nets.json` exactly,
library audit clean. What's open is in `MISSING_PARTS.md` and `docs/06_open_questions.md`.
Decisions Julien made that override the kit docs: **INA228 + ADS1015** telemetry (ACS37612
dropped) and **Rail A = 3.3 V, Rail B = 5 V** (see `docs/01_design_spec.md`).

**The schematic is generated.** `EPS_Lobosat_V1.kicad_sch` is ONE flat A0 sheet (Julien doesn't
want hierarchical sheets): each block is a dashed box with a title; same label text = same net.
It is written by
`scripts/gen_schematic.py`; libraries by `scripts/consolidate_libs.py`. To change a connection,
edit `build_sheets()` in the generator and re-run, don't hand-edit the generated files, or the
next run overwrites them. When Julien starts tidying the drawing by hand in KiCad, the
generator stops being the source of truth: ask Julien before re-running it after that point.

```bash
python3 scripts/consolidate_libs.py      # libs/_downloads -> EPS_Symbols / EPS_Footprints / libs/3d
python3 scripts/gen_schematic.py         # -> EPS_Lobosat_V1.kicad_sch, expected_nets.json
bash scripts/fetch_datasheets.sh         # datasheets/*.pdf (gitignored)
```

`kicad-cli` is not on PATH on Julien's Mac: use `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli`.

## Project layout

```
EPS_Lobosat_V1/
├── CLAUDE.md  README.md
├── EPS_Lobosat_V1.kicad_pro / .kicad_sch (single flat sheet, generated) / .kicad_pcb (empty)
├── libs/
│   ├── symbols/EPS_Symbols.kicad_sym         # generated, all project symbols
│   ├── footprints/EPS_Footprints.pretty/     # generated
│   ├── 3d/                                   # STEP models referenced by the footprints
│   └── _downloads/                           # vendor downloads, never edited
├── sym-lib-table  fp-lib-table               # ${KIPRJMOD} paths only
├── docs/  images/  scripts/  templates/  datasheets/
├── LINK_REPORT.md  MISSING_PARTS.md  expected_nets.json
└── out/               # ERC / netlist / BOM / PDF exports (gitignored)
```
