# -*- coding: utf-8 -*-
"""Sensitivity analysis for qualitative indicator scoring rules.

This script does not fill project data as real observations. It creates
hypothetical scoring-rule scenarios to test whether qualitative score anchors
such as 70, 60 and 40 materially change the final safety grade.
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from copy import deepcopy
from pathlib import Path


SAFE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SAFE_DIR))

from failure_response_barrier_model import evaluate_section, load_json, match_leak_points  # noqa: E402


K_STAKE = "\u6869\u53f7"
K_OPTIONAL = "\u5f85\u8f93\u5165\u6307\u6807"

R_SCORE = "\u5b89\u5168\u5f97\u5206"
R_GRADE = "\u5b89\u5168\u7b49\u7ea7"
R_RHO = "\u7efc\u5408\u98ce\u9669\u5ea6\u91cfrho"
R_MAIN_MODE = "\u4e3b\u63a7\u5931\u6548\u6a21\u5f0f"
R_BARRIER = "\u7ba1\u7406\u5c4f\u969c\u80fd\u529b"


QUALITATIVE_INDICATORS = (
    "A4",
    "A6",
    "A7",
    "A8",
    "A9",
    "B2",
    "B3",
    "B4",
    "C2",
    "C6",
    "D4",
    "D5",
)

MANAGEMENT_INDICATORS = ("E1", "E2", "E3", "E4", "E5")

# Mid-state scores following the current qualitative quantification table.
# These are scenario anchors, not project observations.
NOMINAL_QUALITATIVE_PROFILE = {
    "A4": 60,
    "A6": 60,
    "A7": 70,
    "A8": 70,
    "A9": 70,
    "B2": 60,
    "B3": 70,
    "B4": 60,
    "C2": 70,
    "C6": 60,
    "D4": 60,
    "D5": 40,
}

NOMINAL_MANAGEMENT_PROFILE = {
    "E1": 80,
    "E2": 70,
    "E3": 70,
    "E4": 70,
    "E5": 60,
}

SCORING_SCHEMES = {
    "strict_minus20": -20,
    "conservative_minus10": -10,
    "nominal": 0,
    "optimistic_plus10": 10,
    "relaxed_plus20": 20,
}

OAT_SCORE_GRID = (0, 40, 50, 60, 70, 80, 100)


def load_context(data_dir=SAFE_DIR):
    data_dir = Path(data_dir)
    section_data = load_json(data_dir / "section_data.json")
    leak_points = load_json(data_dir / "leak_points.json")
    section_gps = load_json(data_dir / "section_gps.json")
    geo_cls = load_json(data_dir / "geo_classification.json")
    buildings = load_json(data_dir / "buildings_safety.json")
    hist_dangers = load_json(data_dir / "historical_dangers.json")
    leak_count = match_leak_points(leak_points, section_gps)
    return section_data, geo_cls, buildings, hist_dangers, leak_count


def clamp_score(value):
    return max(0.0, min(100.0, float(value)))


def shifted_profile(profile, shift):
    return {code: clamp_score(score + shift) for code, score in profile.items()}


def with_optional_scores(sec, scores):
    out = deepcopy(sec)
    optional = dict(out.get(K_OPTIONAL, {}))
    optional.update(scores)
    out[K_OPTIONAL] = optional
    return out


def evaluate(sec, context):
    _, geo_cls, buildings, hist_dangers, leak_count = context
    return evaluate_section(
        sec,
        geo_cls,
        buildings,
        hist_dangers,
        leak_count.get(sec[K_STAKE], 0),
    )


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def scheme_sensitivity(context):
    section_data = context[0]
    rows = []
    for sec in section_data:
        baseline = evaluate(sec, context)
        nominal_qual = evaluate(
            with_optional_scores(sec, NOMINAL_QUALITATIVE_PROFILE),
            context,
        )
        nominal_mgmt = evaluate(
            with_optional_scores(sec, NOMINAL_MANAGEMENT_PROFILE),
            context,
        )
        nominal_combined = evaluate(
            with_optional_scores(sec, {**NOMINAL_QUALITATIVE_PROFILE, **NOMINAL_MANAGEMENT_PROFILE}),
            context,
        )
        anchors = {
            "project_missing_optional": baseline,
            "qualitative_only_nominal": nominal_qual,
            "management_only_nominal": nominal_mgmt,
            "combined_nominal": nominal_combined,
        }

        rows.extend(
            {
                "stake": sec[K_STAKE],
                "scenario_group": group,
                "scoring_scheme": "anchor",
                "score": result[R_SCORE],
                "score_change_from_anchor": 0.0,
                "grade": result[R_GRADE],
                "grade_changed": False,
                "rho": result[R_RHO],
                "dominant_mode": result[R_MAIN_MODE],
                "barrier_ability": "" if result[R_BARRIER] is None else result[R_BARRIER],
            }
            for group, result in anchors.items()
        )

        for scheme, shift in SCORING_SCHEMES.items():
            qualitative = shifted_profile(NOMINAL_QUALITATIVE_PROFILE, shift)
            management = shifted_profile(NOMINAL_MANAGEMENT_PROFILE, shift)
            scenarios = {
                "qualitative_only": qualitative,
                "management_only": management,
                "combined": {**qualitative, **management},
            }
            nominal_refs = {
                "qualitative_only": nominal_qual,
                "management_only": nominal_mgmt,
                "combined": nominal_combined,
            }
            for group, optional_scores in scenarios.items():
                result = evaluate(with_optional_scores(sec, optional_scores), context)
                ref = nominal_refs[group]
                rows.append(
                    {
                        "stake": sec[K_STAKE],
                        "scenario_group": group,
                        "scoring_scheme": scheme,
                        "score": result[R_SCORE],
                        "score_change_from_anchor": round(result[R_SCORE] - ref[R_SCORE], 6),
                        "grade": result[R_GRADE],
                        "grade_changed": result[R_GRADE] != ref[R_GRADE],
                        "rho": result[R_RHO],
                        "dominant_mode": result[R_MAIN_MODE],
                        "barrier_ability": "" if result[R_BARRIER] is None else result[R_BARRIER],
                    }
                )
    return rows


def indicator_oat_sensitivity(context):
    section_data = context[0]
    rows = []
    for sec in section_data:
        baseline = evaluate(sec, context)
        for code in QUALITATIVE_INDICATORS + MANAGEMENT_INDICATORS:
            for score in OAT_SCORE_GRID:
                result = evaluate(with_optional_scores(sec, {code: score}), context)
                rows.append(
                    {
                        "stake": sec[K_STAKE],
                        "indicator": code,
                        "input_score": score,
                        "base_score": baseline[R_SCORE],
                        "score": result[R_SCORE],
                        "score_change": round(result[R_SCORE] - baseline[R_SCORE], 6),
                        "grade": result[R_GRADE],
                        "grade_changed_from_missing": result[R_GRADE] != baseline[R_GRADE],
                        "dominant_mode": result[R_MAIN_MODE],
                        "barrier_ability": "" if result[R_BARRIER] is None else result[R_BARRIER],
                    }
                )
    return rows


def range_summary(rows, group_keys, score_key="score"):
    grouped = defaultdict(list)
    grades = defaultdict(set)
    modes = defaultdict(set)
    for row in rows:
        key = tuple(row[k] for k in group_keys)
        grouped[key].append(float(row[score_key]))
        grades[key].add(row["grade"])
        modes[key].add(row["dominant_mode"])

    summary = []
    for key, values in grouped.items():
        item = dict(zip(group_keys, key))
        item.update(
            {
                "min_score": round(min(values), 4),
                "max_score": round(max(values), 4),
                "score_range": round(max(values) - min(values), 4),
                "grades": "/".join(sorted(grades[key])),
                "dominant_modes": "/".join(sorted(modes[key])),
            }
        )
        summary.append(item)
    return sorted(summary, key=lambda x: x["score_range"], reverse=True)


def build_summary(scheme_rows, oat_rows, out_path):
    scheme_core = [
        row
        for row in scheme_rows
        if row["scenario_group"] in {"qualitative_only", "management_only", "combined"}
    ]
    scheme_ranges = range_summary(scheme_core, ["stake", "scenario_group"])
    oat_ranges = range_summary(oat_rows, ["stake", "indicator"])

    lines = [
        "# 定性指标赋分敏感性分析结果",
        "",
        "## 1. 分析目的",
        "",
        "本分析用于检验定性指标中 70、60、40 等锚定分值变化时，综合安全等级和主控失效模式是否稳定。分析过程不将这些情景值作为工程实测输入，仅用于检验赋分规则稳健性。",
        "",
        "## 2. 赋分规则扰动",
        "",
        "以当前定性赋分表中的中间状态作为名义值，并设置五种赋分方案：",
        "",
        "| 方案 | 含义 |",
        "|---|---|",
        "| strict_minus20 | 名义中间分值整体降低 20 分 |",
        "| conservative_minus10 | 名义中间分值整体降低 10 分 |",
        "| nominal | 当前赋分规则 |",
        "| optimistic_plus10 | 名义中间分值整体提高 10 分 |",
        "| relaxed_plus20 | 名义中间分值整体提高 20 分 |",
        "",
        "## 3. 整体扰动结果",
        "",
        "| 桩号 | 情景组 | 得分最小值 | 得分最大值 | 得分变化幅度 | 等级范围 | 主控模式范围 |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for item in scheme_ranges:
        lines.append(
            f"| {item['stake']} | {item['scenario_group']} | {item['min_score']:.2f} | "
            f"{item['max_score']:.2f} | {item['score_range']:.2f} | {item['grades']} | {item['dominant_modes']} |"
        )

    lines.extend(
        [
            "",
            "## 4. 单指标敏感性排序",
            "",
            "| 排名 | 桩号 | 指标 | 得分变化幅度 | 等级范围 | 主控模式范围 |",
            "|---:|---|---|---:|---|---|",
        ]
    )
    for rank, item in enumerate(oat_ranges[:20], start=1):
        lines.append(
            f"| {rank} | {item['stake']} | {item['indicator']} | {item['score_range']:.2f} | "
            f"{item['grades']} | {item['dominant_modes']} |"
        )

    grade_changes = [row for row in oat_rows if str(row["grade_changed_from_missing"]) == "True"]
    scheme_grade_changes = [row for row in scheme_core if str(row["grade_changed"]) == "True"]
    lines.extend(
        [
            "",
            "## 5. 结论",
            "",
            f"- 单指标从 0-100 变化时，发生等级变化的样本数为 {len(grade_changes)}。",
            f"- 整体赋分规则在严格、保守、名义、乐观、宽松五种方案下，发生等级变化的样本数为 {len(scheme_grade_changes)}。",
            "- 若等级变化主要集中在运行管理或穿堤建筑物等缺失指标上，说明这些指标在后续实际应用中需要独立收集资料，而不宜简单默认。",
            "- 论文中可将 70、60、40 解释为状态编码锚点，并用本敏感性分析说明中间分值扰动不会任意改变模型结论，或指出哪些指标需要重点核实。",
        ]
    )
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    out_dir = SAFE_DIR / "sensitivity_outputs"
    context = load_context(SAFE_DIR)

    scheme_rows = scheme_sensitivity(context)
    oat_rows = indicator_oat_sensitivity(context)

    write_csv(
        out_dir / "qualitative_score_scheme_sensitivity.csv",
        scheme_rows,
        [
            "stake",
            "scenario_group",
            "scoring_scheme",
            "score",
            "score_change_from_anchor",
            "grade",
            "grade_changed",
            "rho",
            "dominant_mode",
            "barrier_ability",
        ],
    )
    write_csv(
        out_dir / "qualitative_indicator_oat_sensitivity.csv",
        oat_rows,
        [
            "stake",
            "indicator",
            "input_score",
            "base_score",
            "score",
            "score_change",
            "grade",
            "grade_changed_from_missing",
            "dominant_mode",
            "barrier_ability",
        ],
    )
    build_summary(
        scheme_rows,
        oat_rows,
        out_dir / "qualitative_score_sensitivity_summary.md",
    )

    print(f"qualitative scheme rows: {len(scheme_rows)}")
    print(f"qualitative OAT rows: {len(oat_rows)}")
    print(f"outputs: {out_dir}")


if __name__ == "__main__":
    main()
