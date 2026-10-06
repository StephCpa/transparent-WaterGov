"""Comparison baselines and the multi-objective evaluation system (revision of 2026-10-06).

All learners use the same 14 features, the same grouped five-fold out-of-fold
(OOF) split and no hyperparameter search; settings are fixed below before any
result is seen.  The random forest reuses the unchanged NumPy model code of
``ml_baseline与多目标/run_ml_baselines.py`` (definitions extracted with ``ast``).

Part A -- comparison baselines (original batch and five additional seeds)
  learned only : RF (majority, threshold), logistic regression (LR), ordinal LR
                 (Frank--Hall), RBF support-vector machine (SVM), gradient-boosted
                 trees (GBDT), RF with an expected-cost (Bayes) decision rule;
  rule-aware   : stacked RF with the rule grade as a feature, soft vote of RF
                 probabilities and the one-hot rule grade, confidence switch
                 (RF when max p >= 0.6, otherwise the rule grade);
  floor        : the ordinal physical floor applied to every learned-only decision.

Part B -- multi-objective evaluation system
  policy space : learner x threshold pair (0.05 grid, 0.20--0.90) x floor scope
                 {none, C-only, ordinal}, plus the rule chain itself;
  objectives   : macro-F1, balanced accuracy, C recall (maximize) and the safety
                 loss L_safe (minimize); strict Pareto dominance;
  resources    : escalation rate and A-class overestimates (reported, tie-breaks);
  constraints  : zero direct C->A decisions and C recall >= 0.95; reported both without
                 and with the physical-floor constraint (no decision below the rule grade);
  selection    : lexicographic safety-first rule (min L_safe, max balanced
                 accuracy, max macro-F1, min escalation, min A overestimates);
                 sensitivity: equal-weight distance to the ideal point;
  hypervolume  : of each family's non-dominated set in the normalized objective
                 space (macro-F1, balanced accuracy, C recall, 1 - L_safe/L_max),
                 reference point at the origin.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import sklearn
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
DATA_CSV = REPO / "data" / "875_benchmark" / "2_合成样本" / "synthetic_evaluation_dataset.csv"
ERROR_TRACE = REPO / "experiments" / "analysis" / "875基线分析" / "136条误分类溯源.csv"
MODEL_SRC = REPO / "experiments" / "analysis" / "ml_baseline与多目标" / "run_ml_baselines.py"
SEED_DIR = REPO / "experiments" / "analysis" / "875多种子稳健性"
SEEDS = [20260930, 20260931, 20260932, 20260933, 20260934]
RAW = ["top_elevation_m", "seepage_i", "body_i", "contact_i", "fos_back", "fos_front",
       "scour_depth_m", "uav_density", "uav_level"]
# Same grid construction as run_pareto_policy.py (unrounded values, so exact ties behave identically).
GRID = np.arange(0.20, 0.901, 0.05)
SCOPES = ("none", "c_only", "ordinal")
LEARNERS = ("rf", "lr", "olr", "svm", "gbdt", "rf_rule")
# Expected-cost decision: COST[true, predicted]; underestimates cost more than overestimates.
COST = np.array([[0, 1, 2], [2, 0, 1], [10, 5, 0]], dtype=float)
SWITCH_U = 0.60


def _load_model_code() -> dict:
    tree = ast.parse(MODEL_SRC.read_text(encoding="utf-8"))
    keep = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom, ast.ClassDef, ast.FunctionDef))]
    ns: dict = {}
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(MODEL_SRC), "exec"), ns)
    return ns


NS = _load_model_code()
RandomForest = NS["RandomForest"]


def make_x(rows):
    x0 = np.array([[float(r[k]) for k in RAW] for r in rows], dtype=float)
    return np.column_stack([x0, x0[:, 1] / 0.25, x0[:, 2] / 0.25, x0[:, 3] / 0.25, 1.0 / x0[:, 4], x0[:, 6] / 1.0])


def folds_of(x):
    g = [hashlib.sha1(np.asarray(r, dtype=np.float64).tobytes()).hexdigest() for r in x]
    m = {k: i % 5 for i, k in enumerate(sorted(set(g)))}
    return np.array([m[k] for k in g], dtype=int)


def target_class(s):
    return 0 if s in {"safe", "slight"} else 1 if s == "moderate" else 2


def grade_class(g):
    return "ABC".index(g[0])


# ----------------------------------------------------------------- metrics
def confusion(y, p):
    cm = np.zeros((3, 3), dtype=int)
    np.add.at(cm, (y, p), 1)
    return cm


def summarize(y, p, rule=None) -> dict:
    cm = confusion(y, p)
    rec, f1 = [], []
    for c in range(3):
        tp = cm[c, c]; fn = cm[c].sum() - tp; fp = cm[:, c].sum() - tp
        r = tp / (tp + fn) if tp + fn else 0.0
        q = tp / (tp + fp) if tp + fp else 0.0
        rec.append(r); f1.append(2 * q * r / (q + r) if q + r else 0.0)
    return {
        "accuracy": float(np.trace(cm) / len(y)), "macro_f1": float(np.mean(f1)),
        "balanced_accuracy": float(np.mean(rec)), "c_recall": float(rec[2]),
        "c_to_a": int(cm[2, 0]), "c_to_b": int(cm[2, 1]), "safe_loss": int(2 * cm[2, 0] + cm[2, 1]),
        "a_over": int(cm[0, 1] + cm[0, 2]), "escalation": float(np.mean(p == 2)), "cm": cm.tolist(),
        # decisions below the physics-based grade, and how many of them match the reference class
        "below_rule": int(np.sum(p < rule)) if rule is not None else 0,
        "below_rule_correct": int(np.sum((p < rule) & (p == y))) if rule is not None else 0,
    }


def vs_rule(y, p, rule) -> dict:
    pe, re_ = p != y, rule != y
    return {"rule_errors_corrected": int(np.sum(re_ & ~pe)), "new_errors": int(np.sum(~re_ & pe))}


# ----------------------------------------------------------------- learners
def oof_proba(name: str, x, y, fold, rule) -> np.ndarray:
    proba = np.zeros((len(y), 3))
    for f in range(5):
        tr, te = fold != f, fold == f
        if name in ("rf", "rf_rule"):
            xx = x if name == "rf" else np.column_stack([x, rule])
            m = RandomForest(n_estimators=120, max_depth=7, min_samples_leaf=3, max_features=4, seed=20260929 + f)
            m.fit(xx[tr], y[tr]); proba[te] = m.predict_proba(xx[te])
        elif name == "lr":
            m = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=5000))
            m.fit(x[tr], y[tr]); proba[te] = m.predict_proba(x[te])
        elif name == "olr":  # Frank--Hall: P(y > A) and P(y > B) from two binary models
            cum = []
            for k in (0, 1):
                m = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=5000))
                m.fit(x[tr], (y[tr] > k).astype(int)); cum.append(m.predict_proba(x[te])[:, 1])
            p = np.column_stack([1 - cum[0], cum[0] - cum[1], cum[1]])
            p = np.clip(p, 0, None); proba[te] = p / p.sum(1, keepdims=True)
        elif name == "svm":
            svc = SVC(C=1.0, kernel="rbf", gamma="scale", random_state=20260929 + f)
            m = make_pipeline(StandardScaler(), CalibratedClassifierCV(svc, method="sigmoid", cv=5, ensemble=False))
            m.fit(x[tr], y[tr]); proba[te] = m.predict_proba(x[te])
        elif name == "gbdt":
            m = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, early_stopping=False, random_state=20260929 + f)
            m.fit(x[tr], y[tr]); proba[te] = m.predict_proba(x[te])
        else:
            raise ValueError(name)
    return proba


def threshold(p, tc, tb):
    return np.where(p[:, 2] >= tc, 2, np.where(p[:, 1] >= tb, 1, 0))


def apply_scope(pred, rule, scope):
    if scope == "none":
        return pred
    if scope == "c_only":
        return np.where(rule == 2, 2, pred)
    return np.maximum(pred, rule)


def argmax_high(p):
    """argmax with ties resolved towards the higher-risk class."""
    return 2 - np.argmax(p[:, ::-1], axis=1)


# ----------------------------------------------------------------- Pareto machinery
OBJ = ("macro_f1", "balanced_accuracy", "c_recall")


def objective_matrix(cands, n_c):
    return np.array([[c[k] for k in OBJ] + [1 - c["safe_loss"] / (2 * n_c)] for c in cands])


def strict_front(F: np.ndarray) -> np.ndarray:
    keep = np.ones(len(F), dtype=bool)
    for i in range(len(F)):
        ge = (F >= F[i]).all(1); gt = (F > F[i]).any(1)
        if (ge & gt).any():
            keep[i] = False
    return keep


def hypervolume(P: np.ndarray, ref: np.ndarray) -> float:
    P = P[(P > ref).all(1)]
    if len(P) == 0:
        return 0.0
    if P.shape[1] == 1:
        return float(P.max() - ref[0])
    P = P[np.argsort(-P[:, -1])]
    vol = 0.0
    for i in range(len(P)):
        top = P[i, -1]; bottom = P[i + 1, -1] if i + 1 < len(P) else ref[-1]
        if top > bottom:
            sub = np.unique(P[: i + 1, :-1], axis=0)
            vol += hypervolume(sub, ref[:-1]) * (top - bottom)
    return float(vol)


def lexi_key(c):
    return (c["safe_loss"], -c["balanced_accuracy"], -c["macro_f1"], c["escalation"], c["a_over"],
            -c.get("t_c", 0), -c.get("t_b", 0))


def knee(cands, n_c=350):
    F = objective_matrix(cands, n_c)
    lo, hi = F.min(0), F.max(0)
    span = np.where(hi - lo > 1e-12, hi - lo, 1.0)
    d = np.sqrt((((hi - F) / span) ** 2).sum(1))
    order = sorted(range(len(cands)), key=lambda i: (round(d[i], 12),) + lexi_key(cands[i]))
    return cands[order[0]]


def label(c):
    if c["learner"] == "rule":
        return "rule chain"
    return f"{c['learner']}|{c['scope']}|({c['t_c']:.2f},{c['t_b']:.2f})"


# ----------------------------------------------------------------- batch analysis
def analyse(rows, y, rule, keep_cloud=False, probes=()):
    x = make_x(rows); fold = folds_of(x); n_c = int(np.sum(y == 2))
    P = {n: oof_proba(n, x, y, fold, rule) for n in LEARNERS}

    # Part A: baselines
    base = {}
    base["rule"] = summarize(y, rule)
    rf_thr = threshold(P["rf"], 0.35, 0.20)
    named = {
        "rf_majority": np.argmax(P["rf"], 1),
        "rf_threshold": rf_thr,
        "lr": np.argmax(P["lr"], 1), "olr": np.argmax(P["olr"], 1), "svm": np.argmax(P["svm"], 1),
        "gbdt": np.argmax(P["gbdt"], 1),
        "rf_expected_cost": np.argmin(P["rf"] @ COST, axis=1),
        "rf_rule_stacked": np.argmax(P["rf_rule"], 1),
        "soft_vote": argmax_high((P["rf"] + np.eye(3)[rule]) / 2),
        "confidence_switch": np.where(P["rf"].max(1) >= SWITCH_U, rf_thr, rule),
    }
    for k in ("rf_threshold", "lr", "olr", "svm", "gbdt", "rf_expected_cost", "rf_rule_stacked"):
        named[f"{k}+floor"] = np.maximum(named[k], rule)
    for k, p in named.items():
        base[k] = summarize(y, p, rule); base[k].update(vs_rule(y, p, rule))
    if "target_mode" in rows[0]:
        st = named["rf_rule_stacked"]
        modes = np.array([r["target_mode"] for r in rows])
        base["rf_rule_stacked_below_rule_by_mode"] = {m: int(np.sum((st < rule) & (modes == m))) for m in sorted(set(modes))}
    base["rf_p_c_max_through_structure"] = None

    # Part B: policy space
    cands = [{"learner": "rule", "scope": "none", **summarize(y, rule, rule)}]
    for n in LEARNERS:
        for tc in GRID:
            for tb in GRID:
                raw = threshold(P[n], tc, tb)
                for s in SCOPES:
                    c = summarize(y, apply_scope(raw, rule, s), rule)
                    c.update({"learner": n, "scope": s, "t_c": round(float(tc), 2), "t_b": round(float(tb), 2)})
                    cands.append(c)
    F = objective_matrix(cands, n_c)
    on_front = strict_front(F)
    feasible = np.array([c["c_to_a"] == 0 and c["c_recall"] >= 0.95 for c in cands])
    feas_front_idx = np.where(feasible)[0][strict_front(F[feasible])] if feasible.any() else np.array([], int)
    feas_front = [cands[i] for i in feas_front_idx]
    selected = min(feas_front, key=lexi_key) if feas_front else None
    selected_knee = knee(feas_front) if feas_front else None
    # physical-floor constraint: no decision below the rule grade
    mono = feasible & np.array([c["below_rule"] == 0 for c in cands])
    mono_front_idx = np.where(mono)[0][strict_front(F[mono])] if mono.any() else np.array([], int)
    mono_front = [cands[i] for i in mono_front_idx]
    selected_mono = min(mono_front, key=lexi_key) if mono_front else None
    selected_mono_knee = knee(mono_front) if mono_front else None
    # rf | ordinal at the declared operating point (the floor hybrid of the paper)
    declared = next(c for c in cands if c["learner"] == "rf" and c["scope"] == "ordinal" and c["t_c"] == 0.35 and c["t_b"] == 0.20)
    declared_on_front = bool(on_front[cands.index(declared)])

    fam = {}
    ref = np.zeros(4)
    hv_rule = hypervolume(F[:1], ref)
    for n in LEARNERS:
        for s in SCOPES:
            idx = [i for i, c in enumerate(cands) if c["learner"] == n and c["scope"] == s]
            Fi = F[idx]; fi = strict_front(Fi)
            dom_rule = bool(((Fi >= F[0]).all(1) & (Fi > F[0]).any(1)).any())
            fam[f"{n}|{s}"] = {
                "hypervolume": hypervolume(np.unique(Fi[fi], axis=0), ref),
                "n_feasible": int(feasible[idx].sum()),
                "n_on_global_front": int(on_front[idx].sum()),
                "dominates_rule_chain": dom_rule,
                "min_c_to_a": int(min(cands[i]["c_to_a"] for i in idx)),
            }
    front_counts = {}
    for i in np.where(on_front)[0]:
        key = "rule" if cands[i]["learner"] == "rule" else f"{cands[i]['learner']}|{cands[i]['scope']}"
        front_counts[key] = front_counts.get(key, 0) + 1
    pareto = {
        "n_candidates": len(cands), "n_feasible": int(feasible.sum()),
        "n_global_front": int(on_front.sum()), "global_front_by_family": front_counts,
        "n_feasible_front": len(feas_front),
        "feasible_front_by_family": {k: sum(1 for c in feas_front if f"{c['learner']}|{c['scope']}" == k)
                                     for k in sorted({f"{c['learner']}|{c['scope']}" for c in feas_front})},
        "hv_rule_chain": hv_rule, "families": fam,
        "selected_lexicographic": {k: v for k, v in selected.items() if k != "cm"} | {"label": label(selected)} if selected else None,
        "selected_knee": {k: v for k, v in selected_knee.items() if k != "cm"} | {"label": label(selected_knee)} if selected_knee else None,
        "declared_rf_ordinal_on_global_front": declared_on_front,
        "n_floor_feasible": int(mono.sum()), "n_floor_front": len(mono_front),
        "floor_front_by_family": {k: sum(1 for c in mono_front if f"{c['learner']}|{c['scope']}" == k)
                                  for k in sorted({f"{c['learner']}|{c['scope']}" for c in mono_front})},
        "selected_floor_constrained": ({k: v for k, v in selected_mono.items() if k != "cm"} | {"label": label(selected_mono)}) if selected_mono else None,
        "selected_floor_constrained_knee": ({k: v for k, v in selected_mono_knee.items() if k != "cm"} | {"label": label(selected_mono_knee)}) if selected_mono_knee else None,
        "declared_rf_ordinal_on_floor_front": bool(cands.index(declared) in set(mono_front_idx.tolist())),
    }
    # transfer test: policies fixed elsewhere (e.g. selected on the original batch) evaluated here unchanged
    pareto["probes"] = {}
    for spec in probes:
        hit = next(c for c in cands if c["learner"] == spec["learner"] and c["scope"] == spec["scope"]
                   and c.get("t_c") == spec.get("t_c") and c.get("t_b") == spec.get("t_b"))
        pareto["probes"][label(hit)] = {k: v for k, v in hit.items() if k != "cm"}
    cloud = None
    if keep_cloud:
        cloud = [{"learner": c["learner"], "scope": c["scope"], "t_c": c.get("t_c"), "t_b": c.get("t_b"),
                  "macro_f1": c["macro_f1"], "balanced_accuracy": c["balanced_accuracy"], "c_recall": c["c_recall"],
                  "safe_loss": c["safe_loss"], "c_to_a": c["c_to_a"], "escalation": c["escalation"], "a_over": c["a_over"],
                  "below_rule": c["below_rule"], "on_front": bool(on_front[i]), "feasible": bool(feasible[i]),
                  "floor_feasible": bool(mono[i]), "on_floor_front": bool(i in set(mono_front_idx.tolist()))} for i, c in enumerate(cands)]
    # diagnostic: probability mass the forest gives to C on the through-structure records
    if "target_mode" in rows[0]:
        sel = np.array([r["target_mode"] == "building" for r in rows])
        base["rf_p_c_max_through_structure"] = float(P["rf"][sel, 2].max())
        base["gbdt_p_c_max_through_structure"] = float(P["gbdt"][sel, 2].max())
    return base, pareto, cloud


def main():
    with DATA_CSV.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    y = np.array([target_class(r["target_severity"]) for r in rows])
    rule = y.copy()
    pos = {r["sample_id"]: i for i, r in enumerate(rows)}
    with ERROR_TRACE.open(encoding="utf-8-sig") as f:
        for er in csv.DictReader(f):
            rule[pos[er["sample_id"]]] = grade_class(er["grade"])
    out = {"versions": {"numpy": np.__version__, "scikit_learn": sklearn.__version__},
           "settings": {"grid": np.round(GRID, 2).tolist(), "scopes": SCOPES, "learners": LEARNERS, "cost_matrix": COST.tolist(),
                        "switch_u": SWITCH_U, "feasibility": "c_to_a == 0 and c_recall >= 0.95",
                        "selection": "lexicographic: min safe_loss, max balanced_accuracy, max macro_f1, min escalation, min a_over"}}
    base, pareto, cloud = analyse(rows, y, rule, keep_cloud=True)
    out["original"] = {"baselines": base, "pareto": pareto}
    with (HERE / "policy_cloud_875.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(cloud[0])); w.writeheader(); w.writerows(cloud)
    out["seeds"] = {}
    for s in SEEDS:
        with (SEED_DIR / f"seed_{s}" / "evaluation_dataset.csv").open(encoding="utf-8-sig") as f:
            srows = list(csv.DictReader(f))
        sy = np.array([target_class(r["target_severity"]) for r in srows])
        srule = np.array([grade_class(r["grade"]) for r in srows])
        probes = [pareto["selected_lexicographic"], pareto["selected_floor_constrained"],
                  {"learner": "rf", "scope": "ordinal", "t_c": 0.35, "t_b": 0.2}]
        b, p, _ = analyse(srows, sy, srule, probes=probes)
        out["seeds"][str(s)] = {"baselines": b, "pareto": p}
        print("seed", s, "done", p["selected_lexicographic"]["label"], "| floor-constrained:", p["selected_floor_constrained"]["label"], flush=True)
    (HERE / "baselines_and_pareto.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print("original selected:", pareto["selected_lexicographic"]["label"], "| knee:", pareto["selected_knee"]["label"],
          "| floor-constrained:", pareto["selected_floor_constrained"]["label"], "| knee:", pareto["selected_floor_constrained_knee"]["label"])


if __name__ == "__main__":
    main()
