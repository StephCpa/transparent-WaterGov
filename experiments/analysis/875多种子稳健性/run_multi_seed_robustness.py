"""Evaluate the transparent safety classifier on independent generator seeds.

This script keeps the controlled scenario generator, target construction, feature
exclusions, grouped OOF split, and RF decision policy fixed.  Only the generator
seed changes.  Results are written outside the authoritative 875-sample package.
"""

from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(r"PROJECT_ROOT")
SRC = ROOT / "分析工作区" / "875基线复现"
OUT = ROOT / "分析工作区" / "875多种子稳健性"
OUT.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(SRC))
with contextlib.redirect_stdout(io.StringIO()):
    from synthetic_dataset_evaluation import (  # type: ignore
        SEVERITIES,
        TARGET_MODES,
        evaluate_section,
        generate_dataset,
    )

ML_OUT = ROOT / "分析工作区" / "ml_baseline与多目标"
sys.path.insert(0, str(ML_OUT))
with contextlib.redirect_stdout(io.StringIO()):
    from run_ml_baselines import RandomForest, metrics  # type: ignore

SEEDS = [20260930, 20260931, 20260932, 20260933, 20260934]
N_PER_CELL = 25
FEATURE_NAMES = [
    "top_elevation_m", "seepage_i", "body_i", "contact_i", "fos_back",
    "fos_front", "scour_depth_m", "uav_density", "uav_level",
]


def target_class(severity: str) -> int:
    return 0 if severity in {"safe", "slight"} else 1 if severity == "moderate" else 2


def grade_class(grade: str) -> int:
    if grade.startswith("A"):
        return 0
    if grade.startswith("B"):
        return 1
    if grade.startswith("C"):
        return 2
    raise ValueError(f"unknown safety grade: {grade}")


def extended(y: np.ndarray, pred: np.ndarray) -> dict:
    result = metrics(y, pred)
    cm = np.asarray(result["cm"])
    result.update({
        "c_to_a": int(cm[2, 0]),
        "c_to_b": int(cm[2, 1]),
        "safe_loss": int(2 * cm[2, 0] + cm[2, 1]),
        "a_overestimate": int(cm[0, 1] + cm[0, 2]),
        "escalation_rate": float(np.mean(pred == 2)),
    })
    return result


def build_features(rows: list[dict]) -> tuple[np.ndarray, list[str]]:
    x0 = np.array([[float(r[k]) for k in FEATURE_NAMES] for r in rows], dtype=float)
    x = np.column_stack([
        x0,
        x0[:, 1] / 0.25,
        x0[:, 2] / 0.25,
        x0[:, 3] / 0.25,
        1.0 / x0[:, 4],
        x0[:, 6] / 1.0,
    ])
    names = FEATURE_NAMES + [
        "seepage_ratio", "body_ratio", "contact_ratio", "inv_fos_back", "scour_ratio",
    ]
    return x, names


def grouped_folds(x: np.ndarray, n_folds: int = 5) -> np.ndarray:
    groups = [hashlib.sha1(np.asarray(row, dtype=np.float64).tobytes()).hexdigest() for row in x]
    unique = sorted(set(groups))
    assignment = {g: i % n_folds for i, g in enumerate(unique)}
    return np.array([assignment[g] for g in groups], dtype=int)


