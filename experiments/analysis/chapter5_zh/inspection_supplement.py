"""Field-inspection statistics from the supplementary inspection package (2026-10-12).

Reads only files under inspection/巡检识别补充资料/ and writes inspection_supplement.json next to
this file.  No coordinate, place name or reviewer name is written.

1. flight: relative flight altitude and gimbal pitch of the 113 thermal images, read from the
   DJI XMP block of the raw R-JPEGs (RelativeAltitude is relative to the take-off point), and the
   ground sampling distance GSD = H p / f of the H20T thermal camera (p = 12 um, f = 13.5 mm).
   Images are grouped into the three survey sites by acquisition time (A before 10:30, B 10:30 to
   15:00, C after 15:00), which reproduces the 87/24/2 split of thesis_analyses.json.
2. temperature: image-wise maximum and minimum temperature of all 113 images, parsed from the
   129-page radiometric report (pdftotext -layout).  Four records whose labels are run together
   in the report text are given in FIXED as read from the report.  The report states the
   measurement parameters (distance 5 m, humidity 70 %, emissivity 1.00, reflected 23.0 C).
3. candidates: the nine field detections (label files: class, cx, cy, w, h, confidence, all
   normalised to the 640x512 image) with box size in pixels and metres, the review conclusion and
   reason from the review table, and an approximate box-to-surround temperature difference
   dT = mean(T_box) - median(T_ring), Eq. (5-6), where T is recovered from the exported
   pseudo-colour radiometric image by matching each pixel to the colour bar (top = image maximum,
   bottom = image minimum).  The ring is the box enlarged to twice its width and height minus the
   box itself.  The inversion inherits the palette quantisation and JPEG noise of the export and
   the default emissivity, so dT is an approximate relative value.
4. validation: detections on the 13 artificial-piping images (public model-test data).

Run from the repository root (requires numpy, Pillow and poppler's pdftotext):
    python3 experiments/analysis/chapter5_zh/inspection_supplement.py
"""

from __future__ import annotations

import json
import re
import statistics as st
import subprocess
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
from PIL import Image

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PKG = REPO / "inspection" / "巡检识别补充资料"
RAW = PKG / "第一批优先资料" / "01_原始图像及视频" / "01_益阳堤防红外巡检图像"
DET = PKG / "第一批优先资料" / "02_检测框与置信度输出" / "01_益阳堤防红外巡检图像检测结果" / "detections" / "labels"
VAL = PKG / "第一批优先资料" / "02_检测框与置信度输出" / "02_人造管涌渗漏点红外图像（验证）检测结果" / "detections" / "labels"
REVIEW = PKG / "第一批优先资料" / "04_可疑点复核记录" / "可疑点复核记录表.xlsx"
RAD = PKG / "第二批补充资料" / "01_原始辐射温度"
PIXEL_PITCH, FOCAL = 12e-6, 13.5e-3          # H20T thermal camera
W_IMG, H_IMG = 640, 512
FIXED = {  # report labels run together in the text layer; values as printed in the report
    "DJI_20250828094939_0041_T.JPG": (43.0, 27.9),
    "DJI_20250828095346_0063_T.JPG": (44.2, 26.4),
    "DJI_20250828095402_0066_T.JPG": (44.3, 25.7),
    "DJI_20250828103837_0001_T.JPG": (45.5, 21.1),
}
REASONS = [  # review wording -> reason class, first match wins
    (("图像边缘",), "潮湿地面或镜头边缘"),
    (("水体", "水域", "水岸"), "水陆边界"),
    (("建筑",), "建筑边缘与阴影"),
    (("植被",), "植被与阴影"),
]


def site_of(hhmmss: str) -> str:
    minutes = int(hhmmss[:2]) * 60 + int(hhmmss[3:5])
    return "A" if minutes < 630 else ("B" if minutes < 900 else "C")


def summary(v) -> dict:
    v = [float(x) for x in v]
    return {"n": len(v), "min": round(min(v), 2), "median": round(st.median(v), 2),
            "mean": round(st.mean(v), 2), "max": round(max(v), 2)}


