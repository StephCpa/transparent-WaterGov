"""Publication-draft confusion matrices from the frozen audit summary."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "分析工作区" / "875基线分析"
data = json.loads((DIR / "875统计摘要.json").read_text(encoding="utf-8"))
labels = ("A", "B", "C")
panels = [("All scenarios (n=875)", data["overall"]), ("Seepage target (n=125)", data["by_mode"]["seepage"])]
fig, axes = plt.subplots(1, 2, figsize=(8.0, 3.5), dpi=180, constrained_layout=True)
for ax, (title, values) in zip(axes, panels):
    matrix = [[values["confusion"][r][c] for c in labels] for r in labels]
    ax.imshow(matrix, cmap="Blues", vmin=0, vmax=max(max(row) for row in matrix))
    for i in range(3):
        for j in range(3):
            ax.text(j, i, str(matrix[i][j]), ha="center", va="center", fontsize=11,
                    color="white" if matrix[i][j] > max(max(row) for row in matrix) * 0.55 else "#1a2a40")
    ax.set_xticks(range(3), labels)
    ax.set_yticks(range(3), labels)
    ax.set_xlabel("Model final grade")
    ax.set_ylabel("Synthetic reference grade")
    ax.set_title(title)
fig.savefig(DIR / "图_总体与纯渗流混淆矩阵.png", bbox_inches="tight")
plt.close(fig)
