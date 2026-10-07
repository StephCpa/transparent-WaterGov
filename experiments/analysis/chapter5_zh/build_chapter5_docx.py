"""Build the Chapter 5 Word file from chapter5_source.txt (2026-10-07).

The package parts that carry formatting (styles, settings, theme, font table,
numbering) are copied unchanged from paper/chinese/chapters/chapter2_theory_framework.docx,
and every paragraph and run repeats the direct formatting used in Chapters 1 and 2:
Letter page with 2.5 cm margins; Times New Roman + SimSun body text at 12 pt with
1.5 line spacing and a two-character first-line indent; SimHei bold headings
(14 pt chapter title, 12 pt sections); 10.5 pt captions, tables and references;
three-line tables; superscript [n] citations; equations numbered (5-n).

Source markup (one block per line):
  #1/#2/#3 heading        EQ <math> || (5-n)        FIG <png> || <width in> || <caption>
  TBL <caption> || <col widths in twips> || <alignments L/C>, rows "| a | b", TBLEND
  TNOTE <table note>      REFHEAD <heading>          any other line: body paragraph
Inline: $...$ math (_{} subscript, ^{} superscript, \\up{} upright), **bold**,
[@key] citations ([@1:n] keeps the number n of the Chapter 1 reference list;
other keys are numbered from FIRST_NEW_REF in order of first citation).

Usage: python3 build_chapter5_docx.py [output.docx]
"""

from __future__ import annotations

import re
import struct
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CHAPTERS = REPO / "paper" / "chinese" / "chapters"
TEMPLATE = CHAPTERS / "chapter2_theory_framework.docx"
FIGDIR = CHAPTERS / "figures_ch5"
SOURCE = HERE / "chapter5_source.txt"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else CHAPTERS / "chapter5_transparent_evaluation.docx"

FIRST_NEW_REF = 192          # Chapter 2 ends at [191]; renumber when the thesis is compiled
TEXT_W = 9406                # text width in twips (12240 - 2 x 1417)
EMU_PER_IN = 914400

