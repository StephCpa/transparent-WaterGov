# -*- coding: utf-8 -*-
"""
堤防安全评价体系 —— 核心计算模块

功能：
  1. 28 个二级指标的评分函数
  2. 状态变权（一级 + 二级）
  3. 短板原则
  4. 物理门控（单项否决制）
  5. 云模型定级

依据规范：
  SL/Z 679-2015《堤防工程安全评价导则》
  GB 50286-2013《堤防工程设计规范》
  SL 265-2016《水闸设计规范》
  SL 214-2015《水闸安全鉴定规程》
"""

import json
import math
import os
import random
import re
from pathlib import Path

# ============================================================
# 一、内置固定标准值
# ============================================================

# 1. 设计标准
STD_TOP_WIDTH = 7.5        # 标准堤顶宽 m
STD_OUTER_SLOPE = 2.5      # 标准外坡坡比
STD_INNER_SLOPE = 3.0      # 标准内坡坡比
FREEBOARD_RIVER = 2.0      # 河堤超高 m
FREEBOARD_LAKE = 2.5       # 湖堤超高 m
FOS_BACK_ALLOW = 1.35      # 背水坡FoS允许值 (GB50286-2013)
FOS_FRONT_ALLOW = 1.25     # 临水坡FoS允许值 (GB50286-2013)
SETTLE_ALLOW = 15.0        # 沉降量允许值 cm (SL265-2016)
SETTLE_DIFF_ALLOW = 5.0    # 沉降差允许值 cm (SL265-2016)
DEFAULT_LEAK_MATCH_MAX_DISTANCE_M = 250.0


def front_slope_fos(sec):
    """Return the steady-calculation front-slope FoS used by the evaluation."""
    steady = sec.get("临水坡FoS")
    if steady is None:
        raise KeyError("缺少稳态计算结果：临水坡FoS")
    return float(steady)

# 2. AHP 一级权重（常权）
W1_A = 0.1818   # A_工程质量
W1_B = 0.1818   # B_防洪安全
W1_C = 0.3636   # C_渗流安全
W1_D = 0.1818   # D_结构安全
W1_E = 0.0909   # E_运行管理

# 3. AHP 二级权重
W2_A = {"A1": 0.1042, "A2": 0.2053, "A3": 0.1042, "A4": 0.0604, "A5": 0.0374,
         "A6": 0.2053, "A7": 0.1562, "A8": 0.1042, "A9": 0.0229}
W2_B = {"B1": 0.4832, "B2": 0.1569, "B3": 0.2717, "B4": 0.0882}
W2_C = {"C1": 0.2747, "C2": 0.0890, "C3": 0.0600, "C4": 0.1731, "C5": 0.2747, "C6": 0.1284}
W2_D = {"D1": 0.4060, "D2": 0.2502, "D3": 0.1154, "D4": 0.0634, "D5": 0.1651}
W2_E = {"E1": 0.2634, "E2": 0.0975, "E3": 0.0615, "E4": 0.4174, "E5": 0.1602}

# 4. 云模型标准云参数（简化版使用，与完整版 LEVEL_CLOUDS 保持一致）
CLOUD_PARAMS = {
    "A级_安全":     {"Ex": 90.0, "En": 5.0,  "He": 0.5},
    "B级_基本安全": {"Ex": 60.0, "En": 10.0, "He": 1.0},
    "C级_不安全":   {"Ex": 20.0, "En": 10.0, "He": 1.0},
}

CLOUD_SAMPLE_N = 100  # 采样次数（仅历史保留，简化版未使用）

# ============================================================
# 二、工具函数
# ============================================================

def haversine(lat1, lon1, lat2, lon2):
    """Haversine 公式计算两点间距离（米）"""
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


_STAKE_RE = re.compile(r"(?:K|桩号)?\s*(\d+(?:\.\d+)?)\s*\+\s*(\d+(?:\.\d+)?)", re.IGNORECASE)


def _normalize_stake_text(stake_str):
    text = str(stake_str).strip()
    for old, new in {
        "＋": "+",
        "－": "-",
        "—": "-",
        "～": "~",
        "，": ",",
        "　": " ",
    }.items():
        text = text.replace(old, new)
    return text


def parse_stake(stake_str):
    """将桩号字符串转为米值用于比较。

    支持 ``45+600``、``K45+600``、``45＋600`` 和纯数字米值。
    如果传入范围字符串（如 ``K45+500-K46+096``），默认解析第一个桩号。
    """
    text = _normalize_stake_text(stake_str)
    match = _STAKE_RE.search(text)
    if match:
        return float(match.group(1)) * 1000 + float(match.group(2))

    number = re.search(r"-?\d+(?:\.\d+)?", text)
    if number:
        return float(number.group(0))
    raise ValueError(f"无法解析桩号: {stake_str!r}")


def parse_stake_range(range_str):
    """从范围文本中解析起止桩号，返回 (start_m, end_m)。"""
    text = _normalize_stake_text(range_str)
    matches = list(_STAKE_RE.finditer(text))
    if len(matches) >= 2:
        start = float(matches[0].group(1)) * 1000 + float(matches[0].group(2))
        end = float(matches[1].group(1)) * 1000 + float(matches[1].group(2))
        return (min(start, end), max(start, end))

    parts = re.split(r"\s*(?:-|~|至|到)\s*", text, maxsplit=1)
    if len(parts) == 2:
        start = parse_stake(parts[0])
        end = parse_stake(parts[1])
        return (min(start, end), max(start, end))

    value = parse_stake(text)
    return (value, value)


def stake_in_range(stake_str, start_str, end_str):
    """判断桩号是否在 [起始桩号, 终止桩号] 范围内"""
    s = parse_stake(stake_str)
    return parse_stake(start_str) <= s <= parse_stake(end_str)


