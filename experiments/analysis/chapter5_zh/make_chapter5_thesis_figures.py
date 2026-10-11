"""Data figures of the thesis-style copy of Chapter 5 (2026-10-11).

Writes to paper/chinese/chapters/figures_ch5_thesis/ (300 dpi PNG and PDF).  Fonts, palette and
saving are shared with make_chapter5_figures.py, imported with CH5_THESIS=1.  Inputs are repository
files only:
  * thesis_analyses.json (thesis_analyses.py): flight sites in relative metres, image temperature
    extremes, forest validation curves and grouped permutation importance;
  * case_analyses.json (case_analyses.py): typical records, K45+500 variants, inspection injection;
  * paper_revision/baselines_and_pareto.json, paper_statistics.json, per_record_predictions_875.csv;
  * 875多种子稳健性/review_budget_sweep.csv;
  * inspection/audit review and label records, and the rendered detector outputs and raw images.
The Chapter 4 gradients of the interval figure are the values printed in Sec. 4.5 of the Chapter 4 draft.

Run from the repository root after thesis_analyses.py and case_analyses.py:
    python3 experiments/analysis/chapter5_zh/make_chapter5_thesis_figures.py
"""

from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

os.environ["CH5_THESIS"] = "1"
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_chapter5_figures as B  # noqa: E402  (fonts, palette, save; OUT = figures_ch5_thesis)

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch, Rectangle  # noqa: E402
from PIL import Image  # noqa: E402

HERE = B.HERE
REPO = B.REPO
TA = json.loads((HERE / "thesis_analyses.json").read_text(encoding="utf-8"))
CA = json.loads((HERE / "case_analyses.json").read_text(encoding="utf-8"))
GBDT, STACK = "#D08C2E", "#17375E"
BAND = {"A": "#E6F2EC", "B": "#FBF1DC", "C": "#F8E1DE"}
GCOL = {"A": B.FLOOR, "B": B.OVER, "C": B.DANGER}
GTXT = {"A": B.FLOOR, "B": "#A67C00", "C": B.DANGER}   # darker B for text on light bands
W = B.FIG_W


def title(ax, label: str, text: str) -> None:
    """Panel heading in the style of Chapter 4: letter and title at the top left."""
    ax.set_title(f"{label}  {text}", loc="left", fontsize=B.FS_TEXT, pad=4)


# ---------------------------------------------------------------- survey sites and image temperatures
def fig_survey_sites() -> None:
    sites = {s["site"]: s for s in TA["inspection"]["sites"]}
    fig = plt.figure(figsize=(W, 2.75))
    gs = fig.add_gridspec(1, 3, width_ratios=[0.75, 1.0, 1.2], wspace=0.38, left=0.085, right=0.99, bottom=0.3, top=0.9)
    for k, key in enumerate("AB"):
        s = sites[key]
        ax = fig.add_subplot(gs[0, k])
        pts = s["points"]
        x = np.array([p["x_m"] for p in pts]); y = np.array([p["y_m"] for p in pts])
        order = np.arange(len(pts))
        ax.plot(x, y, color="#C8C8C8", linewidth=0.5, zorder=1)
        ax.scatter(x, y, c=order, cmap="Blues", vmin=-0.3 * len(pts), s=9, edgecolors="none", zorder=2)
        ax.scatter(x[:1], y[:1], marker="^", s=26, color=B.EV if hasattr(B, "EV") else "#8A6D3B", zorder=4)
        cand = np.array([p["reviewed_candidate"] for p in pts])
        ax.scatter(x[cand], y[cand], marker="x", color=B.DANGER, s=22, linewidths=1.0, zorder=3)
        ax.set_aspect("equal", adjustable="datalim")
        ax.set_xlabel("相对东向距离/m")
        if k == 0:
            ax.set_ylabel("相对北向距离/m")
        title(ax, "ab"[k], f"片区{key}（{s['start']}—{s['end']}）")
    ax = fig.add_subplot(gs[0, 2])
    pts = [p for s in TA["inspection"]["sites"] for p in s["points"] if p["t_max"] is not None]
    hh = np.array([int(p["time"][:2]) + int(p["time"][3:5]) / 60 + int(p["time"][6:8]) / 3600 for p in pts])
    tmax = np.array([p["t_max"] for p in pts]); tmin = np.array([p["t_min"] for p in pts])
    ax.vlines(hh, tmin, tmax, color="#D0D0D0", linewidth=0.5)
    ax.scatter(hh, tmax, s=8, color=B.DANGER, zorder=3)
    ax.scatter(hh, tmin, s=8, color=B.RF, zorder=3)
    ax.set_xlabel("采集时刻/h"); ax.set_ylabel("温度/℃")
    ax.set_xlim(9.4, 15.4); ax.set_xticks([10, 11, 12, 13, 14, 15])
    title(ax, "c", "单张图像温度极值")
    handles = [Line2D([], [], marker="^", color="#8A6D3B", linestyle="none", markersize=5),
               Line2D([], [], marker="o", color="#5B8DC3", linestyle="none", markersize=4),
               Line2D([], [], marker="x", color=B.DANGER, linestyle="none", markersize=5),
               Line2D([], [], marker="o", color=B.DANGER, linestyle="none", markersize=4),
               Line2D([], [], marker="o", color=B.RF, linestyle="none", markersize=4)]
    labels = ["首张图像机位", "机位（颜色由浅至深为采集先后）", "经复核的算法候选（均为误报）", "图像最高温度", "图像最低温度"]
    fig.legend(handles, labels, loc="lower center", ncol=3, bbox_to_anchor=(0.52, -0.01), fontsize=B.FS_LEG,
               handletextpad=0.3, columnspacing=1.2)
    B.save(fig, "fig5_survey_sites")


