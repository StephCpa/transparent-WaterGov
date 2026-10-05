"""Strict input gateway for legacy synthetic research, not an engineering rulebook.

Complete PPT875 inputs preserve the historical numeric results. Incomplete or
invalid input has no scalar score/grade. No engineering thresholds are changed.
This gateway deliberately accepts the complete 875 input profile only; genuine
not-applicable modes require a separate, calibrated chapter-6 configuration.
"""
from copy import deepcopy
from math import isfinite
from .baseline875 import load_baseline

REVISION = 'legacy-guard-v1-20260924'
NUMERIC = (
    '堤顶高程_m', '设计洪水位_m', '堤顶宽度_m', '外坡坡比', '内坡坡比',
    '渗透比降i', '堤身渗透比降i', '接触面渗透比降i',
    '背水坡FoS_正常', '临水坡FoS', '软基段_沉降量_cm',
    '软基段_沉降差_cm', '冲刷深度_m', '控制层Gs', '控制层e',
)
SIGNED = {'堤顶高程_m', '设计洪水位_m'}
QUAL_CODES = ('A4','A6','A8','A9','B2','B3','B4','C2','C6','D4','D5',
              'E1','E2','E3','E4','E5')
GRADES = ('A级_安全','B级_基本安全','C级_不安全')
BUILDING = {'一类','二类','三类','四类','1类','2类','3类','4类','加固','改建','重建'}


def _number(value, field, issues, *, positive=False, minimum=None, maximum=None):
    if value is None or value == '':
        issues.append({'field':field,'reason':'missing'})
        return
    if isinstance(value, bool) or not isinstance(value, (int,float)) or not isfinite(value):
        issues.append({'field':field,'reason':'finite_number_required'})
    elif (positive and value <= 0) or (minimum is not None and value < minimum) or (maximum is not None and value > maximum):
        issues.append({'field':field,'reason':'outside_input_domain'})


def _qual(value, code, safety, issues):
    if value is None or value == '':
        issues.append({'field':code,'reason':'missing'})
    elif isinstance(value, dict):
        keys = [k for k in ('score','得分','等级','状态','结论','类别') if k in value]
        if len(keys) != 1:
            issues.append({'field':code,'reason':'one_score_or_category_required'})
        else:
            _qual(value[keys[0]], code, safety, issues)
    elif isinstance(value, str) and value.strip() in safety.OPTIONAL_INDICATOR_SCORE_MAPS.get(code, {}):
        if value.strip() == '不涉及':
            issues.append({'field':code,'reason':'not_applicable_requires_mode_configuration'})
    else:
        try:
            parsed = float(value) if isinstance(value,str) else value
        except ValueError:
            parsed = None
        _number(parsed, code, issues, minimum=0, maximum=100)


def validate_inputs(sec, geo, buildings, history, leak):
    safety = load_baseline().safety
    issues = []
    if not isinstance(sec, dict):
        return [{'field':'section','reason':'object_required'}]
    stake = sec.get('桩号')
    if not isinstance(stake,str) or not stake.strip():
        issues.append({'field':'桩号','reason':'missing_or_invalid'})
    else:
        try:
            safety.parse_stake(stake)
        except ValueError:
            issues.append({'field':'桩号','reason':'invalid'})
    if type(sec.get('是否为湖堤')) is not bool:
        issues.append({'field':'是否为湖堤','reason':'explicit_boolean_required'})
    if sec.get('堤基类型') not in {'A','B','C','D'}:
        issues.append({'field':'堤基类型','reason':'explicit_known_category_required'})
    for key in NUMERIC:
        _number(sec.get(key), key, issues, minimum=None if key in SIGNED else 0)
    if isinstance(sec.get('控制层Gs'), (int,float)) and sec['控制层Gs'] <= 1:
        issues.append({'field':'控制层Gs','reason':'positive_critical_gradient_required'})
    if '堤身Gs' in sec or '堤身e' in sec:
        _number(sec.get('堤身Gs'),'堤身Gs',issues,minimum=1)
        _number(sec.get('堤身e'),'堤身e',issues,minimum=0)
        if isinstance(sec.get('堤身Gs'), (int,float)) and sec['堤身Gs'] <= 1:
            issues.append({'field':'堤身Gs','reason':'positive_critical_gradient_required'})
    if sec.get('控制渗透比降J_allow') is not None:
        _number(sec['控制渗透比降J_allow'],'控制渗透比降J_allow',issues,positive=True)
    optional = sec.get('待输入指标',{})
    if not isinstance(optional, dict):
        issues.append({'field':'待输入指标','reason':'object_required'})
        optional = {}
    for code in QUAL_CODES:
        _qual(optional.get(code,sec.get(code)),code,safety,issues)
    if 'A7' in optional or 'A7' in sec:
        _qual(optional.get('A7',sec.get('A7')),'A7',safety,issues)
    for name, records in [('geo',geo),('buildings',buildings),('history',history)]:
        if not isinstance(records,list) or any(not isinstance(row,dict) for row in records):
            issues.append({'field':name,'reason':'explicit_record_list_required'})
    if not issues:
        try:
            g = [r for r in geo if safety.stake_in_range(stake,r['起始桩号'],r['终止桩号'])]
            if not g or any(r.get('填土质量') not in {'质量较好','质量一般','质量较差'} for r in g):
                issues.append({'field':'A2','reason':'missing_or_invalid_matching_geology'})
            elif len({r['填土质量'] for r in g}) != 1:
                issues.append({'field':'A2','reason':'conflicting_geology'})
            b = [r for r in buildings if r.get('桩号') == stake]
            if not b or any(r.get('检测结论') not in BUILDING for r in b):
                issues.append({'field':'A3','reason':'missing_or_invalid_building_record'})
            elif len({r['检测结论'] for r in b}) != 1:
                issues.append({'field':'A3','reason':'conflicting_building_records'})
            for r in history:
                safety.stake_in_range(stake,r['起始桩号'],r['终止桩号'])
                if not isinstance(r.get('险情类型'),str) or type(r.get('是否已加固')) is not bool:
                    issues.append({'field':'history','reason':'explicit_event_type_and_treatment_required'})
        except (KeyError,TypeError,ValueError):
            issues.append({'field':'reference_records','reason':'malformed_range_or_record'})
    if not isinstance(leak,dict):
        issues.append({'field':'inspection','reason':'explicit_evidence_required'})
    else:
        for key in ('渗漏点数','加权渗漏点密度_点每100m'):
            _number(leak.get(key),key,issues,minimum=0)
        level=leak.get('UAV证据等级')
        if type(level) is not int or level not in range(4):
            issues.append({'field':'UAV证据等级','reason':'explicit_level_0_to_3_required'})
        if 'UAV门控等级上限' not in leak or leak.get('UAV门控等级上限') not in (None,*GRADES):
            issues.append({'field':'UAV门控等级上限','reason':'explicit_known_cap_required'})
    return issues