def evaluate_seed(seed: int) -> dict:
    samples, geo_cls, buildings, hist_dangers = generate_dataset(n_per_cell=N_PER_CELL, seed=seed)
    rows: list[dict] = []
    y_list: list[int] = []
    rule_list: list[int] = []

    for sec, leak in samples:
        result = evaluate_section(sec, geo_cls, buildings, hist_dangers, leak)
        target = target_class(sec["synthetic_severity"])
        y_list.append(target)
        rule_list.append(grade_class(result["安全等级"]))
        rows.append({
            "sample_id": sec["桩号"],
            "target_mode": sec["synthetic_target_mode"],
            "target_severity": sec["synthetic_severity"],
            "grade": result["安全等级"],
            "top_elevation_m": sec["堤顶高程_m"],
            "seepage_i": sec["渗透比降i"],
            "body_i": sec["堤身渗透比降i"],
            "contact_i": sec["接触面渗透比降i"],
            "fos_back": sec["背水坡FoS_正常"],
            "fos_front": sec["临水坡FoS"],
            "scour_depth_m": sec["冲刷深度_m"],
            "uav_density": leak["加权渗漏点密度_点每100m"],
            "uav_level": leak["UAV证据等级"],
        })

    y = np.asarray(y_list, dtype=int)
    rule = np.asarray(rule_list, dtype=int)
    x, feature_names = build_features(rows)
    fold = grouped_folds(x)
    proba = np.zeros((len(y), 3), dtype=float)
    for fidx in range(5):
        train, test = fold != fidx, fold == fidx
        model = RandomForest(
            n_estimators=120, max_depth=7, min_samples_leaf=3,
            max_features=4, seed=20260929 + fidx,
        )
        model.fit(x[train], y[train])
        proba[test] = model.predict_proba(x[test])

    rf_majority = np.argmax(proba, axis=1)
    rf_threshold = np.where(proba[:, 2] >= 0.35, 2, np.where(proba[:, 1] >= 0.20, 1, 0))
    hybrid = np.maximum(rf_threshold, rule)
    uncertain = np.max(proba, axis=1) < 0.60
    review_fallback = hybrid.copy()
    review_fallback[uncertain] = rule[uncertain]

    seed_dir = OUT / f"seed_{seed}"
    seed_dir.mkdir(exist_ok=True)
    with (seed_dir / "evaluation_dataset.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    result = {
        "seed": seed,
        "sample_count": int(len(y)),
        "n_per_cell": N_PER_CELL,
        "target_distribution": dict(Counter(y.tolist())),
        "unique_feature_groups": int(len(set(hashlib.sha1(np.asarray(row, dtype=np.float64).tobytes()).hexdigest() for row in x))),
        "features": feature_names,
        "rule": extended(y, rule),
        "rf_majority": extended(y, rf_majority),
        "rf_threshold": extended(y, rf_threshold),
        "hybrid_physical_veto": extended(y, hybrid),
        "review_fallback": extended(y, review_fallback),
        "review_rate": float(np.mean(uncertain)),
        "n_review": int(np.sum(uncertain)),
        "split": "5-fold grouped OOF by identical physical feature vector",
    }
    (seed_dir / "seed_results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def aggregate(results: list[dict]) -> dict:
    methods = ["rule", "rf_majority", "rf_threshold", "hybrid_physical_veto", "review_fallback"]
    metrics_to_report = [
        "accuracy", "macro_f1", "balanced_accuracy", "c_recall", "c_underestimate",
        "a_overestimate", "safe_loss", "escalation_rate",
    ]
    summary: dict = {"seeds": SEEDS, "sample_count_per_seed": N_PER_CELL * len(TARGET_MODES) * len(SEVERITIES), "methods": {}}
    for method in methods:
        summary["methods"][method] = {}
        for metric in metrics_to_report:
            values = np.array([float(r[method][metric]) for r in results], dtype=float)
            summary["methods"][method][metric] = {
                "mean": float(values.mean()),
                "sd": float(values.std(ddof=1)),
                "min": float(values.min()),
                "max": float(values.max()),
                "values": values.tolist(),
            }
    summary["review_rate"] = {
        "mean": float(np.mean([r["review_rate"] for r in results])),
        "sd": float(np.std([r["review_rate"] for r in results], ddof=1)),
        "values": [r["review_rate"] for r in results],
    }
    return summary


def main() -> None:
    results = [evaluate_seed(seed) for seed in SEEDS]
    summary = aggregate(results)
    (OUT / "multi_seed_results.json").write_text(
        json.dumps({"per_seed": results, "aggregate": summary}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    fields = ["seed", "method", "accuracy", "macro_f1", "balanced_accuracy", "c_recall", "c_underestimate", "a_overestimate", "safe_loss", "escalation_rate", "review_rate"]
    with (OUT / "multi_seed_summary.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for result in results:
            for method in ["rule", "rf_majority", "rf_threshold", "hybrid_physical_veto", "review_fallback"]:
                row = {"seed": result["seed"], "method": method, **{k: result[method][k] for k in fields[2:10]}}
                row["review_rate"] = result["review_rate"]
                writer.writerow(row)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
