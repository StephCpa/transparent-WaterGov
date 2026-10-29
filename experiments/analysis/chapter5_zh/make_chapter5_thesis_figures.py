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
    IS_ = json.loads((HERE / "inspection_supplement.json").read_text(encoding="utf-8"))
    fig = plt.figure(figsize=(W, 4.6))
    gs = fig.add_gridspec(2, 2, width_ratios=[0.8, 1.0], height_ratios=[1.15, 1], wspace=0.3, hspace=0.55,
                          left=0.09, right=0.99, bottom=0.17, top=0.94)
    for k, key in enumerate("AB"):
        s = sites[key]
        ax = fig.add_subplot(gs[0, k])
        pts = s["points"]
        x = np.array([p["x_m"] for p in pts]); y = np.array([p["y_m"] for p in pts])
        order = np.arange(len(pts))
        ax.plot(x, y, color="#C8C8C8", linewidth=0.5, zorder=1)
        ax.scatter(x, y, c=order, cmap="Blues", vmin=-0.3 * len(pts), s=9, edgecolors="none", zorder=2)
        ax.scatter(x[:1], y[:1], marker="^", s=26, color="#8A6D3B", zorder=4)
        cand = np.array([p["reviewed_candidate"] for p in pts])
        ax.scatter(x[cand], y[cand], marker="x", color=B.DANGER, s=22, linewidths=1.0, zorder=3)
        ax.set_aspect("equal", adjustable="datalim")
        ax.set_xlabel("相对东向距离/m")
        if k == 0:
            ax.set_ylabel("相对北向距离/m")
        title(ax, "ab"[k], f"片区{key}（{s['start']}～{s['end']}）")
    scol = {"A": "#2F6DA8", "B": "#E07B39", "C": "#6AAF5A"}
    def hours(t):
        return int(t[:2]) + int(t[3:5]) / 60 + int(t[6:8]) / 3600
    ax = fig.add_subplot(gs[1, 0])
    for sk in "ABC":
        im = [r for r in IS_["flight"]["images"] if r["site"] == sk]
        ax.scatter([hours(r["time"]) for r in im], [r["rel_alt_m"] for r in im], s=8, color=scol[sk], label=f"片区{sk}", zorder=3)
    for h in (50, 100):
        ax.axhline(h, color="#BBBBBB", linewidth=0.6, linestyle="--", zorder=1)
    ax.set_yscale("log"); ax.set_yticks([10, 20, 50, 100, 200, 300], ["10", "20", "50", "100", "200", "300"])
    ax.set_xlim(9.4, 15.4); ax.set_xticks([10, 11, 12, 13, 14, 15])
    ax.set_xlabel("采集时刻/h"); ax.set_ylabel("相对航高/m")
    ax.legend(loc="upper right", fontsize=7.0, handletextpad=0.2, borderaxespad=0.2)
    title(ax, "c", "相对起飞点的飞行高度")
    ax = fig.add_subplot(gs[1, 1])
    rows = IS_["temperature"]["images"]
    hh = np.array([hours(r["time"]) for r in rows])
    tmax = np.array([r["t_max"] for r in rows]); tmin = np.array([r["t_min"] for r in rows])
    ax.vlines(hh, tmin, tmax, color="#D0D0D0", linewidth=0.5)
    ax.scatter(hh, tmax, s=7, color=B.DANGER, zorder=3)
    ax.scatter(hh, tmin, s=7, color=B.RF, zorder=3)
    ax.set_xlabel("采集时刻/h"); ax.set_ylabel("温度/℃")
    ax.set_xlim(9.4, 15.4); ax.set_xticks([10, 11, 12, 13, 14, 15])
    title(ax, "d", f"单张图像温度极值（{len(rows)}张）")
    handles = [Line2D([], [], marker="^", color="#8A6D3B", linestyle="none", markersize=5),
               Line2D([], [], marker="o", color="#5B8DC3", linestyle="none", markersize=4),
               Line2D([], [], marker="x", color=B.DANGER, linestyle="none", markersize=5),
               Line2D([], [], marker="o", color=B.DANGER, linestyle="none", markersize=4),
               Line2D([], [], marker="o", color=B.RF, linestyle="none", markersize=4)]
    labels = ["首张图像机位", "机位（颜色由浅至深为采集先后）", "经复核的算法候选（均为误报）", "图像最高温度", "图像最低温度"]
    fig.legend(handles, labels, loc="lower center", ncol=3, bbox_to_anchor=(0.52, -0.005), fontsize=B.FS_LEG,
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
    # Sample ids such as "0+326" are serial numbers, not chainages; label them as sample numbers.
    serial = lambda sid: int(sid.split("+")[0]) * 1000 + int(sid.split("+")[1])  # noqa: E731
    labels = [f"{names[(r['target_mode'], r['severity'])]}\n（样本{serial(r['sample_id'])}）" for r in recs]
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
    # Maximum upward exit gradients of the 1028 Chapter 4 (Sec. 4.5.2-4.5.3): 2-D steady sections, 3-D on day 30.
    objs = [("断面Ⅰ，30.00 m", "0.9247"), ("断面Ⅱ，30.00 m", "0.4216"), ("断面Ⅰ，33.89 m", "2.149"),
            ("断面Ⅱ，33.89 m", "1.17"), ("三维计算域，33.89 m", "3.279")]
    fig, ax = plt.subplots(figsize=(W, 2.3))
    fig.subplots_adjust(left=0.2, right=0.98, bottom=0.2, top=0.92)
    for lo, hi, g, lab in [(0, 0.8, "A", "C1不触发门控"), (0.8, 1.0, "B", "不优于B级"), (1.0, 4.8, "C", "C级")]:
        ax.axvspan(lo, hi, color=BAND[g], zorder=0)
    # the B band is only 0.2 wide on this axis, so the bands are named in a legend instead of in place
    keys = [Patch(facecolor=BAND[g], edgecolor=GCOL[g], linewidth=0.6, label=lab)
            for g, lab in (("A", "C1不触发门控"), ("B", "不优于B级"), ("C", "C级"))]
    ax.legend(handles=keys, loc="upper right", ncol=3, fontsize=7, handlelength=1.2, columnspacing=0.9,
              frameon=True, facecolor="white", edgecolor="none", framealpha=0.9)
    for k, (lab, text) in enumerate(objs[::-1]):
        i_up = float(text)
        lo, hi = i_up / 1.03125, i_up / 0.825
        ax.plot([lo, hi], [k, k], color="#333333", linewidth=2.2, solid_capstyle="butt", zorder=3)
        ax.plot([lo, hi], [k, k], linestyle="none", marker="|", markersize=8, color="#333333", zorder=3)
        ax.text(hi + 0.05, k, f"$i_{{up}}$={text}", va="center", fontsize=7)
    ax.set_yticks(range(len(objs)), [o[0] for o in objs[::-1]], fontsize=7.6)
    ax.set_xlim(0, 4.8); ax.set_ylim(-0.6, len(objs) - 0.1)
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


# ---------------------------------------------------------------- reused figures (group paper and mid-term report)
P2ES_PDF = REPO / "notes" / "references" / "基于P2ES-YOLO的堤防红外图像管涌渗漏识别_侯国鑫.pdf"
MIDTERM = REPO / "notes" / "20260418中期报告合稿.docx"
IS = json.loads((HERE / "inspection_supplement.json").read_text(encoding="utf-8"))
SA = json.loads((HERE / "sensitivity_analysis.json").read_text(encoding="utf-8"))
REASON_COL = {"水陆边界": "#4C9BD6", "植被与阴影": "#6AAF5A", "建筑边缘与阴影": "#9C7A55", "潮湿地面或镜头边缘": "#BCA640"}


def pdf_figure(page: int) -> np.ndarray:
    """First embedded image of a page of the P2ES-YOLO paper, soft mask composited on white."""
    import pymupdf
    doc = pymupdf.open(P2ES_PDF)
    xref, smask = doc[page - 1].get_images(full=True)[0][:2]
    pix = pymupdf.Pixmap(doc, xref)
    if pix.colorspace and pix.colorspace.n == 4:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n).astype(float)
    rgb = a[:, :, :3]
    if pix.alpha:
        rgb = rgb * a[:, :, 3:4] / 255 + 255 * (1 - a[:, :, 3:4] / 255)
    if smask:
        m = pymupdf.Pixmap(doc, smask)
        m = np.frombuffer(m.samples, dtype=np.uint8).reshape(m.height, m.width, m.n)[:, :, :1] / 255
        rgb = rgb * m + 255 * (1 - m)
    return rgb.clip(0, 255).astype(np.uint8)