def controlling_soil_layer(sec):
    """
    多层堤基按最不利原则取控制土层。

    渗流安全评价时不宜固定取第一层土，尤其是目标段存在粉细砂夹层和
    砂砾石层。这里取 Terzaghi 临界水力梯度 i_cr 最小的土层作为控制层。
    """
    if sec.get("控制层Gs") is not None and sec.get("控制层e") is not None:
        return {
            "Gs": sec.get("控制层Gs", 2.65),
            "e": sec.get("控制层e", 0.70),
            "允许渗透比降J_allow": sec.get("控制渗透比降J_allow"),
            "土层名称": sec.get("控制土层名称", "剖面指定控制层"),
        }

    layers = sec.get("土层参数", [])
    valid = [x for x in layers if x.get("Gs") is not None and x.get("e") is not None]
    if not valid:
        return {"Gs": 2.70, "e": 0.85, "允许渗透比降J_allow": 0.40, "土层名称": "默认控制层"}
    return min(valid, key=lambda x: terzaghi_critical_gradient(x["Gs"], x["e"]))


def terzaghi_critical_gradient(Gs, e):
    """Terzaghi critical hydraulic gradient: i_cr = (Gs - 1) / (1 + e)."""
    Gs = float(Gs)
    e = float(e)
    if 1.0 + e <= 0:
        return 0.0
    return (Gs - 1.0) / (1.0 + e)


def seepage_score_terzaghi(i_actual, Gs, e):
    """Score seepage stability by Terzaghi critical gradient.

    R = i_actual / i_cr; S = 100 * (1 - R^2), clipped to [0, 100].
    """
    i_actual = float(i_actual or 0.0)
    if i_actual <= 0:
        return 100.0
    i_cr = terzaghi_critical_gradient(Gs, e)
    if i_cr <= 0:
        return 0.0
    R = i_actual / i_cr
    score = 100.0 * (1.0 - R ** 2)
    return max(0.0, min(100.0, score))


def seepage_risk_ratio_terzaghi(i_actual, Gs, e):
    i_cr = terzaghi_critical_gradient(Gs, e)
    if i_cr <= 0:
        return 0.0
    return float(i_actual or 0.0) / i_cr


OPTIONAL_INDICATOR_SCORE_MAPS = {
    # A. 工程质量：依据 SL/Z 679 的状态检查内容建立分档赋值。
    "A4": {"优": 100, "良": 80, "中": 60, "一般": 60, "差": 40, "极差": 0},
    "A6": {"无": 100, "轻微": 80, "中度": 60, "严重": 0},
    "A7": {"良好": 100, "一般": 70, "未处理": 0, "险情": 0},
    "A8": {"不涉及": 100, "密实": 100, "良好": 100, "轻微渗漏": 70, "集中渗漏": 0, "严重渗漏": 0},
    "A9": {"不涉及": 100, "无影响": 100, "轻微影响": 70, "存在危险": 0, "危险": 0},

    # B. 防洪安全：优先建议用复核计算结果；无连续计算量时可按复核结论分档输入。
    "B2": {"符合": 100, "待复核": 60, "不符合": 0},
    "B3": {"满足": 100, "待复核": 60, "略超标": 70, "严重超标": 0, "超标": 0},
    "B4": {"不涉及": 100, "完全符合": 100, "符合": 100, "待复核": 60, "高程不足": 60, "不达标": 0},

    # C. 渗流安全。
    "C2": {"通畅": 100, "一般": 60, "局部淤积": 70, "局部堵塞": 70, "失效": 0},
    "C6": {"不涉及": 100, "无渗漏": 100, "明显渗漏": 60, "失稳": 0, "带砂": 0},

    # D. 结构安全。
    "D4": {"不涉及": 100, "全部满足": 100, "满足": 100, "临界状态": 60, "临界": 60, "不满足": 0},
    "D5": {"无": 100, "轻微": 70, "明显": 40, "严重": 0},

    # E. 运行管理。
    "E1": {"完善": 100, "一般": 80, "差": 40},
    "E2": {"健全": 100, "基本健全": 70, "不健全": 40},
    "E3": {"完备": 100, "基本满足": 70, "缺失": 0},
    "E4": {"完备": 100, "基本满足": 70, "严重缺失": 0, "缺失": 0},
    "E5": {"全部处置": 100, "部分处置": 60, "未执行": 0},
}

OPTIONAL_INDICATOR_CODES = tuple(OPTIONAL_INDICATOR_SCORE_MAPS)


def _score_from_optional_value(code, value):
    if isinstance(value, (int, float)):
        return max(0.0, min(100.0, float(value)))

    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return None
        try:
            return max(0.0, min(100.0, float(text)))
        except ValueError:
            pass
        mapping = OPTIONAL_INDICATOR_SCORE_MAPS.get(code, {})
        if text in mapping:
            return float(mapping[text])
        raise ValueError(f"{code} optional indicator value '{value}' is not a supported score or category")

    if isinstance(value, dict):
        if "score" in value:
            return _score_from_optional_value(code, value["score"])
        if "得分" in value:
            return _score_from_optional_value(code, value["得分"])
        for key in ("等级", "状态", "结论", "类别"):
            if key in value:
                return _score_from_optional_value(code, value[key])

    raise ValueError(f"{code} optional indicator value type is unsupported: {type(value).__name__}")


def optional_indicator_score(sec, code):
    """Read an optional indicator score/category; missing means not evaluated."""
    optional_scores = sec.get("待输入指标", {})
    value = optional_scores.get(code, sec.get(code))
    if value is None or value == "":
        return None
    return _score_from_optional_value(code, value)


def score_from_optional_or_calculated(sec, code):
    """Optional qualitative score first; if absent, use indicator-specific numeric rules."""
    supplied = optional_indicator_score(sec, code)
    if supplied is not None:
        return supplied

    if code == "B2":
        current = sec.get("现状防洪标准_年")
        approved = sec.get("批复防洪标准_年")
        if current is not None and approved is not None:
            return 100.0 if float(current) >= float(approved) else 0.0

    if code == "B3":
        q = sec.get("越浪量")
        q_allow = sec.get("允许越浪量")
        if q is not None and q_allow is not None:
            q = float(q)
            q_allow = float(q_allow)
            if q_allow <= 0:
                return 0.0
            ratio = q / q_allow
            if ratio <= 1.0:
                return 100.0
            if ratio <= 1.2:
                return 70.0
            return 0.0

    if code == "B4":
        top = sec.get("穿堤建筑物挡洪高程_m")
        required = sec.get("穿堤建筑物防洪要求高程_m")
        if top is not None and required is not None:
            deficit = float(required) - float(top)
            if deficit <= 0:
                return 100.0
            if deficit <= 0.5:
                return 60.0
            return 0.0

    if code == "D4":
        keys = ("穿堤抗滑安全系数", "穿堤抗倾安全系数", "穿堤承载力安全系数")
        allow_keys = ("穿堤抗滑允许安全系数", "穿堤抗倾允许安全系数", "穿堤承载力允许安全系数")
        if all(sec.get(k) is not None for k in keys) and all(sec.get(k) is not None for k in allow_keys):
            ratios = [float(sec[k]) / float(sec[a]) for k, a in zip(keys, allow_keys) if float(sec[a]) > 0]
            if not ratios:
                return 0.0
            min_ratio = min(ratios)
            if min_ratio >= 1.0:
                return 100.0
            if min_ratio >= 0.9:
                return 60.0
            return 0.0

    return None


