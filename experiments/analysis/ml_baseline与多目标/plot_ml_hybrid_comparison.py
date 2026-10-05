from pathlib import Path
import matplotlib.pyplot as plt

out = Path(r'PROJECT_ROOT\分析工作区\ml_baseline与多目标\图_机器学习安全门控对比.png')
points = [
    ('Rule baseline', 0.8272305676, 0.8371428571, 57, 'o'),
    ('RF majority', 0.7835082222, 0.8542857143, 102, 'o'),
    ('RF threshold', 0.8583787315, 0.8571428571, 100, 'o'),
    ('RF safety weight 6', 0.7009494, 1.0, 0, 'o'),
    ('Physical-veto hybrid', 0.91189034899, 1.0, 0, '*'),
]
fig, ax = plt.subplots(figsize=(6.3, 4.2), dpi=180)
for label, x, y, loss, marker in points:
    ax.scatter(x, y, c=[loss], cmap='plasma', vmin=0, vmax=105, s=90 if marker=='o' else 150, marker=marker, edgecolors='black', linewidths=.5, zorder=3)
    dx, dy = (0.002, 0.003)
    if label == 'RF safety weight 6': dx, dy = 0.002, -0.012
    if label == 'Physical-veto hybrid': dx, dy = -0.038, -0.015
    ax.text(x+dx, y+dy, label, fontsize=8)
sm = plt.cm.ScalarMappable(cmap='plasma', norm=plt.Normalize(vmin=0,vmax=105)); sm.set_array([])
cbar=fig.colorbar(sm, ax=ax, pad=0.02); cbar.set_label('Safety loss $L_{safe}$', fontsize=8)
ax.set_xlabel('Macro-F1'); ax.set_ylabel('C-class recall'); ax.set_xlim(0.68, 0.94); ax.set_ylim(0.62, 1.04)
ax.grid(True, alpha=.3); ax.set_title('Safety-aware comparison on 875 controlled scenarios', fontsize=10)
fig.tight_layout(); fig.savefig(out, bbox_inches='tight'); plt.close(fig)
print(out)
