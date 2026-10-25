"""OpenAPI 3.0 document built from schema.FIELDS (served at /api/v1/openapi.json)."""

from __future__ import annotations

from . import engine, schema

EXAMPLE_REQUEST = {
    "request_id": "demo-0001",
    "section": {
        "section_id": "DEMO-K0+500",
        "is_lake_levee": False,
        "crest_elevation_m": 36.84,
        "design_flood_level_m": 34.04,
        "crest_width_m": 8.5,
        "outer_slope_ratio": 3.0,
        "inner_slope_ratio": 3.2,
        "foundation_class": "B",
        "control_layer": {"name": "粉细砂（合成示例）", "Gs": 2.65, "e": 0.70, "J_allow": 0.25},
        "soil_layers": [
            {"name": "粉质黏土（合成示例）", "Gs": 2.72, "e": 0.82, "thickness_m": 3.5, "k_cm_s": 2.0e-5, "J_allow": 0.45},
            {"name": "粉细砂（合成示例）", "Gs": 2.65, "e": 0.70, "thickness_m": 2.0, "k_cm_s": 4.88e-3, "J_allow": 0.25},
        ],
    },
    "computation": {
        "foundation_gradient": 0.82,
        "body_gradient": 0.30,
        "contact_gradient": 0.45,
        "back_slope_fos": 1.42,
        "front_slope_fos": 1.38,
    },
    "survey": {"scour_depth_m": 0.2, "soft_foundation_settlement_cm": None},
    "records": {"fill_quality": "质量一般", "crossing_structure_class": "不涉及", "historical_dangers": [
        {"type": "蚁穴", "reinforced": True, "severity": "轻微"}]},
    "qualitative": {"A4": "良", "A8": "不涉及", "A9": "不涉及", "B2": "符合", "B4": "不涉及", "C2": "一般", "C6": "不涉及",
                    "D4": "不涉及", "D5": "轻微", "E1": "一般", "E2": "基本健全", "E3": "基本满足",
                    "E4": "基本满足", "E5": "部分处置"},
    "calculated": {"overtopping": {"discharge": 0.0, "allowable_discharge": 0.02}},
    "inspection": {"coverage": "complete", "mode": "events", "segment_length_m": 100,
                   "confirmed_events": [{"position": "堤脚", "repeat_count": 1, "sand": False, "muddy": False,
                                         "spouting": False, "clustered": False}]},
}


def _node(path):
    f = schema.BY_PATH.get(path)
    if f is None:          # array item container
        node = {"type": "object"}
    elif f.type == "object" and path == "qualitative":
        node = {"type": "object", "description": f.desc,
                "properties": {code: {"description": f"{code}：分档名称或0～100分",
                                      "oneOf": [{"type": "string", "enum": cats},
                                                {"type": "number", "minimum": 0, "maximum": 100}]}
                               for code, cats in schema.QUALITATIVE_CATEGORIES.items()},
                "additionalProperties": False}
        return node
    else:
        node = {"type": f.type}
        desc = f.desc + (f"（单位：{f.unit}）" if f.unit else "")
        if desc:
            node["description"] = desc
        if f.enum:
            node["enum"] = list(f.enum)
        if f.minimum is not None:
            node["minimum"] = f.minimum
            if f.exclusive_min:
                node["exclusiveMinimum"] = True
        if f.maximum is not None:
            node["maximum"] = f.maximum
        if f.nullable:
            node["nullable"] = True
        if f.default is not None:
            node["default"] = f.default
        if f.internal:
            node["x-internal-name"] = f.internal
        if f.indicator:
            node["x-indicator"] = f.indicator
    if node["type"] == "object":
        kids = [x for x in schema.FIELDS if x.path.startswith(path + ".") and "." not in x.path[len(path) + 1:]]
        node["properties"] = {x.path.split(".")[-1]: _node(x.path) for x in kids}
        req = [x.path.split(".")[-1] for x in kids if x.required]
        if req:
            node["required"] = req
        node["additionalProperties"] = False
    if node["type"] == "array":
        item = path + "[]"
        node["items"] = _node(item) if any(x.path.startswith(item + ".") for x in schema.FIELDS) else {}
    return node


def request_schema():
    top = [f for f in schema.FIELDS if "." not in f.path]
    return {"type": "object", "properties": {f.path: _node(f.path) for f in top},
            "required": [f.path for f in top if f.required], "additionalProperties": False}


