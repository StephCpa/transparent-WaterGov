"""Schematic figures of Chapter 5 (Chinese thesis chapter, 2026-10-07).

Draws two method schematics with Chinese labels:
  * fig5_1_decision_chain     transparent evaluation decision chain (Sec. 5.2)
  * fig5_3_evaluation_system  multi-objective policy evaluation system (Sec. 5.6.4)

The schematics contain no measured data; the policy-space count is the configuration
of baselines_and_pareto.py (6 learners x 225 thresholds x 3 floor scopes + rule chain
= 4051).

Chinese glyphs use the Simplified-Chinese face of Noto Serif CJK (stand-in for SimSun),
Latin text Liberation Serif (Times New Roman metrics). Run prepare_cjk_fonts.py first;
CH5_CJK_FONT_DIR overrides its default output folder ~/.cache/ch5_cjk_fonts.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
OUT = REPO / "paper" / "chinese" / "chapters" / "figures_ch5"
OUT.mkdir(parents=True, exist_ok=True)

FONT_DIR = Path(os.environ.get("CH5_CJK_FONT_DIR", Path.home() / ".cache" / "ch5_cjk_fonts"))
for name in ("NotoSerifSC-Regular.ttf", "NotoSerifSC-Bold.ttf"):
    path = FONT_DIR / name
    if not path.exists():
        sys.exit(f"missing {path}; run prepare_cjk_fonts.py (see module docstring)")
    font_manager.fontManager.addfont(str(path))

mpl.rcParams.update({
    "font.family": ["Liberation Serif", "Noto Serif CJK SC"],
    "mathtext.fontset": "custom",
    "mathtext.rm": "Liberation Serif",
    "mathtext.it": "Liberation Serif:italic",
    "mathtext.bf": "Liberation Serif:bold",
    "mathtext.fallback": "stix",
    "axes.unicode_minus": False,
    "pdf.fonttype": 42,
})

EV = "#8A6D3B"
NEUT = "#6B6B6B"
RULE = "#5A5A5A"
RF = "#2F6DA8"
FLOOR = "#0E7C6B"
DANGER = "#C0392B"
W = 6.3          # figure width (in), equals the text width at 100 % in the Word file
FS = 8.4         # body text size (pt)
FT = 8.9         # box title size (pt)


def tint(color: str, a: float = 0.08):
    r, g, b = mpl.colors.to_rgb(color)
    return (1 - a + a * r, 1 - a + a * g, 1 - a + a * b)


class Canvas:
    """Axes in inches with helpers for boxes, arrows and mixed Chinese/math lines."""

    def __init__(self, h: float):
        self.fig = plt.figure(figsize=(W, h))
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, W); self.ax.set_ylim(0, h); self.ax.axis("off")
        self.fig.canvas.draw()
        self.r = self.fig.canvas.get_renderer()

    def _width(self, t) -> float:
        bb = t.get_window_extent(self.r)
        return bb.width / self.fig.dpi

    def line(self, x, y, text, size=FS, ha="left", weight="normal", color="black"):
        """Draw one line; segments between $...$ are mathtext, the rest plain text (CJK fallback)."""
        text = text.replace("→", "$\\rightarrow$").replace("$$", "")
        parts = text.split("$")
        segs = [(p, i % 2 == 1) for i, p in enumerate(parts) if p]
        arts, widths = [], []
        for s, is_math in segs:
            t = self.ax.text(0, y, f"${s}$" if is_math else s, fontsize=size, va="center", ha="left",
                             fontweight=weight, color=color)
            arts.append(t); widths.append(self._width(t))
        total = sum(widths)
        x0 = x - total / 2 if ha == "center" else (x - total if ha == "right" else x)
        for t, w in zip(arts, widths):
            t.set_x(x0); x0 += w
        return total

    def box(self, x, y_top, w, h, color, title, lines, align="left", num=None, lw=0.8, title_size=FT,
            pad=0.07, gap=0.165, fill_alpha=0.08):
        p = FancyBboxPatch((x, y_top - h), w, h, boxstyle="round,pad=0,rounding_size=0.05",
                           facecolor=tint(color, fill_alpha), edgecolor=color, linewidth=lw)
        self.ax.add_patch(p)
        cx = x + w / 2
        y = y_top - pad - 0.085
        if title:
            self.line(cx if align == "center" else x + pad, y, title, size=title_size, weight="bold",
                      ha="center" if align == "center" else "left")
            y -= gap + 0.02
        for ln in lines:
            if ln is None:
                y -= gap * 0.45
                continue
            bold = ln.startswith("**")
            ln = ln.strip("*")
            self.line(cx if align == "center" else x + pad, y, ln, size=FS, weight="bold" if bold else "normal",
                      ha="center" if align == "center" else "left")
            y -= gap
        if num is not None:
            self.ax.add_patch(Circle((x + 0.02, y_top - 0.02), 0.085, facecolor=color, edgecolor="white",
                                     linewidth=0.6, zorder=5))
            self.ax.text(x + 0.02, y_top - 0.022, str(num), fontsize=7.6, color="white", ha="center",
                         va="center", fontweight="bold", zorder=6)
        return p

    def arrow(self, xy0, xy1, color="#555555", lw=0.8, style="-|>", ls="-", conn="arc3", ms=7):
        a = FancyArrowPatch(xy0, xy1, arrowstyle=style, mutation_scale=ms, color=color, linewidth=lw,
                            linestyle=ls, connectionstyle=conn, shrinkA=0, shrinkB=0)
        self.ax.add_patch(a)

    def poly(self, pts, color="#555555", lw=0.8, ls="-", head=True):
        xs, ys = zip(*pts)
        self.ax.plot(xs[:-1], ys[:-1], color=color, linewidth=lw, linestyle=ls, solid_capstyle="butt")
        if head:
            self.arrow(pts[-2], pts[-1], color=color, lw=lw, ls=ls)
        else:
            self.ax.plot(xs[-2:], ys[-2:], color=color, linewidth=lw, linestyle=ls)

    def crop(self, y0: float, y1: float):
        """Show only y0..y1 (inches) without rescaling the drawing."""
        self.fig.set_size_inches(W, y1 - y0)
        self.ax.set_ylim(y0, y1)

    def save(self, name: str):
        self.fig.savefig(OUT / f"{name}.png", dpi=300, bbox_inches="tight", pad_inches=0.03)
        self.fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight", pad_inches=0.03)
        plt.close(self.fig)


# --------------------------------------------------------------------- Fig. 5.1
def fig_decision_chain():
    c = Canvas(3.45)
    # column 1: evidence channels
    c.line(0.70, 3.33, "证据通道", size=FT, weight="bold", ha="center", color=EV)
    ev = [("地质与材料", "地层界面、土性参数"), ("渗流与稳定计算", "$i/i_{cr}$、FoS、浸润线"),
          ("历史与工程台账", "险情记录、指标版本"), ("无人机红外巡检", "候选框、复核记录")]
    tops = [3.17, 2.47, 1.77, 1.07]
    for (t, s), top in zip(ev, tops):
        c.box(0.04, top, 1.32, 0.56, EV, t, [s])
    # column 2: admissibility gate
    c.box(1.58, 3.17, 1.16, 2.66, NEUT, "可采纳性门控",
          ["$a_j=1$ 当且仅当", "空间相交、", "时间有效、", "版本相容", None, "**证据状态", "缺失、不适用、", "候选、已复核、", "可采纳", None,
           "不可采纳值只进", "溯源，不进评分"])
    for top in tops:
        c.arrow((1.36, top - 0.28), (1.58, top - 0.28))
    # column 3: rule chain and random forest
    c.box(2.97, 3.17, 1.38, 0.98, RULE, "物理规则链", ["29项指标 → $R_m$ → $S$", "观测上限 → 硬门控", "输出 $y_{rule}$"])
    c.box(2.97, 1.92, 1.38, 0.98, RF, "随机森林决策层", ["14项特征 → $(p_A,p_B,p_C)$", "阈值 $(\\tau_C,\\tau_B)$", "输出 $\\hat{y}_{RF}$"])
    c.arrow((2.74, 2.68), (2.97, 2.68)); c.arrow((2.74, 1.43), (2.97, 1.43))
    # offline policy evaluation feeding the learned layer
    c.box(2.97, 0.80, 1.38, 0.50, RF, None, ["多目标策略评价（离线）", "冻结策略 $\\pi^*$，见图5.3"], fill_alpha=0.03, lw=0.6)
    c.arrow((3.66, 0.80), (3.66, 0.94), color=RF, ls=(0, (3, 2)))
    # column 4: ordinal physical floor
    c.box(4.57, 2.36, 0.98, 1.24, FLOOR, "序数物理下限", ["$\\hat{y}=\\max(\\hat{y}_{RF},y_{rule})$", None, "可提高风险等级，", "不低于物理等级"], lw=1.3)
    c.poly([(4.35, 2.68), (4.46, 2.68), (4.46, 2.02), (4.57, 2.02)])
    c.poly([(4.35, 1.43), (4.46, 1.43), (4.46, 1.62), (4.57, 1.62)])
    # column 5: review gate and published grade
    c.box(5.70, 3.17, 0.58, 1.10, NEUT, "发布", ["等级", "触发门控", "证据状态", "版本"], align="center")
    c.box(5.70, 1.70, 0.58, 0.98, NEUT, "复核门", ["$\\mathrm{max}_c\\,p_c<u$", "或有候选", "转工程师"], align="center")
    c.poly([(5.55, 1.74), (5.62, 1.74), (5.62, 1.21), (5.70, 1.21)])
    c.arrow((5.99, 1.70), (5.99, 2.07))
    c.ax.text(6.05, 1.88, "已复核", fontsize=7.0, ha="left", va="center", color=NEUT, rotation=90)
    # candidate path: inspection candidates become review tasks, never confirmed events
    c.poly([(0.70, 0.51), (0.70, 0.21), (5.99, 0.21), (5.99, 0.72)], color=DANGER, ls=(0, (3, 2)))
    c.ax.text(3.33, 0.02, "巡检候选 → 复核任务；时间、位置与复核状态闭合前不作为确认事件进入等级",
              fontsize=7.6, color=DANGER, ha="center", va="bottom")
    c.save("fig5_1_decision_chain")


# --------------------------------------------------------------------- Fig. 5.3
def fig_evaluation_system():
    c = Canvas(3.32)
    top1, h1 = 3.24, 1.16
    c.box(0.04, top1, 2.08, h1, RF, "候选策略空间 Π",
          ["学习器 ℓ：RF、LR、序数LR、", "SVM、GBDT、堆叠RF", "阈值 $(\\tau_C,\\tau_B)$：15×15网格", "下限范围 φ：无、C-only、序数",
           "每批 6×225×3+1 = 4051 个策略"], num=1)
    c.box(2.33, top1, 1.52, h1, NEUT, "分组样本外评价",
          ["按特征向量分组五折，", "各策略共用同一折", "与随机种子，超参数", "固定 → 每个策略", "一个混淆矩阵"], num=2)
    c.box(4.06, top1, 2.22, h1, FLOOR, "目标向量 F(π)（参与支配）",
          ["宏平均F1↑、平衡准确率↑、", "C类召回率↑、安全损失 $L_{safe}$↓", None, "**资源坐标 R(π)（不参与支配）", "升级率、A类高估数、复核率"], num=3)
    c.arrow((2.12, top1 - h1 / 2), (2.33, top1 - h1 / 2)); c.arrow((3.85, top1 - h1 / 2), (4.06, top1 - h1 / 2))
    top2, h2 = 1.80, 1.28
    c.box(0.04, top2, 1.44, h2, DANGER, "硬约束（事先声明）",
          ["N(C→A) = 0", "C类召回率 ≥ 0.95", None, "物理下限约束：", "每个单元 $\\hat{y}\\geq y_{rule}$"], num=4)
    c.box(1.62, top2, 1.40, h2, FLOOR, "严格帕累托筛选",
          ["可行集内对 F 非支配", "计算各策略族超体积", "记录每个策略的", "淘汰原因"], num=5)
    c.box(3.16, top2, 1.58, h2, FLOOR, "声明的词典序选择",
          ["1. 安全损失最小", "2. 平衡准确率最大", "3. 宏平均F1最大", "4. 升级率最小", "5. A类高估最少", "校核：到理想点距离"], num=6)
    c.box(4.88, top2, 1.40, h2, NEUT, "运行点与审计记录",
          ["选中策略、前沿、", "淘汰策略及原因、", "超体积；冻结后迁移", "到附加种子检验"], num=7)
    c.poly([(5.17, top1 - h1), (5.17, 1.93), (0.76, 1.93), (0.76, top2)])
    for xa, xb in [(1.48, 1.62), (3.02, 3.16), (4.74, 4.88)]:
        c.arrow((xa, top2 - h2 / 2), (xb, top2 - h2 / 2))
    c.crop(top2 - h2 - 0.04, 3.32)
    c.save("fig5_3_evaluation_system")


def main():
    fig_decision_chain()
    fig_evaluation_system()


if __name__ == "__main__":
    main()
