from pathlib import Path
import csv,json
import numpy as np
from run_ml_baselines import X,y,fold,RandomForest,metrics,rows,OUT
# out-of-fold probabilities using the same grouped split as the ML baseline
proba=np.zeros((len(y),3))
for f in range(5):
 tr=fold!=f; te=fold==f
 m=RandomForest(n_estimators=120,max_depth=7,min_samples_leaf=3,max_features=4,seed=20260929+f); m.fit(X[tr],y[tr]); proba[te]=m.predict_proba(X[te])
points=[]
for tc in np.arange(.20,.901,.05):
 for tb in np.arange(.20,.901,.05):
  pred=np.where(proba[:,2]>=tc,2,np.where(proba[:,1]>=tb,1,0))
  mm=metrics(y,pred); mm.update({'t_c':round(float(tc),2),'t_b':round(float(tb),2),'escalation_rate':float(np.mean(pred==2)),'review_rate':float(np.mean(np.max(proba,axis=1)<.60)),'c_to_a':int(mm['cm'][2][0]),'c_to_b':int(mm['cm'][2][1]),'safe_loss':int(2*mm['cm'][2][0]+mm['cm'][2][1])})
  points.append(mm)
# Pareto: maximize accuracy, macro F1, C recall; minimize escalation rate and C underestimation.
def dominates(a,b):
 ge=(a['accuracy']>=b['accuracy'] and a['macro_f1']>=b['macro_f1'] and a['c_recall']>=b['c_recall'] and a['c_underestimate']<=b['c_underestimate'] and a['escalation_rate']<=b['escalation_rate'])
 strict=(a['accuracy']>b['accuracy'] or a['macro_f1']>b['macro_f1'] or a['c_recall']>b['c_recall'] or a['c_underestimate']<b['c_underestimate'] or a['escalation_rate']<b['escalation_rate'])
 return ge and strict
pareto=[p for p in points if not any(dominates(q,p) for q in points)]
pareto=sorted(pareto,key=lambda p:(-p['accuracy'],-p['c_recall'],p['escalation_rate']))
# compact output
compact=[]
for p in pareto:
 compact.append({k:p[k] for k in ['t_c','t_b','accuracy','macro_f1','balanced_accuracy','c_recall','c_underestimate','c_to_a','c_to_b','safe_loss','a_overestimate','escalation_rate']})
(OUT/'pareto_threshold_frontier.json').write_text(json.dumps(compact,ensure_ascii=False,indent=2),encoding='utf-8')
# also save all points for plotting/review
(OUT/'pareto_threshold_grid.csv').write_text('t_c,t_b,accuracy,macro_f1,balanced_accuracy,c_recall,c_underestimate,c_to_a,c_to_b,safe_loss,a_overestimate,escalation_rate\n'+'\n'.join(','.join(str(p[k]) for k in ['t_c','t_b','accuracy','macro_f1','balanced_accuracy','c_recall','c_underestimate','c_to_a','c_to_b','safe_loss','a_overestimate','escalation_rate']) for p in points),encoding='utf-8')
print('grid',len(points),'pareto',len(compact))
for p in compact[:20]: print(p)
