"""
Generate a balanced synthetic scenario dataset and run the failure-response
barrier evaluation model.

The generated records are not engineering measurements.  They are controlled
scenario samples for checking whether the evaluation model can distinguish
different safety levels and dominant failure modes.
"""

from __future__ import annotations

import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from failure_response_barrier_model import evaluate_section
from safety_evaluation import FREEBOARD_RIVER


RNG_SEED = 20260616
DEFAULT_N_PER_CELL = 25
OUTPUT_DIR = Path(__file__).with_name("synthetic_dataset_outputs")


TARGET_MODES = [
    "safe_reference",
    "overtopping",
    "seepage",
    "slope",
    "scour",
    "building",
    "mixed",
]

SEVERITIES = ["safe", "slight", "moderate", "severe", "critical"]


QUAL_SCORE = {
    "good": {
        "A4": 100, "A6": 100, "A8": 100, "A9": 100,
        "B2": 100, "B3": 100, "B4": 100,
        "C2": 100, "C6": 100,
        "D4": 100, "D5": 100,
        "E1": 100, "E2": 100, "E3": 100, "E4": 100, "E5": 100,
    },
    "slight": {
        "A4": 80, "A6": 80, "A8": 70, "A9": 70,
        "B2": 100, "B3": 70, "B4": 100,
        "C2": 70, "C6": 100,
        "D4": 100, "D5": 70,
        "E1": 80, "E2": 70, "E3": 70, "E4": 70, "E5": 60,
    },
    "moderate": {
        "A4": 60, "A6": 60, "A8": 70, "A9": 70,
        "B2": 100, "B3": 70, "B4": 60,
        "C2": 70, "C6": 60,
        "D4": 60, "D5": 40,
        "E1": 40, "E2": 70, "E3": 70, "E4": 70, "E5": 60,
    },
    "severe": {
        "A4": 40, "A6": 0, "A8": 0, "A9": 0,
        "B2": 0, "B3": 0, "B4": 0,
        "C2": 0, "C6": 0,
        "D4": 0, "D5": 0,
        "E1": 40, "E2": 40, "E3": 0, "E4": 0, "E5": 0,
    },
    "critical": {
        "A4": 0, "A6": 0, "A8": 0, "A9": 0,
        "B2": 0, "B3": 0, "B4": 0,
        "C2": 0, "C6": 0,
        "D4": 0, "D5": 0,
        "E1": 40, "E2": 40, "E3": 0, "E4": 0, "E5": 0,
    },
}
QUAL_SCORE["safe"] = dict(QUAL_SCORE["good"])


def jitter(rng, value, width, lo=None, hi=None):
    out = value + rng.uniform(-width, width)
    if lo is not None:
        out = max(lo, out)
    if hi is not None:
        out = min(hi, out)
    return round(out, 4)


def base_section(stake):
    design_flood = 34.04
    return {
        "桩号": stake,
        "是否为湖堤": False,
        "堤顶高程_m": design_flood + FREEBOARD_RIVER + 0.8,
        "堤顶宽度_m": 8.5,
        "外坡坡比": 3.0,
        "内坡坡比": 3.2,
        "设计洪水位_m": design_flood,
        "设计枯水位_m": 26.19,
        "堤基类型": "B",
        "控制土层名称": "synthetic_control_sand",
        "控制层Gs": 2.65,
        "控制层e": 0.70,
        "控制渗透比降J_allow": 0.25,
        "土层参数": [
            {
                "土层名称": "synthetic_control_sand",
                "Gs": 2.65,
                "e": 0.70,
                "厚度_m": 2.0,
                "渗透系数_cm_s": 0.00488,
                "允许渗透比降J_allow": 0.25,
            }
        ],
        "渗透比降i": 0.10,
        "堤身渗透比降i": 0.08,
        "接触面渗透比降i": 0.09,
        "背水坡FoS_正常": 1.62,
        "临水坡FoS": 1.48,
        "软基段_沉降量_cm": 5.0,
        "软基段_沉降差_cm": 1.0,
        "冲刷深度_m": 0.2,
        "基座埋深_m": 2.0,
        "待输入指标": dict(QUAL_SCORE["good"]),
    }


def leak_evidence(severity):
    density = {
        "safe": 0.0,
        "slight": 0.6,
        "moderate": 1.5,
        "severe": 3.0,
        "critical": 5.0,
    }[severity]
    if density <= 0:
        level, score_cap, note = 0, None, "no leakage evidence"
    elif density <= 1:
        level, score_cap, note = 1, None, "ordinary single leakage evidence"
    elif density <= 4:
        level, score_cap, note = 2, "B级_基本安全", "multiple/sensitive leakage evidence"
    else:
        level, score_cap, note = 3, "C级_不安全", "clustered severe leakage evidence"
    return {
        "渗漏点数": int(round(density)),
        "加权渗漏点数": density,
        "加权渗漏点密度_点每100m": density,
        "UAV证据等级": level,
        "UAV门控等级上限": score_cap,
        "UAV门控说明": note,
        "渗漏点明细": [],
    }