# New references of this chapter (GB/T 7714 style as in the Chapter 1 list).
REFS = {
    "Foster": "FOSTER M, FELL R, SPANNAGLE M. The statistics of embankment dam failures and accidents[J]. Canadian Geotechnical Journal, 2000, 37(5): 1000-1024.",
    "vanBeek": "VAN BEEK V M, VAN ESSEN H M, VANDENBOER K, et al. Developments in modelling of backward erosion piping[J]. Géotechnique, 2015, 65(9): 740-754.",
    "CRITIC": "DIAKOULAKI D, MAVROTAS G, PAPAYANNAKIS L. Determining objective weights in multiple criteria problems: the CRITIC method[J]. Computers & Operations Research, 1995, 22(7): 763-770.",
    "PROV": "MOREAU L, MISSIER P. PROV-DM: the PROV data model[EB/OL]. W3C Recommendation, 2013-04-30[2026-10-07]. https://www.w3.org/TR/2013/REC-prov-dm-20130430/.",
    "Clopper": "CLOPPER C J, PEARSON E S. The use of confidence or fiducial limits illustrated in the case of the binomial[J]. Biometrika, 1934, 26(4): 404-413.",
    "Terzaghi": "TERZAGHI K. Theoretical soil mechanics[M]. New York: John Wiley & Sons, 1943.",
    "Hastie": "HASTIE T, TIBSHIRANI R, FRIEDMAN J. The elements of statistical learning[M]. 2nd ed. New York: Springer, 2009.",
    "Breiman": "BREIMAN L. Random forests[J]. Machine Learning, 2001, 45(1): 5-32.",
    "Kaufman": "KAUFMAN S, ROSSET S, PERLICH C, et al. Leakage in data mining: formulation, detection, and avoidance[J]. ACM Transactions on Knowledge Discovery from Data, 2012, 6(4): 15.",
    "Elkan": "ELKAN C. The foundations of cost-sensitive learning[C]//Proceedings of the 17th International Joint Conference on Artificial Intelligence. Seattle: Morgan Kaufmann, 2001: 973-978.",
    "Karpatne": "KARPATNE A, ATLURI G, FAGHMOUS J H, et al. Theory-guided data science: a new paradigm for scientific discovery from data[J]. IEEE Transactions on Knowledge and Data Engineering, 2017, 29(10): 2318-2331.",
    "Chow": "CHOW C K. On optimum recognition error and reject tradeoff[J]. IEEE Transactions on Information Theory, 1970, 16(1): 41-46.",
    "Geifman": "GEIFMAN Y, EL-YANIV R. Selective classification for deep neural networks[C]//Advances in Neural Information Processing Systems 30. Long Beach: Curran Associates, 2017: 4878-4887.",
    "FrankHall": "FRANK E, HALL M. A simple approach to ordinal classification[C]//Proceedings of the 12th European Conference on Machine Learning. Berlin: Springer, 2001: 145-156.",
    "Cortes": "CORTES C, VAPNIK V. Support-vector networks[J]. Machine Learning, 1995, 20(3): 273-297.",
    "Friedman": "FRIEDMAN J H. Greedy function approximation: a gradient boosting machine[J]. The Annals of Statistics, 2001, 29(5): 1189-1232.",
    "Wolpert": "WOLPERT D H. Stacked generalization[J]. Neural Networks, 1992, 5(2): 241-259.",
    "Zitzler2003": "ZITZLER E, THIELE L, LAUMANNS M, et al. Performance assessment of multiobjective optimizers: an analysis and review[J]. IEEE Transactions on Evolutionary Computation, 2003, 7(2): 117-132.",
    "McNemar": "McNEMAR Q. Note on the sampling error of the difference between correlated proportions or percentages[J]. Psychometrika, 1947, 12(2): 153-157.",
    "Efron": "EFRON B, TIBSHIRANI R J. An introduction to the bootstrap[M]. New York: Chapman & Hall, 1993.",
}

# ------------------------------------------------------------------ run formatting
def rpr(size=24, bold=False, italic=False, vert=None, east="SimSun", ascii_font="Times New Roman"):
    f = f'<w:rFonts w:ascii="{ascii_font}" w:eastAsia="{east}" w:hAnsi="{ascii_font}"/>'
    return ("<w:rPr>" + f + ("<w:b/>" if bold else "") + ("<w:i/>" if italic else "")
            + f'<w:sz w:val="{size}"/>' + (f'<w:vertAlign w:val="{vert}"/>' if vert else "") + "</w:rPr>")


def run(text, **kw):
    if text == "":
        return ""
    parts = text.split("\t")
    body = '<w:tab/>'.join(f'<w:t xml:space="preserve">{escape(p)}</w:t>' for p in parts)
    return f"<w:r>{rpr(**kw)}{body}</w:r>"


# ------------------------------------------------------------------ citations
class Citations:
    def __init__(self):
        self.order: list[str] = []

    def number(self, key: str) -> int:
        if key.startswith("1:"):
            return int(key[2:])
        if key not in REFS:
            raise KeyError(f"unknown reference key {key}")
        if key not in self.order:
            self.order.append(key)
        return FIRST_NEW_REF + self.order.index(key)

    def label(self, keys: str) -> str:
        nums = sorted({self.number(k.strip().lstrip("@")) for k in keys.split(",")})
        out, i = [], 0
        while i < len(nums):
            j = i
            while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
                j += 1
            out.append(f"{nums[i]}-{nums[j]}" if j - i >= 2 else ",".join(map(str, nums[i:j + 1])))
            i = j + 1
        return "[" + ",".join(out) + "]"


CITE = Citations()