GRADE_ORDER = {"A级_安全": 3, "B级_基本安全": 2, "C级_不安全": 1}


def cap_grade(grade, cap):
    """只做向下修正：当规范硬指标不满足时，最高等级不得超过 cap。"""
    if GRADE_ORDER.get(grade, 0) > GRADE_ORDER[cap]:
        return cap
    return grade

# ============================================================
# 三、加载输入文件
# ============================================================

def load_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

# ============================================================
# 四、步骤2 —— 渗漏点匹配到剖面
# ============================================================

def match_leak_points(leak_data, gps_list, max_match_distance_m=DEFAULT_LEAK_MATCH_MAX_DISTANCE_M):
    """
    返回字典 {桩号: 已确认渗漏计数}
    """
    leak_count = {g["桩号"]: 0 for g in gps_list}
    confirmed = [p for p in leak_data.get("渗漏点列表", []) if p.get("是否人工确认")]

    for pt in confirmed:
        if pt.get("纬度") is None or pt.get("经度") is None:
            continue
        best_stake = None
        best_dist = float("inf")
        for g in gps_list:
            d = haversine(pt["纬度"], pt["经度"], g["纬度"], g["经度"])
            if d < best_dist:
                best_dist = d
                best_stake = g["桩号"]
        if (
            best_stake is not None
            and (max_match_distance_m is None or best_dist <= max_match_distance_m)
        ):
            leak_count[best_stake] = leak_count.get(best_stake, 0) + 1

    return leak_count


UAV_LEAK_POSITION_WEIGHTS = {
    "普通堤身": 1.0,
    "堤身": 1.0,
    "堤坡": 1.0,
    "堤脚": 1.2,
    "坡脚": 1.2,
    "穿堤建筑物": 1.3,
    "建筑物附近": 1.3,
    "结合部": 1.5,
    "历史险情附近": 1.5,
}


def _uav_point_confidence(pt):
    if pt.get("置信度") is not None:
        return max(0.0, min(1.0, float(pt["置信度"])))
    if pt.get("识别置信度") is not None:
        return max(0.0, min(1.0, float(pt["识别置信度"])))
    if pt.get("是否人工确认"):
        return 1.0
    return 0.6


def _uav_position_weight(pt):
    pos = str(pt.get("位置类型") or pt.get("位置") or "普通堤身").strip()
    return UAV_LEAK_POSITION_WEIGHTS.get(pos, 1.0)


def _uav_repeat_weight(pt):
    repeat = pt.get("重复次数", pt.get("出现次数", 1))
    try:
        repeat = int(repeat)
    except (TypeError, ValueError):
        repeat = 1
    if repeat >= 3:
        return 1.5
    if repeat == 2:
        return 1.2
    return 1.0


def _uav_point_severe(pt):
    severe_keys = ("带砂", "浑水", "冒水", "集中成簇", "严重渗漏", "人工复核严重")
    return any(bool(pt.get(k)) for k in severe_keys)


def _uav_point_sensitive(pt):
    pos = str(pt.get("位置类型") or pt.get("位置") or "").strip()
    return pos in {"堤脚", "坡脚", "穿堤建筑物", "建筑物附近", "结合部", "历史险情附近"}


def _leak_points_list(leak_data):
    return leak_data.get("渗漏点列表") or leak_data.get("无人机渗漏点列表") or leak_data.get("leak_points") or []


def match_uav_leakage_evidence(
    leak_data,
    gps_list,
    section_length_m=100.0,
    max_match_distance_m=DEFAULT_LEAK_MATCH_MAX_DISTANCE_M,
):
    """
    将无人机/巡查识别的渗漏点匹配到最近桩号，并形成 C3 评分和门控所需证据。

    无人机仅提供点状渗漏观测，不推断渗漏面积或渗漏量。
    """
    evidence = {
        g["桩号"]: {
            "渗漏点数": 0,
            "加权渗漏点数": 0.0,
            "加权渗漏点密度_点每100m": 0.0,
            "UAV证据等级": 0,
            "UAV门控等级上限": None,
            "UAV门控说明": "未发现无人机渗漏点",
            "渗漏点明细": [],
        }
        for g in gps_list
    }

    for pt in _leak_points_list(leak_data):
        if pt.get("纬度") is None or pt.get("经度") is None:
            continue
        best_stake = None
        best_dist = float("inf")
        for g in gps_list:
            d = haversine(pt["纬度"], pt["经度"], g["纬度"], g["经度"])
            if d < best_dist:
                best_dist = d
                best_stake = g["桩号"]
        if best_stake is None:
            continue
        if max_match_distance_m is not None and best_dist > max_match_distance_m:
            continue

        confidence = _uav_point_confidence(pt)
        position_weight = _uav_position_weight(pt)
        repeat_weight = _uav_repeat_weight(pt)
        weighted = confidence * position_weight * repeat_weight
        severe = _uav_point_severe(pt)
        sensitive = _uav_point_sensitive(pt)
        repeat_count = int(pt.get("重复次数", pt.get("出现次数", 1)) or 1)

        record = evidence[best_stake]
        record["渗漏点数"] += 1
        record["加权渗漏点数"] += weighted
        record["渗漏点明细"].append({
            "纬度": pt["纬度"],
            "经度": pt["经度"],
            "距代表桩号_m": round(best_dist, 3),
            "置信度": round(confidence, 4),
            "位置权重": round(position_weight, 4),
            "重复权重": round(repeat_weight, 4),
            "加权值": round(weighted, 4),
            "敏感位置": sensitive,
            "严重征兆": severe,
            "重复次数": repeat_count,
            "是否人工确认": bool(pt.get("是否人工确认")),
        })

    for stake, record in evidence.items():
        length = float(record.get("评价段长度_m", section_length_m) or section_length_m)
        density = 100.0 * record["加权渗漏点数"] / length if length > 0 else 0.0
        record["加权渗漏点数"] = round(record["加权渗漏点数"], 6)
        record["加权渗漏点密度_点每100m"] = round(density, 6)

        count = record["渗漏点数"]
        has_sensitive = any(x["敏感位置"] for x in record["渗漏点明细"])
        has_severe = any(x["严重征兆"] for x in record["渗漏点明细"])
        max_repeat = max([x["重复次数"] for x in record["渗漏点明细"]] or [1])

        if count == 0:
            guav = 0
            cap = None
            note = "未发现无人机渗漏点"
        elif has_severe or max_repeat >= 3 or density > 3.0:
            guav = 3
            cap = "C级_不安全"
            note = "无人机渗漏点呈严重征兆/重复出现/高密度，触发C级复核门控"
        elif has_sensitive or count >= 2 or max_repeat == 2 or density > 1.0:
            guav = 2
            cap = "B级_基本安全"
            note = "无人机渗漏点位于敏感部位或多点出现，最高等级限制为B级"
        else:
            guav = 1
            cap = None
            note = "普通单点渗漏观测，仅进入C3评分"

        record["UAV证据等级"] = guav
        record["UAV门控等级上限"] = cap
        record["UAV门控说明"] = note

    return evidence


