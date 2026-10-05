# -*- coding: utf-8 -*-
"""
Failure-response and safety-barrier coupled levee safety assessment.

This module is intentionally independent from the cloud-model entry points.
It reuses the existing indicator quantification functions, then reorganizes
the results into failure-mode responses:

    guideline indicators -> failure-mode responses -> safety-barrier adjustment
    -> shortboard-constrained system risk metric -> safety grade

Missing optional indicators remain missing. The model does not fill project
data; it only evaluates indicators that are present or computable.
"""

from __future__ import annotations

import json
import csv
from pathlib import Path

from safety_evaluation import (
    FREEBOARD_LAKE,
    FREEBOARD_RIVER,
    FOS_BACK_ALLOW,
    FOS_FRONT_ALLOW,
    SETTLE_ALLOW,
    SETTLE_DIFF_ALLOW,
    front_slope_fos,
    W1_A,
    W1_B,
    W1_C,
    W1_D,
    W1_E,
    W2_A,
    W2_B,
    W2_C,
    W2_D,
    W2_E,
    controlling_soil_layer,
    load_json,
    match_leak_points,
    match_uav_leakage_evidence,
    optional_indicator_score,
    score_A1,
    score_A2,
    score_A3,
    score_A5,
    score_A6,
    score_A7,
    score_B1,
    score_C1,
    score_C3,
    score_C4,
    score_C5,
    score_D1,
    score_D2,
    score_D3,
    score_from_optional_or_calculated,
    seepage_risk_ratio_terzaghi,
)


FAILURE_MODES = ("漫顶失效", "渗流破坏", "边坡失稳", "冲刷破坏", "穿堤建筑物失效")

GUIDELINE_WEIGHTS = {
    **{code: W1_A * weight for code, weight in W2_A.items()},
    **{code: W1_B * weight for code, weight in W2_B.items()},
    **{code: W1_C * weight for code, weight in W2_C.items()},
    **{code: W1_D * weight for code, weight in W2_D.items()},
    **{code: W1_E * weight for code, weight in W2_E.items()},
}


