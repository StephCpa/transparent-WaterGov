"""Virtual inspection and the time-varying part of the Chapter 5 evaluation (draft 2026-10-17).

Virtual inspection turns the true exit state of a rehearsal into the evidence a manager would
actually hold: candidates (including false alarms), reviews and confirmed events, with the
evidence states of Chapter 5 (Table 5-12).  Detection and false-alarm rates are placeholders:
the only field data (Chapter 5) are 9 daytime candidates in 113 images, all false; no detection
rate for real boils exists yet.  They are configuration, not results.

The evaluator applies the Chapter 5 seepage gates (R >= 0.8 not better than B, R >= 1.0 C) to
the interval of R implied by the unknown void ratio (i_cr in [0.825, 1.03125]), the observation
gate (a confirmed event is C, an open candidate only raises the possible upper bound) and the
warning levels of Table 5-17.  Static indicators (the other 27) are outside this draft; coupling
them through the delivered rule chain is milestone M1 of the design note.  An upper bound that is
only "possibly B" is reported as a level-three warning, which is more cautious than Table 5-17.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .interfaces import SeepageOutputs

GRADES = "ABC"


@dataclass
class InspectionConfig:
    flight_times_h: tuple[float, ...] = (2.0, 14.0)     # local hours of the two daily flights
    p_detect_night: float = 0.85
    p_detect_day: float = 0.60
    false_rate_night: float = 0.15                    # expected false candidates per section flight
    false_rate_day: float = 1.0
    review_delay_h: float = 2.0
    p_review_correct: float = 0.95                    # a false candidate is cleared, a true one confirmed
    validity_h: float = 24.0                          # coverage older than this counts as missing


@dataclass
class Evidence:
    event_id: str
    section: str
    t_detect: float
    true_event: bool
    state: str = "候选"                               # 候选 -> 已复核(确认 / 误报 / 存疑)
    t_review: float | None = None
    due: float | None = None                          # time the next review is completed


@dataclass
class VirtualInspection:
    cfg: InspectionConfig = field(default_factory=InspectionConfig)
    rng: np.random.Generator = field(default_factory=lambda: np.random.default_rng(0))

    def reset(self, seed: int):
        self.rng = np.random.default_rng(seed)
        self.events: list[Evidence] = []
        self.last_flight: dict[str, float] = {}
        self._n = 0

    def step(self, t0: float, t1: float, outputs: SeepageOutputs, i_cr_true: float, sections):
        """Fly the flights scheduled in (t0, t1] and process reviews that fall due."""
        for day in range(int(np.floor(t0)), int(np.floor(t1)) + 1):
            for hh in self.cfg.flight_times_h:
                tf = day + hh / 24.0
                if not (t0 < tf <= t1):
                    continue
                night = hh < 6 or hh >= 20
                for sec in sections:
                    self.last_flight[sec] = tf
                    for ev in self.events:                    # a doubtful point is re-checked on the next flight
                        if ev.section == sec and ev.state == "存疑" and ev.due is None:
                            ev.due = tf + self.cfg.review_delay_h / 24.0
                    boil = outputs.max_gradient(sec) / i_cr_true >= 1.0
                    p = self.cfg.p_detect_night if night else self.cfg.p_detect_day
                    if boil and self.rng.random() < p:
                        self._add(sec, tf, True)
                    lam = self.cfg.false_rate_night if night else self.cfg.false_rate_day
                    for _ in range(self.rng.poisson(lam)):
                        self._add(sec, tf, False)
        for ev in self.events:
            if ev.state in ("候选", "存疑") and ev.due is not None and ev.due <= t1:
                ok = self.rng.random() < self.cfg.p_review_correct
                ev.state = ("确认" if ok else "存疑") if ev.true_event else ("误报" if ok else "存疑")
                ev.t_review, ev.due = ev.due, None

    def _add(self, sec, t, true_event):
        self._n += 1
        self.events.append(Evidence(f"E{self._n:03d}", sec, t, true_event, due=t + self.cfg.review_delay_h / 24.0))

    def coverage_ok(self, sec, t):
        last = self.last_flight.get(sec)
        return last is not None and t - last <= self.cfg.validity_h / 24.0


@dataclass
class StepAssessment:
    section: str
    r_low: float
    r_high: float
    grade_low: str
    grade_high: str
    warning: str
    reasons: list[str]


def assess(outputs: SeepageOutputs, inspection: VirtualInspection, section: str, t: float) -> StepAssessment:
    faces = [f for f in outputs.exits if f.section == section]
    bounds = [f.risk_ratio_bounds() for f in faces] or [(0.0, 0.0)]
    r_low, r_high = max(b[0] for b in bounds), max(b[1] for b in bounds)
    low, high, why = 0, 0, []
    if r_low >= 1.0:
        low = high = 2; why.append("坡降比确定达到1.0（C级门控）")
    elif r_high >= 1.0:
        high = 2; why.append("坡降比可能达到1.0（取决于出口土层孔隙比）")
    if r_low >= 0.8:
        low = max(low, 1); why.append("坡降比确定达到0.8（不优于B级）")
    elif r_high >= 0.8:
        high = max(high, 1)
    evs = [e for e in inspection.events if e.section == section and e.t_detect <= t]
    if any(e.state == "确认" for e in evs):
        low = high = 2; why.append("存在确认的渗漏/管涌事件（观测门控）")
    elif any(e.state in ("候选", "存疑") for e in evs):
        high = 2; why.append("存在待复核或存疑候选，放宽等级上限")
    if not inspection.coverage_ok(section, t):
        high = max(high, 1); why.append("巡检覆盖缺失或过期，不能给出确定A级")
    high = max(high, low)
    if low == 2:
        warn = "一级"
    elif high == 2 or (low == 1 and r_high >= 0.8):
        warn = "二级"
    elif low == 1:
        warn = "三级"
    elif high == 0:
        warn = "常规"
    else:
        warn = "三级"
    return StepAssessment(section, r_low, r_high, GRADES[low], GRADES[high], warn, why)
