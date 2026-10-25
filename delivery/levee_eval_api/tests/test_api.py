"""Validation, evidence handling and HTTP behaviour of the service."""

import copy
import io
import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock
from wsgiref.util import setup_testing_defaults

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from levee_eval import RequestInvalid, evaluate, evaluate_batch, validate  # noqa: E402
from levee_eval.engine import MODEL_FILES  # noqa: E402
from levee_eval.openapi import EXAMPLE_REQUEST, build_openapi  # noqa: E402
from levee_eval.wsgi import application  # noqa: E402

DELIVERED_SHA256 = {
    "safety_evaluation.py": "89808cfe9c4393b42074ca39a209820d5be3ee5ac06aa74a9442ed34b0b9f7bb",
    "failure_response_barrier_model.py": "c031bd3a71d38dd88abe04bec4b481b618b019214047a5b0ddbb3d921f8f62aa",
    "failure_mode_indicator_matrix.json": "6b4e5ebf8100c4addc0c2b690badd9db73e5546c80699bac31324cb771b6c088",
}


def req(**changes):
    r = copy.deepcopy(EXAMPLE_REQUEST)
    for path, value in changes.items():
        obj, keys = r, path.split("__")
        for k in keys[:-1]:
            obj = obj.setdefault(k, {})
        if value is ...:
            obj.pop(keys[-1], None)
        else:
            obj[keys[-1]] = value
    return r


def reasons(r):
    return {(e["field"], e["reason"]) for e in validate(r)}


class ModelFiles(unittest.TestCase):
    def test_model_is_the_delivered_code(self):
        self.assertEqual(MODEL_FILES, DELIVERED_SHA256)


class Validation(unittest.TestCase):
    def test_example_is_valid(self):
        self.assertEqual(validate(EXAMPLE_REQUEST), [])

    def test_required_and_unknown_fields(self):
        self.assertIn(("computation.foundation_gradient", "required"), reasons(req(computation__foundation_gradient=...)))
        self.assertEqual(validate(req(computation__back_slope_fos=..., survey__scour_depth_m=...)), [])
        self.assertIn(("records.fill_quality", "required"), reasons(req(records__fill_quality=...)))
        self.assertIn(("records.historical_dangers", "required"), reasons(req(records__historical_dangers=...)))
        self.assertIn(("section.crest_hight", "unknown_field"), reasons(req(section__crest_hight=1.0)))

    def test_types_enums_ranges(self):
        self.assertIn(("section.crest_elevation_m", "type_number_required"), reasons(req(section__crest_elevation_m="36")))
        self.assertIn(("section.is_lake_levee", "type_boolean_required"), reasons(req(section__is_lake_levee=1)))
        self.assertIn(("records.fill_quality", "not_in_enum"), reasons(req(records__fill_quality="较好")))
        self.assertIn(("section.crest_width_m", "below_minimum"), reasons(req(section__crest_width_m=0)))
        self.assertIn(("section.control_layer.Gs", "above_maximum"), reasons(req(section__control_layer__Gs=4.0)))
        self.assertIn(("computation.foundation_gradient", "type_number_required"),
                      reasons(req(computation__foundation_gradient=float("nan"))))

    def test_cross_field_rules(self):
        r = req(section__control_layer=..., section__soil_layers=...)
        self.assertIn(("section.control_layer", "control_layer_or_soil_layers_required"), reasons(r))
        self.assertIn(("section.foundation_class", "foundation_class_or_qualitative_A7_required"),
                      reasons(req(section__foundation_class=...)))
        self.assertEqual(validate(req(section__foundation_class=..., qualitative__A7="良好")), [])
        self.assertIn(("survey.soft_foundation_settlement_diff_cm", "required_when_settlement_given"),
                      reasons(req(survey__soft_foundation_settlement_cm=8.0)))
        self.assertIn(("qualitative.A3", "unknown_indicator"), reasons(req(qualitative__A3="良好")))
        self.assertIn(("qualitative.E1", "not_in_enum"), reasons(req(qualitative__E1="良好")))
        self.assertIn(("qualitative.E1", "score_out_of_range_0_100"), reasons(req(qualitative__E1=120)))
        self.assertIn(("inspection.confirmed_events", "required_in_events_mode_empty_list_if_none"),
                      reasons(req(inspection__confirmed_events=...)))
        self.assertIn(("inspection.aggregated", "required_in_aggregated_mode"),
                      reasons(req(inspection__mode="aggregated", inspection__confirmed_events=...)))

    def test_evaluate_raises_on_invalid(self):
        with self.assertRaises(RequestInvalid) as cm:
            evaluate(req(survey=...))
        self.assertEqual(cm.exception.details, [{"field": "survey", "reason": "required"}])


