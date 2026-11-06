"""Helpers for rebuilding Chapter 5 of the 1105-v11 thesis (clean edits, no tracked changes)."""
import copy
import re
import sys

from lxml import etree

sys.path.insert(0, "/home/user/transparent-levee-thesis/tools/1103")
sys.path.insert(0, "/home/user/transparent-WaterGov/paper/chinese/tools/revise_1028")
from docxedit import Editor, make_runs, strip_ids  # noqa: E402

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = "{%s}" % W_NS
M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
TEXT_CHILDREN = {"rPr", "t", "lastRenderedPageBreak"}


class Ed(Editor):
    """Editor that skips runs carrying non-text content (comment references, drawings, breaks)."""

    @staticmethod
    def text_runs(p):
        out = []
        for c in p:
            if etree.QName(c).localname == "r" and all(etree.QName(x).localname in TEXT_CHILDREN for x in c):
                if c.find(W + "t") is not None:
                    out.append(c)
        return out

    @staticmethod
    def run_text(r):
        return "".join(t.text or "" for t in r.findall(W + "t"))

    def _split(self, r, k):
        for x in r.findall(W + "lastRenderedPageBreak"):
            r.remove(x)
        return Editor._split(self, r, k)


ed = Ed(track=False)


def ptext(p):
    return ed.para_text(p)


def rep(p, old, new, count=1):
    text = ptext(p)
    n = text.count(old)
    if n != count:
        raise ValueError(f"rep: expected {count} x {old[:40]!r}, found {n} in {text[:80]!r}")
    for _ in range(count):
        s = ptext(p).index(old)
        ed.replace_range(p, s, s + len(old), new)


def rep_all(el, old, new):
    """Replace every occurrence in every paragraph of el (paragraph, table or cell)."""
    ps = [el] if el.tag == W + "p" else list(el.iter(W + "p"))
    n = 0
    for p in ps:
        pos = 0
        while True:
            t = ptext(p)
            s = t.find(old, pos)
            if s < 0:
                break
            ed.replace_range(p, s, s + len(old), new)
            pos = s + len(re.sub(r"\{(?:sup|sub|i|b):|\}", "", new))
            n += 1
    return n


def rw(p, markup):
    ed.rewrite(p, markup)


def cell_paras(tbl):
    return list(tbl.iter(W + "p"))


def cell_rep(tbl, old, new):
    hits = [p for p in tbl.iter(W + "p") if old in ptext(p)]
    if len(hits) != 1:
        raise ValueError(f"cell_rep: {len(hits)} cells contain {old[:40]!r}")
    rep(hits[0], old, new)


def cell_rw(tbl, needle, markup):
    hits = [p for p in tbl.iter(W + "p") if needle in ptext(p)]
    if len(hits) != 1:
        raise ValueError(f"cell_rw: {len(hits)} cells contain {needle[:40]!r}")
    rw(hits[0], markup)


def drop_bookmarks(el):
    for tag in ("bookmarkStart", "bookmarkEnd"):
        for b in list(el.iter(W + tag)):
            b.getparent().remove(b)
    return el


def clone_para(tmpl, markup):
    p = strip_ids(copy.deepcopy(tmpl))
    drop_bookmarks(p)
    for tag in ("commentRangeStart", "commentRangeEnd"):
        for b in list(p.iter(W + tag)):
            b.getparent().remove(b)
    for r in list(p.findall(W + "r")):
        if r.find(W + "commentReference") is not None:
            p.remove(r)
    for r in p.findall(W + "r"):
        for x in r.findall(W + "lastRenderedPageBreak"):
            r.remove(x)
    rw(p, markup)
    return p


