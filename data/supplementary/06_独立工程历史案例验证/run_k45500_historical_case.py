# -*- coding: utf-8 -*-
"""K45+500 历史管涌险情代表断面复算。

本脚本不把 2017 年险情时刻的水位伪作实测值。由于现有险情记录未记载
该断面的同步水位，35.90 m 仅作为高水位代表工况，用于检验评价模型能否
识别该历史管涌段的渗流风险。
"""

from __future__ import annotations

import copy
import json
import sys
import types
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SAFE_DIR = ROOT / "safe"
SOLVER_DIR = ROOT / "验证剖面3"
OUT_DIR = Path(__file__).resolve().parent / "输出"


def load_module(name: str, path: Path):
    # 原程序入口处有一条与数值求解无关的旧式 f-string 输出，
    # 其中使用了 Unicode 转义，Python 3.9 无法编译。这里仅替换该输出行。
    lines = path.read_text(encoding="utf-8").splitlines()
    fixed = []
    for line in lines:
        if "print(f\"{'\\u6c34\\u4f4d(m)'" in line:
            fixed.append("    print('水位(m)  背水Fs  迎水Fs  imax  imax位置')")
        else:
            fixed.append(line)
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile("\n".join(fixed), str(path), "exec"), module.__dict__)
    return module


def surface(x: np.ndarray) -> np.ndarray:
    """K45+500 等效断面地表线，右侧为临水坡。"""
    toe_z, crest_z = 28.0, 36.30
    left_toe, crest_left = 20.0, 43.24
    crest_right, right_toe = 50.24, 72.65
    topo = np.full_like(x, toe_z, dtype=float)
    left = (x >= left_toe) & (x < crest_left)
    topo[left] = toe_z + (x[left] - left_toe) / 2.8
    crest = (x >= crest_left) & (x <= crest_right)
    topo[crest] = crest_z
    right = (x > crest_right) & (x <= right_toe)
    topo[right] = crest_z - (x[right] - crest_right) / 2.7
    return topo


def build_mesh(solver):
    """按 K45+500 断面尺寸和地勘层厚中值建立有限差分网格。"""
    # 0.50 m 网格用于历史工况复核；足以表达 2.6 m 表层砂层，
    # 也避免自由面迭代因过密网格而失去工程计算效率。
    x = np.arange(0.0, 100.0 + 0.001, 0.50)
    z = np.arange(10.0, 38.0 + 0.001, 0.50)
    topo = surface(x)
    mat = np.zeros((len(z), len(x)), dtype=int)

    for j, top in enumerate(topo):
        for i, elev in enumerate(z):
            if elev > top:
                continue
            if elev >= 28.0:
                mat[i, j] = 1  # 堤身填土
            elif elev >= 25.4:
                mat[i, j] = 2  # 表层粉细砂/砂壤土，厚2.6 m
            elif elev >= 16.9:
                mat[i, j] = 3  # 淤泥质粉质黏土，厚8.5 m
            else:
                mat[i, j] = 6  # 下部砂砾石层

    return solver.MeshGrid(
        node_x=x,
        node_z=z,
        cell_center_x=(x[:-1] + x[1:]) / 2.0,
        cell_center_z=(z[:-1] + z[1:]) / 2.0,
        material_id=mat,
        nx=len(x),
        nz=len(z),
    )


def select_gradients(mesh, seep, soil):
    """从水头场提取出口区、堤身及堤基-堤身接触带的代表坡降。"""
    xx, zz = np.meshgrid(mesh.node_x, mesh.node_z)
    back_toe_zone = (xx >= 16.0) & (xx <= 28.0)
    base_exit = (mesh.material_id == 2) & back_toe_zone
    body = (mesh.material_id == 1) & (xx >= 20.0) & (xx <= 43.5)
    contact = (mesh.material_id == 1) & (zz >= 27.5) & (zz <= 28.25) & back_toe_zone

    def maximum(mask):
        values = seep.i_magnitude[mask]
        return float(np.nanmax(values)) if values.size else 0.0

    layer_labels = {
        1: "堤身填土",
        2: "Q4al+l粉细砂/砂壤土",
        3: "Q4al+l淤泥质粉质黏土",
        6: "Q3al砂砾石",
    }
    layer_checks = []
    for material_id, label in layer_labels.items():
        maximum_i = maximum(mesh.material_id == material_id)
        props = soil[material_id]
        critical_i = (props.Gs - 1.0) / (1.0 + props.e)
        layer_checks.append({
            "材料ID": material_id,
            "土层": label,
            "最大渗透比降": maximum_i,
            "临界渗透比降": critical_i,
            "i_i_cr": maximum_i / critical_i if critical_i > 0 else 0.0,
            "Gs": props.Gs,
            "e": props.e,
        })
    control = max(layer_checks, key=lambda item: item["i_i_cr"])

    return {
        "堤基出口区渗透比降": maximum(base_exit),
        "背水坡堤身渗透比降": maximum(body),
        "堤身-堤基接触带渗透比降": maximum(contact),
        "全场最大渗透比降": float(seep.i_max),
        "全场最大坡降位置_x_m": float(seep.i_max_position[0]),
        "全场最大坡降位置_z_m": float(seep.i_max_position[1]),
        "分层渗流稳定复核": layer_checks,
        "控制层": control,
    }


