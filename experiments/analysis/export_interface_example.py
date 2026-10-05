"""Export a static, explicitly synthetic transparent-evaluation API example."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "875样本模型测试资料包" / "3_样本生成与参考规则"
DATA = SOURCE / "synthetic_dataset_outputs"
OUT = ROOT / "分析工作区" / "离线接口示例_合成样本.json"


def hashfile(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    input_path = DATA / "synthetic_samples_input.json"
    output_path = DATA / "synthetic_evaluation_results.json"
    section = next(r for r in json.loads(input_path.read_text(encoding="utf-8")) if r["桩号"] == "0+326")
    result = next(r for r in json.loads(output_path.read_text(encoding="utf-8")) if r["桩号"] == "0+326")
    assert section["synthetic_target_mode"] == "seepage" and section["synthetic_severity"] == "severe"
    scores = result["二级指标得分"]
    evidence = []
    for code, field, unit in (("C1", "渗透比降i", "无量纲"), ("C4", "堤身渗透比降i", "无量纲"), ("C5", "接触面渗透比降i", "无量纲")):
        evidence.append({"indicator": code, "raw_value": section[field], "unit": unit, "score": scores[code],
                         "value_type": "synthetic scenario input", "applicability": "applicable", "availability": "known",
                         "observed_at": None, "spatial_scope": "synthetic section " + section["桩号"],
                         "source_locator": "synthetic_samples_input.json:" + section["桩号"] + "/" + field})
    evidence.append({"indicator": "C3", "raw_value": result["UAV渗漏观测证据"], "unit": "scenario-coded observations",
                     "score": scores["C3"], "value_type": "synthetic scenario input", "applicability": "applicable", "availability": "known",
                     "observed_at": None, "spatial_scope": "synthetic section " + section["桩号"],
                     "source_locator": "synthetic_evaluation_results.json:" + section["桩号"] + "/UAV渗漏观测证据"})
    data = {
        "schema_version": "example-0.1", "dataset_kind": "controlled_synthetic_scenario", "engineering_validation": False,
        "request": {"section_id": section["桩号"], "scenario_id": "seepage/severe/" + section["桩号"], "evidence_version": hashfile(input_path),
                    "model_version": {"generator_sha256": hashfile(SOURCE / "synthetic_dataset_evaluation.py"),
                                      "evaluator_sha256": hashfile(SOURCE / "failure_response_barrier_model.py"),
                                      "scoring_sha256": hashfile(SOURCE / "safety_evaluation.py")}},
        "response": {"indicator_evidence": evidence, "score": result["安全得分"], "raw_grade": result["模型原始等级"],
                     "uav_grade": result["UAV门控后等级"], "final_grade": result["安全等级"],
                     "dominant_mode": result["主控失效模式"], "triggered_rules": result["硬约束门控原因"],
                     "missing_indicators": result["缺失指标"], "result_source_locator": "synthetic_evaluation_results.json:" + section["桩号"],
                     "interpretation": "model grade for one synthetic scenario; neither site safety certificate nor failure probability"},
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"section": section["桩号"], "score": result["安全得分"], "grade": result["安全等级"], "trigger_rules": len(result["硬约束门控原因"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
