import unittest
from copy import deepcopy
import random

from transparent_eval.core import evaluate, normalize, validate_rules
from transparent_eval.fixtures import case, event, rules, scenarios
from transparent_eval.metrics import ordinal_metrics, validate_split
from transparent_eval.weighting import ahp, critic, combine


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.c, self.r = case(), rules()

    def test_hand_calculated_baseline(self):
        out=evaluate(self.c,self.r)
        self.assertAlmostEqual(out["score_interval"][0],.1)
        self.assertEqual(out["grade_range"],[0,0])
        self.assertTrue(out["evidence_sufficient"])

    def test_physical_floor_survives_aggregation(self):
        self.c["measurements"][0]["value"]=[1,1]
        self.r["alpha"]=0
        out=evaluate(self.c,self.r)
        self.assertAlmostEqual(out["score_interval"][0],.34)
        self.assertEqual(out["determined_grade"],2)
        self.assertLess(out["score_interval"][0],self.r["grade_cuts"][1])

    def test_uncertain_limit_does_not_become_definite(self):
        self.c["measurements"][0]["value"]=[.9,1.1]
        out=evaluate(self.c,self.r)
        self.assertEqual(out["grade_range"],[1,2])
        self.assertIsNone(out["determined_grade"])

    def test_missing_is_interval_not_zero_or_renormalized(self):
        self.c["measurements"]=self.c["measurements"][1:]
        out=evaluate(self.c,self.r)
        for actual, expected in zip(out["modes"]["exit_instability"]["base_interval"],[.02,.82]):
            self.assertAlmostEqual(actual,expected)
        self.assertIsNone(out["determined_grade"])
        self.assertIn("exit_gradient_ratio",out["critical_missing"])

    def test_repeat_observation_does_not_inflate(self):
        self.c["events"]=[event()]
        a=evaluate(self.c,self.r)
        self.c["events"]=[event(),event(),event(event_id="EVENT-2")]
        b=evaluate(self.c,self.r)
        self.assertEqual(a["score_interval"],b["score_interval"])
        self.assertEqual(b["determined_grade"],3)

    def test_confirmation_does_not_age_into_safe(self):
        self.c["events"]=[event()]
        self.c["as_of"]="2026-10-20T11:00:00+08:00"
        out=evaluate(self.c,self.r)
        self.assertEqual(out["determined_grade"],3)
        self.assertFalse(out["evidence_sufficient"])

    def test_resolution_is_explicit(self):
        c=dict(scenarios())["S11_reviewed_resolution"]
        self.assertEqual(evaluate(c,self.r)["determined_grade"],0)
        del c["events"][1]["review_ref"]
        with self.assertRaises(ValueError):evaluate(c,self.r)

    def test_suspicion_is_not_confirmed_failure(self):
        self.c["events"]=[event("suspected")]
        out=evaluate(self.c,self.r)
        self.assertEqual(out["grade_range"],[0,3])
        self.assertIsNone(out["determined_grade"])

    def test_confirmed_but_spatially_uncertain_is_only_possible_locally(self):
        self.c['events'] = [dict(event(), spatial_certainty='possible',
                                 association_ref='candidate-list-v1')]
        out = evaluate(self.c, self.r)
        self.assertEqual(out['grade_range'], [0, 3])
        self.assertIsNone(out['determined_grade'])
        self.assertFalse(out['evidence_sufficient'])
        trigger = out['modes']['exit_instability']['triggers'][0]
        self.assertEqual(trigger['observation_kind'], 'confirmed')
        self.assertEqual(trigger['spatial_certainty'], 'possible')
        self.assertEqual(trigger['certainty'], 'possible')

    def test_spatial_uncertainty_does_not_remove_other_definite_evidence(self):
        self.c['events'] = [event(), dict(event(event_id='E2'),
                              spatial_certainty='possible', association_ref='mapping-v1')]
        out = evaluate(self.c, self.r)
        self.assertEqual(out['determined_grade'], 3)
        self.assertFalse(out['evidence_sufficient'])

    def test_possible_location_requires_basis_and_persists(self):
        e = dict(event(), spatial_certainty='possible')
        self.c['events'] = [e]
        with self.assertRaises(ValueError):
            evaluate(self.c, self.r)
        e['association_ref'] = 'mapping-v1'
        self.c['as_of'] = '2026-10-20T11:00:00+08:00'
        out = evaluate(self.c, self.r)
        self.assertIsNone(out['determined_grade'])
        self.assertEqual(out['active_events'][0]['spatial_certainty'], 'possible')

    def test_uncertain_resolution_cannot_clear_local_event(self):
        c = dict(scenarios())['S11_reviewed_resolution']
        c['events'][1].update(spatial_certainty='possible', association_ref='mapping-v1')
        with self.assertRaises(ValueError):
            evaluate(c, self.r)

    def test_bitemporal_replay_excludes_late_arrival(self):
        self.c["events"]=[event()]
        self.c["events"][0]["received_at"]="2026-09-20T11:30:00+08:00"
        a=evaluate(self.c,self.r)
        self.assertEqual(a["determined_grade"],0)
        self.assertEqual(a["ignored_future_events"],["EVENT-1"])
        self.c["as_of"]="2026-09-20T11:45:00+08:00"
        self.assertEqual(evaluate(self.c,self.r)["determined_grade"],3)

    def test_incomplete_coverage_cannot_certify_low_grade(self):
        self.c["inspection"]["coverage"]="partial"
        out=evaluate(self.c,self.r)
        self.assertIsNone(out["determined_grade"])
        self.assertEqual(out["grade_range"],[0,3])

    def test_future_resolution_cannot_remove_current_confirmation(self):
        c=dict(scenarios())["S11_reviewed_resolution"]
        c["events"][1]["received_at"]="2026-09-21T10:31:00+08:00"
        self.assertEqual(evaluate(c,self.r)["determined_grade"],3)

    def test_resolution_cannot_clear_wrong_event(self):
        c=dict(scenarios())["S11_reviewed_resolution"]
        c["events"][1]["resolves_event_id"]="UNKNOWN"
        with self.assertRaises(ValueError):evaluate(c,self.r)

    def test_quality_degradation_cannot_narrow_envelope(self):
        self.c["measurements"][0]["value"]=[1.2,1.2]
        a=evaluate(self.c,self.r)
        self.c["measurements"][0]["quality"]="unusable"
        b=evaluate(self.c,self.r)
        self.assertLessEqual(b["grade_range"][0],a["grade_range"][0])
        self.assertGreaterEqual(b["grade_range"][1],a["grade_range"][1])
        self.assertIsNone(b["determined_grade"])

    def test_wrong_case_and_units_rejected(self):
        for key,value in [("case_id","WRONG"),("unit","m")]:
            c=deepcopy(self.c);c["measurements"][0][key]=value
            with self.assertRaises(ValueError):evaluate(c,self.r)

    def test_conflicting_event_id_rejected(self):
        self.c["events"]=[event(),event("suspected")]
        with self.assertRaises(ValueError):evaluate(self.c,self.r)

    def test_duplicate_dependence_group_rejected(self):
        self.r["indicators"]["filter_deficiency"]["dependence_group"]="exit_gradient"
        with self.assertRaises(ValueError):validate_rules(self.r)

    def test_unknown_measurement_and_duplicates_rejected(self):
        c=deepcopy(self.c);c["measurements"].append(deepcopy(c["measurements"][0]))
        with self.assertRaises(ValueError):evaluate(c,self.r)
        c=deepcopy(self.c);c["measurements"][0]["indicator_id"]="typo"
        with self.assertRaises(ValueError):evaluate(c,self.r)

    def test_nan_reversed_interval_and_naive_time_rejected(self):
        for value in ([float("nan"),1],[2,1]):
            c=deepcopy(self.c);c["measurements"][0]["value"]=value
            with self.assertRaises(ValueError):evaluate(c,self.r)
        self.c["as_of"]="2026-09-20T11:00:00"
        with self.assertRaises(ValueError):evaluate(self.c,self.r)

    def test_decreasing_normalization(self):
        self.assertEqual(normalize((.5,1.5),[(0,1),(2,0)]),(.25,.75))

    def test_random_monotonicity_and_interval_enclosure(self):
        rng=random.Random(20260921)
        for _ in range(200):
            c=deepcopy(self.c)
            lows=[];highs=[]
            for row in c["measurements"]:
                a,b=sorted([rng.uniform(0,2),rng.uniform(0,2)])
                row["value"]=[a,b];lows.append(a);highs.append(b)
            outer=evaluate(c,self.r)
            for _ in range(3):
                point=deepcopy(c)
                for row,a,b in zip(point["measurements"],lows,highs):
                    x=rng.uniform(a,b);row["value"]=[x,x]
                inner=evaluate(point,self.r)
                self.assertLessEqual(outer["score_interval"][0]-1e-12,inner["score_interval"][0])
                self.assertGreaterEqual(outer["score_interval"][1]+1e-12,inner["score_interval"][1])
                self.assertLessEqual(outer["grade_range"][0],inner["grade_range"][0])
                self.assertGreaterEqual(outer["grade_range"][1],inner["grade_range"][1])
            a,b=deepcopy(c),deepcopy(c)
            for row,lo in zip(a["measurements"],lows):row["value"]=[lo,lo]
            for row,hi in zip(b["measurements"],highs):row["value"]=[hi,hi]
            self.assertLessEqual(evaluate(a,self.r)["score_interval"][0],evaluate(b,self.r)["score_interval"][0])