class Evidence(unittest.TestCase):
    def test_missing_inspection_is_not_a_full_score(self):
        for r in (req(inspection=...), req(inspection={"coverage": "none"})):
            res = evaluate(r)
            self.assertIsNone(res["result"]["indicator_scores"]["C3"])
            self.assertIn("C3", res["result"]["missing_indicators"])
            self.assertIsNone(res["result"]["observation_gate"]["cap"])
            self.assertIn("inspection_missing", {w["code"] for w in res["warnings"]})

    def test_coverage_none_ignores_supplied_events(self):
        res = evaluate(req(inspection__coverage="none"))
        self.assertIn("inspection_ignored", {w["code"] for w in res["warnings"]})
        self.assertIsNone(res["result"]["indicator_scores"]["C3"])

    def test_events_mode_rules(self):
        clean = evaluate(req(inspection__confirmed_events=[]))["result"]
        self.assertEqual(clean["indicator_scores"]["C3"], 100.0)
        self.assertEqual(clean["inspection_evidence"]["evidence_level"], 0)
        ordinary = evaluate(req(inspection__confirmed_events=[{"position": "普通堤身"}]))["result"]
        self.assertEqual(ordinary["inspection_evidence"]["evidence_level"], 1)
        self.assertIsNone(ordinary["observation_gate"]["cap"])
        self.assertEqual(ordinary["indicator_scores"]["C3"], 80.0)
        two = evaluate(req(inspection__confirmed_events=[{}, {}]))["result"]
        self.assertEqual(two["observation_gate"]["cap"], "B")
        sand = evaluate(req(inspection__confirmed_events=[{"sand": True}]))["result"]
        self.assertEqual(sand["observation_gate"]["cap"], "C")
        self.assertEqual(sand["grade"], "C")
        longer = evaluate(req(inspection__confirmed_events=[{}], inspection__segment_length_m=200))["result"]
        self.assertEqual(longer["inspection_evidence"]["weighted_density_per_100m"], 0.5)

    def test_aggregated_mode(self):
        r = req(inspection={"coverage": "complete", "mode": "aggregated",
                            "aggregated": {"weighted_density_per_100m": 2.5, "evidence_level": 2, "gate_cap": "B"}})
        res = evaluate(r)["result"]
        self.assertEqual(res["indicator_scores"]["C3"], 40.0)
        self.assertEqual(res["observation_gate"]["cap"], "B")
        bad = req(inspection={"coverage": "complete", "mode": "aggregated",
                              "aggregated": {"weighted_density_per_100m": 2.5, "evidence_level": 3}})
        self.assertIn(("inspection.aggregated.gate_cap", "inconsistent_with_evidence_level"), reasons(bad))
        bad["inspection"]["aggregated"].update(weighted_density_per_100m=0, evidence_level=1)
        self.assertIn(("inspection.aggregated.evidence_level", "inconsistent_with_density"), reasons(bad))

    def test_hard_gates(self):
        self.assertEqual(evaluate(req(computation__foundation_gradient=1.0))["result"]["grade"], "C")
        self.assertEqual(evaluate(req(computation__back_slope_fos=1.02))["result"]["grade"], "C")
        crest = evaluate(req(section__crest_elevation_m=34.0))["result"]
        self.assertEqual(crest["grade"], "C")
        self.assertTrue(any(g.startswith("B1") for g in crest["gate_reasons"]))

    def test_non_default_option_warns(self):
        res = evaluate(req(options={"alpha": 0.3}))
        self.assertIn("non_default_option", {w["code"] for w in res["warnings"]})

    def test_batch_isolates_bad_items(self):
        out = evaluate_batch([EXAMPLE_REQUEST, req(survey=...), "not an object"])
        self.assertEqual((out["count"], out["succeeded"], out["failed"]), (3, 1, 2))
        self.assertEqual(out["results"][1]["error"]["code"], "validation_failed")
        with self.assertRaises(RequestInvalid):
            evaluate_batch([])


