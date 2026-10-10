"""Chinese data figures for Chapter 5 of the thesis (levee seepage transparent evaluation).

This script is a Chinese-typeset adaptation of
experiments/analysis/paper_revision/make_paper_figures.py (functions
fig_error_structure, fig_tradeoff, fig_inspection and fig_policy_evaluation).
The data logic and assertions are copied unchanged, so every plotted number is
identical to the English manuscript figures; only wording, fonts, sizes and
layout differ.  One panel is new: the acquisition time of day of the 114 field
infrared images (Fig. 5.4b), parsed from the image file names.

Inputs (repository files only):
  * experiments/analysis/paper_revision/paper_statistics.json,
    per_record_predictions_875.csv, baselines_and_pareto.json,
    policy_cloud_875.csv;
  * experiments/analysis/ml_baseline与多目标/cost_sensitive_results.json;
  * inspection/audit/检测标签逐条记录.csv and 可疑点复核记录_非空行.csv;
  * inspection/raw/第一批优先资料/01_原始图像及视频/01_levee_infrared_images/ (file names only).

Outputs: paper/chinese/chapters/figures_ch5/fig5_4_* and the supplementary
fig5_supp_{error_structure,safety_tradeoff,policy_evaluation} (300 dpi .png and .pdf).

Typography: Chinese glyphs in Noto Serif CJK SC (stand-in for SimSun), Latin
letters and digits in Liberation Serif (Times New Roman metrics), via
matplotlib's per-glyph font fallback.  The Simplified-Chinese faces must be
available as standalone font files in $CH5_CJK_FONT_DIR (NotoSerifSC-Regular and
NotoSerifSC-Bold, .ttf preferred, .otf accepted); the system .ttc collections
expose the JP face first.

Run from the repository root:  python3 experiments/analysis/chapter5_zh/make_chapter5_figures.py
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
import warnings
from collections import Counter
from pathlib import Path

import matplotlib as mpl
mpl.use("Agg")
from matplotlib import font_manager
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SRC = REPO / "experiments" / "analysis" / "paper_revision"
OUT = REPO / "paper" / "chinese" / "chapters" / "figures_ch5"
IR_DIR = REPO / "inspection" / "raw" / "第一批优先资料" / "01_原始图像及视频" / "01_levee_infrared_images"

# ------------------------------------------------------------------ fonts
_DEFAULT_FONT_DIR = str(Path.home() / ".cache" / "ch5_cjk_fonts")  # filled by prepare_cjk_fonts.py
FONT_DIR = Path(os.environ.get("CH5_CJK_FONT_DIR", _DEFAULT_FONT_DIR))
CJK_FAMILY, LATIN_FAMILY = "Noto Serif CJK SC", "Liberation Serif"


def register_fonts() -> None:
    """Register the Simplified-Chinese Noto Serif faces from FONT_DIR.

    TrueType-outline copies (NotoSerifSC-*.ttf, made from the .otf files with fontTools cu2qu) are preferred:
    with pdf.fonttype 42 matplotlib embeds fonts as CIDFontType2/FontFile2, which is only valid for glyf
    outlines; the CFF-based .otf files still render but strict PDF readers flag the embedded font.
    """
    picked = []
    for style in ("Regular", "Bold"):
        cands = [FONT_DIR / f"NotoSerifSC-{style}.{ext}" for ext in ("ttf", "otf")]
        hit = next((p for p in cands if p.is_file()), None)
        if hit is None:
            sys.exit(f"Chinese font file not found: {cands[0]} or {cands[1]}\n"
                     "Set CH5_CJK_FONT_DIR to a folder holding the Simplified-Chinese Noto Serif CJK faces "
                     "(NotoSerifSC-Regular/Bold as .ttf or .otf); run prepare_cjk_fonts.py first.")
        if hit.suffix == ".otf":
            print(f"note: using CFF font {hit.name}; PDF readers may report a font-type mismatch", file=sys.stderr)
        font_manager.fontManager.addfont(str(hit))
        picked.append(hit)
    cjk = font_manager.findfont(font_manager.FontProperties(family=CJK_FAMILY), fallback_to_default=False)
    cjk_b = font_manager.findfont(font_manager.FontProperties(family=CJK_FAMILY, weight="bold"), fallback_to_default=False)
    latin = font_manager.findfont(font_manager.FontProperties(family=LATIN_FAMILY), fallback_to_default=False)
    if [Path(cjk).resolve(), Path(cjk_b).resolve()] != [p.resolve() for p in picked]:
        sys.exit(f"{CJK_FAMILY} resolved to {cjk} / {cjk_b}, not to {picked}")
    if "LiberationSerif" not in Path(latin).name:
        sys.exit(f"{LATIN_FAMILY} resolved to {latin}")


register_fonts()
# A missing glyph must stop the build instead of producing tofu boxes.
warnings.filterwarnings("error", message=r".*[Gg]lyph.*missing.*")

FS_TEXT, FS_TICK, FS_LEG, FS_PANEL = 9, 8.5, 8, 9.5
mpl.rcParams.update({
    "font.family": [LATIN_FAMILY, CJK_FAMILY],
    "axes.unicode_minus": False,
    "mathtext.fontset": "stix",
    "pdf.fonttype": 42,
    "svg.fonttype": "none",
    "font.size": FS_TEXT,
    "axes.titlesize": FS_TEXT,
    "axes.labelsize": FS_TEXT,
    "xtick.labelsize": FS_TICK,
    "ytick.labelsize": FS_TICK,
    "legend.fontsize": FS_LEG,
    "legend.title_fontsize": FS_LEG,
    "axes.linewidth": 0.6,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "xtick.major.size": 2.5,
    "ytick.major.size": 2.5,
    "axes.spines.right": False,
    "axes.spines.top": False,
    "legend.frameon": False,
})

# Palette copied from the English manuscript script.
RULE = "#5A5A5A"        # physics-based rule chain (neutral)
RF = "#2F6DA8"          # learned layer
RF_LIGHT = "#A8C3E0"
FLOOR = "#0E7C6B"       # ordinal physical floor (hero)
FLOOR_LIGHT = "#79BDB1"
CONLY = "#8E6BB0"       # C-only floor ablation
DANGER = "#C0392B"      # direct C->A errors only
OVER = "#E8B64C"        # conservative overestimates
UNDER = "#F0A39A"       # one-level underestimates
NIGHT = "#E3EEF8"       # night-time band (Fig. 5.4b)
BAR = "#9A9A9A"         # neutral histogram bars
GRADES = "ABC"
FIG_W = 6.3             # 16 cm text width


def save(fig, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.png", dpi=300, bbox_inches="tight", pad_inches=0.03)
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


def panel_label(fig, ax, text: str, x_in: float, top_in: float) -> None:
    """Bold panel label; x_in is the left edge and top_in the top edge, both in inches from the figure origin."""
    w, h = fig.get_size_inches()
    fig.text(x_in / w, top_in / h, text, fontsize=FS_PANEL, fontweight="bold", ha="left", va="top")


def load_records() -> list[dict]:
    with (SRC / "per_record_predictions_875.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def confusion(rows, key) -> np.ndarray:
    cm = np.zeros((3, 3), int)
    for r in rows:
        cm[GRADES.index(r["reference"]), GRADES.index(r[key])] += 1
    return cm


# ------------------------------------------------------------- supplementary (not in the chapter; backs Sec. 5.7.2 and Table 5.12)
def fig_error_structure(rows, stats) -> None:
    # Explicit geometry (inches): three square matrices and one dot plot share top and bottom edges.
    fig_h, h, bottom = 2.6, 1.10, 0.62
    left, gap, gap_d, right = 0.43, 0.17, 0.82, 0.04
    w_d = FIG_W - left - 3 * h - 2 * gap - gap_d - right
    xs = [left + k * (h + gap) for k in range(3)] + [left + 3 * h + 2 * gap + gap_d]
    fig = plt.figure(figsize=(FIG_W, fig_h))
    rect = lambda k, w: [xs[k] / FIG_W, bottom / fig_h, w / FIG_W, h / fig_h]
    top_label = bottom + h + 0.56
    titles = [("rule", "规则链"), ("rf_threshold", "RF阈值策略"), ("hybrid", "RF+序数物理下限")]
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
                ax.text(j + 0.5, 2 - i + 0.5, str(n), ha="center", va="center", fontsize=FS_TEXT,
                        color=txt_col if n else "#9A9A9A", fontweight="bold" if (i != j and n) else "normal")
        ax.set_xlim(0, 3); ax.set_ylim(0, 3)
        ax.set_xticks([0.5, 1.5, 2.5], list(GRADES)); ax.set_yticks([0.5, 1.5, 2.5], list(reversed(GRADES)))
        ax.tick_params(length=0, pad=2)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_xlabel("决策等级", labelpad=2)
        if k == 0:
            ax.set_ylabel("参考等级", labelpad=3)
        m = stats["original_batch"]["rule" if key == "rule" else key]
        # Accuracy and safety loss on separate lines: on one line the title is wider than the matrix gap.
        ax.set_title(f"{title}\n准确率 {m['accuracy']:.3f}\n安全损失 {m['safe_loss']}", pad=4, linespacing=1.25)
        panel_label(fig, ax, f"({'abc'[k]})", xs[k] - 0.30, top_label)

    ax = fig.add_axes(rect(3, w_d))
    modes = [("safe_reference", "安全基准"), ("overtopping", "漫顶"), ("seepage", "渗流"),
             ("slope", "边坡"), ("scour", "冲刷"), ("building", "穿堤建筑物"), ("mixed", "复合")]
    by_mode = stats["original_batch"]["by_target_mode"]
    series = [("rule", "规则链", RULE, "o", 0.24), ("rf_threshold", "RF阈值策略", RF, "s", 0.0),
              ("hybrid", "RF+序数下限", FLOOR, "D", -0.24)]
    ms = 4.2
    for yi, (mode, label) in enumerate(modes):
        y0 = len(modes) - 1 - yi
        for key, _, col, mk, dy in series:
            ax.plot(by_mode[mode][key]["accuracy"], y0 + dy, marker=mk, color=col, markersize=ms,
                    markeredgewidth=0, linestyle="none", zorder=3)
    b = len(modes) - 1 - 5
    ax.annotate("50条 C→A", xy=(by_mode["building"]["rf_threshold"]["accuracy"], b),
                xytext=(5, 0), textcoords="offset points", fontsize=FS_LEG, color=DANGER, ha="left", va="center",
                fontweight="bold")
    ax.set_yticks(range(len(modes)), [lab for _, lab in reversed(modes)])
    ax.set_xlim(0.3, 1.03); ax.set_ylim(-0.6, len(modes) - 0.4)
    ax.set_xticks([0.4, 0.6, 0.8, 1.0])
    ax.set_xlabel("各目标模式内准确率（每类125条）", labelpad=2)
    d_left = xs[3] - 0.80  # left edge of panel (d) incl. its category labels (inch)
    # The x label is wider than the dot plot: centre it under the whole panel (labels + axes).
    ax.xaxis.set_label_coords(((d_left + xs[3] + w_d) / 2 - xs[3]) / w_d, -0.165)
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", length=2.0, pad=1.0)
    ax.spines["left"].set_visible(False)
    # Title next to the panel label; series legend in two columns between title and plot.
    fig.text((d_left + 0.30) / FIG_W, top_label / fig_h, "错误在生成器目标模式中的位置", ha="left", va="top",
             fontsize=FS_TEXT)
    handles = [Line2D([], [], marker=mk, color=col, linestyle="none", markersize=ms, markeredgewidth=0, label=lab)
               for _, lab, col, mk, _ in series]
    handles = [handles[0], handles[2], handles[1]]  # two columns filled row by row
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=((d_left + 0.25) / FIG_W, (top_label - 0.19) / fig_h),
               ncol=2, handletextpad=0.15, borderaxespad=0.0, labelspacing=0.3, handlelength=1.2, columnspacing=1.0)
    panel_label(fig, ax, "(d)", d_left, top_label)

    key_handles = [Patch(facecolor=OVER, label="保守高估"),
                   Patch(facecolor=UNDER, label="一级低估（B→A、C→B）"),
                   Patch(facecolor=DANGER, label="直接低估（C→A）")]
    fig.legend(handles=key_handles, loc="lower left", bbox_to_anchor=(0.05 / FIG_W, 0.0), ncol=3,
               handlelength=1.1, handleheight=0.8, columnspacing=1.4, handletextpad=0.4, borderaxespad=0.1)
    save(fig, "fig5_supp_error_structure")


# ------------------------------------------------------------- supplementary (not in the chapter; its assertion backs Sec. 5.7.2)
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

    fig_h = 3.0
    fig, ax = plt.subplots(figsize=(FIG_W, fig_h))
    fig.subplots_adjust(left=0.50 / FIG_W, right=4.02 / FIG_W, bottom=0.45 / fig_h, top=1 - 0.06 / fig_h)
    gx = np.array([g[1] for g in grid]); gy = np.array([g[0] for g in grid])
    ax.scatter(gx, gy, s=3, color=RF_LIGHT, linewidths=0, rasterized=True, zorder=1)
    ax.axvspan(-9, 9, color="#E4F2EF", zorder=0, linewidth=0)
    ax.text(11, 0.415, "零直接C→A", color=FLOOR, fontsize=FS_TEXT, va="bottom", ha="left")
    cw = [(m["c_to_a"], m["macro_f1"]) for m in cost["models"]]
    ax.plot([c[0] for c in cw], [c[1] for c in cw], color=RF, linewidth=0.8, linestyle=(0, (2, 1.5)), marker="^",
            markersize=3.8, markeredgewidth=0, zorder=3)
    # Points with zero direct C->A are offset horizontally by up to 4 units so that none is hidden.
    pts = [
        ("规则链", -4, o["rule"]["macro_f1"], RULE, "o", RULE),
        ("RF+C-only下限", 4, o["c_only_floor"]["macro_f1"], CONLY, "v", CONLY),
        ("RF+序数物理下限", -4, o["hybrid"]["macro_f1"], FLOOR, "D", FLOOR),
        ("RF多数投票", o["rf_majority"]["c_to_a"], o["rf_majority"]["macro_f1"], "white", "s", RF),
        ("RF阈值(0.35, 0.20)", o["rf_threshold"]["c_to_a"], o["rf_threshold"]["macro_f1"], RF, "s", RF),
        ("10 000组RF阈值中宏F1最优(0.19, 0.06)", best[1], best[0], RF, "P", RF),
    ]
    handles = []
    for lab, x, yv, face, mk, edge in pts:
        ax.plot(x, yv, marker=mk, markerfacecolor=face, markeredgecolor=edge, markeredgewidth=0.9,
                markersize=5.5, linestyle="none", zorder=4)
        handles.append(Line2D([], [], marker=mk, markerfacecolor=face, markeredgecolor=edge, markeredgewidth=0.9,
                              markersize=5.5, linestyle="none", label=lab))
    handles.append(Line2D([], [], marker="^", color=RF, linestyle=(0, (2, 1.5)), linewidth=0.8, markersize=3.8,
                          markeredgewidth=0, label="代价加权RF（C类权重1.5～6）"))
    handles.append(Line2D([], [], marker="o", color=RF_LIGHT, linestyle="none", markersize=3, markeredgewidth=0,
                          label="0.01网格全部RF阈值组合"))
    ax.legend(handles=handles, loc="center left", bbox_to_anchor=(1.03, 0.5), ncol=1, handletextpad=0.4,
              labelspacing=0.75, handlelength=1.8, borderaxespad=0.0)
    ax.set_xlim(-9, 300); ax.set_ylim(0.4, 0.95)
    ax.set_xlabel("直接C→A低估数（350条C级记录中）")
    ax.set_ylabel("宏平均F1")
    save(fig, "fig5_supp_safety_tradeoff")


# ------------------------------------------------------------- Fig. 5.4
def ir_acquisition_times() -> list[tuple[str, float]]:
    """(file stem, hour of day) for every image in the field infrared folder.

    Names follow DJI_YYYYMMDDHHMMSS_NNNN_X.JPG; 113 files end in _T and one (DJI_20250828150201_0002_S) in _S.
    """
    pat = re.compile(r"^DJI_(\d{8})(\d{2})(\d{2})(\d{2})_\d{4}_[A-Z]$", re.IGNORECASE)
    out = []
    for p in sorted(IR_DIR.iterdir()):
        if p.suffix.lower() != ".jpg":
            continue
        m = pat.match(p.stem)
        assert m, f"unexpected infrared image name: {p.name}"
        assert m.group(1) == "20250828", p.name
        hh, mm, ss = (int(g) for g in m.group(2, 3, 4))
        out.append((p.stem.upper(), hh + mm / 60 + ss / 3600))
    return out


def fig_inspection() -> None:
    audit = REPO / "inspection" / "audit"
    with (audit / "检测标签逐条记录.csv").open(encoding="utf-8-sig") as f:
        labels = list(csv.DictReader(f))
    with (audit / "可疑点复核记录_非空行.csv").open(encoding="utf-8-sig") as f:
        review = {r["文件名"]: r["复核情况说明"] for r in csv.DictReader(f)}
    # Primary cause of each reviewed false positive, coded from the reviewer's note (same rules as the English figure).
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
    zh = {"water-land boundary": "水陆边界", "vegetation / shadow": "植被/阴影",
          "building edge / shadow": "建筑边缘/阴影", "wet ground / lens edge": "潮湿地面/镜头边缘"}
    field, valid = [], []
    for r in labels:
        conf = float(r["confidence"])
        name = Path(r["file"].replace("\\", "/")).stem + ".jpg"
        if r["group"] == "人工管涌验证":
            valid.append(conf)
        else:
            field.append((conf, cause(review[name])))
    assert len(field) == 9 and len(valid) == 14

    # (b) acquisition time of day of the 114 field infrared images
    times = ir_acquisition_times()
    assert len(times) == 114, len(times)
    per_hour = Counter(int(t) for _, t in times)
    print("Fig. 5.4b images per hour:", ", ".join(f"{h:02d}h: {per_hour[h]}" for h in sorted(per_hour)))
    assert sum(per_hour.values()) == 114
    tmap = dict(times)
    cand = sorted(tmap[Path(n).stem.upper()] for n in review)
    assert len(cand) == 9

    fig_h = 2.35
    fig = plt.figure(figsize=(FIG_W, fig_h))
    bottom, top = 0.42, 1.62
    a_l, a_w, b_l = 1.20, 1.30, 3.02
    b_w, b_top = FIG_W - b_l - 0.19, 2.12  # (b) is as tall as (a) plus its legend
    ax = fig.add_axes([a_l / FIG_W, bottom / fig_h, a_w / FIG_W, (top - bottom) / fig_h])
    rng = np.random.default_rng(3)  # vertical display jitter only; confidences are the recorded values
    for conf, c in field:
        ax.plot(conf, 1 + rng.uniform(-0.12, 0.12), marker="o", color=cats[c], markersize=5, markeredgewidth=0.5,
                markeredgecolor="white", linestyle="none")
    ax.plot(valid, 0 + rng.uniform(-0.12, 0.12, len(valid)), marker="o", color="none", markeredgecolor=RULE,
            markeredgewidth=0.8, markersize=4.6, linestyle="none")
    ax.set_yticks([0, 1], ["人工管涌验证\n（13张图，14个框）", "现场候选\n（9个，复核均为误报）"])
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_ylim(-0.5, 1.5); ax.set_xlim(0.4, 1.0)
    ax.set_xlabel("检测置信度")
    counts = {c: sum(1 for _, cc in field if cc == c) for c in cats}
    handles = [Line2D([], [], marker="o", color=col, linestyle="none", markersize=5, markeredgewidth=0,
                      label=f"{zh[c]} ({counts[c]})") for c, col in cats.items()]
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(-1.06 / a_w, 1.0), ncol=2, handletextpad=0.1,
              labelspacing=0.3, columnspacing=0.9, handlelength=1.2, title="复核意见所述误报原因",
              alignment="left", borderaxespad=0.15)
    panel_label(fig, ax, "(a)", 0.0, fig_h - 0.01)

    ax = fig.add_axes([b_l / FIG_W, bottom / fig_h, b_w / FIG_W, (b_top - bottom) / fig_h])
    for x0, x1 in ((0, 6), (20, 24)):
        ax.axvspan(x0, x1, color=NIGHT, linewidth=0, zorder=0)
    hours = np.arange(24)
    ax.bar(hours, [per_hour.get(h, 0) for h in hours], width=1.0, align="edge", color=BAR,
           edgecolor="white", linewidth=0.6, zorder=2)
    # Reviewed candidates: one marker per image, stacked above the bar of its acquisition hour.  Their exact
    # times (09:51-11:13) lie less than one marker width apart at this scale, so they are binned like the bars.
    step, base = 6.0, 5.5  # in images
    cand_hours = Counter(int(t) for t in cand)
    print("Fig. 5.4b reviewed candidates per hour:", ", ".join(f"{h:02d}h: {n}" for h, n in sorted(cand_hours.items())),
          "| times:", ", ".join(f"{int(t):02d}:{int(round(t % 1 * 3600)) // 60:02d}" for t in cand))
    px = [h + 0.5 for h, n in sorted(cand_hours.items()) for _ in range(n)]
    py = [per_hour[h] + base + k * step for h, n in sorted(cand_hours.items()) for k in range(n)]
    ax.plot(px, py, marker="o", linestyle="none", markersize=3.8,
            markerfacecolor="white", markeredgecolor=DANGER, markeredgewidth=0.9, zorder=4)
    ax.text(3.0, 98, "夜间时段\n（第2章推荐）", ha="center", va="top", fontsize=FS_TEXT, color="#2E5C8A",
            linespacing=1.3)
    ax.text(19.6, 98, "共114张，2025-08-28", ha="right", va="top", fontsize=FS_TEXT, color="#333333")
    ax.text(12.4, 34, "已复核候选点\n（9个）", ha="left", va="center", fontsize=FS_TEXT, color=DANGER,
            linespacing=1.3)
    ax.set_xlim(0, 24); ax.set_ylim(0, 100)
    ax.set_xticks(range(0, 25, 3))
    ax.set_xlabel("采集时刻（h）")
    ax.set_ylabel("图像数（张）")
    panel_label(fig, ax, "(b)", b_l - 0.50, fig_h - 0.01)
    save(fig, "fig5_4_inspection_status")


# ------------------------------------------------------------- supplementary (not in the chapter; its numbers back Sec. 5.7.4)
LEARNER_STYLE = {  # display name, colour
    "lr": ("LR", "#9A9A9A"), "olr": ("序数LR", "#B8A23A"), "svm": ("SVM", "#A0527A"),
    "gbdt": ("GBDT", "#D08C2E"), "rf": ("RF", RF), "rf_rule": ("堆叠RF", "#17375E"),
}
SCOPE_STYLE = {"none": ("无下限", RF_LIGHT, "o"), "c_only": ("C-only下限", CONLY, "^"), "ordinal": ("序数下限", FLOOR, "D")}


def fig_policy_evaluation() -> None:
    res = json.loads((SRC / "baselines_and_pareto.json").read_text(encoding="utf-8"))
    with (SRC / "policy_cloud_875.csv").open(encoding="utf-8") as f:
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

    fig_h = 3.1
    fig = plt.figure(figsize=(FIG_W, fig_h))
    widths, gaps = [1.38, 1.95, 1.50], [0.47, 0.50, 0.45]  # inch; (b) is widest so that its notes fit
    lefts = [sum(gaps[:k + 1]) + sum(widths[:k]) for k in range(3)]
    bottom, top = 1.20, fig_h - 0.08
    axes = [fig.add_axes([l / FIG_W, bottom / fig_h, w / FIG_W, (top - bottom) / fig_h]) for l, w in zip(lefts, widths)]
    rng = np.random.default_rng(11)  # display jitter only; all plotted values are recorded results
    ann = FS_LEG  # in-panel annotations

    # (a) whole policy space; stacked RF (rule grade as input) shown separately from learner-only policies
    ax = axes[0]
    groups = [("none", False, RF_LIGHT), ("c_only", False, CONLY), ("ordinal", False, FLOOR), ("none", True, stacked_col)]
    for s, stacked, col in groups:
        pts = [c for c in cloud if c["learner"] != "rule" and c["scope"] == s and (c["learner"] == "rf_rule") == stacked]
        if not stacked and s != "none":
            pts += [c for c in cloud if c["learner"] == "rf_rule" and c["scope"] == s]
        ax.scatter([c["safe_loss"] + rng.uniform(-2, 2) for c in pts], [c["balanced_accuracy"] for c in pts],
                   s=3.5, color=col, alpha=0.55, linewidths=0, rasterized=True, zorder=2 if stacked else 1)
    ax.plot(rule["safe_loss"], rule["balanced_accuracy"], "s", color=RULE, markersize=5.2,
            markeredgecolor="white", markeredgewidth=0.6, zorder=4)
    ax.annotate("规则链", (rule["safe_loss"], rule["balanced_accuracy"]), xytext=(250, 0.975),
                fontsize=ann, color=RULE, va="center",
                arrowprops=dict(arrowstyle="-", color=RULE, linewidth=0.5, shrinkA=1, shrinkB=3))
    ax.text(418, 0.345, "仅学习器策略\n（无规则输入）：\n安全损失≥100", fontsize=ann,
            color=RF, ha="right", va="center", linespacing=1.25)
    ax.set_xlim(-12, 420); ax.set_ylim(0.25, 1.03)
    ax.set_xlabel("安全损失（2N(C→A)+N(C→B)）")
    ax.set_ylabel("平衡准确率")

    # (b) feasible policies: quality against the conservative-escalation burden
    ax = axes[1]
    feas = [c for c in cloud if c["feasible"] and c["learner"] != "rule" and c["balanced_accuracy"] >= 0.78]
    for n, (lab, col) in LEARNER_STYLE.items():
        for s, (_, _, mk) in SCOPE_STYLE.items():
            pts = [c for c in feas if c["learner"] == n and c["scope"] == s]
            if pts:
                ax.scatter([c["a_over"] for c in pts], [c["balanced_accuracy"] for c in pts], s=9, marker=mk,
                           facecolors="none" if s == "none" else col, edgecolors=col, linewidths=0.55, alpha=0.8, zorder=2)
    # Notes sit in the empty upper and right parts of the panel; relpos is where each leader line leaves its note.
    marks = [(sel_u, "*", "white", "black", 11, "仅基准约束下\n的选择", (14, 1.024), "left", (0.0, 0.5)),
             (sel_f, "*", FLOOR, "black", 11, "加物理下限约束\n后的选择", (129, 0.976), "right", (0.0, 0.3)),
             (declared, "D", "white", FLOOR, 5.2, "声明的\nRF+序数下限\n(0.35, 0.20)", (129, 0.906), "right", (0.0, 1.0))]
    for c, mk, face, edge, size, txt, xy, ha, rel in marks:
        ax.plot(c["a_over"], c["balanced_accuracy"], marker=mk, markersize=size, markerfacecolor=face,
                markeredgecolor=edge, markeredgewidth=0.8, linestyle="none", zorder=5)
        ax.annotate(txt, (c["a_over"], c["balanced_accuracy"]), xytext=xy, fontsize=ann, va="center", ha=ha,
                    color=FLOOR if mk == "D" else "black", linespacing=1.2,
                    arrowprops=dict(arrowstyle="-", color="#555555", linewidth=0.5, shrinkA=1, shrinkB=4, relpos=rel))
    ax.set_xlim(-8, 130); ax.set_ylim(0.78, 1.05)
    ax.set_yticks(np.arange(0.80, 1.001, 0.05))
    ax.set_xlabel("A类高估数（350条中）")
    ax.set_ylabel("平衡准确率")

    # (c) hypervolume by learner and floor scope over the original batch and five seeds
    ax = axes[2]
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
    ax.set_xticks(range(len(order)), [LEARNER_STYLE[n][0] for n in order], rotation=45, ha="right",
                  rotation_mode="anchor")
    ax.tick_params(axis="x", length=0, pad=2)
    ax.set_xlim(-0.55, 5.55); ax.set_ylim(0, 1.03)
    ax.set_ylabel("超体积")

    for k, (ax, l) in enumerate(zip(axes, lefts)):
        panel_label(fig, ax, f"({'abc'[k]})", l - 0.47 if k == 0 else l - 0.46, top + 0.02)

    scope_handles = [Line2D([], [], marker=mk, color=col, linestyle="none", markersize=5, label=lab)
                     for lab, col, mk in SCOPE_STYLE.values()]
    scope_handles += [Line2D([], [], marker="o", color=stacked_col, linestyle="none", markersize=5, label="堆叠RF无下限(a)"),
                      Line2D([], [], marker="s", color=RULE, linestyle=(0, (3, 2)), linewidth=0.8, markersize=5, label="规则链")]
    learner_handles = [Line2D([], [], marker="o", color=col, linestyle="none", markersize=5, label=lab)
                       for lab, col in LEARNER_STYLE.values()]
    fig.legend(handles=scope_handles, loc="lower left", bbox_to_anchor=(0.02 / FIG_W, 0.36 / fig_h), ncol=5,
               handletextpad=0.25, columnspacing=1.3, title="下限范围：(b)中为标记形状，(a)(c)中为颜色",
               alignment="left", borderaxespad=0.0)
    fig.legend(handles=learner_handles, loc="lower left", bbox_to_anchor=(0.02 / FIG_W, 0.0), ncol=6,
               handletextpad=0.25, columnspacing=1.3, title="学习器：(b)中为颜色", alignment="left",
               borderaxespad=0.0)
    save(fig, "fig5_supp_policy_evaluation")


def main() -> None:
    stats = json.loads((SRC / "paper_statistics.json").read_text(encoding="utf-8"))
    rows = load_records()
    fig_error_structure(rows, stats)
    fig_tradeoff(rows, stats)
    fig_inspection()
    fig_policy_evaluation()
    for name in ("fig5_supp_error_structure", "fig5_supp_safety_tradeoff", "fig5_4_inspection_status", "fig5_supp_policy_evaluation"):
        print("wrote", OUT / f"{name}.png", "and .pdf")


if __name__ == "__main__":
    main()