# ---------------------------------------------------------------- detector outputs and raw images
def fig_detection_examples() -> None:
    base = REPO / "inspection" / "raw" / "第一批优先资料"
    det = base / "02_检测框与置信度输出"
    panels = [
        (det / "01_levee_infrared_images检测结果" / "detections" / "DJI_20250828104036_0004_T.jpg", "a  现场候选：水体边缘（0.78，误报）"),
        (det / "01_levee_infrared_images检测结果" / "detections" / "DJI_20250828110128_0023_T.jpg", "b  现场候选：植被及阴影（0.77，误报）"),
        (det / "01_levee_infrared_images检测结果" / "detections" / "DJI_20250828095151_0051_T.jpg", "c  现场候选：建筑边缘（0.57，误报）"),
        (det / "02_人造管涌渗漏点红外图像（验证）检测结果" / "detections" / "207_P_HH230530_P_C_T_10_A_P_0_V2W1_03.jpg", "d  人工管涌验证图（0.93）"),
        (det / "02_人造管涌渗漏点红外图像（验证）检测结果" / "detections" / "P_AH230620_A_S_T_10_B_P_0_D1_04.jpg", "e  人工管涌验证图（0.86）"),
        (base / "01_原始图像及视频" / "01_levee_infrared_images" / "DJI_20250828094102_0001_T.JPG", "f  现场原图（未检出候选）"),
    ]
    fig, axes = plt.subplots(2, 3, figsize=(W, 4.05))
    for ax, (path, cap) in zip(axes.ravel(), panels):
        im = Image.open(path).convert("RGB")
        if im.size == (640, 640):                      # crop the square validation images to 5:4 like the field frames
            im = im.crop((0, 64, 640, 576))
        ax.imshow(np.asarray(im)); ax.set_axis_off()
        ax.set_title(cap, loc="left", fontsize=B.FS_LEG, pad=3)
    fig.subplots_adjust(left=0.005, right=0.995, top=0.95, bottom=0.01, wspace=0.04, hspace=0.16)
    B.save(fig, "fig5_detection_examples")