def midterm_image(name: str) -> np.ndarray:
    import io
    import zipfile
    with zipfile.ZipFile(MIDTERM) as z:
        im = Image.open(io.BytesIO(z.read(f"word/media/{name}"))).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255)); bg.alpha_composite(im)
    return np.asarray(bg.convert("RGB"))


def save_raster(arr: np.ndarray, name: str, width: float) -> None:
    h, w = arr.shape[:2]
    fig = plt.figure(figsize=(width, width * h / w))
    ax = fig.add_axes([0, 0, 1, 1]); ax.imshow(arr, interpolation="lanczos"); ax.set_axis_off()
    B.save(fig, name)


def fig_ir_modes() -> None:
    arr = pdf_figure(4)
    w = arr.shape[1] // 4
    caps = ["a  低温异常（植被背景）", "b  低温异常（裸土背景）", "c  高温异常（植被背景）", "d  高温异常（裸土背景）"]
    fig, axes = plt.subplots(1, 4, figsize=(W, 1.85))
    for k, ax in enumerate(axes):
        ax.imshow(arr[:, k * w:(k + 1) * w]); ax.set_axis_off()
        ax.set_title(caps[k], fontsize=B.FS_LEG, pad=3, y=-0.16)
    fig.subplots_adjust(left=0.005, right=0.995, top=0.99, bottom=0.14, wspace=0.04)
    B.save(fig, "fig5_ir_modes")


