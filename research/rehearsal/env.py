"""Rehearsal environment: reset / step over a flood scenario (draft 2026-10-17).

reset(scenario) -> observation;  step(commands) -> (observation, objectives, done, info).
Objectives are returned as a vector-like dict (hours in each grade range, cost, review workload)
instead of one scalar reward, because Chapter 5 selects plans on several objectives with an
explicit "no certain C" constraint.  A Gymnasium wrapper is provided when gymnasium is installed.
"""

from __future__ import annotations

import numpy as np

from .evidence import VirtualInspection, assess
from .interfaces import Scenario
from .plans import Deployment


class RehearsalEnv:
    def __init__(self, adapter, inspection: VirtualInspection | None = None, dt_days=1.0 / 24.0,
                 decision_every=6, sections=None):
        self.adapter = adapter
        self.inspection = inspection or VirtualInspection()
        self.dt = dt_days
        self.decision_every = decision_every
        self.sections = tuple(sections or adapter.sections)

    # ------------------------------------------------------------------ episode control
    def reset(self, scenario: Scenario):
        self.sc = scenario
        self.rng = np.random.default_rng(scenario.seed + 7)
        e = scenario.params.get("e_true", 0.8)
        self.i_cr_true = (2.65 - 1.0) / (1.0 + e)
        self.adapter.reset(scenario)
        self.inspection.reset(scenario.seed)
        self.deploy = Deployment(self.adapter.supported_measures)
        self.t = 0.0
        self.log = []
        self.out = self.adapter.steady(scenario.stage(0.0))
        return self._observe()

    def step(self, commands: dict[str, float]):
        self.deploy.set_commands(commands)
        for _ in range(self.decision_every):
            t0 = self.t
            self.deploy.advance(self.dt)
            self.t += self.dt
            self.adapter.set_boundary(self.t, self.sc.stage(self.t))
            self.adapter.apply_measures(self.deploy.states())
            self.out = self.adapter.advance(self.dt)
            self.inspection.step(t0, self.t, self.out, self.i_cr_true, self.sections)
            for sec in self.sections:
                a = assess(self.out, self.inspection, sec, self.t)
                true_r = self.out.max_gradient(sec) / self.i_cr_true
                self.log.append(dict(t=self.t, section=sec, stage=self.out.river_stage, r_low=a.r_low, r_high=a.r_high,
                                     r_true=true_r, grade_low=a.grade_low, grade_high=a.grade_high, warning=a.warning,
                                     reasons=a.reasons, cost=self.deploy.cost,
                                     levels={k: round(v, 3) for k, v in self.deploy.level.items()}))
        done = self.t >= self.sc.duration - 1e-9
        return self._observe(), self.objectives(), done, {"last": self.log[-len(self.sections):]}

    # ------------------------------------------------------------------ observation and prediction
    def _observe(self):
        noise = self.rng.normal(0.0, 0.03, len(self.out.probes))
        probes = {k: v + n for (k, v), n in zip(self.out.probes.items(), noise)}
        fc = {lead: self.sc.stage(self.t + lead) + self.rng.normal(0.0, self.sc.forecast_error * lead)
              for lead in (0.25, 0.5, 1.0)}
        return {"t": self.t, "stage": self.sc.stage(self.t), "stage_forecast": fc, "probes": probes,
                "evidence": [(e.event_id, e.section, e.state) for e in self.inspection.events],
                "measures": dict(self.deploy.level)}

    def predict_r_high(self, stage, measures):
        """Quasi-steady prediction with the same adapter (the twin forecasting itself)."""
        out = self.adapter.steady(stage, measures)
        return max((f.risk_ratio_bounds()[1] for f in out.exits), default=0.0)

    # ------------------------------------------------------------------ objectives
    def objectives(self):
        h = 24.0 * self.dt
        L = self.log
        first_c = next((r["t"] for r in L if r["grade_low"] == "C"), None)
        first_w2 = next((r["t"] for r in L if r["warning"] in ("一级", "二级")), None)
        lead = None if first_c is None or first_w2 is None else 24.0 * (first_c - first_w2)
        ev = self.inspection.events
        return {
            "hours_certain_C": h * sum(r["grade_low"] == "C" for r in L),
            "hours_possible_C": h * sum(r["grade_high"] == "C" for r in L),
            "hours_B_or_worse": h * sum(r["grade_low"] in "BC" for r in L),
            "hours_true_R_ge_1": h * sum(r["r_true"] >= 1.0 for r in L),
            "max_r_high": max((r["r_high"] for r in L), default=0.0),
            "warning_lead_h": lead,
            "cost": self.deploy.cost,
            "reviews": len(ev),
            "false_reviews": sum(not e.true_event for e in ev),
            "confirmed": sum(e.state == "确认" for e in ev),
        }


def run_episode(env: RehearsalEnv, plan, scenario: Scenario):
    obs = env.reset(scenario)
    ctx = {"predict": env.predict_r_high}
    done = False
    while not done:
        obs, obj, done, _ = env.step(plan(obs, ctx))
    return obj


try:  # optional Gymnasium view: action = four levels in [0, 1]
    import gymnasium as gym

    class RehearsalGymEnv(gym.Env):
        KINDS = ("relief_well", "filter_well", "berm", "polder_storage")

        def __init__(self, env: RehearsalEnv, scenario_sampler, weights=None):
            self.env, self.sample = env, scenario_sampler
            self.w = weights or {"hours_certain_C": 10.0, "hours_possible_C": 1.0, "hours_B_or_worse": 0.2, "cost": 1.0}
            self.action_space = gym.spaces.Box(0.0, 1.0, shape=(4,))
            self.observation_space = gym.spaces.Box(-np.inf, np.inf, shape=(9,))
            self._prev = None

        def _vec(self, obs):
            p = list(obs["probes"].values()) + [0.0] * 3
            fc = obs["stage_forecast"]
            return np.array([obs["stage"], fc[0.5], *p[:3], *(obs["measures"].get(k, 0.0) for k in self.KINDS)], dtype=float)

        def _scalar(self, obj):
            return sum(self.w[k] * obj[k] for k in self.w)

        def reset(self, seed=None, options=None):
            obs = self.env.reset(self.sample(seed))
            self._prev = 0.0
            return self._vec(obs), {}

        def step(self, action):
            cmd = dict(zip(self.KINDS, np.clip(action, 0, 1)))
            obs, obj, done, info = self.env.step(cmd)
            s = self._scalar(obj)
            r, self._prev = -(s - self._prev), s
            return self._vec(obs), r, False, done, {"objectives": obj}
except ImportError:  # pragma: no cover
    RehearsalGymEnv = None
