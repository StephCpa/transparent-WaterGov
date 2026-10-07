"""Schematic figures of Chapter 5 (Chinese thesis chapter, 2026-10-07).

Draws the method schematics with Chinese labels:
  * fig5_1_framework            overall framework of the transparent evaluation (Sec. 5.2)
  * fig5_2_indicator_system     indicator system: target, criterion and indicator layers (Sec. 5.3)
  * fig5_3_inspection_workflow  UAV inspection and recognition workflow (Sec. 5.4)
  * fig5_5_decision_chain       structure of the evaluation model (Sec. 5.5)
  * fig5_6_evaluation_system    multi-objective policy evaluation system (Sec. 5.5)

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
            pad=0.07, gap=0.165, fill_alpha=0.08, vcenter=False):
        p = FancyBboxPatch((x, y_top - h), w, h, boxstyle="round,pad=0,rounding_size=0.05",
                           facecolor=tint(color, fill_alpha), edgecolor=color, linewidth=lw)
        self.ax.add_patch(p)
        cx = x + w / 2
        y = y_top - pad - 0.085
        if vcenter and not title:
            y = y_top - h / 2 + (len(lines) - 1) * gap / 2
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
def fig_framework():
    c = Canvas(4.30)
    ax = c.ax
    layers = [  # (label, top, height, colour)
        ("数据来源", 4.26, 0.52, EV), ("证据层", 3.62, 0.46, NEUT), ("指标层", 3.04, 0.30, RULE),
        ("模型层", 2.62, 0.94, FLOOR), ("标准层", 1.56, 0.30, DANGER), ("输出层", 1.14, 0.50, RF)]
    for lab, top, h, col in layers:
        ax.add_patch(FancyBboxPatch((0.04, top - h), 0.62, h, boxstyle="round,pad=0,rounding_size=0.04",
                                    facecolor=tint(col, 0.22), edgecolor=col, linewidth=0.8))
        c.line(0.35, top - h / 2, lab, size=FT, weight="bold", ha="center", color=col)
    src = [("透明地质（第3章）", "地层与土性参数"), ("透明计算（第4章）", "坡降比、安全系数"), ("透明巡检（5.4节）", "候选、复核、覆盖"),
           ("工程台账", "设计、检测、险情"), ("运行管理", "监测、制度、应急")]
    x, w = 0.78, 1.04
    for t, sub in src:
        c.box(x, 4.26, w, 0.52, EV, t, [sub], align="center", title_size=8.2, fill_alpha=0.06, pad=0.05)
        c.arrow((x + w / 2, 3.74), (x + w / 2, 3.62))
        x += w + 0.065
    c.box(0.78, 3.62, 5.50, 0.46, NEUT, None, ["**证据记录与状态判别：缺失、不适用、候选、已复核、可采纳",
                                              "可采纳性门控（空间、时间、版本相容）与桩号区间关联"],
          align="center", fill_alpha=0.06, vcenter=True)
    c.arrow((3.53, 3.16), (3.53, 3.04))
    c.box(0.78, 3.04, 5.50, 0.30, RULE, None, ["**29项二级指标、5个准则层 → 5类失效模式（关联矩阵）；运行管理作安全屏障修正"],
          align="center", fill_alpha=0.06, vcenter=True)
    c.arrow((3.53, 2.74), (3.53, 2.62))
    mods = [("物理规则链", ["模式响应、短板项", "观测上限、硬门控"], RULE), ("随机森林决策层", ["14项特征", "阈值策略"], RF),
            ("序数物理下限", ["学习层只可调高", "不可调低物理等级"], FLOOR), ("复核门", ["低置信度或巡检", "候选转人工复核"], NEUT)]
    x, w = 0.78, 1.30
    for t, sub, col in mods:
        c.box(x, 2.58, w, 0.58, col, t, sub, align="center", title_size=8.2, fill_alpha=0.07, pad=0.05)
        x += w + 0.10
    c.box(0.78, 1.94, 5.50, 0.24, FLOOR, None, ["多目标策略评价（离线）：在4051个候选策略中按安全优先原则选择并冻结运行策略"],
          align="center", fill_alpha=0.04, lw=0.6, vcenter=True)
    c.arrow((3.53, 1.68), (3.53, 1.56))
    c.box(0.78, 1.56, 5.50, 0.30, DANGER, None, ["**等级划分（A/B/C）、门控阈值、巡检证据判定标准、预警分级"],
          align="center", fill_alpha=0.05, vcenter=True)
    c.arrow((3.53, 1.26), (3.53, 1.14))
    c.box(0.78, 1.14, 4.10, 0.50, RF, None, ["**安全等级、主控失效模式、触发原因、证据清单与待复核事项",
                                            "证据不足时输出等级范围，并给出预警级别"], align="center", fill_alpha=0.06, vcenter=True)
    c.box(5.02, 1.14, 1.26, 0.50, NEUT, None, ["数字孪生平台", "（第6章）"], align="center", fill_alpha=0.06, vcenter=True)
    c.arrow((4.88, 0.89), (5.02, 0.89))
    c.crop(0.60, 4.30)
    c.save("fig5_1_framework")


# --------------------------------------------------------------------- Fig. 5.2
def fig_indicator_system():
    c = Canvas(3.62)
    cols = [
        ("A 工程质量", "0.1818", RULE, ["A1 断面尺寸达标率", "A2 填土质量", "A3 穿堤建筑物完好性", "A4 护坡完好率", "A5 软基段沉降",
                                       "A6 内部隐患", "A7 堤基不良地质处理", "A8 结合部止水质量", "A9 跨堤交叉工程"]),
        ("B 防洪安全", "0.1818", RULE, ["B1 堤顶高程", "B2 防洪标准符合性", "B3 风浪爬高与越浪", "B4 穿堤建筑物防洪"]),
        ("C 渗流安全", "0.3636", FLOOR, ["C1 堤基渗透比降*", "C2 排水设施有效性", "C3 管涌与渗漏观测†", "C4 堤身渗流稳定*",
                                        "C5 接触冲刷安全*", "C6 穿堤建筑物渗流"]),
        ("D 结构安全", "0.1818", RULE, ["D1 背水坡抗滑稳定*", "D2 临水坡抗滑稳定*", "D3 堤岸冲刷稳定", "D4 穿堤结构安全",
                                       "D5 不均匀沉降与裂缝"]),
        ("E 运行管理", "0.0909", NEUT, ["E1 监测设施完备性", "E2 管理制度健全性", "E3 维护记录完整性", "E4 应急预案与物资",
                                       "E5 隐患巡查与处置"]),
    ]
    c.box(1.90, 3.58, 2.50, 0.36, FLOOR, None, ["**目标层：堤防渗流安全透明评价"], align="center", fill_alpha=0.10)
    w, gap = 1.18, 0.07
    x0 = 0.04
    for k, (title, wt, col, items) in enumerate(cols):
        x = x0 + k * (w + gap)
        cx = x + w / 2
        c.poly([(3.15, 3.22), (3.15, 3.12), (cx, 3.12), (cx, 3.02)], head=True)
        c.box(x, 3.02, w, 0.40, col, None, [f"**{title}", f"权重 {wt}"], align="center", fill_alpha=0.12, pad=0.03)
        p = FancyBboxPatch((x, 0.62), w, 1.92, boxstyle="round,pad=0,rounding_size=0.04",
                           facecolor=tint(col, 0.04), edgecolor=col, linewidth=0.6)
        c.ax.add_patch(p)
        c.arrow((cx, 2.62), (cx, 2.54))
        y = 2.43
        for it in items:
            color = DANGER if "†" in it else (RF if "*" in it else "black")
            c.line(x + 0.05, y, it, size=7.5, color=color)
            y -= 0.205
    c.line(0.04, 0.47, "准则层权重为AHP常权；指标经关联矩阵映射到漫顶、渗流破坏、边坡失稳、冲刷、穿堤建筑物失效5类失效模式，运行管理作为安全屏障修正",
           size=7.3, color=NEUT)
    c.line(0.04, 0.30, "*  由透明计算（第4章）提供的物理计算指标；†  由透明巡检（5.4节）提供的观测证据指标", size=7.3, color=NEUT)
    c.crop(0.18, 3.62)
    c.save("fig5_2_indicator_system")


# --------------------------------------------------------------------- Fig. 5.3
def fig_inspection_workflow():
    c = Canvas(2.96)
    row1 = [("航线与时段规划", ["沿堤顶、背水坡、坡脚", "夜间或凌晨、高水位期", "高度按地面分辨率确定"], EV),
            ("红外与可见光采集", ["温度矩阵、可见光影像", "GPS、时间戳、航迹", "辐射参数与覆盖记录"], EV),
            ("图像预处理", ["温度反演与发射率校正", "局部背景温差 ΔT", "双光配准、地面投影"], NEUT),
            ("智能识别", ["YOLOv8n基线网络", "P2小目标层、EIoU损失", "SimAM/CBAM注意力"], RF)]
    row2 = [("评价接入", ["C3指标输入、观测门控", "确认事件等级下限", "覆盖充分性、复核触发"], FLOOR),
            ("证据化", ["事件编号、桩号区间", "采集/入库时间", "证据状态与溯源"], NEUT),
            ("人工复核", ["确认、误报、存疑", "误报原因与处置意见", "复核人与复核时间"], DANGER),
            ("后处理", ["置信度阈值与NMS", "多帧同目标合并", "水体、植被区域排除"], RF)]
    w, gap, h = 1.47, 0.12, 0.80
    top1, top2 = 2.92, 1.86
    for k, (t, lines, col) in enumerate(row1):
        x = 0.04 + k * (w + gap)
        c.box(x, top1, w, h, col, t, lines, num=k + 1, fill_alpha=0.07)
        if k < 3:
            c.arrow((x + w, top1 - h / 2), (x + w + gap, top1 - h / 2))
    for k, (t, lines, col) in enumerate(row2):
        x = 0.04 + k * (w + gap)
        c.box(x, top2, w, h, col, t, lines, num=8 - k, fill_alpha=0.07, lw=1.2 if k == 0 else 0.8)
        if k < 3:
            c.arrow((x + w + gap, top2 - h / 2), (x + w, top2 - h / 2))
    xr = 0.04 + 3 * (w + gap) + w / 2
    c.arrow((xr, top1 - h), (xr, top2))
    c.crop(top2 - h - 0.04, 2.96)
    c.save("fig5_3_inspection_workflow")


# --------------------------------------------------------------------- Fig. 5.5
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
    c.box(2.97, 0.80, 1.38, 0.50, RF, None, ["多目标策略评价（离线）", "冻结策略 $\\pi^*$，见图5.6"], fill_alpha=0.03, lw=0.6)
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
    c.save("fig5_5_decision_chain")


# --------------------------------------------------------------------- Fig. 5.6
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
    c.save("fig5_6_evaluation_system")


def main():
    fig_framework()
    fig_indicator_system()
    fig_inspection_workflow()
    fig_decision_chain()
    fig_evaluation_system()


if __name__ == "__main__":
    main()