def fig_devices() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(W, 2.3), gridspec_kw=dict(width_ratios=[831 / 563, 825 / 516]))
    for ax, (name, cap) in zip(axes, [("image236.png", "a  M300 RTK无人机"), ("image237.png", "b  禅思H20T多传感器载荷")]):
        ax.imshow(midterm_image(name)); ax.set_axis_off()
        ax.set_title(cap, fontsize=B.FS_LEG, pad=3, y=-0.13)
    fig.subplots_adjust(left=0.005, right=0.995, top=0.99, bottom=0.1, wspace=0.04)
    B.save(fig, "fig5_devices")


def fig_dataset_examples() -> None:
    arr = pdf_figure(8)
    w = arr.shape[1] // 3
    lab = midterm_image("image244.png")[14:578, 98:660]       # LabelImg canvas only
    panels = [(arr[:, k * w:(k + 1) * w], c) for k, c in enumerate(["a  植被干扰", "b  夜间采集", "c  日间采集"])]
    panels.append((lab, "d  矩形框标注示例"))
    fig, axes = plt.subplots(1, 4, figsize=(W, 1.85))
    for ax, (im, cap) in zip(axes, panels):
        ax.imshow(im, aspect="auto"); ax.set_axis_off()
        ax.set_title(cap, fontsize=B.FS_LEG, pad=3, y=-0.16)
    fig.subplots_adjust(left=0.005, right=0.995, top=0.99, bottom=0.14, wspace=0.04)
    B.save(fig, "fig5_dataset_examples")


def fig_training_curve() -> None:
    save_raster(midterm_image("image252.png"), "fig5_training_curve", 5.6)


def fig_p2es_structure() -> None:
    save_raster(pdf_figure(5), "fig5_p2es_structure", 4.4)


def fig_c2fsimam() -> None:
    save_raster(pdf_figure(7), "fig5_c2fsimam", 4.8)


def fig_p2es_compare() -> None:
    save_raster(pdf_figure(11), "fig5_p2es_compare", 4.5)


P2ES_ABLATION = [  # Table 2 of the P2ES-YOLO paper, % (P, R, mAP@0.5, mAP@0.5:0.95)
    ("YOLOv8n", 94.0, 89.4, 95.7, 66.8), ("+P2", 92.4, 92.4, 96.9, 68.0),
    ("+P2+EIoU", 93.6, 93.0, 96.9, 68.1), ("P2ES-YOLO", 95.1, 93.4, 97.2, 68.5)]
P2ES_COMPARE = [  # Table 3 of the P2ES-YOLO paper, %
    ("YOLOv5n", 83.1, 75.2, 80.6, 42.3), ("YOLOv8n", 94.0, 89.4, 95.7, 66.8), ("YOLOv9-T", 93.8, 87.4, 95.0, 65.2),
    ("YOLOv10n", 90.6, 89.1, 94.8, 66.8), ("YOLOv11n", 86.9, 87.9, 93.9, 63.2), ("P2ES-YOLO", 95.1, 93.4, 97.2, 68.5)]


XLAB = {"+P2+EIoU": "+P2\n+EIoU", "P2ES-YOLO": "P2ES-\nYOLO", "YOLOv5n": "YOLO\nv5n", "YOLOv8n": "YOLO\nv8n",
        "YOLOv9-T": "YOLO\nv9-T", "YOLOv10n": "YOLO\nv10n", "YOLOv11n": "YOLO\nv11n"}


