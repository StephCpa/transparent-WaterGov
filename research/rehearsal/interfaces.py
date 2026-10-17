"""Data contracts of the rehearsal module (draft 2026-10-17).

The rehearsal environment never touches solver internals.  Every seepage model, from a lookup of
published Chapter 4 results to the Chapter 4 finite-volume code, is wrapped as a SeepageAdapter
that accepts boundary conditions and measures and returns SeepageOutputs.  This mirrors the
PDEBase / TransientSolver split of HydroGym (github.com/dynamicslab/hydrogym), so the same adapter
can also be exposed through HydroGym's FlowEnv (see hydrogym_compat.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

# critical-gradient interval used in Chapter 4 (Gs = 2.65, e = 0.6..1.0) and Chapter 5 case five
I_CR_LOW, I_CR_HIGH = 0.825, 1.03125


@dataclass(frozen=True)
class MeasureState:
    """One emergency measure as currently deployed (after ramp-up)."""
    kind: str                 # "relief_well" | "filter_well" | "berm" | "polder_storage"
    level: float              # 0..1 fraction of the installed capacity in effect
    params: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ExitFace:
    """An upward exit face (2-D segment or 3-D facet) with its normal exit gradient."""
    face_id: str
    section: str              # evaluation unit the face is registered to
    i_up: float               # normal upward exit gradient, Eq. (4-43)
    length_or_area: float
    layer: str = ""
    thickness: float | None = None        # thickness of the exit (blanket) layer, m, when known
    surcharge_head: float = 0.0           # resisting head added by a berm or load, m of water

    def risk_ratio_bounds(self, i_cr_low: float = I_CR_LOW, i_cr_high: float = I_CR_HIGH) -> tuple[float, float]:
        """(lower, upper) bound of R = i / i_cr; a berm surcharge raises the resisting gradient by s/z."""
        extra = self.surcharge_head / self.thickness if self.thickness else 0.0
        return self.i_up / (i_cr_high + extra), self.i_up / (i_cr_low + extra)


@dataclass
class SeepageOutputs:
    t: float                              # days
    river_stage: float                    # m
    exits: list[ExitFace]
    probes: dict[str, float]              # virtual piezometer heads, m
    outflow: float | None = None          # m^2/s per metre (2-D) or m^3/s (3-D)
    high_gradient_area: float | None = None   # area or length with i_up >= I_CR_LOW
    fidelity: str = ""                    # "R0" | "R1" | "R2"
    notes: str = ""

    def max_gradient(self, section: str | None = None) -> float:
        faces = [f for f in self.exits if section is None or f.section == section]
        return max((f.i_up for f in faces), default=0.0)


@runtime_checkable
class SeepageAdapter(Protocol):
    """Contract a seepage model must satisfy to be driven by the rehearsal environment."""

    fidelity: str
    transient: bool                       # False: quasi-steady solve at each step
    supported_measures: tuple[str, ...]
    sections: tuple[str, ...]

    def reset(self, scenario: "Scenario") -> None: ...
    def set_boundary(self, t: float, river_stage: float) -> None: ...
    def apply_measures(self, measures: list[MeasureState]) -> None: ...
    def advance(self, dt: float) -> SeepageOutputs: ...
    def steady(self, river_stage: float, measures: list[MeasureState] | None = None) -> SeepageOutputs: ...


@dataclass
class Scenario:
    """A flood process plus the parameter realisation used for one rehearsal episode."""
    scenario_id: str
    stage: "callable"                     # t (days) -> river stage (m)
    duration: float                       # days
    forecast_error: float = 0.0           # std of the stage forecast error per day of lead, m
    params: dict = field(default_factory=dict)
    seed: int = 0
