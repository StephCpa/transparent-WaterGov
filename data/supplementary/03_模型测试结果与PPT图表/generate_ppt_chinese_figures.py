# -*- coding: utf-8 -*-
"""Generate PPT-ready Chinese figures for the levee safety assessment thesis."""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import numpy as np
import pandas as pd
from matplotlib import font_manager


SAFE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SAFE_DIR))

from failure_response_barrier_model import (  # noqa: E402
    FAILURE_MODES,
    MODE_INDICATOR_WEIGHTS,
    MODE_WEIGHTS,
    load_failure_mode_matrix,
)


OUT_DIR = SAFE_DIR / "ppt_chinese_figures"
SENS_DIR = SAFE_DIR / "sensitivity_outputs"
SYN_DIR = SAFE_DIR / "synthetic_dataset_outputs"

MODE_COLORS = {
    "漫顶失效": "#356EA9",
    "渗流破坏": "#D95F02",
    "边坡失稳": "#1B9E77",
    "冲刷破坏": "#7570B3",
    "穿堤建筑物失效": "#E7298A",
}

VARIABLE_LABELS = {
    "seepage_i_ratio_to_icr": "堤基渗透比降/临界比降",
    "back_slope_fos": "背水坡安全系数",
    "front_slope_fos": "临水坡安全系数",
    "top_elevation_minus_design_flood": "堤顶高程-设计洪水位",
    "body_i": "堤身渗流比降",
    "contact_i": "接触面渗透比降",
    "fos_back": "背水坡安全系数",
    "fos_front": "临水坡安全系数",
    "top_elevation_margin": "堤顶超高裕度",
    "scour_depth_m": "冲刷深度",
}

TARGET_LABELS = {
    "safe_reference": "基准安全",
    "overtopping": "漫顶",
    "seepage": "渗流",
    "slope": "边坡",
    "scour": "冲刷",
    "building": "穿堤建筑物",
    "mixed": "复合不利",
}

SEVERITY_LABELS = {
    "safe": "安全",
    "slight": "轻微不利",
    "moderate": "中等不利",
    "severe": "严重不利",
    "critical": "极端不利",
}

GRADE_ORDER = ["A级安全", "B级基本安全", "C级不安全"]


