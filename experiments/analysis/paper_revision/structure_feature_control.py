"""Control experiment: does the physical floor still add value when the random forest
is given the through-dike structure (穿堤建筑物) state?

Background.  The 14 RF features of Chapter 5 contain no structure information, while the
rule chain scores the four structure indicators A3 (穿堤建筑物完好性), B4 (穿堤建筑物防洪标准),
C6 (穿堤建筑物渗流稳定) and D4 (穿堤结构安全系数).  Part of the gain of the physical floor
max(RF, rule) could therefore be a missing-feature effect rather than an effect of the
floor itself.  This script separates the two.

Design (fixed before any result was seen):
  * data: the original 875-record batch (generator seed 20260616) and the five additional
    generator seeds of ``875多种子稳健性``; every batch is regenerated with the unchanged
    generator so that the structure inputs are available (the published CSVs omit them);
    the regenerated 14 features and rule grades are checked against the published CSVs;
  * feature sets: F14 = the 14 features of Chapter 5; F18 = F14 + the scores of A3, B4, C6, D4
    exactly as the rule chain receives them (A3 from the structure inspection class);
  * split G (grouped): the grouped five-fold OOF split of Chapter 5, computed on F14 so that
    both feature sets use identical folds.  All 125 structure-scenario records share one F14
    vector (their physical inputs are the base section), so under G the structure scenario is
    never seen in training: it tests transfer to an unseen failure pattern;
  * split R (record-level, added after the first G result to separate "missing feature" from
    "unseen pattern"): stratified five-fold split over records (seed 20260929).  Identical
    input vectors can fall into training and test, so R is an optimistic bound, not a
    performance estimate;
  * learner: the unchanged NumPy random forest (120 trees, depth 7, leaf 3, max_features 4);
  * decisions: majority vote and the threshold decision (tau_C, tau_B) = (0.35, 0.20), each
    without and with the physical floor max(RF, rule).
"""

from __future__ import annotations

import contextlib
import csv
import io
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from baselines_and_pareto import (  # noqa: E402
    DATA_CSV, SEED_DIR, SEEDS, RandomForest, folds_of, grade_class, make_x,
    summarize, target_class, threshold, vs_rule,
)

REPO = HERE.parents[2]
GEN_DIR = REPO / "experiments" / "analysis" / "875基线复现"  # same generator as data/supplementary/02, with the matrix JSON
sys.path.insert(0, str(GEN_DIR))
with contextlib.redirect_stdout(io.StringIO()):
    from synthetic_dataset_evaluation import RNG_SEED, evaluate_section, generate_dataset  # noqa: E402
    from safety_evaluation import score_A3  # noqa: E402

OUT_JSON = HERE / "structure_feature_control.json"
OUT_CSV = HERE / "structure_feature_control_summary.csv"
STRUCT = ("A3", "B4", "C6", "D4")
N_PER_CELL = 25
TAU_C, TAU_B = 0.35, 0.20


def regenerate(seed: int) -> tuple[list[dict], np.ndarray, np.ndarray, np.ndarray, list[str]]:
    samples, geo_cls, buildings, hist = generate_dataset(n_per_cell=N_PER_CELL, seed=seed)
    rows, struct, y, rule, modes = [], [], [], [], []
    with contextlib.redirect_stdout(io.StringIO()):
        for sec, leak in samples:
            res = evaluate_section(sec, geo_cls, buildings, hist, leak)
            rows.append({
                "sample_id": sec["桩号"], "grade": res["安全等级"],
                "top_elevation_m": sec["堤顶高程_m"], "seepage_i": sec["渗透比降i"],
                "body_i": sec["堤身渗透比降i"], "contact_i": sec["接触面渗透比降i"],
                "fos_back": sec["背水坡FoS_正常"], "fos_front": sec["临水坡FoS"],
                "scour_depth_m": sec["冲刷深度_m"], "uav_density": leak["加权渗漏点密度_点每100m"],
                "uav_level": leak["UAV证据等级"],
            })
            q = sec["待输入指标"]
            struct.append([score_A3(sec["桩号"], buildings), q.get("B4", 100), q.get("C6", 100), q.get("D4", 100)])
            y.append(target_class(sec["synthetic_severity"]))
            rule.append(grade_class(res["安全等级"]))
            modes.append(sec["synthetic_target_mode"])
    return rows, np.asarray(struct, float), np.asarray(y), np.asarray(rule), modes


def check_against(rows: list[dict], csv_path: Path) -> dict:
    with csv_path.open(encoding="utf-8-sig") as f:
        pub = list(csv.DictReader(f))
    xa, xb = make_x(rows), make_x(pub)
    return {
        "n": len(pub),
        "features_identical": bool(len(pub) == len(rows) and np.allclose(xa, xb, rtol=0, atol=1e-12)),
        "rule_grade_identical": all(a["grade"] == b["grade"] for a, b in zip(rows, pub)),
    }


def record_folds(y, seed: int = 20260929) -> np.ndarray:
    rng = np.random.default_rng(seed)
    fold = np.empty(len(y), dtype=int)
    for c in np.unique(y):
        idx = rng.permutation(np.flatnonzero(y == c))
        fold[idx] = np.arange(len(idx)) % 5
    return fold