class MissingInputs(unittest.TestCase):
    """v1.1: inputs without data stay missing and skip their gate instead of being required or scored 100."""

    def test_no_stability_scour_settlement_inspection(self):
        r = req(computation__back_slope_fos=..., computation__front_slope_fos=..., survey__scour_depth_m=...,
                survey__soft_foundation_status="unknown", inspection=...)
        res = evaluate(r)
        x = res["result"]
        for code in ("D1", "D2", "D3", "A5", "C3"):
            self.assertIsNone(x["indicator_scores"][code], code)
            self.assertIn(code, x["missing_indicators"])
            self.assertEqual(x["indicator_sources"][code], "missing")
        self.assertEqual({g["indicator"] for g in x["gates_not_checked"]}, {"D1", "D2", "D3", "A5", "C3"})
        self.assertFalse([g for g in x["gate_reasons"] if g[:2] in ("D1", "D2", "D3", "A5")])
        self.assertIn("input_missing_no_gate", {w["code"] for w in res["warnings"]})
        self.assertIsNotNone(x["mode_responses"]["slope_instability"]["adjusted"])
        self.assertEqual((x["indicator_sources"]["C1"], x["indicator_sources"]["A1"]), ("computed", "design_survey"))
        self.assertEqual(x["mode_responses"]["slope_instability"]["basis"]["direct_missing"], ["D1", "D2"])
        self.assertEqual(x["mode_responses"]["seepage"]["basis"]["direct_missing"], [])

    def test_one_sided_stability(self):
        x = evaluate(req(computation__front_slope_fos=..., computation__back_slope_fos=1.2))["result"]
        self.assertIsNone(x["indicator_scores"]["D2"])
        self.assertIn("D1背水坡FoS=1.20<允许值1.35", x["gate_reasons"])
        self.assertEqual([g["indicator"] for g in x["gates_not_checked"]], ["D2"])
        failed = evaluate(req(computation__front_slope_fos=..., computation__back_slope_fos=0.95))["result"]
        self.assertEqual(failed["mode_responses"]["slope_instability"]["raw"], 1.0)
        self.assertEqual(failed["grade"], "C")

    def test_scour_missing_with_unrepaired_major_danger(self):
        x = evaluate(req(survey__scour_depth_m=...,
                         records__historical_dangers=[{"type": "管涌", "reinforced": False}]))["result"]
        self.assertEqual(x["indicator_scores"]["D3"], 0)
        self.assertEqual(x["grade"], "C")
        self.assertIn("D3堤岸冲刷稳定性: 有未加固的重大险情记录（管涌），按严重冲刷计0分", x["gate_reasons"])
        self.assertNotIn("D3", {g["indicator"] for g in x["gates_not_checked"]})

    def test_d3_reason_names_the_danger_record(self):
        x = evaluate(req(records__historical_dangers=[{"type": "管涌", "reinforced": True}]))["result"]
        self.assertEqual(x["indicator_scores"]["D3"], 70)
        self.assertIn("D3堤岸冲刷稳定性: 冲刷深度0.20m未达0.5m，因有已加固的重大险情记录（管涌）计70分，存在冲刷风险",
                      x["gate_reasons"])

    def test_settlement_status_rules(self):
        self.assertIn(("survey.soft_foundation_status", "not_allowed_when_settlement_given"),
                      reasons(req(survey__soft_foundation_settlement_cm=8.0, survey__soft_foundation_settlement_diff_cm=2.0,
                                  survey__soft_foundation_status="unknown")))
        self.assertEqual(evaluate(req(survey__soft_foundation_status="non_soft"))["result"]["indicator_scores"]["A5"], 100)


