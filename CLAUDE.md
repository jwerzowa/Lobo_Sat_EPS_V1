# CLAUDE.md — LOBOSAT EPS 2S2P (KiCad)

You are helping set up the KiCad project for the **LOBOSAT Electrical Power System (EPS)**
redesign: a solar-charged 2S2P Li-ion board for the UNM Student Satellite Group.

The owner (Julien) is an EE student. He wants to **learn from the work**, so explain what you
changed and why in short notes, and never hide a guess.

## Your job (in priority order)

1. **Link the libraries.** Every symbol → correct footprint → correct 3D model, using the
   parts already downloaded into `libs/`.
2. **Report what's missing.** Anything not found or not linkable goes in `MISSING_PARTS.md`
   (template: `templates/MISSING_PARTS.md`). Do not invent parts to fill gaps.
3. **Hook up the schematic.** Build the hierarchical schematic and connect every net described
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
| 3. Build schematic | `/build-schematic` | Hierarchical `.kicad_sch` files, generator script |
| 4. Check | `/check` | ERC report, netlist diff, BOM, short summary for Julien |

Stop after each phase, summarize in under 15 lines, and wait for Julien's OK before the next one.

## Expected project layout

```
EPS_2S2P/
├── CLAUDE.md
├── EPS_2S2P.kicad_pro / .kicad_sch / .kicad_pcb
├── sheets/            # one .kicad_sch per block (see docs/02_connections.md)
├── libs/
│   ├── symbols/       # *.kicad_sym  (downloaded parts, one lib per part is fine)
│   ├── footprints/    # *.pretty folders
│   └── 3d/            # *.step / *.wrl
├── sym-lib-table      # project-local, ${KIPRJMOD}/libs/symbols/...
├── fp-lib-table       # project-local, ${KIPRJMOD}/libs/footprints/...
├── docs/  images/  scripts/  templates/  datasheets/
├── LIB_AUDIT.md  LINK_REPORT.md  MISSING_PARTS.md   # you create these
└── out/               # ERC/netlist/BOM exports (gitignored)
```

If Julien's downloaded parts are somewhere else (e.g. a `Downloads` folder of SnapEDA /
Ultra Librarian / SamacSys zips), ask where, then copy/extract them into `libs/` first.
