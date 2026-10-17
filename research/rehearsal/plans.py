"""Emergency measures and emergency plans (预案) as policies (draft 2026-10-17).

Costs are relative placeholders (one-off cost when a measure is first deployed plus a running
cost per day at full level); they must be replaced by local quotas before any comparison is
reported.  Ramp times stand for build-up (filter wells, berm) or start-up (wells, polder storage).
Built measures (filter wells, berm) cannot be withdrawn within an episode.
"""

from __future__ import annotations

from dataclasses import dataclass

from .interfaces import I_CR_LOW, MeasureState


@dataclass(frozen=True)
class MeasureSpec:
    kind: str
    name: str
    ramp_days: float
    one_off_cost: float
    running_cost_per_day: float
    reversible: bool


CATALOGUE = {
    "relief_well": MeasureSpec("relief_well", "减压井抽排", 0.25, 0.0, 1.0, True),
    "filter_well": MeasureSpec("filter_well", "反滤围井（养水盆）", 0.25, 2.0, 0.2, False),
    "berm": MeasureSpec("berm", "压渗平台（盖重）", 1.0, 8.0, 0.0, False),
    "polder_storage": MeasureSpec("polder_storage", "蓄水反压（垸内抬高水位）", 0.5, 0.0, 1.5, True),
}


class Deployment:
    """Tracks commanded and effective levels of every measure, with ramps and costs."""

    def __init__(self, kinds):
        self.kinds = [k for k in kinds if k in CATALOGUE]
        self.level = {k: 0.0 for k in self.kinds}
        self.command = {k: 0.0 for k in self.kinds}
        self.deployed_once: set[str] = set()
        self.cost = 0.0

    def set_commands(self, commands: dict[str, float]):
        for k, v in commands.items():
            if k not in self.level:
                continue
            v = min(max(float(v), 0.0), 1.0)
            if not CATALOGUE[k].reversible:
                v = max(v, self.command[k])
            self.command[k] = v

    def advance(self, dt):
        for k in self.kinds:
            spec, target = CATALOGUE[k], self.command[k]
            step = dt / spec.ramp_days
            cur = self.level[k]
            self.level[k] = min(cur + step, target) if target > cur else max(cur - step, target)
            if self.command[k] > 0 and k not in self.deployed_once:
                self.deployed_once.add(k)
                self.cost += spec.one_off_cost
            self.cost += spec.running_cost_per_day * self.level[k] * dt

    def states(self):
        return [MeasureState(k, self.level[k]) for k in self.kinds if self.level[k] > 0]


# ---------------------------------------------------------------- plans
def r_high_from_probe(obs, probe="P1(x=0 m)", z_b=4.0, z_g=26.5):
    """Upper bound of R at the toe estimated from the toe piezometer (unknown void ratio)."""
    head = obs["probes"].get(probe)
    return 0.0 if head is None else max(head - z_g, 0.0) / z_b / I_CR_LOW


def plan_patrol_only(obs, ctx):
    return {}


def plan_stage_triggered(alert=31.5, guarantee=32.5):
    """Classic stage-triggered response: wells at the alert stage, filter wells at the guarantee stage."""
    def plan(obs, ctx):
        h = obs["stage"]
        return {"relief_well": 1.0 if h >= alert else 0.0, "filter_well": 1.0 if h >= guarantee else 0.0}
    return plan


def plan_piezometer_feedback(lo=0.6, hi=0.9, filter_at=0.95):
    """Proportional relief-well control on the measured toe head; filter wells when R is high."""
    def plan(obs, ctx):
        r = r_high_from_probe(obs)
        return {"relief_well": min(max((r - lo) / (hi - lo), 0.0), 1.0), "filter_well": 1.0 if r >= filter_at else 0.0}
    return plan


def plan_forecast_lookahead(target=0.9, lead_days=0.5):
    """Model-predictive plan: use the digital twin itself on the stage forecast and pick the cheapest
    measure set whose predicted upper-bound R stays below the target."""
    menu = [{}, {"relief_well": 0.5}, {"relief_well": 1.0}, {"relief_well": 1.0, "filter_well": 1.0},
            {"relief_well": 1.0, "filter_well": 1.0, "polder_storage": 1.0}]

    def plan(obs, ctx):
        stage_fc = obs["stage_forecast"].get(lead_days, obs["stage"])
        for m in menu:
            states = [MeasureState(k, v) for k, v in m.items()]
            pred = ctx["predict"](stage_fc, states)
            if pred <= target:
                return m
        return menu[-1]
    return plan


def plan_polder_first(at=0.8):
    def plan(obs, ctx):
        return {"polder_storage": 1.0 if r_high_from_probe(obs) >= at else 0.0}
    return plan


PLANS = {
    "P0 仅巡查": plan_patrol_only,
    "P1 水位分级响应": plan_stage_triggered(),
    "P2 测压管反馈": plan_piezometer_feedback(),
    "P3 预报前瞻（孪生预测）": plan_forecast_lookahead(),
    "P4 蓄水反压优先": plan_polder_first(),
}
