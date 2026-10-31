"""Excerpt of the tracked-changes thesis: Ch2 2.5, 2.6, 2.8 and conclusion 7.1(3), media pruned.

    python3 extract.py <tracked_unpacked_dir> <original_unpacked_dir> <out_dir>
The equation rows (2-7), (2-8) were replaced without tracking in the full file; here the old formula is
shown as a deleted run in front of the new equation so that the reviewer sees both.
"""
import copy, os, re, shutil, sys
from lxml import etree

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
src, orig, out = sys.argv[1:4]
shutil.rmtree(out, ignore_errors=True)
shutil.copytree(src, out)
doc = etree.parse(os.path.join(out, "word", "document.xml"))
body = doc.getroot().find(W + "body")
kids = list(body)
okids = list(etree.parse(os.path.join(orig, "word", "document.xml")).getroot().find(W + "body"))
txt = lambda e: "".join(t.text or "" for t in e.iter(W + "t"))

def find(pred, start=0):
    return next(i for i in range(start, len(kids)) if pred(kids[i]))

keep = list(range(70, 71)) + list(range(134, 163)) + list(range(169, 171))   # Ch2 title, 2.5-2.6, 2.8
c7 = find(lambda e: txt(e).startswith("第7章"), 1500)
keep += [c7, c7 + 1, find(lambda e: txt(e).startswith("（3）在透明评价方面"), c7)]
sect = kids[-1]
selected = [copy.deepcopy(kids[i]) for i in keep]

# old formulas of (2-7) and (2-8) as tracked deletions next to the new equation objects
rid = 990000
for old_i in (153, 158):
    old_text = txt(okids[old_i].findall(W + "tr")[0].findall(W + "tc")[0])
    new_tbl = selected[keep.index(old_i)]
    p = new_tbl.findall(W + "tr")[0].findall(W + "tc")[0].find(W + "p")
    d = etree.Element(W + "del")
    for k, v in (("id", str(rid)), ("author", "Claude"), ("date", "2026-10-31T00:00:00Z")):
        d.set(W + k, v)
    rid += 1
    r = etree.SubElement(d, W + "r")
    rpr = etree.SubElement(r, W + "rPr")
    etree.SubElement(rpr, W + "rFonts").set(W + "ascii", "Times New Roman")
    dt = etree.SubElement(r, W + "delText")
    dt.text = old_text + "  "
    dt.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    p.find(W + "pPr").addnext(d)

for e in list(body):
    body.remove(e)
for e in selected:
    body.append(e)
body.append(sect)
doc.write(os.path.join(out, "word", "document.xml"), xml_declaration=True, encoding="UTF-8", standalone=True)

# drop relationships and media that the excerpt no longer uses
xml = open(os.path.join(out, "word", "document.xml"), encoding="utf-8").read()
used = set(re.findall(r'r:(?:embed|id|link)="([^"]+)"', xml))
rels_path = os.path.join(out, "word", "_rels", "document.xml.rels")
rels = etree.parse(rels_path)
for rel in list(rels.getroot()):
    t = rel.get("Type").rsplit("/", 1)[-1]
    if t in ("image", "oleObject", "package", "chart") and rel.get("Id") not in used:
        target = os.path.join(out, "word", rel.get("Target"))
        rels.getroot().remove(rel)
        if os.path.exists(target):
            os.remove(target)
rels.write(rels_path, xml_declaration=True, encoding="UTF-8", standalone=True)
# media still referenced by headers/footers stay; anything else unreferenced goes
refd = set()
for dp, _, fs in os.walk(os.path.join(out, "word", "_rels")):
    for f in fs:
        refd |= set(re.findall(r'Target="media/([^"]+)"', open(os.path.join(dp, f), encoding="utf-8").read()))
for f in os.listdir(os.path.join(out, "word", "media")):
    if f not in refd:
        os.remove(os.path.join(out, "word", "media", f))
for d in ("embeddings",):
    pth = os.path.join(out, "word", d)
    if os.path.isdir(pth):
        for f in os.listdir(pth):
            if f not in xml and not any(f in open(os.path.join(dp, ff), encoding="utf-8").read()
                                        for dp, _, fs in os.walk(os.path.join(out, "word", "_rels")) for ff in fs):
                os.remove(os.path.join(pth, f))
print("kept", len(selected), "elements;", len(os.listdir(os.path.join(out, "word", "media"))), "media files")
