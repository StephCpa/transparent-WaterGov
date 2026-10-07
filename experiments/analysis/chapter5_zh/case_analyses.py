"""Worked examples of Chapter 5, Sec. 5.7 (2026-10-07).

Runs the unchanged delivered evaluation code and writes case_analyses.json:

1. typical_records: step-by-step values for four benchmark records (inputs, score,
   gates, rule grade, forest probabilities, ordinal-floor grade, reference grade);
2. k45500: the delivered K45+500 result reproduced from its 29 indicator scores,
   and three evidence variants (C3 treated as missing; C1 taken at the exit zone;
   exit-zone C1 with current-state evidence only);
3. inspection_injection: what the delivered C3 rules do with the field candidates
   when they are fed in without review, on benchmark record 0+001.

Inputs: data/875_benchmark (code, results, inputs), the K45+500 delivered result in
data/supplementary/06_独立工程历史案例验证, and the per-record predictions of
experiments/analysis/paper_revision. Run from the repository root.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BENCH = REPO / "data" / "875_benchmark"
sys.path.insert(0, str(BENCH / "3_样本生成与参考规则"))
sys.dont_write_bytecode = True

import failure_response_barrier_model as M  # noqa: E402  (delivered code, unchanged)
import safety_evaluation as SE  # noqa: E402
import synthetic_dataset_evaluation as G  # noqa: E402

ORDER = {"A级_安全": 0, "B级_基本安全": 1, "C级_不安全": 2}
SHORT = {"A级_安全": "A", "B级_基本安全": "B", "C级_不安全": "C"}


def typical_records() -> list[dict]:
    res = {r["桩号"]: r for r in json.loads((BENCH / "2_合成样本" / "synthetic_evaluation_results.json").read_text(encoding="utf-8"))}
    with (BENCH / "2_合成样本" / "synthetic_evaluation_dataset.csv").open(encoding="utf-8-sig") as f:
        ds = {r["sample_id"]: r for r in csv.DictReader(f)}
    with (REPO / "experiments" / "analysis" / "paper_revision" / "per_record_predictions_875.csv").open(encoding="utf-8") as f:
        pr = {r["sample_id"]: r for r in csv.DictReader(f)}
    out = []
    for mode, sev in [("seepage", "severe"), ("building", "critical"), ("safe_reference", "severe"), ("seepage", "slight")]:
        group = [sid for sid, p in pr.items() if p["target_mode"] == mode and p["target_severity"] == sev]
        outcomes = {(pr[s]["reference"], pr[s]["rule"], pr[s]["rf_threshold"], pr[s]["hybrid"]) for s in group}
        assert len(outcomes) == 1, (mode, sev, outcomes)  # every record of the cell behaves the same way
        sid = group[0]
        r, d, p = res[sid], ds[sid], pr[sid]
        out.append({
            "sample_id": sid, "target_mode": mode, "severity": sev, "records_in_cell": len(group),
            "inputs": {k: float(d[k]) for k in ["seepage_i", "body_i", "contact_i", "fos_back", "fos_front", "scour_depth_m", "uav_density"]},
            "score": r["安全得分"], "raw_grade": SHORT[r["模型原始等级"]], "uav_cap": r["UAV观测门控上限"],
            "gate_reasons": r["硬约束门控原因"], "rule_grade": SHORT[r["安全等级"]], "dominant_mode": r["主控失效模式"],
            "mode_responses": r["屏障修正响应"],
            "rf_probabilities": {c: float(p[f"p_{c}"]) for c in "ABC"}, "rf_threshold_grade": p["rf_threshold"],
            "ordinal_floor_grade": p["hybrid"], "reference": p["reference"],
        })
    return out


def _terzaghi_score(ratio: float) -> float:
    return 0.0 if ratio >= 1.0 else 100.0 * (1.0 - ratio * ratio)


def _evaluate_from_scores(scores, r1, r4, r5, fos_back, fos_front, freeboard_response):
    """Mirror evaluate_section for a case known only through its indicator scores."""
    modes = {
        "漫顶失效": M.mode_weighted_response("漫顶失效", scores, overrides={"B1": freeboard_response}),
        "渗流破坏": 1.0 if max(r1, r4, r5) >= 1.0 else M.mode_weighted_response(
            "渗流破坏", scores, overrides={"C1": r1, "C4": r4, "C5": r5}),
        "边坡失稳": M.mode_weighted_response("边坡失稳", scores, overrides={
            "D1": M.clamp01((M.FOS_BACK_ALLOW - fos_back) / (M.FOS_BACK_ALLOW - 1.0)),
            "D2": M.clamp01((M.FOS_FRONT_ALLOW - fos_front) / (M.FOS_FRONT_ALLOW - 1.0))}),
        "冲刷破坏": M.mode_weighted_response("冲刷破坏", scores),
        "穿堤建筑物失效": M.mode_weighted_response("穿堤建筑物失效", scores),
    }
    rho = M.shortboard_constrained_metric(modes, alpha=0.45)  # no E indicators: no barrier correction
    score = 100.0 * (1.0 - rho)
    raw = M.grade_from_score(score)
    gates = []
    for code, ratio in [("C1", r1), ("C4", r4), ("C5", r5)]:
        if ratio >= 1.0:
            gates.append((code, "C级_不安全"))
        elif ratio >= 0.8:
            gates.append((code, "B级_基本安全"))
    if fos_back < 1.05:
        gates.append(("D1", "C级_不安全"))
    elif fos_back < M.FOS_BACK_ALLOW:
        gates.append(("D1", "B级_基本安全"))
    if fos_front < 1.05:
        gates.append(("D2", "C级_不安全"))
    elif fos_front < M.FOS_FRONT_ALLOW:
        gates.append(("D2", "B级_基本安全"))
    if scores.get("D3") == 0:
        gates.append(("D3", "C级_不安全"))
    elif scores.get("D3") is not None and scores["D3"] <= 70:
        gates.append(("D3", "B级_基本安全"))
    final = raw
    for _, g in gates:
        if ORDER[g] > ORDER[final]:
            final = g
    dominant = max((k for k, v in modes.items() if v is not None), key=lambda k: modes[k])
    return {"score": round(score, 4), "raw_grade": SHORT[raw], "final_grade": SHORT[final],
            "gates": [f"{c}:{SHORT[g]}" for c, g in gates], "dominant_mode": dominant,
            "mode_responses": {k: round(v, 4) for k, v in modes.items()}}


def k45500() -> dict:
    case = json.loads((REPO / "data" / "supplementary" / "06_独立工程历史案例验证" /
                       "K45+500_历史管涌代表工况_复算结果.json").read_text(encoding="utf-8"))
    ev = case["评价模型结果"]
    layers = {x["土层"]: x for x in case["渗流计算结果"]["分层渗流稳定复核"]}
    control = case["渗流计算结果"]["控制层"]
    r1 = control["i_i_cr"]
    r4 = layers["堤身填土"]["i_i_cr"]
    r5 = case["渗流计算结果"]["堤身-堤基接触带渗透比降"] / control["临界渗透比降"]
    r1_exit = layers["Q4al+l粉细砂/砂壤土"]["i_i_cr"]
    fos_back, fos_front = case["稳定计算结果"]["背水坡FoS"], case["稳定计算结果"]["临水坡FoS"]
    freeboard = 0.0  # crest 36.30 m >= design flood level 34.04 m + 2.0 m river freeboard
    base = dict(ev["二级指标得分"])
    variants = {}
    variants["delivered"] = _evaluate_from_scores(base, r1, r4, r5, fos_back, fos_front, freeboard)
    assert abs(variants["delivered"]["score"] - ev["安全得分"]) < 1e-3, "delivered K45+500 score not reproduced"
    s = dict(base); s["C3"] = None
    variants["c3_missing"] = _evaluate_from_scores(s, r1, r4, r5, fos_back, fos_front, freeboard)
    s = dict(base); s["C1"] = _terzaghi_score(r1_exit)
    variants["c1_exit_zone"] = _evaluate_from_scores(s, r1_exit, r4, r5, fos_back, fos_front, freeboard)
    s = dict(base); s["C1"] = _terzaghi_score(r1_exit); s["C3"] = None; s["D3"] = 100.0  # scour 0.40 m < 0.5 m without the history record
    variants["c1_exit_zone_current_evidence_only"] = _evaluate_from_scores(s, r1_exit, r4, r5, fos_back, fos_front, freeboard)
    return {"ratios": {"C1_control_layer": r1, "C1_exit_zone": r1_exit, "C4": r4, "C5": r5},
            "delivered_score": ev["安全得分"], "variants": variants}


def inspection_injection() -> dict:
    samples, geo, buildings, dangers = G.generate_dataset()
    sec, leak = samples[0]
    assert sec["桩号"] == "0+001"
    base = M.evaluate_section(sec, geo, buildings, dangers, leak)
    with (REPO / "inspection" / "audit" / "检测标签逐条记录.csv").open(encoding="utf-8-sig") as f:
        conf = {Path(r["file"].replace("\\", "/")).stem: float(r["confidence"]) for r in csv.DictReader(f)
                if r["group"] == "匿名堤防现场巡检"}
    # The two reviewed false positives DJI_..._0029 and _0030 share one camera position.
    # They are placed in this record's 100 m section only to show how the delivered rules react;
    # no field position is reported.
    pair = [conf["DJI_20250828111341_0029_T"], conf["DJI_20250828111347_0030_T"]]
    gps = [{"桩号": sec["桩号"], "纬度": 0.0, "经度": 0.0}]
    points = {"渗漏点列表": [{"纬度": 0.0, "经度": 0.0, "置信度": c} for c in pair]}
    ev = SE.match_uav_leakage_evidence(points, gps)[sec["桩号"]]
    injected = M.evaluate_section(sec, geo, buildings, dangers, ev)
    return {
        "record": sec["桩号"], "confidences": pair,
        "without_candidates": {"score": base["安全得分"], "grade": SHORT[base["安全等级"]], "C3": base["二级指标得分"]["C3"]},
        "delivered_rules_with_unreviewed_candidates": {
            "weighted_density_per_100m": ev["加权渗漏点密度_点每100m"], "uav_cap": ev["UAV门控等级上限"],
            "score": injected["安全得分"], "grade": SHORT[injected["安全等级"]], "C3": injected["二级指标得分"]["C3"]},
        "evidence_state_rules": "one candidate event (two frames, same position) -> one review task; "
                                "reviewed false positive -> no change to C3 or grade",
    }


def main() -> None:
    out = {"typical_records": typical_records(), "k45500": k45500(), "inspection_injection": inspection_injection()}
    path = HERE / "case_analyses.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {path}")
    for k, v in out["k45500"]["variants"].items():
        print(k, v["score"], v["raw_grade"], v["final_grade"], v["gates"])
    print(out["inspection_injection"]["delivered_rules_with_unreviewed_candidates"])


if __name__ == "__main__":
    main()