# ------------------------------------------------------------------ inline math
GREEK_ITALIC = set("αβγδεζηθικλμνξοπρστυφχψωℓŷϕ")
SPECIAL_FONT = set("≼∅⇔∧∨⋯∇⊕⋃∩")      # set in Cambria Math (TNR lacks some of these glyphs)
REL = set("=≥≤<>≠⇔∈≈∧∨")
BIN = set("+−×⊕")
GREEK_CMDS = {"alpha": "α", "lambda": "λ", "tau": "τ", "rho": "ρ", "pi": "π", "phi": "φ", "delta": "δ"}
REL_CMDS = {"in": "∈", "geq": "≥", "leq": "≤"}
COMMANDS = {"max": "max", "min": "min", "quad": " ", ",": " ", " ": " ", "{": "{", "}": "}",
            "bigcup": "⋃", "cdot": "·", "%": "%"}


def _read_group(s: str, i: int) -> tuple[str, int]:
    assert s[i] == "{", s[i:]
    depth, j = 0, i
    while True:
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1


def math_runs(s: str, size=24, vert=None, upright=False, bold=False, script=False) -> str:
    """Render a small LaTeX-like math string as Word runs."""
    out: list[str] = []
    i = 0
    prev_operand = False

    def emit(text, italic, font_special=False, b=False):
        nonlocal prev_operand
        if font_special:
            out.append(run(text, size=size, vert=vert, bold=b, ascii_font="Cambria Math", east="Cambria Math"))
        else:
            out.append(run(text, size=size, italic=italic, vert=vert, bold=b))

    while i < len(s):
        ch = s[i]
        if ch == "\\":
            m = re.match(r"\\([A-Za-z]+|.)", s[i:])
            cmd = m.group(1)
            i += len(m.group(0))
            if cmd == "up":
                g, i = _read_group(s, i)
                out.append(math_runs(g, size, vert, upright=True, bold=bold, script=script))
                prev_operand = True
            elif cmd == "boldsymbol":
                g, i = _read_group(s, i)
                out.append(math_runs(g, size, vert, upright=False, bold=True, script=script))
                prev_operand = True
            elif cmd == "mathrm":
                g, i = _read_group(s, i)
                out.append(math_runs(g, size, vert, upright=True, bold=bold, script=script))
                prev_operand = True
            elif cmd == "frac":
                num, i = _read_group(s, i)
                den, i = _read_group(s, i)
                out.append(math_runs(num, size, vert, upright, bold, script))
                emit("/", False)
                out.append(math_runs("(" + den + ")", size, vert, upright, bold, script))
                prev_operand = True
            elif cmd in GREEK_CMDS:
                emit(GREEK_CMDS[cmd], italic=not upright, b=bold)
                prev_operand = True
            elif cmd in REL_CMDS:
                ch = REL_CMDS[cmd]
                emit(ch if script else f" {ch} ", False)
                prev_operand = False
            elif cmd in COMMANDS:
                text = COMMANDS[cmd]
                if cmd in ("max", "min") and prev_operand:
                    text = "\u2009" + text
                emit(text, False)
                prev_operand = cmd in ("max", "min", "}")
            else:
                raise ValueError(f"unknown math command \\{cmd}")
            continue
        if ch in "_^":
            g, i = _read_group(s, i + 1)
            out.append(math_runs(g, size, "subscript" if ch == "_" else "superscript", upright, bold, script=True))
            prev_operand = True
            continue
        if ch == " ":
            i += 1
            continue
        if ch.isascii() and ch.isalpha():
            j = i
            while j < len(s) and s[j].isascii() and s[j].isalpha():
                j += 1
            word = s[i:j]
            emit(word, italic=(not upright and len(word) == 1), b=bold)
            i = j
            prev_operand = True
            continue
        if ch in GREEK_ITALIC:
            emit(ch, italic=not upright, b=bold)
            i += 1
            prev_operand = True
            continue
        if not script and (ch in REL or (ch in BIN and prev_operand)):
            emit(f" {ch} " if prev_operand else f"{ch} ", False, font_special=ch in SPECIAL_FONT)
            i += 1
            prev_operand = False
            continue
        if ch == "," and not script:
            emit(", ", False)
            i += 1
            prev_operand = False
            continue
        emit(ch, False, font_special=ch in SPECIAL_FONT, b=bold)
        prev_operand = ch.isdigit() or ch in ")]}′"
        i += 1
    return "".join(out)


