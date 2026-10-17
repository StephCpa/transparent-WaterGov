"""Scenario generation, batch plan comparison and inverse rehearsal (draft 2026-10-17)."""

from __future__ import annotations

import numpy as np

from .env import RehearsalEnv, run_episode
from .interfaces import MeasureState, Scenario


def hydrograph(base, peak, t_peak, recession):
    """Smooth rise to the peak, exponential recession afterwards (stage in m, time in days)."""
    def stage(t):
        if t <= t_peak:
            s = min(max(t / t_peak, 0.0), 1.0)
            return base + (peak - base) * s * s * (3 - 2 * s)
        return base + (peak - base) * np.exp(-(t - t_peak) / recession)
    return stage


def sample_scenarios(n, seed=0, base=29.5, peak=(31.5, 35.5), duration=10.0, forecast_error=0.15,
                     param_ranges=None):
    """Flood processes for the R1 synthetic section, with unknown permeabilities and void ratio."""
    rng = np.random.default_rng(seed)
    pr = param_ranges or {"k_f": (30.0, 80.0), "k_b": (0.02, 0.10), "e_true": (0.6, 1.0)}
    out = []
    for j in range(n):
        p = {k: float(rng.uniform(*v)) for k, v in pr.items()}
        hp, tp, rec = rng.uniform(*peak), rng.uniform(2.5, 5.0), rng.uniform(1.0, 3.0)
        out.append(Scenario(f"S{seed}-{j:03d}", hydrograph(base, hp, tp, rec), duration, forecast_error,
                            {k: v for k, v in p.items() if k != "e_true"} | {"e_true": p["e_true"]}, seed * 100000 + j))
    return out


def compare_plans(adapter_factory, plans: dict, scenarios, **env_kw):
    rows = {}
    for name, plan in plans.items():
        objs = [run_episode(RehearsalEnv(adapter_factory(), **env_kw), plan, sc) for sc in scenarios]
        rows[name] = summarize(objs)
    return rows


def summarize(objs):
    keys = [k for k in objs[0] if k != "warning_lead_h"]
    s = {k: float(np.mean([o[k] for o in objs])) for k in keys}
    leads = [o["warning_lead_h"] for o in objs if o["warning_lead_h"] is not None]
    s["episodes_certain_C"] = int(sum(o["hours_certain_C"] > 0 for o in objs))
    s["episodes_true_boil"] = int(sum(o["hours_true_R_ge_1"] > 0 for o in objs))
    s["median_warning_lead_h"] = float(np.median(leads)) if leads else None
    s["n"] = len(objs)
    return s


def pareto(rows, keys=("episodes_certain_C", "hours_possible_C", "cost", "reviews")):
    """Names of the plans not dominated on the given (minimised) objectives."""
    names = list(rows)
    keep = []
    for a in names:
        va = [rows[a][k] for k in keys]
        dominated = any(all(rows[b][k] <= x for k, x in zip(keys, va)) and any(rows[b][k] < x for k, x in zip(keys, va))
                        for b in names if b != a)
        if not dominated:
            keep.append(a)
    return keep


def inverse_rehearsal(adapter, scenario, measures=None, section=None, lo=28.0, hi=37.0, tol=0.005):
    """Lowest river stage at which each gate is reached (quasi-steady), by bisection.

    Returns stages for: possible B (upper R >= 0.8), certain B (lower R >= 0.8),
    possible C (upper R >= 1.0), certain C (lower R >= 1.0).  None if not reached below `hi`.
    """
    adapter.reset(scenario)
    measures = measures or []

    def bounds(stage):
        out = adapter.steady(stage, measures)
        faces = [f for f in out.exits if section is None or f.section == section]
        b = [f.risk_ratio_bounds() for f in faces] or [(0.0, 0.0)]
        return max(x[0] for x in b), max(x[1] for x in b)

    res = {}
    for name, idx, thr in (("possible_B", 1, 0.8), ("certain_B", 0, 0.8), ("possible_C", 1, 1.0), ("certain_C", 0, 1.0)):
        a, b = lo, hi
        if bounds(b)[idx] < thr:
            res[name] = None
            continue
        if bounds(a)[idx] >= thr:
            res[name] = a
            continue
        while b - a > tol:
            m = 0.5 * (a + b)
            a, b = (m, b) if bounds(m)[idx] < thr else (a, m)
        res[name] = round(b, 3)
    return res


def measure_set(**levels):
    return [MeasureState(k, v) for k, v in levels.items()]
