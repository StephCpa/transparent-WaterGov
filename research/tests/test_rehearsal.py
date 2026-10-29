"""Tests of the rehearsal skeleton (needs numpy and scipy; HydroGym part skipped if absent)."""

import importlib.util
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rehearsal.adapters import Blanket1D, ResponseSurfaceCh4  # noqa: E402
from rehearsal.env import RehearsalEnv, run_episode  # noqa: E402
from rehearsal.interfaces import I_CR_HIGH, I_CR_LOW, SeepageAdapter  # noqa: E402
from rehearsal.plans import PLANS  # noqa: E402
from rehearsal.runner import inverse_rehearsal, measure_set, sample_scenarios  # noqa: E402


class RehearsalTests(unittest.TestCase):
    def setUp(self):
        self.sc = sample_scenarios(3, seed=5)

    def test_adapters_satisfy_contract(self):
        for a in (ResponseSurfaceCh4(), Blanket1D()):
            self.assertIsInstance(a, SeepageAdapter)

    def test_r0_reproduces_chapter4_values(self):
        a = ResponseSurfaceCh4()
        a.reset(self.sc[0])
        self.assertAlmostEqual(a.steady(30.00).max_gradient("断面Ⅰ"), 0.9247, places=4)
        self.assertAlmostEqual(a.steady(33.89).max_gradient("断面Ⅰ"), 2.149, places=4)
        self.assertAlmostEqual(a.steady(30.00).max_gradient("断面Ⅱ"), 0.4216, places=4)
        self.assertAlmostEqual(a.steady(33.89).max_gradient("断面Ⅱ"), 1.17, places=4)
        self.assertEqual(a.steady(28.00).max_gradient("断面Ⅰ"), 0.0)
        self.assertAlmostEqual(a.steady(33.89).high_gradient_area, 23822.2, places=1)
        self.assertAlmostEqual(a.steady(33.89).outflow, 5.47273, places=5)
        self.assertAlmostEqual(a.steady(30.00).outflow, 1.33849, places=5)
        with self.assertRaises(NotImplementedError):
            a.steady(31.0, measure_set(relief_well=1.0))

    def test_gate_interval_matches_chapter5(self):
        # 0.825 / 1.03125 = 0.8: "possible C" and "certain B" start at the same gradient
        self.assertAlmostEqual(I_CR_LOW / I_CR_HIGH, 0.8)
        r = inverse_rehearsal(ResponseSurfaceCh4(), self.sc[0])
        self.assertAlmostEqual(r["certain_B"], r["possible_C"], places=2)
        self.assertLess(r["possible_B"], r["certain_B"])
        self.assertLess(r["possible_C"], r["certain_C"])

    def test_measures_raise_gate_stages(self):
        base = inverse_rehearsal(Blanket1D(), self.sc[1])["certain_C"]
        for ms in (measure_set(relief_well=1.0), measure_set(filter_well=1.0), measure_set(berm=1.0),
                   measure_set(polder_storage=1.0)):
            r = inverse_rehearsal(Blanket1D(), self.sc[1], ms)["certain_C"]
            self.assertTrue(r is None or r > base)

    def test_episode_is_deterministic(self):
        plan = PLANS["P2 测压管反馈"]
        a = run_episode(RehearsalEnv(Blanket1D()), plan, self.sc[2])
        b = run_episode(RehearsalEnv(Blanket1D()), plan, self.sc[2])
        self.assertEqual(a, b)

    def test_built_measures_are_not_withdrawn(self):
        env = RehearsalEnv(Blanket1D())
        env.reset(self.sc[0])
        env.step({"berm": 1.0})
        env.step({"berm": 0.0})
        self.assertEqual(env.deploy.command["berm"], 1.0)

    @unittest.skipUnless(importlib.util.find_spec("hydrogym"), "hydrogym not installed")
    def test_hydrogym_flowenv(self):
        from rehearsal.hydrogym_compat import make_flow_env
        env = make_flow_env(Blanket1D, lambda s: sample_scenarios(1, seed=s)[0])
        obs, _ = env.reset()
        steps, done = 0, False
        while not done:
            obs, r, term, trunc, _ = env.step([1.0, 0.0, 0.0, 0.0])
            steps += 1
            done = term or trunc
        self.assertEqual(steps, 40)
        self.assertEqual(obs.shape, (5,))


if __name__ == "__main__":
    unittest.main()