# ---------------------------------------------------------------- forest tuning and importance
def fig_rf_tuning() -> None:
    tun, imp = TA["rf_tuning"], TA["rf_importance"]
    fig = plt.figure(figsize=(W, 4.45))
    gs = fig.add_gridspec(2, 3, height_ratios=[1, 1.05], hspace=0.62, wspace=0.38, left=0.09, right=0.99, bottom=0.08, top=0.86)
    spec = [("n_estimators", "决策树数量", 120), ("max_depth", "最大深度", 7), ("max_features", "分裂候选特征数", 4)]
    for k, (key, lab, chosen) in enumerate(spec):
        ax = fig.add_subplot(gs[0, k])
        rows = tun[key]
        v = [r["value"] for r in rows]
        ax.plot(v, [r["train_macro_f1"] for r in rows], marker="o", markersize=2.8, color=B.RULE, linewidth=1.0, label="训练折")
        ax.plot(v, [r["oof_macro_f1"] for r in rows], marker="s", markersize=2.8, color=B.RF, linewidth=1.0, label="样本外（多数投票）")
        ax.plot(v, [r["oof_macro_f1_threshold"] for r in rows], marker="D", markersize=2.6, color=B.FLOOR, linewidth=1.0,
                linestyle="--", label="样本外（阈值策略）")
        ax.axvline(chosen, color="#999999", linewidth=0.6, linestyle=":")
        ax.set_xlabel(lab); ax.set_ylim(0.4, 0.95)
        if k == 0:
            ax.set_ylabel("宏平均F1")
        title(ax, "abc"[k], f"{lab}（取{chosen}）")
    h, l = fig.axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper center", ncol=3, bbox_to_anchor=(0.54, 1.01), fontsize=B.FS_LEG)
    ax = fig.add_subplot(gs[1, :])
    g = sorted(imp["groups"], key=lambda r: r["d_macro_f1_mean"])
    yy = np.arange(len(g))
    ax.barh(yy, [r["d_macro_f1_mean"] for r in g], xerr=[r["d_macro_f1_sd"] for r in g], color=B.RF_LIGHT,
            edgecolor=B.RF, linewidth=0.5, error_kw=dict(elinewidth=0.6, capsize=1.5))
    ax.set_yticks(yy, [r["group"] for r in g]); ax.axvline(0, color="#777777", linewidth=0.5)
    ax.set_xlabel(f"置换后宏平均F1下降量（{imp['repeats']}次重复，均值±标准差）")
    title(ax, "d", "分组置换特征重要性")
    B.save(fig, "fig5_rf_tuning")


# ---------------------------------------------------------------- method comparison (Table 5-12 as a chart)
def method_rows() -> list[dict]:
    b = json.loads((B.SRC / "baselines_and_pareto.json").read_text(encoding="utf-8"))["original"]["baselines"]
    st = json.loads((B.SRC / "paper_statistics.json").read_text(encoding="utf-8"))["original_batch"]
    recs = B.load_records()
    o = {g: i for i, g in enumerate("ABC")}
    co = st["c_only_floor"]
    co = dict(co, below_rule=sum(o[r["c_only_floor"]] < o[r["rule"]] for r in recs),
              new_errors=sum(r["rule"] == r["reference"] and r["c_only_floor"] != r["reference"] for r in recs),
              a_over=co["a_overestimate"])
    spec = [("规则链", b["rule"], B.RULE), ("RF多数投票", b["rf_majority"], B.RF_LIGHT), ("RF阈值", b["rf_threshold"], B.RF),
            ("GBDT", b["gbdt"], GBDT), ("堆叠RF", b["rf_rule_stacked"], STACK), ("RF+C-only下限", co, B.CONLY),
            ("RF+序数下限", b["rf_threshold+floor"], B.FLOOR), ("GBDT+序数下限", b["gbdt+floor"], B.FLOOR_LIGHT),
            ("堆叠RF+序数下限", b["rf_rule_stacked+floor"], "#0B5A4E")]
    out = []
    for name, m, col in spec:
        out.append({"name": name, "color": col, "acc": m["accuracy"], "f1": m["macro_f1"], "ba": m["balanced_accuracy"],
                    "crec": m["c_recall"], "ca": m["c_to_a"], "cb": m["c_to_b"], "aover": m.get("a_over", m.get("a_overestimate")),
                    "below": m.get("below_rule", 0), "new": m.get("new_errors", 0)})
    assert abs(out[6]["acc"] - 0.926) < 5e-4 and out[2]["ca"] == 50 and out[5]["below"] == 104
    return out


