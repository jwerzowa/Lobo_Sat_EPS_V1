#!/usr/bin/env python3
"""Audit project-local KiCad libraries: symbol -> footprint -> 3D model.

Checks, for every symbol in the project's symbol libraries:
  * Footprint property is set and resolves to an existing .kicad_mod
  * every symbol pin number exists as a pad number in that footprint
  * footprint pads with no matching pin (exposed pads, mounting pads) are listed
  * every (model ...) path in the footprint resolves to an existing file
Optionally (--parts) checks that every downloaded MPN in the parts list has a symbol.

Usage:
  python3 scripts/audit_libs.py --project . [--libs libs] [--parts docs/05_parts_list.csv] [--out LINK_REPORT.md]

No dependencies beyond the standard library. Read-only: never modifies library files.
"""
import argparse, csv, os, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sexpr import parse, child, children, walk  # noqa: E402

VAR_RE = re.compile(r"\$\{([^}]+)\}")


def expand(path, project):
    def sub(m):
        var = m.group(1)
        if var == "KIPRJMOD":
            return str(project)
        return os.environ.get(var, m.group(0))
    return VAR_RE.sub(sub, path)


def read_lib_table(path, project):
    libs = {}
    if not path.exists():
        return libs
    tree = parse(path.read_text(encoding="utf-8", errors="replace"))
    for lib in children(tree, "lib"):
        name = child(lib, "name")[1]
        uri = child(lib, "uri")[1]
        libs[name] = {"uri": uri, "path": Path(expand(uri, project))}
    return libs


def prop(sym, key):
    for p in children(sym, "property"):
        if len(p) > 2 and p[1] == key:
            return p[2]
    return None


def load_symbols(sym_file):
    tree = parse(sym_file.read_text(encoding="utf-8", errors="replace"))
    raw = {}
    for s in children(tree, "symbol"):
        name = s[1]
        pins = {}
        for pin in walk(s, "pin"):
            num, nm = child(pin, "number"), child(pin, "name")
            if num and len(num) > 1:
                pins[num[1]] = nm[1] if nm and len(nm) > 1 else ""
        ext = child(s, "extends")
        raw[name] = {
            "pins": pins,
            "extends": ext[1] if ext else None,
            "footprint": prop(s, "Footprint") or "",
            "props": {p[1]: p[2] for p in children(s, "property") if len(p) > 2},
            "power": child(s, "power") is not None,
        }
    for name, d in raw.items():  # derived symbols inherit parent pins
        if d["extends"] and not d["pins"] and d["extends"] in raw:
            d["pins"] = raw[d["extends"]]["pins"]
    return raw


def load_footprint(fp_file):
    tree = parse(fp_file.read_text(encoding="utf-8", errors="replace"))
    pads = set()
    for pad in children(tree, "pad"):
        if len(pad) > 1 and pad[1] not in ("", '""'):
            pads.add(pad[1])
    models = [m[1] for m in children(tree, "model") if len(m) > 1]
    return pads, models


