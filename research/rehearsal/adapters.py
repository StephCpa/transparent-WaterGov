"""Stand-in seepage adapters until the Chapter 4 finite-volume code is available.

R0  ResponseSurfaceCh4: quasi-steady lookup of the values printed in the 1028 thesis Chapter 4
    (Tables 4-10 and 4-12, Sec. 4.5.2-4.5.3; five stages 26.23-33.89 m, 33.89 m = flood level).
    Section exit gradients are printed at two stages only (30.00 m and 33.89 m; no upward exit at
    28.00 m and below), so each section curve is a piecewise-linear interpolation through
    (28.00, 0), (30.00, i) and (33.89, i), extrapolated above 33.89 m, and flagged as such; the
    three-dimensional high-gradient area (classes II+III, day 60) and outflows have five stages.
    No measures can be represented.  Chapter 4 reports that the 3-D outflow is within 0.28 % of
    its 30-day value after 6 h, which is what justifies a quasi-steady lookup for floods that
    change over days.
R1  Blanket1D: confined sand layer under a semi-pervious landside blanket (one cross-section,
    synthetic parameters), transient implicit finite differences, with four emergency measures:
    relief wells (sink), filter wells / ring dikes around exits (raised tailwater over the exit
    zone), a seepage berm (overburden surcharge), and polder storage (raised tailwater over the
    whole landside).  Heads are converted to elevations with the landside ground level z_g.
R2  (to be written) the Chapter 4 2-D/3-D finite-volume model behind the same interface.
"""

from __future__ import annotations

import numpy as np
from scipy.linalg import solve_banded

from .interfaces import I_CR_LOW, ExitFace, MeasureState, Scenario, SeepageOutputs

# ---------------------------------------------------------------- R0: Chapter 4 published values
CH4_STAGES = np.array([26.23, 28.00, 30.00, 32.00, 33.89])
CH4_OUTFLOW_SEC1 = np.array([0.0, 0.0, 1.14698, 3.58803, 6.0274]) * 1e-3              # m^2/s, Table 4-10
CH4_OUTFLOW_SEC2 = np.array([0.0, 0.0, 1.34603, 3.57222, 5.79195]) * 1e-3
CH4_OUTFLOW_3D = np.array([0.0, 0.00894392, 1.33849, 3.38475, 5.47273])               # m^3/s
CH4_HIGH_AREA_3D = np.array([0.0, 0.0, 1066.7, 6826.7, 23822.2])                       # m^2, i_up >= 0.825 (Table 4-12)
CH4_SECTION_GRADIENT = {                                                               # max upward exit gradient, 2-D steady
    "断面Ⅰ": ((28.00, 0.0), (30.00, 0.9247), (33.89, 2.149)),
    "断面Ⅱ": ((28.00, 0.0), (30.00, 0.4216), (33.89, 1.17)),
}
CH4_GRADIENT_NOTE = "断面梯度按第4章30.00 m与33.89 m两点（28.00 m无向上出逸）分段线性插值"


def _section_gradient(points, stage):
    (h0, g0), (h1, g1), (h2, g2) = points
    if stage <= h0:
        return 0.0
    if stage <= h1:
        return g0 + (g1 - g0) * (stage - h0) / (h1 - h0)
    return g1 + (g2 - g1) * (stage - h1) / (h2 - h1)       # also the extrapolation above 33.89 m


class ResponseSurfaceCh4:
    fidelity = "R0"
    transient = False
    supported_measures: tuple[str, ...] = ()
    sections = tuple(CH4_SECTION_GRADIENT)

    def reset(self, scenario: Scenario) -> None:
        self.stage_now, self.t = scenario.stage(0.0), 0.0

    def set_boundary(self, t, river_stage):
        self.t, self.stage_now = t, river_stage

    def apply_measures(self, measures):
        if any(m.level > 0 for m in measures):
            raise NotImplementedError("R0 cannot represent emergency measures; use R1 or the Chapter 4 adapter")

    def steady(self, river_stage, measures=None):
        self.apply_measures(measures or [])
        exits = [ExitFace(f"{name}/max", name, _section_gradient(points, river_stage), 0.0, layer="出口土层（孔隙比未知）")
                 for name, points in CH4_SECTION_GRADIENT.items()]
        s = float(np.clip(river_stage, CH4_STAGES[0], CH4_STAGES[-1]))
        inside = CH4_STAGES[0] <= river_stage <= CH4_STAGES[-1]
        return SeepageOutputs(
            t=getattr(self, "t", 0.0), river_stage=river_stage,
            exits=exits, probes={}, outflow=float(np.interp(s, CH4_STAGES, CH4_OUTFLOW_3D)),
            high_gradient_area=float(np.interp(s, CH4_STAGES, CH4_HIGH_AREA_3D)), fidelity=self.fidelity,
            notes=CH4_GRADIENT_NOTE + ("" if inside else "；超出26.23～33.89 m时梯度外推、出流与面积取端值"))

    def advance(self, dt):
        self.t += dt
        return self.steady(self.stage_now)