# ------------------------------------------------------------------ inline text
TOKEN = re.compile(r"(\$[^$]+\$|\*\*[^*]+\*\*|\[@[^\]]+\])")


def inline(text: str, size=24, bold=False, east="SimSun") -> str:
    out = []
    for tok in TOKEN.split(text):
        if not tok:
            continue
        if tok.startswith("$"):
            out.append(math_runs(tok[1:-1], size=size, bold=bold))
        elif tok.startswith("**"):
            out.append(run(tok[2:-2], size=size, bold=True, east="SimHei"))
        elif tok.startswith("[@"):
            out.append(run(CITE.label(tok[1:-1]), size=size, vert="superscript"))
        else:
            out.append(run(tok, size=size, bold=bold, east=east))
    return "".join(out)


# ------------------------------------------------------------------ paragraphs
def para(ppr: str, content: str) -> str:
    return f"<w:p><w:pPr>{ppr}</w:pPr>{content}</w:p>"


def chapter_title(t):
    return para('<w:keepNext/><w:spacing w:before="240" w:after="240" w:line="240" w:lineRule="auto"/><w:jc w:val="center"/>',
                run(t, size=28, bold=True, east="SimHei"))


def heading(t, level):
    sp = '<w:spacing w:before="240" w:after="120" w:line="360" w:lineRule="auto"/>' if level == 2 else \
         '<w:spacing w:before="120" w:after="120" w:line="360" w:lineRule="auto"/>'
    return para("<w:keepNext/>" + sp, inline(t, size=24, bold=True, east="SimHei"))


def body(t):
    return para('<w:spacing w:after="0" w:line="360" w:lineRule="auto"/><w:ind w:firstLine="480"/><w:jc w:val="both"/>',
                inline(t))


def equation(expr, number):
    tabs = f'<w:tabs><w:tab w:val="center" w:pos="{TEXT_W // 2}"/><w:tab w:val="right" w:pos="{TEXT_W}"/></w:tabs>'
    content = run("\t") + math_runs(expr) + run("\t" + number)
    return para(tabs + '<w:spacing w:before="60" w:after="60" w:line="360" w:lineRule="auto"/>', content)


class Media:
    def __init__(self):
        self.items: list[tuple[str, Path]] = []

    def add(self, path: Path) -> str:
        rid = f"rId{100 + len(self.items)}"
        self.items.append((rid, path))
        return rid


MEDIA = Media()


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as f:
        head = f.read(24)
    return struct.unpack(">II", head[16:24])


def figure(fname, width_in, caption, idx):
    path = FIGDIR / fname
    w_px, h_px = png_size(path)
    cx = int(float(width_in) * EMU_PER_IN)
    cy = int(cx * h_px / w_px)
    rid = MEDIA.add(path)
    drawing = (
        f'<w:r><w:rPr><w:noProof/><w:lang w:eastAsia="zh-CN"/></w:rPr><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
        f'<wp:extent cx="{cx}" cy="{cy}"/><wp:effectExtent l="0" t="0" r="0" b="0"/>'
        f'<wp:docPr id="{idx}" name="图片 {idx}" descr="{escape(caption)}"/>'
        '<wp:cNvGraphicFramePr><a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/></wp:cNvGraphicFramePr>'
        '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        f'<pic:nvPicPr><pic:cNvPr id="{idx}" name="{escape(fname)}"/><pic:cNvPicPr/></pic:nvPicPr>'
        f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
        '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r>')
    img = para('<w:keepNext/><w:spacing w:before="120" w:after="60"/><w:jc w:val="center"/>', drawing)
    cap = para('<w:spacing w:after="120"/><w:jc w:val="center"/>', inline(caption, size=21))
    return img + cap