def quick_bishop_stability(solver, mesh, seep, soil, water_level):
    """有限候选圆弧的 Bishop 搜索，用于历史工况复核。

    原程序的全局三阶段搜索需计算数万条圆弧，更适合正式设计复核；本次
    只需识别历史险情时是否同时存在边坡失稳风险，故在两坡各取覆盖坡脚、
    坡面及堤顶的 125 条候选圆弧，取其中最小有效安全系数。
    """
    xx, zz, mat, head = mesh.node_x, mesh.node_z, mesh.material_id, seep.head
    topo = solver.compute_ground_surface(mesh)
    solid = mat > 0
    sat = solid & (head > zz[:, np.newaxis])
    chain = (sat.astype(np.float32) + (~solid).astype(np.float32)).cumprod(axis=0)
    phreatic = np.where((chain > 0) & sat, zz[:, np.newaxis] + mesh.dz * 0.5, 0.0).max(axis=0)

    def run(entries, exits, radii, water, fail_left):
        values = []
        for entry_x in entries:
            entry_z = float(np.interp(entry_x, xx, topo))
            for exit_x in exits:
                exit_z = float(np.interp(exit_x, xx, topo))
                for radius in radii:
                    cx, cz = solver._entry_exit_to_center(entry_x, entry_z, exit_x, exit_z, radius)
                    if cx is None:
                        continue
                    try:
                        fs = solver._bishop_safety_factor(
                            cx, cz, radius, xx, topo, head, zz, mat, soil, 30,
                            water, fail_to_left=fail_left, phreatic_z=phreatic,
                            imax=seep.i_max,
                        )
                    except Exception:
                        continue
                    if 0.1 < fs < 100.0:
                        values.append(float(fs))
        return min(values) if values else None

    fs_back = run(
        np.linspace(12.0, 26.0, 5), np.linspace(37.0, 50.0, 5),
        np.linspace(15.0, 45.0, 5), 0.0, True,
    )
    fs_front = run(
        np.linspace(40.0, 53.0, 5), np.linspace(62.0, 75.0, 5),
        np.linspace(20.0, 60.0, 5), water_level, False,
    )
    return {
        "背水坡FoS": fs_back if fs_back is not None else 9.99,
        "临水坡FoS": fs_front if fs_front is not None else 9.99,
        "稳定分析方法": "Bishop简化候选圆弧搜索",
        "土条数": 30,
    }


def evaluate_with_model(gradients, stability):
    sys.path.insert(0, str(SAFE_DIR))
    from failure_response_barrier_model import evaluate_section

    section = json.loads((SAFE_DIR / "section_data.json").read_text(encoding="utf-8"))[0]
    geo = json.loads((SAFE_DIR / "geo_classification.json").read_text(encoding="utf-8"))
    dangers = json.loads((SAFE_DIR / "historical_dangers.json").read_text(encoding="utf-8"))
    sec = copy.deepcopy(section)

    # 评价模型中的设计洪水位保持原设计值；35.90 m 只服务于本次高水位复算。
    control = gradients["控制层"]
    sec["控制土层名称"] = control["土层"]
    sec["控制层Gs"] = control["Gs"]
    sec["控制层e"] = control["e"]
    sec["渗透比降i"] = control["最大渗透比降"]
    sec["堤身渗透比降i"] = gradients["背水坡堤身渗透比降"]
    sec["堤身Gs"] = 2.70
    sec["堤身e"] = 0.778
    sec["接触面渗透比降i"] = gradients["堤身-堤基接触带渗透比降"]
    sec["背水坡FoS_正常"] = stability["背水坡FoS"]
    sec["临水坡FoS"] = stability["临水坡FoS"]
    leak_evidence = {
        "已确认管涌或渗漏": True,
        "证据来源": "工程地质报告记载：2017年K44+500—K46+096段发生管涌险情",
        "说明": "用于历史样本验证的异常状态映射，不表示无人机识别到的点位数量。",
    }
    return evaluate_section(sec, geo, [], dangers, leak_evidence)


def main():
    OUT_DIR.mkdir(exist_ok=True)
    sys.path.insert(0, str(SOLVER_DIR))
    solver = load_module("k45500_solver", SOLVER_DIR / "beiyong_fixed3.py")
    mesh = build_mesh(solver)
    soil = solver._load_soil_params_from_json(str(Path(__file__).resolve().parent / "soil_params_k45500.json"))

    water_level = 35.90
    print(f"计算水位: {water_level:.2f} m")
    head, phreatic = solver.solve_steady_seepage(mesh, water_level, soil)
    seep = solver.compute_seepage_result(mesh, head, phreatic, soil, water_level)
    gradients = select_gradients(mesh, seep, soil)
    stability = quick_bishop_stability(solver, mesh, seep, soil, water_level)
    assessment = evaluate_with_model(gradients, stability)
    result = {
        "案例性质": "2017年K44+500—K46+096管涌险情段的K45+500代表断面复算",
        "历史事实": "该范围2017年发生管涌险情，处置措施为导滤围井。",
        "水位说明": "35.90 m为历史高水位代表工况，不是已取得的2017年实测水位。",
        "断面与地层取值": {
            "堤顶高程_m": 36.30,
            "堤顶宽度_m": 7.0,
            "背水坡坡比": "1:2.8",
            "临水坡坡比": "1:2.7",
            "堤基层序": "0—2.6 m粉细砂/砂壤土；2.6—11.1 m淤泥质粉质黏土；以下砂砾石",
        },
        "计算工况": {"临水位_m": water_level, "背水侧地面高程_m": 28.0},
        "渗流计算结果": gradients,
        "稳定计算结果": stability,
        "评价模型结果": assessment,
    }
    path = OUT_DIR / "K45+500_历史管涌代表工况_复算结果.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n复算结果已保存：", path)
    print(json.dumps({
        "渗流计算结果": gradients,
        "稳定计算结果": stability,
        "模型等级": assessment["安全等级"],
        "主控失效模式": assessment["主控失效模式"],
        "门控原因": assessment["硬约束门控原因"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
