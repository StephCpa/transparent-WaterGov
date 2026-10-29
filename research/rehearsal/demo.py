"""Demonstration of the rehearsal skeleton (run from research/:  python -m rehearsal.demo).

1. Inverse rehearsal on R0 (1028 Chapter 4 values, sections I and II): river stages at which the
   Chapter 5 seepage gates are possibly / certainly reached.
2. Inverse rehearsal on R1 (synthetic section) without and with each measure.
3. Five emergency plans compared on 100 synthetic flood scenarios with virtual inspection
   (two flights a day, 02:00 and 14:00), plus the look-ahead plan with night-only flights.

Everything except the R0 inputs is synthetic and uncalibrated; the output shows that the chain
works end to end, not how a real levee behaves.  Writes outputs/rehearsal_demo_20261017.json.
"""

from __future__ import annotations

import json
from pathlib import Path

from .adapters import Blanket1D, ResponseSurfaceCh4
from .evidence import InspectionConfig, VirtualInspection
from .plans import PLANS
from .runner import compare_plans, inverse_rehearsal, measure_set, pareto, sample_scenarios

OUT = Path(__file__).resolve().parents[1] / "outputs" / "rehearsal_demo_20261017.json"


def main(n_scenarios=100):
    sc0 = sample_scenarios(1, seed=1)[0]
    r0 = {sec: inverse_rehearsal(ResponseSurfaceCh4(), sc0, section=sec) for sec in ResponseSurfaceCh4.sections}
    for sec, stages in r0.items():
        print(f"R0 {sec}（第4章30.00/33.89 m两点插值）门控水位/m:", stages)

    nominal = sample_scenarios(1, seed=2, param_ranges={"k_f": (50, 50), "k_b": (0.05, 0.05), "e_true": (0.7, 0.7)})[0]
    r1 = {}
    for label, ms in [("无措施", []), ("减压井满负荷", measure_set(relief_well=1.0)),
                      ("反滤围井", measure_set(filter_well=1.0)), ("压渗平台", measure_set(berm=1.0)),
                      ("蓄水反压", measure_set(polder_storage=1.0)),
                      ("减压井+反滤围井", measure_set(relief_well=1.0, filter_well=1.0))]:
        r1[label] = inverse_rehearsal(Blanket1D(), nominal, ms)
        print(f"R1 {label:10s}", r1[label])

    scenarios = sample_scenarios(n_scenarios, seed=20261017)
    rows = compare_plans(Blanket1D, PLANS, scenarios)
    night = VirtualInspection(InspectionConfig(flight_times_h=(2.0, 22.0)))
    rows["P3 + 仅夜间巡检"] = compare_plans(Blanket1D, {"x": PLANS["P3 预报前瞻（孪生预测）"]}, scenarios, inspection=night)["x"]
    front = pareto(rows)
    print(f"\n{n_scenarios}个合成洪水情景上的预案比选（Pareto前沿：{front}）")
    hdr = ("预案", "确定C场次", "可能C/h", "B及以上/h", "代价", "复核任务", "误报复核", "预警提前/h")
    print("{:22s} {:>8s} {:>8s} {:>9s} {:>6s} {:>7s} {:>7s} {:>9s}".format(*hdr))
    for k, v in rows.items():
        lead = "—" if v["median_warning_lead_h"] is None else f"{v['median_warning_lead_h']:.0f}"
        print(f"{k:22s} {v['episodes_certain_C']:8d} {v['hours_possible_C']:8.1f} {v['hours_B_or_worse']:9.1f} "
              f"{v['cost']:6.2f} {v['reviews']:7.1f} {v['false_reviews']:7.1f} {lead:>9s}")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"R0_gate_stages": r0, "R1_gate_stages": r1, "plans": rows, "pareto": front,
                               "n_scenarios": n_scenarios, "synthetic": True}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