def call(method, path, body=None, headers=None, raw=None):
    path, _, query = path.partition("?")
    env = {"REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": query}
    data = raw if raw is not None else (b"" if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8"))
    env["wsgi.input"] = io.BytesIO(data)
    env["CONTENT_LENGTH"] = str(len(data))
    env["CONTENT_TYPE"] = "application/json"
    for k, v in (headers or {}).items():
        if k == "Content-Type":
            env["CONTENT_TYPE"] = v
        else:
            env["HTTP_" + k.upper().replace("-", "_")] = v
    setup_testing_defaults(env)
    seen = {}

    def start_response(status, hdrs):
        seen["status"], seen["headers"] = int(status.split()[0]), dict(hdrs)

    payload = b"".join(application(env, start_response))
    return seen["status"], (json.loads(payload) if payload else None), seen["headers"]


class Http(unittest.TestCase):
    def test_endpoints(self):
        self.assertEqual(call("GET", "/api/v1/health")[1]["status"], "ok")
        meta = call("GET", "/api/v1/meta")[1]
        self.assertEqual(len(meta["indicators"]), 29)
        self.assertEqual(call("GET", "/api/v1/openapi.json")[1], json.loads(json.dumps(build_openapi())))
        status, body, headers = call("POST", "/api/v1/evaluate", EXAMPLE_REQUEST, {"X-Request-ID": "abc"})
        self.assertEqual(status, 200)
        self.assertEqual(body["request_id"], "demo-0001")
        self.assertEqual(headers["X-Request-ID"], "abc")
        status, body, _ = call("POST", "/api/v1/evaluate/batch", {"items": [EXAMPLE_REQUEST] * 3})
        self.assertEqual((status, body["succeeded"]), (200, 3))
        full = call("POST", "/api/v1/evaluate", EXAMPLE_REQUEST)[1]["result"]
        summary = call("POST", "/api/v1/evaluate?detail=summary", EXAMPLE_REQUEST)[1]["result"]
        self.assertEqual({k: v for k, v in full.items() if k != "contributions_by_mode"}, summary)
        batch = call("POST", "/api/v1/evaluate/batch?detail=summary", {"items": [EXAMPLE_REQUEST]})[1]
        self.assertNotIn("contributions_by_mode", batch["results"][0]["response"]["result"])

    def test_error_statuses(self):
        self.assertEqual(call("GET", "/api/v1/nothing")[0], 404)
        self.assertEqual(call("POST", "/api/v1/evaluate?detail=brief", EXAMPLE_REQUEST)[0], 400)
        self.assertEqual(call("GET", "/api/v1/evaluate")[0], 405)
        self.assertEqual(call("POST", "/api/v1/evaluate", raw=b"{bad")[0], 400)
        self.assertEqual(call("POST", "/api/v1/evaluate", EXAMPLE_REQUEST, {"Content-Type": "text/plain"})[0], 415)
        status, body, _ = call("POST", "/api/v1/evaluate", req(survey=...))
        self.assertEqual(status, 422)
        self.assertEqual(body["error"]["details"], [{"field": "survey", "reason": "required"}])
        self.assertEqual(call("POST", "/api/v1/evaluate/batch", {"item": []})[0], 422)
        with mock.patch.dict(os.environ, {"LEVEE_EVAL_MAX_BODY_MB": "0.001"}):
            self.assertEqual(call("POST", "/api/v1/evaluate", EXAMPLE_REQUEST)[0], 413)

    def test_api_key_and_cors(self):
        with mock.patch.dict(os.environ, {"LEVEE_EVAL_API_KEY": "s3cret", "LEVEE_EVAL_CORS_ORIGINS": "https://a.example"}):
            self.assertEqual(call("GET", "/api/v1/health")[0], 200)
            self.assertEqual(call("GET", "/api/v1/meta")[0], 401)
            self.assertEqual(call("GET", "/api/v1/meta", headers={"X-API-Key": "wrong"})[0], 401)
            status, _, headers = call("GET", "/api/v1/meta", headers={"X-API-Key": "s3cret", "Origin": "https://a.example"})
            self.assertEqual(status, 200)
            self.assertEqual(headers["Access-Control-Allow-Origin"], "https://a.example")
            self.assertNotIn("Access-Control-Allow-Origin",
                             call("GET", "/api/v1/health", headers={"Origin": "https://b.example"})[2])
            self.assertEqual(call("OPTIONS", "/api/v1/evaluate", headers={"Origin": "https://a.example"})[0], 204)

    def test_real_socket_server(self):
        from socketserver import ThreadingMixIn
        from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

        class Srv(ThreadingMixIn, WSGIServer):
            daemon_threads = True

        class Quiet(WSGIRequestHandler):
            def log_message(self, *a):
                pass

        httpd = make_server("127.0.0.1", 0, application, Srv, Quiet)
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        try:
            url = f"http://127.0.0.1:{httpd.server_port}/api/v1/evaluate"
            data = json.dumps(EXAMPLE_REQUEST, ensure_ascii=False).encode("utf-8")
            r = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json; charset=utf-8"})
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(r, timeout=10) as resp:
                self.assertEqual(json.loads(resp.read())["result"]["grade"], "B")
            with self.assertRaises(urllib.error.HTTPError) as cm:
                opener.open(urllib.request.Request(url, data=b"{}", headers={"Content-Type": "application/json"}), timeout=10)
            self.assertEqual(cm.exception.code, 422)
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