def setup_font() -> None:
    for path in [Path(r"C:\Windows\Fonts\msyh.ttc"), Path(r"C:\Windows\Fonts\times.ttf")]:
        if path.exists():
            font_manager.fontManager.addfont(str(path))
    plt.rcParams["font.family"] = ["Times New Roman", "Microsoft YaHei"]
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
    plt.rcParams["font.serif"] = ["Times New Roman"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.facecolor"] = "white"
    plt.rcParams["axes.facecolor"] = "white"
    plt.rcParams["savefig.facecolor"] = "white"


def savefig(name: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / name
    plt.tight_layout()
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    return out


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def simple_grade(value: str) -> str:
    if str(value).startswith("A"):
        return "A级安全"
    if str(value).startswith("B"):
        return "B级基本安全"
    return "C级不安全"


def expected_grade(severity: str) -> str:
    if severity in {"safe", "slight"}:
        return "A级安全"
    if severity == "moderate":
        return "B级基本安全"
    return "C级不安全"


def plot_mode_weights() -> Path:
    labels = list(MODE_WEIGHTS)
    values = [MODE_WEIGHTS[k] for k in labels]
    colors = [MODE_COLORS.get(label, "#666666") for label in labels]
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    bars = ax.bar(labels, values, color=colors, edgecolor="#2F2F2F", linewidth=0.5)
    ax.set_ylabel("权重")
    ax.set_title("失效模式权重")
    ax.set_ylim(0, max(values) * 1.24)
    ax.grid(axis="y", alpha=0.22)
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value + max(values) * 0.025,
            f"{value:.3f}",
            ha="center",
            va="bottom",
            fontsize=10,
        )
    ax.tick_params(axis="x", rotation=12)
    return savefig("01_失效模式权重.png")


def plot_indicator_matrix() -> Path:
    rows = [row for row in load_failure_mode_matrix() if not row["code"].startswith("E")]
    matrix = [[row["modes"].get(mode, 0) for mode in FAILURE_MODES] for row in rows]
    y_labels = [row["code"] for row in rows]

    fig, ax = plt.subplots(figsize=(9.6, 9.2))
    image = ax.imshow(matrix, cmap="YlOrRd", vmin=0, vmax=3, aspect="auto")
    ax.set_xticks(range(len(FAILURE_MODES)), FAILURE_MODES, rotation=20, ha="right")
    ax.set_yticks(range(len(y_labels)), y_labels)
    ax.set_title("指标-失效模式关联矩阵")
    ax.set_xlabel("失效模式")
    ax.set_ylabel("评价指标")
    for i, row in enumerate(matrix):
        for j, value in enumerate(row):
            if value:
                ax.text(j, i, str(value), ha="center", va="center", fontsize=8.5, color="#202020")
    cbar = fig.colorbar(image, ax=ax, fraction=0.035, pad=0.02)
    cbar.set_label("关联强度（0-3）")
    return savefig("02_指标失效模式关联矩阵.png")


def plot_internal_weights() -> Path:
    fig, axes = plt.subplots(len(FAILURE_MODES), 1, figsize=(8.4, 11.0))
    for ax, mode in zip(axes, FAILURE_MODES):
        items = sorted(MODE_INDICATOR_WEIGHTS[mode].items(), key=lambda x: x[1], reverse=True)[:8]
        labels = [code for code, _ in items][::-1]
        values = [value for _, value in items][::-1]
        ax.barh(labels, values, color=MODE_COLORS.get(mode, "#5B8C85"), edgecolor="#2F2F2F", linewidth=0.4)
        ax.set_title(mode, loc="left", fontsize=11)
        ax.set_xlim(0, max(values) * 1.28 if values else 1)
        ax.grid(axis="x", alpha=0.18)
        for y, value in enumerate(values):
            ax.text(value + 0.004, y, f"{value:.3f}", va="center", fontsize=8.8)
    fig.suptitle("各失效模式内部主控指标权重", y=0.997, fontsize=14)
    return savefig("03_各失效模式内部指标权重.png")


def summarize_ranges(rows: list[dict[str, str]], keys: list[str]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, ...], list[float]] = defaultdict(list)
    for row in rows:
        key = tuple(row[k] for k in keys)
        grouped[key].append(float(row["score"]))
    summary = []
    for key, values in grouped.items():
        summary.append({**dict(zip(keys, key)), "range": max(values) - min(values)})
    return sorted(summary, key=lambda item: item["range"], reverse=True)