def load_failure_mode_matrix(path=None):
    if path is None:
        path = Path(__file__).with_name("failure_mode_indicator_matrix.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["indicators"]


def derive_failure_mode_weights(matrix_rows=None):
    """Derive mode and within-mode weights from the guideline-constrained matrix.

    Association strength uses 0, 1, 2, 3:
    0 = no direct relation, 1 = indirect, 2 = important, 3 = direct control.
    The weight contribution is guideline_weight * association_strength.
    """
    matrix_rows = matrix_rows or load_failure_mode_matrix()
    raw_mode_weights = {mode: 0.0 for mode in FAILURE_MODES}
    raw_indicator_weights = {mode: {} for mode in FAILURE_MODES}

    for row in matrix_rows:
        code = row["code"]
        guideline_weight = GUIDELINE_WEIGHTS.get(code, 0.0)
        for mode in FAILURE_MODES:
            strength = float(row.get("modes", {}).get(mode, 0.0))
            contribution = guideline_weight * strength
            if contribution <= 0:
                continue
            raw_mode_weights[mode] += contribution
            raw_indicator_weights[mode][code] = contribution

    mode_total = sum(raw_mode_weights.values())
    mode_weights = {
        mode: raw_mode_weights[mode] / mode_total
        for mode in FAILURE_MODES
        if raw_mode_weights[mode] > 0 and mode_total > 0
    }

    indicator_weights = {}
    for mode, items in raw_indicator_weights.items():
        total = sum(items.values())
        indicator_weights[mode] = {
            code: contribution / total
            for code, contribution in items.items()
            if total > 0
        }

    return mode_weights, indicator_weights


MODE_WEIGHTS, MODE_INDICATOR_WEIGHTS = derive_failure_mode_weights()


def clamp01(value):
    return max(0.0, min(1.0, float(value)))


def score_to_response(score):
    """Convert a 0-100 safety score to a 0-1 risk response."""
    if score is None:
        return None
    return clamp01(1.0 - float(score) / 100.0)


def weighted_available(items):
    """Weighted average over present risk responses."""
    present = [(v, w) for v, w in items if v is not None]
    if not present:
        return None
    total = sum(w for _, w in present)
    if total <= 0:
        return None
    return sum(v * w for v, w in present) / total


def mode_weighted_response(mode, scores, overrides=None):
    """Weighted risk response for one failure mode from the matrix-derived weights."""
    overrides = overrides or {}
    items = []
    for code, weight in MODE_INDICATOR_WEIGHTS.get(mode, {}).items():
        if code in overrides:
            response = overrides[code]
        else:
            response = score_to_response(scores.get(code))
        items.append((response, weight))
    return weighted_available(items)


def mode_contribution_overrides(sec):
    """Physical response overrides used for contribution decomposition.

    These keep diagnostic contributions consistent with the mode-response
    functions: B1 uses freeboard deficit, C1/C4/C5 use Terzaghi risk ratios,
    and D1/D2 use safety-factor margins.
    """
    fb = FREEBOARD_LAKE if sec["是否为湖堤"] else FREEBOARD_RIVER
    required = sec["设计洪水位_m"] + fb
    deficit = max(0.0, required - sec["堤顶高程_m"])
    freeboard_response = clamp01(deficit / fb) if fb > 0 else None

    ctrl = controlling_soil_layer(sec)
    raw_base = seepage_risk_ratio_terzaghi(sec["渗透比降i"], ctrl["Gs"], ctrl["e"])

    i_body = sec.get("堤身渗透比降i", 0.0)
    body_gs = sec.get("堤身Gs", ctrl["Gs"])
    body_e = sec.get("堤身e", ctrl["e"])
    raw_body = seepage_risk_ratio_terzaghi(i_body, body_gs, body_e)

    i_contact = sec.get("接触面渗透比降i", 0.0)
    raw_contact = seepage_risk_ratio_terzaghi(i_contact, ctrl["Gs"], ctrl["e"])

    fos_back = float(sec["背水坡FoS_正常"])
    fos_front = front_slope_fos(sec)
    back = 1.0 if fos_back < 1.0 else clamp01((FOS_BACK_ALLOW - fos_back) / (FOS_BACK_ALLOW - 1.0))
    front = 1.0 if fos_front < 1.0 else clamp01((FOS_FRONT_ALLOW - fos_front) / (FOS_FRONT_ALLOW - 1.0))

    return {
        "漫顶失效": {"B1": freeboard_response},
        "渗流破坏": {"C1": clamp01(raw_base), "C4": clamp01(raw_body), "C5": clamp01(raw_contact)},
        "边坡失稳": {"D1": back, "D2": front},
    }


def indicator_contributions_for_mode(mode, scores, overrides=None):
    """Return indicator contribution list for one failure mode.

    contribution = mode_internal_weight * indicator_risk_response
    contribution_rate = contribution / sum(contribution)
    """
    overrides = overrides or {}
    rows = []
    total = 0.0

    for code, weight in MODE_INDICATOR_WEIGHTS.get(mode, {}).items():
        if code in overrides:
            response = overrides[code]
            response_source = "物理响应"
        else:
            response = score_to_response(scores.get(code))
            response_source = "指标得分"

        if response is None:
            rows.append(
                {
                    "指标": code,
                    "指标得分": None,
                    "风险响应": None,
                    "模式内权重": round(weight, 6),
                    "贡献值": None,
                    "贡献率": None,
                    "来源": response_source,
                }
            )
            continue

        contribution = weight * response
        total += contribution
        rows.append(
            {
                "指标": code,
                "指标得分": round(scores.get(code), 4) if isinstance(scores.get(code), (int, float)) else scores.get(code),
                "风险响应": round(response, 6),
                "模式内权重": round(weight, 6),
                "贡献值": round(contribution, 6),
                "贡献率": None,
                "来源": response_source,
            }
        )

    for row in rows:
        contribution = row["贡献值"]
        if contribution is None or total <= 0:
            row["贡献率"] = None
        else:
            row["贡献率"] = round(contribution / total, 6)

    return sorted(
        rows,
        key=lambda x: -1.0 if x["贡献值"] is None else x["贡献值"],
        reverse=True,
    )


def all_mode_contributions(scores, overrides_by_mode):
    return {
        mode: indicator_contributions_for_mode(
            mode,
            scores,
            overrides=overrides_by_mode.get(mode, {}),
        )
        for mode in FAILURE_MODES
    }


def score_dict(sec, stake, geo_cls, buildings, hist_dangers, leak_n):
    """Compute the same indicator scores as the current guideline layer."""
    return {
        "A1": score_A1(sec),
        "A2": score_A2(stake, geo_cls),
        "A3": score_A3(stake, buildings),
        "A4": optional_indicator_score(sec, "A4"),
        "A5": score_A5(sec),
        "A6": optional_indicator_score(sec, "A6")
        if optional_indicator_score(sec, "A6") is not None
        else score_A6(stake, hist_dangers),
        "A7": optional_indicator_score(sec, "A7")
        if optional_indicator_score(sec, "A7") is not None
        else score_A7(sec),
        "A8": optional_indicator_score(sec, "A8"),
        "A9": optional_indicator_score(sec, "A9"),
        "B1": score_B1(sec),
        "B2": score_from_optional_or_calculated(sec, "B2"),
        "B3": score_from_optional_or_calculated(sec, "B3"),
        "B4": score_from_optional_or_calculated(sec, "B4"),
        "C1": score_C1(sec),
        "C2": optional_indicator_score(sec, "C2"),
        "C3": score_C3(leak_n),
        "C4": score_C4(sec),
        "C5": score_C5(sec),
        "C6": optional_indicator_score(sec, "C6"),
        "D1": score_D1(sec),
        "D2": score_D2(sec),
        "D3": score_D3(sec, hist_dangers),
        "D4": score_from_optional_or_calculated(sec, "D4"),
        "D5": optional_indicator_score(sec, "D5"),
        "E1": optional_indicator_score(sec, "E1"),
        "E2": optional_indicator_score(sec, "E2"),
        "E3": optional_indicator_score(sec, "E3"),
        "E4": optional_indicator_score(sec, "E4"),
        "E5": optional_indicator_score(sec, "E5"),
    }


def overtopping_response(sec, scores):
    fb = FREEBOARD_LAKE if sec["是否为湖堤"] else FREEBOARD_RIVER
    required = sec["设计洪水位_m"] + fb
    deficit = max(0.0, required - sec["堤顶高程_m"])
    # Deficit equal to the whole freeboard is treated as critical.
    freeboard_response = clamp01(deficit / fb) if fb > 0 else score_to_response(scores["B1"])
    if freeboard_response >= 1.0:
        return 1.0
    return mode_weighted_response("漫顶失效", scores, overrides={"B1": freeboard_response})


def seepage_response(sec, scores):
    ctrl = controlling_soil_layer(sec)
    raw_base = seepage_risk_ratio_terzaghi(sec["渗透比降i"], ctrl["Gs"], ctrl["e"])
    r_base = clamp01(raw_base)

    i_body = sec.get("堤身渗透比降i", 0.0)
    body_gs = sec.get("堤身Gs", ctrl["Gs"])
    body_e = sec.get("堤身e", ctrl["e"])
    raw_body = seepage_risk_ratio_terzaghi(i_body, body_gs, body_e)
    r_body = clamp01(raw_body)

    i_contact = sec.get("接触面渗透比降i", 0.0)
    raw_contact = seepage_risk_ratio_terzaghi(i_contact, ctrl["Gs"], ctrl["e"])
    r_contact = clamp01(raw_contact)

    if max(raw_base, raw_body, raw_contact) >= 1.0:
        return 1.0

    return mode_weighted_response(
        "渗流破坏",
        scores,
        overrides={"C1": r_base, "C4": r_body, "C5": r_contact},
    )


def slope_response(sec, scores):
    fos_back = float(sec["背水坡FoS_正常"])
    fos_front = front_slope_fos(sec)
    if fos_back < 1.0 or fos_front < 1.0:
        return 1.0
    back = clamp01((FOS_BACK_ALLOW - fos_back) / (FOS_BACK_ALLOW - 1.0))
    front = clamp01((FOS_FRONT_ALLOW - fos_front) / (FOS_FRONT_ALLOW - 1.0))
    return mode_weighted_response(
        "边坡失稳",
        scores,
        overrides={"D1": back, "D2": front},
    )


def scour_response(scores):
    return mode_weighted_response("冲刷破坏", scores)


def building_response(scores):
    return mode_weighted_response("穿堤建筑物失效", scores)


def management_barrier(scores):
    """Return (safety-barrier ability Bm, information coverage).

    Missing management indicators are not filled. Coverage scales the barrier
    correction so that one supplied E indicator cannot represent the whole
    management barrier.
    """
    present = [(scores.get(k), W2_E[k]) for k in W2_E if scores.get(k) is not None]
    if not present:
        return None, 0.0
    total = sum(w for _, w in present)
    full_total = sum(W2_E.values())
    ability = sum(float(score) / 100.0 * w for score, w in present) / total
    coverage = total / full_total if full_total > 0 else 0.0
    return ability, coverage


def apply_barrier(raw_modes, barrier_ability, barrier_coverage=1.0, barrier_lambda=0.5):
    """Management barrier adjusts only present physical failure-mode responses."""
    if barrier_ability is None:
        return dict(raw_modes)
    effective_lambda = barrier_lambda * barrier_coverage
    adjusted = {}
    for mode, value in raw_modes.items():
        if value is None:
            adjusted[mode] = None
            continue
        # Poorer barrier amplifies intermediate risks most; zero and critical
        # risks are kept anchored.
        adjusted[mode] = clamp01(value + effective_lambda * value * (1.0 - value) * (1.0 - barrier_ability))
    return adjusted


def shortboard_constrained_metric(mode_responses, alpha=0.45):
    present = [(mode, value) for mode, value in mode_responses.items() if value is not None]
    if not present:
        return None
    available_weights = {mode: MODE_WEIGHTS[mode] for mode, _ in present}
    total_w = sum(available_weights.values())
    weighted = sum(value * available_weights[mode] / total_w for mode, value in present)
    shortboard = max(value for _, value in present)
    return clamp01(alpha * shortboard + (1.0 - alpha) * weighted)


def grade_from_score(score):
    if score >= 80:
        return "A级_安全"
    if score >= 40:
        return "B级_基本安全"
    return "C级_不安全"


def cap_grade_by_uav(grade, uav_cap):
    if uav_cap is None:
        return grade
    order = {"A级_安全": 0, "B级_基本安全": 1, "C级_不安全": 2}
    if order.get(grade, 2) < order.get(uav_cap, 2):
        return uav_cap
    return grade


def hard_constraint_gate(sec, scores, grade):
    """Apply downward-only caps for guideline hard constraints.

    The failure-mode matrix explains which failure mode is controlling, while
    this gate prevents critical single-item limit states from being averaged
    away by otherwise normal indicators.
    """
    order = {"A级_安全": 0, "B级_基本安全": 1, "C级_不安全": 2}
    cap = None
    reasons = []

    def apply_cap(target, reason):
        nonlocal cap
        if cap is None or order[target] > order[cap]:
            cap = target
        reasons.append(reason)

    fb = FREEBOARD_LAKE if sec["是否为湖堤"] else FREEBOARD_RIVER
    required = sec["设计洪水位_m"] + fb
    freeboard_deficit = required - sec["堤顶高程_m"]
    if freeboard_deficit > 0:
        ratio = freeboard_deficit / fb if fb > 0 else 1.0
        if sec["堤顶高程_m"] < sec["设计洪水位_m"] or ratio >= 0.5:
            apply_cap("C级_不安全", f"B1堤顶高程严重不足: 超高亏欠{freeboard_deficit:.2f}m")
        else:
            apply_cap("B级_基本安全", f"B1堤顶高程不足: 超高亏欠{freeboard_deficit:.2f}m")

    ctrl = controlling_soil_layer(sec)
    seepage_checks = [
        ("C1堤基渗透比降", seepage_risk_ratio_terzaghi(sec["渗透比降i"], ctrl["Gs"], ctrl["e"])),
        (
            "C4堤身渗流稳定",
            seepage_risk_ratio_terzaghi(
                sec.get("堤身渗透比降i", 0.0),
                sec.get("堤身Gs", ctrl["Gs"]),
                sec.get("堤身e", ctrl["e"]),
            ),
        ),
        (
            "C5接触冲刷稳定",
            seepage_risk_ratio_terzaghi(sec.get("接触面渗透比降i", 0.0), ctrl["Gs"], ctrl["e"]),
        ),
    ]
    for label, ratio in seepage_checks:
        if ratio >= 1.0:
            apply_cap("C级_不安全", f"{label}: i/i_cr={ratio:.2f}达到临界")
        elif ratio >= 0.8:
            apply_cap("B级_基本安全", f"{label}: i/i_cr={ratio:.2f}接近临界")

    fos_back = float(sec["背水坡FoS_正常"])
    fos_front = front_slope_fos(sec)
    if fos_back < 1.05:
        apply_cap("C级_不安全", f"D1背水坡FoS={fos_back:.2f}<1.05")
    elif fos_back < FOS_BACK_ALLOW:
        apply_cap("B级_基本安全", f"D1背水坡FoS={fos_back:.2f}<允许值{FOS_BACK_ALLOW:.2f}")
    if fos_front < 1.05:
        apply_cap("C级_不安全", f"D2临水坡FoS={fos_front:.2f}<1.05")
    elif fos_front < FOS_FRONT_ALLOW:
        apply_cap("B级_基本安全", f"D2临水坡FoS={fos_front:.2f}<允许值{FOS_FRONT_ALLOW:.2f}")

    scour = sec.get("冲刷深度_m")
    if scores.get("D3") == 0:
        apply_cap("C级_不安全", f"D3冲刷深度={scour:.2f}m达到严重冲刷" if scour is not None else "D3存在严重冲刷")
    elif scores.get("D3") is not None and scores.get("D3") <= 70:
        apply_cap("B级_基本安全", f"D3冲刷深度={scour:.2f}m存在冲刷风险" if scour is not None else "D3存在冲刷风险")

    for code, label in [
        ("A3", "穿堤建筑物完好性"),
        ("B4", "穿堤建筑物防洪标准"),
        ("C6", "穿堤建筑物渗流稳定"),
        ("D4", "穿堤建筑物结构安全"),
    ]:
        value = scores.get(code)
        if value == 0:
            apply_cap("C级_不安全", f"{code}{label}为失效状态")
        elif value is not None and value <= 60:
            apply_cap("B级_基本安全", f"{code}{label}处于不利状态")

    settlement = sec.get("软基段_沉降量_cm")
    settlement_diff = sec.get("软基段_沉降差_cm")
    if settlement is not None:
        if settlement > SETTLE_ALLOW * 1.5 or settlement_diff > SETTLE_DIFF_ALLOW * 1.5:
            apply_cap("C级_不安全", f"A5软基沉降严重超限: {settlement:.1f}cm/{settlement_diff:.1f}cm")
        elif settlement > SETTLE_ALLOW or settlement_diff > SETTLE_DIFF_ALLOW:
            apply_cap("B级_基本安全", f"A5软基沉降超限: {settlement:.1f}cm/{settlement_diff:.1f}cm")

    if cap is not None and order.get(grade, 2) < order[cap]:
        return cap, reasons
    return grade, reasons


def evaluate_section(sec, geo_cls, buildings, hist_dangers, leak_n, alpha=0.45, barrier_lambda=0.5):
    stake = sec["桩号"]
    scores = score_dict(sec, stake, geo_cls, buildings, hist_dangers, leak_n)
    contribution_overrides = mode_contribution_overrides(sec)
    raw_modes = {
        "漫顶失效": overtopping_response(sec, scores),
        "渗流破坏": seepage_response(sec, scores),
        "边坡失稳": slope_response(sec, scores),
        "冲刷破坏": scour_response(scores),
        "穿堤建筑物失效": building_response(scores),
    }
    barrier, barrier_coverage = management_barrier(scores)
    adjusted_modes = apply_barrier(raw_modes, barrier, barrier_coverage, barrier_lambda=barrier_lambda)
    rho = shortboard_constrained_metric(adjusted_modes, alpha=alpha)
    score = 100.0 * (1.0 - rho) if rho is not None else None
    model_grade = grade_from_score(score) if score is not None else "无法评价"

    uav_cap = leak_n.get("UAV门控等级上限") if isinstance(leak_n, dict) else None
    uav_note = leak_n.get("UAV门控说明") if isinstance(leak_n, dict) else None
    uav_capped_grade = cap_grade_by_uav(model_grade, uav_cap)
    final_grade, gate_reasons = hard_constraint_gate(sec, scores, uav_capped_grade)
    main_mode = None
    if adjusted_modes:
        present = {k: v for k, v in adjusted_modes.items() if v is not None}
        if present:
            main_mode = max(present, key=present.get)

    contributions = all_mode_contributions(scores, contribution_overrides)

    return {
        "桩号": stake,
        "安全得分": round(score, 4) if score is not None else None,
        "安全等级": final_grade,
        "模型原始等级": model_grade,
        "UAV门控后等级": uav_capped_grade,
        "硬约束门控原因": gate_reasons,
        "综合风险度量rho": round(rho, 6) if rho is not None else None,
        "主控失效模式": main_mode,
        "管理屏障能力": round(barrier, 6) if barrier is not None else None,
        "管理信息覆盖度": round(barrier_coverage, 6),
        "UAV渗漏观测证据": leak_n if isinstance(leak_n, dict) else None,
        "UAV观测门控上限": uav_cap,
        "UAV观测门控说明": uav_note,
        "原始失效响应": {k: round(v, 6) if v is not None else None for k, v in raw_modes.items()},
        "屏障修正响应": {k: round(v, 6) if v is not None else None for k, v in adjusted_modes.items()},
        "主控模式指标贡献率": contributions.get(main_mode, []) if main_mode is not None else [],
        "全部失效模式指标贡献率": contributions,
        "缺失指标": [k for k, v in scores.items() if v is None],
        "二级指标得分": {k: round(v, 4) if isinstance(v, float) else v for k, v in scores.items()},
    }


def run_failure_response_barrier_model(data_dir=None, alpha=0.45, barrier_lambda=0.5):
    if data_dir is None:
        data_dir = Path(__file__).parent
    data_dir = Path(data_dir)

    section_data = load_json(data_dir / "section_data.json")
    leak_points = load_json(data_dir / "leak_points.json")
    section_gps = load_json(data_dir / "section_gps.json")
    geo_cls = load_json(data_dir / "geo_classification.json")
    buildings = load_json(data_dir / "buildings_safety.json")
    hist_dangers = load_json(data_dir / "historical_dangers.json")

    leak_count = match_leak_points(leak_points, section_gps)
    uav_evidence = match_uav_leakage_evidence(leak_points, section_gps)
    print("渗漏计数:", leak_count)
    print("UAV渗漏证据:", {k: {"点数": v["渗漏点数"], "密度": v["加权渗漏点密度_点每100m"], "等级": v["UAV证据等级"]} for k, v in uav_evidence.items()})

    results = []
    for sec in section_data:
        result = evaluate_section(
            sec,
            geo_cls,
            buildings,
            hist_dangers,
            uav_evidence.get(sec["桩号"], {"渗漏点数": leak_count.get(sec["桩号"], 0)}),
            alpha=alpha,
            barrier_lambda=barrier_lambda,
        )
        results.append(result)
        print(
            f"[{result['桩号']}] 得分={result['安全得分']:.2f}  "
            f"等级={result['安全等级']}  主控={result['主控失效模式']}  "
            f"rho={result['综合风险度量rho']:.3f}"
        )

    out_path = data_dir / "final_results_failure_response_barrier.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    contribution_path = data_dir / "final_results_failure_mode_contributions.csv"
    with open(contribution_path, "w", encoding="utf-8-sig", newline="") as f:
        fieldnames = [
            "桩号",
            "安全得分",
            "安全等级",
            "主控失效模式",
            "指标",
            "指标得分",
            "风险响应",
            "模式内权重",
            "贡献值",
            "贡献率",
            "来源",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            for item in result["主控模式指标贡献率"]:
                writer.writerow(
                    {
                        "桩号": result["桩号"],
                        "安全得分": result["安全得分"],
                        "安全等级": result["安全等级"],
                        "主控失效模式": result["主控失效模式"],
                        **item,
                    }
                )
    print(f"\n评价完成，结果已保存到: {out_path}")
    print(f"主控模式贡献率已保存到: {contribution_path}")
    return results


if __name__ == "__main__":
    run_failure_response_barrier_model()
