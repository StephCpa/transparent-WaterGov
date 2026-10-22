"""Service output must equal the delivered model output on the 875 synthetic samples.

Fixtures come from tools/build_fixtures.py: requests in API form, expected values from the
delivered evaluate_section() (cross-checked against the delivered results file).
"""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from levee_eval import evaluate  # noqa: E402

FIX = ROOT / "tests" / "fixtures"


def _project(r):
    return {"score": r["score"], "grade": r["grade"], "model_grade": r["model_grade"],
            "grade_after_observation_gate": r["grade_after_observation_gate"], "rho": r["rho"],
            "dominant_mode": r["dominant_mode"]["name"], "gate_reasons": r["gate_reasons"],
            "barrier_ability": r["barrier"]["ability"], "barrier_coverage": r["barrier"]["coverage"],
            "mode_responses_raw": {v["name"]: v["raw"] for v in r["mode_responses"].values()},
            "mode_responses_adjusted": {v["name"]: v["adjusted"] for v in r["mode_responses"].values()},
            "indicator_scores": r["indicator_scores"], "missing_indicators": r["missing_indicators"]}


class Regression875(unittest.TestCase):
    def test_identical_to_delivered_model(self):
        requests = json.loads((FIX / "synthetic_875_requests.json").read_text(encoding="utf-8"))
        expected = json.loads((FIX / "synthetic_875_expected.json").read_text(encoding="utf-8"))
        self.assertEqual(len(requests), 875)
        for req, exp in zip(requests, expected):
            with self.subTest(req["request_id"]):
                resp = evaluate(req)
                self.assertEqual(resp["request_id"], exp["request_id"])
                self.assertEqual(_project(resp["result"]), {k: v for k, v in exp.items() if k != "request_id"})


if __name__ == "__main__":
    unittest.main()
