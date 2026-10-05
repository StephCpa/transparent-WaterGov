"""Safety-constrained Pareto policy selection and gate ablations.

This experiment keeps the scenario generator, target construction, feature
exclusions, grouped OOF split, and random-forest hyperparameters fixed.  For
each independent generator seed it evaluates a grid of RF class thresholds
and three decision-layer policies:

* ``rf``: thresholded RF only;
* ``c_veto``: force class C when the delivered physical rule is C;
* ``bc_veto``: use the ordinal lower bound ``max(RF, rule)`` for B/C.

The gate is applied after the RF prediction, so it is an explicit decision
policy rather than a feature available to the learner.  Candidates are
considered feasible only when C recall is at least 0.95 and no C case is
assigned to A.  A Pareto front is then computed over macro-F1, balanced
accuracy, C recall, safe-loss, A overestimation, and escalation rate.  The
reported operating point is the Pareto candidate with the smallest normalized
distance to the safety-first ideal (ties: higher macro-F1, lower escalation).

The outputs are written under ``875多种子稳健性`` and never overwrite the
authoritative 875-sample package or the manuscript.
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
TC_GRID = np.arange(0.20, 0.901, 0.05)
TB_GRID = np.arange(0.20, 0.901, 0.05)
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
    result.update(
        {
            "c_to_a": int(cm[2, 0]),
            "c_to_b": int(cm[2, 1]),
            "safe_loss": int(2 * cm[2, 0] + cm[2, 1]),
            "a_overestimate": int(cm[0, 1] + cm[0, 2]),
            "escalation_rate": float(np.mean(pred == 2)),
        }
    )
    return result


def build_features(rows: list[dict]) -> np.ndarray:
    x0 = np.array([[float(r[k]) for k in FEATURE_NAMES] for r in rows], dtype=float)
    return np.column_stack(
        [
            x0,
            x0[:, 1] / 0.25,
            x0[:, 2] / 0.25,
            x0[:, 3] / 0.25,
            1.0 / x0[:, 4],
            x0[:, 6] / 1.0,
        ]
    )


def grouped_folds(x: np.ndarray, n_folds: int = 5) -> np.ndarray:
    groups = [
        hashlib.sha1(np.asarray(row, dtype=np.float64).tobytes()).hexdigest()
        for row in x
    ]
    unique = sorted(set(groups))
    assignment = {g: i % n_folds for i, g in enumerate(unique)}
    return np.array([assignment[g] for g in groups], dtype=int)


def threshold_policy(proba: np.ndarray, tc: float, tb: float) -> np.ndarray:
    return np.where(proba[:, 2] >= tc, 2, np.where(proba[:, 1] >= tb, 1, 0))


def policy_prediction(
    proba: np.ndarray, rule: np.ndarray, tc: float, tb: float, policy: str
) -> np.ndarray:
    rf = threshold_policy(proba, tc, tb)
    if policy == "rf":
        return rf
    if policy == "c_veto":
        return np.where(rule == 2, 2, rf)
    if policy == "bc_veto":
        return np.maximum(rf, rule)
    raise ValueError(policy)


def candidate_record(
    y: np.ndarray,
    pred: np.ndarray,
    proba: np.ndarray,
    seed: int,
    policy: str,
    tc: float,
    tb: float,
) -> dict:
    m = extended(y, pred)
    m.update(
        {
            "seed": int(seed),
            "policy": policy,
            "t_c": round(float(tc), 2),
            "t_b": round(float(tb), 2),
            "review_rate": float(np.mean(np.max(proba, axis=1) < 0.60)),
        }
    )
    return m


# Objectives are all expressed as larger-is-better after transformation.
OBJECTIVES = [
    ("macro_f1", True),
    ("balanced_accuracy", True),
    ("c_recall", True),
    ("safe_loss", False),
    ("a_overestimate", False),
    ("escalation_rate", False),
]


def feasible(row: dict) -> bool:
    return row["c_recall"] >= 0.95 and row["c_to_a"] == 0


def dominates(a: dict, b: dict) -> bool:
    ge = True
    strict = False
    for key, maximize in OBJECTIVES:
        if maximize:
            ge = ge and a[key] >= b[key]
            strict = strict or a[key] > b[key]
        else:
            ge = ge and a[key] <= b[key]
            strict = strict or a[key] < b[key]
    return bool(ge and strict)


def pareto_front(rows: list[dict]) -> list[dict]:
    return [row for row in rows if not any(dominates(other, row) for other in rows)]


def select_knee(rows: list[dict]) -> dict:
    """Select a reproducible safety-first point from a feasible Pareto set.

    The ideal point uses the best value observed in the feasible candidate set;
    the nadir uses the worst.  Each objective is min-max normalized and the
    Euclidean distance to the ideal is computed with equal objective weights.
    Equal weights avoid silently privileging accuracy over safety after the
    hard safety constraint has been applied.
    """
    if not rows:
        raise ValueError("no feasible Pareto candidates")
    mins = {key: min(row[key] for row in rows) for key, _ in OBJECTIVES}
    maxs = {key: max(row[key] for row in rows) for key, _ in OBJECTIVES}
    scored = []
    for row in rows:
        d2 = 0.0
        for key, maximize in OBJECTIVES:
            span = maxs[key] - mins[key]
            if span <= 1e-12:
                continue
            z = (row[key] - mins[key]) / span
            distance = 1.0 - z if maximize else z
            d2 += distance * distance
        copy = dict(row)
        copy["ideal_distance"] = float(np.sqrt(d2))
        scored.append(copy)
    scored.sort(
        key=lambda row: (
            row["ideal_distance"],
            -row["macro_f1"],
            row["escalation_rate"],
            row["t_c"],
            row["t_b"],
            row["policy"],
        )
    )
    return scored[0]


def evaluate_seed(seed: int) -> dict:
    samples, geo_cls, buildings, hist_dangers = generate_dataset(
        n_per_cell=N_PER_CELL, seed=seed
    )
    rows: list[dict] = []
    y_list: list[int] = []
    rule_list: list[int] = []
    for sec, leak in samples:
        result = evaluate_section(sec, geo_cls, buildings, hist_dangers, leak)
        y_list.append(target_class(sec["synthetic_severity"]))
        rule_list.append(grade_class(result["安全等级"]))
        rows.append(
            {
                "top_elevation_m": sec["堤顶高程_m"],
                "seepage_i": sec["渗透比降i"],
                "body_i": sec["堤身渗透比降i"],
                "contact_i": sec["接触面渗透比降i"],
                "fos_back": sec["背水坡FoS_正常"],
                "fos_front": sec["临水坡FoS"],
                "scour_depth_m": sec["冲刷深度_m"],
                "uav_density": leak["加权渗漏点密度_点每100m"],
                "uav_level": leak["UAV证据等级"],
            }
        )

    y = np.asarray(y_list, dtype=int)
    rule = np.asarray(rule_list, dtype=int)
    x = build_features(rows)
    fold = grouped_folds(x)
    proba = np.zeros((len(y), 3), dtype=float)
    for fidx in range(5):
        train, test = fold != fidx, fold == fidx
        model = RandomForest(
            n_estimators=120,
            max_depth=7,
            min_samples_leaf=3,
            max_features=4,
            seed=20260929 + fidx,
        )
        model.fit(x[train], y[train])
        proba[test] = model.predict_proba(x[test])

    all_rows: list[dict] = []
    for policy in ["rf", "c_veto", "bc_veto"]:
        for tc in TC_GRID:
            for tb in TB_GRID:
                pred = policy_prediction(proba, rule, float(tc), float(tb), policy)
                all_rows.append(candidate_record(y, pred, proba, seed, policy, tc, tb))

    feasible_rows = [row for row in all_rows if feasible(row)]
    front = pareto_front(feasible_rows)
    selected = select_knee(front)

    fixed = {}
    for policy in ["rf", "c_veto", "bc_veto"]:
        pred = policy_prediction(proba, rule, 0.35, 0.20, policy)
        fixed[policy] = candidate_record(y, pred, proba, seed, policy, 0.35, 0.20)

    review = fixed["bc_veto"].copy()
    review["policy"] = "bc_veto_review_fallback"
    uncertain = np.max(proba, axis=1) < 0.60
    base_pred = policy_prediction(proba, rule, 0.35, 0.20, "bc_veto")
    review_pred = base_pred.copy()
    review_pred[uncertain] = rule[uncertain]
    review = candidate_record(y, review_pred, proba, seed, review["policy"], 0.35, 0.20)

    return {
        "seed": int(seed),
        "sample_count": int(len(y)),
        "target_distribution": dict(Counter(y.tolist())),
        "candidate_count": len(all_rows),
        "feasible_candidate_count": len(feasible_rows),
        "pareto_count": len(front),
        "fixed": fixed,
        "review_fallback": review,
        "selected": selected,
        "pareto_front": front,
    }


def aggregate(selected_rows: list[dict], fixed_rows: list[dict]) -> dict:
    metrics_to_report = [
        "accuracy",
        "macro_f1",
        "balanced_accuracy",
        "c_recall",
        "c_underestimate",
        "c_to_a",
        "c_to_b",
        "safe_loss",
        "a_overestimate",
        "escalation_rate",
    ]
    methods = sorted(set(row["method"] for row in selected_rows + fixed_rows))
    out: dict = {"methods": {}}
    for method in methods:
        rows = [row for row in selected_rows + fixed_rows if row["method"] == method]
        out["methods"][method] = {}
        for metric in metrics_to_report:
            values = np.asarray([float(row[metric]) for row in rows], dtype=float)
            out["methods"][method][metric] = {
                "mean": float(values.mean()),
                "sd": float(values.std(ddof=1)) if len(values) > 1 else 0.0,
                "min": float(values.min()),
                "max": float(values.max()),
                "values": values.tolist(),
            }
    return out


def main() -> None:
    results = [evaluate_seed(seed) for seed in SEEDS]
    selected_rows = []
    fixed_rows = []
    all_front_rows = []
    for result in results:
        chosen = dict(result["selected"])
        chosen["method"] = "selected_pareto_knee"
        selected_rows.append(chosen)
        for policy, row in result["fixed"].items():
            fixed = dict(row)
            fixed["method"] = f"fixed_{policy}"
            fixed_rows.append(fixed)
        review = dict(result["review_fallback"])
        review["method"] = "fixed_bc_veto_review_fallback"
        fixed_rows.append(review)
        for row in result["pareto_front"]:
            point = dict(row)
            point["is_selected"] = bool(
                point["policy"] == result["selected"]["policy"]
                and point["t_c"] == result["selected"]["t_c"]
                and point["t_b"] == result["selected"]["t_b"]
            )
            all_front_rows.append(point)

    aggregate_result = aggregate(selected_rows, fixed_rows)
    output = {
        "config": {
            "seeds": SEEDS,
            "n_per_cell": N_PER_CELL,
            "threshold_grid": [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90],
            "feasibility": {"c_recall_min": 0.95, "c_to_a_max": 0},
            "objectives": OBJECTIVES,
            "split": "5-fold grouped OOF by identical physical feature vector",
            "rf": {"n_estimators": 120, "max_depth": 7, "min_samples_leaf": 3, "max_features": 4},
        },
        "per_seed": results,
        "aggregate": aggregate_result,
    }
    (OUT / "safety_pareto_ablation_results.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    fields = [
        "seed", "method", "policy", "t_c", "t_b", "accuracy", "macro_f1",
        "balanced_accuracy", "c_recall", "c_underestimate", "c_to_a", "c_to_b",
        "safe_loss", "a_overestimate", "escalation_rate", "review_rate", "ideal_distance",
    ]
    with (OUT / "safety_pareto_ablation_summary.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in selected_rows + fixed_rows:
            writer.writerow({key: row.get(key, "") for key in fields})

    front_fields = fields + ["is_selected"]
    with (OUT / "safety_pareto_front.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=front_fields)
        writer.writeheader()
        for row in all_front_rows:
            writer.writerow({key: row.get(key, "") for key in front_fields})

    print(json.dumps({"aggregate": aggregate_result, "selected": selected_rows}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
