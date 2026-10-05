"""Analytic postprocessing experiments, independent of any engineering solver."""
import json
from pathlib import Path
from .hydraulics import extract_section, exit_ratio
from .core import evaluate
from .fixtures import case, rules


def grid(n, field, *, datum=0):
    nodes=[{"id":f"{i}:{j}","x":i/n,"z":j/n+datum,"value":field(i/n,j/n)+datum}
           for i in range(n+1) for j in range(n+1)]
    elements=[]
    for i in range(n):
        for j in range(n):
            a,b,c,d=f"{i}:{j}",f"{i+1}:{j}",f"{i+1}:{j+1}",f"{i}:{j+1}"
            for label,ids in [("a",[a,b,c]),("b",[a,c,d])]:
                elements.append({"id":f"{i}:{j}:{label}","node_ids":ids,"material_id":"analytic_homogeneous",
                                 "conductivity":[1e-5,0,1e-5]})
    return {"unit_id":"SYNTHETIC-U01","case_id":"SYNTHETIC-STEADY-01","model_version":"analytic-interpolant-v1",
            "crs":"local_x_z","vertical_datum":"local_zero","source_ref":"analytic://prescribed_head_field",
            "coordinate_units":"m","conductivity_units":"m/s","field_kind":"total_head_m",
            "nodes":nodes,"elements":elements,"exit_edges":[[f"{n}:{j}",f"{n}:{j+1}"] for j in range(n)]}


def run():
    root=Path(__file__).resolve().parents[1];out=root/"outputs";out.mkdir(exist_ok=True)
    linear=extract_section(grid(4,lambda x,z:10-x))
    hydro=extract_section(grid(4,lambda x,z:10))
    shifted=extract_section(grid(4,lambda x,z:10-x,datum=100))
    refinements=[]
    for n in [2,4,8,16,32]:
        extracted=extract_section(grid(n,lambda x,z:10-x*x+z*z))
        errors=[abs(e["outward_head_gradient"]-2) for e in extracted["exit_edges"]]
        refinements.append({"n":n,"n_triangles":2*n*n,"max_exit_gradient_error":max(errors),
                            "expected_error":1/n})
    ratios=exit_ratio(linear,[.8,1.2],"synthetic://allowable-interval",normal_criterion_confirmed=True)
    c=case();c["model_version"]=linear["model_version"]
    row=c["measurements"][0];row.update({"value":ratios["value"],"source_ref":ratios["source_ref"],
                                        "evidence_ids":["ANALYTIC-RIGHT-BOUNDARY"]})
    assessment=evaluate(c,rules())
    summary={"evidence_type":"analytic_postprocessing_not_engineering_validation",
             "linear_gradient_max_error":max(abs(e["outward_head_gradient"]-1) for e in linear["exit_edges"]),
             "linear_selected_flux_m2_s":linear["selected_boundary_flux_m2_s"],
             "hydrostatic_selected_flux_m2_s":hydro["selected_boundary_flux_m2_s"],
             "datum_shift_flux_difference":shifted["selected_boundary_flux_m2_s"]-linear["selected_boundary_flux_m2_s"],
             "refinement":refinements,"ratio":ratios,"evaluation":assessment}
    (out/"hydraulic_experiments.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    lines=["# 水头场后处理与评价接入验证", "", "运行：`python -m transparent_eval.hydraulic_experiments`。",
           "", "输入为单位正方形上的解析总水头场、各向同性K=10⁻⁵ m/s。仅验证后处理与数据接入；未进行渗流求解，也未模拟真实堤防。右边界是指定水头的计算检查边界，不是零压力自由渗出面。",
           "", f"- H=10−x：出口法向梯度真值1，最大误差{summary['linear_gradient_max_error']:.3g}；单位宽度边界出流量{summary['linear_selected_flux_m2_s']:.6g} m²/s。",
           f"- H=10：静水总水头场，边界出流量{summary['hydrostatic_selected_flux_m2_s']:.3g} m²/s。",
           f"- 同时将z与H平移100 m：出流量变化{summary['datum_shift_flux_difference']:.3g} m²/s。",
           "", "## 网格细化检验", "", "解析场H=10−x²+z²为均质各向同性条件下的调和场。右边界精确法向梯度为2；线性三角形从节点重建的边界梯度为2−1/n，因此最大误差应为1/n。此处检验的是插值求导误差，不是求解器收敛阶。",
           "", "| 每方向划分数n | 三角形数 | 实测梯度误差 | 理论插值误差 |", "|---|---|---|---|"]
    lines += [f"| {r['n']} | {r['n_triangles']} | {r['max_exit_gradient_error']:.6g} | {r['expected_error']:.6g} |" for r in refinements]
    lines += ["", "## 接入评价核心", "", f"线性场梯度1、示例允许梯度区间[0.8,1.2]得到比值[{ratios['value'][0]:.6g},{ratios['value'][1]:.6g}]；其他指标使用既有合成情景输入。输出研究类别范围为G{assessment['grade_range'][0]}—G{assessment['grade_range'][1]}，确定类别为{assessment['determined_grade']}。",
              "", "允许梯度区间纯为接口测试示例。该比值范围只传播分母范围，尚不包含网格、地层及水头误差。实际数据应以多网格/多参数场计算并保留各自结果。",
              "", "各向异性张量可计算达西通量，但程序不把其法向水头梯度直接转成上述简单评价比值。物理判据适用性需单独确定。"]
    (out/"水头场后处理验证报告.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps({k:summary[k] for k in ["linear_gradient_max_error","hydrostatic_selected_flux_m2_s","datum_shift_flux_difference"]}))


if __name__=="__main__":run()
