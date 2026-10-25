"""Generate docs/03_parameter_dictionary.md, docs/openapi.json and examples/*.json from the code.

    python tools/gen_docs.py          # write
    python tools/gen_docs.py --check  # exit 1 if any generated file is out of date (used by tests)
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from levee_eval import engine, schema  # noqa: E402
from levee_eval.openapi import EXAMPLE_REQUEST, build_openapi  # noqa: E402

FIXED_TIME = "2026-10-22T00:00:00+00:00"   # examples carry a fixed timestamp so they do not churn

OUTPUT_FIELDS = [
    ("request_id", "string/null", "调用方请求编号（原样返回）"),
    ("section_id", "string", "评价单元编号（原样返回）"),
    ("api_version", "string", "接口版本"),
    ("model.files", "object", "模型文件名→sha256，用于确认服务端模型未被改动"),
    ("result.score", "number", "安全得分S=100(1−ρ)，0～100"),
    ("result.grade", "string", "最终评价等级A/B/C（得分分级→观测门控→硬约束门控，只降不升）"),
    ("result.grade_label", "string", "等级名称：安全/基本安全/不安全"),
    ("result.model_grade", "string", "仅按得分分级的等级（A≥80，40≤B<80，C<40）"),
    ("result.grade_after_observation_gate", "string", "经巡检观测门控后的等级"),
    ("result.gate_reasons", "string[]", "硬约束门控触发原因（交付模型原文；D3由险情记录触发时改写为说明记录的文字），为空表示未触发"),
    ("result.gates_not_checked[]", "object[]", "因缺资料未做的门控检查：indicator、reason（如未给安全系数时的D1/D2、无有效巡检时的C3）"),
    ("result.rho", "number", "综合风险度量ρ=α·max(Rk)+(1−α)·Σwk·Rk"),
    ("result.dominant_mode.code / name", "string", "主控失效模式（屏障修正后响应最大者）"),
    ("result.barrier.ability / coverage / lambda", "number", "运行管理屏障能力Bm、信息覆盖度、屏障强度λ"),
    ("result.observation_gate.cap / note", "string/null", "巡检观测门控上限（B/C/null）及说明"),
    ("result.inspection_evidence", "object/null", "巡检证据汇总：模式、加权密度、证据等级、事件明细；无有效巡检时为null"),
    ("result.mode_responses.<mode>", "object", "五类失效模式的权重、原始响应raw、屏障修正响应adjusted（0～1，越大越危险）"),
    ("result.mode_responses.<mode>.basis", "object", "该模式的资料支撑：direct_indicators（直接控制指标）、direct_missing（其中缺失的）、with_data / not_applicable / missing 计数；direct_missing非空时该模式响应依据不足"),
    ("result.indicator_scores.<code>", "number/null", "29项二级指标得分（0～100）；null为缺失"),
    ("result.missing_indicators", "string[]", "缺失指标代码；缺失指标不作满分处理，在模式内按现有权重归一化"),
    ("result.indicator_sources.<code>", "string", "各指标得分的资料来源：design_survey、computed、records、survey、survey_records、inspection、qualitative、calculated、not_applicable、missing；中文名见 /api/v1/meta 的 indicator_source_labels"),
    ("result.dominant_mode_contributions[]", "object[]", "主控模式内各指标的风险响应、模式内权重、贡献值和贡献率（降序）"),
    ("result.contributions_by_mode.<mode>[]", "object[]", "全部失效模式的指标贡献（detail=summary时省略）"),
    ("result.seepage_checks", "object", "控制土层及C1/C4/C5的比降、Terzaghi临界比降、i/i_cr与门控状态"),
    ("warnings[]", "object[]", "提示：code、message、indicator（见02_http_api.md第6节）"),
    ("notice", "string", "等级含义与使用限制的固定说明"),
    ("provenance.evaluated_at", "string", "评价时间（UTC，ISO 8601）"),
    ("provenance.input_sha256", "string", "请求体规范化JSON的sha256，用于追溯同一输入"),
]
MODE_ROWS = [("overtopping", "漫顶失效"), ("seepage", "渗流破坏"), ("slope_instability", "边坡失稳"),
             ("scour", "冲刷破坏"), ("crossing_structure", "穿堤建筑物失效")]
GROUPS = [("", "顶层"), ("section", "section：评价单元基本信息"), ("computation", "computation：渗流与稳定计算结果"),
          ("survey", "survey：测量与检查"), ("records", "records：台账与检查结论"),
          ("qualitative", "qualitative：定性指标结论"), ("calculated", "calculated：可替代定性结论的计算量"),
          ("inspection", "inspection：巡检证据"), ("options", "options：模型参数")]


def _range(f):
    if f.enum:
        return " / ".join(f.enum)
    lo = "" if f.minimum is None else (f">{f.minimum:g}" if f.exclusive_min else f"≥{f.minimum:g}")
    hi = "" if f.maximum is None else f"≤{f.maximum:g}"
    return "，".join(x for x in (lo, hi) if x)


def _cell(x):
    return str(x).replace("|", "\\|") if x not in (None, "") else ""


def dictionary_md():
    se = engine.SE
    out = ["# 输入输出参数字典", "",
           "> 本文件由 `tools/gen_docs.py` 根据 `levee_eval/schema.py` 自动生成，请勿手工修改。",
           "> 字段路径中 `[]` 表示数组元素；“必填”指其所在对象出现时必须给出。", "",
           "## 1 输入字段", ""]
    for prefix, title in GROUPS:
        rows = [f for f in schema.FIELDS
                if (f.path.split(".")[0] == prefix if prefix else "." not in f.path and f.path not in dict(GROUPS))]
        if not rows:
            continue
        out += [f"### {title}", "",
                "| 字段路径 | 类型 | 必填 | 单位 | 取值/范围 | 默认 | 对应指标 | 模型内部字段 | 说明 |",
                "|---|---|---|---|---|---|---|---|---|"]
        for f in rows:
            out.append("| " + " | ".join(_cell(x) for x in (
                f"`{f.path}`", f.type + ("，可null" if f.nullable else ""), "是" if f.required else "",
                f.unit, _range(f), json.dumps(f.default, ensure_ascii=False) if f.default is not None else "",
                f.indicator, f.internal, f.desc)) + " |")
        out.append("")
    out += ["### 交叉校验规则", "",
            "- `section.control_layer` 与 `section.soil_layers` 至少给出其一；都给出时以 control_layer 为准。",
            "- `section.foundation_class` 与 `qualitative.A7` 至少给出其一；都给出时A7以qualitative为准。",
            "- 给出 `survey.soft_foundation_settlement_cm` 时必须同时给出 `soft_foundation_settlement_diff_cm`，且不得填写 `soft_foundation_status`。",
            "- `inspection.coverage=complete` 且 `mode=events`（默认）时必须给出 `confirmed_events`（无事件传 `[]`），不得给出 `aggregated`；"
            "`mode=aggregated` 时必须给出 `aggregated`，不得给出 `confirmed_events`。",
            "- aggregated模式下证据等级与门控上限须符合交付规则：0级、1级无门控（gate_cap为null或不给），2级为B，3级为C；"
            "加权密度为0当且仅当证据等级为0。",
            "- 未声明的字段一律报 `unknown_field`，防止拼写错误被静默忽略。", "",
            "## 2 定性指标分档与赋分", "",
            "`qualitative` 的值可以是下表中的分档名称，也可以是0～100的数值得分。",
            "B2、B3、B4、D4 未在 `qualitative` 中给出时，可由 `calculated` 中的计算量换算；两者都没有则按缺失处理。", "",
            "| 指标 | 名称 | 分档：得分 |", "|---|---|---|"]
    names = {r["code"]: r["name"] for r in engine.M.load_failure_mode_matrix()}
    for code, cats in schema.QUALITATIVE_CATEGORIES.items():
        m = se.OPTIONAL_INDICATOR_SCORE_MAPS[code]
        out.append(f"| {code} | {names[code]} | " + "；".join(f"{c}：{m[c]}" for c in cats) + " |")
    meta = engine.meta()
    out += ["", "其他由台账字段换算的指标：", "",
            "| 指标 | 来源字段 | 换算 |", "|---|---|---|",
            "| A2 填土质量 | records.fill_quality | " + "；".join(f"{k}：{v}" for k, v in meta["fill_quality_scores"].items()) + " |",
            "| A3 穿堤建筑物完好性 | records.crossing_structure_class | " + "；".join(f"{k}：{v}" for k, v in meta["crossing_structure_scores"].items()) + " |",
            "| A6 内部隐患 | qualitative.A6，否则records.historical_dangers | 多条记录取最低；有severity按A6分档；否则类型含“蚁”或“隐患”：未加固0、已加固80；其他类型：未加固60、已加固不扣分；无记录100 |",
            "| A7 堤基不良地质处理 | qualitative.A7，否则section.foundation_class | C类70分，D类60分，A/B类100分 |",
            "| D3 堤岸冲刷稳定性 | survey.scour_depth_m＋records.historical_dangers | 冲刷≥1.0 m或有未加固的重大险情记录（类型含“崩”、管涌、散浸、渗漏）：0；冲刷≥0.5 m或有已加固的重大险情记录：70；否则100。未给冲刷深度：有未加固的重大险情记录仍为0，否则缺失 |",
            "| A5 软基段沉降 | survey.soft_foundation_settlement_cm、soft_foundation_settlement_diff_cm、soft_foundation_status | 沉降量≤15 cm且沉降差≤5 cm：100，否则0。未给沉降量：soft_foundation_status=non_soft（默认）按100分，unknown按缺失 |",
            "| D1、D2 抗滑稳定 | computation.back_slope_fos、front_slope_fos | 按安全系数分段评分（见第5章）；未给安全系数：缺失，不做该侧稳定门控 |",
            "| C3 管涌隐患（巡检） | inspection | 加权密度0：100；≤1：80；≤2：60；≤4：40；>4：0（点/100 m）；无有效巡检：缺失 |",
            "", "巡检事件位置权重：" + "，".join(f"{k} {v}" for k, v in meta["inspection_position_weights"].items())
            + "；重复2次×1.2，≥3次×1.5。", "",
            "## 3 输出字段", "", "| 字段 | 类型 | 说明 |", "|---|---|---|"]
    out += [f"| `{p}` | {t} | {d} |" for p, t, d in OUTPUT_FIELDS]
    out += ["", "失效模式代码：" + "，".join(f"`{c}` {n}" for c, n in MODE_ROWS) + "。", "",
            "## 4 错误码", "", "| HTTP状态 | error.code | 含义 |", "|---|---|---|",
            "| 400 | invalid_json / invalid_query | 请求体不是合法UTF-8 JSON；detail参数非法 |",
            "| 401 | unauthorized | 启用API Key时缺少或错误的 X-API-Key |",
            "| 404 | not_found | 路径不存在 |", "| 405 | method_not_allowed | 方法不对（GET/POST） |",
            "| 413 | payload_too_large | 请求体超过上限（默认5 MB） |",
            "| 415 | unsupported_media_type | Content-Type 不是 application/json |",
            "| 422 | validation_failed | 字段校验未通过，`error.details[]` 逐项给出 field 与 reason |",
            "| 500 | internal_error | 服务内部错误，凭 trace_id 查日志 |", "",
            "`error.details[].reason` 取值：required、unknown_field、type_<类型>_required、not_in_enum、below_minimum、"
            "above_maximum、unknown_indicator、score_out_of_range_0_100、category_or_score_required、"
            "control_layer_or_soil_layers_required、foundation_class_or_qualitative_A7_required、"
            "required_when_settlement_given、not_allowed_when_settlement_given、required_in_events_mode_empty_list_if_none、required_in_aggregated_mode、"
            "not_allowed_in_events_mode、not_allowed_in_aggregated_mode、inconsistent_with_evidence_level、"
            "inconsistent_with_density、too_many_items、empty。", ""]
    return "\n".join(out)


def _response(req, **kw):
    r = engine.evaluate(req, **kw)
    r["provenance"]["evaluated_at"] = FIXED_TIME
    return r


def examples():
    full = copy.deepcopy(EXAMPLE_REQUEST)
    aggregated = copy.deepcopy(EXAMPLE_REQUEST)
    aggregated["request_id"] = "demo-0002"
    aggregated["inspection"] = {"coverage": "complete", "mode": "aggregated", "aggregated": {
        "weighted_density_per_100m": 1.2, "evidence_level": 2, "gate_cap": "B", "note": "调用方系统按交付规则汇总"}}
    minimal = copy.deepcopy(EXAMPLE_REQUEST)
    minimal["request_id"] = "demo-0003"
    minimal["section"].pop("soil_layers")
    minimal.pop("qualitative")
    minimal.pop("calculated")
    minimal.pop("inspection")
    invalid = copy.deepcopy(EXAMPLE_REQUEST)
    invalid["request_id"] = "demo-0004"
    invalid["section"]["crest_elevation_m"] = "36.84"
    invalid["records"]["fill_quality"] = "较好"
    invalid["computation"].pop("foundation_gradient")
    invalid["qualitative"]["E1"] = "良好"
    invalid_resp = {"error": {"code": "validation_failed", "message": "请求字段校验未通过",
                              "details": schema.validate(invalid)}, "trace_id": "<服务端生成或回传X-Request-ID>"}
    data_only = copy.deepcopy(EXAMPLE_REQUEST)   # only inputs that site data usually supports
    data_only["request_id"] = "demo-0005"
    data_only["section"].pop("soil_layers")
    for key in ("back_slope_fos", "front_slope_fos"):
        data_only["computation"].pop(key)
    data_only["survey"] = {"soft_foundation_status": "unknown"}
    data_only["qualitative"] = {"A8": "不涉及", "A9": "不涉及", "B2": "符合", "B4": "不涉及", "C6": "不涉及", "D4": "不涉及"}
    data_only.pop("calculated")
    data_only.pop("inspection")
    batch = {"items": [full, aggregated, invalid]}
    batch_resp = engine.evaluate_batch(batch["items"], detail="summary")
    for item in batch_resp["results"]:
        if item["ok"]:
            item["response"]["provenance"]["evaluated_at"] = FIXED_TIME
    return {
        "request_full.json": full, "response_full.json": _response(full),
        "request_aggregated.json": aggregated, "response_aggregated_summary.json": _response(aggregated, detail="summary"),
        "request_minimal_no_inspection.json": minimal, "response_minimal_no_inspection.json": _response(minimal),
        "request_data_supported.json": data_only, "response_data_supported.json": _response(data_only),
        "request_invalid.json": invalid, "response_invalid_422.json": invalid_resp,
        "request_batch.json": batch, "response_batch_summary.json": batch_resp,
    }


def targets():
    t = {ROOT / "docs" / "03_parameter_dictionary.md": dictionary_md(),
         ROOT / "docs" / "openapi.json": json.dumps(build_openapi(), ensure_ascii=False, indent=2) + "\n"}
    for name, obj in examples().items():
        t[ROOT / "examples" / name] = json.dumps(obj, ensure_ascii=False, indent=2) + "\n"
    return t


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    stale = []
    for path, text in targets().items():
        old = path.read_text(encoding="utf-8") if path.exists() else None
        if old != text:
            stale.append(path.relative_to(ROOT).as_posix())
            if not args.check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
    if args.check:
        print("out of date: " + ", ".join(stale) if stale else "generated files are up to date")
        return 1 if stale else 0
    print("wrote: " + (", ".join(stale) or "nothing (up to date)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
