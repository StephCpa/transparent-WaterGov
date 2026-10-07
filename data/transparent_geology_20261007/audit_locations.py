from pathlib import Path
import pandas as pd
import numpy as np
from scipy.spatial import ConvexHull
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=Path(__file__).resolve().parent
f=pd.read_csv(p/'interfaces.csv')
xy=f[['X','Y']].drop_duplicates().sort_values('Y')
xy.insert(0,'location_id',[f'P{i+1:02}' for i in range(len(xy))])
f=f.merge(xy,on=['X','Y'])
f[f.duplicated(['X','Y','Z'],keep=False)].to_csv(p/'coincident_interfaces.csv',index=False,encoding='utf-8-sig')
wide=f.pivot(index='location_id',columns='formation',values='Z').reindex(columns=['FT','MCN1','FS','MCN2','FS2','GR','Basics'])
xy.merge(wide,on='location_id').to_csv(p/'location_interface_elevations.csv',index=False,encoding='utf-8-sig')
pts=xy[['X','Y']].to_numpy(); h=ConvexHull(pts)
area=h.volume
print('locations',len(xy),'hull_area',area,'area_fraction',area/(500*800))
print('coincident rows',f.duplicated(['X','Y','Z'],keep=False).sum())
print(wide.to_string())
plt.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei'];plt.rcParams['axes.unicode_minus']=False
fig,axs=plt.subplots(1,2,figsize=(12,5),layout='constrained')
axs[0].plot(np.r_[pts[h.vertices,0],pts[h.vertices[0],0]],np.r_[pts[h.vertices,1],pts[h.vertices[0],1]],'--',color='gray',label='点位凸包')
axs[0].scatter(pts[:,0],pts[:,1],c='black',s=14)
for _,r in xy.iterrows(): axs[0].annotate(r.location_id,(r.X,r.Y),xytext=(4,2),textcoords='offset points',fontsize=7)
axs[0].plot([505000,505500],[3181450,3181450],c='red',label='原脚本横剖面')
axs[0].set(xlim=(505000,505500),ylim=(3181000,3181800),xlabel='X（原始坐标）',ylabel='Y（原始坐标）',title='13 个点位及横剖面覆盖范围');axs[0].legend(fontsize=8);axs[0].ticklabel_format(useOffset=False,style='plain')
for col in wide.columns:
 axs[1].scatter(range(len(wide)),wide[col],label=col,s=26)
axs[1].set(xticks=range(len(wide)),xticklabels=wide.index,ylabel='界面高程（原始单位）',title='各点位界面高程（仅观测点，不插值）');axs[1].tick_params(axis='x',rotation=60);axs[1].legend(ncol=3,fontsize=8)
fig.savefig(p/'location_and_elevation_audit.png',dpi=180)