def aggregate_sensitivity(summary: list[dict[str, object]], key: str) -> list[dict[str, object]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for item in summary:
        grouped[str(item[key])].append(float(item["range"]))
    return sorted(
        (
            {
                key: name,
                "max_range": max(values),
                "mean_range": sum(values) / len(values),
            }
            for name, values in grouped.items()
        ),
        key=lambda item: item["max_range"],
        reverse=True,
    )


def plot_physical_sensitivity() -> Path:
    rows = read_csv(SENS_DIR / "failure_response_barrier_physical_oat.csv")
    per_profile = summarize_ranges(rows, ["stake", "variable"])
    summary = aggregate_sensitivity(per_profile, "variable")
    labels = [VARIABLE_LABELS.get(str(item["variable"]), str(item["variable"])) for item in summary][::-1]
    values = [float(item["max_range"]) for item in summary][::-1]

    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    ax.barh(labels, values, color="#C8553D", edgecolor="#2F2F2F", linewidth=0.4)
    ax.set_xlabel("安全得分最大变化幅度")
    ax.set_title("关键物理指标敏感性排序")
    ax.grid(axis="x", alpha=0.22)
    for y, value in enumerate(values):
        ax.text(value + 0.35, y, f"{value:.2f}", va="center", fontsize=9)
    return savefig("04_物理指标敏感性分析.png")


def plot_qualitative_sensitivity() -> Path:
    rows = read_csv(SENS_DIR / "qualitative_indicator_oat_sensitivity.csv")
    per_profile = summarize_ranges(rows, ["stake", "indicator"])
    summary = aggregate_sensitivity(per_profile, "indicator")[:12]
    labels = [str(item["indicator"]) for item in summary][::-1]
    values = [float(item["max_range"]) for item in summary][::-1]

    fig, ax = plt.subplots(figsize=(7.4, 5.2))
    ax.barh(labels, values, color="#627C85", edgecolor="#2F2F2F", linewidth=0.4)
    ax.set_xlabel("安全得分最大变化幅度")
    ax.set_title("定性指标赋分敏感性排序")
    ax.grid(axis="x", alpha=0.22)
    for y, value in enumerate(values):
        ax.text(value + 0.20, y, f"{value:.2f}", va="center", fontsize=9)
    return savefig("05_定性指标赋分敏感性.png")


def plot_alpha_sensitivity() -> Path:
    rows = read_csv(SENS_DIR / "failure_response_barrier_alpha_lambda.csv")
    selected = [
        row
        for row in rows
        if row["management_scenario"] == "no_management_input" and abs(float(row["barrier_lambda"]) - 0.5) < 1e-9
    ]
    by_alpha: dict[float, list[float]] = defaultdict(list)
    for row in selected:
        by_alpha[float(row["alpha"])].append(float(row["score"]))

    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    alpha_values = sorted(by_alpha)
    mean_scores = [sum(by_alpha[alpha]) / len(by_alpha[alpha]) for alpha in alpha_values]
    min_scores = [min(by_alpha[alpha]) for alpha in alpha_values]
    max_scores = [max(by_alpha[alpha]) for alpha in alpha_values]
    ax.plot(alpha_values, mean_scores, marker="o", linewidth=2.0, color="#356EA9", label="平均得分")
    ax.fill_between(alpha_values, min_scores, max_scores, color="#356EA9", alpha=0.18, label="得分范围")
    ax.set_xlabel("短板控制系数 α")
    ax.set_ylabel("安全得分")
    ax.set_title("短板控制系数敏感性分析")
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False)
    return savefig("06_短板控制系数敏感性.png")


def plot_synthetic_grade_distribution(df: pd.DataFrame) -> Path:
    counts = df["模型等级简化"].value_counts().reindex(GRADE_ORDER, fill_value=0)
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    bars = ax.bar(counts.index, counts.values, color=["#2E7D32", "#F9A825", "#C62828"], edgecolor="#2F2F2F", linewidth=0.4)
    ax.set_ylabel("样本数量")
    ax.set_title("合成情景数据集评价等级分布")
    ax.grid(axis="y", alpha=0.22)
    ax.bar_label(bars, padding=3, fontsize=10)
    ax.set_ylim(0, max(counts.values) * 1.18)
    return savefig("07_合成数据集评价等级分布.png")


def plot_expected_vs_model_heatmap(df: pd.DataFrame) -> Path:
    conf = pd.crosstab(df["预设等级"], df["模型等级简化"]).reindex(index=GRADE_ORDER, columns=GRADE_ORDER, fill_value=0)
    conf.to_csv(OUT_DIR / "合成数据集预设等级_模型等级交叉表.csv", encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(7.4, 5.8))
    image = ax.imshow(conf.values, cmap="YlGnBu")
    ax.set_xticks(np.arange(len(GRADE_ORDER)), labels=GRADE_ORDER, rotation=16, ha="right")
    ax.set_yticks(np.arange(len(GRADE_ORDER)), labels=GRADE_ORDER)
    ax.set_xlabel("模型评价等级")
    ax.set_ylabel("数据集预设等级")
    ax.set_title("数据集预设等级与模型评价等级对比")
    for i in range(conf.shape[0]):
        for j in range(conf.shape[1]):
            value = int(conf.values[i, j])
            color = "white" if value > conf.values.max() * 0.55 else "#202020"
            ax.text(j, i, str(value), ha="center", va="center", color=color, fontsize=11, fontweight="bold")
    cbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("样本数量")
    return savefig("08_预设等级与模型等级对比.png")


