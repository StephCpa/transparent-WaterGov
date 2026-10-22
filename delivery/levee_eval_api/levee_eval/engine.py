"""Evaluation engine: JSON request -> delivered rule-chain model -> JSON response.

The model files in model/ are the delivered code, copied unchanged (sha256 in MODEL_FILES).
This module only translates field names, builds the auxiliary lists the delivered
evaluate_section() expects for a single evaluation unit, and translates the result back.

One behaviour is adapted at import time: the delivered score_C3() cannot express "no valid
inspection" (it raises on None), so it is wrapped to return None in that case and C3 is then
treated as a missing indicator, as Chapter 5 requires.  For every other input the wrapper calls
the delivered function unchanged.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import schema

API_VERSION = "1.0.0"
MODEL_DIR = Path(__file__).resolve().parent / "model"
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))

import failure_response_barrier_model as M  # noqa: E402
import safety_evaluation as SE  # noqa: E402

_delivered_score_C3 = M.score_C3


def _score_C3_allow_missing(leak_n):
    return None if leak_n is None else _delivered_score_C3(leak_n)


M.score_C3 = _score_C3_allow_missing


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


MODEL_FILES = {p.name: _sha256(p) for p in sorted(MODEL_DIR.iterdir())
               if p.suffix in (".py", ".json") and not p.name.startswith("__")}
MODEL_INFO = {"name": "failure-response / safety-barrier rule chain (Chapter 5)", "files": MODEL_FILES}

STAKE = "0+000"   # every request is one evaluation unit; the caller's id is only echoed back
MODE_CODES = {"漫顶失效": "overtopping", "渗流破坏": "seepage", "边坡失稳": "slope_instability",
              "冲刷破坏": "scour", "穿堤建筑物失效": "crossing_structure"}
GRADES = {"A级_安全": ("A", "安全"), "B级_基本安全": ("B", "基本安全"), "C级_不安全": ("C", "不安全")}
GATE_CAPS = {"B": "B级_基本安全", "C": "C级_不安全"}
SOURCES = {"物理响应": "physical_response", "指标得分": "indicator_score"}
NOTICE = ("A/B/C为本研究评价等级（A≥80，40≤B<80，C<40），不等同于SL/Z 679-2015的一类/二类/三类堤，"
          "不能直接替代安全鉴定结论；结果的可信程度取决于输入资料的质量与时效。")

_FLAT_GROUPS = ("section.", "computation.", "survey.", "calculated.")
_FLAT_FIELDS = [f for f in schema.FIELDS
                if f.internal and f.path.startswith(_FLAT_GROUPS) and "[]" not in f.path
                and f.path != "section.section_id"]


class RequestInvalid(Exception):
    def __init__(self, details):
        super().__init__("request failed validation")
        self.details = details


def _get(obj, dotted):
    for key in dotted.split("."):
        if not isinstance(obj, dict) or key not in obj:
            return None
        obj = obj[key]
    return obj


def to_internal(req):
    """Return (sec, geo_cls, buildings, hist_dangers, leak_n) for evaluate_section()."""
    sec = {"桩号": STAKE, "软基段_沉降量_cm": None}
    for f in _FLAT_FIELDS:
        v = _get(req, f.path)
        if v is not None:
            sec[f.internal] = v
    layer_fields = [f for f in schema.FIELDS if f.path.startswith("section.soil_layers[].")]
    if req["section"].get("soil_layers"):
        sec["土层参数"] = [{f.internal: lay[f.path.split(".")[-1]] for f in layer_fields
                          if lay.get(f.path.split(".")[-1]) is not None}
                         for lay in req["section"]["soil_layers"]]
    sec["待输入指标"] = dict(req.get("qualitative") or {})

    rec = req["records"]
    geo_cls = [{"起始桩号": STAKE, "终止桩号": STAKE, "填土质量": rec["fill_quality"]}]
    cls = rec["crossing_structure_class"]
    buildings = [] if cls == "不涉及" else [{"桩号": STAKE, "检测结论": cls}]
    hist = []
    for h in rec["historical_dangers"]:
        item = {"起始桩号": STAKE, "终止桩号": STAKE, "险情类型": h["type"], "是否已加固": h["reinforced"]}
        if h.get("severity") is not None:
            item["严重程度"] = h["severity"]
        hist.append(item)
    return sec, geo_cls, buildings, hist, _leak_evidence(req.get("inspection"))


def _leak_evidence(ins):
    if not ins or ins["coverage"] != "complete":
        return None
    if ins.get("mode", "events") == "aggregated":
        a = ins["aggregated"]
        cap = GATE_CAPS.get(a.get("gate_cap"))
        return {"加权渗漏点密度_点每100m": float(a["weighted_density_per_100m"]),
                "UAV证据等级": a["evidence_level"], "UAV门控等级上限": cap,
                "UAV门控说明": a.get("note") or ("调用方汇总证据，" + ("无门控" if cap is None else f"门控上限{a['gate_cap']}级"))}
    pts = []
    for e in ins["confirmed_events"]:
        pts.append({"纬度": 0.0, "经度": 0.0, "是否人工确认": True,
                    "位置类型": e.get("position", "普通堤身"), "重复次数": e.get("repeat_count", 1),
                    "带砂": e.get("sand", False), "浑水": e.get("muddy", False),
                    "冒水": e.get("spouting", False), "集中成簇": e.get("clustered", False)})
    # one pseudo-location: every confirmed event already belongs to this unit
    evidence = SE.match_uav_leakage_evidence({"渗漏点列表": pts}, [{"桩号": STAKE, "纬度": 0.0, "经度": 0.0}],
                                             section_length_m=float(ins.get("segment_length_m", 100.0)),
                                             max_match_distance_m=None)
    return evidence[STAKE]


def _grade(g):
    code, label = GRADES.get(g, (None, g))
    return code, label


def _contrib_rows(rows):
    return [{"indicator": r["指标"], "score": r["指标得分"], "risk_response": r["风险响应"],
             "weight_in_mode": r["模式内权重"], "contribution": r["贡献值"], "contribution_rate": r["贡献率"],
             "source": SOURCES.get(r["来源"], r["来源"])} for r in rows]


def _inspection_out(leak, ins):
    if leak is None:
        return None
    out = {"mode": ins.get("mode", "events"),
           "weighted_density_per_100m": leak["加权渗漏点密度_点每100m"],
           "evidence_level": leak["UAV证据等级"],
           "gate_cap": _grade(leak["UAV门控等级上限"])[0] if leak.get("UAV门控等级上限") else None,
           "note": leak.get("UAV门控说明")}
    if "渗漏点数" in leak and out["mode"] == "events":
        out["event_count"] = leak["渗漏点数"]
        out["weighted_event_count"] = leak["加权渗漏点数"]
        out["segment_length_m"] = float(ins.get("segment_length_m", 100.0))
        out["events"] = [{"position_weight": d["位置权重"], "repeat_weight": d["重复权重"], "weighted_value": d["加权值"],
                          "sensitive_position": d["敏感位置"], "severe_sign": d["严重征兆"], "repeat_count": d["重复次数"]}
                         for d in leak["渗漏点明细"]]
    return out


def _seepage_checks(sec):
    ctrl = SE.controlling_soil_layer(sec)
    gs, e = float(ctrl["Gs"]), float(ctrl["e"])
    icr = SE.terzaghi_critical_gradient(gs, e)
    body_gs, body_e = float(sec.get("堤身Gs", gs)), float(sec.get("堤身e", e))
    body_icr = SE.terzaghi_critical_gradient(body_gs, body_e)
    rows = {}
    for code, key, cr, g, ee in (("C1", "渗透比降i", icr, gs, e), ("C4", "堤身渗透比降i", body_icr, body_gs, body_e),
                                 ("C5", "接触面渗透比降i", icr, gs, e)):
        ratio = SE.seepage_risk_ratio_terzaghi(sec[key], g, ee)
        rows[code] = {"gradient": sec[key], "critical_gradient": round(cr, 6), "ratio": round(ratio, 6),
                      "state": "critical" if ratio >= 1.0 else ("near_critical" if ratio >= 0.8 else "below_gate")}
    return {"control_layer": {"name": ctrl.get("土层名称"), "Gs": gs, "e": e}, **rows}


def _warnings(req, scores, missing):
    w = []
    rec, sv, ins = req["records"], req["survey"], req.get("inspection")
    q = req.get("qualitative") or {}

    def add(code, message, indicator=None):
        w.append({"code": code, "message": message, **({"indicator": indicator} if indicator else {})})

    if not ins or ins["coverage"] == "none":
        add("inspection_missing", "无有效巡检覆盖，C3按缺失处理，不触发观测门控；不能解读为未发现渗漏", "C3")
        if ins and ("confirmed_events" in ins or "aggregated" in ins):
            add("inspection_ignored", "coverage=none时传入的巡检事件或汇总证据未参与计算", "C3")
    if rec["crossing_structure_class"] == "不涉及":
        add("not_applicable_scored_100", "无穿堤建筑物（不涉及），A3按交付模型编码为100分", "A3")
    if sv.get("soft_foundation_settlement_cm") is None:
        add("not_applicable_scored_100", "未给出软基沉降（非软基段），A5按交付模型编码为100分", "A5")
    if "A6" not in q and not rec["historical_dangers"]:
        add("derived_from_records", "未给出qualitative.A6且历史险情记录为空，A6按“无隐患”计100分", "A6")
    if "A7" not in q:
        add("derived_from_records", f"A7由堤基类型{req['section']['foundation_class']}推定为{scores['A7']:g}分", "A7")
    if missing:
        add("indicators_missing", "以下指标缺失，已在模式内按现有权重归一化，不作满分处理：" + "、".join(missing))
    opt = req.get("options") or {}
    for key, default in (("alpha", 0.45), ("barrier_lambda", 0.5)):
        if key in opt and opt[key] != default:
            add("non_default_option", f"options.{key}={opt[key]}（默认{default}），结果与标准配置不可直接比较")
    return w


DETAIL_LEVELS = ("full", "summary")


def evaluate(req, *, validate=True, detail="full"):
    """Evaluate one request dict and return the response dict.  Raises RequestInvalid.

    detail="summary" omits result.contributions_by_mode (about half of the response size);
    the dominant mode's contributions are always returned.
    """
    if validate:
        errors = schema.validate(req)
        if errors:
            raise RequestInvalid(errors)
    sec, geo_cls, buildings, hist, leak = to_internal(req)
    opt = req.get("options") or {}
    r = M.evaluate_section(sec, geo_cls, buildings, hist, leak,
                           alpha=opt.get("alpha", 0.45), barrier_lambda=opt.get("barrier_lambda", 0.5))
    grade, label = _grade(r["安全等级"])
    dominant = r["主控失效模式"]
    modes = {MODE_CODES[m]: {"name": m, "weight": round(M.MODE_WEIGHTS[m], 6),
                             "raw": r["原始失效响应"][m], "adjusted": r["屏障修正响应"][m]} for m in M.FAILURE_MODES}
    result = {
        "score": r["安全得分"],
        "grade": grade,
        "grade_label": label,
        "model_grade": _grade(r["模型原始等级"])[0],
        "grade_after_observation_gate": _grade(r["UAV门控后等级"])[0],
        "gate_reasons": r["硬约束门控原因"],
        "rho": r["综合风险度量rho"],
        "dominant_mode": {"code": MODE_CODES.get(dominant), "name": dominant} if dominant else None,
        "barrier": {"ability": r["管理屏障能力"], "coverage": r["管理信息覆盖度"],
                    "lambda": opt.get("barrier_lambda", 0.5)},
        "observation_gate": {"cap": _grade(r["UAV观测门控上限"])[0] if r["UAV观测门控上限"] else None,
                             "note": r["UAV观测门控说明"]},
        "inspection_evidence": _inspection_out(leak, req.get("inspection") or {}),
        "mode_responses": modes,
        "indicator_scores": r["二级指标得分"],
        "missing_indicators": r["缺失指标"],
        "dominant_mode_contributions": _contrib_rows(r["主控模式指标贡献率"]),
        "contributions_by_mode": {MODE_CODES[m]: _contrib_rows(rows) for m, rows in r["全部失效模式指标贡献率"].items()},
        "seepage_checks": _seepage_checks(sec),
    }
    if detail == "summary":
        del result["contributions_by_mode"]
    canonical = json.dumps(req, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "request_id": req.get("request_id"),
        "section_id": req["section"]["section_id"],
        "api_version": API_VERSION,
        "model": MODEL_INFO,
        "result": result,
        "warnings": _warnings(req, r["二级指标得分"], r["缺失指标"]),
        "notice": NOTICE,
        "provenance": {"evaluated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       "input_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest()},
    }


def evaluate_batch(items, *, detail="full"):
    """Evaluate a list of requests independently; one bad item does not fail the batch."""
    if not isinstance(items, list):
        raise RequestInvalid([{"field": "items", "reason": "type_array_required"}])
    if not items:
        raise RequestInvalid([{"field": "items", "reason": "empty"}])
    if len(items) > schema.MAX_BATCH:
        raise RequestInvalid([{"field": "items", "reason": "too_many_items", "maximum": schema.MAX_BATCH}])
    out = []
    for k, req in enumerate(items):
        try:
            out.append({"index": k, "ok": True, "response": evaluate(req, detail=detail)})
        except RequestInvalid as exc:
            out.append({"index": k, "ok": False, "request_id": req.get("request_id") if isinstance(req, dict) else None,
                        "error": {"code": "validation_failed", "message": "请求字段校验未通过", "details": exc.details}})
        except Exception as exc:  # noqa: BLE001 - reported per item, never hides the rest of the batch
            out.append({"index": k, "ok": False, "request_id": req.get("request_id") if isinstance(req, dict) else None,
                        "error": {"code": "evaluation_failed", "message": f"{type(exc).__name__}: {exc}"}})
    ok = sum(x["ok"] for x in out)
    return {"api_version": API_VERSION, "count": len(out), "succeeded": ok, "failed": len(out) - ok, "results": out}


def meta():
    """Model constants, weights and category dictionaries (GET /api/v1/meta)."""
    rows = M.load_failure_mode_matrix()
    w1 = {"A": SE.W1_A, "B": SE.W1_B, "C": SE.W1_C, "D": SE.W1_D, "E": SE.W1_E}
    w2 = {**SE.W2_A, **SE.W2_B, **SE.W2_C, **SE.W2_D, **SE.W2_E}
    return {
        "api_version": API_VERSION,
        "model": MODEL_INFO,
        "indicators": [{"code": r["code"], "name": r["name"], "group_weight": w1[r["code"][0]],
                        "weight_in_group": w2[r["code"]], "modes": r["modes"],
                        "barrier_role": r.get("barrier_role"),
                        "qualitative_categories": SE.OPTIONAL_INDICATOR_SCORE_MAPS.get(r["code"])} for r in rows],
        "failure_modes": [{"code": MODE_CODES[m], "name": m, "weight": round(M.MODE_WEIGHTS[m], 6),
                           "indicator_weights": {k: round(v, 6) for k, v in M.MODE_INDICATOR_WEIGHTS[m].items()}}
                          for m in M.FAILURE_MODES],
        "fill_quality_scores": {"质量较好": 100, "质量一般": 80, "质量较差": 60},
        "crossing_structure_scores": {"一类": 100, "二类": 100, "三类": 70, "四类": 0, "1类": 100, "2类": 100,
                                      "3类": 70, "4类": 0, "加固": 100, "改建": 70, "重建": 0, "不涉及": 100},
        "inspection_position_weights": SE.UAV_LEAK_POSITION_WEIGHTS,
        "grades": [{"grade": "A", "label": "安全", "score_min": 80}, {"grade": "B", "label": "基本安全", "score_min": 40},
                   {"grade": "C", "label": "不安全", "score_min": 0}],
        "constants": {"std_crest_width_m": SE.STD_TOP_WIDTH, "std_outer_slope": SE.STD_OUTER_SLOPE,
                      "std_inner_slope": SE.STD_INNER_SLOPE, "freeboard_river_m": SE.FREEBOARD_RIVER,
                      "freeboard_lake_m": SE.FREEBOARD_LAKE, "fos_back_allow": SE.FOS_BACK_ALLOW,
                      "fos_front_allow": SE.FOS_FRONT_ALLOW, "settlement_allow_cm": SE.SETTLE_ALLOW,
                      "settlement_diff_allow_cm": SE.SETTLE_DIFF_ALLOW, "seepage_gate_B_ratio": 0.8,
                      "seepage_gate_C_ratio": 1.0},
        "options_default": {"alpha": 0.45, "barrier_lambda": 0.5},
        "max_batch": schema.MAX_BATCH,
        "notice": NOTICE,
    }
