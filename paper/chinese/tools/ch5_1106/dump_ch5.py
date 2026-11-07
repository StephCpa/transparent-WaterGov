import sys
from lxml import etree
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
body = etree.parse(sys.argv[1]).getroot().find(W + "body")
def t(e):
    return "".join(x.text or "" for x in e.iter(W + "t", M + "t"))
for i, e in enumerate(body):
    if e.tag == W + "tbl":
        rows = [" | ".join("".join(t(p) for p in c.iter(W + "p")) for c in r.iter(W + "tc")) for r in e.iter(W + "tr")]
        print(f"[{i}] TBL " + " ‖ ".join(rows))
    elif e.tag == W + "p":
        s = t(e)
        if s.strip():
            print(f"[{i}] {s}")