def plot_expected_vs_model_distribution(df: pd.DataFrame) -> Path:
    expected = df["预设等级"].value_counts().reindex(GRADE_ORDER, fill_value=0)
    evaluated = df["模型等级简化"].value_counts().reindex(GRADE_ORDER, fill_value=0)
    x = np.arange(len(GRADE_ORDER))
    width = 0.36
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    bars1 = ax.bar(x - width / 2, expected.values, width, label="数据集预设等级", color="#3B82F6")
    bars2 = ax.bar(x + width / 2, evaluated.values, width, label="模型评价等级", color="#F97316")
    ax.set_xticks(x, labels=GRADE_ORDER)
    ax.set_ylabel("样本数量")
    ax.set_title("预设等级与模型输出等级分布对比")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.22)
    ax.bar_label(bars1, padding=3, fontsize=9)
    ax.bar_label(bars2, padding=3, fontsize=9)
    ax.set_ylim(0, max(expected.max(), evaluated.max()) * 1.18)
    return savefig("09_预设等级与模型等级分布对比.png")


def plot_mode_distribution(df: pd.DataFrame) -> Path:
    counts = df["dominant_mode"].value_counts().reindex(FAILURE_MODES, fill_value=0)
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    bars = ax.bar(counts.index, counts.values, color=[MODE_COLORS.get(k, "#666666") for k in counts.index], edgecolor="#2F2F2F", linewidth=0.4)
    ax.set_ylabel("样本数量")
    ax.set_title("主控失效模式识别结果分布")
    ax.tick_params(axis="x", rotation=14)
    ax.grid(axis="y", alpha=0.22)
    ax.bar_label(bars, padding=3, fontsize=10)
    ax.set_ylim(0, max(counts.values) * 1.18)
    return savefig("10_主控失效模式分布.png")


def plot_target_mode_heatmap(df: pd.DataFrame) -> Path:
    work = df.copy()
    work["目标情景"] = work["target_mode"].map(TARGET_LABELS)
    target_order = [TARGET_LABELS[k] for k in TARGET_LABELS]
    conf = pd.crosstab(work["目标情景"], work["dominant_mode"]).reindex(index=target_order, columns=FAILURE_MODES, fill_value=0)

    fig, ax = plt.subplots(figsize=(9.4, 5.8))
    image = ax.imshow(conf.values, cmap="PuBuGn", aspect="auto")
    ax.set_xticks(np.arange(len(FAILURE_MODES)), labels=FAILURE_MODES, rotation=18, ha="right")
    ax.set_yticks(np.arange(len(target_order)), labels=target_order)
    ax.set_xlabel("模型识别主控失效模式")
    ax.set_ylabel("预设情景类型")
    ax.set_title("预设情景与主控失效模式识别对比")
    for i in range(conf.shape[0]):
        for j in range(conf.shape[1]):
            value = int(conf.values[i, j])
            if value:
                color = "white" if value > conf.values.max() * 0.55 else "#202020"
                ax.text(j, i, str(value), ha="center", va="center", color=color, fontsize=9, fontweight="bold")
    cbar = fig.colorbar(image, ax=ax, fraction=0.035, pad=0.02)
    cbar.set_label("样本数量")
    return savefig("11_预设情景与主控失效模式对比.png")


def plot_score_by_severity(df: pd.DataFrame) -> Path:
    work = df.copy()
    order = ["safe", "slight", "moderate", "severe", "critical"]
    data = [work.loc[work["target_severity"] == key, "score"].values for key in order]
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    bp = ax.boxplot(data, tick_labels=[SEVERITY_LABELS[k] for k in order], patch_artist=True, showmeans=True)
    colors = ["#2E7D32", "#7CB342", "#F9A825", "#EF6C00", "#C62828"]
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.72)
    ax.set_ylabel("安全得分")
    ax.set_title("不同不利程度情景下的安全得分分布")
    ax.grid(axis="y", alpha=0.22)
    return savefig("12_不同严重程度安全得分分布.png")


