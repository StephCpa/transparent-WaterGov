"""Excel import for the levee evaluation service (standard library only).

The import template has one row per section on the sheet “断面” and three optional
sheets: “历史险情”, “巡检事件” and “其他指标”.  This script turns every row into an
evaluation request and reports problems by Excel row number, so whoever filled in the
file can fix it without reading the API documentation.

    python excel_import/levee_excel.py 断面资料.xlsx -o batch_request.json
    python excel_import/levee_excel.py 断面资料.xlsx --evaluate results.csv
    python excel_import/levee_excel.py 断面资料.xlsx --url http://127.0.0.1:8080 --evaluate results.csv
    python excel_import/levee_excel.py 断面资料.xlsx --auto auto_fill.json --evaluate results.csv

COLUMNS below is the single source for the template, this converter and the column
table in docs/05_excel_import.md.
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import math
import posixpath
import re
import sys
import urllib.error
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
try:
    from levee_eval import schema as _schema
except ImportError:   # converter copied out of the package: conversion still works, local validation is skipped
    _schema = None

SHEET_HELP, SHEET_MAIN, SHEET_DANGERS, SHEET_EVENTS, SHEET_OTHER = "填写说明", "断面", "历史险情", "巡检事件", "其他指标"
BLANK_TOKENS = {"", "-", "—", "/", "－"}
POSITIONS = ["普通堤身", "堤身", "堤坡", "堤脚", "坡脚", "穿堤建筑物", "建筑物附近", "结合部", "历史险情附近"]
STRUCTURE_CLASSES = ["一类", "二类", "三类", "四类", "1类", "2类", "3类", "4类", "加固", "改建", "重建"]
STRUCTURE_INDICATORS = ("A8", "B4", "C6", "D4")   # set to 不涉及 when there is no crossing structure
MISSING_DATA_NAMES = {"D1": "安全系数", "D2": "安全系数", "D3": "冲刷深度", "A5": "沉降资料", "C3": "巡检"}


class Col:
    """One template column.  options maps what the user picks to the API value."""

    def __init__(self, key, header, group, required, kind, path=None, options=None, aliases=None, note=""):
        self.key, self.header, self.group, self.required, self.kind = key, header, group, required, kind
        self.path, self.options, self.aliases, self.note = path, options or {}, aliases or {}, note


GROUPS = [("basic", "基本信息"), ("auto", "前两步带入（平台可按桩号自动填入）"),
          ("fill", "需要填写"), ("optional", "选填：有资料时再填，没有就留空")]
_FOUNDATION = {k: k for k in "ABCD"}
_FOUNDATION_ALIASES = {f"{k}类": k for k in "ABCD"} | {k.lower(): k for k in "ABCD"} | {f"{k.lower()}类": k for k in "ABCD"}

COLUMNS = [
    Col("section_id", "桩号", "basic", True, "text", "section.section_id",
        note="断面或评价单元编号，如 K45+500；同一文件内不能重复"),
    Col("levee_type", "堤段类型", "basic", True, "choice", "section.is_lake_levee", {"河堤": False, "湖堤": True},
        note="决定堤顶超高要求：河堤 2.0 m，湖堤 2.5 m"),
    Col("crest_elevation", "堤顶高程(m)", "auto", True, "number", "section.crest_elevation_m"),
    Col("layer_name", "控制土层", "auto", False, "text", "section.control_layer.name", note="渗流控制土层名称，可不填"),
    Col("layer_gs", "控制层比重Gs", "auto", True, "number", "section.control_layer.Gs", note="土粒比重，一般 2.6–2.8"),
    Col("layer_e", "控制层孔隙比e", "auto", True, "number", "section.control_layer.e"),
    Col("grad_foundation", "堤基渗透比降", "auto", True, "number", "computation.foundation_gradient", note="渗流计算结果"),
    Col("grad_body", "堤身渗透比降", "auto", True, "number", "computation.body_gradient", note="渗流计算结果"),
    Col("grad_contact", "接触面渗透比降", "auto", True, "number", "computation.contact_gradient", note="渗流计算结果"),
    Col("body_gs", "堤身比重Gs", "auto", False, "number", "computation.body_Gs", note="不填时取控制层"),
    Col("body_e", "堤身孔隙比e", "auto", False, "number", "computation.body_e", note="不填时取控制层"),
    Col("design_flood_level", "设计洪水位(m)", "fill", True, "number", "section.design_flood_level_m"),
    Col("crest_width", "堤顶宽度(m)", "fill", True, "number", "section.crest_width_m"),
    Col("outer_slope", "迎水坡坡比", "fill", True, "ratio", "section.outer_slope_ratio", note="填 1:2.5 或 2.5"),
    Col("inner_slope", "背水坡坡比", "fill", True, "ratio", "section.inner_slope_ratio", note="填 1:3 或 3"),
    Col("foundation_class", "堤基类型", "fill", True, "choice", "section.foundation_class", _FOUNDATION, _FOUNDATION_ALIASES,
        note="地勘报告中的堤基分类"),
    Col("fill_quality", "填土质量", "fill", True, "choice", "records.fill_quality",
        {"较好": "质量较好", "一般": "质量一般", "较差": "质量较差"},
        {"质量较好": "较好", "质量一般": "一般", "质量较差": "较差"}, note="地勘结论"),
    Col("flood_standard", "防洪标准", "fill", False, "choice", "qualitative.B2",
        {"符合": "符合", "待复核": "待复核", "不符合": "不符合"}, note="现状防洪标准是否达到批复标准；不清楚可留空"),
    Col("structure", "穿堤建筑物", "fill", True, "structure", "records.crossing_structure_class",
        {"无": "不涉及", **{k: k for k in STRUCTURE_CLASSES}}, {"不涉及": "无", "没有": "无"},
        note="没有填“无”；有的填安全检测结论"),
    Col("over_crossing", "跨堤交叉工程", "fill", False, "choice", "qualitative.A9",
        {"无": "不涉及", "无影响": "无影响", "轻微影响": "轻微影响", "存在危险": "存在危险"}, {"不涉及": "无", "没有": "无"},
        note="没有跨堤工程填“无”；有的填对堤防的影响"),
    Col("dangers", "历史险情", "fill", True, "dangers", "records.historical_dangers", {"无": False, "有": True},
        {"没有": "无"}, note="已核查没有险情记录填“无”；有的填“有”，并在“历史险情”表逐条填写"),
    Col("back_fos", "背水坡安全系数", "optional", False, "number", "computation.back_slope_fos",
        note="边坡稳定计算的抗滑安全系数；没算过就留空"),
    Col("front_fos", "临水坡安全系数", "optional", False, "number", "computation.front_slope_fos"),
    Col("scour_depth", "冲刷深度(m)", "optional", False, "number", "survey.scour_depth_m", note="堤脚冲刷深度"),
    Col("settlement", "软基沉降量(cm)", "optional", False, "number", "survey.soft_foundation_settlement_cm"),
    Col("settlement_diff", "软基沉降差(cm)", "optional", False, "number", "survey.soft_foundation_settlement_diff_cm",
        note="填了沉降量时必填"),
    Col("soft_foundation", "是否软基段", "optional", False, "soft", "survey.soft_foundation_status",
        {"非软基段": "non_soft", "软基段": "unknown", "不清楚": "unknown"},
        note="没有沉降资料时用；不填按“不清楚”处理（沉降指标按缺失，不按满分）"),
    Col("inspection", "巡检情况", "optional", False, "inspection", "inspection",
        {"无巡检": None, "未发现险情": "none_found", "有确认险情": "events"}, {"无": "无巡检", "没有": "无巡检"},
        note="巡检须完整覆盖本断面且在有效期内；算法候选未经人工复核的不算险情"),
    Col("segment_length", "巡检段长(m)", "optional", False, "number", "inspection.segment_length_m", note="不填按 100 m"),
]
COLUMN_BY_KEY = {c.key: c for c in COLUMNS}
COLUMN_LABELS = {c.path: c.header for c in COLUMNS if c.path and "." in c.path}

DANGER_COLUMNS = [
    Col("section_id", "桩号", "", True, "text"),
    Col("type", "险情类型", "", True, "text", note="如 管涌、散浸、渗漏、崩岸、蚁穴、裂缝"),
    Col("reinforced", "是否已处理", "", True, "choice", options={"已处理": True, "未处理": False},
        aliases={"已加固": "已处理", "未加固": "未处理", "是": "已处理", "否": "未处理"}),
    Col("severity", "严重程度", "", False, "choice", options={k: k for k in ("无", "轻微", "中度", "严重")}),
]
EVENT_COLUMNS = [
    Col("section_id", "桩号", "", True, "text"),
    Col("position", "位置", "", False, "choice", options={k: k for k in POSITIONS}, note="不填按“普通堤身”"),
    Col("repeat_count", "重复次数", "", False, "integer", note="同一位置出现次数，不填按 1"),
    Col("sand", "带砂", "", False, "bool"),
    Col("muddy", "浑水", "", False, "bool"),
    Col("spouting", "冒水", "", False, "bool"),
    Col("clustered", "集中成簇", "", False, "bool"),
]
OTHER_COLUMNS = [
    Col("section_id", "桩号", "", True, "text"),
    Col("code", "指标代码", "", True, "text", note="如 A4、C2、D5、E1"),
    Col("value", "结论或分数", "", True, "text", note="分档名称（见参数字典第2节）或 0–100 分"),
]
DETAIL_SHEETS = {SHEET_DANGERS: DANGER_COLUMNS, SHEET_EVENTS: EVENT_COLUMNS, SHEET_OTHER: OTHER_COLUMNS}
DETAIL_LABELS = {c.key: c.header for c in DANGER_COLUMNS + EVENT_COLUMNS}   # keys are the API field names
_BOOL = {"是": True, "否": False, "有": True, "无": False}


def fill_hint(col):
    """How to fill a column, in one line (used by the template, its instructions sheet and the docs)."""
    if col.kind in ("choice", "structure", "dangers", "soft", "inspection"):
        shown = [k for k in col.options if not re.fullmatch(r"\d类", k)]
        head = "选：" + " / ".join(shown)
    elif col.kind == "ratio":
        head = "坡比"
    elif col.kind in ("number", "integer"):
        unit = re.search(r"\((.*?)\)", col.header)
        head = ("整数" if col.kind == "integer" else "数字") + (f"，单位 {unit.group(1)}" if unit else "")
    elif col.kind == "bool":
        head = "填：是 / 否，不填按否"
    else:
        head = "文字"
    return head + (f"。{col.note}" if col.note else "")


class ImportFileError(Exception):
    """The file as a whole cannot be read (wrong format, missing sheet or columns)."""


# ----------------------------------------------------------------------------- xlsx reader
_M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_P = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_MAX_PART_BYTES = 50 * 2 ** 20


def read_xlsx(path) -> dict:
    """Return {sheet name: {row number: {column index: value}}}; values are str, float or bool."""
    try:
        z = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise ImportFileError("无法读取：不是 .xlsx 文件（.xls 或 .csv 请先在 Excel / WPS 中另存为 .xlsx）") from exc
    with z:
        names = set(z.namelist())

        def part(name):
            if z.getinfo(name).file_size > _MAX_PART_BYTES:
                raise ImportFileError("文件内容过大")
            return ET.fromstring(z.read(name))

        if "xl/workbook.xml" not in names:
            raise ImportFileError("无法读取：不是 .xlsx 文件")
        shared = [_rich_text(si) for si in part("xl/sharedStrings.xml").iter(_M + "si")] \
            if "xl/sharedStrings.xml" in names else []
        rels = {r.get("Id"): r.get("Target", "") for r in part("xl/_rels/workbook.xml.rels").iter(_P + "Relationship")}
        sheets = {}
        for s in part("xl/workbook.xml").iter(_M + "sheet"):
            target = rels.get(s.get(_R + "id"), "")
            name = posixpath.normpath(target.lstrip("/") if target.startswith("/") else "xl/" + target)
            if name in names:
                sheets[s.get("name")] = _sheet_rows(part(name), shared)
    return sheets


def _rich_text(node):
    if node is None:
        return ""
    out = []
    for child in node:       # plain <t>, or rich-text runs <r><t>; phonetic hints <rPh> are skipped
        if child.tag == _M + "t":
            out.append(child.text or "")
        elif child.tag == _M + "r":
            t = child.find(_M + "t")
            out.append((t.text or "") if t is not None else "")
    return "".join(out)


def _col_index(ref):
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group(0):
        n = n * 26 + ord(ch) - 64
    return n - 1


def _cell_value(c, shared):
    t = c.get("t", "n")
    if t == "inlineStr":
        return _rich_text(c.find(_M + "is"))
    v = c.find(_M + "v")
    if v is None or v.text is None:
        return None
    if t == "s":
        return shared[int(v.text)]
    if t == "b":
        return v.text.strip() == "1"
    if t in ("str", "e"):
        return v.text
    try:
        return float(v.text)
    except ValueError:
        return v.text


def _sheet_rows(root, shared):
    rows, last = {}, 0
    for row in root.iter(_M + "row"):
        rnum = int(row.get("r") or last + 1)
        last, cells, nxt = rnum, {}, 0
        for c in row.findall(_M + "c"):
            col = _col_index(c.get("r")) if c.get("r") else nxt
            nxt = col + 1
            value = _cell_value(c, shared)
            if value is not None and not (isinstance(value, str) and not value.strip()):
                cells[col] = value
        if cells:
            rows[rnum] = cells
    return rows


# ----------------------------------------------------------------------------- cell parsing
def _norm(text):
    s = str(text or "").replace("（", "(").replace("）", ")").replace("＊", "*")
    return re.sub(r"[\s*]", "", re.sub(r"\(.*?\)", "", s))


def _text(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "是" if v else "否"
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else repr(v)
    return str(v).strip()


def _number(v):
    if isinstance(v, bool):
        raise ValueError("须为数字")
    if isinstance(v, (int, float)):
        x = float(v)
    else:
        s = _text(v)
        if s in BLANK_TOKENS:
            return None
        try:
            x = float(s)
        except ValueError:
            raise ValueError(f"须为数字（填的是“{s}”；没有资料请留空）") from None
    if not math.isfinite(x):
        raise ValueError("须为数字")
    return x


def _ratio(v):
    if isinstance(v, float) and 0 < v < 0.5:    # Excel turned "1:3" typed into a General cell into a time of day
        raise ValueError("看起来被 Excel 当成了时间，请把单元格设为文本后填 1:3，或直接填 3")
    s = _text(v).replace("：", ":")
    if ":" in s:
        head, _, tail = s.partition(":")
        if head.strip() not in ("1", "1.0"):
            raise ValueError(f"坡比请填 1:m 或 m（填的是“{s}”）")
        return _number(tail.strip())
    return _number(v)


def _choice(col, v):
    s = _text(v)
    if s in BLANK_TOKENS:
        return None, None
    pick = col.aliases.get(s, s)
    if pick not in col.options:
        raise ValueError(f"只能填 {'、'.join(col.options)}（填的是“{s}”）")
    return pick, col.options[pick]


def _parse(col, v):
    """Return the API value (None when blank); raise ValueError with a message for the user."""
    if col.kind == "number":
        return _number(v)
    if col.kind == "ratio":
        return _ratio(v)
    if col.kind == "integer":
        x = _number(v)
        if x is not None and not x.is_integer():
            raise ValueError("须为整数")
        return None if x is None else int(x)
    if col.kind == "bool":
        s = _text(v)
        if s in BLANK_TOKENS:
            return None
        if s not in _BOOL:
            raise ValueError(f"只能填 是、否（填的是“{s}”）")
        return _BOOL[s]
    if col.kind == "text":
        s = _text(v)
        return None if s in BLANK_TOKENS else s
    return _choice(col, v)[1]


def _put(obj, path, value):
    keys = path.split(".")
    for k in keys[:-1]:
        obj = obj.setdefault(k, {})
    obj[keys[-1]] = value


def _get(obj, path):
    for k in path.split("."):
        if not isinstance(obj, dict) or k not in obj:
            return None
        obj = obj[k]
    return obj


def _merge(base, over):
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def _header_row(rows, limit=10):
    for rnum in sorted(rows)[:limit]:
        names = {c: _norm(v) for c, v in rows[rnum].items()}
        if "桩号" in names.values():
            return rnum, names
    return None, {}


def _map_columns(names, columns, sheet):
    by_norm = {_norm(c.header): c for c in columns}
    colmap, unknown = {}, []
    for idx, n in sorted(names.items()):
        c = by_norm.get(n)
        if c is None:
            unknown.append(n)
        elif c.key in colmap:
            raise ImportFileError(f"“{sheet}”表中“{c.header}”列重复")
        else:
            colmap[c.key] = idx
    return colmap, unknown


# ----------------------------------------------------------------------------- conversion
class RowResult:
    def __init__(self, row, section_id):
        self.row, self.section_id = row, section_id
        self.request = None
        self.problems, self.notes = [], []
        self.origin = dict(COLUMN_LABELS)   # API path -> where the user typed it (for error messages)

    @property
    def ok(self):
        return self.request is not None and not self.problems


class ImportResult:
    def __init__(self):
        self.rows: list[RowResult] = []
        self.file_notes: list[str] = []

    @property
    def requests(self):
        return [r.request for r in self.rows if r.ok]


def _read_detail(sheets, sheet, columns, known, result):
    """Rows of a detail sheet grouped by 桩号: {section_id: [(row, values, problems)]}."""
    rows = sheets.get(sheet)
    out = {}
    if not rows:
        return out
    hdr, names = _header_row(rows)
    if hdr is None:
        if any(r > 1 for r in rows):
            raise ImportFileError(f"“{sheet}”表找不到表头（应有“桩号”列）")
        return out
    colmap, unknown = _map_columns(names, columns, sheet)
    for c in columns:
        if c.required and c.key not in colmap:
            raise ImportFileError(f"“{sheet}”表缺少“{c.header}”列")
    if unknown:
        result.file_notes.append(f"“{sheet}”表中未使用的列：{'、'.join(unknown)}")
    for rnum in sorted(r for r in rows if r > hdr):
        cells = rows[rnum]
        raw = {c.key: cells.get(colmap[c.key]) for c in columns if c.key in colmap}
        if all(_text(v) in BLANK_TOKENS for v in raw.values()):
            continue
        where = f"“{sheet}”表第{rnum}行"
        sid = _text(raw.get("section_id"))
        values, problems = {}, []
        for c in columns:
            if c.key == "section_id":
                continue
            try:
                val = _parse(c, raw.get(c.key))
            except ValueError as exc:
                problems.append(f"{where} {c.header}：{exc}")
                continue
            if val is None and c.required:
                problems.append(f"{where} {c.header}：必填")
            values[c.key] = val
        if not sid:
            result.file_notes.append(f"{where}：缺桩号，这一行没有使用")
        elif sid not in known:
            result.file_notes.append(f"{where}：桩号 {sid} 在“断面”表中没有，这一行没有使用")
        else:
            out.setdefault(sid, []).append((rnum, values, problems))
    return out


def convert_sheets(sheets: dict, auto: dict | None = None) -> ImportResult:
    """Convert workbook cells (as returned by read_xlsx) into evaluation requests."""
    result = ImportResult()
    main = sheets.get(SHEET_MAIN)
    if main is None:
        raise ImportFileError(f"找不到“{SHEET_MAIN}”表（请使用导入模板，表名不要改）")
    hdr, names = _header_row(main)
    if hdr is None:
        raise ImportFileError(f"“{SHEET_MAIN}”表找不到表头（应有“桩号”列）")
    colmap, unknown = _map_columns(names, COLUMNS, SHEET_MAIN)
    for c in COLUMNS:
        if c.required and c.key not in colmap and (c.group != "auto" or auto is None):
            raise ImportFileError(f"“{SHEET_MAIN}”表缺少必填列“{c.header}”")
    if unknown:
        result.file_notes.append(f"“{SHEET_MAIN}”表中未使用的列：{'、'.join(unknown)}")

    raw_rows, seen = [], {}
    for rnum in sorted(r for r in main if r > hdr):
        raw = {k: main[rnum].get(i) for k, i in colmap.items()}
        if all(_text(v) in BLANK_TOKENS for v in raw.values()):
            continue
        rr = RowResult(rnum, _text(raw.get("section_id")))
        if not rr.section_id:
            rr.problems.append("桩号：必填")
        elif rr.section_id in seen:
            rr.problems.append(f"桩号：与第{seen[rr.section_id]}行重复")
        else:
            seen[rr.section_id] = rnum
        raw_rows.append((rr, raw))
        result.rows.append(rr)

    known = set(seen)
    details = {s: _read_detail(sheets, s, cols, known, result) for s, cols in DETAIL_SHEETS.items()}
    auto = auto or {}
    for rr, raw in raw_rows:
        _convert_row(rr, raw, details, auto.get(rr.section_id) if rr.section_id in seen else None)
        if rr.request is not None and not rr.problems and _schema is not None:
            for err in _schema.validate(rr.request):
                rr.problems.append(_error_text(err, rr.origin))
    return result


def _convert_row(rr, raw, details, auto_part):
    req = {"request_id": f"xlsx-row-{rr.row}", "section": {"section_id": rr.section_id},
           "computation": {}, "survey": {}, "records": {}, "qualitative": {}}
    picked = {}
    for c in COLUMNS:
        if c.key == "section_id":
            continue
        v = raw.get(c.key)
        try:
            if c.kind in ("choice", "structure", "dangers", "soft", "inspection"):
                picked[c.key], val = _choice(c, v)
            else:
                val = _parse(c, v)
        except ValueError as exc:
            rr.problems.append(f"{c.header}：{exc}")
            continue
        if val is None and picked.get(c.key) is None and c.required and c.group != "auto" and c.kind != "dangers":
            rr.problems.append(f"{c.header}：必填")
            continue
        if c.kind in ("choice", "number", "ratio", "text") and val is not None:
            _put(req, c.path, val)
            rr.origin[c.path] = c.header

    sid = rr.section_id
    # crossing structure: “无” also marks the structure indicators as not applicable
    if picked.get("structure") is not None:
        req["records"]["crossing_structure_class"] = COLUMN_BY_KEY["structure"].options[picked["structure"]]
        rr.origin["records.crossing_structure_class"] = "穿堤建筑物"
        if picked["structure"] == "无":
            for code in STRUCTURE_INDICATORS:
                req["qualitative"][code] = "不涉及"
                rr.origin[f"qualitative.{code}"] = "穿堤建筑物"

    # historical dangers: explicit 无 / 有, records on their own sheet
    records = details[SHEET_DANGERS].get(sid, [])
    flag = picked.get("dangers")
    if flag is None and records:
        flag = "有"
    if flag is None:
        if not any(p.startswith("历史险情：") for p in rr.problems):
            rr.problems.append("历史险情：必填（已核查没有险情记录填“无”）")
    elif flag == "无" and records:
        rr.problems.append(f"历史险情：填了“无”，但“历史险情”表中有本桩号的{len(records)}条记录")
    elif flag == "有" and not records:
        rr.problems.append("历史险情：填了“有”，请在“历史险情”表逐条填写")
    else:
        items = []
        for k, (rnum, values, problems) in enumerate(records):
            rr.problems.extend(problems)
            item = {"type": values.get("type"), "reinforced": values.get("reinforced")}
            if values.get("severity") is not None:
                item["severity"] = values["severity"]
            items.append(item)
            rr.origin[f"records.historical_dangers[{k}]"] = f"“历史险情”表第{rnum}行"
        req["records"]["historical_dangers"] = items

    # settlement: without a measured value, say whether this is a soft-foundation section
    survey = req["survey"]
    soft = picked.get("soft_foundation")
    if "soft_foundation_settlement_cm" in survey:
        if soft == "非软基段":
            rr.problems.append("是否软基段：填了沉降量，应为“软基段”或留空")
    elif "soft_foundation_settlement_diff_cm" in survey:
        rr.problems.append("软基沉降量(cm)：填了沉降差时请同时填沉降量")
    else:
        survey["soft_foundation_status"] = "non_soft" if soft == "非软基段" else "unknown"
        rr.origin["survey.soft_foundation_status"] = "是否软基段"

    # inspection
    events = details[SHEET_EVENTS].get(sid, [])
    mode = COLUMN_BY_KEY["inspection"].options.get(picked.get("inspection")) if picked.get("inspection") else None
    seg = _get(req, "inspection.segment_length_m")
    req.pop("inspection", None)
    if mode is None:
        if events:
            rr.problems.append(f"巡检情况：“巡检事件”表中有本桩号的{len(events)}条记录，请填“有确认险情”")
        if seg is not None:
            rr.notes.append("没有巡检，巡检段长未使用")
    elif mode == "none_found" and events:
        rr.problems.append(f"巡检情况：填了“未发现险情”，但“巡检事件”表中有本桩号的{len(events)}条记录")
    elif mode == "events" and not events:
        rr.problems.append("巡检情况：填了“有确认险情”，请在“巡检事件”表逐条填写")
    else:
        insp = {"coverage": "complete", "mode": "events", "confirmed_events": []}
        if seg is not None:
            insp["segment_length_m"] = seg
            rr.origin["inspection.segment_length_m"] = "巡检段长(m)"
        for k, (rnum, values, problems) in enumerate(events):
            rr.problems.extend(problems)
            insp["confirmed_events"].append({key: val for key, val in values.items() if val is not None})
            rr.origin[f"inspection.confirmed_events[{k}]"] = f"“巡检事件”表第{rnum}行"
        req["inspection"] = insp
        rr.origin["inspection"] = "巡检情况"

    # other indicators
    for rnum, values, problems in details[SHEET_OTHER].get(sid, []):
        rr.problems.extend(problems)
        code = (values.get("code") or "").upper()
        if not code:
            continue
        where = f"“其他指标”表第{rnum}行"
        if code in req["qualitative"]:
            rr.problems.append(f"{where}：{code} 已由“断面”表的“{rr.origin.get('qualitative.' + code, '')}”列给出，不要重复填")
            continue
        value = values.get("value")
        try:
            value = _number(value) if value is not None else None
        except ValueError:
            pass
        req["qualitative"][code] = value
        rr.origin[f"qualitative.{code}"] = f"{where} 结论或分数"

    if picked.get("structure") not in (None, "无"):
        absent = [c for c in STRUCTURE_INDICATORS if c not in req["qualitative"]]
        if absent:
            rr.notes.append(f"有穿堤建筑物：{'、'.join(absent)} 未在“其他指标”表给出，按缺失处理")

    if auto_part:
        merged = copy.deepcopy({k: v for k, v in auto_part.items() if k != "request_id"})
        req = _merge(merged, req)
        req["section"]["section_id"] = sid
    for c in COLUMNS:
        if c.group == "auto" and c.required and _get(req, c.path) is None:
            rr.problems.append(f"{c.header}：必填（可由前两步按桩号自动带入）")
    if not req["qualitative"]:
        del req["qualitative"]
    rr.request = req


_REASONS = {
    "required": "必填",
    "unknown_indicator": "没有这个指标代码",
    "score_out_of_range_0_100": "分数须在 0–100 之间",
    "category_or_score_required": "须填分档名称或 0–100 分",
    "control_layer_or_soil_layers_required": "须填控制层比重和孔隙比",
    "foundation_class_or_qualitative_A7_required": "须填堤基类型",
    "required_when_settlement_given": "填了沉降量时必须同时填沉降差",
    "unknown_field": "不认识的字段",
}


def _error_text(err, origin):
    path = err.get("field", "")
    probe = path
    while probe and probe not in origin:      # fall back to the nearest parent the user typed, e.g. a sheet row
        m = re.search(r"(\.[^.\[\]]+|\[\d+\])$", probe)
        probe = probe[:m.start()] if m else ""
    if not probe:
        label = path
    elif probe == path:
        label = origin[path]
    else:
        rest = path[len(probe):].lstrip(".")
        label = f"{origin[probe]} {DETAIL_LABELS.get(rest, rest)}"
    reason = err.get("reason", "")
    if reason == "below_minimum":
        msg = f"须大于 {err['minimum']:g}" if err.get("exclusive") else f"不能小于 {err['minimum']:g}"
    elif reason == "above_maximum":
        msg = f"不能大于 {err['maximum']:g}"
    elif reason == "not_in_enum":
        msg = "只能填 " + "、".join(str(x) for x in err.get("allowed", []))
    elif reason.startswith("type_"):
        msg = "格式不对"
    else:
        msg = _REASONS.get(reason, reason)
    return f"{label}：{msg}"


# ----------------------------------------------------------------------------- evaluation and results
def evaluate_requests(requests, url=None, api_key=None, timeout=120):
    """Evaluate in chunks; returns one (ok, payload) per request: (True, response) or (False, error details)."""
    size = _schema.MAX_BATCH if _schema is not None else 1000
    out = []
    for start in range(0, len(requests), size):
        chunk = requests[start:start + size]
        if url:
            data = json.dumps({"items": chunk}, ensure_ascii=False).encode("utf-8")
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["X-API-Key"] = api_key
            req = urllib.request.Request(f"{url.rstrip('/')}/api/v1/evaluate/batch?detail=summary",
                                         data=data, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                raise RuntimeError(f"HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:500]}") from None
        else:
            from levee_eval import evaluate_batch
            body = evaluate_batch(chunk, detail="summary")
        for item in body["results"]:
            out.append((True, item["response"]) if item["ok"] else (False, item["error"]))
    return out


RESULT_HEADERS = ["Excel行号", "桩号", "状态", "等级", "等级含义", "得分", "最大渗透比降比值", "主要风险",
                  "决定等级的原因", "缺的资料", "一句话结论", "需修改的内容"]


def decisive_reason(res):
    """What fixed the grade, in plain words: the limits whose cap equals the final grade, else the score band."""
    grade, score = res["grade"], res["score"]
    picked = [d["plain"] for d in res.get("gate_details", []) if d["cap"] == grade]
    if picked:
        return "；".join(picked)
    if grade == "A":
        return "未触发限级，得分≥80"
    return f"综合得分{score:.1f}（40–80分为B级）" if grade == "B" else f"综合得分{score:.1f}（低于40分为C级）"


def missing_data(res):
    names = []
    for g in res.get("gates_not_checked", []):
        n = MISSING_DATA_NAMES.get(g["indicator"])
        if n and n not in names:
            names.append(n)
    return "、".join(names)


def max_ratio(res):
    checks = res.get("seepage_checks") or {}
    ratios = [checks[k]["ratio"] for k in ("C1", "C4", "C5") if isinstance(checks.get(k), dict) and "ratio" in checks[k]]
    return round(max(ratios), 2) if ratios else None


def result_rows(imported: ImportResult, outcomes=None):
    """One table row per section in Excel order; outcomes aligns with imported.requests."""
    it = iter(outcomes or [])
    rows = []
    for rr in imported.rows:
        base = {"Excel行号": rr.row, "桩号": rr.section_id}
        if not rr.ok:
            rows.append({**base, "状态": "需修改", "需修改的内容": "；".join(rr.problems)})
            continue
        if outcomes is None:
            rows.append({**base, "状态": "可评价"})
            continue
        ok, payload = next(it)
        if not ok:
            details = payload.get("details") or [{"field": "", "reason": payload.get("message", "")}]
            rows.append({**base, "状态": "需修改", "需修改的内容": "；".join(_error_text(d, rr.origin) for d in details)})
            continue
        res = payload["result"]
        rows.append({**base, "状态": "已评价", "等级": res["grade"], "等级含义": res["grade_label"],
                     "得分": round(res["score"], 1), "最大渗透比降比值": max_ratio(res),
                     "主要风险": res["dominant_mode"]["name"], "决定等级的原因": decisive_reason(res),
                     "缺的资料": missing_data(res), "一句话结论": res.get("conclusion_text", "")})
    return rows


def write_csv(path, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:   # BOM so that Excel opens it as UTF-8
        w = csv.DictWriter(f, fieldnames=RESULT_HEADERS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description="把断面资料 Excel 转成评价服务的批量请求，并可直接计算")
    ap.add_argument("xlsx", type=Path, help="按导入模板填写的 .xlsx 文件")
    ap.add_argument("-o", "--output", type=Path, help="写出批量请求 JSON（只含可评价的行）")
    ap.add_argument("--evaluate", type=Path, metavar="RESULTS.csv", help="计算并写出结果表（CSV，Excel 可直接打开）")
    ap.add_argument("--url", help="评价服务地址；不填时在本机直接计算")
    ap.add_argument("--api-key", help="服务设置了 LEVEE_EVAL_API_KEY 时填写")
    ap.add_argument("--auto", type=Path, metavar="AUTO.json",
                    help="前两步的结果：{桩号: {section: {...}, computation: {...}}}，表中留空的项由它补齐")
    args = ap.parse_args(argv)
    try:
        auto = json.loads(args.auto.read_text(encoding="utf-8")) if args.auto else None
        imported = convert_sheets(read_xlsx(args.xlsx), auto)
    except ImportFileError as exc:
        print(f"{args.xlsx.name}：{exc}", file=sys.stderr)
        return 1
    good = imported.requests
    bad = [r for r in imported.rows if not r.ok]
    print(f"{args.xlsx.name}：共 {len(imported.rows)} 个断面，可评价 {len(good)} 个，需修改 {len(bad)} 个")
    for r in bad:
        for p in r.problems:
            print(f"  第 {r.row} 行（{r.section_id or '无桩号'}）{p}")
    for note in imported.file_notes:
        print(f"  提示：{note}")
    for r in imported.rows:
        for n in r.notes:
            print(f"  提示：第 {r.row} 行（{r.section_id}）{n}")
    if args.output:
        args.output.write_text(json.dumps({"items": good}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"已写出批量请求：{args.output}（{len(good)} 项）")
    if args.evaluate:
        outcomes = evaluate_requests(good, args.url, args.api_key) if good else []
        rows = result_rows(imported, outcomes)
        write_csv(args.evaluate, rows)
        done = [r for r in rows if r["状态"] == "已评价"]
        counts = {g: sum(r["等级"] == g for r in done) for g in "CBA"}
        print(f"已评价 {len(done)} 个：C级 {counts['C']}，B级 {counts['B']}，A级 {counts['A']}；结果表：{args.evaluate}")
        worst = [r["桩号"] for r in done if r["等级"] == "C"]
        if worst:
            print("  C级断面：" + "、".join(worst))
        converted = {x.row for x in imported.rows if x.ok}
        rejected = [r for r in rows if r["状态"] == "需修改" and r["Excel行号"] in converted]
        for r in rejected:            # refused by the service although the file looked fine
            print(f"  第 {r['Excel行号']} 行（{r['桩号']}）{r['需修改的内容']}")
        bad = bad + rejected
    return 0 if not bad else 2


if __name__ == "__main__":
    sys.exit(main())
