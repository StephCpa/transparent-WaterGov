"""Excel import: template layout, conversion rules, row-numbered messages and the example round trip."""

import csv
import io
import json
import sys
import tempfile
import threading
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "excel_import"))
sys.path.insert(0, str(ROOT / "tools"))

import gen_import_template as G  # noqa: E402
import levee_excel as L  # noqa: E402
from levee_eval import evaluate, schema  # noqa: E402
from levee_eval.wsgi import application  # noqa: E402

TEMPLATE = ROOT / "excel_import" / "levee_import_template.xlsx"
EXAMPLE = ROOT / "excel_import" / "levee_import_example.xlsx"
DEMO = ROOT / "excel_import" / "levee_import_k45500_demo.xlsx"

BASE = {"section_id": "K45+500", "levee_type": "河堤", "crest_elevation": 36.30, "layer_name": "淤泥质粉质黏土",
        "layer_gs": 2.75, "layer_e": 1.115, "grad_foundation": 0.865, "grad_body": 0.535, "grad_contact": 0.535,
        "body_gs": 2.70, "body_e": 0.778, "design_flood_level": 34.04, "crest_width": 7.0, "outer_slope": "1:2.7",
        "inner_slope": "1：2.8", "foundation_class": "D类", "fill_quality": "较差", "flood_standard": "符合",
        "structure": "无", "over_crossing": "无", "dangers": "有"}
DANGERS = [{"section_id": "K45+500", "type": "蚁穴", "reinforced": "未处理", "severity": "严重"},
           {"section_id": "K45+500", "type": "管涌", "reinforced": "已处理"}]


def book(main, dangers=(), events=(), other=(), columns=None):
    """Workbook cells as read_xlsx returns them: band row 1, header row 2, data from row 3."""
    columns = columns or L.COLUMNS
    sheet = {1: {0: "分组"}, 2: {j: c.header + ("*" if c.required else "") for j, c in enumerate(columns)}}
    for r, row in enumerate(main, 3):
        sheet[r] = {j: row[c.key] for j, c in enumerate(columns) if row.get(c.key) is not None}
    out = {L.SHEET_MAIN: sheet}
    for name, cols, rows in ((L.SHEET_DANGERS, L.DANGER_COLUMNS, dangers), (L.SHEET_EVENTS, L.EVENT_COLUMNS, events),
                             (L.SHEET_OTHER, L.OTHER_COLUMNS, other)):
        ds = {1: {j: c.header for j, c in enumerate(cols)}}
        for r, row in enumerate(rows, 2):
            ds[r] = {j: row[c.key] for j, c in enumerate(cols) if row.get(c.key) is not None}
        out[name] = ds
    return out


def convert(main_overrides=None, dangers=DANGERS, events=(), other=(), auto=None, extra_rows=()):
    row = {**BASE, **(main_overrides or {})}
    res = L.convert_sheets(book([row, *extra_rows], dangers, events, other), auto)
    return res, res.rows[0]


