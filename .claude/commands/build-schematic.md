---
description: Phase 3 — generate the hierarchical schematic and connect every net
---
Phase 3: build the schematic. Read `docs/02_connections.md` and `docs/04_kicad_workflow.md` §2.

1. Ask Julien to create a blank project in their KiCad version (or use the existing one) so you
   have a correctly-formatted root `.kicad_sch` to copy structure from. KiCad must be closed.
2. Write `scripts/gen_schematic.py`. It should:
   - create one sheet per block listed in `docs/01_design_spec.md`, plus the root sheet
   - place each part from the linked libraries (embed `lib_symbols`), on the 1.27 mm grid
   - assign reference designators deterministically per sheet
   - connect pins by placing labels exactly on pin connection points (Y-axis flip!)
   - add no-connect flags on unused pins, `PWR_FLAG`s where needed, `(dnp yes)` on DNP parts
   - set Value = `TBD` where `docs/06_open_questions.md` says so
3. Build **one sheet at a time**, starting with `battery`. After each sheet:
   export netlist → check → fix → commit.
4. Write `expected_nets.json` from `docs/02_connections.md` as you assign references.
5. Never guess a pin. If a datasheet is missing, place the part, leave its pins unconnected
   with a text note, and add it to `MISSING_PARTS.md`.
6. Report per sheet: parts placed, nets connected, anything left open. Wait.
