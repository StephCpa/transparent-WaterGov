"""Reproducible algebra and behavior checks. Not engineering validation."""
from copy import deepcopy
import json
from pathlib import Path
import random
import unittest

from .core import evaluate
from .fixtures import rules, scenarios


def hierarchy_check(seed=20260921, repeats=1000):
    rng = random.Random(seed)
    error, amplification = 0.0, None
    for _ in range(repeats):
        n,m=5,3
        raw=[rng.random()+.05 for _ in range(n)]
        w=[v/sum(raw) for v in raw]
        a=[[rng.randint(1,3) for _ in range(m)] for _ in range(n)]
        r=[rng.random() for _ in range(n)]
        q=[sum(w[i]*a[i][j] for i in range(n)) for j in range(m)]
        mode_w=[v/sum(q) for v in q]
        b=[sum(w[i]*a[i][j]*r[i] for i in range(n))/q[j] for j in range(m)]
        nested=sum(x*y for x,y in zip(mode_w,b))
        collapsed=sum(w[i]*sum(a[i])*r[i] for i in range(n))/sum(q)
        error=max(error,abs(nested-collapsed))
        if amplification is None:
            amplification={"original_weights":w,"effective_weights":[w[i]*sum(a[i])/sum(q) for i in range(n)],
                           "row_sums":[sum(row) for row in a]}
    return {"seed":seed,"repeats":repeats,"max_absolute_identity_error":error,
            "assumption":"W_m proportional to sum_i w_i*a_im; no nonlinear correction",
            "example":amplification}


def run():
    root=Path(__file__).resolve().parents[1]
    out=root/"outputs";out.mkdir(exist_ok=True)
    cases=scenarios();cfg=rules()
    (root/"configs"/"synthetic_cases.json").write_text(json.dumps([c for _,c in cases],ensure_ascii=False,indent=2),encoding="utf-8")
    results=[]
    for name,c in cases:
        full=evaluate(c,cfg)
        no_physical=deepcopy(cfg)
        for spec in no_physical["indicators"].values():spec.pop("constraint",None)
        no_observation=deepcopy(c);no_observation["events"]=[]
        results.append({"scenario":name,"full":full,
                        "without_physical_constraint":evaluate(c,no_physical),
                        "without_observation":evaluate(no_observation,cfg)})
    algebra=hierarchy_check()
    suite=unittest.defaultTestLoader.discover(str(root/"tests"))
    with (out/"test_log.txt").open("w",encoding="utf-8") as log:
        test_result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    summary={"experiment_type":"synthetic_implementation_and_algebra_only",
             "engineering_validation":False,"rule_id":cfg["rule_id"],
             "algebra":algebra,"n_scenarios":len(results),"tests_run":test_result.testsRun,
             "tests_passed":test_result.wasSuccessful(),"results":results}
    (out/"implementation_experiments.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    lines=["# 评价原型：公式与实现验证记录", "", "本报告由 `python -m transparent_eval.experiments` 生成。",
           "", "所有输入、分级阈值和约束均为程序验证示例，不是工程数据，不用于现场安全判断。本报告不计算工程准确率。",
           "", f"- 单元/性质测试：{test_result.testsRun}项，{'全部通过' if test_result.wasSuccessful() else '存在失败，见test_log.txt'}。",
           f"- 公式等价检查：固定随机种子{algebra['seed']}，{algebra['repeats']}组正权重/关联矩阵；两层加权与展开公式的最大绝对差为{algebra['max_absolute_identity_error']:.3g}。",
           "- 等价结论以模式权重由关联加权总量归一化得到为前提；PPT未提供该步骤完整公式，不能认定前期实现一定使用了这一形式。",
           "", "| 合成情景 | 指数范围 | 可能等级 | 确定等级 | 数据充分 | 去物理约束后的等级范围 | 去观测后的等级范围 |",
           "|---|---|---|---|---|---|---|"]
    for row in results:
        v=row["full"];lo,hi=v["score_interval"]
        label="待补证据/跨等级" if v["determined_grade"] is None else f"G{v['determined_grade']}"
        fmt=lambda r:f"G{r[0]}—G{r[1]}"
        lines.append(f"| {row['scenario']} | {lo:.3f}—{hi:.3f} | {fmt(v['grade_range'])} | {label} | {'是' if v['evidence_sufficient'] else '否'} | {fmt(row['without_physical_constraint']['grade_range'])} | {fmt(row['without_observation']['grade_range'])} |")
    lines += ["", "## 解读", "", "1. S02显示局部物理约束可以独立于显示总分约束最终类别。这是构造性质，不是工程改进证据。",
              "2. S03的物理比值跨过示例阈值，输出可能等级范围；不把可能超限当作确定超限。",
              "3. S04/S05不把缺失或不可用数据补零；固定原权重、传播[0,1]未知响应。",
              "4. S06疑似观测要求复核，不直接认定为最高等级；低计算指数也不据此给出确定低等级。",
              "5. S07—S09证明重复观测不会重复累加危险程度。事件是否为同一物理对象仍需上游关联。",
              "6. S10/S16中未解除的确认事件保留约束，即使模型或巡检数据已过期/缺失；数据充分性仍显示为否。",
              "7. S11仅检验有依据的显式解除流程；现实中是否可以解除由现场复核与工程条件决定。",
              "8. S12以当时实际入库的信息回放，防止迟到记录泄漏到更早预测。",
              "9. G0—G3均为研究原型中的有序标签，不对应规范工程综合安全类别。",
              "", "## 尚未完成", "", "原始场数据到指标的工程适用转换、实际时空配准、现场参数校准、独立工程测试、非稳态渗流求解和在线平台联调仍待实施。"]
    (out/"公式与实现验证报告.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps({k:summary[k] for k in ["n_scenarios","tests_run","tests_passed"]}))
    if not test_result.wasSuccessful():raise SystemExit(1)


if __name__=="__main__":run()