class Example(unittest.TestCase):
    def test_example_round_trip(self):
        imp = L.convert_sheets(L.read_xlsx(EXAMPLE))
        self.assertEqual(len(imp.rows), 24)
        bad = {r.row: r.problems for r in imp.rows if not r.ok}
        self.assertEqual(bad, {6: ["堤顶宽度(m)：须大于 0"],
                               11: ["填土质量：只能填 较好、一般、较差（填的是“好”）"],
                               20: ["堤基渗透比降：必填（可由前两步按桩号自动带入）"]})
        original = G.example_requests()
        grades = []
        for rr in imp.rows:
            if not rr.ok:
                continue
            a = evaluate(original[rr.row - 3], detail="summary")["result"]
            b = evaluate(rr.request, detail="summary")["result"]
            for f in ("score", "grade", "gate_reasons", "indicator_scores", "mode_responses", "conclusion_text"):
                self.assertEqual(a[f], b[f], f"row {rr.row} {f}")
            grades.append(b["grade"])
        self.assertEqual({g: grades.count(g) for g in "ABC"}, {"A": 11, "B": 5, "C": 5})

    def test_k45500_demo_with_existing_data(self):
        imp = L.convert_sheets(L.read_xlsx(DEMO))
        self.assertEqual([r.problems for r in imp.rows], [[]])
        _, base = convert()                       # the same section as typed in these tests
        demo = imp.rows[0].request
        self.assertEqual({k: v for k, v in demo.items() if k != "request_id"},
                         {k: v for k, v in base.request.items() if k != "request_id"} | {
                             "section": {**base.request["section"], "control_layer": {
                                 "name": "淤泥质粉质黏土（MCN1）", "Gs": 2.75, "e": 1.115}}})
        res = evaluate(demo)["result"]
        self.assertEqual((round(res["score"], 1), res["grade"], res["dominant_mode"]["name"]), (22.8, "C", "渗流破坏"))
        self.assertEqual([g["indicator"] for g in res["gates_not_checked"]], ["D1", "D2", "D3", "A5", "C3"])
        demo["computation"].update(back_slope_fos=1.155, front_slope_fos=2.063)   # step 2 of the demo
        res = evaluate(demo)["result"]
        self.assertEqual((round(res["score"], 1), res["grade"]), (24.3, "C"))
        self.assertEqual([(d["indicator"], d["cap"]) for d in res["gate_details"]], [("C1", "C"), ("D1", "B")])

    def test_template_layout(self):
        sheets = L.read_xlsx(TEMPLATE)
        self.assertEqual(list(sheets), [L.SHEET_HELP, L.SHEET_MAIN, L.SHEET_DANGERS, L.SHEET_EVENTS, L.SHEET_OTHER])
        main = sheets[L.SHEET_MAIN]
        self.assertEqual(sorted(main), [1, 2])                       # no data rows in the template
        self.assertEqual([main[2][j] for j in sorted(main[2])],
                         [c.header + ("*" if c.required else "") for c in L.COLUMNS])
        self.assertEqual([v for _, v in sorted(main[1].items())], [t for _, t in L.GROUPS])
        for name, cols in L.DETAIL_SHEETS.items():
            self.assertEqual(sheets[name], {1: {j: c.header + ("*" if c.required else "") for j, c in enumerate(cols)}})
        help_text = {v for row in sheets[L.SHEET_HELP].values() for v in row.values()}
        for c in L.COLUMNS:
            self.assertIn(c.header, help_text)
        self.assertEqual(L.convert_sheets(sheets).rows, [])

    def test_constants_match_schema(self):
        self.assertEqual(L.POSITIONS, schema.POSITIONS)
        self.assertTrue(set(L.STRUCTURE_CLASSES) < set(schema.BUILDING_CLASSES))
        for c in L.COLUMNS:
            if c.path and c.path.startswith("qualitative."):
                cats = schema.QUALITATIVE_CATEGORIES[c.path.split(".")[1]]
                self.assertTrue(set(c.options.values()) <= set(cats), c.header)
            elif c.path and "." in c.path:
                self.assertTrue(c.path in schema.BY_PATH, c.path)
                enum = schema.BY_PATH[c.path].enum
                if enum and c.kind == "choice":
                    self.assertTrue(set(c.options.values()) <= set(enum), c.header)