def apply_severity(sec, target, severity, rng):
    sec["待输入指标"] = dict(QUAL_SCORE["good"])
    sev_index = SEVERITIES.index(severity)

    # Broad background deterioration for unsafe samples.
    if severity in {"severe", "critical"}:
        sec["堤顶宽度_m"] = jitter(rng, 7.0, 0.25, 5.8, 8.5)
        sec["软基段_沉降量_cm"] = jitter(rng, 17.0 if severity == "severe" else 24.0, 2.0, 0)
        sec["软基段_沉降差_cm"] = jitter(rng, 6.0 if severity == "severe" else 9.0, 1.0, 0)

    if target == "safe_reference":
        if severity != "safe":
            sec["待输入指标"].update({
                "A4": QUAL_SCORE[severity]["A4"],
                "A6": QUAL_SCORE[severity]["A6"],
                "D5": QUAL_SCORE[severity]["D5"],
            })
            sec["渗透比降i"] = jitter(rng, 0.13 + sev_index * 0.02, 0.01, 0.03)
            sec["背水坡FoS_正常"] = jitter(rng, 1.58 - sev_index * 0.04, 0.02, 1.05)
            sec["临水坡FoS"] = jitter(rng, 1.45 - sev_index * 0.035, 0.02, 1.02)
        return sec, leak_evidence("safe")

    if target == "overtopping":
        margin = {
            "safe": 0.8,
            "slight": 0.2,
            "moderate": -0.2,
            "severe": -0.9,
            "critical": -1.8,
        }[severity]
        required = sec["设计洪水位_m"] + FREEBOARD_RIVER
        sec["堤顶高程_m"] = jitter(rng, required + margin, 0.08)
        sec["待输入指标"]["B3"] = {"safe": 100, "slight": 70, "moderate": 70, "severe": 0, "critical": 0}[severity]

    elif target == "seepage":
        ratio = {
            "safe": 0.35,
            "slight": 0.55,
            "moderate": 0.75,
            "severe": 0.95,
            "critical": 1.15,
        }[severity]
        icr = (sec["控制层Gs"] - 1.0) / (1.0 + sec["控制层e"])
        sec["渗透比降i"] = jitter(rng, icr * ratio, 0.015, 0.01)
        sec["堤身渗透比降i"] = jitter(rng, icr * (ratio * 0.85), 0.015, 0.01)
        sec["接触面渗透比降i"] = jitter(rng, icr * (ratio * 0.95), 0.015, 0.01)
        sec["待输入指标"]["C2"] = QUAL_SCORE[severity]["C2"]
        sec["待输入指标"]["C6"] = QUAL_SCORE[severity]["C6"]
        return sec, leak_evidence(severity)

    elif target == "slope":
        sec["背水坡FoS_正常"] = jitter(
            rng,
            {"safe": 1.58, "slight": 1.43, "moderate": 1.28, "severe": 1.08, "critical": 0.92}[severity],
            0.025,
            0.75,
        )
        sec["临水坡FoS"] = jitter(
            rng,
            {"safe": 1.45, "slight": 1.32, "moderate": 1.16, "severe": 1.04, "critical": 0.90}[severity],
            0.025,
            0.75,
        )
        sec["待输入指标"]["D5"] = QUAL_SCORE[severity]["D5"]

    elif target == "scour":
        sec["冲刷深度_m"] = jitter(
            rng,
            {"safe": 0.2, "slight": 0.45, "moderate": 0.75, "severe": 1.15, "critical": 1.6}[severity],
            0.06,
            0,
        )
        sec["待输入指标"]["A4"] = QUAL_SCORE[severity]["A4"]

    elif target == "building":
        sec["待输入指标"]["A3"] = QUAL_SCORE[severity].get("A3", 100)
        sec["待输入指标"]["B4"] = QUAL_SCORE[severity]["B4"]
        sec["待输入指标"]["C6"] = QUAL_SCORE[severity]["C6"]
        sec["待输入指标"]["D4"] = QUAL_SCORE[severity]["D4"]

    elif target == "mixed":
        sec["待输入指标"] = dict(QUAL_SCORE[severity])
        ratio = {
            "safe": 0.35,
            "slight": 0.55,
            "moderate": 0.75,
            "severe": 0.95,
            "critical": 1.15,
        }[severity]
        icr = (sec["控制层Gs"] - 1.0) / (1.0 + sec["控制层e"])
        sec["渗透比降i"] = jitter(rng, icr * ratio, 0.015, 0.01)
        sec["堤身渗透比降i"] = jitter(rng, icr * (ratio * 0.85), 0.015, 0.01)
        sec["接触面渗透比降i"] = jitter(rng, icr * (ratio * 0.95), 0.015, 0.01)
        sec["背水坡FoS_正常"] = jitter(rng, 1.50 - sev_index * 0.11, 0.02, 0.85)
        sec["临水坡FoS"] = jitter(rng, 1.38 - sev_index * 0.09, 0.02, 0.85)
        sec["冲刷深度_m"] = jitter(rng, 0.25 + sev_index * 0.25, 0.05, 0)
        sec["待输入指标"].update({k: min(sec["待输入指标"].get(k, 100), v) for k, v in QUAL_SCORE[severity].items()})
        return sec, leak_evidence(severity)

    return sec, leak_evidence("safe")


