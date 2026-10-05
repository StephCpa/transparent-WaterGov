"""Read-only audit of the delivered 875 synthetic scenarios and local replay."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "分析工作区"
OUT = WORK / "875基线分析"
BASE = ROOT / "875样本模型测试资料包" / "3_样本生成与参考规则"
DELIVERED = BASE / "synthetic_dataset_outputs"
REPLAY = WORK / "875基线复现" / "synthetic_dataset_outputs"
GRADES = ("A", "B", "C")
MODES = ("safe_reference", "overtopping", "seepage", "slope", "scour", "building", "mixed")
SEVERITIES = ("safe", "slight", "moderate", "severe", "critical")
REFERENCE = {"safe": "A", "slight": "A", "moderate": "B", "severe": "C", "critical": "C"}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as file:
        for part in iter(lambda: file.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def grade(value: str) -> str:
    assert value and value[0] in GRADES, value
    return value[0]


def metrics(rows: list[dict]) -> dict:
    cm = {ref: {pred: 0 for pred in GRADES} for ref in GRADES}
    for row in rows:
        cm[row["reference"]][row["grade"]] += 1
    n = len(rows)
    per_class = {}
    for cls in GRADES:
        tp = cm[cls][cls]
        support = sum(cm[cls].values())
        predicted = sum(cm[ref][cls] for ref in GRADES)
        precision = tp / predicted if predicted else None
        recall = tp / support if support else None
        f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else None
        per_class[cls] = {"support": support, "predicted": predicted, "precision": precision, "recall": recall, "f1": f1}
    return {
        "n": n,
        "correct": sum(cm[c][c] for c in GRADES),
        "accuracy": sum(cm[c][c] for c in GRADES) / n if n else None,
        "confusion": cm,
        "per_class": per_class,
        "macro_f1": sum(v["f1"] for v in per_class.values() if v["f1"] is not None) / sum(v["f1"] is not None for v in per_class.values()),
        "balanced_accuracy": sum(v["recall"] for v in per_class.values() if v["recall"] is not None) / sum(v["recall"] is not None for v in per_class.values()),
        "distance_1": sum(abs(GRADES.index(r["reference"]) - GRADES.index(r["grade"])) == 1 for r in rows),
        "distance_2": sum(abs(GRADES.index(r["reference"]) - GRADES.index(r["grade"])) == 2 for r in rows),
        "C_underestimated": cm["C"]["A"] + cm["C"]["B"],
        "A_overestimated": cm["A"]["B"] + cm["A"]["C"],
    }


def main() -> None:
    OUT.mkdir(exist_ok=True)
    names = ("synthetic_samples_input.json", "synthetic_evaluation_results.json", "synthetic_evaluation_dataset.csv", "synthetic_dataset_summary.json", "synthetic_top_contributions.csv")
    comparison = [{"file": name, "delivered_sha256": digest(DELIVERED / name), "replay_sha256": digest(REPLAY / name), "byte_identical": digest(DELIVERED / name) == digest(REPLAY / name)} for name in names]
    (OUT / "复现文件比对.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    assert all(x["byte_identical"] for x in comparison), comparison

    manifest = []
    for directory in (ROOT / "875样本模型测试资料包", ROOT / "补充资料"):
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            ext = path.suffix.lower()
            role = "code" if ext == ".py" else "structured_data" if ext in (".json", ".csv", ".xlsx") else "narrative" if ext in (".md", ".txt", ".docx", ".pdf") else "figure_or_other"
            manifest.append({"relative_path": str(path.relative_to(ROOT)), "size_bytes": path.stat().st_size, "sha256": digest(path), "role": role, "read_status": "indexed; content review pending unless listed in analysis report"})
    for name in ("875样本模型测试资料包.rar", "补充资料.rar"):
        path = ROOT / name
        if path.exists():
            manifest.append({"relative_path": name, "size_bytes": path.stat().st_size, "sha256": digest(path), "role": "source_archive", "read_status": "indexed archive"})
    write_csv(OUT / "原始文件清单.csv", manifest, ["relative_path", "size_bytes", "sha256", "role", "read_status"])

    samples = json.loads((DELIVERED / names[0]).read_text(encoding="utf-8"))
    results = json.loads((DELIVERED / names[1]).read_text(encoding="utf-8"))
    with (DELIVERED / names[2]).open(encoding="utf-8-sig", newline="") as file:
        csv_rows = list(csv.DictReader(file))
    assert len(samples) == len(results) == len(csv_rows) == 875
    sample_by_id = {r["桩号"]: r for r in samples}
    result_by_id = {r["桩号"]: r for r in results}
    csv_by_id = {r["sample_id"]: r for r in csv_rows}
    assert len(sample_by_id) == len(result_by_id) == len(csv_by_id) == 875
    assert sample_by_id.keys() == result_by_id.keys() == csv_by_id.keys()

    rows = []
    for sample_id, sample in sample_by_id.items():
        result, flat = result_by_id[sample_id], csv_by_id[sample_id]
        mode, severity = sample["synthetic_target_mode"], sample["synthetic_severity"]
        assert (mode, severity) == (result["synthetic_target_mode"], result["synthetic_severity"])
        assert (mode, severity) == (flat["target_mode"], flat["target_severity"])
        predicted = grade(result["安全等级"])
        assert predicted == grade(flat["grade"])
        record = {
            "sample_id": sample_id, "target_mode": mode, "severity": severity,
            "reference": REFERENCE[severity], "grade": predicted,
            "raw_grade": grade(result["模型原始等级"]),
            "uav_grade": grade(result["UAV门控后等级"]),
            "score": result["安全得分"], "rho": result["综合风险度量rho"],
            "dominant_mode": result["主控失效模式"],
            "physical_gate": ";".join(map(str, result["硬约束门控原因"])),
            "uav_gate": result["UAV观测门控说明"],
            "seepage_i": sample.get("渗透比降i"),
            "body_i": sample.get("堤身渗透比降i"),
            "contact_i": sample.get("接触面渗透比降i"),
            "fos_back": sample.get("背水坡FoS_正常"),
            "input_indicator_json": json.dumps(sample.get("待输入指标"), ensure_ascii=False, separators=(",", ":")),
        }
        rows.append(record)
    cell_count = Counter((r["target_mode"], r["severity"]) for r in rows)
    assert len(cell_count) == 35 and all(value == 25 for value in cell_count.values())
    input_signatures = {}
    for sample_id, sample in sample_by_id.items():
        value = {k: v for k, v in sample.items() if k not in ("桩号", "synthetic_target_mode", "synthetic_severity")}
        input_signatures[sample_id] = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    unique_inputs_by_cell = {f"{mode}/{severity}": len({input_signatures[r["sample_id"]] for r in rows if r["target_mode"] == mode and r["severity"] == severity}) for mode in MODES for severity in SEVERITIES}

    overall = metrics(rows)
    assert [[overall["confusion"][a][b] for b in GRADES] for a in GRADES] == [[296,54,0],[25,150,0],[0,57,293]]
    assert overall["correct"] == 739
    cells = []
    for mode in MODES:
        for severity in SEVERITIES:
            group = [r for r in rows if r["target_mode"] == mode and r["severity"] == severity]
            cells.append({"target_mode": mode, "severity": severity, "reference": REFERENCE[severity], "n": 25,
                          "pred_A": sum(r["grade"] == "A" for r in group), "pred_B": sum(r["grade"] == "B" for r in group), "pred_C": sum(r["grade"] == "C" for r in group),
                          "correct": sum(r["reference"] == r["grade"] for r in group),
                          "score_min": min(r["score"] for r in group), "score_mean": sum(r["score"] for r in group)/25, "score_max": max(r["score"] for r in group)})
    write_csv(OUT / "35组合分层统计.csv", cells, list(cells[0]))
    errors = [r for r in rows if r["grade"] != r["reference"]]
    write_csv(OUT / "136条误分类溯源.csv", errors, list(rows[0]))
    by_mode = {m: metrics([r for r in rows if r["target_mode"] == m]) for m in MODES}
    by_severity = {s: metrics([r for r in rows if r["severity"] == s]) for s in SEVERITIES}
    gate_stage = Counter((r["reference"], r["raw_grade"], r["uav_grade"], r["grade"]) for r in rows)
    info = {"overall": overall, "by_mode": by_mode, "by_severity": by_severity,
            "by_raw_grade": metrics([{**r, "grade": r["raw_grade"]} for r in rows]),
            "by_uav_grade": metrics([{**r, "grade": r["uav_grade"]} for r in rows]),
            "grade_stage_counts": [{"reference": a, "raw": b, "uav": c, "final": d, "n": n} for (a,b,c,d),n in sorted(gate_stage.items())],
            "gate_stage_change_counts": {"raw_to_uav": sum(r["raw_grade"] != r["uav_grade"] for r in rows), "uav_to_final": sum(r["uav_grade"] != r["grade"] for r in rows), "raw_to_final": sum(r["raw_grade"] != r["grade"] for r in rows)},
            "gate_change_by_mode": {m: sum(r["raw_grade"] != r["grade"] for r in rows if r["target_mode"] == m) for m in MODES},
            "distinct_input_payloads_excluding_id_and_design_labels": len(set(input_signatures.values())),
            "unique_inputs_by_cell": unique_inputs_by_cell,
            "error_stage_counts": {"raw_wrong_final_right": sum(r["raw_grade"] != r["reference"] and r["grade"] == r["reference"] for r in rows), "raw_right_final_wrong": sum(r["raw_grade"] == r["reference"] and r["grade"] != r["reference"] for r in rows), "both_wrong": sum(r["raw_grade"] != r["reference"] and r["grade"] != r["reference"] for r in rows)},
            "dominant_mode_by_target": {m: dict(Counter(r["dominant_mode"] for r in rows if r["target_mode"] == m)) for m in MODES},
            "replay_byte_identical": True, "n_files_in_manifest": len(manifest)}
    (OUT / "875统计摘要.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"overall": overall, "by_mode": {m: {"n": x["n"], "correct": x["correct"], "confusion": x["confusion"]} for m,x in by_mode.items()}, "gate_stage_change_counts": info["gate_stage_change_counts"], "n_manifest": len(manifest)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
