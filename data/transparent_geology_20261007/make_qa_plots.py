from pathlib import Path
import struct
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm

ROOT=Path(__file__).resolve().parent

def read_tiff(path):
 raw=path.read_bytes(); e='<' if raw[:2]==b'II' else '>'; ifd=struct.unpack_from(e+'I',raw,4)[0]; n=struct.unpack_from(e+'H',raw,ifd)[0]; tags={}
 for i in range(n):
  off=ifd+2+12*i; tag,typ,count,val=struct.unpack_from(e+'HHII',raw,off); size={1:1,2:1,3:2,4:4,5:8,12:8}.get(typ)
  if size is None: continue
  b=raw[off+8:off+12] if size*count<=4 else raw[val:val+size*count]
  if typ==3: v=list(struct.unpack(e+'H'*count,b[:2*count]))
  elif typ==4: v=list(struct.unpack(e+'I'*count,b[:4*count]))
  elif typ==5: v=[struct.unpack(e+'II',b[j:j+8]) for j in range(0,8*count,8)]
  elif typ==12: v=list(struct.unpack(e+'d'*count,b[:8*count]))
  else: v=list(b)
  tags[tag]=v[0] if count==1 and isinstance(v,list) else v
 w,h=int(tags[256]),int(tags[257]); offs=tags[273] if isinstance(tags[273],list) else [tags[273]]; counts=tags[279] if isinstance(tags[279],list) else [tags[279]]; rps=int(tags.get(278,h)); arr=np.empty((h,w)); row=0
 for o,c in zip(offs,counts):
  nr=min(rps,h-row); arr[row:row+nr]=np.frombuffer(raw[int(o):int(o)+int(c)],dtype='<f8',count=nr*w).reshape(nr,w); row+=nr
 return arr

iface=pd.read_csv(ROOT/'interfaces.csv'); dem=read_tiff(ROOT/'高程模型.tif')
plt.rcParams['font.sans-serif']=['SimHei','Microsoft YaHei','DejaVu Sans']; plt.rcParams['axes.unicode_minus']=False
scale_x,scale_y=1.002004008016032,1.6032064128256514
xmin,ymax=505000,3181800
xmax=xmin+dem.shape[1]*scale_x; ymin=ymax-dem.shape[0]*scale_y
fig,ax=plt.subplots(figsize=(8,6),dpi=180)
im=ax.imshow(dem,extent=[xmin,xmax,ymin,ymax],origin='upper',cmap='terrain')
sc=ax.scatter(iface.X,iface.Y,c=iface.Z,cmap='viridis',s=22,edgecolor='k',linewidth=.3,label='界面点')
ax.set_xlabel('X'); ax.set_ylabel('Y'); ax.set_title('DEM与地质界面点空间范围检查'); fig.colorbar(im,ax=ax,label='高程'); ax.legend(); fig.tight_layout(); fig.savefig(ROOT/'dem_interface_overlay.png'); plt.close(fig)

fig,ax=plt.subplots(figsize=(8,5),dpi=180)
forms=sorted(iface.formation.unique()); cmap=plt.get_cmap('tab10',len(forms))
for i,f in enumerate(forms):
 d=iface[iface.formation==f]; ax.scatter(d.X,d.Y,s=35,color=cmap(i),label=f,edgecolor='k',linewidth=.25)
ax.axhline(3181450,color='red',ls='--',lw=1.5,label='section1 trace: Y=3181450')
ax.set_xlabel('X'); ax.set_ylabel('Y'); ax.set_title('地层界面点与 section1 剖面线'); ax.legend(ncol=2,fontsize=8); fig.tight_layout(); fig.savefig(ROOT/'interface_points_section_trace.png'); plt.close(fig)
print('plots complete')
