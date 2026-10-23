# 04 — KiCad workflow, tools and gotchas

## 0. Before anything

```bash
kicad-cli version            # note the version: file formats differ between 7, 8 and 9
git status || git init       # commit the untouched state first
```

- KiCad must be **closed** while files are edited.
- If `kicad-cli` isn't on PATH:
  - Windows: `C:\Program Files\KiCad\<ver>\bin\kicad-cli.exe`
  - macOS: `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli`
- Python helpers: `pip install kiutils` (reads/writes `.kicad_sym`, `.kicad_mod`, `.kicad_sch`).
  kiutils lags behind new KiCad versions. If it fails to parse or writes a file KiCad rejects,
  fall back to writing the s-expressions yourself and validate with `kicad-cli`.

## 1. Verification commands (run after every phase)

```bash
mkdir -p out
# Library audit (this kit's script)
python3 scripts/audit_libs.py --project . --parts docs/05_parts_list.csv --out LINK_REPORT.md

# File is valid + connectivity (if this fails, the schematic file is malformed)
kicad-cli sch export netlist --format kicadsexpr -o out/EPS_2S2P.net EPS_2S2P.kicad_sch

# ERC (KiCad 8+). Add --format json if your version supports it.
kicad-cli sch erc --severity-all -o out/erc.rpt EPS_2S2P.kicad_sch

# Netlist vs intended connections (this kit's script)
python3 scripts/check_netlist.py out/EPS_2S2P.net expected_nets.json

# BOM (KiCad 8+)
kicad-cli sch export bom -o out/bom.csv EPS_2S2P.kicad_sch

# PDF for Julien to review visually
kicad-cli sch export pdf -o out/EPS_2S2P.pdf EPS_2S2P.kicad_sch
```

Run `--help` on any subcommand if a flag is rejected: flags changed between versions.

`expected_nets.json` is something **you write** from `docs/02_connections.md`: a map of
net name → list of `"REF:PIN_NAME"` (or `"REF:PIN_NUMBER"`) once reference designators exist. Example:

```json
{
  "BAT_MID": ["U2:VC", "U3:VC1", "BT1:-", "BT2:-", "BT3:+", "BT4:+"],
  "VBUS":    ["F2:2", "U1:BAT", "Q3:S"]
}
```

`check_netlist.py` reports missing and unexpected connections per net.

## 2. Generating / editing schematics: the gotchas

Write a generator script (`scripts/gen_schematic.py`) instead of hand-editing. Keep the
coordinate math in one function.

**Coordinates**
- Units are **mm**. Place everything on the **1.27 mm (50 mil) grid**. Pins that land off-grid
  will not connect.
- **Y axis flips.** Symbol libraries are Y-up, schematics are Y-down. For a symbol placed at
  `(X, Y)` with rotation 0 and no mirror, a library pin at `(px, py)` ends up at
  `(X + px, Y − py)`. Apply rotation/mirror to `(px, −py)` before adding `(X, Y)`.
- The pin's `(at x y angle)` in the library is the pin's **connection point** (outer end).

**Connecting things**
- A label, wire end or no-connect connects **only** if its point exactly equals the pin's
  connection point. "Close" is not connected.
- Simplest reliable method: put a **label directly on each pin's connection point** (no wires).
  Same label text = same net. It's ugly but correct. Julien can tidy the drawing later.
- Global labels connect across all sheets. Local labels connect within one sheet only.
- Unused pins get a **no-connect** flag at the pin point.
- Nets fed only by a connector, battery clip or switch need a **`PWR_FLAG`** symbol, or ERC
  reports "power input pin not driven". Typical: `VSOLAR_RAW`, `BAT_P`, `BAT_N`, `GND`.

**File structure (KiCad 7/8/9)**
- Each `.kicad_sch` embeds copies of every library symbol it uses in `(lib_symbols ...)`,
  named exactly like the `lib_id` (`"EPS_Symbols:S-8252AAC-M6T1U"`). Missing embed = symbol
  shows as missing/garbled.
- Every symbol, wire, label, sheet has a unique `uuid`.
- Hierarchical instance data: each placed symbol carries
  `(instances (project "EPS_2S2P" (path "/<root-uuid>/<sheet-uuid>" (reference "U3") (unit 1))))`.
  Sheet symbols in the root carry their own instance/page data. Wrong paths = references show
  as `U?` or duplicate.
- Reference designators must be unique across the whole hierarchy. Assign them in the
  generator (`U1`, `U2`, ... by sheet) rather than relying on annotation.
- Multi-unit parts (LM393 has 2 comparators + power unit, FS8205A may be split) need one
  placed symbol per unit with the same reference and different `unit` numbers.
- When unsure of exact syntax, open an existing `.kicad_sch` written by the **same KiCad
  version** (a blank project Julien creates is fine) and copy its structure.

**Fields**
- Set on every symbol: `Reference`, `Value`, `Footprint`, `Datasheet`, `MPN`, `Manufacturer`.
- `DNP` parts: KiCad 8+ has a `(dnp yes)` attribute on the symbol. Use it for the optional
  heater and per-cell fuses.

## 3. Phase discipline

- Do one sheet at a time: generate → export netlist → check → commit.
- Never mass-replace across all files with sed/regex without re-running the checks.
- If ERC shows an error you can't fix without a design decision, leave it, and write it in
  your summary with the exact ERC message.
