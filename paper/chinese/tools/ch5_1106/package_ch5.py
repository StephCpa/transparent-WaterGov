"""Package the rebuilt thesis: replace Chapter 5 figures, fix aspect ratios, ask Word to update fields, zip;
then cut the Chapter 5 excerpt. Usage: python3 package_ch5.py <document_new.xml> <out_dir>"""
import copy
import os
import shutil
import subprocess
import sys

from lxml import etree
from PIL import Image

sys.path.insert(0, "/home/user/transparent-levee-thesis/tools/1103")
from package import drop_comments, prune_media, save  # noqa: E402

SCR = "/tmp/claude-0/-home-user/f59ef07b-f32a-5042-95e9-1f3b78d4895d/scratchpad"
SRC_DIR = f"{SCR}/v11/x"
FIGS = "/home/user/transparent-WaterGov/paper/chinese/chapters/figures_ch5_thesis"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
WP = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
MEDIA = {  # v11 media file -> regenerated figure (new terms, no grey lettering)
    "image126.png": "fig5_1_framework.png", "image127.png": "fig5_2_indicator_system.png",
    "image119.png": "fig5_3_inspection_workflow.png", "image128.png": "fig5_5_decision_chain.png",
    "image131.png": "fig5_6_evaluation_system.png", "image132.png": "fig5_method_compare.png",
    "image133.png": "fig5_supp_error_structure.png", "image134.png": "fig5_typical_records.png",
    "image129.png": "fig5_sensitivity.png", "image130.png": "fig5_rf_tuning.png",
    "image135.png": "fig5_multiseed.png", "image136.png": "fig5_supp_policy_evaluation.png",
    "image137.png": "fig5_k45500.png", "image138.png": "fig5_ch4_interval.png",
    "image122.png": "fig5_survey_sites.png", "image125.png": "fig5_detection_examples.png",
    "image139.png": "fig5_injection.png"}

doc_xml, out = sys.argv[1], sys.argv[2]
full = f"{out}/full"
shutil.rmtree(out, ignore_errors=True)
shutil.copytree(SRC_DIR, full)
shutil.copyfile(doc_xml, f"{full}/word/document.xml")

# ---------------------------------------------------------------- figures and aspect ratios
rels = etree.parse(f"{full}/word/_rels/document.xml.rels").getroot()
rid2media = {r.get("Id"): os.path.basename(r.get("Target")) for r in rels}
ratio = {}
for media, png in MEDIA.items():
    shutil.copyfile(f"{FIGS}/{png}", f"{full}/word/media/{media}")
    w, h = Image.open(f"{FIGS}/{png}").size
    ratio[media] = h / w
doc = etree.parse(f"{full}/word/document.xml")
fixed = 0
for drawing in doc.getroot().iter(W + "drawing"):
    blip = next(drawing.iter(A + "blip"), None)
    if blip is None:
        continue
    media = rid2media.get(blip.get(R + "embed"))
    if media not in ratio:
        continue
    ext = next(drawing.iter(WP + "extent"))
    cx = int(ext.get("cx"))
    cy = int(round(cx * ratio[media]))
    ext.set("cy", str(cy))
    for x in drawing.iter(A + "ext"):
        if x.get("cx") is not None:
            x.set("cx", str(cx)); x.set("cy", str(cy))
    fixed += 1
save(doc, f"{full}/word/document.xml")
print("figures replaced:", len(MEDIA), "| drawings resized:", fixed)

# ---------------------------------------------------------------- ask Word to refresh the table of contents
st_p = f"{full}/word/settings.xml"
st = etree.parse(st_p)
if st.getroot().find(W + "updateFields") is None:
    uf = etree.Element(W + "updateFields"); uf.set(W + "val", "true")
    after = ("hdrShapeDefaults", "footnotePr", "endnotePr", "compat", "docVars", "rsids")
    nxt = next(c for c in st.getroot() if etree.QName(c).localname in after)
    nxt.addprevious(uf)
save(st, st_p)


def zipdir(d, path):
    if os.path.exists(path):
        os.remove(path)
    subprocess.run(["zip", "-qXr", os.path.abspath(path), "."], cwd=d, check=True)


zipdir(full, f"{out}/full.docx")

# ---------------------------------------------------------------- Chapter 5 excerpt
ex = f"{out}/ch5"
shutil.copytree(full, ex)
d = etree.parse(f"{ex}/word/document.xml")
body = d.getroot().find(W + "body")
kids = list(body)
vis = lambda e: "".join(t.text or "" for t in e.iter(W + "t"))  # noqa: E731
a5 = next(i for i, e in enumerate(kids) if e.tag == W + "p" and vis(e).startswith("第5章　"))
b5 = next(i for i, e in enumerate(kids) if i > a5 and e.tag == W + "p" and vis(e).startswith("第6章　"))
sect = None
for i in range(b5 - 1, a5, -1):
    sp = kids[i].find(f"{W}pPr/{W}sectPr")
    if sp is not None:
        sect = copy.deepcopy(sp)
        break
sel = [copy.deepcopy(kids[i]) for i in range(a5, b5)]
for e in list(body):
    body.remove(e)
for e in sel:
    for sp in e.iter(W + "sectPr"):
        sp.getparent().remove(sp)
    body.append(e)
body.append(sect)
save(d, f"{ex}/word/document.xml")
dropped = drop_comments(ex)
print("excerpt elements:", len(sel), "| comments dropped:", len(dropped), "| pruned:", prune_media(ex))
zipdir(ex, f"{out}/ch5.docx")