def fig_method_compare() -> None:
    rows = method_rows()
    n = len(rows)
    x = np.arange(n)
    fig = plt.figure(figsize=(W, 4.5))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.1, 1], hspace=0.62, wspace=0.28, left=0.08, right=0.99, bottom=0.12, top=0.88)
    ax = fig.add_subplot(gs[0, :])
    mets = [("acc", "准确率", "#1F4E79"), ("f1", "宏平均F1", "#3F7FBF"), ("ba", "平衡准确率", "#7FB0DD"), ("crec", "C级召回率", "#BCD5EC")]
    wbar = 0.2
    for j, (key, lab, col) in enumerate(mets):
        ax.bar(x + (j - 1.5) * wbar, [r[key] for r in rows], wbar, color=col, edgecolor="#1F4E79", linewidth=0.3, label=lab)
    ax.set_ylim(0.7, 1.1); ax.set_xticks(x, [r["name"].replace("+", "+\n") for r in rows], rotation=0, fontsize=7.2)
    for t, r in zip(ax.get_xticklabels(), rows):
        if "序数" in r["name"]:
            t.set_color(B.FLOOR); t.set_fontweight("bold")
    ax.set_ylabel("指标值"); ax.set_yticks([0.7, 0.8, 0.9, 1.0]); ax.legend(ncol=4, loc="upper left", borderaxespad=0.1)
    title(ax, "a", "判别质量（875条记录，样本外）")
    ax = fig.add_subplot(gs[1, 0])
    ax.bar(x, [2 * r["ca"] for r in rows], color=B.DANGER, width=0.62, label="2×C判A")
    ax.bar(x, [r["cb"] for r in rows], bottom=[2 * r["ca"] for r in rows], color=B.UNDER, width=0.62, label="C判B")
    for xi, r in zip(x, rows):
        ax.text(xi, 2 * r["ca"] + r["cb"] + 2, str(2 * r["ca"] + r["cb"]), ha="center", fontsize=6.8)
    ax.set_xticks(x, [str(i + 1) for i in x]); ax.set_ylabel("安全损失"); ax.set_ylim(0, 125)
    ax.legend(loc="upper right")
    title(ax, "b", "安全损失")
    ax = fig.add_subplot(gs[1, 1])
    ax.bar(x - 0.2, [r["below"] for r in rows], 0.38, color="#A8A8A8", label="调低规则等级")
    ax.bar(x + 0.2, [r["new"] for r in rows], 0.38, color=B.OVER, label="新增错误")
    ax.set_xticks(x, [str(i + 1) for i in x]); ax.set_ylabel("记录数"); ax.set_ylim(0, 195)
    ax.legend(loc="upper right")
    title(ax, "c", "相对规则链的改动")
    fig.text(0.08, 0.015, "b、c横轴序号1—9依次对应a中的9种方法。", fontsize=B.FS_LEG, color="#444444")
    B.save(fig, "fig5_method_compare")