_NUM = {"type": "number"}
_NUM_N = {"type": "number", "nullable": True}
_STR_N = {"type": "string", "nullable": True}
_GRADE = {"type": "string", "enum": ["A", "B", "C"], "nullable": True}
_CONTRIB = {"type": "object", "properties": {
    "indicator": {"type": "string"}, "score": _NUM_N, "risk_response": _NUM_N, "weight_in_mode": _NUM,
    "contribution": _NUM_N, "contribution_rate": _NUM_N,
    "source": {"type": "string", "enum": ["physical_response", "indicator_score"]}}}
_MODE_ENUM = ["overtopping", "seepage", "slope_instability", "scour", "crossing_structure"]
_ERROR_BODY = {"type": "object", "properties": {
    "code": {"type": "string"}, "message": {"type": "string"},
    "details": {"type": "array", "items": {"type": "object", "properties": {
        "field": {"type": "string"}, "reason": {"type": "string"}}}}}}
_ERROR = {"type": "object", "properties": {"error": {"$ref": "#/components/schemas/ErrorBody"},
                                           "trace_id": {"type": "string"}}}


def response_schema():
    seep = {"type": "object", "properties": {"gradient": _NUM, "critical_gradient": _NUM, "ratio": _NUM,
                                             "state": {"type": "string", "enum": ["below_gate", "near_critical", "critical"]}}}
    return {"type": "object", "properties": {
        "request_id": _STR_N, "section_id": {"type": "string"}, "api_version": {"type": "string"},
        "model": {"type": "object", "description": "模型名称与各模型文件sha256"},
        "result": {"type": "object", "properties": {
            "score": {**_NUM, "description": "安全得分S=100(1-ρ)"},
            "grade": {**_GRADE, "description": "最终等级（经观测门控与硬约束门控）"},
            "grade_label": {"type": "string"},
            "model_grade": {**_GRADE, "description": "仅按得分划分的等级"},
            "grade_after_observation_gate": _GRADE,
            "gate_reasons": {"type": "array", "items": {"type": "string"}, "description": "硬约束门控触发原因"},
            "conclusion_text": {"type": "string", "description": "一句话结论：决定最终等级的限级条件（无则为得分）、等级、主要风险、因缺资料未做的检查（v1.2）"},
            "gate_details": {"type": "array", "description": "逐条限级（门控）：indicator、kind（hard硬约束/observation巡检）、cap（B/C）、reason（原文）、plain（通俗说明）（v1.2）",
                             "items": {"type": "object", "properties": {"indicator": {"type": "string"}, "kind": {"type": "string", "enum": ["hard", "observation"]},
                                                                         "cap": {"type": "string", "enum": ["B", "C"]}, "reason": _STR_N, "plain": {"type": "string"}}}},
            "gates_not_checked": {"type": "array", "description": "因缺资料未做的门控检查（v1.1）", "items": {"type": "object", "properties": {
                "indicator": {"type": "string"}, "reason": {"type": "string"}}}},
            "rho": {**_NUM, "description": "综合风险度量ρ"},
            "dominant_mode": {"type": "object", "nullable": True, "properties": {
                "code": {"type": "string", "enum": _MODE_ENUM}, "name": {"type": "string"}}},
            "barrier": {"type": "object", "properties": {"ability": _NUM_N, "coverage": _NUM, "lambda": _NUM}},
            "observation_gate": {"type": "object", "properties": {"cap": _GRADE, "note": _STR_N}},
            "inspection_evidence": {"type": "object", "nullable": True},
            "mode_responses": {"type": "object", "additionalProperties": {"type": "object", "properties": {
                "name": {"type": "string"}, "weight": _NUM, "raw": _NUM_N, "adjusted": _NUM_N,
                "basis": {"type": "object", "description": "该模式的资料支撑（v1.1）：直接控制指标（关联强度3）、其中缺失的指标、按来源计数",
                          "properties": {"direct_indicators": {"type": "array", "items": {"type": "string"}},
                                         "direct_missing": {"type": "array", "items": {"type": "string"}},
                                         "with_data": {"type": "integer"}, "not_applicable": {"type": "integer"},
                                         "missing": {"type": "integer"}}}}}},
            "indicator_scores": {"type": "object", "additionalProperties": _NUM_N},
            "missing_indicators": {"type": "array", "items": {"type": "string"}},
            "indicator_sources": {"type": "object", "description": "各指标的资料来源（v1.1），中文名见 /api/v1/meta 的 indicator_source_labels",
                                  "additionalProperties": {"type": "string", "enum": ["design_survey", "computed", "records", "survey",
                                                                                       "survey_records", "inspection", "qualitative",
                                                                                       "calculated", "not_applicable", "missing"]}},
            "dominant_mode_contributions": {"type": "array", "items": _CONTRIB},
            "contributions_by_mode": {"type": "object", "description": "detail=summary时省略",
                                      "additionalProperties": {"type": "array", "items": _CONTRIB}},
            "seepage_checks": {"type": "object", "properties": {
                "control_layer": {"type": "object"}, "C1": seep, "C4": seep, "C5": seep}},
        }},
        "warnings": {"type": "array", "items": {"type": "object", "properties": {
            "code": {"type": "string"}, "message": {"type": "string"}, "indicator": {"type": "string"}}}},
        "notice": {"type": "string"},
        "provenance": {"type": "object", "properties": {"evaluated_at": {"type": "string", "format": "date-time"},
                                                        "input_sha256": {"type": "string"}}},
    }}


