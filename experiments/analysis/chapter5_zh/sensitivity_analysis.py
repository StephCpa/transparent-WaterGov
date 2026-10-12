"""Sensitivity of the delivered rule chain to the short-board coefficient and to single indicators (2026-10-12).

Uses the unchanged delivered code in data/875_benchmark/3_样本生成与参考规则/ and writes
sensitivity_analysis.json next to this file.

1. alpha: the 875 controlled records (generate_dataset() with the delivered seed) are evaluated
   with the short-board coefficient alpha = 0, 0.05, ..., 1 (barrier strength 0.5).  For each
   alpha: mean score, grade counts before and after the gates, accuracy of the rule grade
   against the reference grade (safe/slight A, moderate B, severe/critical C) and C->A count.
   alpha = 0.45 must reproduce the delivered rule-chain result (739 of 875 correct).
2. one_at_a_time: starting from the delivered base section (all qualitative indicators good,
   no leakage evidence), each indicator is moved over its full range with the others held:
   seepage ratios R of C1, C4, C5 from 0 to 1.2, back/front slope FoS from 1.70/1.60 to 0.90,
   crest elevation from design flood level + 2.8 m to design flood level - 0.5 m, and every
   qualitative indicator from 100 to 0 points.  The score range (pre-gate) and the grades
   reached (after gates) are recorded.

Run from the repository root:
    python3 experiments/analysis/chapter5_zh/sensitivity_analysis.py
"""

from __future__ import annotations

import copy
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "data" / "875_benchmark" / "3_样本生成与参考规则"))
sys.dont_write_bytecode = True

import failure_response_barrier_model as M  # noqa: E402  (delivered code, unchanged)
import synthetic_dataset_evaluation as G  # noqa: E402

REF = {"safe": "A", "slight": "A", "moderate": "B", "severe": "C", "critical": "C"}
SHORT = {"A级_安全": "A", "B级_基本安全": "B", "C级_不安全": "C"}
QUAL = ["A4", "A6", "A7", "A8", "A9", "B2", "B3", "B4", "C2", "C6", "D4", "D5", "E1", "E2", "E3", "E4", "E5"]


def alpha_sweep() -> list:
    samples, geo, bld, hist = G.generate_dataset()
    out = []
    for k in range(21):
        a = round(k * 0.05, 2)
        res = [(M.evaluate_section(copy.deepcopy(s), geo, bld, hist, leak, alpha=a), REF[s["synthetic_severity"]])
               for s, leak in samples]
        final = [SHORT[r["安全等级"]] for r, _ in res]
        raw = [SHORT[r["模型原始等级"]] for r, _ in res]
        ref = [y for _, y in res]
        out.append({"alpha": a, "mean_score": round(sum(r["安全得分"] for r, _ in res) / len(res), 2),
                    "raw_counts": dict(Counter(raw)), "final_counts": dict(Counter(final)),
                    "raw_correct": sum(p == y for p, y in zip(raw, ref)),
                    "final_correct": sum(p == y for p, y in zip(final, ref)),
                    "C_to_A": sum(p == "A" and y == "C" for p, y in zip(final, ref)),
                    "A_to_B_or_C": sum(p != "A" and y == "A" for p, y in zip(final, ref))})
    assert next(o for o in out if o["alpha"] == 0.45)["final_correct"] == 739
    return out


def _eval(sec, leak):
    r = M.evaluate_section(sec, [], [], [], leak)
    return r["安全得分"], SHORT[r["安全等级"]]


def one_at_a_time() -> list:
    base = G.base_section("0+001")
    leak = G.leak_evidence("safe")
    icr = (base["控制层Gs"] - 1) / (1 + base["控制层e"])
    cases = []

    def sweep(label, code, values, setter):
        scores, grades = [], []
        for v in values:
            sec = copy.deepcopy(base)
            setter(sec, v)
            s, g = _eval(sec, leak)
            scores.append(s); grades.append(g)
        cases.append({"label": label, "code": code, "score_max": round(max(scores), 2), "score_min": round(min(scores), 2),
                      "range": round(max(scores) - min(scores), 2), "grades": sorted(set(grades))})

    ratios = [k * 0.05 for k in range(25)]
    sweep("堤基坡降比", "C1", ratios, lambda s, r: s.__setitem__("渗透比降i", r * icr))
    sweep("堤身坡降比", "C4", ratios, lambda s, r: s.__setitem__("堤身渗透比降i", r * icr))
    sweep("接触面坡降比", "C5", ratios, lambda s, r: s.__setitem__("接触面渗透比降i", r * icr))
    sweep("背水坡安全系数", "D1", [1.70 - 0.02 * k for k in range(41)], lambda s, f: s.__setitem__("背水坡FoS_正常", f))
    sweep("临水坡安全系数", "D2", [1.60 - 0.02 * k for k in range(36)], lambda s, f: s.__setitem__("临水坡FoS", f))
    sweep("堤顶高程", "B1", [2.8 - 0.1 * k for k in range(34)],
          lambda s, d: s.__setitem__("堤顶高程_m", s["设计洪水位_m"] + d))
    sweep("冲刷深度", "D3", [0.1 * k for k in range(16)], lambda s, d: s.__setitem__("冲刷深度_m", d))
    for code in QUAL:
        sweep(code, code, [100, 0], lambda s, v, c=code: s["待输入指标"].__setitem__(c, v))
    base_score, base_grade = _eval(copy.deepcopy(base), leak)
    return {"base_score": round(base_score, 2), "base_grade": base_grade,
            "cases": sorted(cases, key=lambda c: -c["range"])}


def main() -> None:
    out = {"alpha": alpha_sweep(), "one_at_a_time": one_at_a_time()}
    (HERE / "sensitivity_analysis.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for o in out["alpha"]:
        print(o["alpha"], o["mean_score"], o["final_correct"], o["raw_correct"], o["C_to_A"], o["A_to_B_or_C"], o["final_counts"])
    print("base", out["one_at_a_time"]["base_score"], out["one_at_a_time"]["base_grade"])
    for c in out["one_at_a_time"]["cases"]:
        print(c)


if __name__ == "__main__":
    main()