def score_C3_from_uav_evidence(evidence):
    density = float(evidence.get("加权渗漏点密度_点每100m", 0.0) or 0.0)
    if density <= 0:
        return 100.0
    if density <= 1.0:
        return 80.0
    if density <= 2.0:
        return 60.0
    if density <= 4.0:
        return 40.0
    return 0.0

# ============================================================
# 五、步骤3 —— 逐剖面单指标量化评分
# ============================================================

def score_A1(sec):
    """堤顶宽度 + 外坡坡比 + 内坡坡比 三项几何指标，
    属于设计合规性指标，规范有硬性最低标准，保留 0/100 二值评分。"""
    if (sec["堤顶宽度_m"] >= STD_TOP_WIDTH and
        sec["外坡坡比"] >= STD_OUTER_SLOPE and
        sec["内坡坡比"] >= STD_INNER_SLOPE):
        return 100
    return 0


def score_B1(sec):
    """堤顶高程是否满足 设计洪水位 + 超高，规范硬性要求，保留 0/100。"""
    fb = FREEBOARD_LAKE if sec["是否为湖堤"] else FREEBOARD_RIVER
    if sec["堤顶高程_m"] >= sec["设计洪水位_m"] + fb:
        return 100
    return 0


def score_C1(sec):
    """
    【连续评分】基于 Terzaghi 临界水力梯度的堤基渗流稳定评分。

    i_cr = (Gs - 1) / (1 + e)
    R = i_actual / i_cr
    S = 100 * (1 - R^2)，并限制在 [0, 100]。
    """
    ctrl_layer = controlling_soil_layer(sec)
    i_actual = sec["渗透比降i"]
    return seepage_score_terzaghi(i_actual, ctrl_layer["Gs"], ctrl_layer["e"])


def score_D1(sec):
    """
    【连续评分 - 强化版】背水坡抗滑安全系数评分（FoS_allow = 1.35）

    设计要点：FoS=1.0（临界失稳）必须显著拉低综合得分，
    不依赖物理门控也能识别"接近失稳"的危险状态。

    分段：
      FoS ≥ 1.50           : 100
      1.35 ≤ FoS < 1.50    : 75 → 100 线性（满足规范，得分较高）
      1.00 ≤ FoS < 1.35    : 20 → 75  线性（不达标但未临界）
      FoS < 1.00           : 0       （已失稳）
    """
    fos = sec["背水坡FoS_正常"]
    if fos >= 1.50:
        return 100.0
    elif fos >= 1.35:
        return 75.0 + 25.0 * (fos - 1.35) / 0.15
    elif fos >= 1.00:
        return 20.0 + 55.0 * (fos - 1.00) / 0.35
    else:
        return 0.0


def score_D2(sec):
    """
    【连续评分 - 强化版】临水坡抗滑安全系数评分（FoS_allow = 1.25）

    仅采用稳态渗流-稳定计算得到的 ``临水坡FoS``；缺少该字段时直接报错，
    防止旧的非稳态结果混入正式评价。

    分段（相对 D1 各阈值下移 0.10，对应临水坡允许值更低）：
      FoS ≥ 1.40           : 100
      1.25 ≤ FoS < 1.40    : 75 → 100 线性
      1.00 ≤ FoS < 1.25    : 20 → 75  线性
      FoS < 1.00           : 0
    """
    fos = front_slope_fos(sec)
    if fos >= 1.40:
        return 100.0
    elif fos >= 1.25:
        return 75.0 + 25.0 * (fos - 1.25) / 0.15
    elif fos >= 1.00:
        return 20.0 + 55.0 * (fos - 1.00) / 0.25
    else:
        return 0.0


def score_A5(sec):
    """软基沉降，规范有明确限值，保留 0/100。"""
    if sec["软基段_沉降量_cm"] is None:
        return 100
    if sec["软基段_沉降量_cm"] <= SETTLE_ALLOW and sec["软基段_沉降差_cm"] <= SETTLE_DIFF_ALLOW:
        return 100
    return 0


def score_A2(stake, geo_cls):
    """填土质量分档评分。
    量化规则（依据地勘报告定性结论）：
      优（压实度达标，均匀性好）: 100
      良（压实度基本达标）: 80
      差（压实度不足，均匀性差）: 60
    """
    for seg in geo_cls:
        if stake_in_range(stake, seg["起始桩号"], seg["终止桩号"]):
            quality = seg["填土质量"]
            if quality == "质量较好":
                return 100
            elif quality == "质量一般":
                return 80
            else:
                return 60
    return 100


