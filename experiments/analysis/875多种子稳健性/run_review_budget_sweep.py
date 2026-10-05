"""Sweep the manual-review threshold after the RF physical-veto policy.

The script reuses each saved seed dataset, retrains the same grouped OOF RF,
and varies only the uncertainty threshold used to route predictions to review.
The rule grade is used as an offline fallback so the operational trade-off is
reported separately from the closed-set RF classification result.
"""

from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(r"PROJECT_ROOT")
OUT = ROOT / "分析工作区" / "875多种子稳健性"
ML_OUT = ROOT / "分析工作区" / "ml_baseline与多目标"
sys.path.insert(0, str(ML_OUT))
with contextlib.redirect_stdout(io.StringIO()):
    from run_ml_baselines import RandomForest, metrics  # type: ignore

SEEDS = [20260930, 20260931, 20260932, 20260933, 20260934]
FEATURE_NAMES = [
    "top_elevation_m", "seepage_i", "body_i", "contact_i", "fos_back",
    "fos_front", "scour_depth_m", "uav_density", "uav_level",
]
UNCERTAINTY_THRESHOLDS = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90]


def class_from_severity(value: str) -> int:
    return 0 if value in {"safe", "slight"} else 1 if value == "moderate" else 2


def class_from_grade(value: str) -> int:
    return 0 if value.startswith("A") else 1 if value.startswith("B") else 2


def make_x(rows: list[dict]) -> np.ndarray:
    x0 = np.array([[float(r[k]) for k in FEATURE_NAMES] for r in rows], dtype=float)
    return np.column_stack([
        x0, x0[:, 1] / 0.25, x0[:, 2] / 0.25, x0[:, 3] / 0.25,
        1.0 / x0[:, 4], x0[:, 6] / 1.0,
    ])


def folds(x: np.ndarray) -> np.ndarray:
    groups = [hashlib.sha1(np.asarray(row, dtype=np.float64).tobytes()).hexdigest() for row in x]
    unique = sorted(set(groups))
    mapping = {g: i % 5 for i, g in enumerate(unique)}
    return np.array([mapping[g] for g in groups], dtype=int)


def extended(y: np.ndarray, pred: np.ndarray) -> dict:
    m = metrics(y, pred)
    cm = np.asarray(m["cm"])
    m.update({
        "c_to_a": int(cm[2, 0]), "c_to_b": int(cm[2, 1]),
        "c_underestimate": int(cm[2, 0] + cm[2, 1]),
        "safe_loss": int(2 * cm[2, 0] + cm[2, 1]),
        "a_overestimate": int(cm[0, 1] + cm[0, 2]),
        "escalation_rate": float(np.mean(pred == 2)),
    })
    return m


def one_seed(seed: int) -> list[dict]:
    with (OUT / f"seed_{seed}" / "evaluation_dataset.csv").open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    x = make_x(rows)
    y = np.array([class_from_severity(r["target_severity"]) for r in rows], dtype=int)
    rule = np.array([class_from_grade(r["grade"]) for r in rows], dtype=int)
    split = folds(x)
    proba = np.zeros((len(y), 3), dtype=float)
    for fidx in range(5):
        train, test = split != fidx, split == fidx
        model = RandomForest(n_estimators=120, max_depth=7, min_samples_leaf=3,
                             max_features=4, seed=20260929 + fidx)
        model.fit(x[train], y[train])
        proba[test] = model.predict_proba(x[test])
    rf = np.where(proba[:, 2] >= 0.35, 2, np.where(proba[:, 1] >= 0.20, 1, 0))
    hybrid = np.maximum(rf, rule)
    out = []
    for threshold in UNCERTAINTY_THRESHOLDS:
        review = np.max(proba, axis=1) < threshold
        pred = hybrid.copy()
        pred[review] = rule[review]
        result = extended(y, pred)
        result.update({"seed": seed, "review_threshold": threshold,
                       "review_rate": float(np.mean(review)),
                       "n_review": int(np.sum(review))})
        out.append(result)
    return out


def main() -> None:
    rows = [item for seed in SEEDS for item in one_seed(seed)]
    fields = ["seed", "review_threshold", "review_rate", "n_review", "accuracy",
              "macro_f1", "balanced_accuracy", "c_recall", "c_underestimate",
              "c_to_a", "c_to_b", "safe_loss", "a_overestimate", "escalation_rate"]
    with (OUT / "review_budget_sweep.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: row[k] for k in fields} for row in rows)

    aggregate = []
    for threshold in UNCERTAINTY_THRESHOLDS:
        subset = [r for r in rows if r["review_threshold"] == threshold]
        item = {"review_threshold": threshold}
        for metric in ["review_rate", "accuracy", "macro_f1", "balanced_accuracy",
                       "c_recall", "c_underestimate", "safe_loss", "a_overestimate"]:
            values = np.array([float(r[metric]) for r in subset])
            item[metric] = {"mean": float(values.mean()), "sd": float(values.std(ddof=1)),
                            "min": float(values.min()), "max": float(values.max()),
                            "values": values.tolist()}
        aggregate.append(item)
    result = {
        "seeds": SEEDS,
        "thresholds": UNCERTAINTY_THRESHOLDS,
        "policy": "RF threshold (tau_C=0.35, tau_B=0.20) -> physical veto -> rule fallback when max probability is below threshold",
        "per_seed": rows,
        "aggregate": aggregate,
    }
    (OUT / "review_budget_sweep.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"aggregate": aggregate}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