def flight() -> dict:
    rows = []
    for f in sorted(RAW.glob("*_T.JPG")):
        raw = f.read_bytes()
        m = re.search(rb"<x:xmpmeta.*?</x:xmpmeta>", raw, re.S)
        xmp = m.group(0).decode("utf-8", "ignore") if m else ""
        def g(k):
            mm = re.search(k + r'="([^"]*)"', xmp)
            return float(mm.group(1)) if mm else None
        t = f.name[12:14] + ":" + f.name[14:16] + ":" + f.name[16:18]
        rows.append({"file": f.name, "time": t, "site": site_of(t),
                     "rel_alt_m": g("drone-dji:RelativeAltitude"), "pitch_deg": g("drone-dji:GimbalPitchDegree")})
    out = {"n_images": len(rows), "sites": {}}
    for s in "ABC":
        r = [x for x in rows if x["site"] == s]
        alts = [x["rel_alt_m"] for x in r]
        out["sites"][s] = {"n": len(r), "start": r[0]["time"][:5], "end": r[-1]["time"][:5],
                           "rel_alt_m": summary(alts), "pitch_deg": summary(x["pitch_deg"] for x in r),
                           "n_alt_40_60": sum(40 <= a < 60 for a in alts), "n_alt_85_105": sum(85 <= a < 105 for a in alts)}
    nadir = [x for x in rows if x["pitch_deg"] <= -80]
    out["n_nadir_pitch_le_-80"] = len(nadir)
    out["gsd_cm_at_50m"] = round(50 * PIXEL_PITCH / FOCAL * 100, 2)
    out["gsd_cm_at_100m"] = round(100 * PIXEL_PITCH / FOCAL * 100, 2)
    out["footprint_m_at_50m"] = [round(50 * PIXEL_PITCH / FOCAL * W_IMG, 1), round(50 * PIXEL_PITCH / FOCAL * H_IMG, 1)]
    out["images"] = [{k: x[k] for k in ("file", "time", "site", "rel_alt_m", "pitch_deg")} for x in rows]
    return out


def temperatures() -> dict:
    pdf = RAD / "原始图像辐射温度报告.pdf"
    text = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, check=True).stdout.decode("utf-8")
    t = re.sub(r"\s+", " ", text)
    pat = re.compile(r"(DJI_\d{14}_\d{4}_T\.JPG) (\d+(?:\.\d+)?) (\d+(?:\.\d+)?)℃ (\d+(?:\.\d+)?)℃ (\d+(?:\.\d+)?) "
                     r"(DJI_\d{14}_\d{4}_T\.JPG) \d{4}/\d\d/\d\d (\d\d:\d\d:\d\d)")
    rec = {}
    for m in pat.finditer(t):
        n, a, b, c, d, n2, tm = m.groups()
        assert n == n2 and a == b and c == d, m.group(0)
        rec[n] = (float(a), float(c))
    names = sorted(set(re.findall(r"DJI_\d{14}_\d{4}_T\.JPG", t)))
    for n, v in FIXED.items():
        assert n in names and n not in rec, n
        rec[n] = v
    assert len(rec) == len(names) == 113, (len(rec), len(names))
    params = {k: sorted(set(re.findall(k + r" (\S+(?: mm)?)", t))) for k in ("距离", "空气湿度", "发射率", "反射温度", "焦距", "光圈")}
    rows = [{"file": n, "time": n[12:14] + ":" + n[14:16] + ":" + n[16:18], "t_max": rec[n][0], "t_min": rec[n][1]} for n in names]
    for r in rows:
        r["site"] = site_of(r["time"])
        r["span"] = round(r["t_max"] - r["t_min"], 1)
    out = {"n_images": len(rows), "parameters": params, "all": {
        "t_max": summary(r["t_max"] for r in rows), "t_min": summary(r["t_min"] for r in rows),
        "span": summary(r["span"] for r in rows)}, "sites": {}, "images": rows}
    for s in "ABC":
        r = [x for x in rows if x["site"] == s]
        out["sites"][s] = {"t_max": summary(x["t_max"] for x in r), "t_min": summary(x["t_min"] for x in r),
                           "span": summary(x["span"] for x in r)}
    return out


def review_table() -> dict:
    z = zipfile.ZipFile(REVIEW)
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    ss = ["".join(x.text or "" for x in si.iter(ns + "t")) for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(ns + "si")]
    cells = {}
    for c in ET.fromstring(z.read("xl/worksheets/sheet1.xml")).iter(ns + "c"):
        v = c.find(ns + "v")
        if v is not None:
            cells[c.get("r")] = ss[int(v.text)] if c.get("t") == "s" else v.text
    out = {}
    for r in range(2, 200):
        name = cells.get(f"C{r}")
        if name and name.startswith("DJI_"):
            note = cells.get(f"J{r}", "")
            reason = next(lab for keys, lab in REASONS if any(k in note for k in keys))
            out[name.replace(".jpg", "").replace(".JPG", "")] = {
                "conf_table": float(cells[f"H{r}"]), "result": cells.get(f"I{r}"), "reason": reason,
                "reviewer_given": bool(cells.get(f"L{r}")), "review_time_given": bool(cells.get(f"M{r}")),
                "action_given": bool(cells.get(f"K{r}"))}
    return out


def palette_temperature(img: np.ndarray, t_max: float, t_min: float) -> np.ndarray:
    """Temperature of the 640x512 image area by nearest colour on the exported colour bar."""
    bar = img[:, 690:698].mean(axis=1)
    rows = np.nonzero(bar.sum(axis=1) > 0)[0]
    r0, r1 = rows[0], rows[-1]
    pal = bar[r0:r1 + 1]                                    # top = maximum
    temps = t_max - (np.arange(len(pal)) / (len(pal) - 1)) * (t_max - t_min)
    area = img[8:8 + H_IMG, 0:W_IMG].reshape(-1, 3)
    idx = np.empty(len(area), dtype=int)
    for k in range(0, len(area), 40960):                   # chunked nearest-neighbour search
        d = ((area[k:k + 40960, None, :] - pal[None, :, :]) ** 2).sum(axis=2)
        idx[k:k + 40960] = d.argmin(axis=1)
    return temps[idx].reshape(H_IMG, W_IMG)