# ---------------------------------------------------------------- additional batches
def fig_multiseed() -> None:
    st = json.loads((B.SRC / "paper_statistics.json").read_text(encoding="utf-8"))
    seeds = st["additional_seeds"]
    keys = [("rule", "规则\n链", B.RULE, "o"), ("rf_threshold", "RF\n阈值", B.RF, "s"), ("c_only_floor", "C-only\n下限", B.CONLY, "v"),
            ("hybrid", "序数\n下限", B.FLOOR, "D"), ("hybrid_review_u050", "序数+\n复核", B.FLOOR_LIGHT, "D")]
    jit = np.linspace(-0.12, 0.12, 5)  # display offsets only
    fig = plt.figure(figsize=(W, 2.35))
    gs = fig.add_gridspec(1, 3, wspace=0.45, left=0.075, right=0.99, bottom=0.25, top=0.88)
    for k, (metric, ylab, lim) in enumerate([("macro_f1", "宏平均F1", (0.76, 0.94)), ("safe_loss", "安全损失", (-6, 125))]):
        ax = fig.add_subplot(gs[0, k])
        for i, (key, lab, col, mk) in enumerate(keys):
            v = np.array([seeds[s][key][metric] for s in sorted(seeds)], float)
            ax.plot(i + jit, v, marker=mk, color=col, markersize=3.2, markeredgewidth=0, linestyle="none")
            ax.plot([i - 0.28, i + 0.28], [v.mean()] * 2, color=col, linewidth=1.2)
        ax.set_xticks(range(len(keys)), [lab for _, lab, _, _ in keys], fontsize=7.2)
        ax.tick_params(axis="x", length=0); ax.set_xlim(-0.6, len(keys) - 0.4); ax.set_ylim(*lim)
        ax.set_ylabel(ylab)
        title(ax, "ab"[k], f"{ylab}（另外5批）")
    ax = fig.add_subplot(gs[0, 2])
    with (REPO / "experiments" / "analysis" / "875多种子稳健性" / "review_budget_sweep.csv").open(encoding="utf-8-sig") as f:
        sweep = list(csv.DictReader(f))
    us = sorted({float(r["review_threshold"]) for r in sweep})
    rr = np.array([[100 * float(r["review_rate"]) for r in sweep if float(r["review_threshold"]) == u] for u in us])
    sl = np.array([[float(r["safe_loss"]) for r in sweep if float(r["review_threshold"]) == u] for u in us])
    ax.errorbar(rr.mean(1), sl.mean(1), xerr=rr.std(1, ddof=1), yerr=sl.std(1, ddof=1), color=B.FLOOR, marker="o",
                markersize=3, linewidth=0.8, elinewidth=0.5, capsize=1.5)
    for u, xv, yv in zip(us, rr.mean(1), sl.mean(1)):
        if u in (0.5, 0.7, 0.9):
            ax.annotate(f"u={u:.1f}", (xv, yv), xytext=(4, 4), textcoords="offset points", fontsize=6.8)
    ax.set_xlim(0, 30); ax.set_ylim(-2, 58)
    ax.set_xlabel("转人工复核的记录比例/%"); ax.set_ylabel("回退规则等级后的安全损失")
    title(ax, "c", "复核门阈值")
    B.save(fig, "fig5_multiseed")


# ---------------------------------------------------------------- typical records step by step
def fig_typical_records() -> None:
    recs = CA["typical_records"]
    names = {("seepage", "severe"): "渗流严重", ("building", "critical"): "穿堤建筑物临界",
             ("safe_reference", "severe"): "安全基准严重", ("seepage", "slight"): "渗流轻微"}
    labels = [f"{names[(r['target_mode'], r['severity'])]}\n（{r['sample_id']}）" for r in recs]
    y = np.arange(len(recs))[::-1]
    fig = plt.figure(figsize=(W, 2.55))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.25, 1.0, 0.95], wspace=0.16, left=0.15, right=0.99, bottom=0.2, top=0.87)
    ax = fig.add_subplot(gs[0, 0])
    for lo, hi, g in [(0, 40, "C"), (40, 80, "B"), (80, 100, "A")]:
        ax.axvspan(lo, hi, color=BAND[g], zorder=0)
        ax.text((lo + hi) / 2, len(recs) - 0.45, f"{g}级", ha="center", fontsize=7.2, color=GTXT[g])
    ax.barh(y, [r["score"] for r in recs], height=0.5, color="#9A9A9A", zorder=2)
    for yi, r in zip(y, recs):
        ax.text(r["score"] + 1.5, yi, f"{r['score']:.2f}", va="center", fontsize=7.2, zorder=3)
    ax.set_yticks(y, labels, fontsize=7.4); ax.set_xlim(0, 100); ax.set_xticks([0, 40, 80]); ax.set_ylim(-0.6, len(recs) - 0.2)
    ax.set_xlabel("综合得分S")
    title(ax, "a", "综合得分与等级区间")
    ax = fig.add_subplot(gs[0, 1])
    left = np.zeros(len(recs))
    for g in "ABC":
        v = np.array([r["rf_probabilities"][g] for r in recs])
        ax.barh(y, v, left=left, height=0.5, color=GCOL[g], alpha=0.85, label=f"$p_{g}$")
        left += v
    ax.axvline(0.35, color="#333333", linewidth=0.6, linestyle="--")
    ax.text(0.36, len(recs) - 0.45, "$τ_C$=0.35", fontsize=7, va="center")
    ax.set_yticks(y, []); ax.set_xlim(0, 1); ax.set_xticks([0, 0.5, 1]); ax.set_ylim(-0.6, len(recs) - 0.2); ax.set_xlabel("随机森林类别概率")
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.27), handlelength=1.0, columnspacing=0.8)
    title(ax, "b", "随机森林概率")
    ax = fig.add_subplot(gs[0, 2])
    cols = [("规则", "rule_grade"), ("学习", "rf_threshold_grade"), ("最终", "ordinal_floor_grade"), ("参考", "reference")]
    for j, (lab, key) in enumerate(cols):
        for yi, r in zip(y, recs):
            g = r[key]
            ax.add_patch(Rectangle((j - 0.4, yi - 0.3), 0.8, 0.6, facecolor=BAND[g], edgecolor=GCOL[g], linewidth=0.8))
            ax.text(j, yi, g, ha="center", va="center", fontsize=8.5, color=GTXT[g], fontweight="bold")
    ax.set_xlim(-0.6, 3.6); ax.set_ylim(-0.6, len(recs) - 0.2)
    ax.set_xticks(range(4), [c[0] for c in cols]); ax.set_yticks(y, [])
    for s in ("left", "bottom"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)
    title(ax, "c", "等级")
    B.save(fig, "fig5_typical_records")


