"""Four paired diagnostics for the two UAV channels of the original 875 model."""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "分析工作区" / "875基线复现"
OUT = ROOT / "分析工作区" / "875观测通道消融"
sys.path.insert(0, str(BASE))
from synthetic_dataset_evaluation import generate_dataset  # noqa: E402
from failure_response_barrier_model import evaluate_section  # noqa: E402


def alter(leak: dict, anchor: bool, cap_off: bool) -> dict:
    value = dict(leak)
    if anchor:
        value["加权渗漏点密度_点每100m"] = 0.0
        value["加权渗漏点数"] = 0.0
        value["渗漏点数"] = 0
        value["渗漏点明细"] = []
    if cap_off:
        value["UAV门控等级上限"] = None
    return value


def main() -> None:
    OUT.mkdir(exist_ok=True)
    samples, geo, buildings, dangers = generate_dataset()
    settings = [("full", False, False), ("cap_off", False, True), ("C3_anchor100", True, False), ("C3_anchor100_cap_off", True, True)]
    records = []
    for sec, leak in samples:
        for name, anchor, cap_off in settings:
            out = evaluate_section(sec, geo, buildings, dangers, alter(leak, anchor, cap_off))
            records.append({"sample_id": sec["桩号"], "target_mode": sec["synthetic_target_mode"], "severity": sec["synthetic_severity"], "arm": name,
                            "score": out["安全得分"], "raw_grade": out["模型原始等级"], "uav_grade": out["UAV门控后等级"],
                            "final_grade": out["安全等级"], "dominant_mode": out["主控失效模式"], "C3_score": out["二级指标得分"]["C3"]})
    with (OUT / "逐样本四组结果.csv").open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    by = {arm: {r["sample_id"]: r for r in records if r["arm"] == arm} for arm, _, _ in settings}
    delivered = json.loads((ROOT / "875样本模型测试资料包" / "3_样本生成与参考规则" / "synthetic_dataset_outputs" / "synthetic_evaluation_results.json").read_text(encoding="utf-8"))
    for row in delivered:
        test = by["full"][row["桩号"]]
        assert (test["score"], test["final_grade"], test["dominant_mode"]) == (row["安全得分"], row["安全等级"], row["主控失效模式"])
    comparison = {}
    for arm, _, _ in settings[1:]:
        diffs = []
        for sample_id, orig in by["full"].items():
            candidate = by[arm][sample_id]
            diffs.append({"sample_id": sample_id, "target_mode": orig["target_mode"], "severity": orig["severity"],
                          "score_delta": round(candidate["score"] - orig["score"], 4),
                          "raw_grade_changed": candidate["raw_grade"] != orig["raw_grade"],
                          "final_grade_changed": candidate["final_grade"] != orig["final_grade"],
                          "mode_changed": candidate["dominant_mode"] != orig["dominant_mode"]})
        comparison[arm] = {"n": len(diffs), "score_changed": sum(x["score_delta"] != 0 for x in diffs),
                           "score_delta_min": min(x["score_delta"] for x in diffs), "score_delta_max": max(x["score_delta"] for x in diffs),
                           "raw_grade_changed": sum(x["raw_grade_changed"] for x in diffs),
                           "final_grade_changed": sum(x["final_grade_changed"] for x in diffs),
                           "mode_changed": sum(x["mode_changed"] for x in diffs),
                           "final_grade_changed_by_target": dict(Counter(x["target_mode"] for x in diffs if x["final_grade_changed"]))}
    (OUT / "消融摘要.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(comparison, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
