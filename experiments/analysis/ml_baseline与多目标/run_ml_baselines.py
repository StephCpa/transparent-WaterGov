from pathlib import Path
import csv, json, hashlib
from collections import Counter
import numpy as np
ROOT=Path(r'PROJECT_ROOT')
CSV_PATH=ROOT/'875样本模型测试资料包'/'2_合成样本'/'synthetic_evaluation_dataset.csv'
OUT=ROOT/'分析工作区'/'ml_baseline与多目标'; OUT.mkdir(parents=True,exist_ok=True)
rows=list(csv.DictReader(open(CSV_PATH,encoding='utf-8-sig')))
feature_names=['top_elevation_m','seepage_i','body_i','contact_i','fos_back','fos_front','scour_depth_m','uav_density','uav_level']
X=np.array([[float(r[k]) for k in feature_names] for r in rows],float)
X=np.column_stack([X, X[:,1]/0.25, X[:,2]/0.25, X[:,3]/0.25, 1.0/X[:,4], X[:,6]/1.0])
feature_names += ['seepage_ratio','body_ratio','contact_ratio','inv_fos_back','scour_ratio']
# Reference target follows the frozen synthetic severity-to-grade rule, not the CSV model grade.
y=np.array([0 if r['target_severity'] in ('safe','slight') else 1 if r['target_severity']=='moderate' else 2 for r in rows])
groups=[hashlib.sha1(np.asarray(row,dtype=np.float64).tobytes()).hexdigest() for row in X]
unique=sorted(set(groups)); gfold={g:i%5 for i,g in enumerate(unique)}; fold=np.array([gfold[g] for g in groups])
def gini(labels):
 if len(labels)==0:return 0
 c=np.bincount(labels,minlength=3)/len(labels); return 1-float(np.sum(c*c))
class Node:
 __slots__=('pred','feature','threshold','left','right')
 def __init__(self,pred): self.pred=pred; self.feature=None; self.threshold=None; self.left=None; self.right=None
class DecisionTree:
 def __init__(self,max_depth=5,min_samples_leaf=4,max_features=None,rng=None): self.max_depth=max_depth; self.min_samples_leaf=min_samples_leaf; self.max_features=max_features; self.rng=rng or np.random.default_rng(0)
 def fit(self,X,y): self.n_features=X.shape[1]; self.root=self._grow(np.arange(len(y)),X,y,0); return self
 def _grow(self,idx,X,y,depth):
  node=Node(int(Counter(y[idx]).most_common(1)[0][0]));
  if depth>=self.max_depth or len(idx)<2*self.min_samples_leaf or len(set(y[idx]))==1:return node
  fs=np.arange(self.n_features)
  if self.max_features and self.max_features<self.n_features: fs=self.rng.choice(fs,self.max_features,replace=False)
  best=None; base=gini(y[idx])
  for f in fs:
   vals=np.unique(X[idx,f]);
   if len(vals)<=1: continue
   if len(vals)>30: vals=np.quantile(vals,np.linspace(.05,.95,19))
   thresholds=(vals[:-1]+vals[1:])/2
   for t in thresholds:
    li=idx[X[idx,f]<=t]; ri=idx[X[idx,f]>t]
    if len(li)<self.min_samples_leaf or len(ri)<self.min_samples_leaf: continue
    gain=base-(len(li)*gini(y[li])+len(ri)*gini(y[ri]))/len(idx)
    if best is None or gain>best[0]: best=(gain,f,float(t),li,ri)
  if best is None or best[0]<=1e-10:return node
  node.feature,node.threshold=best[1],best[2]; node.left=self._grow(best[3],X,y,depth+1); node.right=self._grow(best[4],X,y,depth+1); return node
 def _pred(self,row,node): return node.pred if node.feature is None else self._pred(row,node.left if row[node.feature]<=node.threshold else node.right)
 def predict(self,X): return np.array([self._pred(r,self.root) for r in X])