# ---------------------------------------------------------------- K45+500
def fig_k45() -> None:
    v = CA["k45500"]["variants"]
    order = [("delivered", "①交付\n结果"), ("c3_missing", "②C3按\n缺失"), ("c1_exit_zone", "③C1取\n出口区"),
             ("c1_exit_zone_current_evidence_only", "④仅当期\n证据")]
    modes = ["漫顶失效", "渗流破坏", "边坡失稳", "冲刷破坏", "穿堤建筑物失效"]
    fig = plt.figure(figsize=(W, 2.45))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.1, 1.0], wspace=0.32, left=0.08, right=0.99, bottom=0.25, top=0.88)
    ax = fig.add_subplot(gs[0, 0])
    xm = np.arange(len(modes))
    for j, (key, lab, col) in enumerate([("delivered", "①交付结果", B.DANGER), ("c1_exit_zone", "③C1取出口区", B.RF)]):
        ax.bar(xm + (j - 0.5) * 0.36, [v[key]["mode_responses"][m] for m in modes], 0.34, color=col, alpha=0.85, label=lab)
    ax.set_xticks(xm, ["漫顶", "渗流破坏", "边坡失稳", "冲刷", "穿堤建筑物"], fontsize=7.4)
    ax.set_ylim(0, 1.12); ax.set_ylabel("修正后模式响应"); ax.legend(loc="upper right")
    title(ax, "a", "失效模式响应")
    ax = fig.add_subplot(gs[0, 1])
    for lo, hi, g in [(0, 40, "C"), (40, 80, "B"), (80, 100, "A")]:
        ax.axhspan(lo, hi, color=BAND[g], zorder=0)
        ax.text(3.62, (lo + hi) / 2, f"{g}级", va="center", fontsize=7.2, color=GTXT[g])
    xs = np.arange(len(order))
    ax.bar(xs, [v[k]["score"] for k, _ in order], 0.55, color="#8C8C8C", zorder=2)
    for xi, (k, _) in zip(xs, order):
        ax.text(xi, v[k]["score"] + 2, f"{v[k]['score']:.2f}\n最终{v[k]['final_grade']}级", ha="center", fontsize=7, zorder=3)
    ax.set_xticks(xs, [lab for _, lab in order], fontsize=7.2); ax.set_xlim(-0.5, 3.9); ax.set_ylim(0, 100)
    ax.set_ylabel("综合得分S")
    title(ax, "b", "不同证据处理方式")
    B.save(fig, "fig5_k45500")