def score_A3(stake, buildings):
    """穿堤建筑物检测结论分档评分。"""
    mapping = {
        "一类": 100, "二类": 100, "三类": 70, "四类": 0,
        "1类": 100, "2类": 100, "3类": 70, "4类": 0,
        "加固": 100, "改建": 70, "重建": 0,
    }
    for b in buildings:
        if b["桩号"] == stake:
            return mapping.get(b["检测结论"], 100)
    return 100


def _matching_dangers(stake, hist_dangers):
    return [
        h for h in hist_dangers
        if stake_in_range(stake, h["起始桩号"], h["终止桩号"])
    ]


def _danger_type_text(danger):
    return str(danger.get("险情类型", ""))


def score_A6(stake, hist_dangers):
    """堤身内部隐患评分。

    地勘资料中已明确的蚁穴堤、堤身隐患不应默认为缺失或满分。
    按“无 100、轻微 80、中度 60、严重 0”的分档语义量化。
    """
    matches = _matching_dangers(stake, hist_dangers)
    if not matches:
        return 100

    score = 100
    for danger in matches:
        dtype = _danger_type_text(danger)
        repaired = bool(danger.get("是否已加固"))
        severity = str(danger.get("严重程度", "")).strip()
        if severity in OPTIONAL_INDICATOR_SCORE_MAPS["A6"]:
            score = min(score, OPTIONAL_INDICATOR_SCORE_MAPS["A6"][severity])
            continue
        if "蚁" in dtype or "隐患" in dtype:
            score = min(score, 80 if repaired else 0)
        elif not repaired:
            score = min(score, 60)
    return score


def score_A7(sec):
    """堤基不良地质体基础评分。

    若后续有处理质量资料，可用待输入指标 A7 覆盖；否则按地勘给出的
    C/D 类地基进行保守量化。
    """
    foundation = sec.get("堤基类型")
    if foundation == "D":
        return 60
    if foundation == "C":
        return 70
    return 100


def score_D3(sec, hist_dangers):
    """冲刷深度 + 历史险情综合分档评分。"""
    stake = sec["桩号"]
    scour = sec["冲刷深度_m"]

    has_repaired_major = False
    has_unrepaired_major = False
    for h in _matching_dangers(stake, hist_dangers):
        dtype = _danger_type_text(h)
        is_major = any(key in dtype for key in ("崩", "管涌", "散浸", "渗漏"))
        if is_major:
            if h.get("是否已加固"):
                has_repaired_major = True
            else:
                has_unrepaired_major = True

    if scour >= 1.0 or has_unrepaired_major:
        return 0
    if scour >= 0.5 or has_repaired_major:
        return 70
    if scour < 0.5 and not has_repaired_major:
        return 100
    return 70


def score_C3(leak_n):
    """C3 管涌与渗漏观测证据评分。

    兼容两种输入：
    - 数值：历史逻辑，按渗漏点数量扣分；
    - 字典：无人机/巡查点状渗漏证据，按加权渗漏点密度分级。
    """
    if isinstance(leak_n, dict):
        return score_C3_from_uav_evidence(leak_n)
    return max(0, 100 - float(leak_n) * 50)


def score_C4(sec):
    """
    【连续评分】基于 Terzaghi 临界水力梯度的堤身渗流稳定评分。

    堤身若未单独给出 Gs/e，则沿用剖面控制层参数。
    """
    i_body = sec.get("堤身渗透比降i", 0.0)
    ctrl_layer = controlling_soil_layer(sec)
    Gs = sec.get("堤身Gs", ctrl_layer["Gs"])
    e = sec.get("堤身e", ctrl_layer["e"])
    return seepage_score_terzaghi(i_body, Gs, e)


def score_C5(sec):
    """
    【连续评分】基于 Terzaghi 临界水力梯度的接触面渗透稳定评分。
    """
    i_contact = sec.get("接触面渗透比降i", 0.0)
    ctrl_layer = controlling_soil_layer(sec)
    return seepage_score_terzaghi(i_contact, ctrl_layer["Gs"], ctrl_layer["e"])

# ============================================================
# 六、步骤4 —— 一级得分（含二级变权）
# ============================================================

def _sub_variable_weight_factor(danger_ratio, max_factor=1.8):
    """
    二级变权因子：s(d) = 1 + 0.8×d²，封顶 1.8 倍。
    danger_ratio: 0=安全, 1=临界破坏。
    """
    if danger_ratio <= 0:
        return 1.0
    elif danger_ratio < 1.0:
        return 1.0 + (max_factor - 1.0) * danger_ratio ** 2
    else:
        return max_factor


def _available_score_weighted_sum(scores, weights):
    available = {k: weights[k] for k in weights if scores.get(k) is not None}
    if not available:
        return None, {}
    total = sum(available.values())
    normed = {k: v / total for k, v in available.items()}
    return sum(scores[k] * normed[k] for k in normed), normed


