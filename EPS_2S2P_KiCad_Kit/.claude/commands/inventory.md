---
description: Phase 0 — inventory the KiCad project and downloaded libraries (read-only)
---
Phase 0: inventory. **Do not modify any KiCad file in this phase.**

1. Run `kicad-cli version` and record it. If `kicad-cli` isn't found, check the paths in
   `docs/04_kicad_workflow.md` and tell Julien.
2. `git status`. If not a repo: `git init`, add a `.gitignore` (copy `templates/gitignore`),
   commit everything as "Initial state before Claude Code".
3. List what exists: `.kicad_pro`, `.kicad_sch`, `.kicad_pcb`, `sym-lib-table`, `fp-lib-table`,
   everything under `libs/` (symbols, `.pretty` folders, 3D files), any vendor zips.
4. If downloaded parts are still zipped or outside `libs/`, ask Julien where they are before
   touching them. Extract zips into `libs/_downloads/<part>/` (never overwrite).
5. Run `python3 scripts/audit_libs.py --project . --parts docs/05_parts_list.csv --out LIB_AUDIT.md`.
6. List files in `datasheets/` and compare with `datasheets/README.md`.
7. Report in under 15 lines: KiCad version, counts, which parts look present/missing, anything
   surprising. Wait for Julien's OK.
