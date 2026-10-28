"""Small run-level editing helpers for word/document.xml (lxml), with optional tracked changes.

Text markup in new strings: {sup:..} superscript, {sub:..} subscript, {i:..} italic, {b:..} bold,
nested once at most (e.g. {b:0.94}).  Plain text outside braces uses the template run format.
"""
import copy
import re

from lxml import etree

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = "{%s}" % W_NS
W14 = "{http://schemas.microsoft.com/office/word/2010/wordml}"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
AUTHOR, DATE = "Claude", "2026-10-28T00:00:00Z"

RPR_ORDER = ["rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps", "strike", "dstrike", "outline",
             "shadow", "emboss", "imprint", "noProof", "snapToGrid", "vanish", "webHidden", "color", "spacing",
             "w", "kern", "position", "sz", "szCs", "highlight", "u", "effect", "bdr", "shd", "fitText",
             "vertAlign", "rtl", "cs", "em", "lang", "eastAsianLayout", "specVanish", "oMath"]
TOKEN = re.compile(r"\{(sup|sub|i|b):((?:[^{}]|\{[^{}]*\})*)\}")


def parse_markup(s):
    """'a{sup:[1]}b' -> [('a', set()), ('[1]', {'sup'}), ('b', set())]; one nesting level."""
    out, pos = [], 0
    for m in TOKEN.finditer(s):
        if m.start() > pos:
            out.append((s[pos:m.start()], frozenset()))
        for text, styles in parse_markup(m.group(2)):
            out.append((text, styles | {m.group(1)}))
        pos = m.end()
    if pos < len(s):
        out.append((s[pos:], frozenset()))
    return [x for x in out if x[0]]


def _set_child(rpr, name, val=None):
    for old in rpr.findall(W + name):
        rpr.remove(old)
    el = etree.Element(W + name)
    if val is not None:
        el.set(W + "val", val)
    idx = RPR_ORDER.index(name)
    for i, c in enumerate(rpr):
        cname = etree.QName(c).localname
        if cname in RPR_ORDER and RPR_ORDER.index(cname) > idx:
            c.addprevious(el)
            return
    rpr.append(el)


def styled_rpr(template, styles):
    rpr = copy.deepcopy(template) if template is not None else etree.Element(W + "rPr")
    for name in ("highlight", "vertAlign", "i", "iCs", "b", "bCs"):
        for old in rpr.findall(W + name):
            rpr.remove(old)
    if template is not None and template.find(W + "b") is not None and "nob" not in styles:
        _set_child(rpr, "b")
    if "b" in styles:
        _set_child(rpr, "b")
    if "i" in styles:
        _set_child(rpr, "i")
    if "sup" in styles:
        _set_child(rpr, "vertAlign", "superscript")
    if "sub" in styles:
        _set_child(rpr, "vertAlign", "subscript")
    return rpr


def make_runs(template_rpr, markup):
    runs = []
    for text, styles in parse_markup(markup):
        r = etree.Element(W + "r")
        r.append(styled_rpr(template_rpr, styles))
        for k, piece in enumerate(text.split("\n")):  # "\n" becomes a manual line break (table cells only)
            if k:
                etree.SubElement(r, W + "br")
            if piece:
                t = etree.SubElement(r, W + "t")
                t.text = piece
                if piece != piece.strip():
                    t.set(XML_SPACE, "preserve")
        runs.append(r)
    return runs


def strip_ids(el):
    for e in el.iter():
        for a in (W14 + "paraId", W14 + "textId"):
            if a in e.attrib:
                del e.attrib[a]
    return el