def build_openapi():
    errs = {str(c): {"description": d, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}}
            for c, d in ((400, "请求体不是合法JSON"), (401, "缺少或错误的X-API-Key"), (413, "请求体过大"),
                         (415, "Content-Type不是application/json"), (422, "字段校验未通过（details逐项列出）"),
                         (500, "服务内部错误"))}
    detail = [{"name": "detail", "in": "query", "required": False,
               "description": "full（默认）返回全部失效模式的指标贡献；summary省略result.contributions_by_mode，仅保留主控模式贡献",
               "schema": {"type": "string", "enum": ["full", "summary"], "default": "full"}}]
    json_body = lambda ref: {"required": True, "content": {"application/json": {"schema": {"$ref": ref}}}}  # noqa: E731
    ok = lambda ref, d: {"200": {"description": d, "content": {"application/json": {"schema": {"$ref": ref}}}}}  # noqa: E731
    return {
        "openapi": "3.0.3",
        "info": {"title": "堤防渗流安全评价服务", "version": engine.API_VERSION,
                 "description": "失效响应—安全屏障规则链评价模型的HTTP接口。" + engine.NOTICE},
        "servers": [{"url": "http://localhost:8080"}],
        "components": {
            "securitySchemes": {"ApiKey": {"type": "apiKey", "in": "header", "name": "X-API-Key"}},
            "schemas": {
                "EvaluateRequest": {**request_schema(), "example": EXAMPLE_REQUEST},
                "EvaluateResponse": response_schema(),
                "BatchRequest": {"type": "object", "required": ["items"], "additionalProperties": False,
                                 "properties": {"items": {"type": "array", "maxItems": schema.MAX_BATCH,
                                                          "items": {"$ref": "#/components/schemas/EvaluateRequest"}}}},
                "BatchResponse": {"type": "object", "properties": {
                    "api_version": {"type": "string"}, "count": {"type": "integer"},
                    "succeeded": {"type": "integer"}, "failed": {"type": "integer"},
                    "results": {"type": "array", "items": {"type": "object", "properties": {
                        "index": {"type": "integer"}, "ok": {"type": "boolean"},
                        "response": {"$ref": "#/components/schemas/EvaluateResponse"},
                        "error": {"$ref": "#/components/schemas/ErrorBody"}}}}}},
                "Error": _ERROR,
                "ErrorBody": _ERROR_BODY,
            },
        },
        "security": [{"ApiKey": []}],
        "paths": {
            "/api/v1/health": {"get": {"summary": "健康检查（不需要API Key）", "security": [],
                                       "responses": {"200": {"description": "服务正常"}}}},
            "/api/v1/meta": {"get": {"summary": "权重、分档、等级阈值与常数",
                                     "responses": {"200": {"description": "模型元数据"}, "401": errs["401"]}}},
            "/api/v1/openapi.json": {"get": {"summary": "本文档", "responses": {"200": {"description": "OpenAPI文档"}}}},
            "/api/v1/evaluate": {"post": {
                "summary": "单个评价单元评价", "parameters": detail,
                "requestBody": json_body("#/components/schemas/EvaluateRequest"),
                "responses": {**ok("#/components/schemas/EvaluateResponse", "评价结果"), **errs}}},
            "/api/v1/evaluate/batch": {"post": {
                "summary": f"批量评价（≤{schema.MAX_BATCH}个；单项失败不影响其他项）", "parameters": detail,
                "requestBody": json_body("#/components/schemas/BatchRequest"),
                "responses": {**ok("#/components/schemas/BatchResponse", "逐项结果"), **errs}}},
        },
    }
