# 03 — Library linking: symbol → footprint → 3D model

## How KiCad links the three

```
sym-lib-table ──► libs/symbols/S-8252AAC.kicad_sym
                     (symbol "S-8252AAC-M6T1U"
                        (property "Footprint" "EPS_Footprints:SOT-23-6")   ◄── link 1
                        (pin ... (number "1")) ...)
fp-lib-table  ──► libs/footprints/EPS_Footprints.pretty/SOT-23-6.kicad_mod
                     (footprint "SOT-23-6"
                        (pad "1" smd ...) ...
                        (model "${KIPRJMOD}/libs/3d/SOT-23-6.step" ...))  ◄── link 2
```

- **Link 1:** the symbol's `Footprint` property = `<fp-lib nickname>:<footprint name>`. The
  nickname must exist in `fp-lib-table`. The footprint name is the `.kicad_mod` file name
  without the extension.
- **Link 2:** the footprint's `(model "...")` path points at the `.step`/`.wrl` file.
- **Pin ↔ pad:** connectivity on the PCB works by matching symbol pin **numbers** to footprint
  pad **numbers**. Names don't matter, numbers do.

## Project rules

1. **Library tables are project-local** (`sym-lib-table`, `fp-lib-table` next to the
   `.kicad_pro`) and use `${KIPRJMOD}`:
   ```
   (sym_lib_table
     (version 7)
     (lib (name "EPS_Symbols")(type "KiCad")(uri "${KIPRJMOD}/libs/symbols/EPS_Symbols.kicad_sym")(options "")(descr "LOBOSAT EPS parts"))
   )
   ```
   Check the `version` number that the user's KiCad writes (look at an existing table or
   `kicad-cli version`) and match it.
2. **Prefer one consolidated library** for downloaded parts: `EPS_Symbols.kicad_sym` and
   `EPS_Footprints.pretty`. Downloaded parts usually arrive as one lib per part; merge them
   (copy each `(symbol ...)` block into one file) so the tables stay short. Keep the originals in
   `libs/_downloads/` untouched.
3. **3D model paths** use `${KIPRJMOD}/libs/3d/<file>.step`. Fix any path that is absolute or
   points into a download folder. Prefer `.step` over `.wrl` (both are fine for rendering;
   STEP is needed for mechanical export).
4. **Standard parts may use KiCad's built-in libraries** (resistors, capacitors, generic
   diodes, `power:GND`, `Device:R`, etc.) with standard footprints such as
   `Resistor_SMD:R_0603_1608Metric`. Built-ins already have 3D models. This is preferred over
   downloading generic passives.
5. **Footprint names**: keep the downloaded name unless it's unreadable. If you rename, rename
   the file, the `(footprint "name")` inside it, and every symbol's Footprint property that
   references it.
6. **Datasheet field**: fill the symbol's `Datasheet` property with the local path
   `${KIPRJMOD}/datasheets/<file>.pdf` if the PDF exists, else the manufacturer URL.
7. **Fields for BOM** on every symbol: `MPN` (manufacturer part number) and `Manufacturer`.
   Add `LCSC`/`Mouser` fields only if Julien has them.

## Checks for each part (record result in `LINK_REPORT.md`)

| Check | How |
|---|---|
| Symbol exists | Found in a lib listed in `sym-lib-table` |
| Footprint property set and resolvable | Nickname in `fp-lib-table`, `.kicad_mod` file exists |
| Pin numbers ⊆ pad numbers | Every symbol pin number has a pad with the same number (`scripts/audit_libs.py`) |
| Unused pads explained | Pads with no matching pin: exposed pad (should be a pin, or connected via net-tie per datasheet) or mounting/NC pads |
| Exposed pad handled | Datasheet says EP → GND? Symbol must have a pin for it (often numbered like `9` or `EP`), and it must be connected |
| 3D model resolves | Path expands with `${KIPRJMOD}` to an existing file |
| 3D model aligned | Can't be checked from text. List these for Julien to eyeball in the 3D viewer |
| Package matches parts list | Footprint package matches `docs/05_parts_list.csv` "Package" column |

## Known pitfalls with downloaded parts (SnapEDA / Ultra Librarian / SamacSys)

- Symbol `Footprint` field empty or pointing at a nickname like `SamacSys_Parts:...` that
  doesn't exist in this project → re-point it to `EPS_Footprints:...`.
- Exposed pad numbered differently in symbol vs footprint (e.g. symbol `EP`, footprint `9`).
  Fix the **symbol** pin number to match the footprint, after confirming with the datasheet.
- 3D model `offset`/`rotate` from the vendor is sometimes wrong. Don't "fix" it blindly. Flag it.
- KiCad 5-era files (`.lib`, `.dcm`, `.mod`) need converting. Ask Julien to open them once in
  KiCad's Symbol/Footprint Editor and save, or use `kicad-cli sym upgrade` / `kicad-cli fp upgrade`
  if available in his version.
- Duplicate symbol names after merging libraries → rename with the full MPN.
