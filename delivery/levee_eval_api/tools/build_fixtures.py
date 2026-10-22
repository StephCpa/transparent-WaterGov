"""Regenerate the 875-sample regression fixtures (tests/fixtures/).

The synthetic dataset is regenerated with the delivered generator (tools/reference, fixed seed),
each internal section is translated to an API request, and the expected outputs are computed by
calling the delivered evaluate_section() directly, without this service's translation layer.
With --delivered-results the expected outputs are also checked against the delivered results
file (synthetic_evaluation_results.json), so the fixtures are tied to the delivered run.

    python tools/build_fixtures.py [--delivered-results PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "levee_eval" / "model"), str(ROOT / "tools" / "reference")]

import failure_response_barrier_model as M  # noqa: E402  (delivered code, unpatched)
from synthetic_dataset_evaluation import generate_dataset  # noqa: E402

OUT = ROOT / "tests" / "fixtures"
GRADE = {"A级_安全": "A", "B级_基本安全": "B", "C级_不安全": "C"}
CAP = {None: None, "B级_基本安全": "B", "C级_不安全": "C"}
QUAL_CODES = ("A4", "A6", "A7", "A8", "A9", "B2", "B3", "B4", "C2", "C6", "D4", "D5", "E1", "E2", "E3", "E4", "E5")


def to_request(sec, leak, fill_quality, building_class, k):
    lay = sec["土层参数"][0]
    return {
        "request_id": f"syn-{k:04d}-{sec['synthetic_target_mode']}-{sec['synthetic_severity']}",
        "section": {
            "section_id": f"SYN-{sec['桩号']}",
            "is_lake_levee": sec["是否为湖堤"],
            "crest_elevation_m": sec["堤顶高程_m"],
            "design_flood_level_m": sec["设计洪水位_m"],
            "crest_width_m": sec["堤顶宽度_m"],
            "outer_slope_ratio": sec["外坡坡比"],
            "inner_slope_ratio": sec["内坡坡比"],
            "foundation_class": sec["堤基类型"],
            "control_layer": {"name": sec["控制土层名称"], "Gs": sec["控制层Gs"], "e": sec["控制层e"],
                              "J_allow": sec["控制渗透比降J_allow"]},
            "soil_layers": [{"name": lay["土层名称"], "Gs": lay["Gs"], "e": lay["e"], "thickness_m": lay["厚度_m"],
                             "k_cm_s": lay["渗透系数_cm_s"], "J_allow": lay["允许渗透比降J_allow"]}],
        },
        "computation": {
            "foundation_gradient": sec["渗透比降i"],
            "body_gradient": sec["堤身渗透比降i"],
            "contact_gradient": sec["接触面渗透比降i"],
            "back_slope_fos": sec["背水坡FoS_正常"],
            "front_slope_fos": sec["临水坡FoS"],
        },
        "survey": {"scour_depth_m": sec["冲刷深度_m"],
                   "soft_foundation_settlement_cm": sec["软基段_沉降量_cm"],
                   "soft_foundation_settlement_diff_cm": sec["软基段_沉降差_cm"]},
        "records": {"fill_quality": fill_quality, "crossing_structure_class": building_class, "historical_dangers": []},
        # the generator also writes 待输入指标.A3, which the delivered score_dict ignores (A3 comes from buildings)
        "qualitative": {c: v for c, v in sec["待输入指标"].items() if c in QUAL_CODES},
        "inspection": {"coverage": "complete", "mode": "aggregated", "aggregated": {
            "weighted_density_per_100m": leak["加权渗漏点密度_点每100m"], "evidence_level": leak["UAV证据等级"],
            "gate_cap": CAP[leak["UAV门控等级上限"]], "note": leak["UAV门控说明"]}},
    }


def expected_of(r):
    return {"score": r["安全得分"], "grade": GRADE[r["安全等级"]], "model_grade": GRADE[r["模型原始等级"]],
            "grade_after_observation_gate": GRADE[r["UAV门控后等级"]], "rho": r["综合风险度量rho"],
            "dominant_mode": r["主控失效模式"], "gate_reasons": r["硬约束门控原因"],
            "barrier_ability": r["管理屏障能力"], "barrier_coverage": r["管理信息覆盖度"],
            "mode_responses_raw": r["原始失效响应"], "mode_responses_adjusted": r["屏障修正响应"],
            "indicator_scores": r["二级指标得分"], "missing_indicators": r["缺失指标"]}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--delivered-results", type=Path, help="synthetic_evaluation_results.json of the delivered run")
    args = ap.parse_args(argv)

    samples, geo_cls, buildings, hist = generate_dataset()
    requests, expected = [], []
    for k, ((sec, leak), geo, bld) in enumerate(zip(samples, geo_cls, buildings), start=1):
        assert geo["起始桩号"] == bld["桩号"] == sec["桩号"]
        r = M.evaluate_section(sec, geo_cls, buildings, hist, leak)
        requests.append(to_request(sec, leak, geo["填土质量"], bld["检测结论"], k))
        expected.append({"request_id": requests[-1]["request_id"], **expected_of(r)})

    if args.delivered_results:
        delivered = json.loads(args.delivered_results.read_text(encoding="utf-8"))
        assert len(delivered) == len(expected), "sample count differs from the delivered run"
        bad = [e["request_id"] for e, d in zip(expected, delivered) if {**e, "request_id": None} != {**expected_of(d), "request_id": None}]
        assert not bad, f"{len(bad)} samples differ from the delivered results, e.g. {bad[:3]}"
        print(f"expected outputs identical to the delivered results ({len(delivered)} samples)")

    sys.path.insert(0, str(ROOT))
    from levee_eval.schema import validate
    invalid = [(q["request_id"], validate(q)) for q in requests if validate(q)]
    assert not invalid, invalid[:3]

    OUT.mkdir(parents=True, exist_ok=True)
    dump = dict(ensure_ascii=False, separators=(",", ":"))
    (OUT / "synthetic_875_requests.json").write_text(json.dumps(requests, **dump), encoding="utf-8")
    (OUT / "synthetic_875_expected.json").write_text(json.dumps(expected, **dump), encoding="utf-8")
    print(f"wrote {len(requests)} requests and expected outputs to {OUT}")


if __name__ == "__main__":
    main()