class Rules(unittest.TestCase):
    def test_base_row(self):
        _, rr = convert()
        self.assertEqual(rr.problems, [])
        q = rr.request
        self.assertEqual(q["section"]["outer_slope_ratio"], 2.7)
        self.assertEqual(q["section"]["inner_slope_ratio"], 2.8)
        self.assertEqual(q["section"]["foundation_class"], "D")
        self.assertIs(q["section"]["is_lake_levee"], False)
        self.assertEqual(q["records"]["fill_quality"], "质量较差")
        self.assertEqual(q["records"]["crossing_structure_class"], "不涉及")
        self.assertEqual(q["qualitative"], {"B2": "符合", "A9": "不涉及", "A8": "不涉及", "B4": "不涉及",
                                            "C6": "不涉及", "D4": "不涉及"})
        self.assertEqual(q["records"]["historical_dangers"],
                         [{"type": "蚁穴", "reinforced": False, "severity": "严重"}, {"type": "管涌", "reinforced": True}])
        self.assertEqual(q["survey"], {"soft_foundation_status": "unknown"})
        self.assertNotIn("inspection", q)
        x = evaluate(q)["result"]
        self.assertEqual((round(x["score"], 1), x["grade"]), (22.8, "C"))   # the K45+500 page

    def test_values_users_type(self):
        _, rr = convert({"outer_slope": 2.5, "foundation_class": "b", "fill_quality": "质量一般", "structure": "不涉及"})
        self.assertEqual(rr.problems, [])
        self.assertEqual((rr.request["section"]["outer_slope_ratio"], rr.request["section"]["foundation_class"],
                          rr.request["records"]["fill_quality"]), (2.5, "B", "质量一般"))
        _, rr = convert({"outer_slope": "2:3", "crest_width": "七米", "levee_type": "江堤"})
        self.assertEqual(rr.problems, ["堤段类型：只能填 河堤、湖堤（填的是“江堤”）",
                                       "堤顶宽度(m)：须为数字（填的是“七米”；没有资料请留空）",
                                       "迎水坡坡比：坡比请填 1:m 或 m（填的是“2:3”）"])
        _, rr = convert({"outer_slope": 0.04375})                # “1:3” typed into a General cell (01:03 a.m.)
        self.assertEqual(rr.problems, ["迎水坡坡比：看起来被 Excel 当成了时间，请把单元格设为文本后填 1:3，或直接填 3"])
        _, rr = convert({"design_flood_level": None})
        self.assertEqual(rr.problems, ["设计洪水位(m)：必填"])

    def test_dangers_need_an_explicit_answer(self):
        _, rr = convert({"dangers": None}, dangers=())
        self.assertEqual(rr.problems, ["历史险情：必填（已核查没有险情记录填“无”）"])
        _, rr = convert({"dangers": None})                     # records present: taken as 有
        self.assertEqual(len(rr.request["records"]["historical_dangers"]), 2)
        _, rr = convert({"dangers": "无"})
        self.assertEqual(rr.problems, ["历史险情：填了“无”，但“历史险情”表中有本桩号的2条记录"])
        _, rr = convert({"dangers": "有"}, dangers=())
        self.assertEqual(rr.problems, ["历史险情：填了“有”，请在“历史险情”表逐条填写"])
        _, rr = convert({"dangers": "无"}, dangers=())
        self.assertEqual(rr.request["records"]["historical_dangers"], [])
        res, rr = convert(dangers=[{**DANGERS[0], "reinforced": "处理中"}, {**DANGERS[1], "section_id": "K9+999"}])
        self.assertEqual(rr.problems, ["“历史险情”表第2行 是否已处理：只能填 已处理、未处理（填的是“处理中”）"])
        self.assertEqual(res.file_notes, ["“历史险情”表第3行：桩号 K9+999 在“断面”表中没有，这一行没有使用"])

    def test_structure_present(self):
        _, rr = convert({"structure": "三类"})
        self.assertEqual(rr.request["records"]["crossing_structure_class"], "三类")
        self.assertNotIn("C6", rr.request["qualitative"])
        self.assertEqual(rr.notes, ["有穿堤建筑物：A8、B4、C6、D4 未在“其他指标”表给出，按缺失处理"])
        _, rr = convert({"structure": "三类"}, other=[{"section_id": "K45+500", "code": "c6", "value": "明显渗漏"},
                                                     {"section_id": "K45+500", "code": "D4", "value": 60}])
        self.assertEqual((rr.request["qualitative"]["C6"], rr.request["qualitative"]["D4"]), ("明显渗漏", 60.0))

    def test_other_indicators(self):
        _, rr = convert(other=[{"section_id": "K45+500", "code": "B2", "value": "不符合"}])
        self.assertEqual(rr.problems, ["“其他指标”表第2行：B2 已由“断面”表的“防洪标准”列给出，不要重复填"])
        _, rr = convert(other=[{"section_id": "K45+500", "code": "Z9", "value": 50}])
        self.assertEqual(rr.problems, ["“其他指标”表第2行 结论或分数：没有这个指标代码"])
        _, rr = convert(other=[{"section_id": "K45+500", "code": "A4", "value": "良"},
                               {"section_id": "K45+500", "code": "E1", "value": 140}])
        self.assertEqual(rr.problems, ["“其他指标”表第3行 结论或分数：分数须在 0–100 之间"])

    def test_settlement(self):
        _, rr = convert({"soft_foundation": "非软基段"})
        self.assertEqual(rr.request["survey"], {"soft_foundation_status": "non_soft"})
        _, rr = convert({"settlement": 12, "settlement_diff": 3})
        self.assertEqual(rr.request["survey"], {"soft_foundation_settlement_cm": 12.0,
                                                "soft_foundation_settlement_diff_cm": 3.0})
        _, rr = convert({"settlement": 12})
        self.assertEqual(rr.problems, ["软基沉降差(cm)：填了沉降量时必须同时填沉降差"])
        _, rr = convert({"settlement_diff": 3})
        self.assertEqual(rr.problems, ["软基沉降量(cm)：填了沉降差时请同时填沉降量"])
        _, rr = convert({"settlement": 12, "settlement_diff": 3, "soft_foundation": "非软基段"})
        self.assertEqual(rr.problems, ["是否软基段：填了沉降量，应为“软基段”或留空"])

    def test_inspection(self):
        _, rr = convert({"inspection": "未发现险情", "segment_length": 200})
        self.assertEqual(rr.request["inspection"], {"coverage": "complete", "mode": "events",
                                                    "confirmed_events": [], "segment_length_m": 200.0})
        ev = [{"section_id": "K45+500", "position": "堤脚", "repeat_count": 2, "sand": "是", "muddy": "否"}]
        _, rr = convert({"inspection": "有确认险情"}, events=ev)
        self.assertEqual(rr.request["inspection"]["confirmed_events"],
                         [{"position": "堤脚", "repeat_count": 2, "sand": True, "muddy": False}])
        self.assertEqual(evaluate(rr.request)["result"]["observation_gate"]["cap"] is not None, True)
        _, rr = convert({"inspection": "有确认险情"})
        self.assertEqual(rr.problems, ["巡检情况：填了“有确认险情”，请在“巡检事件”表逐条填写"])
        _, rr = convert({"inspection": "未发现险情"}, events=ev)
        self.assertEqual(rr.problems, ["巡检情况：填了“未发现险情”，但“巡检事件”表中有本桩号的1条记录"])
        _, rr = convert(events=[{**ev[0], "repeat_count": 1.5}], main_overrides={"inspection": "有确认险情"})
        self.assertEqual(rr.problems, ["“巡检事件”表第2行 重复次数：须为整数"])

    def test_auto_fill_from_previous_steps(self):
        blank = {c.key: None for c in L.COLUMNS if c.group == "auto"}
        _, rr = convert(blank)
        self.assertIn("堤基渗透比降：必填（可由前两步按桩号自动带入）", rr.problems)
        auto = {"K45+500": {"section": {"crest_elevation_m": 36.30,
                                        "control_layer": {"name": "淤泥质粉质黏土", "Gs": 2.75, "e": 1.115}},
                            "computation": {"foundation_gradient": 0.865, "body_gradient": 0.535,
                                            "contact_gradient": 0.535, "body_Gs": 2.70, "body_e": 0.778}}}
        _, rr = convert(blank, auto=auto)
        self.assertEqual(rr.problems, [])
        _, full = convert()
        self.assertEqual(evaluate(rr.request)["result"]["score"], evaluate(full.request)["result"]["score"])
        _, rr = convert({**blank, "grad_foundation": 0.5}, auto=auto)       # a typed value wins
        self.assertEqual(rr.request["computation"]["foundation_gradient"], 0.5)
        sheets = book([{k: v for k, v in BASE.items() if k not in blank}], DANGERS,
                      columns=[c for c in L.COLUMNS if c.group != "auto"])
        with self.assertRaises(L.ImportFileError):
            L.convert_sheets(sheets)                                       # no columns and no auto data
        self.assertEqual(L.convert_sheets(sheets, auto).rows[0].problems, [])

    def test_duplicates_and_blank_rows(self):
        res, _ = convert(extra_rows=[{}, dict(BASE)])
        self.assertEqual([r.row for r in res.rows], [3, 5])
        self.assertEqual(res.rows[1].problems[0], "桩号：与第3行重复")

    def test_missing_sheet_or_column(self):
        with self.assertRaises(L.ImportFileError):
            L.convert_sheets({"Sheet1": {}})
        sheets = book([BASE], columns=[c for c in L.COLUMNS if c.key != "fill_quality"])
        with self.assertRaises(L.ImportFileError) as cm:
            L.convert_sheets(sheets)
        self.assertIn("填土质量", str(cm.exception))


