"""Audit provenance and indicator conflicts in the delivered K45+500 case."""

from __future__ import annotations

import csv
import difflib
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "分析工作区" / "K45+500追溯"
CASE = ROOT / "补充资料" / "06_独立工程历史案例验证"
BASE = ROOT / "875样本模型测试资料包" / "3_样本生成与参考规则"
RESEARCH = ROOT / "research" / "transparent_eval"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def csv_out(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    result = json.loads((CASE / "K45+500_历史管涌代表工况_复算结果.json").read_text(encoding="utf-8"))
    model = result["评价模型结果"]
    score_map = model["二级指标得分"]
    with (CASE / "01_K45+500_29项指标取值表.csv").open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 29 and len(score_map) == 29
    assert {r["代码"] for r in rows} == set(score_map)
    ledger = []
    conflicts = []
    for row in rows:
        code = row["代码"]
        table_score = float(row["模型得分"]) if row["模型得分"].strip() else None
        result_score = score_map[code]
        status = "一致" if table_score == result_score else "冲突"
        item = {"代码": code, "指标": row["二级指标"], "原值或状态": row["本次取值或状态"],
                "表中模型得分": table_score, "结果JSON得分": result_score, "核对": status,
                "单位": "见原值或状态；未规范化", "适用性": "待确认" if "不涉及" in row["本次取值或状态"] or "非控制项" in row["本次取值或状态"] else "表述为适用，工程范围待核",
                "取值类型": row["取值类型"], "依据或计算方法": row["依据或计算方法"],
                "资料依据": row["规范或资料依据"], "处理说明": row["处理说明"],
                "表中来源定位": "01_K45+500_29项指标取值表.csv:" + code,
                "结果来源定位": "K45+500_历史管涌代表工况_复算结果.json:评价模型结果/二级指标得分/" + code,
                "观测时间": "", "接收时间": "", "空间范围": "K45+500代表断面，详细覆盖待核", "可用性": "冲突" if status == "冲突" else "交付值已知；证据独立性待核", "质量说明": "需核查规范适用、空间时间和输入原件"}
        ledger.append(item)
        if status == "冲突":
            conflicts.append(item)
    csv_out(OUT / "29指标证据台账.csv", ledger, list(ledger[0]))
    csv_out(OUT / "指标得分冲突.csv", conflicts, list(ledger[0]))

    versions = []
    for name in ("failure_response_barrier_model.py", "safety_evaluation.py"):
        paths = {"875基线": BASE / name, "历史案例": CASE / name,
                 "补充资料875": ROOT / "补充资料" / "02_875合成样本与生成程序" / name}
        for label, path in paths.items():
            versions.append({"name": name, "version": label, "exists": path.exists(), "sha256": sha(path) if path.exists() else "", "bytes": path.stat().st_size if path.exists() else ""})
        if paths["历史案例"].exists():
            old = paths["875基线"].read_text(encoding="utf-8").splitlines(keepends=True)
            new = paths["历史案例"].read_text(encoding="utf-8").splitlines(keepends=True)
            diff = "".join(difflib.unified_diff(old, new, fromfile=str(paths["875基线"].relative_to(ROOT)), tofile=str(paths["历史案例"].relative_to(ROOT))))
            (OUT / (name + ".diff")).write_text(diff, encoding="utf-8")
    for name in ("core.py", "legacy_guard.py", "baseline875.py"):
        path = RESEARCH / name
        versions.append({"name": name, "version": "前期research试验入口，非原版基线", "exists": path.exists(), "sha256": sha(path) if path.exists() else "", "bytes": path.stat().st_size if path.exists() else ""})
    csv_out(OUT / "代码版本登记.csv", versions, ["name", "version", "exists", "sha256", "bytes"])
    facts = {"case": result["案例性质"], "historical_record": result["历史事实"], "water_level_note": result["水位说明"],
             "section": result["断面与地层取值"], "scenario": result["计算工况"],
             "seepage": result["渗流计算结果"], "stability": result["稳定计算结果"],
             "evaluation": {k: model.get(k) for k in ("安全得分", "安全等级", "模型原始等级", "UAV门控后等级", "硬约束门控原因", "主控失效模式", "缺失指标")},
             "indicator_conflicts": [r["代码"] for r in conflicts]}
    (OUT / "案例交付结果摘录.json").write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"indicator_count": len(rows), "score_conflicts": [{"code": x["代码"], "table": x["表中模型得分"], "result": x["结果JSON得分"]} for x in conflicts], "version_hashes": versions, "evaluation": facts["evaluation"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
