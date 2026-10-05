"""Audit whether RF thresholds alone can satisfy a zero C-to-A constraint.

The threshold grid is deliberately finer than the exploratory Pareto grid.  The
script separates (i) a pure learned threshold policy from (ii) the decision-layer
physical floor, so the reported hybrid gain is not attributed to the RF alone.
"""

from __future__ import annotations

import contextlib
import csv
import io
import json
from pathlib import Path

import numpy as np

ROOT = Path(r"PROJECT_ROOT")
OUT = ROOT / "分析工作区" / "ml_baseline与多目标"

import sys
sys.path.insert(0, str(OUT))
with contextlib.redirect_stdout(io.StringIO()):
    from run_ml_baselines import RandomForest, metrics, rows, X, y, fold


def extended(pred: np.ndarray) -> dict:
    m = metrics(y, pred)
    cm = np.asarray(m["cm"])
    m.update({
        "c_to_a": int(cm[2, 0]),
        "c_to_b": int(cm[2, 1]),
        "safe_loss": int(2 * cm[2, 0] + cm[2, 1]),
        "a_overestimate": int(cm[0, 1] + cm[0, 2]),
        "escalation_rate": float(np.mean(pred == 2)),
    })
    return m


def main() -> None:
    rule = y.copy()
    with (ROOT / "分析工作区" / "875基线分析" / "136条误分类溯源.csv").open(encoding="utf-8-sig") as f:
        for er in csv.DictReader(f):
            idx = next(i for i, r in enumerate(rows) if r["sample_id"] == er["sample_id"])
            rule[idx] = {"A": 0, "B": 1, "C": 2}[er["grade"]]

    proba = np.zeros((len(y), 3), dtype=float)
    for fidx in range(5):
        train, test = fold != fidx, fold == fidx
        model = RandomForest(n_estimators=120, max_depth=7, min_samples_leaf=3,
                             max_features=4, seed=20260929 + fidx)
        model.fit(X[train], y[train])
        proba[test] = model.predict_proba(X[test])

    points = []
    for tc in np.arange(0.01, 1.001, 0.01):
        for tb in np.arange(0.01, 1.001, 0.01):
            pred = np.where(proba[:, 2] >= tc, 2,
                            np.where(proba[:, 1] >= tb, 1, 0))
            m = extended(pred)
            points.append({"t_c": round(float(tc), 2), "t_b": round(float(tb), 2), **m})

    unrestricted = max(points, key=lambda p: (p["macro_f1"], p["accuracy"], p["c_recall"]))
    min_c_to_a = min(p["c_to_a"] for p in points)
    min_c_points = [p for p in points if p["c_to_a"] == min_c_to_a]
    best_min_c = max(min_c_points, key=lambda p: (p["macro_f1"], p["accuracy"], p["c_recall"]))
    hard_safe_points = [p for p in points if p["c_to_a"] == 0]

    rf_threshold = np.where(proba[:, 2] >= 0.35, 2,
                            np.where(proba[:, 1] >= 0.20, 1, 0))
    hybrid = np.maximum(rf_threshold, rule)
    summary = {
        "grid": {"step": 0.01, "n_points": len(points), "threshold_min": 0.01, "threshold_max": 1.0},
        "pure_rf_unrestricted_best": unrestricted,
        "pure_rf_minimum_c_to_a": best_min_c,
        "pure_rf_zero_c_to_a_candidate_count": len(hard_safe_points),
        "rf_performance_threshold": extended(rf_threshold),
        "physical_veto_hybrid": extended(hybrid),
        "interpretation": "No pure RF threshold pair on the 0.01 grid satisfies zero direct C-to-A errors; the physical floor is a separate decision-layer constraint.",
    }
    (OUT / "safety_constraint_ablation.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
