from pathlib import Path
import pandas as pd
p=Path(__file__).resolve().parent
f=pd.read_csv(p/'interfaces.csv'); y0=3181450.0
f['section_y']=y0; f['abs_dy']=(f.Y-y0).abs(); f.sort_values(['abs_dy','X','Z']).to_csv(p/'section1_nearest_observations.csv',index=False,encoding='utf-8-sig')
near=f[f.abs_dy<=60].copy();
lines=['# section1 附近观测点清单（不含插值）','',f'- 目标剖面：Y={y0:.1f}','- 说明：此表只列出剖面附近的原始界面点，不是 GemPy 剖面结果。','',f'- 60 m 范围内记录数：{len(near)}，点位数：{near[["X","Y"]].drop_duplicates().shape[0]}。','', '| X | Y | Z | formation | 与剖面距离 |','|---:|---:|---:|---|---:|']
for _,r in near.sort_values(['X','Z']).iterrows(): lines.append(f'| {r.X:.3f} | {r.Y:.3f} | {r.Z:.3f} | {r.formation} | {r.abs_dy:.3f} |')
(p/'section1_nearest_observations.md').write_text('\n'.join(lines),encoding='utf-8')
print('\n'.join(lines))