class Reader(unittest.TestCase):
    def test_reads_shared_inline_rich_and_bool_cells(self):
        ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
        files = {
            "[Content_Types].xml": "<Types/>",
            "xl/workbook.xml": f'<workbook {ns} xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/'
                               'relationships"><sheets><sheet name="断面" sheetId="1" r:id="rId1"/></sheets></workbook>',
            "xl/_rels/workbook.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
                                          'relationships"><Relationship Id="rId1" Target="worksheets/s1.xml"/>'
                                          '</Relationships>',
            "xl/sharedStrings.xml": f'<sst {ns}><si><t>桩号</t></si><si><r><t>K0</t></r><r><t>+100</t></r>'
                                    '<rPh><t>ignored</t></rPh></si></sst>',
            "xl/worksheets/s1.xml": f'<worksheet {ns}><sheetData>'
                                    '<row r="2"><c r="A2" t="s"><v>0</v></c><c r="C2" t="inlineStr"><is><t>备注</t></is></c></row>'
                                    '<row r="3"><c t="s"><v>1</v></c><c><v>2.5</v></c><c t="b"><v>1</v></c>'
                                    '<c r="E3" t="str"><f>A1</f><v>公式</v></c></row>'
                                    '</sheetData></worksheet>',
        }
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "t.xlsx"
            with zipfile.ZipFile(path, "w") as z:
                for name, text in files.items():
                    z.writestr(name, text)
            self.assertEqual(L.read_xlsx(path), {"断面": {2: {0: "桩号", 2: "备注"}, 3: {0: "K0+100", 1: 2.5, 2: True, 4: "公式"}}})
            bad = Path(d) / "t.xls"
            bad.write_bytes(b"\xd0\xcf\x11\xe0 old excel")
            with self.assertRaises(L.ImportFileError):
                L.read_xlsx(bad)


