from pathlib import Path
import json, numpy as np
from run_ml_baselines import X,y,fold,RandomForest,metrics,OUT,groups

def grid_pick(prob,yt):
 best=None
 for tc in np.arange(.20,.901,.05):
  for tb in np.arange(.20,.901,.05):
   pred=np.where(prob[:,2]>=tc,2,np.where(prob[:,1]>=tb,1,0)); m=metrics(yt,pred); esc=float(np.mean(pred==2))
   # safety-constrained selection; if no candidate passes, maximize joint score
   # Safety guard: the candidate may not collapse a reference C case directly to A.
   no_direct_c_to_a=(m['cm'][2][0]==0)
   feasible=(m['c_recall']>=.85 and no_direct_c_to_a)
   key=(1 if feasible else 0, m['macro_f1']+0.25*m['c_recall']-0.05*esc, -esc, -m['c_underestimate'])
   if best is None or key>best[0]: best=(key,float(tc),float(tb))
 return best[1],best[2]

oof=np.zeros(len(y),int); thresholds=[]
for outer in range(5):
 te=fold==outer; tr=~te
 # inner folds derived from group hashes within outer training
 ug=sorted(set(groups[i] for i in np.where(tr)[0])); mp={g:i%3 for i,g in enumerate(ug)}; inf=np.array([mp[groups[i]] if tr[i] else -1 for i in range(len(y))])
 ip=np.zeros((tr.sum(),3)); iy=y[tr]; tr_indices=np.where(tr)[0]
 for inner in range(3):
  it=tr_indices[inf[tr_indices]!=inner]; iv=tr_indices[inf[tr_indices]==inner]
  m=RandomForest(n_estimators=80,max_depth=7,min_samples_leaf=3,max_features=4,seed=20261000+outer*10+inner);m.fit(X[it],y[it]);
  # use vote probabilities from inner validation
  ip[np.isin(tr_indices,iv)]=m.predict_proba(X[iv])
 tc,tb=grid_pick(ip,iy); thresholds.append({'outer':outer,'t_c':tc,'t_b':tb})
 m=RandomForest(n_estimators=80,max_depth=7,min_samples_leaf=3,max_features=4,seed=20261050+outer);m.fit(X[tr],y[tr]); prob=m.predict_proba(X[te]); oof[te]=np.where(prob[:,2]>=tc,2,np.where(prob[:,1]>=tb,1,0))
res=metrics(y,oof); res['thresholds']=thresholds;res['split']='5 outer x 3 inner grouped nested CV';res['n_estimators']=80
(OUT/'nested_pareto_results.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
