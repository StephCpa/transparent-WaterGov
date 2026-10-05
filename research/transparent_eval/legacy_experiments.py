"""Reproduce the frozen baseline, diagnose channels, and check input boundaries.

No engineering accuracy, statistical significance, or calibrated thresholds are
estimated. Outputs are written only under research/outputs/ppt875_20260924.
"""
from collections import Counter
from copy import deepcopy
import csv
import hashlib
import json
from pathlib import Path
import sys
from .baseline875 import load_baseline,verify_snapshot
from .legacy_guard import evaluate_guarded,GRADES

REFERENCE={'safe':0,'slight':0,'moderate':1,'severe':2,'critical':2}
VARIANTS={'full':(True,True),'no_uav_gate':(True,False),
          'c3_neutral':(False,True),'both_neutral':(False,False)}


def metrics(reference,prediction):
    cm=[[0]*3 for _ in range(3)]
    for a,b in zip(reference,prediction):cm[a][b]+=1
    high=sum(a==2 for a in reference)
    low=sum(a<2 for a in reference)
    return {'n':len(reference),'correct':sum(cm[i][i] for i in range(3)),
            'accuracy':sum(cm[i][i] for i in range(3))/len(reference),
            'confusion_matrix':cm,'C_underestimated':sum(cm[2][:2]),
            'C_underestimation_rate':sum(cm[2][:2])/high if high else None,
            'non_C_to_C':sum(cm[i][2] for i in (0,1)),
            'non_C_to_C_rate':sum(cm[i][2] for i in (0,1))/low if low else None}


def source_row(sec,leak,r):
    return [str(v) for v in [sec['桩号'],sec['synthetic_target_mode'],sec['synthetic_severity'],
        r['安全得分'],r['安全等级'],r['模型原始等级'],r['综合风险度量rho'],r['主控失效模式'],
        sec['堤顶高程_m'],sec['渗透比降i'],sec['堤身渗透比降i'],sec['接触面渗透比降i'],
        sec['背水坡FoS_正常'],sec['临水坡FoS'],sec['冲刷深度_m'],
        leak['加权渗漏点密度_点每100m'],leak['UAV证据等级']]]


def run():
    manifest=verify_snapshot()
    b=load_baseline()
    samples,geo,buildings,history=b.generator.generate_dataset()
    table=[manifest['expected']['csv_header']]
    rows=[]; predictions={v:[] for v in VARIANTS}; refs=[]; counters=Counter()
    for sec,leak in samples:
        legacy=b.model.evaluate_section(sec,geo,buildings,history,leak)
        table.append(source_row(sec,leak,legacy))
        y=REFERENCE[sec['synthetic_severity']];refs.append(y)
        row={'sample_id':sec['桩号'],'target_mode':sec['synthetic_target_mode'],
             'severity':sec['synthetic_severity'],'reference':y}
        full=None
        for name,(c3,gate) in VARIANTS.items():
            r=evaluate_guarded(sec,geo,buildings,history,leak,
                               c3_enabled=c3,uav_gate_enabled=gate)
            if r['status']!='evaluated':raise AssertionError(r['issues'])
            if name=='full':
                full=r['result']
                if full!=legacy:raise AssertionError('complete-input baseline changed')
            pred=GRADES.index(r['safety_grade']);predictions[name].append(pred)
            row[name]=pred;row[name+'_score']=r['safety_score']
            if name!='full':
                counters[name+'_grade_changed']+=int(pred!=row['full'])
                counters[name+'_score_changed']+=int(r['safety_score']!=row['full_score'])
        counters['uav_stage_changes']+=int(full['模型原始等级']!=full['UAV门控后等级'])
        counters['hard_gate_stage_changes']+=int(full['UAV门控后等级']!=full['安全等级'])
        rows.append(row)
    digest=hashlib.sha256(json.dumps(table,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    if digest!=manifest['expected']['csv_table_sha256']:
        raise AssertionError('875-row table differs from the frozen original CSV')
    totals={name:metrics(refs,ys) for name,ys in predictions.items()}
    if totals['full']['confusion_matrix']!=manifest['expected']['confusion_matrix']:
        raise AssertionError('reference matrix changed')
    by_mode={}
    for mode in b.generator.TARGET_MODES:
        selected=[i for i,row in enumerate(rows) if row['target_mode']==mode]
        by_mode[mode]={v:metrics([refs[i] for i in selected],
                                [predictions[v][i] for i in selected]) for v in VARIANTS}
    boundary=[]
    base,leak=deepcopy(samples[250])
    for field in ('堤身渗透比降i','接触面渗透比降i','控制层Gs','软基段_沉降量_cm'):
        changed=deepcopy(base);changed.pop(field)
        guarded=evaluate_guarded(changed,geo,buildings,history,leak)
        boundary.append({'case':'missing:'+field,'status':guarded['status'],
                         'grade':guarded['safety_grade'],'issues':guarded['issues']})
    # Independent inspection changes, constructed for mechanism checks only.
    s,l=deepcopy(samples[0])
    l.update({'渗漏点数':5,'加权渗漏点密度_点每100m':5.,
              'UAV证据等级':3,'UAV门控等级上限':'C级_不安全'})
    conflict={v:evaluate_guarded(s,geo,buildings,history,l,
                  c3_enabled=c3,uav_gate_enabled=gate)['safety_grade']
              for v,(c3,gate) in VARIANTS.items()}
    allowed=[]
    for value in (0.05,0.25,1.0):
        s,l=deepcopy(samples[250]);s['控制渗透比降J_allow']=value
        s['土层参数'][0]['允许渗透比降J_allow']=value
        r=evaluate_guarded(s,geo,buildings,history,l)
        allowed.append({'J_allow':value,'score':r['safety_score'],'grade':r['safety_grade']})
    summary={'snapshot_id':manifest['snapshot_id'],'python':sys.version.split()[0],
       'engineering_validation':False,'sample_count':len(rows),
       'complete_input_parity':True,'original_csv_canonical_sha256':digest,
       'reference_rule':REFERENCE,'variant_definitions':{
        'full':'Frozen legacy evaluation through strict input gateway.',
        'no_uav_gate':'Disable only the final UAV category cap.',
        'c3_neutral':'Replace C3 with the no-anomaly anchor 100; keep weights fixed.',
        'both_neutral':'Apply both interventions; not a claim of no inspection in every other input.'},
       'metrics':totals,'changes_vs_full':dict(counters),'by_target_mode':by_mode,
       'missing_input_checks':boundary,'constructed_low_physics_high_observation':conflict,
       'J_allow_path_check':allowed,
       'limitations':['Synthetic severity-derived reference, not independent field truth.',
         'C3 neutralization is not missingness and is not feature removal with reweighting.',
         'Other indicators may also encode observation/history; both_neutral isolates only the two explicit UAV/C3 channels.',
         'No A/B/C to G0-G3 conversion or new engineering threshold is introduced.']}
    out=Path(__file__).resolve().parents[1]/'outputs'/'ppt875_20260924'
    out.mkdir(parents=True,exist_ok=True)
    (out/'ablation_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with (out/'ablation_cases.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    with (out/'baseline_reproduced.csv').open('w',encoding='utf-8-sig',newline='') as f:
        csv.writer(f).writerows(table)
    print(json.dumps({'sample_count':len(rows),'baseline_parity':True,
       'metrics':totals,'changes':dict(counters),'constructed_conflict':conflict},ensure_ascii=False,indent=2))
    return summary


if __name__=='__main__':run()