def generate_dataset(n_per_cell=DEFAULT_N_PER_CELL, seed=RNG_SEED):
    rng = random.Random(seed)
    samples = []
    geo_cls = []
    buildings = []
    hist_dangers = []

    idx = 1
    for target in TARGET_MODES:
        for severity in SEVERITIES:
            for _ in range(n_per_cell):
                stake = f"{idx // 1000}+{idx % 1000:03d}"
                sec = base_section(stake)
                sec, leak = apply_severity(sec, target, severity, rng)
                sec["synthetic_target_mode"] = target
                sec["synthetic_severity"] = severity
                samples.append((sec, leak))
                geo_cls.append({
                    "起始桩号": stake,
                    "终止桩号": stake,
                    "填土质量": "质量较好" if severity in {"safe", "slight"} else ("质量一般" if severity == "moderate" else "质量较差"),
                })
                buildings.append({
                    "桩号": stake,
                    "检测结论": "一类" if target != "building" or severity in {"safe", "slight"} else ("三类" if severity == "moderate" else "四类"),
                })
                idx += 1

    return samples, geo_cls, buildings, hist_dangers


def summarize(results):
    grade_counter = Counter(r["安全等级"] for r in results)
    mode_counter = Counter(r["主控失效模式"] for r in results)
    cross = Counter((r["synthetic_target_mode"], r["主控失效模式"]) for r in results)
    severity_grade = Counter((r["synthetic_severity"], r["安全等级"]) for r in results)
    return grade_counter, mode_counter, cross, severity_grade


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    samples, geo_cls, buildings, hist_dangers = generate_dataset()
    results = []
    rows = []
    contrib_rows = []

    for sec, leak in samples:
        result = evaluate_section(sec, geo_cls, buildings, hist_dangers, leak)
        result["synthetic_target_mode"] = sec["synthetic_target_mode"]
        result["synthetic_severity"] = sec["synthetic_severity"]
        results.append(result)

        row = {
            "sample_id": sec["桩号"],
            "target_mode": sec["synthetic_target_mode"],
            "target_severity": sec["synthetic_severity"],
            "score": result["安全得分"],
            "grade": result["安全等级"],
            "model_grade": result["模型原始等级"],
            "rho": result["综合风险度量rho"],
            "dominant_mode": result["主控失效模式"],
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
        rows.append(row)

        for rank, item in enumerate(result["主控模式指标贡献率"][:5], start=1):
            contrib_rows.append({
                "sample_id": sec["桩号"],
                "target_mode": sec["synthetic_target_mode"],
                "target_severity": sec["synthetic_severity"],
                "dominant_mode": result["主控失效模式"],
                "rank": rank,
                "indicator": item["指标"],
                "indicator_score": item["指标得分"],
                "contribution_rate": item["贡献率"],
            })

    with (OUTPUT_DIR / "synthetic_samples_input.json").open("w", encoding="utf-8") as f:
        json.dump([x[0] for x in samples], f, ensure_ascii=False, indent=2)
    with (OUTPUT_DIR / "synthetic_evaluation_results.json").open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    with (OUTPUT_DIR / "synthetic_evaluation_dataset.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    with (OUTPUT_DIR / "synthetic_top_contributions.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(contrib_rows[0]))
        writer.writeheader()
        writer.writerows(contrib_rows)

    grade_counter, mode_counter, cross, severity_grade = summarize(results)
    summary = {
        "sample_count": len(results),
        "target_modes": TARGET_MODES,
        "severities": SEVERITIES,
        "n_per_target_mode_severity": DEFAULT_N_PER_CELL,
        "grade_distribution": dict(grade_counter),
        "dominant_mode_distribution": dict(mode_counter),
        "target_vs_dominant_mode": {f"{k[0]} -> {k[1]}": v for k, v in cross.items()},
        "severity_vs_grade": {f"{k[0]} -> {k[1]}": v for k, v in severity_grade.items()},
    }
    with (OUTPUT_DIR / "synthetic_dataset_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"generated samples: {len(results)}")
    print("grade distribution:", dict(grade_counter))
    print("dominant mode distribution:", dict(mode_counter))
    print(f"output: {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