def new_table(tmpl, widths, header, rows, body_align=None):
    """Three-line table built from template tmpl (header row, body rows, last row)."""
    assert abs(sum(widths) - 9406) < 3, sum(widths)
    tbl = etree.Element(W + "tbl")
    tbl.append(copy.deepcopy(tmpl.find(W + "tblPr")))
    grid = etree.SubElement(tbl, W + "tblGrid")
    for w in widths:
        etree.SubElement(grid, W + "gridCol").set(W + "w", str(w))
    trs = tmpl.findall(W + "tr")
    allrows = [header] + rows
    ncol = len(widths)
    body_align = body_align or (["center"] + ["left"] * (ncol - 1))
    for k, vals in enumerate(allrows):
        assert len(vals) == ncol, vals
        src = trs[0] if k == 0 else (trs[-1] if k == len(allrows) - 1 else trs[1])
        tr = strip_ids(copy.deepcopy(src))
        tcs = tr.findall(W + "tc")
        while len(tcs) < ncol:
            tr.append(copy.deepcopy(tcs[-1]))
            tcs = tr.findall(W + "tc")
        for tc in tcs[ncol:]:
            tr.remove(tc)
        for j, (tc, val) in enumerate(zip(tr.findall(W + "tc"), vals)):
            tcpr = tc.find(W + "tcPr")
            tcpr.find(W + "tcW").set(W + "w", str(widths[j]))
            for gs in tcpr.findall(W + "gridSpan") + tcpr.findall(W + "vMerge"):
                tcpr.remove(gs)
            ps = tc.findall(W + "p")
            for extra in ps[1:]:
                tc.remove(extra)
            p = ps[0]
            r0 = p.find(".//" + W + "r")
            tmpl_rpr = copy.deepcopy(r0.find(W + "rPr")) if r0 is not None and r0.find(W + "rPr") is not None else None
            if tmpl_rpr is not None:
                for x in tmpl_rpr.findall(W + "b") + tmpl_rpr.findall(W + "bCs"):
                    tmpl_rpr.remove(x)
            for c in list(p):
                if etree.QName(c).localname != "pPr":
                    p.remove(c)
            ppr = p.find(W + "pPr")
            if ppr is None:
                ppr = etree.Element(W + "pPr")
                p.insert(0, ppr)
            jc = ppr.find(W + "jc")
            if jc is None:
                jc = etree.SubElement(ppr, W + "jc")
            jc.set(W + "val", "center" if k == 0 else body_align[j])
            for r in make_runs(tmpl_rpr, val):
                p.append(r)
        tbl.append(tr)
    return tbl


def anchor_comment(cid, start_el, start_sub, refs, end_el=None, end_sub=None):
    """Wrap text start_sub (in start_el) .. end_sub (in end_el) in comment cid; refs = (cRS, cRE, ref_run)."""
    crs, cre, rr = (copy.deepcopy(x) for x in refs)
    end_el = end_el if end_el is not None else start_el
    end_sub = end_sub if end_sub is not None else start_sub
    t = ptext(start_el)
    s = t.index(start_sub)
    runs = ed._isolate(start_el, s, s + len(start_sub))
    runs[0].addprevious(crs)
    t2 = ptext(end_el)
    e0 = t2.index(end_sub)
    runs2 = ed._isolate(end_el, e0, e0 + len(end_sub))
    runs2[-1].addnext(cre)
    cre.addnext(rr)


def remove_comment_marks(elements, cid):
    for el in elements:
        for tag in ("commentRangeStart", "commentRangeEnd"):
            for x in list(el.iter(W + tag)):
                if x.get(W + "id") == cid:
                    x.getparent().remove(x)
        for x in list(el.iter(W + "commentReference")):
            if x.get(W + "id") == cid:
                r = x.getparent()
                r.getparent().remove(r)


def collect_comment(elements, cid):
    crs = cre = rr = None
    for el in elements:
        for x in el.iter(W + "commentRangeStart"):
            if x.get(W + "id") == cid:
                crs = copy.deepcopy(x)
        for x in el.iter(W + "commentRangeEnd"):
            if x.get(W + "id") == cid:
                cre = copy.deepcopy(x)
        for x in el.iter(W + "commentReference"):
            if x.get(W + "id") == cid:
                rr = copy.deepcopy(x.getparent())
    assert crs is not None and cre is not None and rr is not None, cid
    return crs, cre, rr


def remap_numbers(p, fig, tab, eq):
    """Map unmarked old numbers to new ones; marked numbers (5.#n) are left for strip_markers."""
    pats = [(re.compile(r"(?<=图)5\.(\d+)"), fig), (re.compile(r"(?<=表)5\.(\d+)"), tab),
            (re.compile(r"(?<=Fig\. )5\.(\d+)"), fig), (re.compile(r"(?<=Table )5\.(\d+)"), tab),
            (re.compile(r"(?<=（)5\.(\d+)(?=）)"), eq)]
    text = ptext(p)
    hits = []
    for pat, mp in pats:
        for m in pat.finditer(text):
            n = int(m.group(1))
            if n not in mp:
                raise ValueError(f"unmapped number 5.{n} in {text[:60]!r}")
            hits.append((m.start(), m.end(), f"5.{mp[n]}"))
    for s, e, new in sorted(hits, reverse=True):
        if text[s:e] != new:
            ed.replace_range(p, s, e, new)


def strip_markers(p):
    text = ptext(p)
    for m in sorted(re.finditer(r"5\.#", text), key=lambda m: -m.start()):
        ed.replace_range(p, m.start(), m.end(), "5.")
