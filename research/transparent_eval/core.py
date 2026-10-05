"""Interval-valued, traceable evaluation with persistent observation evidence.

No failure probability, real-time seepage solver or trained detector is implied.
Each evaluation is a historical snapshot using both acquisition and receipt time.
"""
from __future__ import annotations

from bisect import bisect_right
from datetime import datetime
from math import isclose, isfinite


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not isfinite(value):
        raise ValueError(f"{name}: finite number required")
    return float(value)


def timestamp(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("timestamps must include a timezone")
    return dt


def require_text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name}: nonempty text required")


def interval(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("value must be a two-endpoint interval")
    lo, hi = (number(x, "interval endpoint") for x in value)
    if lo > hi:
        raise ValueError("interval endpoints are reversed")
    return lo, hi


def normalize(raw, knots):
    """Monotone piecewise linear map; clamp outside explicitly supplied anchors."""
    def point(x):
        if x <= knots[0][0]:
            return knots[0][1]
        for (x0, y0), (x1, y1) in zip(knots, knots[1:]):
            if x <= x1:
                return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
        return knots[-1][1]
    endpoints = [point(x) for x in raw]
    return min(endpoints), max(endpoints)


def validate_rules(rules):
    if rules["schema_version"] != "0.1":
        raise ValueError("unsupported schema_version")
    require_text(rules["rule_id"], "rule_id")
    require_text(rules["basis_ref"], "basis_ref")
    if not isinstance(rules["illustrative_only"], bool):
        raise ValueError("illustrative_only must be boolean")
    cuts = rules["grade_cuts"]
    if len(cuts) != 3 or any(not 0 < number(x, "grade cut") < 1 for x in cuts):
        raise ValueError("three grade cuts within (0,1) required")
    if any(a >= b for a, b in zip(cuts, cuts[1:])):
        raise ValueError("grade cuts must increase")
    if not 0 <= number(rules["alpha"], "alpha") <= 1:
        raise ValueError("alpha outside [0,1]")
    modes, indicators = rules["modes"], rules["indicators"]
    if not modes or not indicators:
        raise ValueError("modes and indicators cannot be empty")
    used = set()
    for name, spec in indicators.items():
        require_text(spec["basis_ref"], f"{name}.basis_ref")
        require_text(spec["unit"], f"{name}.unit")
        require_text(spec["dependence_group"], f"{name}.dependence_group")
        if not isinstance(spec["critical"], bool):
            raise ValueError("critical must be boolean")
        knots = spec["knots"]
        if len(knots) < 2:
            raise ValueError("at least two normalization anchors required")
        for x, y in knots:
            number(x, "anchor x")
            if not 0 <= number(y, "anchor response") <= 1:
                raise ValueError("anchor response outside [0,1]")
        if any(a[0] >= b[0] for a, b in zip(knots, knots[1:])):
            raise ValueError("raw anchors must strictly increase")
        dy = [b[1] - a[1] for a, b in zip(knots, knots[1:])]
        if not (all(x >= 0 for x in dy) or all(x <= 0 for x in dy)):
            raise ValueError("normalization must be monotone")
        if "constraint" in spec:
            gate = spec["constraint"]
            if gate["operator"] not in ("ge", "le"):
                raise ValueError("constraint operator must be ge or le")
            number(gate["threshold"], "constraint threshold")
            if type(gate["grade_floor"]) is not int or gate["grade_floor"] not in (1, 2, 3):
                raise ValueError("invalid constraint grade floor")
            require_text(gate["basis_ref"], "constraint basis")
    for name, mode in modes.items():
        weights = mode["weights"]
        if not weights or any(k not in indicators for k in weights):
            raise ValueError(f"{name}: unknown or absent indicators")
        if any(number(w, "indicator weight") <= 0 for w in weights.values()):
            raise ValueError("active indicator weights must be positive")
        if not isclose(sum(weights.values()), 1.0, abs_tol=1e-10):
            raise ValueError("within-mode weights must sum to one")
        groups = [indicators[k]["dependence_group"] for k in weights]
        if len(groups) != len(set(groups)):
            raise ValueError("same dependence group counted twice within additive mode")
        used.update(weights)
        if number(mode["weight"], "mode weight") <= 0:
            raise ValueError("mode weights must be positive")
    if used != set(indicators):
        raise ValueError("unused indicator in rules")
    if not isclose(sum(m["weight"] for m in modes.values()), 1, abs_tol=1e-10):
        raise ValueError("mode weights must sum to one")
    floor = rules["confirmed_observation_grade_floor"]
    if type(floor) is not int or floor not in (1, 2, 3):
        raise ValueError("invalid confirmed observation grade floor")


def _usable(record, as_of):
    observed, received = timestamp(record["observed_at"]), timestamp(record["received_at"])
    if received < observed:
        raise ValueError("receipt precedes acquisition")
    if observed > as_of or received > as_of:
        return False, "not_available_at_snapshot"
    until = timestamp(record["valid_until"])
    if until < observed:
        raise ValueError("validity ends before acquisition")
    if until < as_of:
        return False, "expired"
    if record["quality"] not in ("usable", "unusable"):
        raise ValueError("unknown quality status")
    if record["quality"] != "usable":
        return False, "unusable"
    return True, "usable"


def evaluate(case, rules):
    """Evaluate one unit and hydraulic case; never silently renormalize missing data."""
    validate_rules(rules)
    if case["schema_version"] != "0.1":
        raise ValueError("unsupported case schema_version")
    for field in ("unit_id", "case_id", "model_version"):
        require_text(case[field], field)
    as_of = timestamp(case["as_of"])
    specs, modes = rules["indicators"], rules["modes"]
    rows, evidence, issues = {}, {}, []
    for row in case["measurements"]:
        key = row["indicator_id"]
        if key not in specs or key in rows:
            raise ValueError("unknown or duplicate measurement; resolve versions upstream")
        if row["unit_id"] != case["unit_id"] or row["case_id"] != case["case_id"]:
            raise ValueError("measurement unit/case mismatch")
        if row["unit"] != specs[key]["unit"]:
            raise ValueError("measurement unit mismatch")
        require_text(row["source_ref"], "measurement source_ref")
        if not row["evidence_ids"]:
            raise ValueError("measurement provenance required")
        for eid in row["evidence_ids"]:
            require_text(eid, "evidence_id")
        if row["value"] is not None:
            interval(row["value"])
        rows[key] = row
    critical_missing = []
    for key, spec in specs.items():
        row = rows.get(key)
        ok, reason = _usable(row, as_of) if row else (False, "missing")
        if ok and row["value"] is None:
            ok, reason = False, "missing_value"
        raw = interval(row["value"]) if ok else None
        normalized = normalize(raw, spec["knots"]) if ok else (0.0, 1.0)
        if not ok:
            issues.append(f"{key}:{reason}")
            if spec["critical"]:
                critical_missing.append(key)
        evidence[key] = {"raw_interval": raw, "response_interval": normalized,
                         "status": reason, "evidence_ids": row["evidence_ids"] if row else [],
                         "source_ref": row["source_ref"] if row else None}

    # Events are persistent assertions; resolution is an explicit, reviewed event.
    unique = {}
    for event in case["events"]:
        eid = event["event_id"]
        require_text(eid, "event_id")
        if eid in unique and unique[eid] != event:
            raise ValueError("conflicting duplicate event_id")
        if event["unit_id"] != case["unit_id"]:
            raise ValueError("event unit mismatch")
        spatial = event.get("spatial_certainty", "definite")
        if spatial not in ("definite", "possible"):
            raise ValueError("unknown spatial certainty")
        if spatial == "possible":
            require_text(event.get("association_ref"), "candidate association reference")
            if event["kind"] == "resolved":
                raise ValueError("uncertain local resolution cannot clear an event")
        if event["kind"] not in ("suspected", "confirmed", "resolved"):
            raise ValueError("unknown event kind")
        if not event["mode_ids"] or not set(event["mode_ids"]) <= set(modes):
            raise ValueError("unknown or empty event mode assignment")
        require_text(event["source_ref"], "event source_ref")
        require_text(event["evidence_id"], "event evidence_id")
        if event["kind"] in ("confirmed", "resolved"):
            require_text(event.get("review_ref"), "review_ref")
        obs, rec = timestamp(event["observed_at"]), timestamp(event["received_at"])
        if rec < obs:
            raise ValueError("event receipt precedes acquisition")
        unique[eid] = event
    active, ignored = {}, []
    ordered = sorted(unique.values(), key=lambda e: (timestamp(e["observed_at"]), e["event_id"]))
    for event in ordered:
        eid = event["event_id"]
        if timestamp(event["observed_at"]) > as_of or timestamp(event["received_at"]) > as_of:
            ignored.append(eid)
            continue
        if event["kind"] == "resolved":
            target = event["resolves_event_id"]
            if target not in active:
                raise ValueError("resolution must reference an active earlier event")
            if timestamp(event["observed_at"]) <= timestamp(active[target]["observed_at"]):
                raise ValueError("resolution must follow target acquisition")
            if set(event["mode_ids"]) != set(active[target]["mode_ids"]):
                raise ValueError("partial resolution must be represented upstream")
            del active[target]
        else:
            active[eid] = event

    inspection = case.get("inspection")
    coverage_ok = False
    if inspection:
        if inspection["unit_id"] != case["unit_id"]:
            raise ValueError("inspection unit mismatch")
        require_text(inspection["source_ref"], "inspection source_ref")
        if inspection["coverage"] not in ("complete", "partial", "none"):
            raise ValueError("unknown inspection coverage")
        coverage_ok = _usable(inspection, as_of)[0] and inspection["coverage"] == "complete"
    if not coverage_ok:
        issues.append("inspection:incomplete_or_unavailable")
    if any(e["kind"] == "suspected" for e in active.values()):
        issues.append("inspection:unresolved_suspicion")
    spatial_uncertainty = any(e.get("spatial_certainty", "definite") == "possible"
                              for e in active.values())
    if spatial_uncertainty:
        issues.append("inspection:uncertain_spatial_assignment")

    cuts = rules["grade_cuts"]
    grade = lambda x: bisect_right(cuts, x)
    floor_value = lambda g: 0.0 if g == 0 else cuts[g - 1]
    results = {}
    for name, mode in modes.items():
        base = [sum(w * evidence[key]["response_interval"][j]
                    for key, w in mode["weights"].items()) for j in (0, 1)]
        definite, possible, triggers = 0, 0, []
        for key in mode["weights"]:
            gate = specs[key].get("constraint")
            if gate is None:
                continue
            raw = evidence[key]["raw_interval"]
            if raw is None:
                certain, maybe = False, True
            elif gate["operator"] == "ge":
                certain, maybe = raw[0] >= gate["threshold"], raw[1] >= gate["threshold"]
            else:
                certain, maybe = raw[1] <= gate["threshold"], raw[0] <= gate["threshold"]
            if certain:
                definite = max(definite, gate["grade_floor"])
            if maybe:
                possible = max(possible, gate["grade_floor"])
                triggers.append({"type": "physical", "indicator_id": key,
                                 "certainty": "definite" if certain else "possible",
                                 "grade_floor": gate["grade_floor"], "basis_ref": gate["basis_ref"]})
        # Unobserved regions or unresolved suspicion may conceal an adverse event.
        # This expands a possibility envelope, not a probability or definite alarm.
        if not coverage_ok:
            possible = max(possible, rules["confirmed_observation_grade_floor"])
            triggers.append({"type": "observation_coverage", "certainty": "possible",
                             "grade_floor": rules["confirmed_observation_grade_floor"],
                             "basis_ref": "unobserved_state_not_excluded"})
        # Multiple frames / repeat assertions never add to the grade constraint.
        for eid, event in active.items():
            if name in event["mode_ids"]:
                g = rules["confirmed_observation_grade_floor"]
                possible = max(possible, g)
                local_confirmation = (event["kind"] == "confirmed" and
                                      event.get("spatial_certainty", "definite") == "definite")
                if local_confirmation:
                    definite = max(definite, g)
                triggers.append({"type": "observation", "event_id": eid,
                                 "certainty": "definite" if local_confirmation else "possible",
                                 "observation_kind": event["kind"],
                                 "spatial_certainty": event.get("spatial_certainty", "definite"),
                                 "association_ref": event.get("association_ref"),
                                 "grade_floor": g, "review_ref": event.get("review_ref")})
        response = [max(base[0], floor_value(definite)), max(base[1], floor_value(possible))]
        results[name] = {"base_interval": base, "response_interval": response,
                         "grade_range": [max(grade(response[0]), definite),
                                         max(grade(response[1]), possible)],
                         "definite_grade_floor": definite, "possible_grade_floor": possible,
                         "linear_contributions": {key: [w * v for v in evidence[key]["response_interval"]]
                                                  for key, w in mode["weights"].items()},
                         "triggers": triggers}
    alpha = rules["alpha"]
    score = [alpha * max(r["response_interval"][j] for r in results.values()) +
             (1 - alpha) * sum(modes[m]["weight"] * r["response_interval"][j]
                               for m, r in results.items()) for j in (0, 1)]
    # Numeric display index must not dilute a categorical physical/observed floor.
    definite = max(r["definite_grade_floor"] for r in results.values())
    possible = max(r["possible_grade_floor"] for r in results.values())
    grade_range = [max(grade(score[0]), definite), max(grade(score[1]), possible)]
    sufficient = not critical_missing and coverage_ok and not spatial_uncertainty and not any(
        e["kind"] == "suspected" for e in active.values())
    determined = grade_range[0] == grade_range[1] and (sufficient or definite == 3)
    effective_weights = {key: sum(mode["weight"] * mode["weights"].get(key, 0)
                                  for mode in modes.values()) for key in specs}
    return {"schema_version": "0.1", "unit_id": case["unit_id"], "case_id": case["case_id"],
            "as_of": case["as_of"], "model_version": case["model_version"],
            "rule_id": rules["rule_id"], "illustrative_only": rules["illustrative_only"],
            "score_interval": score, "grade_range": grade_range,
            "determined_grade": grade_range[0] if determined else None,
            "evidence_sufficient": sufficient, "critical_missing": critical_missing,
            "issues": issues, "modes": results, "indicator_evidence": evidence,
            "active_events": list(active.values()), "ignored_future_events": ignored,
            "effective_linear_weights": effective_weights,
            "interpretation": "response index and possibility interval; not failure probability"}
