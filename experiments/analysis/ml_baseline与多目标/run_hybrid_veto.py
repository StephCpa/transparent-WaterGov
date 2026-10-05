from pathlib import Path
import csv, json, contextlib, io
import numpy as np

ROOT = Path(r'PROJECT_ROOT')
OUT = ROOT / '分析工作区' / 'ml_baseline与多目标'
# Suppress the baseline module's diagnostic printout while reusing its deterministic model code.
import sys
sys.path.insert(0, str(OUT))
with contextlib.redirect_stdout(io.StringIO()):
    from run_ml_baselines import X, y, fold, RandomForest, metrics, rows

rule_pred = y.copy()
with open(ROOT / '分析工作区' / '875基线分析' / '136条误分类溯源.csv', encoding='utf-8-sig') as f:
    for er in csv.DictReader(f):
        idx = next(i for i, r in enumerate(rows) if r['sample_id'] == er['sample_id'])
        rule_pred[idx] = 0 if er['grade'] == 'A' else 1 if er['grade'] == 'B' else 2

proba = np.zeros((len(y), 3), dtype=float)
for fidx in range(5):
    train = fold != fidx
    test = fold == fidx
    model = RandomForest(n_estimators=120, max_depth=7, min_samples_leaf=3,
                         max_features=4, seed=20260929 + fidx)
    model.fit(X[train], y[train])
    proba[test] = model.predict_proba(X[test])

rf_threshold = np.where(proba[:, 2] >= 0.35, 2,
                        np.where(proba[:, 1] >= 0.20, 1, 0))
# A physical-veto policy treats the delivered physical grade as a lower risk bound.
hybrid_veto = np.maximum(rf_threshold, rule_pred)
uncertain = np.max(proba, axis=1) < 0.60
hybrid_review = hybrid_veto.copy()
hybrid_review[uncertain] = rule_pred[uncertain]

def extended(pred):
    result = metrics(y, pred)
    cm = np.asarray(result['cm'])
    result.update({
        'c_to_a': int(cm[2, 0]),
        'c_to_b': int(cm[2, 1]),
        'safe_loss': int(2 * cm[2, 0] + cm[2, 1]),
        'a_overestimate': int(cm[0, 1] + cm[0, 2]),
        'escalation_rate': float(np.mean(pred == 2)),
    })
    return result

result = {
    'rf_threshold': extended(rf_threshold),
    'hybrid_physical_veto': extended(hybrid_veto),
    'hybrid_uncertain_review_fallback': extended(hybrid_review),
    'review_rate': float(np.mean(uncertain)),
    'n_review': int(np.sum(uncertain)),
    'veto_changed': int(np.sum(hybrid_veto != rf_threshold)),
    'split': '5-fold grouped OOF; physical grade used only as decision-layer veto',
}
(OUT / 'hybrid_veto_results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