def candidates(temp: dict, fl: dict) -> list:
    alt = {x["file"].replace(".JPG", ""): x["rel_alt_m"] for x in fl["images"]}
    tmm = {x["file"].replace(".JPG", ""): (x["t_max"], x["t_min"]) for x in temp["images"]}
    rev = review_table()
    out = []
    for f in sorted(DET.glob("*.txt")):
        stem = f.stem
        cls, cx, cy, w, h, conf = map(float, f.read_text().split())
        exported = sorted((RAD / "原始辐射温度图像").glob(stem + "_JPG__*.jpg"))
        assert len(exported) == 1, stem
        img = np.asarray(Image.open(exported[0]).convert("RGB")).astype(float)
        assert img.shape[:2] == (555, 739), img.shape
        tmax, tmin = tmm[stem]
        T = palette_temperature(img, tmax, tmin)
        x0, x1 = int(round((cx - w / 2) * W_IMG)), int(round((cx + w / 2) * W_IMG))
        y0, y1 = int(round((cy - h / 2) * H_IMG)), int(round((cy + h / 2) * H_IMG))
        X0, X1 = max(0, int(round((cx - w) * W_IMG))), min(W_IMG, int(round((cx + w) * W_IMG)))
        Y0, Y1 = max(0, int(round((cy - h) * H_IMG))), min(H_IMG, int(round((cy + h) * H_IMG)))
        mask = np.zeros_like(T, dtype=bool); mask[Y0:Y1, X0:X1] = True
        inner = np.zeros_like(mask); inner[max(0, y0):y1, max(0, x0):x1] = True
        ring = mask & ~inner
        t_box, t_ring = float(T[inner].mean()), float(np.median(T[ring]))
        gsd = alt[stem] * PIXEL_PITCH / FOCAL
        r = rev[stem]
        assert abs(r["conf_table"] - conf) < 0.006, (stem, r["conf_table"], conf)
        out.append({"file": stem, "time": stem[12:14] + ":" + stem[14:16] + ":" + stem[16:18],
                    "site": site_of(stem[12:14] + ":" + stem[14:16]), "conf": round(conf, 3),
                    "box_px": [round(w * W_IMG), round(h * H_IMG)], "box_frac_area": round(w * h, 3),
                    "rel_alt_m": round(alt[stem], 1), "box_m": [round(w * W_IMG * gsd, 1), round(h * H_IMG * gsd, 1)],
                    "touches_edge": bool(x0 <= 2 or y0 <= 2 or x1 >= W_IMG - 2 or y1 >= H_IMG - 2),
                    "t_box": round(t_box, 1), "t_ring": round(t_ring, 1), "dT": round(t_box - t_ring, 1),
                    "box_percentile": round(float((T < t_box).mean() * 100), 1),
                    "image_span": round(tmax - tmin, 1), "result": r["result"], "reason": r["reason"]})
    return out


def validation() -> dict:
    boxes = []
    for f in sorted(VAL.glob("*.txt")):
        for line in f.read_text().split("\n"):
            if line.strip():
                cls, cx, cy, w, h, conf = map(float, line.split())
                boxes.append({"file": f.stem, "conf": round(conf, 3), "box_frac_area": round(w * h, 3)})
    return {"n_images": len({b["file"] for b in boxes}), "n_boxes": len(boxes),
            "conf": summary(b["conf"] for b in boxes), "boxes": boxes}


def main() -> None:
    fl = flight()
    temp = temperatures()
    cand = candidates(temp, fl)
    rev = review_table()
    out = {"flight": fl, "temperature": temp, "candidates": cand, "validation": validation(),
           "review": {"n": len(rev), "results": sorted({v["result"] for v in rev.values()}),
                      "reasons": {k: sum(v["reason"] == k for v in rev.values()) for _, k in REASONS},
                      "reviewer_given": sum(v["reviewer_given"] for v in rev.values()),
                      "review_time_given": sum(v["review_time_given"] for v in rev.values()),
                      "action_given": sum(v["action_given"] for v in rev.values())}}
    text = json.dumps(out, ensure_ascii=False, indent=1)
    assert not re.search(r"\b(28|112)\.\d{4,}", text), "coordinates must not be written"
    (HERE / "inspection_supplement.json").write_text(text, encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("review", "validation")}, ensure_ascii=False)[:600])
    for c in cand:
        print(c["file"][13:], c["site"], c["conf"], c["box_px"], c["box_m"], c["rel_alt_m"], c["t_box"], c["t_ring"], c["dT"], c["box_percentile"], c["image_span"], c["reason"], c["touches_edge"])
    print("sites", json.dumps(fl["sites"], ensure_ascii=False))
    print("temps", json.dumps(temp["all"], ensure_ascii=False), json.dumps(temp["sites"], ensure_ascii=False))


if __name__ == "__main__":
    main()
