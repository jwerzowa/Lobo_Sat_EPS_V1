---
description: Phase 4 — run ERC, netlist diff and BOM, and summarize for Julien
---
Phase 4: verify. Run every command in `docs/04_kicad_workflow.md` §1.

1. ERC: fix real errors. For each warning you leave, give the exact ERC text and why it's OK.
2. `python3 scripts/check_netlist.py out/EPS_2S2P.net expected_nets.json` must PASS.
3. BOM: compare `out/bom.csv` with `docs/05_parts_list.csv` (quantities, MPNs, DNP flags).
4. Export `out/EPS_2S2P.pdf` for visual review.
5. Final summary for Julien (under 25 lines):
   - what's done, what's TBD (with the list from `docs/06_open_questions.md`)
   - remaining ERC warnings
   - contents of `MISSING_PARTS.md` in one line each
   - parts to eyeball in the 3D viewer
   - suggested next step
6. Commit: "Schematic connected and verified".