def table(caption, widths, aligns, rows):
    widths = [int(w) for w in widths.split(",")]
    assert sum(widths) <= TEXT_W, (caption, sum(widths))
    ncol = len(widths)
    out = [para('<w:keepNext/><w:spacing w:before="120" w:after="60" w:line="240" w:lineRule="auto"/><w:jc w:val="center"/>', inline(caption, size=21))]
    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)
    out.append('<w:tbl><w:tblPr>'
               f'<w:tblW w:w="{sum(widths)}" w:type="dxa"/><w:jc w:val="center"/>'
               '<w:tblBorders><w:top w:val="single" w:sz="12" w:space="0" w:color="000000"/>'
               '<w:bottom w:val="single" w:sz="12" w:space="0" w:color="000000"/></w:tblBorders>'
               '<w:tblLayout w:type="fixed"/>'
               '<w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="1" w:lastColumn="0" w:noHBand="0" w:noVBand="1"/>'
               f'</w:tblPr><w:tblGrid>{grid}</w:tblGrid>')
    for r_i, cells in enumerate(rows):
        assert len(cells) == ncol, (caption, cells)
        header = r_i == 0
        last = r_i == len(rows) - 1
        tr = ['<w:tr><w:trPr>' + ('<w:tblHeader/>' if header else '') + ('<w:cantSplit/>') + '<w:jc w:val="center"/></w:trPr>']
        for c_i, (w, cell) in enumerate(zip(widths, cells)):
            borders = '<w:tcBorders><w:bottom w:val="single" w:sz="6" w:space="0" w:color="000000"/></w:tcBorders>' if header else ""
            jc = "center" if header or aligns[c_i] == "C" else "left"
            keep = "<w:keepNext/>" if header else ""
            p = para(f'{keep}<w:spacing w:before="20" w:after="20" w:line="240" w:lineRule="auto"/><w:jc w:val="{jc}"/>',
                     inline(cell.strip(), size=21, bold=header))
            tr.append(f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/>{borders}<w:vAlign w:val="center"/></w:tcPr>{p}</w:tc>')
        tr.append("</w:tr>")
        out.append("".join(tr))
    out.append("</w:tbl>")
    return "".join(out)


def table_note(t):
    return para('<w:spacing w:before="60" w:after="120" w:line="300" w:lineRule="auto"/><w:jc w:val="both"/>', inline(t, size=21))


def ref_heading(t):
    return para('<w:keepNext/><w:spacing w:before="360"/>', run(t, size=24, bold=True, east="SimHei"))


def ref_entry(n, text):
    return para('<w:spacing w:after="0" w:line="360" w:lineRule="auto"/><w:ind w:left="420" w:hanging="420"/><w:jc w:val="both"/>',
                run(f"[{n}] {text}", size=21))


# ------------------------------------------------------------------ document
def build_body() -> str:
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    parts, i, fig_idx = [], 0, 1
    ref_head = None
    while i < len(lines):
        ln = lines[i].rstrip()
        i += 1
        if not ln.strip():
            continue
        if ln.startswith("#1 "):
            parts.append(chapter_title(ln[3:]))
        elif ln.startswith("#2 "):
            parts.append(heading(ln[3:], 2))
        elif ln.startswith("#3 "):
            parts.append(heading(ln[3:], 3))
        elif ln.startswith("EQ "):
            expr, num = [x.strip() for x in ln[3:].split("||")]
            parts.append(equation(expr, num))
        elif ln.startswith("FIG "):
            fname, width, cap = [x.strip() for x in ln[4:].split("||")]
            parts.append(figure(fname, width, cap, fig_idx))
            fig_idx += 1
        elif ln.startswith("TBL "):
            cap, widths, aligns = [x.strip() for x in ln[4:].split("||")]
            rows = []
            while not lines[i].startswith("TBLEND"):
                assert lines[i].startswith("| "), lines[i]
                rows.append(lines[i][2:].split(" | "))
                i += 1
            i += 1
            parts.append(table(cap, widths, aligns, rows))
        elif ln.startswith("TNOTE "):
            parts.append(table_note(ln[6:]))
        elif ln.startswith("REFHEAD "):
            ref_head = ln[8:]
        else:
            parts.append(body(ln))
    if ref_head:
        parts.append(ref_heading(ref_head))
        for k, key in enumerate(CITE.order):
            parts.append(ref_entry(FIRST_NEW_REF + k, REFS[key]))
    unused = sorted(set(REFS) - set(CITE.order))
    if unused:
        raise SystemExit(f"references defined but never cited: {unused}")
    return "".join(parts)


def main() -> None:
    zin = zipfile.ZipFile(TEMPLATE)
    tmpl_doc = zin.read("word/document.xml").decode("utf-8")
    root_open = re.match(r"(?s)(<\?xml[^>]*\?>\s*<w:document[^>]*>)", tmpl_doc).group(1)
    sect = ('<w:sectPr><w:pgSz w:w="12240" w:h="15840"/>'
            '<w:pgMar w:top="1417" w:right="1417" w:bottom="1417" w:left="1417" w:header="720" w:footer="720" w:gutter="0"/>'
            '<w:cols w:space="720"/><w:docGrid w:linePitch="360"/></w:sectPr>')
    body_xml = build_body()
    document = f"{root_open}<w:body>{body_xml}{sect}</w:body></w:document>"

    rels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']
    base = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
    for rid, typ, target in [("rId1", "customXml", "../customXml/item1.xml"), ("rId2", "numbering", "numbering.xml"),
                             ("rId3", "styles", "styles.xml"), ("rId4", "settings", "settings.xml"),
                             ("rId5", "webSettings", "webSettings.xml"), ("rId10", "fontTable", "fontTable.xml"),
                             ("rId11", "theme", "theme/theme1.xml")]:
        rels.append(f'<Relationship Id="{rid}" Type="{base}{typ}" Target="{target}"/>')
    for k, (rid, path) in enumerate(MEDIA.items, 1):
        rels.append(f'<Relationship Id="{rid}" Type="{base}image" Target="media/image{k}.png"/>')
    rels.append("</Relationships>")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    core = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            '<dc:title>第5章 融合渗流机理与空基巡检病害信息的堤防渗流安全透明评价</dc:title><dc:creator></dc:creator>'
            '<cp:lastModifiedBy></cp:lastModifiedBy><cp:revision>1</cp:revision>'
            f'<dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>'
            f'<dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified></cp:coreProperties>')
    app = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
           'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
           '<Template>Normal</Template><Application>Microsoft Office Word</Application><DocSecurity>0</DocSecurity>'
           '<ScaleCrop>false</ScaleCrop><LinksUpToDate>false</LinksUpToDate><SharedDoc>false</SharedDoc>'
           '<HyperlinksChanged>false</HyperlinksChanged><AppVersion>16.0000</AppVersion></Properties>')

    OUT.parent.mkdir(parents=True, exist_ok=True)
    keep = ["[Content_Types].xml", "_rels/.rels", "customXml/_rels/item1.xml.rels", "customXml/item1.xml",
            "customXml/itemProps1.xml", "word/styles.xml", "word/settings.xml", "word/webSettings.xml",
            "word/fontTable.xml", "word/numbering.xml", "word/theme/theme1.xml"]
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for name in keep:
            z.writestr(name, zin.read(name))
        z.writestr("docProps/core.xml", core)
        z.writestr("docProps/app.xml", app)
        z.writestr("word/document.xml", document)
        z.writestr("word/_rels/document.xml.rels", "".join(rels))
        for k, (rid, path) in enumerate(MEDIA.items, 1):
            z.write(path, f"word/media/image{k}.png")
    print(f"wrote {OUT} ({len(MEDIA.items)} figures, {len(CITE.order)} new references "
          f"[{FIRST_NEW_REF}]-[{FIRST_NEW_REF + len(CITE.order) - 1}])")


if __name__ == "__main__":
    main()