# ---------------------------------------------------------------- Chapter 4 results as C1 evidence
def fig_ch4_interval() -> None:
    objs = [("断面Ⅰ，29.00 m", 0.4218), ("断面Ⅰ，32.16 m", 1.6436), ("断面Ⅱ，32.16 m", 0.8449), ("三维计算域，32.16 m", 2.3412)]
    fig, ax = plt.subplots(figsize=(W, 1.95))
    fig.subplots_adjust(left=0.2, right=0.98, bottom=0.24, top=0.9)
    for lo, hi, g, lab in [(0, 0.8, "A", "C1不触发门控"), (0.8, 1.0, "B", "不优于B级"), (1.0, 3.0, "C", "C级")]:
        ax.axvspan(lo, hi, color=BAND[g], zorder=0)
        ax.text((lo + min(hi, 1.6)) / 2 if g != "C" else 2.4, len(objs) - 0.35, lab, ha="center", fontsize=7.2, color=GTXT[g])
    for k, (lab, i_up) in enumerate(objs[::-1]):
        lo, hi = i_up / 1.03125, i_up / 0.825
        ax.plot([lo, hi], [k, k], color="#333333", linewidth=2.2, solid_capstyle="butt", zorder=3)
        ax.plot([lo, hi], [k, k], linestyle="none", marker="|", markersize=8, color="#333333", zorder=3)
        ax.text(hi + 0.04, k, f"$i_{{up}}$={i_up:.4f}", va="center", fontsize=7)
    ax.set_yticks(range(len(objs)), [o[0] for o in objs[::-1]], fontsize=7.6)
    ax.set_xlim(0, 3.0); ax.set_ylim(-0.6, len(objs) - 0.1)
    ax.set_xlabel("风险比 R（临界梯度取0.825—1.03125）")
    B.save(fig, "fig5_ch4_interval")


# ---------------------------------------------------------------- inspection candidates fed into the evaluation
def fig_injection() -> None:
    d = CA["inspection_injection"]
    cases = [("无巡检候选", d["without_candidates"]["score"], d["without_candidates"]["C3"], "A"),
             ("原规则：2个未复核\n候选直接计入", d["delivered_rules_with_unreviewed_candidates"]["score"],
              d["delivered_rules_with_unreviewed_candidates"]["C3"], d["delivered_rules_with_unreviewed_candidates"]["grade"]),
             ("本章规则：合并为1个\n候选，复核为误报", d["without_candidates"]["score"], d["without_candidates"]["C3"], "A")]
    fig = plt.figure(figsize=(W, 2.05))
    gs = fig.add_gridspec(1, 2, wspace=0.55, left=0.2, right=0.97, bottom=0.2, top=0.87)
    y = np.arange(len(cases))[::-1]
    for k, (idx, lab) in enumerate([(2, "C3得分"), (1, "综合得分S")]):
        ax = fig.add_subplot(gs[0, k])
        ax.barh(y, [c[idx] for c in cases], height=0.5, color=[GCOL[c[3]] for c in cases], alpha=0.8)
        for yi, c in zip(y, cases):
            txt = f"{c[idx]:.2f}" if idx == 1 else f"{c[idx]:.0f}"
            if idx == 1:
                txt += f"，最终{c[3]}级"
            ax.text(c[idx] + 1, yi, txt, va="center", fontsize=7.2)
        ax.set_yticks(y, [c[0] for c in cases] if k == 0 else [], fontsize=7.4)
        ax.set_xlim(0, 130 if idx == 1 else 115); ax.set_xlabel(lab)
        title(ax, "ab"[k], lab)
    B.save(fig, "fig5_injection")


def main() -> None:
    fig_survey_sites()
    fig_detection_examples()
    fig_rf_tuning()
    fig_method_compare()
    fig_multiseed()
    fig_typical_records()
    fig_k45()
    fig_ch4_interval()
    fig_injection()
    print("wrote thesis figures to", B.OUT)


if __name__ == "__main__":
    main()
