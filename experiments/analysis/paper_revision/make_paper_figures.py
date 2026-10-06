"""Regenerate the data figures of the English manuscript (revision of 2026-10-05).

Inputs are repository files only:
  * paper_statistics.json and per_record_predictions_875.csv (this folder,
    written by paper_statistics.py);
  * ml_baseline与多目标/cost_sensitive_results.json;
  * 875多种子稳健性/review_budget_sweep.csv;
  * inspection/audit/检测标签逐条记录.csv and 可疑点复核记录_非空行.csv;
  * baselines_and_pareto.json and policy_cloud_875.csv (this folder, written by
    baselines_and_pareto.py) for the policy-space evaluation figure.

Outputs (vector PDF, editable TrueType text) are written to
paper/english/figures/.  If the environment variable NATURE_FIGURE_SCRIPTS
points to the nature-figure ``scripts`` directory, the render-time panel
alignment gate is applied before export.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
FIG = REPO / "paper" / "english" / "figures"
FIG.mkdir(parents=True, exist_ok=True)

mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Liberation Sans", "Arial", "Helvetica", "DejaVu Sans"],
    "pdf.fonttype": 42,
    "svg.fonttype": "none",
    "font.size": 7,
    "axes.titlesize": 7,
    "axes.labelsize": 7,
    "xtick.labelsize": 6.5,
    "ytick.labelsize": 6.5,
    "legend.fontsize": 6.5,
    "axes.linewidth": 0.6,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "xtick.major.size": 2.5,
    "ytick.major.size": 2.5,
    "axes.spines.right": False,
    "axes.spines.top": False,
    "legend.frameon": False,
    "mathtext.default": "regular",
})

# One restrained palette for the whole manuscript.
RULE = "#5A5A5A"        # physics-based rule chain (neutral)
RF = "#2F6DA8"          # learned layer
RF_LIGHT = "#A8C3E0"
FLOOR = "#0E7C6B"       # ordinal physical floor (hero)
FLOOR_LIGHT = "#79BDB1"
CONLY = "#8E6BB0"       # C-only floor ablation
DANGER = "#C0392B"      # direct C->A errors only
OVER = "#E8B64C"        # conservative overestimates
UNDER = "#F0A39A"       # one-level underestimates
GRADES = "ABC"
COL_W, DBL_W = 3.5, 7.16  # IEEE column and page widths (inch)


def alignment_gate(fig, name: str, exemptions=(), row_groups=None) -> None:
    path = os.environ.get("NATURE_FIGURE_SCRIPTS")
    if not path:
        return
    sys.path.insert(0, path)
    from audit_panel_alignment import require_matplotlib_panel_alignment  # type: ignore
    qa = HERE / "figure_qa"
    qa.mkdir(exist_ok=True)
    require_matplotlib_panel_alignment(fig, json_out=qa / f"{name}.alignment.json",
                                       tolerance_pt=1.5, gutter_tolerance_pt=1.5, strict=True,
                                       exemptions=list(exemptions), row_groups=row_groups)


def save(fig, name: str, exemptions=(), row_groups=None) -> None:
    fig.canvas.draw()
    alignment_gate(fig, name, exemptions, row_groups)
    fig.savefig(FIG / f"{name}.pdf", bbox_inches="tight", pad_inches=0.02)
    fig.savefig(HERE / "figure_qa" / f"{name}.svg", bbox_inches="tight", pad_inches=0.02)
    fig.savefig(HERE / "figure_qa" / f"{name}.png", dpi=300, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def panel_label(ax, text: str, x: float = -0.02, y: float = 1.02) -> None:
    ax.text(x, y, text, transform=ax.transAxes, fontsize=8, fontweight="bold", ha="right", va="bottom")


def load_records() -> list[dict]:
    with (HERE / "per_record_predictions_875.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def confusion(rows, key) -> np.ndarray:
    cm = np.zeros((3, 3), int)
    for r in rows:
        cm[GRADES.index(r["reference"]), GRADES.index(r[key])] += 1
    return cm


# --------------------------------------------------------------------- Fig. 2
def fig_error_structure(rows, stats) -> None:
    # Explicit geometry: three square matrices and one wider dot plot share top and bottom edges.
    fig_h, h, bottom = 2.0, 1.16, 0.43
    left, gap, gap_d, right = 0.40, 0.25, 1.02, 0.05
    w_d = DBL_W - left - 3 * h - 2 * gap - gap_d - right
    xs = [left + k * (h + gap) for k in range(3)] + [left + 3 * h + 2 * gap + gap_d]
    fig = plt.figure(figsize=(DBL_W, fig_h))
    rect = lambda k, w: [xs[k] / DBL_W, bottom / fig_h, w / DBL_W, h / fig_h]
    titles = [("rule", "Rule chain"), ("rf_threshold", "RF threshold policy"), ("hybrid", "RF + ordinal floor")]
    for k, (key, title) in enumerate(titles):
        ax = fig.add_axes(rect(k, h))
        cm = confusion(rows, key)
        for i in range(3):
            for j in range(3):
                n = cm[i, j]
                if i == j:
                    face = mpl.colors.to_rgba("#D9D9D9", 0.35 + 0.65 * n / 350)
                elif n == 0:
                    face = "white"
                elif j > i:
                    face = OVER
                elif i == 2 and j == 0:
                    face = DANGER
                else:
                    face = UNDER
                ax.add_patch(Rectangle((j, 2 - i), 1, 1, facecolor=face, edgecolor="white", linewidth=1.2))
                txt_col = "white" if (i == 2 and j == 0 and n) else "black"
                ax.text(j + 0.5, 2 - i + 0.5, str(n), ha="center", va="center", fontsize=7,
                        color=txt_col if n else "#9A9A9A", fontweight="bold" if (i != j and n) else "normal")
        ax.set_xlim(0, 3); ax.set_ylim(0, 3)
        ax.set_xticks([0.5, 1.5, 2.5], list(GRADES)); ax.set_yticks([0.5, 1.5, 2.5], list(reversed(GRADES)))
        ax.tick_params(length=0, pad=2)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_xlabel("Decision")
        if k == 0:
            ax.set_ylabel("Reference class")
        m = stats["original_batch"]["rule" if key == "rule" else key]
        ax.set_title(f"{title}\nacc. {m['accuracy']:.3f}, loss {m['safe_loss']}", pad=3)
        panel_label(ax, f"({'abc'[k]})", x=-0.12)

    ax = fig.add_axes(rect(3, w_d))
    modes = [("safe_reference", "Safe reference"), ("overtopping", "Overtopping"), ("seepage", "Seepage"),
             ("slope", "Slope"), ("scour", "Scour"), ("building", "Through-structure"), ("mixed", "Mixed")]
    by_mode = stats["original_batch"]["by_target_mode"]
    series = [("rule", "Rule chain", RULE, "o", 0.24), ("rf_threshold", "RF threshold", RF, "s", 0.0),
              ("hybrid", "RF + ordinal floor", FLOOR, "D", -0.24)]
    for yi, (mode, label) in enumerate(modes):
        y0 = len(modes) - 1 - yi
        for key, _, col, mk, dy in series:
            ax.plot(by_mode[mode][key]["accuracy"], y0 + dy, marker=mk, color=col, markersize=3.6,
                    markeredgewidth=0, linestyle="none", zorder=3)
    b = len(modes) - 1 - 5
    ax.annotate("50 C$\\rightarrow$A", xy=(by_mode["building"]["rf_threshold"]["accuracy"], b),
                xytext=(6, 0), textcoords="offset points", fontsize=6.3, color=DANGER, ha="left", va="center",
                fontweight="bold")
    ax.set_yticks(range(len(modes)), [lab for _, lab in reversed(modes)])
    ax.set_xlim(0.3, 1.03); ax.set_ylim(-0.6, len(modes) - 0.4)
    ax.set_xlabel("Accuracy within target mode (n = 125 each)")
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    handles = [Line2D([], [], marker=mk, color=col, linestyle="none", markersize=3.6, markeredgewidth=0, label=lab)
               for _, lab, col, mk, _ in series]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.0, 0.86), handletextpad=0.2, borderaxespad=0.2,
              labelspacing=0.3)
    ax.set_title("Error location by generator target mode", pad=3)
    panel_label(ax, "(d)", x=-0.36)

    key_handles = [Patch(facecolor=OVER, label="conservative overestimate"),
                   Patch(facecolor=UNDER, label="one-level underestimate (B$\\rightarrow$A, C$\\rightarrow$B)"),
                   Patch(facecolor=DANGER, label="direct underestimate (C$\\rightarrow$A)")]
    fig.legend(handles=key_handles, loc="lower left", bbox_to_anchor=(left / DBL_W - 0.01, -0.01), ncol=3,
               handlelength=1.0, handleheight=0.8, columnspacing=1.2, handletextpad=0.4)
    save(fig, "fig_error_structure", exemptions=[{
        "panels": ["d"], "checks": ["panel-width", "horizontal-gutter"],
        "reason": "panel d is a dot plot whose long category labels sit in a wider gutter; the three confusion matrices are square by design"}],
        row_groups=[["a", "b", "c", "d"]])


# --------------------------------------------------------------------- Fig. 3
def fine_grid(rows) -> list[tuple[float, float, int]]:
    p = np.array([[float(r["p_A"]), float(r["p_B"]), float(r["p_C"])] for r in rows])
    y = np.array([GRADES.index(r["reference"]) for r in rows])
    out = []
    for tc in np.arange(0.01, 1.001, 0.01):
        for tb in np.arange(0.01, 1.001, 0.01):
            pred = np.where(p[:, 2] >= tc, 2, np.where(p[:, 1] >= tb, 1, 0))
            cm = np.zeros((3, 3), int)
            np.add.at(cm, (y, pred), 1)
            f1 = []
            for c in range(3):
                tp = cm[c, c]; fn = cm[c].sum() - tp; fp = cm[:, c].sum() - tp
                rr = tp / (tp + fn) if tp + fn else 0.0; pp = tp / (tp + fp) if tp + fp else 0.0
                f1.append(2 * pp * rr / (pp + rr) if pp + rr else 0.0)
            out.append((float(np.mean(f1)), int(cm[2, 0]), int(cm[0, 1] + cm[0, 2])))
    return out


def fig_tradeoff(rows, stats) -> None:
    grid = fine_grid(rows)
    zero = [g for g in grid if g[1] == 0]
    assert not zero, "a pure-RF threshold pair reached zero C->A; update the manuscript text"
    best = max(grid, key=lambda g: g[0])
    cost = json.loads((REPO / "experiments" / "analysis" / "ml_baseline与多目标" / "cost_sensitive_results.json").read_text(encoding="utf-8"))
    o = stats["original_batch"]

    fig, ax = plt.subplots(figsize=(COL_W, 2.85))
    fig.subplots_adjust(left=0.15, right=0.98, bottom=0.335, top=0.98)
    gx = np.array([g[1] for g in grid]); gy = np.array([g[0] for g in grid])
    ax.scatter(gx, gy, s=2.5, color=RF_LIGHT, linewidths=0, rasterized=True, zorder=1)
    ax.axvspan(-9, 9, color="#E4F2EF", zorder=0, linewidth=0)
    ax.text(11, 0.415, "zero direct C$\\rightarrow$A", color=FLOOR, fontsize=6.3, va="bottom", ha="left")
    cw = [(m["c_to_a"], m["macro_f1"]) for m in cost["models"]]
    ax.plot([c[0] for c in cw], [c[1] for c in cw], color=RF, linewidth=0.7, linestyle=(0, (2, 1.5)), marker="^",
            markersize=3, markeredgewidth=0, zorder=3)
    # Points with zero direct C->A are offset horizontally by up to 4 units so that none is hidden.
    pts = [
        ("Rule chain", -4, o["rule"]["macro_f1"], RULE, "o", RULE),
        ("RF + C-only floor", 4, o["c_only_floor"]["macro_f1"], CONLY, "v", CONLY),
        ("RF + ordinal floor", -4, o["hybrid"]["macro_f1"], FLOOR, "D", FLOOR),
        ("RF majority vote", o["rf_majority"]["c_to_a"], o["rf_majority"]["macro_f1"], "white", "s", RF),
        ("RF threshold (0.35, 0.20)", o["rf_threshold"]["c_to_a"], o["rf_threshold"]["macro_f1"], RF, "s", RF),
        ("Best of 10,000 RF thresholds (0.19, 0.06)", best[1], best[0], RF, "P", RF),
    ]
    handles = []
    for lab, x, yv, face, mk, edge in pts:
        ax.plot(x, yv, marker=mk, markerfacecolor=face, markeredgecolor=edge, markeredgewidth=0.8,
                markersize=4.6, linestyle="none", zorder=4)
        handles.append(Line2D([], [], marker=mk, markerfacecolor=face, markeredgecolor=edge, markeredgewidth=0.8,
                              markersize=4.6, linestyle="none", label=lab))
    handles.append(Line2D([], [], marker="^", color=RF, linestyle=(0, (2, 1.5)), linewidth=0.7, markersize=3,
                          markeredgewidth=0, label="Cost-weighted RF, C weight 1.5 to 6"))
    handles.append(Line2D([], [], marker="o", color=RF_LIGHT, linestyle="none", markersize=2.5, markeredgewidth=0,
                          label="All 0.01-grid RF threshold pairs"))
    fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.01, 0.0), ncol=2, columnspacing=0.8,
               handletextpad=0.3, labelspacing=0.35, fontsize=6.1)
    ax.set_xlim(-9, 300); ax.set_ylim(0.4, 0.95)
    ax.set_xlabel("Direct C$\\rightarrow$A underestimates (of 350 C records)")
    ax.set_ylabel("Macro-F1")
    save(fig, "fig_safety_tradeoff")


# --------------------------------------------------------------------- Fig. 4
def fig_seeds(stats) -> None:
    seeds = stats["additional_seeds"]
    keys = [("rule", "Rule", RULE, "o"), ("rf_threshold", "RF thr.", RF, "s"), ("c_only_floor", "C-only\nfloor", CONLY, "v"),
            ("hybrid", "Ordinal\nfloor", FLOOR, "D"), ("hybrid_review_u050", "Floor +\nreview", FLOOR_LIGHT, "D")]
    rng = np.random.default_rng(7)  # display jitter only; no data are simulated
    jit = rng.uniform(-0.13, 0.13, 5)
    fig = plt.figure(figsize=(DBL_W, 2.0))
    gs = fig.add_gridspec(1, 3, wspace=0.42, left=0.065, right=0.99, bottom=0.25, top=0.95)
    for k, (metric, ylab, lim) in enumerate([("macro_f1", "Macro-F1", (0.76, 0.94)), ("safe_loss", "Safety loss (2 C\u2192A + C\u2192B)", (-6, 125))]):
        ax = fig.add_subplot(gs[0, k])
        for i, (key, lab, col, mk) in enumerate(keys):
            v = np.array([seeds[s][key][metric] for s in sorted(seeds)], float)
            ax.plot(i + jit, v, marker=mk, color=col, markersize=3.2, markeredgewidth=0, linestyle="none", alpha=0.9)
            ax.plot([i - 0.28, i + 0.28], [v.mean()] * 2, color=col, linewidth=1.2)
        ax.set_xticks(range(len(keys)), [lab for _, lab, _, _ in keys])
        ax.tick_params(axis="x", length=0)
        ax.set_xlim(-0.6, len(keys) - 0.4); ax.set_ylim(*lim)
        ax.set_ylabel(ylab)
        panel_label(ax, f"({'ab'[k]})", x=-0.2)

    ax = fig.add_subplot(gs[0, 2])
    with (REPO / "experiments" / "analysis" / "875多种子稳健性" / "review_budget_sweep.csv").open(encoding="utf-8-sig") as f:
        sweep = list(csv.DictReader(f))
    us = sorted({float(r["review_threshold"]) for r in sweep})
    rr = np.array([[100 * float(r["review_rate"]) for r in sweep if float(r["review_threshold"]) == u] for u in us])
    sl = np.array([[float(r["safe_loss"]) for r in sweep if float(r["review_threshold"]) == u] for u in us])
    ax.add_patch(Rectangle((0, 0), 5, 6, facecolor="#E4F2EF", edgecolor="none", zorder=0))
    ax.annotate("exploratory budget:\nreview \u2264 5%,\nsafety loss \u2264 6", xy=(2.5, 6), xytext=(0.8, 27),
                fontsize=6.0, color=FLOOR, va="bottom",
                arrowprops=dict(arrowstyle="-", color=FLOOR, linewidth=0.5, shrinkA=1, shrinkB=1))
    ax.errorbar(rr.mean(1), sl.mean(1), xerr=rr.std(1, ddof=1), yerr=sl.std(1, ddof=1), color=FLOOR, marker="o",
                markersize=3, linewidth=0.8, elinewidth=0.5, capsize=1.5, zorder=3)
    offsets = {0.5: (19, -5, "left"), 0.6: (6, -5, "left"), 0.7: (6, -4, "left"), 0.9: (0, 7, "right")}
    for u, x, yv in zip(us, rr.mean(1), sl.mean(1)):
        if u in offsets:
            dx, dy, ha = offsets[u]
            ax.annotate(f"u = {u:.2f}", (x, yv), xytext=(dx, dy), textcoords="offset points",
                        fontsize=6.0, ha=ha, color="#333333")
    ax.set_xlim(0, 30); ax.set_ylim(-2, 58)
    ax.set_xlabel("Records routed to review (%)")
    ax.set_ylabel("Safety loss after rule fallback")
    panel_label(ax, "(c)", x=-0.17)
    save(fig, "fig_multiseed_review")


# --------------------------------------------------------------------- Fig. 5
def fig_inspection() -> None:
    audit = REPO / "inspection" / "audit"
    with (audit / "检测标签逐条记录.csv").open(encoding="utf-8-sig") as f:
        labels = list(csv.DictReader(f))
    with (audit / "可疑点复核记录_非空行.csv").open(encoding="utf-8-sig") as f:
        review = {r["文件名"]: r["复核情况说明"] for r in csv.DictReader(f)}
    # Primary cause of each reviewed false positive, coded from the reviewer's note.
    def cause(note: str) -> str:
        if "建筑" in note and "水" not in note:
            return "building edge / shadow"
        if "植被" in note:
            return "vegetation / shadow"
        if "积水" in note or "渐晕" in note:
            return "wet ground / lens edge"
        return "water-land boundary"
    cats = {"water-land boundary": "#4C9BD6", "vegetation / shadow": "#6FAF5A",
            "building edge / shadow": "#9C7A55", "wet ground / lens edge": "#B5A642"}
    field, valid = [], []
    for r in labels:
        conf = float(r["confidence"])
        name = Path(r["file"].replace("\\", "/")).stem + ".jpg"
        if r["group"] == "人工管涌验证":
            valid.append(conf)
        else:
            field.append((conf, cause(review[name])))
    assert len(field) == 9 and len(valid) == 14

    fig, ax = plt.subplots(figsize=(COL_W, 1.75))
    fig.subplots_adjust(left=0.27, right=0.98, bottom=0.24, top=0.80)
    rng = np.random.default_rng(3)  # vertical display jitter only; confidences are the recorded values
    for conf, c in field:
        ax.plot(conf, 1 + rng.uniform(-0.12, 0.12), marker="o", color=cats[c], markersize=4.2, markeredgewidth=0.4,
                markeredgecolor="white", linestyle="none")
    ax.plot(valid, 0 + rng.uniform(-0.12, 0.12, len(valid)), marker="o", color="none", markeredgecolor=RULE,
            markeredgewidth=0.7, markersize=3.8, linestyle="none")
    ax.set_yticks([0, 1], ["Artificial validation\n(14 boxes, 13 images)", "Field candidates\n(9; all reviewed FP)"])
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_ylim(-0.5, 1.5); ax.set_xlim(0.4, 1.0)
    ax.set_xlabel("Detector confidence")
    counts = {c: sum(1 for _, cc in field if cc == c) for c in cats}
    handles = [Line2D([], [], marker="o", color=col, linestyle="none", markersize=4, markeredgewidth=0, label=f"{c} ({counts[c]})")
               for c, col in cats.items()]
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(-0.02, 1.0), ncol=2, handletextpad=0.2,
              labelspacing=0.25, columnspacing=0.9, fontsize=6.0, title="Reviewer-stated cause of the false positive",
              title_fontsize=6.0, alignment="left")
    save(fig, "fig_inspection_status")


# --------------------------------------------------------------------- Fig. 7
LEARNER_STYLE = {  # display name, colour
    "lr": ("LR", "#9A9A9A"), "olr": ("ordinal LR", "#B8A23A"), "svm": ("SVM", "#A0527A"),
    "gbdt": ("GBDT", "#D08C2E"), "rf": ("RF", RF), "rf_rule": ("stacked RF", "#17375E"),
}
SCOPE_STYLE = {"none": ("no floor", RF_LIGHT, "o"), "c_only": ("C-only floor", CONLY, "^"), "ordinal": ("ordinal floor", FLOOR, "D")}


def fig_policy_evaluation() -> None:
    res = json.loads((HERE / "baselines_and_pareto.json").read_text(encoding="utf-8"))
    with (HERE / "policy_cloud_875.csv").open(encoding="utf-8") as f:
        cloud = list(csv.DictReader(f))
    for c in cloud:
        for k in ("macro_f1", "balanced_accuracy", "c_recall", "escalation"):
            c[k] = float(c[k])
        for k in ("safe_loss", "c_to_a", "a_over", "below_rule"):
            c[k] = int(c[k])
        for k in ("on_front", "feasible", "floor_feasible", "on_floor_front"):
            c[k] = c[k] == "True"
    po = res["original"]["pareto"]
    sel_u, sel_f = po["selected_lexicographic"], po["selected_floor_constrained"]
    rule = next(c for c in cloud if c["learner"] == "rule")
    declared = next(c for c in cloud if c["learner"] == "rf" and c["scope"] == "ordinal"
                    and float(c["t_c"]) == 0.35 and float(c["t_b"]) == 0.2)
    stacked_col = LEARNER_STYLE["rf_rule"][1]

    fig = plt.figure(figsize=(DBL_W, 2.55))
    gs = fig.add_gridspec(1, 3, wspace=0.34, left=0.06, right=0.99, bottom=0.36, top=0.95)
    rng = np.random.default_rng(11)  # display jitter only; all plotted values are recorded results

    # (a) whole policy space; stacked RF (rule grade as input) shown separately from learner-only policies
    ax = fig.add_subplot(gs[0, 0])
    groups = [("none", False, RF_LIGHT), ("c_only", False, CONLY), ("ordinal", False, FLOOR), ("none", True, stacked_col)]
    for s, stacked, col in groups:
        pts = [c for c in cloud if c["learner"] != "rule" and c["scope"] == s and (c["learner"] == "rf_rule") == stacked]
        if not stacked and s != "none":
            pts += [c for c in cloud if c["learner"] == "rf_rule" and c["scope"] == s]
        ax.scatter([c["safe_loss"] + rng.uniform(-2, 2) for c in pts], [c["balanced_accuracy"] for c in pts],
                   s=3, color=col, alpha=0.55, linewidths=0, rasterized=True, zorder=2 if stacked else 1)
    ax.plot(rule["safe_loss"], rule["balanced_accuracy"], "s", color=RULE, markersize=4.5,
            markeredgecolor="white", markeredgewidth=0.6, zorder=4)
    ax.annotate("rule chain", (rule["safe_loss"], rule["balanced_accuracy"]), xytext=(150, 0.975),
                fontsize=6.2, color=RULE, va="center",
                arrowprops=dict(arrowstyle="-", color=RULE, linewidth=0.5, shrinkA=1, shrinkB=3))
    ax.text(300, 0.40, "learner-only policies\n(no rule input):\nsafety loss \u2265 100", fontsize=6.2,
            color=RF, ha="center", va="center")
    ax.set_xlim(-12, 420); ax.set_ylim(0.3, 1.03)
    ax.set_xlabel("Safety loss (2 C\u2192A + C\u2192B)")
    ax.set_ylabel("Balanced accuracy")
    panel_label(ax, "(a)", x=-0.17)

    # (b) feasible policies: quality against the conservative-escalation burden
    ax = fig.add_subplot(gs[0, 1])
    feas = [c for c in cloud if c["feasible"] and c["learner"] != "rule" and c["balanced_accuracy"] >= 0.78]
    for n, (lab, col) in LEARNER_STYLE.items():
        for s, (_, _, mk) in SCOPE_STYLE.items():
            pts = [c for c in feas if c["learner"] == n and c["scope"] == s]
            if pts:
                ax.scatter([c["a_over"] for c in pts], [c["balanced_accuracy"] for c in pts], s=7, marker=mk,
                           facecolors="none" if s == "none" else col, edgecolors=col, linewidths=0.5, alpha=0.8, zorder=2)
    marks = [(sel_u, "*", "white", "black", 10, "selected: benchmark\nconstraints only", (32, 0.995)),
             (sel_f, "*", FLOOR, "black", 10, "selected: with physical-\nfloor constraint", (84, 0.975)),
             (declared, "D", "white", FLOOR, 4.5, "RF + ordinal floor,\ndeclared (0.35, 0.20)", (84, 0.935))]
    for c, mk, face, edge, size, txt, xy in marks:
        ax.plot(c["a_over"], c["balanced_accuracy"], marker=mk, markersize=size, markerfacecolor=face,
                markeredgecolor=edge, markeredgewidth=0.8, linestyle="none", zorder=5)
        ax.annotate(txt, (c["a_over"], c["balanced_accuracy"]), xytext=xy, fontsize=6.0, va="center",
                    color=FLOOR if mk == "D" else "black",
                    arrowprops=dict(arrowstyle="-", color="#555555", linewidth=0.5, shrinkA=1, shrinkB=4))
    ax.set_xlim(-8, 130); ax.set_ylim(0.78, 1.015)
    ax.set_xlabel("A-class overestimates (of 350)")
    ax.set_ylabel("Balanced accuracy")
    panel_label(ax, "(b)", x=-0.2)

    # (c) hypervolume by learner and floor scope over the original batch and five seeds
    ax = fig.add_subplot(gs[0, 2])
    batches = [res["original"]] + [res["seeds"][k] for k in sorted(res["seeds"])]
    order = ["lr", "olr", "svm", "gbdt", "rf", "rf_rule"]
    width = 0.26
    for j, (s, (lab, col, _)) in enumerate(SCOPE_STYLE.items()):
        for i, n in enumerate(order):
            v = np.array([b["pareto"]["families"][f"{n}|{s}"]["hypervolume"] for b in batches])
            x = i + (j - 1) * width
            ax.bar(x, v.mean(), width=width * 0.92, color=col, edgecolor="none", zorder=2)
            ax.errorbar(x, v.mean(), yerr=v.std(ddof=1), color="black", linewidth=0.5, capsize=1.2, zorder=3)
    hv_rule = np.array([b["pareto"]["hv_rule_chain"] for b in batches])
    ax.axhline(hv_rule.mean(), color=RULE, linestyle=(0, (3, 2)), linewidth=0.8, zorder=1)
    ticks = {"lr": "LR", "olr": "ordinal\nLR", "svm": "SVM", "gbdt": "GBDT", "rf": "RF", "rf_rule": "stacked\nRF"}
    ax.set_xticks(range(len(order)), [ticks[n] for n in order])
    ax.tick_params(axis="x", length=0, labelsize=6.2)
    ax.set_xlim(-0.55, 5.55); ax.set_ylim(0, 1.03)
    ax.set_ylabel("Hypervolume")
    panel_label(ax, "(c)", x=-0.18)

    scope_handles = [Line2D([], [], marker=mk, color=col, linestyle="none", markersize=4, label=lab)
                     for lab, col, mk in SCOPE_STYLE.values()]
    scope_handles += [Line2D([], [], marker="o", color=stacked_col, linestyle="none", markersize=4, label="stacked RF, no floor (a)"),
                      Line2D([], [], marker="s", color=RULE, linestyle=(0, (3, 2)), linewidth=0.8, markersize=4, label="rule chain")]
    learner_handles = [Line2D([], [], marker="o", color=col, linestyle="none", markersize=4, label=lab)
                       for lab, col in LEARNER_STYLE.values()]
    fig.legend(handles=scope_handles, loc="lower left", bbox_to_anchor=(0.045, 0.065), ncol=5,
                      handletextpad=0.25, columnspacing=1.1, fontsize=6.2, title="Floor scope: marker in (b), colour in (a) and (c)",
                      title_fontsize=6.2, alignment="left")
    fig.legend(handles=learner_handles, loc="lower left", bbox_to_anchor=(0.045, -0.035), ncol=6,
               handletextpad=0.25, columnspacing=1.1, fontsize=6.2, title="Learner: colour in (b)", title_fontsize=6.2,
               alignment="left")
    save(fig, "fig_policy_evaluation")


def main() -> None:
    (HERE / "figure_qa").mkdir(exist_ok=True)
    stats = json.loads((HERE / "paper_statistics.json").read_text(encoding="utf-8"))
    rows = load_records()
    fig_error_structure(rows, stats)
    fig_tradeoff(rows, stats)
    fig_seeds(stats)
    fig_inspection()
    if (HERE / "baselines_and_pareto.json").exists():
        fig_policy_evaluation()


if __name__ == "__main__":
    main()
