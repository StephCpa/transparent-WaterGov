"""Synthetic two-unit replay; explicit bridge, not an operational ingestion API."""
import json
from pathlib import Path
from .association import associate
from .core import evaluate
from .fixtures import case, event, rules


def run():
    units = [dict(unit_id=u, reference_id='synthetic-axis', geometry_version='v1',
                  chainage_m=b) for u, b in [('U1', [0, 50]), ('U2', [50, 100])]]
    contexts = [dict(context_id=u['unit_id']+'-ctx', unit_id=u['unit_id'],
                     model_version='synthetic-fixture-v1', basis_ref='synthetic fixed load',
                     valid_from='2026-09-20T10:00:00+08:00',
                     valid_to='2026-09-20T12:00:00+08:00',
                     available_at='2026-09-20T10:01:00+08:00') for u in units]
    assertion = dict(event(), reference_id='synthetic-axis', geometry_version='v1',
                     chainage_m=[49, 51], received_at='2026-09-20T10:40:00+08:00')
    snapshots = []
    for time in ['2026-09-20T10:30:00+08:00', '2026-09-20T11:00:00+08:00']:
        associations = associate([assertion], units, contexts, time)
        outputs = []
        for unit in units:
            c = case()
            c['unit_id'], c['as_of'] = unit['unit_id'], time
            for row in c['measurements']:
                row['unit_id'] = unit['unit_id']
            c['inspection']['unit_id'] = unit['unit_id']
            for record in associations['records']:
                if unit['unit_id'] not in record['candidate_units']:
                    continue
                # This fixture has one available, applicable context per unit.
                # General ingestion must also resolve context and mode applicability.
                c['events'].append(dict(assertion, unit_id=unit['unit_id'],
                    spatial_certainty='possible',
                    association_ref='synthetic://boundary-association-v1'))
            outputs.append(evaluate(c, rules()))
        snapshots.append(dict(as_of=time, associations=associations, evaluations=outputs))
    assert all(x['determined_grade'] == 0 for x in snapshots[0]['evaluations'])
    assert all(x['grade_range'] == [0, 3] and x['determined_grade'] is None
               for x in snapshots[1]['evaluations'])
    report = dict(engineering_validation=False, unique_observation_count=1,
                  snapshots=snapshots)
    output = Path(__file__).resolve().parents[1] / 'outputs'
    output.mkdir(exist_ok=True)
    (output/'association_replay.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (output/'空间歧义与迟到证据回放.md').write_text('''# 空间歧义与迟到证据回放

生成命令：`python -m transparent_eval.association_experiments`。

纯合成接口验证，非现场性能。一个已确认观测的桩号范围为49—51 m，
两个单元分界为50 m。观测10:15采集，10:40入库。

| 快照 | 可用事件数 | U1输出 | U2输出 |
|---|---|---|---|
| 10:30 | 0 | G0 | G0 |
| 11:00 | 1 | G0—G3，待定 | G0—G3，待定 |

早期G0仅反映当时合成输入，不能解释为后来证据证明其真实安全。
第二个快照的两个单元共享同一个观测ID，不是两起独立险情。
确认的是异常本身，空间归属仍待定，因此不对两个单元同时施加确定最高等级。
两个区间之间存在共享事件关联，不能当作独立样本或独立概率相乘。

本示例仅检查字段传递与回放语义。真实影像定位、跨帧归并、几何发布时间管理、
一般工况匹配与现场复核后空间归属修订流程仍需接入。
''', encoding='utf-8')
    print(json.dumps({'snapshots': len(snapshots), 'unique_observation_count': 1,
                      'engineering_validation': False}))


if __name__ == '__main__':
    run()
