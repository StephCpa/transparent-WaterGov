"""Tiny LaTeX-like notation -> Office Math (OMML), for the display equations of the thesis.

Supported: x_{..}, x^{..}, \\frac{a}{b}, \\sum_{..}^{..}{body}, \\maxl{lim}{body} (max with a limit below),
\\dl{(}{)}{body} (stretchy delimiters), \\cases{row \\\\ row} (left brace with stacked rows; '&' is dropped),
\\text{..} (upright), \\quad, '\\ ' (thin space), \\{ and \\} (literal braces).  '-' is written as U+2212.
"""
from lxml import etree

M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
M = "{%s}" % M_NS


def _el(tag, parent=None, **attrs):
    e = etree.SubElement(parent, M + tag) if parent is not None else etree.Element(M + tag)
    for k, v in attrs.items():
        e.set(M + k, v)
    return e


def _run(text, upright=False, normal=False):
    """normal=True writes ordinary (non-math) text: words such as max, gt or in, and lone signs in scripts."""
    r = _el("r")
    rpr = _el("rPr", r)
    if normal:
        _el("nor", rpr)
    elif upright:
        _el("sty", rpr, val="p")
    t = _el("t", r)
    t.text = text.replace("-", "−")
    if text != text.strip():
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    return r


class _P:
    def __init__(self, s):
        self.s, self.i = s, 0

    def peek(self):
        return self.s[self.i] if self.i < len(self.s) else ""

    def group(self):
        """{...} -> list of elements; a single character otherwise."""
        if self.peek() == "{":
            self.i += 1
            out = self.expr("}")
            self.i += 1
            return out
        return self.atom()

    def raw_group(self):
        assert self.peek() == "{", self.s[self.i:]
        depth, j = 0, self.i
        while True:
            c = self.s[j]
            if c == "\\":          # an escaped character never opens or closes a group
                j += 2
                continue
            depth += c == "{"
            depth -= c == "}"
            j += 1
            if depth == 0:
                break
        txt = self.s[self.i + 1:j - 1]
        self.i = j
        return txt

    def command(self):
        j = self.i + 1
        if j < len(self.s) and not self.s[j].isalpha():
            self.i = j + 1
            ch = self.s[j]
            if ch == " ":
                return [_run(" ", True)]
            if ch in "{}":
                return [_run(ch, True)]
            if ch == "\\":
                return "ROWBREAK"
            raise ValueError(ch)
        while j < len(self.s) and self.s[j].isalpha():
            j += 1
        name = self.s[self.i + 1:j]
        self.i = j
        if name == "text":
            return [_run(self.raw_group(), True, normal=True)]
        if name == "quad":
            return [_run(" ", True)]
        if name == "frac":
            f = _el("f")
            _el("fPr", f)
            num = _el("num", f)
            for e in self.group():
                num.append(e)
            den = _el("den", f)
            for e in self.group():
                den.append(e)
            return [f]
        if name in ("sum", "prod"):
            n = _el("nary")
            pr = _el("naryPr", n)
            _el("chr", pr, val="∑" if name == "sum" else "∏")
            _el("limLoc", pr, val="undOvr")
            sub, sup = [], []
            while self.peek() in "_^":
                c = self.peek()
                self.i += 1
                (sub if c == "_" else sup).extend(self.group())
            if not sub:
                _el("subHide", pr, val="1")
            if not sup:
                _el("supHide", pr, val="1")
            se = _el("sub", n)
            for e in sub:
                se.append(e)
            sp = _el("sup", n)
            for e in sup:
                sp.append(e)
            body = _el("e", n)
            for e in self.group():
                body.append(e)
            return [n]
        if name == "maxl":
            fn = _el("func")
            _el("funcPr", fn)
            fname = _el("fName", fn)
            ll = _el("limLow", fname)
            _el("limLowPr", ll)
            e = _el("e", ll)
            e.append(_run("max", True, normal=True))
            lim = _el("lim", ll)
            for x in self.group():
                lim.append(x)
            body = _el("e", fn)
            for x in self.group():
                body.append(x)
            return [fn]
        if name == "dl":
            beg, end = (g.replace("\\", "") for g in (self.raw_group(), self.raw_group()))
            d = _el("d")
            pr = _el("dPr", d)
            _el("begChr", pr, val=beg)
            _el("endChr", pr, val=end)
            e = _el("e", d)
            for x in self.group():
                e.append(x)
            return [d]
        if name == "cases":
            d = _el("d")
            pr = _el("dPr", d)
            _el("begChr", pr, val="{")
            _el("endChr", pr, val="")
            e = _el("e", d)
            arr = _el("eqArr", e)
            _el("eqArrPr", arr)
            assert self.peek() == "{"
            self.i += 1
            row = _el("e", arr)
            while self.peek() != "}":
                item = self.item()
                if item == "ROWBREAK":
                    row = _el("e", arr)
                    continue
                for x in item:
                    row.append(x)
            self.i += 1
            return [d]
        raise ValueError("unknown command \\" + name)

    def atom(self):
        c = self.peek()
        if c == "\\":
            return self.command()
        if c == "{":
            return self.group()
        if c == "&":
            self.i += 1
            return [_run(" ", True)]
        # plain run: letters/digits/symbols up to a special character, one char at a time for scripts
        self.i += 1
        return [_run(c, upright=c.isdigit() or c in ".,;:()[]|=+-<>≤≥≠∈∩∪⊕⊙·≼→∅′ ΔΠ")]

    def item(self):
        base = self.atom()
        if base == "ROWBREAK":
            return base
        sub = sup = None
        while self.peek() in ("_", "^") and self.peek():
            c = self.peek()
            self.i += 1
            g = self.group()
            if len(g) == 1 and g[0].tag == M + "r" and g[0].find(M + "t").text in ("+", "\u2212"):
                g = [_run(g[0].find(M + "t").text, normal=True)]
            if c == "_":
                sub = g
            else:
                sup = g
        if sub is None and sup is None:
            return base
        tag = "sSubSup" if sub is not None and sup is not None else ("sSub" if sub is not None else "sSup")
        s = _el(tag)
        _el(tag + "Pr", s)
        e = _el("e", s)
        # scripts attach to the last element of the base only
        for x in base[:-1]:
            pass
        e.append(base[-1])
        if sub is not None:
            se = _el("sub", s)
            for x in sub:
                se.append(x)
        if sup is not None:
            sp = _el("sup", s)
            for x in sup:
                sp.append(x)
        return base[:-1] + [s]

    def expr(self, stop=None):
        out = []
        while self.i < len(self.s) and self.peek() != (stop or "\0"):
            it = self.item()
            if it == "ROWBREAK":
                raise ValueError("row break outside cases")
            out.extend(it)
        return out


def _merge(elems):
    """Join neighbouring plain runs with the same style, so letters read as words in the XML."""
    out = []
    for e in elems:
        kind = lambda x: tuple(etree.QName(c).localname for c in x.find(M + "rPr"))  # noqa: E731
        if (out and e.tag == M + "r" and out[-1].tag == M + "r" and kind(e) == kind(out[-1]) == ("sty",)):
            out[-1].find(M + "t").text += e.find(M + "t").text
            out[-1].find(M + "t").set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        else:
            out.append(e)
    return out


def omath_para(latex):
    p = _P(latex)
    elems = _merge(p.expr())
    para = _el("oMathPara")
    om = _el("oMath", para)
    for e in elems:
        om.append(e)
    return para