class Editor:
    def __init__(self, track):
        self.track = track
        self.nid = 900000

    def _rev(self, tag):
        self.nid += 1
        el = etree.Element(W + tag)
        el.set(W + "id", str(self.nid))
        el.set(W + "author", AUTHOR)
        el.set(W + "date", DATE)
        return el

    # ------------------------------------------------------------------ runs and offsets
    @staticmethod
    def text_runs(p):
        out = []
        for c in p:
            tag = etree.QName(c).localname
            if tag == "r":
                out.append(c)
            elif tag == "ins":
                out.extend(c.findall(W + "r"))
        return out

    @staticmethod
    def run_text(r):
        for c in r:
            tag = etree.QName(c).localname
            if tag not in ("rPr", "t"):
                raise ValueError(f"run with non-text content <{tag}> cannot be edited")
        return "".join(t.text or "" for t in r.findall(W + "t"))

    def para_text(self, p):
        return "".join(self.run_text(r) for r in self.text_runs(p))

    def _split(self, r, k):
        text = self.run_text(r)
        ts = r.findall(W + "t")
        for t in ts[1:]:
            r.remove(t)
        ts[0].text = text[:k]
        ts[0].set(XML_SPACE, "preserve")
        r2 = copy.deepcopy(r)
        r2.find(W + "t").text = text[k:]
        r.addnext(r2)
        return r2

    def _isolate(self, p, start, end):
        pos = 0
        for r in list(self.text_runs(p)):
            n = len(self.run_text(r))
            if pos < start < pos + n:
                self._split(r, start - pos)
                break
            pos += n
        pos = 0
        for r in list(self.text_runs(p)):
            n = len(self.run_text(r))
            if pos < end < pos + n:
                self._split(r, end - pos)
                break
            pos += n
        inside, pos = [], 0
        for r in self.text_runs(p):
            n = len(self.run_text(r))
            if pos >= start and pos + n <= end and n:
                inside.append(r)
            pos += n
        return inside

    @staticmethod
    def _template(runs):
        """Format of the first plain run: no superscript and, if possible, none of the author's highlights."""
        plain = [r for r in runs if r.find(W + "rPr") is None or r.find(W + "rPr/" + W + "vertAlign") is None]
        for r in plain:
            rpr = r.find(W + "rPr")
            if rpr is None or rpr.find(W + "highlight") is None:
                return rpr
        return (plain or runs)[0].find(W + "rPr")

    # ------------------------------------------------------------------ edits
    def replace(self, p, old, new, template_rpr=None):
        text = self.para_text(p)
        n = text.count(old)
        if n != 1:
            raise ValueError(f"expected one occurrence of {old[:30]!r}, found {n} in {text[:40]!r}")
        start = text.index(old)
        self.replace_range(p, start, start + len(old), new, template_rpr)

    def rewrite(self, p, new):
        self.replace_range(p, 0, len(self.para_text(p)), new)

    def insert_after(self, p, anchor, new):
        text = self.para_text(p)
        if text.count(anchor) != 1:
            raise ValueError(f"anchor {anchor[:30]!r} not unique")
        pos = text.index(anchor) + len(anchor)
        self._isolate(p, pos, pos)
        acc, prev = 0, None
        for r in self.text_runs(p):
            acc += len(self.run_text(r))
            if acc == pos:
                prev = r
                break
        new_runs = make_runs(self._template([prev]), new)
        self._place_after(prev, new_runs)

    def _place_after(self, prev, new_runs):
        if self.track:
            ins = self._rev("ins")
            for r in new_runs:
                ins.append(r)
            anchor = prev.getparent() if etree.QName(prev.getparent()).localname == "ins" else prev
            anchor.addnext(ins)
        else:
            for r in reversed(new_runs):
                prev.addnext(r)

    def replace_range(self, p, start, end, new, template_rpr=None):
        runs = self._isolate(p, start, end)
        if not runs:
            raise ValueError("empty range")
        for r in runs:
            if r.getparent() is not p:
                raise ValueError("refusing to edit inside an earlier insertion")
        tmpl = template_rpr if template_rpr is not None else self._template(runs)
        new_runs = make_runs(tmpl, new) if new else []
        if self.track:
            d = self._rev("del")
            runs[0].addprevious(d)
            for r in runs:
                d.append(r)
                for t in r.findall(W + "t"):
                    t.tag = W + "delText"
            if new_runs:
                ins = self._rev("ins")
                for r in new_runs:
                    ins.append(r)
                d.addnext(ins)
        else:
            for r in new_runs:
                runs[0].addprevious(r)
            for r in runs:
                p.remove(r)

    def new_paragraph_after(self, anchor_el, ppr_template, rpr_template, markup):
        p = etree.Element(W + "p")
        ppr = copy.deepcopy(ppr_template) if ppr_template is not None else etree.Element(W + "pPr")
        p.append(ppr)
        if self.track:
            prpr = ppr.find(W + "rPr")
            if prpr is None:
                prpr = etree.SubElement(ppr, W + "rPr")
            prpr.insert(0, self._rev("ins"))
        runs = make_runs(rpr_template, markup)
        if self.track:
            ins = self._rev("ins")
            for r in runs:
                ins.append(r)
            p.append(ins)
        else:
            for r in runs:
                p.append(r)
        anchor_el.addnext(p)
        return p