def fig_p2es_results() -> None:
    mets = [("查准率", "#1F4E79"), ("查全率", "#3F7FBF"), ("mAP@0.5", "#7FB0DD"), ("mAP@0.5:0.95", "#BCD5EC")]
    fig, axes = plt.subplots(1, 2, figsize=(W, 2.65), gridspec_kw=dict(width_ratios=[4, 6]))
    for ax, rows, lab, txt, lo in [(axes[0], P2ES_ABLATION, "a", "消融试验（逐模块叠加）", 60), (axes[1], P2ES_COMPARE, "b", "与主流轻量模型对比", 40)]:
        x = np.arange(len(rows)); wb = 0.2
        for j, (m, col) in enumerate(mets):
            v = [r[j + 1] for r in rows]
            ax.bar(x + (j - 1.5) * wb, v, wb, color=col, edgecolor="#1F4E79", linewidth=0.3, label=m)
        ax.set_xticks(x, [XLAB.get(r[0], r[0]) for r in rows], fontsize=7.2)
        ax.get_xticklabels()[-1].set_color(B.FLOOR); ax.get_xticklabels()[-1].set_fontweight("bold")
        ax.set_ylim(lo, 100); ax.set_ylabel("指标值/%")
        title(ax, lab, txt)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=4, bbox_to_anchor=(0.5, -0.01), fontsize=B.FS_LEG)
    fig.subplots_adjust(left=0.08, right=0.99, top=0.9, bottom=0.27, wspace=0.25)
    B.save(fig, "fig5_p2es_results")


def fig_candidates() -> None:
    cand = IS["candidates"]; val = IS["validation"]["boxes"]
    fig = plt.figure(figsize=(W, 2.9))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.0, 1.25, 1.05], wspace=0.42, left=0.075, right=0.99, bottom=0.36, top=0.9)
    ax = fig.add_subplot(gs[0, 0])
    rng = np.random.default_rng(3)
    for c in cand:
        ax.scatter(c["conf"], 1 + rng.uniform(-0.12, 0.12), s=22, color=REASON_COL[c["reason"]], edgecolors="white", linewidths=0.4, zorder=3)
    ax.scatter([b["conf"] for b in val], 0 + rng.uniform(-0.12, 0.12, len(val)), s=20, facecolors="none", edgecolors="#555555", linewidths=0.8)
    ax.set_yticks([0, 1], ["人工管涌\n验证图", "现场\n候选"]); ax.set_ylim(-0.5, 1.5)
    ax.set_xlim(0.4, 1.0); ax.set_xlabel("检测置信度")
    title(ax, "a", "置信度分布")
    ax = fig.add_subplot(gs[0, 1])
    order = sorted(range(len(cand)), key=lambda i: cand[i]["time"])
    y = np.arange(len(order))[::-1]
    for yi, i in zip(y, order):
        c = cand[i]
        ax.barh(yi, c["dT"], color=REASON_COL[c["reason"]], height=0.62)
        ax.text(c["dT"] + (0.3 if c["dT"] >= 0 else -0.3), yi, f"{c['dT']:+.1f}", va="center", ha="left" if c["dT"] >= 0 else "right", fontsize=6.8)
    ax.set_yticks(y, [f"{cand[i]['time']}（{cand[i]['site']}）" for i in order], fontsize=6.6)
    ax.axvline(0, color="#555555", linewidth=0.6); ax.set_xlim(-10, 11)
    ax.set_xlabel("框内外温差ΔT/℃")
    title(ax, "b", "候选框的近似温差")
    ax = fig.add_subplot(gs[0, 2])
    hrs = [int(x["time"][:2]) + int(x["time"][3:5]) / 60 for x in IS["temperature"]["images"]]
    ax.axvspan(0, 6, color="#E3EDF7", zorder=0); ax.axvspan(20, 24, color="#E3EDF7", zorder=0)
    ax.hist(hrs, bins=np.arange(0, 24.5, 1), color="#9A9A9A", edgecolor="white", linewidth=0.4, zorder=2)
    ax.text(3, 72, "夜间", ha="center", color="#2F5F8F", fontsize=7.5)
    ax.set_xlim(0, 24); ax.set_xticks([0, 6, 12, 18, 24]); ax.set_ylim(0, 80)
    ax.set_xlabel("采集时刻/h"); ax.set_ylabel("图像数/张")
    title(ax, "c", "采集时刻分布")
    handles = [Line2D([], [], marker="o", color=REASON_COL[k], linestyle="none", markersize=5) for k in REASON_COL]
    handles.append(Line2D([], [], marker="o", markerfacecolor="none", markeredgecolor="#555555", linestyle="none", markersize=5))
    labels = [f"{k}（{IS['review']['reasons'][k]}个）" for k in REASON_COL] + ["验证图检出框（14个）"]
    fig.legend(handles, labels, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.01), fontsize=B.FS_LEG, columnspacing=1.0)
    B.save(fig, "fig5_candidates")


