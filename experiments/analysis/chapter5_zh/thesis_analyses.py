"""Additional analyses for the thesis-style copy of Chapter 5 (2026-10-11).

1. rf_tuning: validation curves of the random-forest decision layer on the 875-record
   benchmark (grouped five-fold out-of-fold macro-F1 and training-fold macro-F1) for the
   number of trees, the maximum depth and the number of candidate features per split,
   with the other two held at the delivered setting (120 trees, depth 7, 4 features).
2. rf_importance: grouped permutation importance of the delivered forest.  A raw feature
   and its derived copy (e.g. seepage_i and seepage_i/0.25) are permuted together, so the
   nine physical/inspection quantities are scored, not the fourteen columns.
3. inspection: de-identified description of the 2025-08-28 field flights.  Camera
   positions are read from the radiometric-report text, split into survey sites at jumps
   larger than 1 km, and written as metres relative to each site's first image; no
   absolute coordinate and no inter-site distance is written.  Image-wise maximum and
   minimum temperatures are taken only where the report text gives them unambiguously
   (file name followed by the two values).

Run from the repository root.  Writes thesis_analyses.json next to this file.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "experiments" / "analysis" / "paper_revision"))
import paper_statistics as P  # noqa: E402  (feature construction, folds and forest as in the paper)

GROUPS = [  # (label, columns of P.FEATURES)
    ("堤顶高程", ["top_elevation_m"]),
    ("堤基坡降", ["seepage_i", "seepage_ratio"]),
    ("堤身坡降", ["body_i", "body_ratio"]),
    ("接触带坡降", ["contact_i", "contact_ratio"]),
    ("背水坡安全系数", ["fos_back", "inv_fos_back"]),
    ("临水坡安全系数", ["fos_front"]),
    ("冲刷深度", ["scour_depth_m", "scour_ratio"]),
    ("巡检异常密度", ["uav_density"]),
    ("巡检证据等级", ["uav_level"]),
]


def macro_f1(y, pred) -> float:
    return float(P.metrics(y, pred)["macro_f1"])


def fit_folds(x, y, fold, n_estimators=120, max_depth=7, max_features=4):
    models = []
    for f in range(5):
        m = P.RandomForest(n_estimators=n_estimators, max_depth=max_depth, min_samples_leaf=3,
                           max_features=max_features, seed=20260929 + f)
        m.fit(x[fold != f], y[fold != f])
        models.append(m)
    return models


def scores(models, x, y, fold):
    oof = np.zeros((len(y), 3))
    train = []
    for f, m in enumerate(models):
        oof[fold == f] = m.predict_proba(x[fold == f])
        train.append(macro_f1(y[fold != f], np.argmax(m.predict_proba(x[fold != f]), 1)))
    return oof, float(np.mean(train))


def rf_tuning(x, y, fold) -> dict:
    grid = {"n_estimators": [10, 20, 40, 60, 80, 120, 160, 200],
            "max_depth": [2, 3, 4, 5, 6, 7, 8, 10, 12],
            "max_features": [1, 2, 3, 4, 6, 8, 10, 14]}
    base = {"n_estimators": 120, "max_depth": 7, "max_features": 4}
    out = {}
    for name, values in grid.items():
        rows = []
        for v in values:
            kw = dict(base, **{name: v})
            oof, tr = scores(fit_folds(x, y, fold, **kw), x, y, fold)
            pred_thr = P.threshold(oof)
            rows.append({"value": v, "train_macro_f1": tr, "oof_macro_f1": macro_f1(y, np.argmax(oof, 1)),
                         "oof_macro_f1_threshold": macro_f1(y, pred_thr),
                         "oof_c_to_a_threshold": int(np.sum((y == 2) & (pred_thr == 0)))})
            print(name, v, {k: round(val, 3) if isinstance(val, float) else val for k, val in rows[-1].items()})
        out[name] = rows
    return out


def rf_importance(x, y, fold, repeats=10) -> dict:
    models = fit_folds(x, y, fold)
    oof, _ = scores(models, x, y, fold)
    ref = P.oof_proba(x, y, fold)
    assert np.allclose(oof, ref), "delivered forest not reproduced"
    base_pred = P.threshold(oof)
    base = {"accuracy": float(np.mean(base_pred == y)), "macro_f1": macro_f1(y, base_pred)}
    rng = np.random.default_rng(20261011)
    res = []
    for label, cols in GROUPS:
        idx = [P.FEATURES.index(c) for c in cols]
        d_acc, d_f1 = [], []
        for _ in range(repeats):
            proba = np.zeros_like(oof)
            for f, m in enumerate(models):
                te = np.where(fold == f)[0]
                xp = x[te].copy()
                perm = rng.permutation(len(te))
                xp[:, idx] = xp[perm][:, idx]          # permute the quantity and its derived copy together
                proba[te] = m.predict_proba(xp)
            pred = P.threshold(proba)
            d_acc.append(base["accuracy"] - float(np.mean(pred == y)))
            d_f1.append(base["macro_f1"] - macro_f1(y, pred))
        res.append({"group": label, "columns": cols, "d_accuracy_mean": float(np.mean(d_acc)),
                    "d_accuracy_sd": float(np.std(d_acc, ddof=1)), "d_macro_f1_mean": float(np.mean(d_f1)),
                    "d_macro_f1_sd": float(np.std(d_f1, ddof=1))})
        print(label, round(res[-1]["d_macro_f1_mean"], 4))
    return {"baseline": base, "repeats": repeats, "groups": res}


def inspection() -> dict:
    text = (REPO / "inspection" / "audit" / "原始图像辐射温度报告_提取文本.txt").read_text(encoding="utf-8")
    names = list(dict.fromkeys(re.findall(r"DJI_\d{14}_\d{4}_T\.JPG", text)))
    gps = [(float(a), float(b)) for a, b in re.findall(r"经纬度 ([\d.]+), ([\d.]+)", text)]
    assert names == sorted(names) and len(gps) == len(names) == 113
    times = [dt.datetime.strptime(n[4:18], "%Y%m%d%H%M%S") for n in names]
    heads = {m.group(1): (float(m.group(2)), float(m.group(3)))
             for m in re.finditer(r"(DJI_\d{14}_\d{4}_T\.JPG)\n(\d+(?:\.\d+)?)\n(\d+(?:\.\d+)?)\n", text)}

    def metres(p, o):
        return ((p[1] - o[1]) * 111320.0 * math.cos(math.radians(o[0])), (p[0] - o[0]) * 110540.0)

    sites, cur = [], [0]
    for k in range(1, len(gps)):
        if math.dist(metres(gps[k], gps[k - 1]), (0, 0)) > 1000.0:
            sites.append(cur)
            cur = []
        cur.append(k)
    sites.append(cur)
    with (REPO / "inspection" / "audit" / "可疑点复核记录_非空行.csv").open(encoding="utf-8-sig") as f:
        reviewed = {r["文件名"].strip() for r in csv.DictReader(f)}
    out = []
    for s, idx in enumerate(sites):
        o = gps[idx[0]]
        pts = [metres(gps[k], o) for k in idx]
        length = sum(math.dist(pts[j], pts[j - 1]) for j in range(1, len(pts)))
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        out.append({
            "site": "ABC"[s], "images": len(idx), "start": times[idx[0]].strftime("%H:%M"), "end": times[idx[-1]].strftime("%H:%M"),
            "path_length_m": round(length), "extent_m": [round(max(xs) - min(xs)), round(max(ys) - min(ys))],
            "points": [{"file": names[k], "x_m": round(p[0], 1), "y_m": round(p[1], 1), "time": times[k].strftime("%H:%M:%S"),
                        "reviewed_candidate": names[k] in reviewed or names[k].replace(".JPG", ".jpg") in reviewed,
                        "t_max": heads.get(names[k], (None, None))[0], "t_min": heads.get(names[k], (None, None))[1]}
                       for k, p in zip(idx, pts)],
        })
    return {"note": "metres relative to the first image of each site; no absolute coordinates",
            "images_in_report": len(names), "images_with_unambiguous_temperature": len(heads), "sites": out}


def main() -> None:
    with P.DATA_CSV.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    y = np.array([P.target_class(r["target_severity"]) for r in rows], dtype=int)
    x = P.make_x(rows)
    fold = P.grouped_folds(P.group_ids(x))
    out = {"inspection": inspection()}
    for s in out["inspection"]["sites"]:
        print(s["site"], s["images"], s["start"], s["end"], s["path_length_m"], s["extent_m"],
              sum(p["reviewed_candidate"] for p in s["points"]))
    out["rf_importance"] = rf_importance(x, y, fold)
    out["rf_tuning"] = rf_tuning(x, y, fold)
    (HERE / "thesis_analyses.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", HERE / "thesis_analyses.json")


if __name__ == "__main__":
    main()
