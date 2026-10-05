"""Create a compact confidence and review-status figure for the inspection audit."""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "分析工作区" / "巡检识别审计"
rows = list(csv.DictReader((AUDIT / "检测标签逐条记录.csv").open(encoding="utf-8-sig")))
field = [float(r["confidence"]) for r in rows if r["group"] == "匿名堤防现场巡检"]
artificial = [float(r["confidence"]) for r in rows if r["group"] == "人工管涌验证"]

fig, axes = plt.subplots(1, 2, figsize=(8.0, 3.2), dpi=180, constrained_layout=True)
axes[0].boxplot([field, artificial], labels=["Field review\n9 boxes", "Controlled\n14 boxes"], patch_artist=True,
                boxprops={"facecolor": "#6baed6"}, medianprops={"color": "#17365d", "linewidth": 1.5})
axes[0].set_ylabel("Detection confidence")
axes[0].set_ylim(0, 1)
axes[0].set_title("Confidence distribution")
axes[1].bar(["Field images", "Detected", "Reviewed FP"], [114, 9, 9], color=["#bdbdbd", "#6baed6", "#de2d26"])
axes[1].set_ylabel("Count")
axes[1].set_title("Field screening and review")
for i, v in enumerate([114, 9, 9]):
    axes[1].text(i, v + 2, str(v), ha="center", va="bottom")
fig.savefig(AUDIT / "图_巡检检测置信度与复核状态.png", bbox_inches="tight")
plt.close(fig)