NAMES = {"C1": "C1 堤基坡降比", "C4": "C4 堤身坡降比", "C5": "C5 接触面坡降比", "D1": "D1 背水坡安全系数",
         "D2": "D2 临水坡安全系数", "B1": "B1 堤顶高程", "D3": "D3 冲刷深度", "C6": "C6 穿堤建筑物渗流",
         "B3": "B3 风浪爬高", "A6": "A6 内部隐患", "A7": "A7 堤基处理", "C2": "C2 排水设施", "A8": "A8 结合部止水",
         "D5": "D5 沉降与裂缝", "B2": "B2 防洪标准", "B4": "B4 建筑物防洪标准", "D4": "D4 穿堤结构", "A4": "A4 护坡",
         "E4": "E4 应急预案", "E1": "E1 监测设施"}


def fig_sensitivity() -> None:
    al = SA["alpha"]; oat = SA["one_at_a_time"]["cases"]
    fig = plt.figure(figsize=(W, 3.0))
    gs = fig.add_gridspec(1, 2, width_ratios=[1, 1.15], wspace=0.62, left=0.085, right=0.985, bottom=0.17, top=0.9)
    ax = fig.add_subplot(gs[0, 0])
    a = [o["alpha"] for o in al]
    ax.plot(a, [o["mean_score"] for o in al], color=B.RULE, marker="o", markersize=2.6, linewidth=1.0, label="平均得分")
    ax.set_xlabel("短板系数α"); ax.set_ylabel("平均得分"); ax.set_ylim(40, 90)
    ax.axvline(0.45, color="#999999", linestyle=":", linewidth=0.7)
    ax2 = ax.twinx()
    ax2.plot(a, [o["final_correct"] / 875 for o in al], color=B.FLOOR, marker="s", markersize=2.6, linewidth=1.0, label="规则等级准确率")
    ax2.plot(a, [o["raw_correct"] / 875 for o in al], color=B.RF, marker="^", markersize=2.6, linewidth=1.0, linestyle="--", label="仅按得分定级的准确率")
    ax2.set_ylim(0.1, 0.92); ax2.set_ylabel("准确率")
    for sp in ("right",):
        ax2.spines[sp].set_visible(True)
    h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="lower left", fontsize=7.0, borderaxespad=0.2)
    title(ax, "a", "短板系数敏感性（875条记录）")
    ax = fig.add_subplot(gs[0, 1])
    top = [c for c in oat if c["range"] >= 0.7][:16][::-1]
    y = np.arange(len(top))
    cont = {"C1", "C4", "C5", "D1", "D2", "B1", "D3"}
    ax.barh(y, [c["range"] for c in top], color=[B.RF if c["code"] in cont else B.RF_LIGHT for c in top],
            edgecolor=B.RF, linewidth=0.4, height=0.66)
    for yi, c in zip(y, top):
        ax.text(c["range"] + 0.8, yi, f"{c['range']:.1f}", va="center", fontsize=6.6)
    ax.set_yticks(y, [NAMES.get(c["code"], c["code"]) for c in top], fontsize=6.8)
    ax.set_xlim(0, 78); ax.set_xlabel("得分变化幅度")
    title(ax, "b", "单指标敏感性")
    handles = [Patch(color=B.RF), Patch(color=B.RF_LIGHT)]
    ax.legend(handles, ["物理量连续变化", "分档取100分与0分"], loc="lower right", fontsize=7.0)
    B.save(fig, "fig5_sensitivity")


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
    fig_ir_modes()
    fig_devices()
    fig_dataset_examples()
    fig_training_curve()
    fig_p2es_structure()
    fig_c2fsimam()
    fig_p2es_results()
    fig_candidates()
    fig_sensitivity()
    print("wrote thesis figures to", B.OUT)


if __name__ == "__main__":
    main()
