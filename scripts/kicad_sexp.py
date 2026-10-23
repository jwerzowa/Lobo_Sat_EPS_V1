"""Round-trip KiCad s-expression reader/writer (no dependencies).

Unlike sexpr.py (read-only, drops quoting), this keeps quoted strings as `Q` so files
can be edited and written back. Nodes are Python lists; atoms are `str` (bare) or `Q`
(quoted).
"""
import uuid as _uuid


class Q(str):
    """A quoted string atom."""


def parse(text):
    toks = _tokenize(text)
    node, _ = _read(toks, 0)
    return node


def _tokenize(text):
    toks, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
        elif c in "()":
            toks.append(c)
            i += 1
        elif c == '"':
            j, buf = i + 1, []
            while text[j] != '"':
                if text[j] == "\\":
                    nxt = text[j + 1]
                    buf.append({"n": "\n", "t": "\t", "\\": "\\", '"': '"'}.get(nxt, "\\" + nxt))
                    j += 2
                else:
                    buf.append(text[j])
                    j += 1
            toks.append(Q("".join(buf)))
            i = j + 1
        else:
            j = i
            while j < n and text[j] not in ' \t\r\n()"':
                j += 1
            toks.append(text[i:j])
            i = j
    return toks


def _read(toks, pos):
    t = toks[pos]
    if t == "(" and not isinstance(t, Q):
        lst, pos = [], pos + 1
        while not (toks[pos] == ")" and not isinstance(toks[pos], Q)):
            node, pos = _read(toks, pos)
            lst.append(node)
        return lst, pos + 1
    return t, pos + 1


def _atom(a):
    if isinstance(a, Q):
        return '"' + a.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
    if isinstance(a, float):
        return fmt(a)
    return str(a)


def dump(node, indent=0):
    """Serialize like KiCad: one child list per line, atoms inline."""
    if not isinstance(node, list):
        return _atom(node)
    pad = "\t" * indent
    atoms = [a for a in node if not isinstance(a, list)]
    lists = [a for a in node if isinstance(a, list)]
    head = "(" + " ".join(_atom(a) for a in atoms)
    if not lists:
        return pad + head + ")"
    out = [pad + head]
    for c in lists:
        out.append(dump(c, indent + 1))
    out.append(pad + ")")
    return "\n".join(out)


def fmt(v):
    """Format a coordinate without float noise (KiCad style)."""
    s = f"{round(v, 4):.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def children(node, name):
    return [c for c in node if isinstance(c, list) and c and c[0] == name]


def child(node, name):
    found = children(node, name)
    return found[0] if found else None


def walk(node, name):
    if isinstance(node, list):
        if node and node[0] == name:
            yield node
        for c in node[1:]:
            yield from walk(c, name)


def prop(sym, key):
    for p in children(sym, "property"):
        if p[1] == key:
            return p
    return None


def set_prop(sym, key, value, hide=True):
    """Set (or add) a property on a library symbol."""
    p = prop(sym, key)
    if p is not None:
        p[2] = Q(value)
        return p
    p = [
        "property", Q(key), Q(value), ["at", "0", "0", "0"],
        ["effects", ["font", ["size", "1.27", "1.27"]]] + ([["hide", "yes"]] if hide else []),
    ]
    # insert after the last existing property so field order stays sensible
    idx = max((i for i, c in enumerate(sym) if isinstance(c, list) and c and c[0] == "property"), default=1)
    sym.insert(idx + 1, p)
    return p


def new_uuid(seed):
    """Deterministic UUID so re-running a generator gives identical files."""
    return str(_uuid.uuid5(_uuid.NAMESPACE_URL, "lobosat-eps/" + seed))