def calc_level1(scores, sec=None):
    """
    计算一级得分，支持二级变权（C1, C5, D1, D2）+ 短板原则。

    短板原则：当关键渗流/稳定指标得分 < 60 时，
    该维度一级得分 = min_score × (min_score/60)²，
    让关键子指标的严重恶化不被其他子指标稀释。
    """
    SHORTBOARD_THRESHOLD = 60.0

    # A/B/E 维度：缺失待输入指标不参与，组内权重重归一化
    A, _ = _available_score_weighted_sum(scores, W2_A)
    B, _ = _available_score_weighted_sum(scores, W2_B)
    E, _ = _available_score_weighted_sum(scores, W2_E)

    # --- C 维度（二级变权: C1, C4, C5 权重随危险程度增大）---
    if sec is not None:
        ctrl_layer = controlling_soil_layer(sec)
        i_val = sec["渗透比降i"]
        r_c1 = seepage_risk_ratio_terzaghi(i_val, ctrl_layer["Gs"], ctrl_layer["e"])
        s_c1 = _sub_variable_weight_factor(r_c1)
        # C4 堤身渗流：用堤身比降/堤身临界水力梯度
        i_body = sec.get("堤身渗透比降i", 0.0)
        body_Gs = sec.get("堤身Gs", ctrl_layer["Gs"])
        body_e = sec.get("堤身e", ctrl_layer["e"])
        r_c4 = seepage_risk_ratio_terzaghi(i_body, body_Gs, body_e)
        s_c4 = _sub_variable_weight_factor(r_c4)
        # C5 接触冲刷：用接触面比降/控制层临界水力梯度
        i_contact = sec.get("接触面渗透比降i", 0.0)
        r_c5 = seepage_risk_ratio_terzaghi(i_contact, ctrl_layer["Gs"], ctrl_layer["e"])
        s_c5 = _sub_variable_weight_factor(r_c5)
    else:
        s_c1 = 1.0
        s_c4 = 1.0
        s_c5 = 1.0

    c_weights = {k: W2_C[k] for k in W2_C}
    c_weights["C1"] = W2_C["C1"] * s_c1
    c_weights["C4"] = W2_C["C4"] * s_c4
    c_weights["C5"] = W2_C["C5"] * s_c5
    C_weighted, _ = _available_score_weighted_sum(scores, c_weights)

    # C 组短板原则（C1 或 C5 严重恶化时触发）
    critical_c_scores = [scores[k] for k in ("C1", "C5") if scores.get(k) is not None]
    if C_weighted is not None and critical_c_scores and min(critical_c_scores) < SHORTBOARD_THRESHOLD:
        min_c = min(scores[k] for k in W2_C if scores.get(k) is not None)
        penalty = (min_c / SHORTBOARD_THRESHOLD) ** 2
        C = min_c * penalty
    else:
        C = C_weighted

    # --- D 维度（二级变权: D1/D2 随 FoS 降低增大，D5 随得分降低增大）---
    if sec is not None:
        fos_back = sec["背水坡FoS_正常"]
        fos_front = front_slope_fos(sec)
        danger_d1 = max(0.0, (FOS_BACK_ALLOW - fos_back) / (FOS_BACK_ALLOW - 1.0))
        s_d1 = _sub_variable_weight_factor(danger_d1)
        danger_d2 = max(0.0, (FOS_FRONT_ALLOW - fos_front) / (FOS_FRONT_ALLOW - 1.0))
        s_d2 = _sub_variable_weight_factor(danger_d2)
    else:
        s_d1 = 1.0
        s_d2 = 1.0

    # D5 变权：得分 < 60 时触发，得分越低变权越大
    d5_score = scores.get("D5")
    if d5_score is not None and d5_score < 60:
        danger_d5 = (60 - d5_score) / 60.0  # 0→1
        s_d5 = _sub_variable_weight_factor(danger_d5)
    else:
        s_d5 = 1.0

    d_weights = {k: W2_D[k] for k in W2_D}
    d_weights["D1"] = W2_D["D1"] * s_d1
    d_weights["D2"] = W2_D["D2"] * s_d2
    d_weights["D5"] = W2_D["D5"] * s_d5
    D_weighted, _ = _available_score_weighted_sum(scores, d_weights)

    # D 组短板原则
    d_critical_scores = [scores[k] for k in ("D1", "D2") if scores.get(k) is not None]
    if D_weighted is not None and d_critical_scores and min(d_critical_scores) < SHORTBOARD_THRESHOLD:
        min_d = min(d_critical_scores)
        penalty = (min_d / SHORTBOARD_THRESHOLD) ** 2
        D = min_d * penalty
    else:
        D = D_weighted

    return {"A": A, "B": B, "C": C, "D": D, "E": E}

# ============================================================
# 七、步骤5 —— 状态变权（一级：C + D）
# ============================================================

def state_variable_weight(sec):
    """
    一级状态变权：根据渗流和稳定性的危险程度动态调整维度权重。

    C 维度变权：R > 0.5 时触发，最大放大 2.5 倍（二次曲线）
    D 维度变权：FoS < 1.50/1.40 时触发，最大放大 3.5 倍（线性）

    返回归一化后的五维度权重字典。
    """
    C_MAX_FACTOR = 2.5
    D_MAX_FACTOR = 3.5

    ctrl_layer = controlling_soil_layer(sec)
    Gs = float(ctrl_layer["Gs"])
    e = float(ctrl_layer["e"])
    ic = terzaghi_critical_gradient(Gs, e)
    i = sec["渗透比降i"]
    R = i / ic if ic > 0 else 0.0

    # C 一级变权（渗流）—— 二次曲线
    if R <= 0.5:
        s_C = 1.0
    elif R < 1.0:
        danger_C = (R - 0.5) / 0.5
        s_C = 1.0 + (C_MAX_FACTOR - 1.0) * danger_C ** 2
    else:
        s_C = C_MAX_FACTOR

    # D 一级变权（抗滑稳定）—— 线性曲线，触发阈值提前到 FoS_allow+0.15
    fos_back = sec["背水坡FoS_正常"]
    fos_front = front_slope_fos(sec)
    BACK_TRIG = FOS_BACK_ALLOW + 0.15   # 1.50
    FRONT_TRIG = FOS_FRONT_ALLOW + 0.15 # 1.40
    danger_back = max(0.0, (BACK_TRIG - fos_back) / (BACK_TRIG - 1.0))
    danger_front = max(0.0, (FRONT_TRIG - fos_front) / (FRONT_TRIG - 0.9))
    danger_D = max(danger_back, danger_front)

    if danger_D <= 0:
        s_D = 1.0
    elif danger_D < 1.0:
        s_D = 1.0 + (D_MAX_FACTOR - 1.0) * danger_D  # 线性
    else:
        s_D = D_MAX_FACTOR

    C_new = W1_C * s_C
    D_new = W1_D * s_D
    raw = [W1_A, W1_B, C_new, D_new, W1_E]
    total = sum(raw)
    normed = [w / total for w in raw]
    return {"A": normed[0], "B": normed[1], "C": normed[2], "D": normed[3], "E": normed[4]}


# ============================================================
# 七b、临界安全惩罚因子（已废弃 - 由连续评分 + 状态变权承担其功能）
# ============================================================

def critical_penalty(sec):
    """已废弃，恒返回 1.0。保留函数签名仅为向后兼容。"""
    return 1.0