def plot_method_flowchart() -> Path:
    fig, ax = plt.subplots(figsize=(10.0, 5.4))
    ax.axis("off")
    box_common = dict(boxstyle="round,pad=0.32,rounding_size=0.05", fc="#F7F7F7", ec="#333333", lw=0.9)
    box_core = dict(boxstyle="round,pad=0.32,rounding_size=0.05", fc="#E8F4FD", ec="#1D4E89", lw=1.1)
    box_gate = dict(boxstyle="round,pad=0.32,rounding_size=0.05", fc="#FFF4E6", ec="#B45309", lw=1.1)
    nodes = [
        ("规范导则指标体系\nA/B/C/D/E", 0.12, 0.66, box_common),
        ("指标量化\n机理计算+分档赋分", 0.31, 0.66, box_common),
        ("失效模式关联矩阵\n0-3级关联强度", 0.52, 0.66, box_core),
        ("失效模式响应\n漫顶/渗流/边坡/冲刷/穿堤", 0.74, 0.66, box_core),
        ("UAV渗漏证据门控", 0.52, 0.30, box_gate),
        ("运行管理安全屏障", 0.74, 0.30, box_gate),
        ("综合安全等级\n主控失效模式+贡献率", 0.91, 0.49, box_common),
    ]
    for text, x, y, style in nodes:
        ax.text(x, y, text, ha="center", va="center", fontsize=10.5, bbox=style)
    arrows = [
        ((0.20, 0.66), (0.25, 0.66)),
        ((0.39, 0.66), (0.45, 0.66)),
        ((0.60, 0.66), (0.66, 0.66)),
        ((0.82, 0.66), (0.87, 0.53)),
        ((0.58, 0.30), (0.68, 0.30)),
        ((0.80, 0.34), (0.87, 0.45)),
        ((0.52, 0.58), (0.52, 0.38)),
    ]
    for start, end in arrows:
        ax.annotate("", xy=end, xytext=start, arrowprops=dict(arrowstyle="->", lw=1.25, color="#333333"))
    ax.text(0.63, 0.90, "核心改进：由单一综合打分转为“失效模式响应+安全屏障修正”的可解释评价", ha="center", fontsize=12.5, weight="bold")
    return savefig("13_评价方法流程图.png")


def plot_overview(paths: list[Path]) -> Path:
    files = [path for path in paths if path.suffix.lower() == ".png"]
    cols = 3
    rows = (len(files) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(15.0, rows * 4.0), dpi=180)
    axes = np.asarray(axes).ravel()
    for ax, path in zip(axes, files):
        image = mpimg.imread(path)
        ax.imshow(image)
        ax.set_title(path.stem, fontsize=11, pad=8)
        ax.axis("off")
    for ax in axes[len(files):]:
        ax.axis("off")
    fig.suptitle("PPT中文汇报图总览", fontsize=18, y=0.995)
    fig.tight_layout(rect=[0, 0, 1, 0.985])
    out = OUT_DIR / "00_中文图总览.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def main() -> None:
    setup_font()
    synthetic = pd.read_csv(SYN_DIR / "synthetic_evaluation_dataset.csv", encoding="utf-8-sig")
    synthetic["模型等级简化"] = synthetic["grade"].map(simple_grade)
    synthetic["预设等级"] = synthetic["target_severity"].map(expected_grade)

    paths = [
        plot_mode_weights(),
        plot_indicator_matrix(),
        plot_internal_weights(),
        plot_physical_sensitivity(),
        plot_qualitative_sensitivity(),
        plot_alpha_sensitivity(),
        plot_synthetic_grade_distribution(synthetic),
        plot_expected_vs_model_heatmap(synthetic),
        plot_expected_vs_model_distribution(synthetic),
        plot_mode_distribution(synthetic),
        plot_target_mode_heatmap(synthetic),
        plot_score_by_severity(synthetic),
        plot_method_flowchart(),
    ]
    overview_path = plot_overview(paths)
    index = {
        "说明": "PPT中文汇报版图片，已使用中文字体重画，避免英文和乱码。",
        "图片": [overview_path.name] + [path.name for path in paths],
    }
    (OUT_DIR / "figure_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"generated {len(paths)} figures in {OUT_DIR}")
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
