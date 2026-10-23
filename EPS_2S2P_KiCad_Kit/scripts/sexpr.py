"""Minimal KiCad s-expression reader (no dependencies).

parse(text) -> nested Python lists. Atoms are str. Quoted strings keep their content
(unescaped), unquoted atoms are returned as-is.
"""

def parse(text):
    tokens = _tokenize(text)
    pos = 0
    out = []
    while pos < len(tokens):
        node, pos = _read(tokens, pos)
        out.append(node)
    return out[0] if len(out) == 1 else out


def _tokenize(text):
    toks, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
        elif c in "()":
            toks.append(c); i += 1
        elif c == '"':
            j, buf = i + 1, []
            while j < n and text[j] != '"':
                if text[j] == "\\" and j + 1 < n:
                    buf.append(text[j + 1]); j += 2
                else:
                    buf.append(text[j]); j += 1
            toks.append(("str", "".join(buf))); i = j + 1
        else:
            j = i
            while j < n and text[j] not in ' \t\r\n()"':
                j += 1
            toks.append(text[i:j]); i = j
    return toks


def _read(toks, pos):
    t = toks[pos]
    if t == "(":
        lst, pos = [], pos + 1
        while toks[pos] != ")":
            node, pos = _read(toks, pos)
            lst.append(node)
        return lst, pos + 1
    if isinstance(t, tuple):
        return t[1], pos + 1
    return t, pos + 1


def head(node):
    return node[0] if isinstance(node, list) and node else None


def children(node, name):
    return [c for c in node[1:] if isinstance(c, list) and c and c[0] == name] if isinstance(node, list) else []


def child(node, name):
    found = children(node, name)
    return found[0] if found else None


def walk(node, name):
    """Yield every sub-list (at any depth) whose head is `name`."""
    if isinstance(node, list):
        if node and node[0] == name:
            yield node
        for c in node[1:]:
            yield from walk(c, name)
