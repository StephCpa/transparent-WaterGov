"""Expose a SeepageAdapter through HydroGym's FlowEnv (optional; needs `hydrogym` core).

HydroGym's core classes are solver-independent: a PDEBase holds state, actuators, observations
and the objective; a TransientSolver advances it; FlowEnv provides the Gymnasium API with
actuation sub-steps.  Wrapping the adapter this way lets HydroGym tooling (and Stable-Baselines3
etc.) drive the levee rehearsal.  The objective is a scalarisation of the Chapter 5 gates plus
measure cost; plan selection itself should stay multi-objective (runner.compare_plans).
"""

from __future__ import annotations

import numpy as np
from hydrogym.core import ActuatorBase, FlowEnv, PDEBase, TransientSolver

from .interfaces import MeasureState
from .plans import CATALOGUE


class RampActuator(ActuatorBase):
    def __init__(self, ramp_days, **kw):
        super().__init__(**kw)
        self.ramp = ramp_days

    def step(self, u, dt):
        u = float(np.clip(u, 0.0, 1.0))
        d = dt / self.ramp
        self.x = min(self.x + d, u) if u > self.x else max(self.x - d, u)


class LeveeRehearsalFlow(PDEBase):
    MAX_CONTROL = 1.0
    DEFAULT_DT = 1.0 / 24.0

    def __init__(self, adapter_factory, scenario_sampler, seed=0, **cfg):
        self.adapter = adapter_factory()
        self.kinds = list(self.adapter.supported_measures)
        self.sample, self.seed = scenario_sampler, seed
        super().__init__(**cfg)

    @property
    def num_inputs(self):
        return len(self.kinds)

    @property
    def num_outputs(self):
        return 2 + 3

    def load_mesh(self, name):
        return None

    def initialize_state(self):
        self.t = 0.0

    def init_bcs(self):
        self.actuators = [RampActuator(CATALOGUE[k].ramp_days) for k in self.kinds]

    def reset(self, q0=None, t=0.0):
        self.scenario = self.sample(self.seed)
        self.seed += 1
        self.adapter.reset(self.scenario)
        self.t = t
        self.reset_controls()
        self.out = self.adapter.steady(self.scenario.stage(t))

    def copy_state(self, deepcopy=True):
        return None

    def save_checkpoint(self, filename):
        pass

    def load_checkpoint(self, filename):
        pass

    def render(self, **kw):
        pass

    def get_observations(self):
        p = list(self.out.probes.values()) + [0.0] * 3
        return np.array([self.scenario.stage(self.t), self.scenario.stage(self.t + 0.5), *p[:3]])

    def evaluate_objective(self, q=None):
        r_high = max((f.risk_ratio_bounds()[1] for f in self.out.exits), default=0.0)
        cost = sum(CATALOGUE[k].running_cost_per_day * a.state for k, a in zip(self.kinds, self.actuators))
        return 50.0 * max(r_high - 0.8, 0.0) ** 2 + 500.0 * max(r_high - 1.0, 0.0) ** 2 + cost


class AdapterSolver(TransientSolver):
    def step(self, iter, control=None, **kw):
        f = self.flow
        f.advance_time(self.dt, None if control is None else list(np.clip(np.ravel(control), 0.0, 1.0)))
        f.adapter.set_boundary(f.t, f.scenario.stage(f.t))
        f.adapter.apply_measures([MeasureState(k, a.state) for k, a in zip(f.kinds, f.actuators) if a.state > 0])
        f.out = f.adapter.advance(self.dt)
        return f


def make_flow_env(adapter_factory, scenario_sampler, substeps=6, episode_days=10.0):
    return FlowEnv({
        "flow": LeveeRehearsalFlow,
        "flow_config": {"adapter_factory": adapter_factory, "scenario_sampler": scenario_sampler},
        "solver": AdapterSolver, "solver_config": {"dt": 1.0 / 24.0},
        "actuation_config": {"num_substeps": substeps, "reward_aggregation": "mean"},
        "max_steps": int(round(episode_days * 24)) - 1,
    })
