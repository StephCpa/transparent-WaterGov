"""Evaluation engine: JSON request -> delivered rule-chain model -> JSON response.

The model files in model/ are the delivered code, copied unchanged (sha256 in MODEL_FILES).
This module only translates field names, builds the auxiliary lists the delivered
evaluate_section() expects for a single evaluation unit, and translates the result back.

A few delivered functions are wrapped at import time so that inputs the delivered code requires
can be absent; an absent input then makes its indicator missing and skips its gate, instead of
raising or defaulting to a full score.  Whenever the input is present the wrapper calls the
delivered function unchanged (the 875-sample regression test checks this):

  C3      no valid inspection                   (delivered score_C3 raises on None)
  D1, D2  no slope-stability safety factor      (delivered code indexes the FoS directly)
  D3      no scour depth                        (still 0 when an unrepaired major danger exists)
  A5      settlement status unknown             (delivered code scores a missing settlement as 100)
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import schema

API_VERSION = "1.1.0"
MODEL_DIR = Path(__file__).resolve().parent / "model"
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))

import failure_response_barrier_model as M  # noqa: E402
import safety_evaluation as SE  # noqa: E402

_delivered = {name: getattr(M, name) for name in ("score_C3", "score_D1", "score_D2", "score_D3", "score_A5",
                                                  "slope_response", "mode_contribution_overrides",
                                                  "hard_constraint_gate")}
_BACK, _FRONT, _SCOUR, _SETTLE = "背水坡FoS_正常", "临水坡FoS", "冲刷深度_m", "软基段_沉降量_cm"
_A5_UNKNOWN = "_软基状态未知"   # internal flag set by to_internal(); not a delivered field
_NO_GATE_FOS = 99.0            # stands in for an absent FoS only inside the gate check; never scored
MAJOR_DANGER_KEYS = ("崩", "管涌", "散浸", "渗漏")   # delivered score_D3's notion of a major danger


def _has(sec, key):
    return sec.get(key) is not None


def _score_C3(leak_n):
    return None if leak_n is None else _delivered["score_C3"](leak_n)


def _score_D1(sec):
    return _delivered["score_D1"](sec) if _has(sec, _BACK) else None


def _score_D2(sec):
    return _delivered["score_D2"](sec) if _has(sec, _FRONT) else None


def _score_D3(sec, hist):
    if _has(sec, _SCOUR):
        return _delivered["score_D3"](sec, hist)
    # without a depth only an unrepaired major danger decides D3: the delivered rule gives 0 at any depth
    return 0 if _delivered["score_D3"]({**sec, _SCOUR: 0.0}, hist) == 0 else None


def _score_A5(sec):
    return None if sec.get(_A5_UNKNOWN) else _delivered["score_A5"](sec)


def _with_fos_placeholders(sec):
    return {**sec, **{k: _NO_GATE_FOS for k in (_BACK, _FRONT) if not _has(sec, k)}}


def _slope_response(sec, scores):
    if _has(sec, _BACK) and _has(sec, _FRONT):
        return _delivered["slope_response"](sec, scores)
    overrides = {}   # same rule as the delivered slope_response, for the side that has a FoS
    for key, code, allow in ((_BACK, "D1", SE.FOS_BACK_ALLOW), (_FRONT, "D2", SE.FOS_FRONT_ALLOW)):
        if _has(sec, key):
            fos = float(sec[key])
            if fos < 1.0:
                return 1.0
            overrides[code] = M.clamp01((allow - fos) / (allow - 1.0))
    return M.mode_weighted_response("边坡失稳", scores, overrides=overrides)


def _mode_contribution_overrides(sec):
    out = _delivered["mode_contribution_overrides"](_with_fos_placeholders(sec))
    for key, code in ((_BACK, "D1"), (_FRONT, "D2")):
        if not _has(sec, key):
            out["边坡失稳"].pop(code, None)
    return out


def _hard_constraint_gate(sec, scores, grade):
    return _delivered["hard_constraint_gate"](_with_fos_placeholders(sec), scores, grade)


M.score_C3, M.score_D1, M.score_D2, M.score_D3, M.score_A5 = _score_C3, _score_D1, _score_D2, _score_D3, _score_A5
M.slope_response = _slope_response
M.mode_contribution_overrides = _mode_contribution_overrides
M.hard_constraint_gate = _hard_constraint_gate


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
    if req["survey"].get("soft_foundation_status") == "unknown":
        sec[_A5_UNKNOWN] = True

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


def _rewrite_d3_reason(reasons, req, scores):
    """The delivered D3 gate message names only the scour depth, also when the 70 or the 0 comes
    from the danger records; state what actually set it.  Scores and caps are unchanged."""
    d3, scour = scores.get("D3"), req["survey"].get("scour_depth_m")
    majors = [h for h in req["records"]["historical_dangers"] if any(k in h["type"] for k in MAJOR_DANGER_KEYS)]

    def names(reinforced):
        return "、".join(dict.fromkeys(h["type"] for h in majors if h["reinforced"] is reinforced))

    if d3 == 0 and (scour is None or scour < 1.0):
        text = f"D3堤岸冲刷稳定性: 有未加固的重大险情记录（{names(False)}），按严重冲刷计0分"
    elif d3 == 70 and scour is not None and scour < 0.5:
        text = f"D3堤岸冲刷稳定性: 冲刷深度{scour:.2f}m未达0.5m，因有已加固的重大险情记录（{names(True)}）计70分，存在冲刷风险"
    else:
        return reasons
    return [text if r.startswith("D3") else r for r in reasons]


def _gates_not_checked(req, scores, leak):
    comp, sv = req["computation"], req["survey"]
    out = []
    if comp.get("back_slope_fos") is None:
        out.append({"indicator": "D1", "reason": "未提供背水坡抗滑稳定安全系数，未做背水坡稳定门控"})
    if comp.get("front_slope_fos") is None:
        out.append({"indicator": "D2", "reason": "未提供临水坡抗滑稳定安全系数，未做临水坡稳定门控"})
    if sv.get("scour_depth_m") is None and scores.get("D3") is None:
        out.append({"indicator": "D3", "reason": "未提供冲刷深度，未做冲刷门控"})
    if sv.get("soft_foundation_status") == "unknown":
        out.append({"indicator": "A5", "reason": "软基沉降资料缺失，未做沉降门控"})
    if leak is None:
        out.append({"indicator": "C3", "reason": "无有效巡检，未做观测门控"})
    return out


INDICATOR_SOURCE_LABELS = {"design_survey": "设计或测量资料", "computed": "渗流或稳定计算", "records": "地勘与台账资料",
                           "survey": "监测资料", "survey_records": "测量与险情记录", "inspection": "巡检证据",
                           "qualitative": "定性结论", "calculated": "复核计算量", "not_applicable": "不涉及",
                           "missing": "缺失（未参与评价）"}


def _indicator_sources(req, scores):
    """Which kind of input each indicator score came from (keys of INDICATOR_SOURCE_LABELS)."""
    q, sv, rec = req.get("qualitative") or {}, req["survey"], req["records"]
    out = {}
    for code, score in scores.items():
        if score is None:
            out[code] = "missing"
        elif code in q:
            out[code] = "not_applicable" if q[code] == "不涉及" else "qualitative"
        elif code in ("C1", "C4", "C5", "D1", "D2"):
            out[code] = "computed"
        elif code in ("A1", "B1"):
            out[code] = "design_survey"
        elif code == "A5":
            out[code] = "survey" if sv.get("soft_foundation_settlement_cm") is not None else "not_applicable"
        elif code == "A3":
            out[code] = "not_applicable" if rec["crossing_structure_class"] == "不涉及" else "records"
        elif code == "D3":
            out[code] = "survey_records" if sv.get("scour_depth_m") is not None else "records"
        elif code in ("A2", "A6", "A7"):
            out[code] = "records"
        elif code in ("B2", "B3", "B4", "D4"):
            out[code] = "calculated"
        elif code == "C3":
            out[code] = "inspection"
        else:
            out[code] = "qualitative"
    return out


_MATRIX = {r["code"]: r["modes"] for r in M.load_failure_mode_matrix()}


def _mode_basis(mode, sources):
    """How well a failure-mode response is supported: its direct-control indicators (association
    strength 3 in the delivered matrix), which of them are missing, and counts by source."""
    codes = list(M.MODE_INDICATOR_WEIGHTS[mode])
    direct = [c for c in codes if float(_MATRIX[c].get(mode, 0)) >= 3]
    return {"direct_indicators": direct,
            "direct_missing": [c for c in direct if sources[c] == "missing"],
            "with_data": sum(sources[c] not in ("missing", "not_applicable") for c in codes),
            "not_applicable": sum(sources[c] == "not_applicable" for c in codes),
            "missing": sum(sources[c] == "missing" for c in codes)}


def _warnings(req, scores, missing):
    w = []
    rec, sv, ins, comp = req["records"], req["survey"], req.get("inspection"), req["computation"]
    q = req.get("qualitative") or {}

    def add(code, message, indicator=None):
        w.append({"code": code, "message": message, **({"indicator": indicator} if indicator else {})})

    if not ins or ins["coverage"] == "none":
        add("inspection_missing", "无有效巡检覆盖，C3按缺失处理，不触发观测门控；不能解读为未发现渗漏", "C3")
        if ins and ("confirmed_events" in ins or "aggregated" in ins):
            add("inspection_ignored", "coverage=none时传入的巡检事件或汇总证据未参与计算", "C3")
    for key, code, what in (("back_slope_fos", "D1", "背水坡"), ("front_slope_fos", "D2", "临水坡")):
        if comp.get(key) is None:
            add("input_missing_no_gate", f"未提供{what}抗滑稳定安全系数，{code}按缺失处理，未做{what}稳定门控", code)
    if sv.get("scour_depth_m") is None:
        if scores.get("D3") == 0:
            add("input_missing_no_gate", "未提供冲刷深度；因有未加固的重大险情记录，D3按交付规则计0分", "D3")
        else:
            add("input_missing_no_gate", "未提供冲刷深度，D3按缺失处理，未做冲刷门控", "D3")
    if rec["crossing_structure_class"] == "不涉及":
        add("not_applicable_scored_100", "无穿堤建筑物（不涉及），A3按交付模型编码为100分", "A3")
    if sv.get("soft_foundation_status") == "unknown":
        add("input_missing_no_gate", "软基沉降资料缺失，A5按缺失处理，未做沉降门控", "A5")
    elif sv.get("soft_foundation_settlement_cm") is None:
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
    sources = _indicator_sources(req, r["二级指标得分"])
    modes = {MODE_CODES[m]: {"name": m, "weight": round(M.MODE_WEIGHTS[m], 6),
                             "raw": r["原始失效响应"][m], "adjusted": r["屏障修正响应"][m],
                             "basis": _mode_basis(m, sources)} for m in M.FAILURE_MODES}
    result = {
        "score": r["安全得分"],
        "grade": grade,
        "grade_label": label,
        "model_grade": _grade(r["模型原始等级"])[0],
        "grade_after_observation_gate": _grade(r["UAV门控后等级"])[0],
        "gate_reasons": _rewrite_d3_reason(r["硬约束门控原因"], req, r["二级指标得分"]),
        "gates_not_checked": _gates_not_checked(req, r["二级指标得分"], leak),
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
        "indicator_sources": sources,
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
        "indicator_source_labels": INDICATOR_SOURCE_LABELS,
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
