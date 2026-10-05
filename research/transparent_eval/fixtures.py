"""Explicitly synthetic fixtures for software/logic checks only."""
from copy import deepcopy
import json
from pathlib import Path


def rules():
    return json.loads((Path(__file__).resolve().parents[1]/"configs"/"illustrative_rules.json").read_text(encoding="utf-8"))


def case():
    common = {"unit_id": "SYNTHETIC-U01", "case_id": "SYNTHETIC-STEADY-01",
              "observed_at": "2026-09-20T10:00:00+08:00", "received_at": "2026-09-20T10:01:00+08:00",
              "valid_until": "2026-09-20T12:00:00+08:00", "quality": "usable"}
    measurements = []
    for name, value in [("exit_gradient_ratio", .2), ("uplift_demand_ratio", .2), ("filter_deficiency", .1)]:
        measurements.append({**common, "indicator_id": name, "value": [value,value],
                             "unit": "1", "source_ref": f"synthetic://{name}", "evidence_ids": [f"SIM-{name}"]})
    return {"schema_version": "0.1", "unit_id": common["unit_id"], "case_id": common["case_id"],
            "as_of": "2026-09-20T11:00:00+08:00", "model_version": "synthetic-fixture-v1",
            "measurements": measurements, "events": [],
            "inspection": {k:v for k,v in {**common, "source_ref": "synthetic://inspection", "coverage": "complete"}.items() if k!="case_id"}}


def event(kind="confirmed", event_id="EVENT-1"):
    result = {"event_id": event_id, "evidence_id": "SYNTHETIC-PHOTO-1", "unit_id": "SYNTHETIC-U01",
              "kind": kind, "observed_at": "2026-09-20T10:15:00+08:00",
              "received_at": "2026-09-20T10:16:00+08:00", "mode_ids": ["exit_instability"],
              "source_ref": "synthetic://observation"}
    if kind in ("confirmed", "resolved"):
        result["review_ref"] = "synthetic://independent-review"
    return result


def scenarios():
    out = []
    def add(name, c):
        out.append((name, deepcopy(c)))
    c=case();add("S01_complete_low_response",c)
    c=case();c["measurements"][0]["value"]=[1.01,1.01];add("S02_physical_limit_crossed",c)
    c=case();c["measurements"][0]["value"]=[.9,1.1];add("S03_physical_limit_uncertain",c)
    c=case();c["measurements"]=c["measurements"][1:];add("S04_missing_critical_input",c)
    c=case();c["measurements"][0]["quality"]="unusable";add("S05_unusable_input",c)
    c=case();c["events"]=[event("suspected")];add("S06_suspected_observation",c)
    c=case();c["events"]=[event()];add("S07_confirmed_observation",c)
    c=case();c["events"]=[event(),event()];add("S08_duplicate_frame",c)
    c=case();c["events"]=[event(),event(event_id="EVENT-2")];add("S09_repeated_confirmation",c)
    c=case();c["events"]=[event()];c["as_of"]="2026-09-25T11:00:00+08:00";add("S10_old_unresolved_confirmation",c)
    c=case();c["events"]=[event()];r=event("resolved","RESOLVE-1");r.update({"observed_at":"2026-09-20T10:30:00+08:00","received_at":"2026-09-20T10:31:00+08:00","resolves_event_id":"EVENT-1"});c["events"].append(r);add("S11_reviewed_resolution",c)
    c=case();e=event();e["received_at"]="2026-09-20T11:30:00+08:00";c["events"]=[e];add("S12_late_arriving_record",c)
    c=case();c["inspection"]["coverage"]="partial";add("S13_incomplete_inspection",c)
    c=case();c["measurements"][2]["value"]=[0,1];add("S14_uncertain_noncritical_input",c)
    c=case();c["measurements"][0]["value"]=[1.8,1.8];c["events"]=[event("suspected")];add("S15_physical_concern_pending_review",c)
    c=case();c["events"]=[event()];c["measurements"]=[];add("S16_confirmed_with_missing_model",c)
    return out
