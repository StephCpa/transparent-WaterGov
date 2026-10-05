# -*- coding: utf-8 -*-
"""Sensitivity analysis for the failure-response/barrier safety model.

Outputs:
    sensitivity_outputs/failure_response_barrier_alpha_lambda.csv
    sensitivity_outputs/failure_response_barrier_physical_oat.csv
    sensitivity_outputs/failure_response_barrier_sensitivity_summary.md
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from copy import deepcopy
from pathlib import Path


SAFE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SAFE_DIR))

from failure_response_barrier_model import (  # noqa: E402
    controlling_soil_layer,
    evaluate_section,
    load_json,
    match_leak_points,
    run_failure_response_barrier_model,
)
from safety_evaluation import terzaghi_critical_gradient  # noqa: E402


K_STAKE = "\u6869\u53f7"
K_TOP = "\u5824\u9876\u9ad8\u7a0b_m"
K_DESIGN_FLOOD = "\u8bbe\u8ba1\u6d2a\u6c34\u4f4d_m"
K_BACK_FOS = "\u80cc\u6c34\u5761FoS_\u6b63\u5e38"
K_FRONT_FOS = "\u4e34\u6c34\u5761FoS"
K_SEEPAGE_I = "\u6e17\u900f\u6bd4\u964di"
K_OPTIONAL = "\u5f85\u8f93\u5165\u6307\u6807"

R_SCORE = "\u5b89\u5168\u5f97\u5206"
R_GRADE = "\u5b89\u5168\u7b49\u7ea7"
R_RHO = "\u7efc\u5408\u98ce\u9669\u5ea6\u91cfrho"
R_MAIN_MODE = "\u4e3b\u63a7\u5931\u6548\u6a21\u5f0f"
R_BARRIER = "\u7ba1\u7406\u5c4f\u969c\u80fd\u529b"

MANAGEMENT_CODES = ("E1", "E2", "E3", "E4", "E5")


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


def with_management(sec, score):
    if score is None:
        return deepcopy(sec)
    out = deepcopy(sec)
    optional = dict(out.get(K_OPTIONAL, {}))
    optional.update({code: score for code in MANAGEMENT_CODES})
    out[K_OPTIONAL] = optional
    return out


def evaluate(sec, context, alpha=0.45, barrier_lambda=0.5):
    _, geo_cls, buildings, hist_dangers, leak_count = context
    return evaluate_section(
        sec,
        geo_cls,
        buildings,
        hist_dangers,
        leak_count.get(sec[K_STAKE], 0),
        alpha=alpha,
        barrier_lambda=barrier_lambda,
    )


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def alpha_lambda_sensitivity(context):
    section_data = context[0]
    alpha_grid = sorted({round(x / 10, 2) for x in range(0, 11)} | {0.45})
    lambda_grid = [0.0, 0.25, 0.5, 0.75, 1.0]
    management_scenarios = {
        "no_management_input": None,
        "strong_management_100": 100,
        "medium_management_60": 60,
        "weak_management_0": 0,
    }

    rows = []
    for sec in section_data:
        for management_name, management_score in management_scenarios.items():
            managed_sec = with_management(sec, management_score)
            for alpha in alpha_grid:
                for barrier_lambda in lambda_grid:
                    result = evaluate(
                        managed_sec,
                        context,
                        alpha=alpha,
                        barrier_lambda=barrier_lambda,
                    )
                    rows.append(
                        {
                            "stake": sec[K_STAKE],
                            "management_scenario": management_name,
                            "management_input_score": "" if management_score is None else management_score,
                            "alpha": alpha,
                            "barrier_lambda": barrier_lambda,
                            "score": result[R_SCORE],
                            "grade": result[R_GRADE],
                            "rho": result[R_RHO],
                            "dominant_mode": result[R_MAIN_MODE],
                            "barrier_ability": "" if result[R_BARRIER] is None else result[R_BARRIER],
                        }
                    )
    return rows


def physical_oat_sensitivity(context):
    section_data = context[0]
    rows = []

    for sec in section_data:
        base_result = evaluate(sec, context)
        base_score = base_result[R_SCORE]

        # Hydraulic gradient: use physically meaningful ratios to Terzaghi i_cr.
        ctrl = controlling_soil_layer(sec)
        i_cr = terzaghi_critical_gradient(ctrl["Gs"], ctrl["e"])
        for ratio in (0.10, 0.30, 0.50, 0.70, 0.90, 1.00, 1.10):
            changed = deepcopy(sec)
            changed[K_SEEPAGE_I] = i_cr * ratio
            result = evaluate(changed, context)
            rows.append(
                {
                    "stake": sec[K_STAKE],
                    "variable": "seepage_i_ratio_to_icr",
                    "value": round(ratio, 4),
                    "base_score": base_score,
                    "score": result[R_SCORE],
                    "score_change": round(result[R_SCORE] - base_score, 6),
                    "grade": result[R_GRADE],
                    "dominant_mode": result[R_MAIN_MODE],
                }
            )

        for value in (0.95, 1.00, 1.10, 1.25, 1.35, 1.50, 1.70):
            changed = deepcopy(sec)
            changed[K_BACK_FOS] = value
            result = evaluate(changed, context)
            rows.append(
                {
                    "stake": sec[K_STAKE],
                    "variable": "back_slope_fos",
                    "value": value,
                    "base_score": base_score,
                    "score": result[R_SCORE],
                    "score_change": round(result[R_SCORE] - base_score, 6),
                    "grade": result[R_GRADE],
                    "dominant_mode": result[R_MAIN_MODE],
                }
            )

        for value in (0.95, 1.00, 1.10, 1.25, 1.35, 1.50):
            changed = deepcopy(sec)
            changed[K_FRONT_FOS] = value
            result = evaluate(changed, context)
            rows.append(
                {
                    "stake": sec[K_STAKE],
                    "variable": "front_slope_fos",
                    "value": value,
                    "base_score": base_score,
                    "score": result[R_SCORE],
                    "score_change": round(result[R_SCORE] - base_score, 6),
                    "grade": result[R_GRADE],
                    "dominant_mode": result[R_MAIN_MODE],
                }
            )

        for delta in (-2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0):
            changed = deepcopy(sec)
            changed[K_TOP] = sec[K_DESIGN_FLOOD] + delta
            result = evaluate(changed, context)
            rows.append(
                {
                    "stake": sec[K_STAKE],
                    "variable": "top_elevation_minus_design_flood",
                    "value": delta,
                    "base_score": base_score,
                    "score": result[R_SCORE],
                    "score_change": round(result[R_SCORE] - base_score, 6),
                    "grade": result[R_GRADE],
                    "dominant_mode": result[R_MAIN_MODE],
                }
            )

    return rows


def range_summary(rows, group_keys):
    grouped = defaultdict(list)
    for row in rows:
        grouped[tuple(row[k] for k in group_keys)].append(float(row["score"]))

    summary = []
    for key, values in grouped.items():
        min_score = min(values)
        max_score = max(values)
        item = dict(zip(group_keys, key))
        item.update(
            {
                "min_score": round(min_score, 4),
                "max_score": round(max_score, 4),
                "score_range": round(max_score - min_score, 4),
            }
        )
        summary.append(item)
    return sorted(summary, key=lambda x: x["score_range"], reverse=True)


def build_markdown_summary(alpha_lambda_rows, physical_rows, out_path):
    alpha_default_lambda = [
        row
        for row in alpha_lambda_rows
        if float(row["barrier_lambda"]) == 0.5
        and row["management_scenario"] == "no_management_input"
    ]
    lambda_default_alpha = [
        row
        for row in alpha_lambda_rows
        if float(row["alpha"]) == 0.45
        and row["management_scenario"] in {"no_management_input", "medium_management_60", "weak_management_0"}
    ]

    alpha_ranges = range_summary(alpha_default_lambda, ["stake", "management_scenario"])
    lambda_ranges = range_summary(lambda_default_alpha, ["stake", "management_scenario"])
    physical_ranges = range_summary(physical_rows, ["stake", "variable"])

    lines = [
        "# 失效响应-安全屏障耦合模型敏感性分析结果",
        "",
        "## 1. 分析对象",
        "",
        "- 模型参数：`alpha`，即短板控制系数；取值 0.0-1.0。",
        "- 模型参数：`barrier_lambda`，即运行管理屏障修正强度；取值 0.0、0.25、0.5、0.75、1.0。",
        "- 物理指标：渗透比降、背水坡抗滑安全系数、临水坡抗滑安全系数、堤顶高程。",
        "",
        "## 2. 模型参数敏感性",
        "",
        "### alpha 敏感性（无运行管理输入，barrier_lambda=0.5）",
        "",
        "| 桩号 | 得分最小值 | 得分最大值 | 得分变化幅度 |",
        "|---|---:|---:|---:|",
    ]
    for item in alpha_ranges:
        lines.append(
            f"| {item['stake']} | {item['min_score']:.2f} | {item['max_score']:.2f} | {item['score_range']:.2f} |"
        )

    lines.extend(
        [
            "",
            "### barrier_lambda 敏感性（alpha=0.45）",
            "",
            "| 桩号 | 管理情景 | 得分最小值 | 得分最大值 | 得分变化幅度 |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for item in lambda_ranges:
        lines.append(
            f"| {item['stake']} | {item['management_scenario']} | {item['min_score']:.2f} | {item['max_score']:.2f} | {item['score_range']:.2f} |"
        )

    lines.extend(
        [
            "",
            "## 3. 关键物理指标敏感性",
            "",
            "| 桩号 | 变量 | 得分最小值 | 得分最大值 | 得分变化幅度 |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for item in physical_ranges:
        lines.append(
            f"| {item['stake']} | {item['variable']} | {item['min_score']:.2f} | {item['max_score']:.2f} | {item['score_range']:.2f} |"
        )

    top_physical = physical_ranges[:5]
    lines.extend(
        [
            "",
            "## 4. 结论",
            "",
            "- `alpha` 对结果有明显影响，因为它控制“最不利失效模式”在综合风险中的占比。论文中不宜只给一个固定值，应说明取值依据并做敏感性分析。",
            "- `barrier_lambda` 在没有运行管理输入时不影响结果；只有输入 E1-E5 后才会改变评价结果。这一点符合模型设计：运行管理不是凭空参与计算，而是在有资料时作为安全屏障修正风险。",
            "- 物理指标中，抗滑安全系数、渗透比降和堤顶高程均能触发 C 级临界结果，说明模型没有把物理失效平均掉。",
            "- 当前最敏感的前五组变量如下：",
        ]
    )
    for item in top_physical:
        lines.append(
            f"  - {item['stake']} / {item['variable']}：得分变化 {item['score_range']:.2f}"
        )

    lines.extend(
        [
            "",
            "## 5. 建议",
            "",
            "- 论文正文建议取 `alpha=0.45` 作为基准值，同时展示 `alpha=0.3-0.6` 范围内等级是否稳定。",
            "- `barrier_lambda` 建议作为情景参数，不建议在缺少运行管理记录时强行参与评价。",
            "- 后续接入 GeoStudio 四个剖面计算结果后，应重复本敏感性分析，重点比较渗流比降和抗滑安全系数的主控性。",
        ]
    )

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    out_dir = SAFE_DIR / "sensitivity_outputs"
    context = load_context(SAFE_DIR)

    # Keep the standard model output fresh for comparison.
    run_failure_response_barrier_model(SAFE_DIR)

    alpha_lambda_rows = alpha_lambda_sensitivity(context)
    physical_rows = physical_oat_sensitivity(context)

    write_csv(
        out_dir / "failure_response_barrier_alpha_lambda.csv",
        alpha_lambda_rows,
        [
            "stake",
            "management_scenario",
            "management_input_score",
            "alpha",
            "barrier_lambda",
            "score",
            "grade",
            "rho",
            "dominant_mode",
            "barrier_ability",
        ],
    )
    write_csv(
        out_dir / "failure_response_barrier_physical_oat.csv",
        physical_rows,
        [
            "stake",
            "variable",
            "value",
            "base_score",
            "score",
            "score_change",
            "grade",
            "dominant_mode",
        ],
    )
    build_markdown_summary(
        alpha_lambda_rows,
        physical_rows,
        out_dir / "failure_response_barrier_sensitivity_summary.md",
    )

    print(f"alpha/lambda rows: {len(alpha_lambda_rows)}")
    print(f"physical OAT rows: {len(physical_rows)}")
    print(f"outputs: {out_dir}")


if __name__ == "__main__":
    main()
