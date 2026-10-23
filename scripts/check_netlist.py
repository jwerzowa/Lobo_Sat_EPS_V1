#!/usr/bin/env python3
"""Compare a KiCad netlist (kicadsexpr) against intended connections.

Usage:
  kicad-cli sch export netlist --format kicadsexpr -o out/EPS_Lobosat_V1.net EPS_Lobosat_V1.kicad_sch
  python3 scripts/check_netlist.py out/EPS_Lobosat_V1.net expected_nets.json

expected_nets.json: {"NET_NAME": ["REF:PIN", ...], ...}
PIN may be the pin number ("U2:5") or the pin name/function ("U2:VC").
KiCad prefixes local/hierarchical net names with the sheet path (e.g. "/battery/BAT_P_F");
matching ignores that prefix. Exit code 1 if any expected connection is missing.
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sexpr import parse, child, children, walk  # noqa: E402


def load_netlist(path):
    tree = parse(Path(path).read_text(encoding="utf-8", errors="replace"))
    nets = {}
    for net in walk(tree, "net"):
        name_n = child(net, "name")
        if not name_n:
            continue
        name = name_n[1]
        nodes = set()
        for nd in children(net, "node"):
            ref = child(nd, "ref")[1]
            pin = child(nd, "pin")[1]
            pf = child(nd, "pinfunction")
            nodes.add(f"{ref}:{pin}")
            if pf and len(pf) > 1 and pf[1]:
                nodes.add(f"{ref}:{pf[1]}")
        nets[name] = nodes
    return nets


def short(name):
    return name.rsplit("/", 1)[-1]


def main():
    if len(sys.argv) != 3:
        print(__doc__); sys.exit(2)
    nets = load_netlist(sys.argv[1])
    expected = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    by_short = {}
    for n, nodes in nets.items():
        by_short.setdefault(short(n), set()).update(nodes)

    failures = 0
    print(f"Netlist: {len(nets)} nets | expected: {len(expected)} nets\n")
    for net, want in expected.items():
        have = by_short.get(net)
        if have is None:
            print(f"[MISSING NET] {net}")
            failures += 1
            continue
        missing = [w for w in want if w not in have]
        refs_have = {h.split(":")[0] for h in have}
        refs_want = {w.split(":")[0] for w in want}
        unexpected = sorted(r for r in refs_have - refs_want)
        if missing:
            failures += 1
            print(f"[FAIL] {net}: missing {', '.join(missing)}")
        else:
            print(f"[ OK ] {net}")
        if unexpected:
            print(f"       note: also connected to {', '.join(unexpected)}")

    unlisted = sorted(n for n in by_short if n not in expected and not n.startswith("Net-("))
    if unlisted:
        print("\nNamed nets not in expected_nets.json: " + ", ".join(unlisted))
    unnamed = sorted(n for n in nets if short(n).startswith("Net-("))
    if unnamed:
        print(f"Auto-named nets (wires without labels): {len(unnamed)}")
    print(f"\n{'PASS' if not failures else f'{failures} net(s) with problems'}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