# ---------------------------------------------------------------- R1: one-dimensional blanket model
class Blanket1D:
    fidelity = "R1"
    transient = True
    supported_measures = ("relief_well", "filter_well", "berm", "polder_storage")
    sections = ("S1",)
    DEFAULTS = dict(L_r=100.0, B=40.0, L_l=400.0, dx=5.0, D=15.0, k_f=50.0, Ss=1e-4, z_b=4.0, k_b=0.05,
                    z_g=26.5, x_w=15.0, q_well=30.0, filter_zone=(0.0, 30.0), filter_rise=1.5,
                    berm_zone=(0.0, 40.0), berm_thickness=1.5, berm_unit_weight=19.0, polder_rise=1.0,
                    exit_zone=(0.0, 120.0), probes=(0.0, 30.0, 80.0))

    def __init__(self, **cfg):
        self.base = dict(self.DEFAULTS, **cfg)

    # -- interface
    def reset(self, scenario: Scenario) -> None:
        self.c = dict(self.base, **scenario.params)
        c = self.c
        self.x = np.arange(-(c["L_r"] + c["B"]), c["L_l"] + 1e-9, c["dx"])
        self.T, self.S = c["k_f"] * c["D"], c["Ss"] * c["D"]
        self.land = self.x > 1e-9
        self.iw = int(np.argmin(abs(self.x - c["x_w"])))
        self.measures: list[MeasureState] = []
        self.t = 0.0
        self.stage_now = scenario.stage(0.0)
        self.h = self._solve(None, 0.0)

    def set_boundary(self, t, river_stage):
        self.t, self.stage_now = t, river_stage

    def apply_measures(self, measures):
        bad = [m.kind for m in measures if m.kind not in self.supported_measures]
        if bad:
            raise NotImplementedError(f"R1 does not represent {bad}")
        self.measures = list(measures)

    def advance(self, dt):
        self.h = self._solve(self.h, dt)
        self.t += dt
        return self._outputs()

    def steady(self, river_stage, measures=None):
        keep = (self.stage_now, self.measures, self.h)
        self.stage_now = river_stage
        if measures is not None:
            self.apply_measures(measures)
        self.h = self._solve(None, 0.0)
        out = self._outputs()
        self.stage_now, self.measures, self.h = keep
        return out

    # -- physics
    def _level(self, kind):
        return sum(m.level for m in self.measures if m.kind == kind)

    def _tailwater(self):
        c, x = self.c, self.x
        tw = np.zeros_like(x)
        a, b = c["filter_zone"]
        tw[(x > a) & (x <= b)] += c["filter_rise"] * self._level("filter_well")
        tw[self.land] += c["polder_rise"] * self._level("polder_storage")
        return tw

    def _solve(self, h_old, dt):
        c = self.c
        n, a = len(self.x), self.T / c["dx"] ** 2
        leak = np.where(self.land, c["k_b"] / c["z_b"], 0.0)
        st = self.S / dt if dt else 0.0
        ab = np.zeros((3, n))
        ab[1] = st + 2 * a + leak
        ab[0, 1:] = -a
        ab[2, :-1] = -a
        ab[1, 0], ab[0, 1] = 1.0, 0.0                       # river entry: Dirichlet
        ab[1, -1] = st + a + leak[-1]                        # far landside: no flow
        rhs = leak * self._tailwater() + (st * h_old if dt else 0.0)
        rhs[self.iw] -= c["q_well"] * self._level("relief_well") / c["dx"]
        rhs[0] = self.stage_now - c["z_g"]
        return solve_banded((1, 1), ab, rhs)

    def _outputs(self):
        c, x = self.c, self.x
        tw = self._tailwater()
        a, b = c["exit_zone"]
        ba, bb = c["berm_zone"]
        surcharge = c["berm_thickness"] * c["berm_unit_weight"] / 9.81 * self._level("berm")
        exits = []
        for k in np.nonzero((x > a) & (x <= b))[0]:
            i_up = max(self.h[k] - tw[k], 0.0) / c["z_b"]
            s = surcharge if ba < x[k] <= bb else 0.0
            exits.append(ExitFace(f"S1/x={x[k]:.0f}", "S1", float(i_up), c["dx"], layer="盖层", thickness=c["z_b"],
                                  surcharge_head=float(s)))
        probes = {f"P{j + 1}(x={p:.0f} m)": float(np.interp(p, x, self.h) + c["z_g"]) for j, p in enumerate(c["probes"])}
        high = sum(f.length_or_area for f in exits if f.i_up >= I_CR_LOW)
        q_out = float(np.sum(np.where(self.land, c["k_b"] / c["z_b"] * (self.h - tw), 0.0)) * c["dx"] / 86400)
        return SeepageOutputs(t=self.t, river_stage=self.stage_now, exits=exits, probes=probes, outflow=q_out,
                              high_gradient_area=high, fidelity=self.fidelity, notes="合成断面，参数未率定")