def _diagnostic(sec,geo,buildings,history,leak, *, c3_enabled,uav_gate_enabled):
    """C3-off uses its no-anomaly anchor with fixed weights, NOT a missing value."""
    m=load_baseline().model
    scores=m.score_dict(sec,sec['桩号'],geo,buildings,history,leak)
    if not c3_enabled:
        scores['C3']=100.0
    raw={'漫顶失效':m.overtopping_response(sec,scores),
         '渗流破坏':m.seepage_response(sec,scores),
         '边坡失稳':m.slope_response(sec,scores),
         '冲刷破坏':m.scour_response(scores),
         '穿堤建筑物失效':m.building_response(scores)}
    barrier,coverage=m.management_barrier(scores)
    adjusted=m.apply_barrier(raw,barrier,coverage)
    rho=m.shortboard_constrained_metric(adjusted)
    score=100*(1-rho)
    initial=m.grade_from_score(score)
    cap=leak['UAV门控等级上限'] if uav_gate_enabled else None
    after_uav=m.cap_grade_by_uav(initial,cap)
    grade,reasons=m.hard_constraint_gate(sec,scores,after_uav)
    return {'桩号':sec['桩号'],'安全得分':round(score,4),'安全等级':grade,
            '综合风险度量rho':round(rho,6),'模型原始等级':initial,
            'UAV门控后等级':after_uav,'硬约束门控原因':reasons,
            '主控失效模式':max(adjusted,key=adjusted.get),
            '二级指标得分':scores,'缺失指标':[]}


def evaluate_guarded(sec,geo,buildings,history,leak, *, c3_enabled=True,uav_gate_enabled=True):
    if type(c3_enabled) is not bool or type(uav_gate_enabled) is not bool:
        raise ValueError('diagnostic switches must be booleans')
    issues=validate_inputs(sec,geo,buildings,history,leak)
    base={'revision':REVISION,'snapshot_id':'ppt875-20260924',
          'engineering_validated':False,'intended_use':'legacy_synthetic_research',
          'issues':issues,'channels':{'c3_enabled':c3_enabled,'uav_gate_enabled':uav_gate_enabled}}
    if issues:
        return {**base,'status':'insufficient_or_invalid_input','result':None,
                'safety_score':None,'safety_grade':None,
                'interpretation':'No grade inferred from unavailable input; not evidence of safety.'}
    args=deepcopy((sec,geo,buildings,history,leak))
    if c3_enabled and uav_gate_enabled:
        result=load_baseline().model.evaluate_section(*args)
    else:
        result=_diagnostic(*args,c3_enabled=c3_enabled,uav_gate_enabled=uav_gate_enabled)
    assumptions=['Frozen physical thresholds and scoring are not engineering-calibrated.',
                 'J_allow is recorded but not used by the historical Terzaghi response.',
                 'C3 neutralization is an intervention, not a missing-data rule.']
    if '堤身Gs' not in sec:
        assumptions.append('Body Gs/e inherit control-layer values under the historical rule.')
    return {**base,'status':'evaluated','result':result,
            'safety_score':result['安全得分'],'safety_grade':result['安全等级'],
            'assumptions':assumptions}