def oof_rf(x, y, fold) -> np.ndarray:
    proba = np.zeros((len(y), 3))
    for f in range(5):
        tr, te = fold != f, fold == f
        m = RandomForest(n_estimators=120, max_depth=7, min_samples_leaf=3, max_features=4, seed=20260929 + f)
        m.fit(x[tr], y[tr])
        proba[te] = m.predict_proba(x[te])
    return proba


def evaluate(y, rule, modes, proba) -> dict:
    out = {}
    decisions = {
        "majority": np.argmax(proba, axis=1),
        "threshold": threshold(proba, TAU_C, TAU_B),
    }
    building = np.array([m == "building" for m in modes])
    for name, pred in decisions.items():
        for floor in (False, True):
            p = np.maximum(pred, rule) if floor else pred
            key = f"{name}{'+floor' if floor else ''}"
            r = summarize(y, p, rule)
            r.update(vs_rule(y, p, rule))
            # how much the floor changes this decision, and whether those changes are correct
            changed = p != pred
            r["floor_changes"] = int(changed.sum())
            r["floor_changes_correct"] = int(np.sum(changed & (p == y)))
            r["floor_changes_wrong"] = int(np.sum(changed & (p != y) & (pred == y)))
            yb, pb = y[building], p[building]
            r["building"] = {
                "n": int(building.sum()),
                "accuracy": float(np.mean(yb == pb)),
                "c_recall": float(np.mean(pb[yb == 2] == 2)),
                "c_to_a": int(np.sum((yb == 2) & (pb == 0))),
                "c_to_b": int(np.sum((yb == 2) & (pb == 1))),
            }
            out[key] = r
    return out


def run_batch(seed: int, csv_path: Path) -> dict:
    rows, struct, y, rule, modes = regenerate(seed)
    check = check_against(rows, csv_path)
    x14 = make_x(rows)
    x18 = np.column_stack([x14, struct])
    folds = {"G": folds_of(x14), "R": record_folds(y)}
    res = {"seed": seed, "check": check, "rule": summarize(y, rule, rule)}
    b = np.array(modes) == "building"
    res["rule"]["building"] = {"accuracy": float(np.mean(y[b] == rule[b])),
                               "c_recall": float(np.mean(rule[b & (y == 2)] == 2))}
    for split, fold in folds.items():
        for tag, x in (("F14", x14), ("F18", x18)):
            res[f"{split}/{tag}"] = evaluate(y, rule, modes, oof_rf(x, y, fold))
    return res


METRICS = ("accuracy", "macro_f1", "balanced_accuracy", "c_recall", "c_to_a", "c_to_b", "safe_loss",
           "a_over", "escalation", "below_rule", "rule_errors_corrected", "new_errors",
           "floor_changes", "floor_changes_correct", "floor_changes_wrong")
VARIANTS = [(f"{sp}/{fs}", d) for sp in ("G", "R") for fs in ("F14", "F18")
            for d in ("majority", "majority+floor", "threshold", "threshold+floor")]


def main() -> None:
    batches = [run_batch(RNG_SEED, DATA_CSV)]
    batches += [run_batch(s, SEED_DIR / f"seed_{s}" / "evaluation_dataset.csv") for s in SEEDS]
    agg = {}
    for fs, d in VARIANTS:
        key = f"{fs}/{d}"
        vals = {m: [b[fs][d][m] for b in batches] for m in METRICS}
        vals["building_c_recall"] = [b[fs][d]["building"]["c_recall"] for b in batches]
        vals["building_c_to_a"] = [b[fs][d]["building"]["c_to_a"] for b in batches]
        agg[key] = {
            "original": {m: v[0] for m, v in vals.items()},
            "seeds_mean": {m: float(np.mean(v[1:])) for m, v in vals.items()},
            "seeds_sd": {m: float(np.std(v[1:], ddof=1)) for m, v in vals.items()},
            "seeds_min": {m: float(np.min(v[1:])) for m, v in vals.items()},
            "seeds_max": {m: float(np.max(v[1:])) for m, v in vals.items()},
        }
    rule_vals = {m: [b["rule"][m] for b in batches] for m in ("accuracy", "macro_f1", "balanced_accuracy", "c_recall", "c_to_a", "safe_loss")}
    agg["rule"] = {"original": {m: v[0] for m, v in rule_vals.items()},
                   "seeds_mean": {m: float(np.mean(v[1:])) for m, v in rule_vals.items()}}
    OUT_JSON.write_text(json.dumps({"batches": batches, "aggregate": agg}, ensure_ascii=False, indent=2), encoding="utf-8")
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["variant", "batch"] + list(METRICS) + ["building_c_recall", "building_c_to_a"])
        for fs, d in VARIANTS:
            for b in batches:
                r = b[fs][d]
                w.writerow([f"{fs}/{d}", b["seed"]] + [r[m] for m in METRICS] + [r["building"]["c_recall"], r["building"]["c_to_a"]])
    for b in batches:
        print(b["seed"], b["check"])
    for k, v in agg.items():
        o, s = v["original"], v["seeds_mean"]
        print(f"{k:28s} acc {o['accuracy']:.3f}/{s['accuracy']:.3f}  C->A {o['c_to_a']}/{s['c_to_a']:.1f}  "
              f"Lsafe {o['safe_loss']}/{s['safe_loss']:.1f}"
              + (f"  bldgCrec {o['building_c_recall']:.2f}/{s['building_c_recall']:.2f}  fl+ {o['floor_changes_correct']} fl- {o['floor_changes_wrong']}"
                 if "building_c_recall" in o else ""))


if __name__ == "__main__":
    main()