# ============================================================
# 八、步骤6 —— 云模型定级（简化版）
# ============================================================

def cloud_model_classify(composite_score):
    """
    云模型定级（简化版）：基于综合得分计算对各等级标准云的隶属度。
    隶属度公式：μ = exp(-(score - Ex)² / (2 × En²))
    """
    mu = {}
    for name, cp in CLOUD_PARAMS.items():
        mu[name] = math.exp(-(composite_score - cp["Ex"]) ** 2 / (2 * cp["En"] ** 2))

    best_grade = max(mu, key=mu.get)

    return {
        "综合得分": round(float(composite_score), 4),
        "安全等级": best_grade,
        "相似度": {k: round(v, 6) for k, v in mu.items()},
        "云参数": {"Ex": round(float(composite_score), 4), "En": 0.0, "He": 0.0},
    }

# ============================================================
# 八b、物理门控规则
# ============================================================
# 工程依据：堤防失效的两类直接破坏模式为渗流破坏与抗滑失稳。
# 物理门控仅做向下修正（只降不升）：
#   - 当 R = i / i_cr ≥ 1.0 或 FoS < 1.05 时，强制判为 C 级（不安全）。
#   - 其他情况保留云模型原判定。
# 不设向上门控：物理安全时变权后得分自然高，云模型自行判定即可。

R_SAFE = 0.5             # 渗流安全阈值（R = i / i_cr）—— 仅用于状态变权参考
R_FAIL = 1.0             # 渗流失效阈值（R ≥ 1.0 触发向下门控）
FOS_DOWN_LIMIT = 1.05    # 抗滑稳定下限（FoS < 1.05 视为接近失稳）


def physical_gate(sec, cloud_grade):
    """
    物理门控：仅做向下修正（只降不升）—— 单项否决制。
    依据 SL/Z 679-2015：关键指标单独达到 C 类标准时，整体直接判 C 级。

    门控分两级：
      - 规范控制值轻微不满足：最高等级限制为 B 级；
      - 达到临界破坏或严重超标：强制 C 级。

    强制 C 级触发条件（满足任一）：
      1. R ≥ 1.0（渗透比降达到临界水力梯度）
      2. FoS_back < 1.05 或 FoS_front < 1.05（边坡接近失稳）
      3. R_body ≥ 1.0（堤身渗流达到临界水力梯度）
      4. R_contact ≥ 1.0（接触面渗流达到临界水力梯度）
      5. 堤顶高程严重不足（低于设计洪水位，无超高）

    不设向上门控：如果物理安全，变权后得分自然高，云模型自行判定即可。
    """
    ctrl_layer = controlling_soil_layer(sec)
    Gs = float(ctrl_layer["Gs"])
    e = float(ctrl_layer["e"])
    ic = terzaghi_critical_gradient(Gs, e)
    i = sec["渗透比降i"]
    R = i / ic if ic > 0 else 0.0

    fos_back = sec["背水坡FoS_正常"]
    fos_front = front_slope_fos(sec)
    # 堤身和接触面参数
    i_body = sec.get("堤身渗透比降i", 0.0)
    i_contact = sec.get("接触面渗透比降i", 0.0)
    body_Gs = sec.get("堤身Gs", Gs)
    body_e = sec.get("堤身e", e)
    R_body = seepage_risk_ratio_terzaghi(i_body, body_Gs, body_e)
    R_contact = seepage_risk_ratio_terzaghi(i_contact, Gs, e)

    # 堤顶高程
    fb = FREEBOARD_LAKE if sec["是否为湖堤"] else FREEBOARD_RIVER
    overtop_severe = sec["堤顶高程_m"] < sec["设计洪水位_m"]  # 低于洪水位本身（无任何超高）

    # ---- 向下门控：严重超标 → 强制 C 级 ----
    severe_reasons = []
    if R >= R_FAIL:
        severe_reasons.append(f"R={R:.2f}>=1.0")
    if fos_back < FOS_DOWN_LIMIT:
        severe_reasons.append(f"FoS_back={fos_back:.2f}<1.05")
    if fos_front < FOS_DOWN_LIMIT:
        severe_reasons.append(f"FoS_front={fos_front:.2f}<1.05")
    if R_body >= R_FAIL:
        severe_reasons.append(f"R_body={R_body:.2f}>=1.0")
    if R_contact >= R_FAIL:
        severe_reasons.append(f"R_contact={R_contact:.2f}>=1.0")
    if overtop_severe:
        severe_reasons.append(f"堤顶低于设计洪水位")

    if severe_reasons:
        if cloud_grade == "C级_不安全":
            return (cloud_grade, f"物理门控确认: {', '.join(severe_reasons)}")
        else:
            return (
                "C级_不安全",
                f"单项否决: {', '.join(severe_reasons)}, {cloud_grade}→C级",
            )

    # ---- 规范控制值不满足但未达到严重超标：最高限制为 B 级 ----
    cap_reasons = []
    if fos_back < FOS_BACK_ALLOW:
        cap_reasons.append(f"FoS_back={fos_back:.2f}<1.35")
    if fos_front < FOS_FRONT_ALLOW:
        cap_reasons.append(f"FoS_front={fos_front:.2f}<1.25")
    if sec["堤顶宽度_m"] < STD_TOP_WIDTH:
        cap_reasons.append(f"top_width={sec['堤顶宽度_m']:.1f}m<7.5m")
    if sec["外坡坡比"] < STD_OUTER_SLOPE:
        cap_reasons.append(f"outer_slope=1:{sec['外坡坡比']:.1f}<1:2.5")
    if sec["内坡坡比"] < STD_INNER_SLOPE:
        cap_reasons.append(f"inner_slope=1:{sec['内坡坡比']:.1f}<1:3.0")
    freeboard_required = sec["设计洪水位_m"] + fb
    if sec["堤顶高程_m"] < freeboard_required:
        cap_reasons.append(f"freeboard_margin={sec['堤顶高程_m'] - freeboard_required:.2f}m<0")
    if sec.get("堤基类型") in {"C", "D"}:
        cap_reasons.append(f"foundation_class={sec['堤基类型']}")
    if sec.get("软基段_沉降量_cm") is not None:
        if sec["软基段_沉降量_cm"] > SETTLE_ALLOW:
            cap_reasons.append(f"settle={sec['软基段_沉降量_cm']:.1f}cm>15cm")
        if sec["软基段_沉降差_cm"] > SETTLE_DIFF_ALLOW:
            cap_reasons.append(f"settle_diff={sec['软基段_沉降差_cm']:.1f}cm>5cm")

    if cap_reasons:
        capped = cap_grade(cloud_grade, "B级_基本安全")
        if capped != cloud_grade:
            return (capped, f"规范控制值不满足: {', '.join(cap_reasons)}, {cloud_grade}→B级")
        return (cloud_grade, f"规范控制值不满足但云模型已降级: {', '.join(cap_reasons)}")

    # ---- 无门控触发：保留云模型原判定 ----
    return (cloud_grade, "物理安全, 保留云模型等级")