class RandomForest:
 def __init__(self,n_estimators=100,max_depth=7,min_samples_leaf=3,max_features=None,seed=42,class_weight=None): self.n_estimators=n_estimators; self.max_depth=max_depth; self.min_samples_leaf=min_samples_leaf; self.max_features=max_features; self.seed=seed; self.class_weight=class_weight
 def fit(self,X,y):
  rng=np.random.default_rng(self.seed); self.trees=[]; mf=self.max_features or max(1,int(np.sqrt(X.shape[1])))
  for _ in range(self.n_estimators):
   if self.class_weight:
    prob=np.array([float(self.class_weight.get(int(v),1.0)) for v in y]); prob=prob/prob.sum(); idx=rng.choice(len(y),len(y),replace=True,p=prob)
   else: idx=rng.integers(0,len(y),len(y))
   tree=DecisionTree(self.max_depth,self.min_samples_leaf,mf,np.random.default_rng(int(rng.integers(0,2**31-1)))); tree.fit(X[idx],y[idx]); self.trees.append(tree)
  return self
 def predict(self,X):
  p=np.vstack([t.predict(X) for t in self.trees]); return np.array([Counter(p[:,i]).most_common(1)[0][0] for i in range(X.shape[0])])
 def predict_proba(self,X):
  p=np.vstack([t.predict(X) for t in self.trees]); out=np.zeros((X.shape[0],3),float)
  for c in range(3): out[:,c]=(p==c).mean(axis=0)
  return out
def metrics(y,p):
 cm=np.zeros((3,3),int)
 for a,b in zip(y,p):cm[a,b]+=1
 acc=np.trace(cm)/len(y); f1=[]; rec=[]
 for c in range(3):
  tp=cm[c,c]; fn=cm[c].sum()-tp; fp=cm[:,c].sum()-tp; rr=tp/(tp+fn) if tp+fn else 0; pp=tp/(tp+fp) if tp+fp else 0; f1.append(2*pp*rr/(pp+rr) if pp+rr else 0); rec.append(rr)
 return {'accuracy':acc,'macro_f1':float(np.mean(f1)),'balanced_accuracy':float(np.mean(rec)),'c_recall':rec[2],'c_underestimate':int(cm[2,0]+cm[2,1]),'a_overestimate':int(cm[0,1]+cm[0,2]),'cm':cm.tolist()}
# The flat audit table stores only the 136 final-grade errors; all other rows are correct.
# This reconstructs the delivered final-grade baseline without confusing the raw CSV grade with the final gated grade.
rule_pred=y.copy()
for er in csv.DictReader(open(ROOT/'分析工作区'/'875基线分析'/'136条误分类溯源.csv',encoding='utf-8-sig')):
    idx=next(i for i,r in enumerate(rows) if r['sample_id']==er['sample_id'])
    rule_pred[idx]=0 if er['grade']=='A' else 1 if er['grade']=='B' else 2
results=[]
for name,model in [('decision_tree',lambda seed:DecisionTree(max_depth=5,min_samples_leaf=5,max_features=None,rng=np.random.default_rng(seed))),('random_forest',lambda seed:RandomForest(n_estimators=120,max_depth=7,min_samples_leaf=3,max_features=4,seed=seed))]:
 oof=np.zeros(len(y),int); fold_metrics=[]
 for f in range(5):
  tr=fold!=f;te=fold==f;m=model(20260929+f);m.fit(X[tr],y[tr]);oof[te]=m.predict(X[te]);fold_metrics.append(metrics(y[te],oof[te]))
 overall=metrics(y,oof); overall.update({'model':name,'fold_metrics':fold_metrics,'features':feature_names,'split':'5-fold grouped by identical physical feature vector'}); results.append(overall)
base=metrics(y,rule_pred); base.update({'model':'delivered_rule','fold_metrics':[],'features':[],'split':'fixed delivered rule output'}); results.insert(0,base)
(OUT/'ml_baseline_results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'ml_feature_manifest.json').write_text(json.dumps({'n':len(y),'unique_groups':len(unique),'features':feature_names,'excluded':['target_mode','target_severity','sample_id','model_grade','score','rho','dominant_mode']},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(results,ensure_ascii=False,indent=2))
