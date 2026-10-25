"""Request schema of the levee seepage-safety evaluation service (single source of truth).

Every request field is declared once here.  The validator, the internal field mapping, the
OpenAPI document and the parameter dictionary in docs/ are all generated from FIELDS, so the
documentation cannot drift from the code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

QUALITATIVE_CATEGORIES = {   # categories accepted by the delivered code (OPTIONAL_INDICATOR_SCORE_MAPS)
    "A4": ["优", "良", "中", "一般", "差", "极差"],
    "A6": ["无", "轻微", "中度", "严重"],
    "A7": ["良好", "一般", "未处理", "险情"],
    "A8": ["不涉及", "密实", "良好", "轻微渗漏", "集中渗漏", "严重渗漏"],
    "A9": ["不涉及", "无影响", "轻微影响", "存在危险", "危险"],
    "B2": ["符合", "待复核", "不符合"],
    "B3": ["满足", "待复核", "略超标", "严重超标", "超标"],
    "B4": ["不涉及", "完全符合", "符合", "待复核", "高程不足", "不达标"],
    "C2": ["通畅", "一般", "局部淤积", "局部堵塞", "失效"],
    "C6": ["不涉及", "无渗漏", "明显渗漏", "失稳", "带砂"],
    "D4": ["不涉及", "全部满足", "满足", "临界状态", "临界", "不满足"],
    "D5": ["无", "轻微", "明显", "严重"],
    "E1": ["完善", "一般", "差"],
    "E2": ["健全", "基本健全", "不健全"],
    "E3": ["完备", "基本满足", "缺失"],
    "E4": ["完备", "基本满足", "严重缺失", "缺失"],
    "E5": ["全部处置", "部分处置", "未执行"],
}
POSITIONS = ["普通堤身", "堤身", "堤坡", "堤脚", "坡脚", "穿堤建筑物", "建筑物附近", "结合部", "历史险情附近"]
BUILDING_CLASSES = ["一类", "二类", "三类", "四类", "1类", "2类", "3类", "4类", "加固", "改建", "重建", "不涉及"]


@dataclass(frozen=True)
class Field:
    path: str                      # dotted path; "[]" marks array items
    type: str                      # number | integer | boolean | string | object | array
    required: bool = False
    desc: str = ""
    unit: str = ""
    enum: tuple = ()
    minimum: float | None = None
    maximum: float | None = None
    exclusive_min: bool = False
    nullable: bool = False
    default: Any = None
    internal: str = ""             # internal (delivered-code) field name, for the dictionary
    indicator: str = ""            # indicator code(s) the field feeds


F = Field
FIELDS: list[Field] = [
    F("request_id", "string", desc="调用方请求编号，原样返回，便于日志关联"),
    # ---- section
    F("section", "object", True, "评价单元（代表断面）基本信息"),
    F("section.section_id", "string", True, "断面或评价单元编号，如K0+500，原样返回", internal="桩号"),
    F("section.is_lake_levee", "boolean", True, "是否为湖堤；决定规范超高（湖堤2.5 m，河堤2.0 m）", internal="是否为湖堤", indicator="B1"),
    F("section.crest_elevation_m", "number", True, "堤顶高程", "m", internal="堤顶高程_m", indicator="B1"),
    F("section.design_flood_level_m", "number", True, "设计洪水位", "m", internal="设计洪水位_m", indicator="B1"),
    F("section.crest_width_m", "number", True, "堤顶宽度（设计标准7.5 m）", "m", minimum=0, exclusive_min=True, internal="堤顶宽度_m", indicator="A1"),
    F("section.outer_slope_ratio", "number", True, "临水坡（外坡）坡比1:m中的m（标准2.5）", minimum=0, exclusive_min=True, internal="外坡坡比", indicator="A1"),
    F("section.inner_slope_ratio", "number", True, "背水坡（内坡）坡比1:m中的m（标准3.0）", minimum=0, exclusive_min=True, internal="内坡坡比", indicator="A1"),
    F("section.foundation_class", "string", desc="堤基类型（地勘分类）；未给出qualitative.A7时用于A7：C类70分、D类60分、其余100分", enum=("A", "B", "C", "D"), internal="堤基类型", indicator="A7"),
    F("section.control_layer", "object", desc="渗流控制土层；与soil_layers至少给出其一", indicator="C1,C4,C5"),
    F("section.control_layer.name", "string", desc="控制土层名称", internal="控制土层名称"),
    F("section.control_layer.Gs", "number", True, "控制土层土粒比重", minimum=2.0, maximum=3.2, internal="控制层Gs"),
    F("section.control_layer.e", "number", True, "控制土层孔隙比", minimum=0.1, maximum=3.0, internal="控制层e"),
    F("section.control_layer.J_allow", "number", desc="控制土层允许渗透比降（仅记录）", minimum=0, internal="控制渗透比降J_allow"),
    F("section.soil_layers", "array", desc="土层参数表；未给control_layer时取临界比降最小的土层为控制层"),
    F("section.soil_layers[].name", "string", True, "土层名称", internal="土层名称"),
    F("section.soil_layers[].Gs", "number", True, "土粒比重", minimum=2.0, maximum=3.2, internal="Gs"),
    F("section.soil_layers[].e", "number", True, "孔隙比", minimum=0.1, maximum=3.0, internal="e"),
    F("section.soil_layers[].thickness_m", "number", desc="厚度", unit="m", minimum=0, internal="厚度_m"),
    F("section.soil_layers[].k_cm_s", "number", desc="渗透系数", unit="cm/s", minimum=0, internal="渗透系数_cm_s"),
    F("section.soil_layers[].J_allow", "number", desc="允许渗透比降", minimum=0, internal="允许渗透比降J_allow"),
    # ---- computation (seepage and stability)
    F("computation", "object", True, "渗流计算与边坡稳定复核结果（同一水位工况）"),
    F("computation.foundation_gradient", "number", True, "堤基渗透比降i（出口法向出逸梯度）", minimum=0, internal="渗透比降i", indicator="C1"),
    F("computation.body_gradient", "number", True, "堤身渗透比降", minimum=0, internal="堤身渗透比降i", indicator="C4"),
    F("computation.contact_gradient", "number", True, "堤基接触面渗透比降", minimum=0, internal="接触面渗透比降i", indicator="C5"),
    F("computation.body_Gs", "number", desc="堤身土粒比重（缺省取控制层）", minimum=2.0, maximum=3.2, internal="堤身Gs", indicator="C4"),
    F("computation.body_e", "number", desc="堤身孔隙比（缺省取控制层）", minimum=0.1, maximum=3.0, internal="堤身e", indicator="C4"),
    F("computation.back_slope_fos", "number", desc="背水坡抗滑稳定安全系数（正常运用）；未做稳定计算时不填或null：D1按缺失处理，不做背水坡稳定门控", minimum=0, exclusive_min=True, nullable=True, internal="背水坡FoS_正常", indicator="D1"),
    F("computation.front_slope_fos", "number", desc="临水坡抗滑稳定安全系数（稳态）；未做稳定计算时不填或null：D2按缺失处理，不做临水坡稳定门控", minimum=0, exclusive_min=True, nullable=True, internal="临水坡FoS", indicator="D2"),
    # ---- survey
    F("survey", "object", True, "测量与检查资料"),
    F("survey.scour_depth_m", "number", desc="堤脚冲刷深度；无测量资料时不填或null：D3按缺失处理（有未加固的重大险情记录时仍计0分），不做冲刷门控", unit="m", minimum=0, nullable=True, internal="冲刷深度_m", indicator="D3"),
    F("survey.soft_foundation_settlement_cm", "number", desc="软基段沉降量；缺省或null时按soft_foundation_status处理", unit="cm", minimum=0, nullable=True, internal="软基段_沉降量_cm", indicator="A5"),
    F("survey.soft_foundation_settlement_diff_cm", "number", desc="软基段沉降差；给出沉降量时必填", unit="cm", minimum=0, nullable=True, internal="软基段_沉降差_cm", indicator="A5"),
    F("survey.soft_foundation_status", "string", desc="未给沉降量时说明原因：non_soft＝非软基段（默认，A5按100分并提示）；unknown＝软基情况或沉降资料未知（A5按缺失处理，不做沉降门控）。给出沉降量时不得填写", enum=("non_soft", "unknown"), default="non_soft", indicator="A5"),
    # ---- records
    F("records", "object", True, "台账与检查结论"),
    F("records.fill_quality", "string", True, "堤身填土质量（地勘结论）", enum=("质量较好", "质量一般", "质量较差"), internal="填土质量", indicator="A2"),
    F("records.crossing_structure_class", "string", True, "穿堤建筑物安全检测结论；无穿堤建筑物填“不涉及”（按交付模型编码为100分，并给出提示）", enum=tuple(BUILDING_CLASSES), internal="检测结论", indicator="A3"),
    F("records.historical_dangers", "array", True, "本评价单元的历史险情与隐患记录；已核查无记录时传空数组", indicator="A6,D3"),
    F("records.historical_dangers[].type", "string", True, "险情类型，如管涌、散浸、渗漏、崩岸、蚁穴、隐患", internal="险情类型"),
    F("records.historical_dangers[].reinforced", "boolean", True, "是否已加固处置", internal="是否已加固"),
    F("records.historical_dangers[].severity", "string", desc="严重程度", enum=("无", "轻微", "中度", "严重"), internal="严重程度"),
    # ---- qualitative
    F("qualitative", "object", desc="定性指标结论：键为指标代码，值为分档名称或0～100分；未给出的指标按缺失处理（不默认100分）", internal="待输入指标"),
    # ---- calculated alternatives
    F("calculated", "object", desc="可替代定性结论的计算量（qualitative中给出同一指标时以qualitative为准）"),
    F("calculated.flood_standard", "object", desc="防洪标准", indicator="B2"),
    F("calculated.flood_standard.current_return_period_a", "number", True, "现状防洪标准（重现期）", "a", minimum=0, internal="现状防洪标准_年"),
    F("calculated.flood_standard.approved_return_period_a", "number", True, "批复防洪标准（重现期）", "a", minimum=0, internal="批复防洪标准_年"),
    F("calculated.overtopping", "object", desc="越浪量复核", indicator="B3"),
    F("calculated.overtopping.discharge", "number", True, "越浪量", "L/(s·m)", minimum=0, internal="越浪量"),
    F("calculated.overtopping.allowable_discharge", "number", True, "允许越浪量", "L/(s·m)", minimum=0, internal="允许越浪量"),
    F("calculated.crossing_structure", "object", desc="穿堤建筑物复核计算", indicator="B4,D4"),
    F("calculated.crossing_structure.flood_defence_elevation_m", "number", desc="挡洪高程（与required_elevation_m同时给出用于B4）", unit="m", internal="穿堤建筑物挡洪高程_m"),
    F("calculated.crossing_structure.required_elevation_m", "number", desc="防洪要求高程", unit="m", internal="穿堤建筑物防洪要求高程_m"),
    F("calculated.crossing_structure.sliding_fos", "number", desc="抗滑安全系数（D4需六项齐全）", minimum=0, internal="穿堤抗滑安全系数"),
    F("calculated.crossing_structure.overturning_fos", "number", desc="抗倾安全系数", minimum=0, internal="穿堤抗倾安全系数"),
    F("calculated.crossing_structure.bearing_fos", "number", desc="承载力安全系数", minimum=0, internal="穿堤承载力安全系数"),
    F("calculated.crossing_structure.sliding_fos_allow", "number", desc="抗滑允许安全系数", minimum=0, internal="穿堤抗滑允许安全系数"),
    F("calculated.crossing_structure.overturning_fos_allow", "number", desc="抗倾允许安全系数", minimum=0, internal="穿堤抗倾允许安全系数"),
    F("calculated.crossing_structure.bearing_fos_allow", "number", desc="承载力允许安全系数", minimum=0, internal="穿堤承载力允许安全系数"),
    # ---- inspection
    F("inspection", "object", desc="巡检证据（C3与观测门控）；缺省时C3按缺失处理", indicator="C3"),
    F("inspection.coverage", "string", True, "巡检覆盖状态：complete为覆盖完整且在有效期内；none为未覆盖或过期（C3按缺失处理）", enum=("complete", "none")),
    F("inspection.mode", "string", desc="events：传入已确认事件，由服务按交付规则汇总；aggregated：传入已汇总的密度与门控", enum=("events", "aggregated"), default="events"),
    F("inspection.segment_length_m", "number", desc="评价段长度（events模式）", unit="m", minimum=0, exclusive_min=True, default=100.0),
    F("inspection.confirmed_events", "array", desc="经人工复核确认的渗漏/管涌事件；events模式必填，无事件时传空数组；算法候选与误报不得传入"),
    F("inspection.confirmed_events[].position", "string", desc="位置类型（决定位置权重：普通1.0，堤脚1.2，建筑物附近1.3，结合部或历史险情附近1.5）", enum=tuple(POSITIONS), default="普通堤身", internal="位置类型"),
    F("inspection.confirmed_events[].repeat_count", "integer", desc="同一位置出现次数", minimum=1, default=1, internal="重复次数"),
    F("inspection.confirmed_events[].sand", "boolean", desc="带砂", default=False, internal="带砂"),
    F("inspection.confirmed_events[].muddy", "boolean", desc="浑水", default=False, internal="浑水"),
    F("inspection.confirmed_events[].spouting", "boolean", desc="冒水", default=False, internal="冒水"),
    F("inspection.confirmed_events[].clustered", "boolean", desc="集中成簇", default=False, internal="集中成簇"),
    F("inspection.aggregated", "object", desc="已汇总的巡检证据（aggregated模式）"),
    F("inspection.aggregated.weighted_density_per_100m", "number", True, "加权渗漏点密度", "点/100 m", minimum=0, internal="加权渗漏点密度_点每100m"),
    F("inspection.aggregated.evidence_level", "integer", True, "巡检证据等级0～3", minimum=0, maximum=3, internal="UAV证据等级"),
    F("inspection.aggregated.gate_cap", "string", desc="观测门控等级上限（B或C；不设门控时为null）", enum=("B", "C"), nullable=True, internal="UAV门控等级上限"),
    F("inspection.aggregated.note", "string", desc="门控说明", internal="UAV门控说明"),
    # ---- options
    F("options", "object", desc="模型参数（一般不需改动；改动时响应中给出提示）"),
    F("options.alpha", "number", desc="短板系数α", minimum=0, maximum=1, default=0.45),
    F("options.barrier_lambda", "number", desc="运行管理屏障强度λ", minimum=0, maximum=1, default=0.5),
]
BY_PATH = {f.path: f for f in FIELDS}
MAX_BATCH = 1000


def _type_ok(value, t):
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool) and value == value and abs(value) != float("inf")
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "boolean":
        return isinstance(value, bool)
    if t == "string":
        return isinstance(value, str)
    if t == "object":
        return isinstance(value, dict)
    if t == "array":
        return isinstance(value, list)
    return False


def _children(prefix):
    depth = prefix.count(".") + 1 if prefix else 0
    out = []
    for f in FIELDS:
        p = f.path
        if prefix and not p.startswith(prefix + "."):
            continue
        rest = p[len(prefix) + 1:] if prefix else p
        if "." not in rest:
            out.append(f)
    return out


def _validate_obj(obj, prefix, shown, errors):
    known = {f.path[len(prefix) + 1:] if prefix else f.path for f in _children(prefix)}
    for key in obj:
        if key not in known:
            errors.append({"field": f"{shown}.{key}" if shown else key, "reason": "unknown_field"})
    for f in _children(prefix):
        name = f.path.split(".")[-1]
        where = f"{shown}.{name}" if shown else name
        if name not in obj or obj[name] is None:
            if obj.get(name, "missing") is None and f.nullable:
                continue
            if f.required:
                errors.append({"field": where, "reason": "required"})
            continue
        _validate_value(obj[name], f, where, errors)


def _validate_value(v, f, where, errors):
    if not _type_ok(v, f.type):
        errors.append({"field": where, "reason": f"type_{f.type}_required"})
        return
    if f.enum and v not in f.enum:
        errors.append({"field": where, "reason": "not_in_enum", "allowed": list(f.enum)})
    if f.type in ("number", "integer"):
        if f.minimum is not None and (v < f.minimum or (f.exclusive_min and v == f.minimum)):
            errors.append({"field": where, "reason": "below_minimum", "minimum": f.minimum, "exclusive": f.exclusive_min})
        if f.maximum is not None and v > f.maximum:
            errors.append({"field": where, "reason": "above_maximum", "maximum": f.maximum})
    if f.type == "object" and f.path != "qualitative":
        _validate_obj(v, f.path, where, errors)
    if f.type == "array":
        item_prefix = f.path + "[]"
        if any(x.path.startswith(item_prefix + ".") for x in FIELDS):
            for k, item in enumerate(v):
                if not isinstance(item, dict):
                    errors.append({"field": f"{where}[{k}]", "reason": "type_object_required"})
                else:
                    _validate_obj(item, item_prefix, f"{where}[{k}]", errors)


def _validate_qualitative(q, errors):
    for code, val in q.items():
        where = f"qualitative.{code}"
        if code not in QUALITATIVE_CATEGORIES:
            errors.append({"field": where, "reason": "unknown_indicator", "allowed": sorted(QUALITATIVE_CATEGORIES)})
        elif isinstance(val, str):
            if val not in QUALITATIVE_CATEGORIES[code]:
                errors.append({"field": where, "reason": "not_in_enum", "allowed": QUALITATIVE_CATEGORIES[code]})
        elif _type_ok(val, "number"):
            if not 0 <= val <= 100:
                errors.append({"field": where, "reason": "score_out_of_range_0_100"})
        else:
            errors.append({"field": where, "reason": "category_or_score_required"})


def validate(req) -> list[dict]:
    """Return a list of {field, reason, ...}; empty when the request is valid."""
    if not isinstance(req, dict):
        return [{"field": "", "reason": "type_object_required"}]
    errors: list[dict] = []
    _validate_obj(req, "", "", errors)
    q = req.get("qualitative") if isinstance(req.get("qualitative"), dict) else {}
    _validate_qualitative(q, errors)
    if errors:
        return errors
    s, sv = req["section"], req["survey"]
    if "control_layer" not in s and not s.get("soil_layers"):
        errors.append({"field": "section.control_layer", "reason": "control_layer_or_soil_layers_required"})
    if "A7" not in q and "foundation_class" not in s:
        errors.append({"field": "section.foundation_class", "reason": "foundation_class_or_qualitative_A7_required"})
    if sv.get("soft_foundation_settlement_cm") is not None and sv.get("soft_foundation_settlement_diff_cm") is None:
        errors.append({"field": "survey.soft_foundation_settlement_diff_cm", "reason": "required_when_settlement_given"})
    if sv.get("soft_foundation_settlement_cm") is not None and "soft_foundation_status" in sv:
        errors.append({"field": "survey.soft_foundation_status", "reason": "not_allowed_when_settlement_given"})
    ins = req.get("inspection")
    if ins and ins.get("coverage") == "complete":
        if ins.get("mode", "events") == "aggregated":
            if "aggregated" not in ins:
                errors.append({"field": "inspection.aggregated", "reason": "required_in_aggregated_mode"})
            else:   # the delivered rules always pair level 0/1 with no cap, 2 with B, 3 with C
                a = ins["aggregated"]
                if a.get("gate_cap") != {0: None, 1: None, 2: "B", 3: "C"}[a["evidence_level"]]:
                    errors.append({"field": "inspection.aggregated.gate_cap", "reason": "inconsistent_with_evidence_level"})
                if (a["weighted_density_per_100m"] == 0) != (a["evidence_level"] == 0):
                    errors.append({"field": "inspection.aggregated.evidence_level", "reason": "inconsistent_with_density"})
            if "confirmed_events" in ins:
                errors.append({"field": "inspection.confirmed_events", "reason": "not_allowed_in_aggregated_mode"})
        else:
            if "confirmed_events" not in ins:
                errors.append({"field": "inspection.confirmed_events", "reason": "required_in_events_mode_empty_list_if_none"})
            if "aggregated" in ins:
                errors.append({"field": "inspection.aggregated", "reason": "not_allowed_in_events_mode"})
    return errors