# ============================================================
# 九、主流程
# ============================================================

def run_evaluation(data_dir=None):
    if data_dir is None:
        data_dir = Path(__file__).parent

    data_dir = Path(data_dir)

    section_data    = load_json(data_dir / "section_data.json")
    leak_points     = load_json(data_dir / "leak_points.json")
    section_gps     = load_json(data_dir / "section_gps.json")
    geo_cls         = load_json(data_dir / "geo_classification.json")
    buildings       = load_json(data_dir / "buildings_safety.json")
    hist_dangers    = load_json(data_dir / "historical_dangers.json")

    leak_count = match_leak_points(leak_points, section_gps)
    uav_evidence = match_uav_leakage_evidence(leak_points, section_gps)
    print("渗漏计数:", leak_count)
    print("UAV渗漏证据:", {
        k: {"点数": v["渗漏点数"], "密度": v["加权渗漏点密度_点每100m"], "等级": v["UAV证据等级"]}
        for k, v in uav_evidence.items()
    })

    results = []
    for sec in section_data:
        stake = sec["桩号"]

        scores = {
            "A1": score_A1(sec),
            "A2": score_A2(stake, geo_cls),
            "A3": score_A3(stake, buildings),
            "A4": optional_indicator_score(sec, "A4"),
            "A5": score_A5(sec),
            "A6": optional_indicator_score(sec, "A6") if optional_indicator_score(sec, "A6") is not None else score_A6(stake, hist_dangers),
            "A7": optional_indicator_score(sec, "A7") if optional_indicator_score(sec, "A7") is not None else score_A7(sec),
            "A8": optional_indicator_score(sec, "A8"),
            "A9": optional_indicator_score(sec, "A9"),
            "B1": score_B1(sec),
            "B2": score_from_optional_or_calculated(sec, "B2"),
            "B3": score_from_optional_or_calculated(sec, "B3"),
            "B4": score_from_optional_or_calculated(sec, "B4"),
            "C1": score_C1(sec),
            "C2": optional_indicator_score(sec, "C2"),
            "C3": score_C3(uav_evidence.get(stake, {"渗漏点数": leak_count.get(stake, 0)})),
            "C4": score_C4(sec),
            "C5": score_C5(sec),
            "C6": optional_indicator_score(sec, "C6"),
            "D1": score_D1(sec),
            "D2": score_D2(sec),
            "D3": score_D3(sec, hist_dangers),
            "D4": score_from_optional_or_calculated(sec, "D4"),
            "D5": optional_indicator_score(sec, "D5"),
            "E1": optional_indicator_score(sec, "E1"),
            "E2": optional_indicator_score(sec, "E2"),
            "E3": optional_indicator_score(sec, "E3"),
            "E4": optional_indicator_score(sec, "E4"),
            "E5": optional_indicator_score(sec, "E5"),
        }

        level1 = calc_level1(scores, sec)
        dyn_w = state_variable_weight(sec)

        available_level = {k: v for k, v in level1.items() if v is not None}
        available_w = {k: dyn_w[k] for k in available_level}
        w_total = sum(available_w.values())
        effective_dyn_w = {k: v / w_total for k, v in available_w.items()}
        composite = sum(available_level[k] * effective_dyn_w[k] for k in available_level)

        # 临界安全惩罚已废弃（恒返回 1.0）
        alpha = critical_penalty(sec)
        final_score = composite * alpha

        cloud = cloud_model_classify(final_score)
        gated_grade, gate_note = physical_gate(sec, cloud["安全等级"])

        # ---- 漫顶预警（独立于评分，仅作提醒） ----
        fb = FREEBOARD_LAKE if sec["是否为湖堤"] else FREEBOARD_RIVER
        required_elev = sec["设计洪水位_m"] + fb
        overtop_margin = sec["堤顶高程_m"] - required_elev
        overtop_warning = overtop_margin < 0
        overtop_note = ""
        if overtop_warning:
            overtop_note = f"漫顶预警: 堤顶高程不足，差值={-overtop_margin:.2f}m"

        record = {
            "桩号": stake,
            "综合得分": cloud["综合得分"],
            "安全等级": gated_grade,
            "云模型原等级": cloud["安全等级"],
            "门控说明": gate_note,
            "漫顶预警": overtop_warning,
            "漫顶说明": overtop_note,
            "UAV渗漏观测证据": uav_evidence.get(stake),
            "相似度": cloud["相似度"],
            "云参数": cloud["云参数"],
            "一级得分": {k: round(v, 4) if isinstance(v, (int, float)) else v for k, v in level1.items()},
            "有效动态权重": {k: round(v, 6) for k, v in effective_dyn_w.items()},
            "原始动态权重": {k: round(v, 6) for k, v in dyn_w.items()},
            "缺失待输入指标": [k for k, v in scores.items() if v is None],
            "二级得分": {k: round(v, 4) if isinstance(v, float) else v for k, v in scores.items()},
        }
        results.append(record)

        tag = "" if gated_grade == cloud["安全等级"] else f"  [门控:{cloud['安全等级']}→{gated_grade}]"
        warn = "  [漫顶]" if overtop_warning else ""
        print(f"[{stake}] 综合={cloud['综合得分']:.2f}  等级={gated_grade}{tag}{warn}")

    out_path = data_dir / "final_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n评价完成，结果已保存到: {out_path}")

    return results


if __name__ == "__main__":
    run_evaluation()