class AnalysisTests(unittest.TestCase):
    def test_metrics_count_abstention(self):
        out=ordinal_metrics([3,3,0,0],[None,2,3,0])
        self.assertEqual(out["coverage"],.75)
        self.assertEqual(out["high_grade_underestimation_rate"],.5)
        self.assertEqual(out["high_grade_abstention_rate"],.5)
        self.assertEqual(out["false_alarm_rate"],.5)
        self.assertEqual(out["accuracy_all_cases"],.25)

    def test_no_high_cases_rate_undefined(self):
        self.assertIsNone(ordinal_metrics([0],[0])["high_grade_recall"])

    def test_group_leakage_rejected(self):
        rows=[{"sample_id":"a","split":"development","group_ids":["event-1"]},
              {"sample_id":"b","split":"test","group_ids":["event-1"]}]
        with self.assertRaises(ValueError):validate_split(rows)

    def test_ahp_known_consistent_matrix(self):
        expected=[.5,.3,.2]
        out=ahp([[a/b for b in expected] for a in expected])
        for a,b in zip(out["weights"],expected):self.assertAlmostEqual(a,b)
        self.assertAlmostEqual(out["consistency_index"],0)
        self.assertIsNone(out["consistency_ratio"])

    def test_critic_symmetric_anticorrelation(self):
        out=critic([[0,1],[.5,.5],[1,0]],["g1","g2","g3"])
        self.assertEqual(out["weights"],[.5,.5])

    def test_critic_degenerate_not_silent_equal_weights(self):
        for matrix in ([[0,0],[.5,.5],[1,1]],[[1,1],[1,1],[1,1]]):
            with self.assertRaises(ValueError):critic(matrix,["g1","g2","g3"])

    def test_critic_repeated_group_rejected(self):
        with self.assertRaises(ValueError):critic([[0,1],[.5,.5],[1,0]],["same"]*3)

    def test_combination_endpoints(self):
        self.assertEqual(combine([.8,.2],[.3,.7],1),[.8,.2])
        self.assertEqual(combine([.8,.2],[.3,.7],0),[.3,.7])


if __name__=="__main__":unittest.main()