def norm(s):
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".")
    ap.add_argument("--libs", default=None, help="extra folder to scan (default <project>/libs)")
    ap.add_argument("--parts", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    project = Path(a.project).resolve()
    libs_dir = Path(a.libs).resolve() if a.libs else project / "libs"

    sym_tab = read_lib_table(project / "sym-lib-table", project)
    fp_tab = read_lib_table(project / "fp-lib-table", project)

    # symbol libs: from table, plus any .kicad_sym found under libs/ that isn't in the table
    sym_files = {n: d["path"] for n, d in sym_tab.items()}
    untabled_sym = []
    if libs_dir.exists():
        tabled = {p.resolve() for p in sym_files.values() if p.exists()}
        for f in sorted(libs_dir.rglob("*.kicad_sym")):
            if f.resolve() not in tabled:
                untabled_sym.append(f)
                sym_files.setdefault(f.stem, f)
    fp_dirs = {n: d["path"] for n, d in fp_tab.items()}
    untabled_fp = []
    if libs_dir.exists():
        tabled = {p.resolve() for p in fp_dirs.values() if p.exists()}
        for d in sorted(libs_dir.rglob("*.pretty")):
            if d.is_dir() and d.resolve() not in tabled:
                untabled_fp.append(d)
                fp_dirs.setdefault(d.stem, d)

    lines, rows, problems = [], [], 0
    all_symbols = []  # (lib, name, data)
    for lib, f in sorted(sym_files.items()):
        if not f.exists():
            lines.append(f"- Symbol lib `{lib}` → `{f}` **does not exist** (external or broken path)")
            continue
        try:
            syms = load_symbols(f)
        except Exception as e:  # malformed file
            lines.append(f"- Symbol lib `{lib}` could not be parsed: {e}")
            problems += 1
            continue
        for name, d in syms.items():
            all_symbols.append((lib, name, d))

    fp_cache = {}
    for lib, name, d in all_symbols:
        if d["power"]:
            continue
        status, notes = [], []
        fp = d["footprint"]
        pads, models = None, []
        if not fp:
            status.append("NO FOOTPRINT")
        elif ":" not in fp:
            status.append("FOOTPRINT HAS NO LIB NICKNAME")
        else:
            nick, fpname = fp.split(":", 1)
            if nick not in fp_dirs:
                status.append(f"UNKNOWN FP LIB '{nick}'")
            else:
                fpfile = fp_dirs[nick] / f"{fpname}.kicad_mod"
                if not fpfile.exists():
                    status.append("FOOTPRINT FILE MISSING")
                else:
                    if fpfile not in fp_cache:
                        fp_cache[fpfile] = load_footprint(fpfile)
                    pads, models = fp_cache[fpfile]
        if pads is not None:
            pins = set(d["pins"])
            missing = sorted(pins - pads, key=_natkey)
            extra = sorted(pads - pins, key=_natkey)
            if missing:
                status.append("PIN/PAD MISMATCH")
                notes.append("pins without pad: " + ", ".join(missing))
            if extra:
                notes.append("pads without pin (check EP/mounting): " + ", ".join(extra))
            if not models:
                status.append("NO 3D MODEL")
            for m in models:
                mp = expand(m, project)
                if "${" in mp:
                    notes.append(f"3D uses external var: `{m}`")
                elif not Path(mp).exists():
                    status.append("3D FILE MISSING")
                    notes.append(f"3D path not found: `{m}`")
                elif "KIPRJMOD" not in m and not m.startswith("${KICAD"):
                    notes.append(f"3D path not ${{KIPRJMOD}}-relative: `{m}`")
        ok = not status
        problems += 0 if ok else 1
        rows.append((lib, name, fp or "—", "OK" if ok else "; ".join(status), "; ".join(notes)))

    out = ["# LINK_REPORT.md", "", f"Project: `{project}`", ""]
    out.append(f"- Symbol libs in sym-lib-table: {len(sym_tab)} | footprint libs in fp-lib-table: {len(fp_tab)}")
    out.append(f"- Symbols checked: {len(rows)} | with problems: {problems}")
    for f in untabled_sym:
        out.append(f"- Symbol lib **not in sym-lib-table**: `{f.relative_to(project) if project in f.parents else f}`")
    for d in untabled_fp:
        out.append(f"- Footprint lib **not in fp-lib-table**: `{d.relative_to(project) if project in d.parents else d}`")
    out += lines
    out += ["", "## Symbols", "", "| Lib | Symbol | Footprint | Status | Notes |", "|---|---|---|---|---|"]
    for r in rows:
        out.append("| " + " | ".join(x.replace("|", "\\|") for x in r) + " |")

    if a.parts:
        out += ["", "## Parts list coverage (downloaded parts)", "", "| MPN | Sheet | Found as | Status |", "|---|---|---|---|"]
        with open(a.parts, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                mpn = row.get("MPN", "")
                if row.get("Library") != "downloaded" or mpn in ("", "TBD", "per datasheet"):
                    continue
                key = norm(mpn.replace("-series", "").split("#")[0])
                hits = []
                for lib, name, d in all_symbols:
                    hay = [norm(name)] + [norm(v) for k, v in d["props"].items() if k in ("Value", "MPN", "MF", "Manufacturer_Part_Number", "MP")]
                    if any(key and (key in h or (len(h) >= 5 and h in key)) for h in hay):
                        hits.append(f"{lib}:{name}")
                status = "found" if hits else "**MISSING**"
                out.append(f"| {mpn} | {row.get('Sheet','')} | {', '.join(hits[:3]) or '—'} | {status} |")

    text = "\n".join(out) + "\n"
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
        print(f"wrote {a.out}: {len(rows)} symbols, {problems} with problems")
    else:
        print(text)


def _natkey(s):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]


if __name__ == "__main__":
    main()
