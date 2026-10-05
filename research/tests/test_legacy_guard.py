import copy
import json
from pathlib import Path
import tempfile
import unittest
from transparent_eval.baseline875 import load_baseline, verify_snapshot
from transparent_eval.legacy_guard import evaluate_guarded


class LegacyGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b=load_baseline()
        cls.samples,cls.geo,cls.buildings,cls.history=cls.b.generator.generate_dataset()

    def setUp(self):
        self.sec,self.leak=copy.deepcopy(self.samples[250])

    def evaluate(self,sec=None,**kwargs):
        return evaluate_guarded(self.sec if sec is None else sec,self.geo,self.buildings,
                                self.history,self.leak,**kwargs)

    def test_complete_input_exact_legacy_output(self):
        expected=self.b.model.evaluate_section(self.sec,self.geo,self.buildings,self.history,self.leak)
        actual=self.evaluate()
        self.assertEqual(actual['result'],expected)
        self.assertFalse(actual['engineering_validated'])

    def test_missing_gradients_cannot_become_full_scores(self):
        for field in ('渗透比降i','堤身渗透比降i','接触面渗透比降i'):
            for mode in ('delete','null'):
                with self.subTest(field=field,mode=mode):
                    sec=copy.deepcopy(self.sec)
                    if mode=='delete':del sec[field]
                    else:sec[field]=None
                    r=self.evaluate(sec)
                    self.assertIsNone(r['result'])
                    self.assertIsNone(r['safety_score'])
                    self.assertIsNone(r['safety_grade'])
                    self.assertIn(field,[x['field'] for x in r['issues']])

    def test_known_zero_gradient_is_distinct_from_missing(self):
        self.sec['堤身渗透比降i']=0.0
        r=self.evaluate()
        self.assertEqual(r['status'],'evaluated')
        self.assertEqual(r['result']['二级指标得分']['C4'],100.0)

    def test_invalid_numeric_inputs_have_no_grade(self):
        for bad in (float('nan'),float('inf'),True,-0.1):
            with self.subTest(bad=bad):
                self.sec['堤身渗透比降i']=bad
                self.assertIsNone(self.evaluate()['safety_grade'])

    def test_material_defaults_and_invalid_critical_gradient_blocked(self):
        for mutation in ({'控制层Gs':None},{'控制层Gs':1.0},{'控制层e':-1.0},
                         {'堤身Gs':2.65,'堤身e':None}):
            with self.subTest(mutation=mutation):
                sec={**self.sec,**mutation}
                self.assertIsNone(self.evaluate(sec)['safety_grade'])

    def test_missing_management_not_silently_reweighted(self):
        del self.sec['待输入指标']['E1']
        self.assertIsNone(self.evaluate()['safety_grade'])

    def test_missing_geology_and_buildings_not_assumed_normal(self):
        for geo,buildings in (([],self.buildings),(self.geo,[])):
            r=evaluate_guarded(self.sec,geo,buildings,self.history,self.leak)
            self.assertIsNone(r['safety_grade'])

    def test_absent_inspection_not_no_anomaly(self):
        for leak in (None,{},0):
            with self.subTest(leak=leak):
                r=evaluate_guarded(self.sec,self.geo,self.buildings,self.history,leak)
                self.assertIsNone(r['safety_grade'])

    def test_out_of_range_scores_are_not_clamped(self):
        for bad in (101,-1,True,'nan'):
            self.sec['待输入指标']['C2']=bad
            self.assertIsNone(self.evaluate()['safety_grade'])

    def test_not_applicable_requires_new_mode_configuration(self):
        self.sec['待输入指标']['C6']='不涉及'
        self.assertIsNone(self.evaluate()['safety_grade'])

    def test_missing_settlement_not_full_score(self):
        self.sec['软基段_沉降量_cm']=None
        self.assertIsNone(self.evaluate()['safety_grade'])

    def test_uav_channel_is_capable_of_affecting_controlled_case(self):
        self.sec,self.leak=copy.deepcopy(self.samples[0])
        self.leak.update({'渗漏点数':5,'加权渗漏点密度_点每100m':5.,
                          'UAV证据等级':3,'UAV门控等级上限':'C级_不安全'})
        full=self.evaluate()
        off=self.evaluate(uav_gate_enabled=False)
        self.assertEqual(full['safety_grade'],'C级_不安全')
        self.assertNotEqual(off['safety_grade'],full['safety_grade'])

    def test_diagnostic_switches_do_not_mutate_baseline(self):
        before=self.evaluate()['result']
        self.evaluate(c3_enabled=False,uav_gate_enabled=False)
        self.assertEqual(self.evaluate()['result'],before)

    def test_snapshot_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)
            (p/'manifest.json').write_text(json.dumps({'normalized_sha256':{'x.py':'0'*64}}))
            (p/'x.py').write_text('changed\n')
            with self.assertRaisesRegex(ValueError,'frozen baseline changed'):
                verify_snapshot(p)


if __name__=='__main__':unittest.main()
