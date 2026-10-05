"""Supplementary statistics for the English manuscript (revision of 2026-10-05).

The script re-runs the grouped five-fold out-of-fold (OOF) random-forest
pipeline on the original 875-record batch with the *unchanged* model code from
``ml_baseline与多目标/run_ml_baselines.py``.  The class and function
definitions are extracted from that file with ``ast`` so that its top-level
training and file-writing side effects are not executed.

It then computes quantities that were not stored by the original scripts:

* per-record OOF predictions for the rule chain, RF policies and hybrids;
* the decomposition of hybrid changes relative to the rule and the RF policy;
* error-set complementarity between the rule chain and the RF threshold policy;
* the C-only versus ordinal (B/C) physical-floor ablation;
* an inspection-channel ablation of the learned layer;
* exact McNemar tests and a grouped paired bootstrap for hybrid versus rule;
* per-target-mode accuracy and C-class underestimates;
* a Clopper--Pearson bound for the 0/9 reviewed field candidates.

All paths are resolved relative to the repository, so the script runs from a
fresh clone with Python >= 3.10 and NumPy.  Outputs are written next to this
file and never overwrite the authoritative benchmark package.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
DATA_CSV = REPO / "data" / "875_benchmark" / "2_合成样本" / "synthetic_evaluation_dataset.csv"
ERROR_TRACE = REPO / "experiments" / "analysis" / "875基线分析" / "136条误分类溯源.csv"
MODEL_SRC = REPO / "experiments" / "analysis" / "ml_baseline与多目标" / "run_ml_baselines.py"
SEED_DIR = REPO / "experiments" / "analysis" / "875多种子稳健性"
SEEDS = [20260930, 20260931, 20260932, 20260933, 20260934]

RAW_FEATURES = [
    "top_elevation_m", "seepage_i", "body_i", "contact_i", "fos_back",
    "fos_front", "scour_depth_m", "uav_density", "uav_level",
]
FEATURES = RAW_FEATURES + [
    "seepage_ratio", "body_ratio", "contact_ratio", "inv_fos_back", "scour_ratio",
]
INSPECTION_FEATURES = {"uav_density", "uav_level"}
GRADES = "ABC"


def load_model_code() -> dict:
    """Return the DecisionTree/RandomForest/metrics definitions without side effects."""
    tree = ast.parse(MODEL_SRC.read_text(encoding="utf-8"))
    keep = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom, ast.ClassDef, ast.FunctionDef))]
    namespace: dict = {}
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(MODEL_SRC), "exec"), namespace)
    return namespace


NS = load_model_code()
RandomForest = NS["RandomForest"]
metrics = NS["metrics"]


def make_x(rows: list[dict]) -> np.ndarray:
    x0 = np.array([[float(r[k]) for k in RAW_FEATURES] for r in rows], dtype=float)
    return np.column_stack([x0, x0[:, 1] / 0.25, x0[:, 2] / 0.25, x0[:, 3] / 0.25, 1.0 / x0[:, 4], x0[:, 6] / 1.0])


def group_ids(x: np.ndarray) -> list[str]:
    return [hashlib.sha1(np.asarray(row, dtype=np.float64).tobytes()).hexdigest() for row in x]


def grouped_folds(groups: list[str]) -> np.ndarray:
    unique = sorted(set(groups))
    mapping = {g: i % 5 for i, g in enumerate(unique)}
    return np.array([mapping[g] for g in groups], dtype=int)


def target_class(severity: str) -> int:
    return 0 if severity in {"safe", "slight"} else 1 if severity == "moderate" else 2


def grade_class(grade: str) -> int:
    return GRADES.index(grade[0])


def oof_proba(x: np.ndarray, y: np.ndarray, fold: np.ndarray, columns: list[int] | None = None) -> np.ndarray:
    cols = columns if columns is not None else list(range(x.shape[1]))
    mf = min(4, len(cols))
    proba = np.zeros((len(y), 3), dtype=float)
    for f in range(5):
        tr, te = fold != f, fold == f
        model = RandomForest(n_estimators=120, max_depth=7, min_samples_leaf=3, max_features=mf, seed=20260929 + f)
        model.fit(x[tr][:, cols], y[tr])
        proba[te] = model.predict_proba(x[te][:, cols])
    return proba


def threshold(proba: np.ndarray, tc: float = 0.35, tb: float = 0.20) -> np.ndarray:
    return np.where(proba[:, 2] >= tc, 2, np.where(proba[:, 1] >= tb, 1, 0))


def extended(y: np.ndarray, pred: np.ndarray) -> dict:
    m = metrics(y, pred)
    cm = np.asarray(m["cm"])
    m.update({
        "c_to_a": int(cm[2, 0]), "c_to_b": int(cm[2, 1]),
        "safe_loss": int(2 * cm[2, 0] + cm[2, 1]),
        "a_overestimate": int(cm[0, 1] + cm[0, 2]),
        "escalation_rate": float(np.mean(pred == 2)),
    })
    return m


def mcnemar_exact(y: np.ndarray, a: np.ndarray, b: np.ndarray) -> dict:
    """Two-sided exact McNemar test on correctness of paired predictions."""
    ca, cb = a == y, b == y
    n01 = int(np.sum(ca & ~cb))  # a right, b wrong
    n10 = int(np.sum(~ca & cb))  # a wrong, b right
    n = n01 + n10
    k = min(n01, n10)
    p = min(1.0, 2.0 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0
    return {"a_only_correct": n01, "b_only_correct": n10, "p_two_sided": p}


def grouped_bootstrap(y, preds: dict, groups, n_boot=2000, seed=20261005) -> dict:
    """Paired bootstrap over feature-vector groups for hybrid-minus-rule differences."""
    rng = np.random.default_rng(seed)
    uniq = sorted(set(groups))
    index = {g: [] for g in uniq}
    for i, g in enumerate(groups):
        index[g].append(i)
    members = [np.array(index[g]) for g in uniq]
    stats = {"accuracy": [], "macro_f1": [], "c_recall": [], "safe_loss": []}
    for _ in range(n_boot):
        pick = rng.integers(0, len(uniq), len(uniq))
        idx = np.concatenate([members[j] for j in pick])
        h = extended(y[idx], preds["hybrid"][idx])
        r = extended(y[idx], preds["rule"][idx])
        for key in stats:
            stats[key].append(h[key] - r[key])
    out = {}
    for key, vals in stats.items():
        vals = np.asarray(vals, dtype=float)
        out[key] = {"mean": float(vals.mean()), "ci95": [float(np.quantile(vals, 0.025)), float(np.quantile(vals, 0.975))]}
    out["n_boot"] = n_boot
    out["n_groups"] = len(uniq)
    return out


def clopper_pearson_upper(k: int, n: int, alpha: float) -> float:
    """One-sided upper bound for a binomial proportion with k=0 (closed form)."""
    if k != 0:
        raise ValueError("closed form implemented only for k = 0")
    return 1.0 - alpha ** (1.0 / n)


def analyse_batch(rows: list[dict], y: np.ndarray, rule: np.ndarray, with_channel_ablation: bool) -> tuple[dict, dict, np.ndarray]:
    x = make_x(rows)
    groups = group_ids(x)
    fold = grouped_folds(groups)
    proba = oof_proba(x, y, fold)
    rf_major = np.argmax(proba, axis=1)
    rf_thr = threshold(proba)
    hybrid = np.maximum(rf_thr, rule)
    c_floor = np.where(rule == 2, 2, rf_thr)
    review = hybrid.copy()
    low = np.max(proba, axis=1) < 0.50
    review[low] = rule[low]
    preds = {"rule": rule, "rf_majority": rf_major, "rf_threshold": rf_thr, "hybrid": hybrid,
             "c_only_floor": c_floor, "hybrid_review_u050": review}
    out = {name: extended(y, p) for name, p in preds.items()}
    out["review_u050_n"] = int(low.sum())
    out["n_groups"] = len(set(groups))

    rule_err, hyb_err, rf_err = rule != y, hybrid != y, rf_thr != y
    out["hybrid_vs_rule"] = {
        "rule_errors": int(rule_err.sum()), "hybrid_errors": int(hyb_err.sum()),
        "rule_errors_corrected": int(np.sum(rule_err & ~hyb_err)),
        "new_errors_introduced": int(np.sum(~rule_err & hyb_err)),
        "decisions_changed": int(np.sum(hybrid != rule)),
    }
    out["hybrid_vs_rf_threshold"] = {
        "rf_errors": int(rf_err.sum()),
        "rf_errors_corrected": int(np.sum(rf_err & ~hyb_err)),
        "new_errors_introduced": int(np.sum(~rf_err & hyb_err)),
        "decisions_changed": int(np.sum(hybrid != rf_thr)),
    }
    is_c = y == 2
    out["c_error_complementarity"] = {
        "rule_misses_c": int(np.sum(is_c & (rule < 2))),
        "rf_threshold_misses_c": int(np.sum(is_c & (rf_thr < 2))),
        "both_miss_c": int(np.sum(is_c & (rule < 2) & (rf_thr < 2))),
        "rule_c_to_a": int(np.sum(is_c & (rule == 0))),
    }
    out["mcnemar"] = {
        "hybrid_vs_rule": mcnemar_exact(y, hybrid, rule),
        "rf_threshold_vs_rule": mcnemar_exact(y, rf_thr, rule),
    }
    if with_channel_ablation:
        keep = [i for i, f in enumerate(FEATURES) if f not in INSPECTION_FEATURES]
        p_noinsp = oof_proba(x, y, fold, keep)
        thr_noinsp = threshold(p_noinsp)
        out["rf_threshold_no_inspection_features"] = extended(y, thr_noinsp)
        out["hybrid_no_inspection_features"] = extended(y, np.maximum(thr_noinsp, rule))
        out["no_inspection_threshold_decisions_changed"] = int(np.sum(thr_noinsp != rf_thr))
        out["bootstrap_hybrid_minus_rule"] = grouped_bootstrap(y, preds, groups)
    return out, preds, proba


def main() -> None:
    with DATA_CSV.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    y = np.array([target_class(r["target_severity"]) for r in rows], dtype=int)
    rule = y.copy()
    with ERROR_TRACE.open(encoding="utf-8-sig") as f:
        pos = {r["sample_id"]: i for i, r in enumerate(rows)}
        for er in csv.DictReader(f):
            rule[pos[er["sample_id"]]] = grade_class(er["grade"])

    original, preds, proba = analyse_batch(rows, y, rule, with_channel_ablation=True)

    # Reproduce the cost-weighted forests of test_cost_sensitive.py (class-weighted
    # bootstrap resampling, fold seeds 203000+f) to recover their full confusion matrices.
    x = make_x(rows)
    fold = grouped_folds(group_ids(x))
    stored = json.loads((MODEL_SRC.parent / "cost_sensitive_results.json").read_text(encoding="utf-8"))["models"]
    cost_weighted = []
    for ref in stored:
        pred = np.zeros(len(y), dtype=int)
        for f in range(5):
            tr, te = fold != f, fold == f
            model = RandomForest(n_estimators=120, max_depth=7, min_samples_leaf=3, max_features=4,
                                 seed=203000 + f, class_weight={0: 1, 1: 1, 2: ref["c_weight"]})
            model.fit(x[tr], y[tr])
            pred[te] = model.predict(x[te])
        m = extended(y, pred)
        assert abs(m["accuracy"] - ref["accuracy"]) < 1e-6 and m["c_to_a"] == ref["c_to_a"], "cost-weighted run not reproduced"
        m["c_weight"] = ref["c_weight"]
        cost_weighted.append(m)
    original["cost_weighted_rf"] = cost_weighted

    modes = sorted({r["target_mode"] for r in rows}, key=[r["target_mode"] for r in rows].index)
    by_mode = {}
    for m in modes:
        sel = np.array([r["target_mode"] == m for r in rows])
        by_mode[m] = {name: {"accuracy": float(np.mean(p[sel] == y[sel])),
                             "c_under": int(np.sum((y[sel] == 2) & (p[sel] < 2))),
                             "c_to_a": int(np.sum((y[sel] == 2) & (p[sel] == 0)))}
                      for name, p in preds.items() if name in {"rule", "rf_threshold", "hybrid"}}
    original["by_target_mode"] = by_mode

    with (HERE / "per_record_predictions_875.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sample_id", "target_mode", "target_severity", "reference", "rule", "rf_majority",
                    "rf_threshold", "hybrid", "c_only_floor", "hybrid_review_u050", "p_A", "p_B", "p_C"])
        for i, r in enumerate(rows):
            w.writerow([r["sample_id"], r["target_mode"], r["target_severity"], GRADES[y[i]]]
                       + [GRADES[preds[k][i]] for k in ("rule", "rf_majority", "rf_threshold", "hybrid", "c_only_floor", "hybrid_review_u050")]
                       + [f"{v:.4f}" for v in proba[i]])

    seeds = {}
    for s in SEEDS:
        with (SEED_DIR / f"seed_{s}" / "evaluation_dataset.csv").open(encoding="utf-8-sig") as f:
            srows = list(csv.DictReader(f))
        sy = np.array([target_class(r["target_severity"]) for r in srows], dtype=int)
        srule = np.array([grade_class(r["grade"]) for r in srows], dtype=int)
        seeds[str(s)], _, _ = analyse_batch(srows, sy, srule, with_channel_ablation=False)

    def agg(key: str, metric: str) -> dict:
        v = np.array([seeds[str(s)][key][metric] for s in SEEDS], dtype=float)
        return {"mean": float(v.mean()), "sd": float(v.std(ddof=1)), "min": float(v.min()), "max": float(v.max())}

    seed_summary = {}
    for key in ("rule", "rf_majority", "rf_threshold", "hybrid", "c_only_floor", "hybrid_review_u050"):
        seed_summary[key] = {m: agg(key, m) for m in ("accuracy", "macro_f1", "balanced_accuracy", "c_recall",
                                                     "c_underestimate", "c_to_a", "safe_loss", "a_overestimate")}
    seed_summary["both_miss_c"] = [seeds[str(s)]["c_error_complementarity"]["both_miss_c"] for s in SEEDS]
    seed_summary["hybrid_new_errors_vs_rule"] = [seeds[str(s)]["hybrid_vs_rule"]["new_errors_introduced"] for s in SEEDS]
    seed_summary["mcnemar_hybrid_vs_rule_p"] = [seeds[str(s)]["mcnemar"]["hybrid_vs_rule"]["p_two_sided"] for s in SEEDS]

    result = {
        "original_batch": original,
        "additional_seeds": seeds,
        "additional_seed_summary": seed_summary,
        "inspection_review": {
            "reviewed_field_candidates": 9, "confirmed_piping": 0,
            "candidate_precision_upper_one_sided_95": clopper_pearson_upper(0, 9, 0.05),
            "candidate_precision_upper_two_sided_95": clopper_pearson_upper(0, 9, 0.025),
        },
    }
    (HERE / "paper_statistics.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: original[k] for k in ("hybrid_vs_rule", "hybrid_vs_rf_threshold", "c_error_complementarity", "mcnemar")}, indent=1))


if __name__ == "__main__":
    main()
