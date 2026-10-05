from run_ml_baselines import X,y,fold,RandomForest,metrics
import numpy as np
for w in [1.5,2,3,4,6]:
 p=np.zeros(len(y),int)
 for f in range(5):
  tr=fold!=f;te=fold==f;m=RandomForest(n_estimators=120,max_depth=7,min_samples_leaf=3,max_features=4,seed=203000+f,class_weight={0:1,1:1,2:w});m.fit(X[tr],y[tr]);p[te]=m.predict(X[te])
 mm=metrics(y,p);print(w,{k:mm[k] for k in ['accuracy','macro_f1','balanced_accuracy','c_recall','c_underestimate','a_overestimate']},'c_to_a',mm['cm'][2][0],'c_to_b',mm['cm'][2][1])
