from pathlib import Path
import pandas as pd
import numpy as np
p=Path(__file__).resolve().parent
iface=pd.read_csv(p/'interfaces.csv'); ori=pd.read_csv(p/'orientations.csv')
issues=[]
if not iface[['X','Y','Z','formation']].equals(ori[['X','Y','Z','formation']]): issues.append('interfaces.csv 与 orientations.csv 的坐标/地层字段不完全一致')
conf=iface[iface.duplicated(['X','Y','Z'],keep=False)].sort_values(['X','Y','Z','formation'])
if len(conf): issues.append(f'存在 {len(conf)} 条相同 X/Y/Z 但不同记录的界面点')
if np.allclose(ori.dip.to_numpy(),0) and np.allclose(ori.azimuth.to_numpy(),0): issues.append('dip 和 azimuth 全为 0：请确认是水平层假设还是缺失值')
loc=iface[['X','Y']].drop_duplicates();
lines=['# GemPy 建模前置检查（2026-10-07）','',f'- 界面记录：{len(iface)} 条；平面点位：{len(loc)} 个。',f'- 产状记录：{len(ori)} 条。']
if issues:
 lines += ['', '## 需要人工确认的事项', ''] + [f'- {x}' for x in issues]
 lines += ['', '## 建模决策建议', '', '- 若确认全零产状代表水平层，可保留并在论文方法中明确“水平层假设”。', '- 若不是水平层假设，应先补充实测产状，避免将插值结果表述为实测约束模型。', '- P01 的 GR/Basics 重合记录应确认是否为不同结构组的编码标记。']
else: lines += ['', '未发现前置数据冲突。']
(p/'gempy_preflight_20261007.md').write_text('\n'.join(lines),encoding='utf-8')
print('\n'.join(lines))
