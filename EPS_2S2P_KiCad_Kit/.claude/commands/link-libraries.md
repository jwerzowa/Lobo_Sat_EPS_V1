---
description: Phase 1 — consolidate libraries and link symbol → footprint → 3D model
---
Phase 1: link libraries. Read `docs/03_library_linking.md` first.

1. Create/repair project-local `sym-lib-table` and `fp-lib-table` with `${KIPRJMOD}` paths.
   Match the table `version` your KiCad writes.
2. Consolidate downloaded parts into `libs/symbols/EPS_Symbols.kicad_sym`,
   `libs/footprints/EPS_Footprints.pretty/`, `libs/3d/`. Keep originals in `libs/_downloads/`.
   Prefer writing `scripts/consolidate_libs.py` over hand copying, so it can be re-run.
3. For every symbol: set `Footprint` = `EPS_Footprints:<name>` (or a KiCad built-in footprint
   for generic passives), set `Datasheet`, add `MPN` and `Manufacturer` fields.
4. For every footprint: set `(model "${KIPRJMOD}/libs/3d/<file>.step")`. Keep vendor
   offset/rotation values unchanged.
5. Fix pin↔pad number mismatches only when the datasheet confirms the fix. Otherwise record it.
6. Re-run `python3 scripts/audit_libs.py --project . --parts docs/05_parts_list.csv --out LINK_REPORT.md`
   until every remaining problem is either fixed or explained.
7. Write `MISSING_PARTS.md` from `templates/MISSING_PARTS.md`. Include every MPN marked
   MISSING, every partial part, every library problem and every missing datasheet.
8. List the parts whose 3D alignment Julien should eyeball in KiCad's 3D viewer.
9. Commit: "Link symbols, footprints and 3D models". Report and wait.