class CommandLine(unittest.TestCase):
    def run_cli(self, *extra):
        with tempfile.TemporaryDirectory() as d:
            out, csv_path = Path(d) / "batch.json", Path(d) / "results.csv"
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = L.main([str(EXAMPLE), "-o", str(out), "--evaluate", str(csv_path), *extra])
            with open(csv_path, encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
            return code, json.loads(out.read_text(encoding="utf-8")), rows, buf.getvalue()

    def check(self, code, batch, rows, text):
        self.assertEqual(code, 2)                          # some rows need fixing
        self.assertEqual(len(batch["items"]), 21)
        self.assertEqual(len(rows), 24)
        self.assertEqual([r["状态"] for r in rows].count("需修改"), 3)
        k0400 = next(r for r in rows if r["桩号"] == "K0+400")
        self.assertEqual((k0400["等级"], k0400["最大渗透比降比值"], k0400["缺的资料"]), ("C", "1.16", "沉降资料、巡检"))
        self.assertTrue(k0400["一句话结论"].startswith("K0+400：堤基渗透比降达到临界"))
        self.assertIn("C级 5，B级 5，A级 11", text)
        self.assertIn("第 11 行（K1+600）填土质量", text)

    def test_local(self):
        self.check(*self.run_cli())

    def test_http(self):
        from socketserver import ThreadingMixIn
        from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

        class Srv(ThreadingMixIn, WSGIServer):
            daemon_threads = True

        class Quiet(WSGIRequestHandler):
            def log_message(self, *a):
                pass

        httpd = make_server("127.0.0.1", 0, application, Srv, Quiet)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            self.check(*self.run_cli("--url", f"http://127.0.0.1:{httpd.server_port}"))
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
