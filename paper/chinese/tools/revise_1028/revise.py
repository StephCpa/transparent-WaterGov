"""Apply the 2026-10-28 revision list to an unpacked copy of the 1028 thesis.

    python3 revise.py <unpacked_dir> <track|clean> <fig5_5.png> <fig5_20.png> <fig5_24.png>

Element indices refer to the body of the original 1028 document (after merge_runs); all targets are
resolved before any edit, so insertions do not shift them.
"""
import copy
import shutil
import sys
from pathlib import Path

from lxml import etree
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from docxedit import W, Editor, make_runs, strip_ids, styled_rpr  # noqa: E402
FIGDIR = next(d for d in Path(__file__).resolve().parents if (d / "paper" / "chinese").is_dir()) / "paper" / "chinese" / "chapters" / "figures_ch5_thesis"

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
WP = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"

root, mode, fig55, fig520, fig524 = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4]), Path(sys.argv[5])
doc_path = root / "word" / "document.xml"
doc = etree.parse(str(doc_path))
body = doc.getroot().find(W + "body")
E = list(body)
ed = Editor(track=(mode == "track"))


def cell(tbl_idx, r, c):
    return E[tbl_idx].findall(W + "tr")[r].findall(W + "tc")[c].find(W + "p")


# ---------------------------------------------------------------- 1. Sec. 1.2.3, last paragraph
ed.replace(E[50],
    "单一方法难以同时兼顾可解释性与精度：确定性加权类方法过程透明但本质上是静态的，概率与机器学习类方法具备动态更新能力但依赖大量数据支撑。这一对比表明，发展“机理约束+数据驱动”的混合评价模型是必要的。",
    "单一方法难以同时兼顾可解释性与精度。确定性加权类方法过程透明，但本质上是静态的；概率与机器学习类方法具备动态更新能力，但依赖大量数据支撑，其结论也不一定满足渗流机理与规范判据的要求。这一对比表明，有必要发展以渗流机理与规范判据为约束、以数据驱动模型为补充的混合评价模型，使数据驱动模型只能在机理判据的基础上修正评价结论，而不能放松机理判据给出的安全底线。")

# ---------------------------------------------------------------- 2. Sec. 1.3 item (3)
ed.rewrite(E[59],
    "（3）现有评价多以规范赋分与确定性计算为主，难以纳入动态巡检信息，亦难以刻画堤防安全状态随水位变化与隐患发展的演化过程，主控失效模式识别能力不足{sup:[110,116,139]}。为此，本文首先将渗流计算结果与巡检结果统一表征为携带来源、时间、空间范围与证据状态的评价证据，使巡检信息得以可追溯地进入评价；其次，依据规范导则规定的优先级确定指标基础权重，借助“指标—失效模式”关联矩阵识别主控失效模式，以运行管理能力为安全屏障修正中间风险，并通过物理临界与巡检观测双重门控避免临界指标被平均化处理；最后，用物理规则约束随机森林学习模型的修正方向，构建可随水位工况与巡检证据滚动更新的动态透明评价模型，使评价结论兼具物理机理与现场证据的双重支撑。")

# ---------------------------------------------------------------- 3. Chapter 5 introduction
ed.rewrite(E[1132],
    "堤防渗流安全评价是连接渗流机理分析与工程管理决策的关键环节。第4章给出了多水位工况下的水头场、出逸梯度与潜在管涌通道，本章以此为机理依据开展透明评价。然而，计算结果反映的是堤防内部的渗流状态，表面已出现的渗漏迹象还需依靠现场观测获取，因此还需将无人机巡检结果纳入评价。之所以要将二者结合，是因为现有评价方法还存在三个方面的不足。一是机理计算与现场观测相互割裂，无人机巡检目前仍主要作为独立的隐患发现手段使用，其发现的渗漏迹象缺少与地质体、渗流场的空间关联和面向评价的定量表达，尚未成为可以量化、可追溯的证据输入{sup:[23,28]}。二是评价以静态加权汇总为主，综合得分容易掩盖个别达到临界状态的指标，难以识别主控失效模式及其风险来源{sup:[139,158]}。三是缺乏随水位变化、巡检发现和复核结果滚动更新的机制{sup:[140]}，而且现有评价通常只记录指标取值，不记录取值背后的证据状况。例如，已巡查未见异常与尚未巡查在评价表中往往同样记为“无异常”，算法检出的可疑目标与现场确认的管涌也常被同等对待，前者会使评价偏于乐观，后者则可能因误报造成不必要的降级。")
ed.rewrite(E[1133],
    "针对上述不足，围绕第1章提出的第二个关键科学问题，即如何融合三维渗流场定量计算结果与无人机巡检实景病害信息、建立堤防渗流安全动态透明评价方法，本章以第2章阐述的红外热成像探测机理、目标检测理论、临界水力比降判据和失效模式关联评价理论为基础开展研究。首先，将渗流计算指标与巡检病害信息统一表达为带有来源、时间、空间范围和证据状态的评价证据，构建评价框架与指标体系，使两类信息能够在同一尺度上比较和追溯。其次，提出指标量化与赋权方法以及无人机巡检识别、空间配准与证据接入方法，并以失效模式关联和门控规则突出最危险环节。然后，建立物理规则链与随机森林相结合、以序数物理下限约束学习模型的评价模型，采用多目标策略评价选定模型的运行参数，并通过分步实施流程使评价能够随水位工况、巡检发现和复核结论更新。最后，以受控情景记录、工程历史险情断面、第4章渗流计算成果和真实巡检候选四类资料构成六个案例，对评价方法进行检验。")

# ---------------------------------------------------------------- 5. "评价时刻" -> 资料截止时间
ed.rewrite(E[1138],
    "本章的评价对象为指定水位工况下、依据截至某一时点（下称“资料截止时间”）已入库资料所判定的堤段渗流安全状态。堤段以代表断面表示，并对应堤轴线上确定的桩号区间；水位工况与渗流计算采用的水位一致；资料截止时间随评价结论一并记录，新资料入库后即触发新一轮评价。按此定义，同一断面在不同水位工况或不同资料截止时间下可以得到不同的结论，每一个评价结果都有明确的适用条件，并可依据同一批资料重复计算。")
ed.replace(E[1157], "同一时刻", "同一资料截止时间")
ed.replace(cell(1160, 1, 2), "评价时刻", "资料截止时间")
ed.replace(E[1161], "以水位工况和评价时刻确定评价单元", "以水位工况和资料截止时间确定评价单元")
ed.replace(E[1319], "在评价时刻前已入库的记录参与评价，迟到记录只进入之后的评价", "在资料截止时间前已入库的记录参与评价，迟到记录进入下一轮评价")
ed.replace(cell(1155, 1, 2), "评价时刻", "资料截止时间")

# ---------------------------------------------------------------- 6/7. Table 5-1 and the paragraph after it
t51 = E[1142]
grid = t51.find(W + "tblGrid").findall(W + "gridCol")
t51.find(W + "tblGrid").remove(grid[2])
widths = ["2200", "7206"]
for g, w in zip(grid[:2], widths):
    g.set(W + "w", w)
for tr in t51.findall(W + "tr"):
    tcs = tr.findall(W + "tc")
    tr.remove(tcs[2])
    for tc, w in zip(tcs[:2], widths):
        tc.find(W + "tcPr/" + W + "tcW").set(W + "w", w)
ed.replace(cell(1142, 1, 1), "评价时刻", "资料截止时间")
ed.replace(cell(1142, 3, 1), "安全等级与主控失效模式",
           "安全等级，即A级（安全）、B级（基本安全）或C级（不安全），证据不足时给出等级范围；主控失效模式")
ed.rewrite(E[1143],
    "表5-1的五项要素中，评价结论是最直接的输出，其中安全等级给出堤段的安全状态，主控失效模式说明风险的主要来源；其余四项分别说明结论在什么条件下成立、依据哪些资料、因何得出以及还需要补充什么。资料不完整时，只要已取得的关键指标足以触发门控，评价仍可以给出确定等级；反之，即使大部分指标已有取值，关键证据缺失时也只能给出等级范围或“证据不足”。由此可见，评价结论的完整性与资料的完整性并不等同，评价需要同时说明结论是什么以及结论在多大程度上依赖尚未取得的资料。")

# ---------------------------------------------------------------- 8. warning colours (Tables 5-2, 5-18, Sec. 5.3.1.4, Chapter 6)
ed.replace(cell(1155, 8, 2), "一级（红）、二级（橙）、三级（黄）或常规，附响应建议",
           "一级、二级、三级或常规，附响应建议；显示颜色见表5-18")
ed.replace(cell(1375, 1, 0), "（红）", "（红色）")
ed.replace(cell(1375, 2, 0), "（橙）", "（琥珀色）")
ed.replace(cell(1375, 3, 0), "（黄）", "（琥珀色）")
ed.insert_after(cell(1375, 4, 0), "常规", "（蓝色）")
ed.insert_after(E[1372], "或存在巡检候选时转人工复核。",
    "平台显示时，预警与安全等级共用红色、琥珀色和蓝色三种色相，一级预警为红色，二级、三级预警为琥珀色并以文字标注区分，常规状态为蓝色。")
ed.replace(E[1723],
    "平台上呈现的等级与第五章表5-16的三级划分对应，并在界面上以一级安全、二级警戒与三级危险命名，分别以绿色、黄色与红色标识，与主页预警事件面板、堤段统计徽标使用同一套色标。",
    "平台上呈现的等级与第五章表5-16的三级划分一一对应，界面直接采用A级（安全）、B级（基本安全）与C级（不安全）的名称，分别以平台蓝、琥珀色与红色标识，与主页预警事件面板、堤段统计徽标使用同一套色标；界面只保留这三种色相，门控触发、等级范围等提示以文字标签附加在对应色块上。")
ed.replace(E[1735], "一级安全仅", "A级仅")
ed.replace(E[1735], "二级警戒向", "B级向")
ed.replace(E[1735], "三级危险提升", "C级提升")
ed.replace(E[1745], "当前危险、警戒与安全堤段的数量", "当前C级、B级与A级堤段的数量")
ed.replace(E[1749], "预警等级以颜色区分，其中一级安全以绿色标识、二级警戒以黄色标识、三级危险以红色标识。",
           "预警等级按表5-18划分，颜色与评价等级共用同一套色标，一级预警以红色标识，二级、三级预警以琥珀色标识并以文字区分，常规状态以平台蓝标识。")

# ---------------------------------------------------------------- 9. Figure 5-5 with the on-site photograph
ed.replace(E[1215], "（图5-5）", "（图5-5a、b）")
ed.insert_after(E[1215], "可在采集后重新设定发射率等参数进行温度反演。",
    "现场作业时，地面人员在堤顶道路就近起降无人机，按设定航线和航高沿堤采集可见光与红外图像（图5-5c）。")
ed.insert_after(E[1217], "巡检设备", "与现场作业")
ed.insert_after(E[1218], "Inspection equipment", " and on-site operation")
blip = next(E[1216].iter(A + "blip"))
rid = blip.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
rels = etree.parse(str(root / "word/_rels/document.xml.rels")).getroot()
target = next(r.get("Target") for r in rels if r.get("Id") == rid)
shutil.copyfile(fig55, root / "word" / target)
wpx, hpx = Image.open(fig55).size
ext = E[1216].find(".//" + WP + "extent")
cx = int(ext.get("cx"))
cy = round(cx * hpx / wpx)
ext.set("cy", str(cy))
for a_ext in E[1216].iter(A + "ext"):
    if a_ext.get("cx") == str(cx):
        a_ext.set("cy", str(cy))

# ---------------------------------------------------------------- 10. where the 875 records come from
ed.replace(E[1377], "在875条受控情景记录上", "在875条受控情景记录（设定方法见5.3.2.2节）上")
ed.rewrite(E[1390],
    "随机森林的训练数据与识别模型的图像数据相互独立。学习模型的训练和检验需要大量等级已知的样本，而具有独立安全鉴定结论的真实堤段数量很少；渗流严重乃至发生管涌、溃口的实测记录更难获得，因为险情一旦出现，现场的首要任务是抢险和修复，而不是系统地测量和保存资料。为此，本章以规范判据和工程经验为依据设定了875条情景样本，使样本在覆盖堤防常见工况与病害状态的同时，也包含实测资料中难以获得的严重和临界状态。由于各样本的条件和参考等级均事先设定，本章将其称为受控情景记录（简称受控记录）。样本以一个满足设计要求的基准断面为起点（堤顶超高2.80 m，背水坡、临水坡抗滑安全系数分别为1.62和1.48，控制层临界坡降0.971），按7类情景和5档严重程度改变相应输入，每档25条，构成见表5-19。各档中心取值参照规范阈值和门控阈值设定，同档25条记录在中心值附近随机扰动，避免记录完全相同。参考等级在评价之前按严重程度设定，不取自评价模型的输出，只用于检验方法能否随风险加重给出方向正确的等级，不是现场鉴定结论；第4章的计算结果和本章的现场巡检资料均未参与训练。另以5个不同的随机种子按同一规则各设定875条记录，用于检验结论的稳定性（见5.4.3节）。模型输入为表5-20所列14项特征，情景类型、严重程度和综合得分等直接关联参考等级的信息不作为特征。14项特征中不含穿堤建筑物状态，这一缺口将使学习模型无法区分穿堤建筑物情景的严重程度。")
ed.rewrite(E[1429],
    "前述评价方法和评价模型需要通过案例检验其判别能力、计算过程、稳定性以及接入实际资料后的作用。本节设置六个案例，按由受控到实际、由整体到局部的顺序展开，各案例的检验内容与数据来源见表5-21。案例一至案例三基于受控情景记录，参考等级由情景设定给出，相关定量结果反映方法本身的行为，在取得独立现场标签之前不代表真实堤防上的预测精度；案例四至案例六分别接入工程历史险情断面的复算资料、第4章的渗流计算成果和本章现场巡检的真实候选，检验评价链在实际资料条件下的作用。")
ed.rewrite(E[1431],
    "本案例在5.3.2.2节设定的875条受控记录上比较9种评价方法，重点考察总体精度与C级漏判之间的关系。受控记录的参考等级事先已知，可以逐条核对评价结论并统计各类误判，而实测断面缺少独立鉴定结论，难以这样检验。比较采用分组五折交叉验证的样本外预测，结果见表5-22和图5-18；方法间差异的显著性采用McNemar检验{sup:[243]}，波动范围采用分组Bootstrap重抽样{sup:[244]}估计。")

# ---------------------------------------------------------------- 11. Table 5-21 rebuilt with the main inputs
ed.replace(E[1446], "从四类典型情景中各取第1条记录（同类25条记录的结果相同），逐步列出评价结果（表5-21、图5-20）。",
    "从四类典型情景中各取第1条记录（同档25条记录的各级判定结果相同），列出其主要输入和逐步评价结果（表5-23、图5-20）。设定样本时，各类情景只改变与对应失效模式直接相关的输入，其余输入保持基准值，严重和临界档另按整体劣化减小堤顶宽度、增大沉降。因此，渗流情景的关键输入是三项坡降比以及与渗流相关的排水设施状态和巡检渗漏点密度，其抗滑安全系数、冲刷深度等仍为基准值。这样设定可以使评价结果的变化明确归因于关键输入，表5-23中以加粗表示。")
ed.replace(E[1447], "表5-21　典型情景的逐步评价结果", "表5-23　典型情景的主要输入与逐步评价结果")
ed.replace(E[1448], "Table 5-21 Step-by-step evaluation results of a typical scenario",
           "Table 5-23 Main inputs and step-by-step evaluation results of typical scenarios")

old = E[1449]
rows = old.findall(W + "tr")
hdr_t, row_t = rows[0], rows[1]
new = etree.Element(W + "tbl")
new.append(copy.deepcopy(old.find(W + "tblPr")))
tg = etree.SubElement(new, W + "tblGrid")
COLW = [2006, 1850, 1850, 1850, 1850]
for w in COLW:
    etree.SubElement(tg, W + "gridCol").set(W + "w", str(w))


def build_row(template, values, span=False, top_rule=False, first_center=False):
    tr = strip_ids(copy.deepcopy(template))
    tcs = tr.findall(W + "tc")
    keep = 2 if span else 5
    for tc in tcs[keep:]:
        tr.remove(tc)
    tcs = tr.findall(W + "tc")[:keep]
    for j, (tc, val) in enumerate(zip(tcs, values)):
        tcpr = tc.find(W + "tcPr")
        width = sum(COLW[1:]) if (span and j == 1) else COLW[j]
        tcpr.find(W + "tcW").set(W + "w", str(width))
        if span and j == 1:
            gs = etree.Element(W + "gridSpan")
            gs.set(W + "val", "4")
            tcpr.find(W + "tcW").addnext(gs)
        if top_rule:
            b = tcpr.find(W + "tcBorders")
            if b is None:
                b = etree.Element(W + "tcBorders")
                (tcpr.find(W + "gridSpan") if tcpr.find(W + "gridSpan") is not None else tcpr.find(W + "tcW")).addnext(b)
            top = etree.SubElement(b, W + "top")
            for k, v in (("val", "single"), ("color", "000000"), ("sz", "4"), ("space", "0")):
                top.set(W + k, v)
            b.insert(0, top)
        p = tc.find(W + "p")
        for extra in tc.findall(W + "p")[1:]:
            tc.remove(extra)
        tmpl = p.find(".//" + W + "rPr")
        tmpl = copy.deepcopy(p.find(W + "r").find(W + "rPr")) if p.find(W + "r") is not None else tmpl
        for c in list(p):
            if etree.QName(c).localname != "pPr":
                p.remove(c)
        ppr = p.find(W + "pPr")
        jc = ppr.find(W + "jc")
        if j == 0 and not first_center:
            # explicit left alignment: a justified cell would stretch the lines ended by manual breaks
            if jc is None:
                jc = etree.SubElement(ppr, W + "jc")
                rpr_in_ppr = ppr.find(W + "rPr")
                if rpr_in_ppr is not None:
                    rpr_in_ppr.addprevious(jc)
            jc.set(W + "val", "left")
        elif jc is None:
            jc = etree.SubElement(ppr, W + "jc")
            jc.set(W + "val", "center")
            rpr_in_ppr = ppr.find(W + "rPr")
            if rpr_in_ppr is not None:
                rpr_in_ppr.addprevious(jc)
        for r in make_runs(tmpl, val):
            p.append(r)
    return tr


HEAD = ["项目", "渗流严重\n（样本326）", "穿堤建筑物临界\n（样本726）", "安全基准严重\n（样本76）", "渗流轻微\n（样本276）"]
INPUTS = [
    ("断面", "堤顶超高2.80 m（规范要求2.0 m），外坡1:3.0，内坡1:3.2"),
    ("控制土层", "{i:G}{sub:s} = 2.65，{i:e} = 0.70，临界坡降0.971"),
    ("堤顶宽度/m", ["6.99", "6.84", "6.89", "8.50"]),
    ("堤基、堤身、\n接触面坡降比", ["{b:0.94、0.81、0.89}", "0.10、0.08、0.09", "{b:0.20}、0.08、0.09", "{b:0.55、0.48、0.52}"]),
    ("背水坡、临水坡\n安全系数", ["1.62、1.48", "1.62、1.48", "{b:1.46、1.33}", "1.62、1.48"]),
    ("冲刷深度/m", ["0.20", "0.20", "0.20", "0.20"]),
    ("沉降量、沉降差/cm", ["15.7、5.3", "25.2、9.7", "15.9、6.4", "5.0、1.0"]),
    ("巡检渗漏点密度\n/（点/100 m）", ["{b:3.0}", "0", "0", "{b:0.6}"]),
    ("定性指标异常", ["{b:C2、C6失效}", "{b:A3、B4、\nC6、D4失效}", "{b:A4差；\nA6、D5严重}", "{b:C2局部淤堵}"]),
]
RESULTS = [
    ("综合得分，\n初定等级", ["43.88，B", "54.16，B", "80.11，A", "75.84，B"]),
    ("触发门控\n→ 规则等级", ["渗流、沉降与\n巡检B级；\nC6失效C级 → C", "建筑物与沉降\nC级 → C", "沉降B级 → B", "无 → B"]),
    ("森林 ({i:p}{sub:A}, {i:p}{sub:B}, {i:p}{sub:C})，\n学习等级", ["(0, 0, 1.00)，C", "(1.00, 0, 0)，A", "(0.375, 0, 0.625)，\nC", "(1.00, 0, 0)，A"]),
    ("最终等级\n（参考等级）", ["C（C）", "C（C）", "C（C）", "B（A）"]),
]
new.append(build_row(hdr_t, HEAD, first_center=True))
for label, vals in INPUTS:
    span = isinstance(vals, str)
    new.append(build_row(row_t, [label, vals] if span else [label] + vals, span=span))
for k, (label, vals) in enumerate(RESULTS):
    new.append(build_row(row_t, [label] + vals, top_rule=(k == 0)))
old.addprevious(new)
body.remove(old)
note_tmpl = E[1435]
ed.new_paragraph_after(new, note_tmpl.find(W + "pPr"), note_tmpl.find(W + "r").find(W + "rPr"),
    "注：样本编号为受控情景记录的序号，不对应堤防桩号；坡降比为渗透坡降与控制层临界坡降之比；加粗为该类情景按设定重点改变的输入，其余输入取基准值，严重和临界档另按整体劣化减小堤顶宽度、增大沉降。")
blip = next(E[1450].iter(A + "blip"))
rid = blip.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
target = next(r.get("Target") for r in rels if r.get("Id") == rid)
shutil.copyfile(fig520, root / "word" / target)

# ---------------------------------------------------------------- Case 5 recomputed with the 1028 Chapter 4 (33.89 m)
ed.insert_after(E[1477], "的渗流计算结果接入评价。",
    "所用出逸梯度均直接取自第4章4.5.2～4.5.3节的计算结果，计算水位取33.89 m洪水位和30.00 m，后者是两断面开始出现向上出逸的最低计算水位。")
CASE5 = [
    ["断面Ⅰ，30.00 m", "0.9247", "Ⅱ级", "0.897～1.121", "0～19.6", "B级，可能C级", "B～C级"],
    ["断面Ⅱ，30.00 m", "0.4216", "Ⅰ级", "0.409～0.511", "73.9～83.3", "未触发", "证据不足，取决于其余指标"],
    ["断面Ⅰ，33.89 m", "2.149", "Ⅲ级", "2.084～2.605", "0", "C级", "C级"],
    ["断面Ⅱ，33.89 m", "1.17", "Ⅲ级", "1.135～1.418", "0", "C级", "C级"],
    ["三维计算域，33.89 m", "3.279", "Ⅲ级", "3.180～3.975", "0", "C级", "先关联到桩号区间"],
]
t524 = E[1480]
rows524 = t524.findall(W + "tr")
spare = strip_ids(copy.deepcopy(rows524[-1]))          # template for the fifth data row, taken before editing
for tr, vals in zip(rows524[1:], CASE5[:4]):
    for tc, val in zip(tr.findall(W + "tc"), vals):
        p = tc.find(W + "p")
        if ed.para_text(p) != val:
            ed.rewrite(p, val)
for tc, val in zip(spare.findall(W + "tc"), CASE5[4]):
    p = tc.find(W + "p")
    tmpl = copy.deepcopy(p.find(W + "r").find(W + "rPr"))
    for r in p.findall(W + "r"):
        p.remove(r)
    runs = make_runs(tmpl, val)
    if ed.track:
        ins = ed._rev("ins")
        for r in runs:
            ins.append(r)
        p.append(ins)
    else:
        for r in runs:
            p.append(r)
if ed.track:
    spare.find(W + "trPr").append(ed._rev("ins"))
rows524[-1].addnext(spare)
ed.rewrite(E[1481], "注：33.89 m为洪水位；断面取二维稳态结果，三维计算域取第30天结果，其8条代表性通道中Ⅰ、Ⅱ、Ⅲ级分别为1、3、4条。")
blip = next(E[1482].iter(A + "blip"))
rid = blip.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
target = next(r.get("Target") for r in rels if r.get("Id") == rid)
shutil.copyfile(fig524, root / "word" / target)
wpx, hpx = Image.open(fig524).size
ext = E[1482].find(".//" + WP + "extent")
cx = int(ext.get("cx"))
cy = round(cx * hpx / wpx)
ext.set("cy", str(cy))
for a_ext in E[1482].iter(A + "ext"):
    if a_ext.get("cx") == str(cx):
        a_ext.set("cy", str(cy))
ed.rewrite(E[1485], "33.89 m洪水位下，断面Ⅰ、Ⅱ的最大出逸梯度分别为2.149和1.17，均超过临界区间上界1.03125，孔隙比在0.6～1.0内无论取何值，C1均已达到临界，C级门控是确定的，其余28项指标即使全部取得也不会使等级优于C级；即使巡检覆盖完整且未见异常，也保持该等级。30.00 m时，断面Ⅰ的0.9247位于临界区间内，只能确定不优于B级，C级仅为可能，应输出B～C级，并将出口土层孔隙比列为待补证据；断面Ⅱ的0.4216未触发门控，但其余指标缺失，仅凭渗流计算不能给出安全结论。由此可见，同一断面随水位升高会由“证据不足”或B～C级转为确定的C级，评价结论随水位工况而变化。三维计算域不是评价单元，其高梯度出逸面（洪水位下梯度不小于0.825的Ⅱ、Ⅲ级出逸面积约23822 m²，第60天）须先关联到桩号区间，同时作为巡检航线的重点区域。第4章的出口分级以理想无黏性土柱的临界梯度为参照，正式评价还应结合出口土料的启动条件复核。")

# ---------------------------------------------------------------- 12. the five additional batches
ed.replace(E[1455], "为检验结论是否依赖某一批数据，在另外5批独立生成的情景上重复上述评价（图5-21）。",
    "为检验结论是否依赖某一批数据，按5.3.2.2节的同一设定规则，以5个不同的随机种子另外生成5批受控情景，每批同样包含7类情景、5档严重程度、每档25条，共875条，参考等级分布与第一批相同（A级350条、B级175条、C级350条）。各批的情景构成和各档中心取值不变，不同的是中心值附近的随机扰动，因此各批的取值范围基本一致而逐条取值互不相同，例如渗流情景的堤基渗透坡降均在0.33～1.13之间，边坡情景的背水坡安全系数均在0.90～1.61之间，每批互不相同的特征组合为723～725种。评价模型的参数和决策阈值保持不变，各批分别独立完成分组五折交叉验证，学习模型只用本批样本训练和检验（图5-21）。这5批情景检验的是结论对样本随机性的稳定性，而不是对不同堤防或不同情景分布的适用性。")

# ---------------------------------------------------------------- 13. Sec. 5.5 summary
SUMMARY = {
    1492: "本章围绕第1章提出的第二个关键科学问题，研究了融合渗流机理与空基巡检病害信息的堤防渗流安全透明评价方法，在评价框架、巡检识别、证据接入、评价模型和工程应用等方面取得了以下成果。",
    1493: "（1）构建了以证据层为核心的堤防渗流安全透明评价框架与指标体系。以指定水位工况和资料截止时间下的堤段渗流安全状态为评价对象，以安全等级、主控失效模式和待补资料为评价目标，建立了六层评价框架和八步实施流程；指标体系以渗流计算可直接给出的坡降比替代依赖监测设施的渗压与渗漏量指标，使透明计算成果能够直接进入评价。",
    1494: "（2）提出了面向渗漏探测的无人机红外巡检与管涌智能识别方法。给出了巡检时段、航线与航高的设计方法，采用P2ES-YOLO模型增强了对小尺度、边界模糊渗漏目标的感知能力和对背景热干扰的抑制能力，识别精度较基线模型明显提高；现场巡检的应用分析揭示了白天日照形成的背景温差是误报的主要来源，明确了巡检结果须经复核方可进入评价。",
    1495: "（3）建立了巡检结果的证据状态控制与接入规则。将算法检出、人工复核和现场确认分开处理，并区分已检查无异常与未检查，使巡检结果分别以指标输入、等级约束和复核触发三种方式进入评价，既能约束评价结论，又避免了因误报造成的不必要降级。",
    1496: "（4）构建了物理规则链与随机森林相结合的评价模型。规则链以失效模式响应、运行管理屏障修正、短板项和物理硬门控体现规范要求与专家经验，随机森林从受控情景中学习指标组合风险，二者以序数物理下限组合，学习模型只能调高、不能调低规则等级，在提高判别精度的同时从机制上避免了将不安全断面判为安全的最危险误判。",
    1497: "（5）分析了评价模型的判别能力、稳定性与证据依赖性，建立了兼顾安全与精度的多目标策略选择方法。受控情景检验表明，组合模型在消除C级判为A级误判的同时提高了总体精度，且结论在多批情景上保持稳定；工程历史断面、渗流计算结果和现场巡检结果的接入分析表明，评价链能够追溯结论的来源，指出结论对关键指标取值的敏感性，并将证据缺失与不确定性明确列为待办事项。",
    1498: "（6）实现了评价结论的透明表达与动态更新。评价输出同时给出安全等级、主控失效模式、触发原因、证据清单和待办事项，可随水位工况、巡检发现和复核结论滚动更新，并通过标准化输出字段接入第6章的数字孪生平台，为汛期堤段巡查、复核和处置决策提供可追溯的依据。",
    1499: "需要指出的是，本章的定量检验主要基于受控情景，序数下限的保护以规则链门控正确为前提；识别模型与评价模型的现场适用性，仍需利用夜间采集、带有确认管涌和独立鉴定结论的现场数据进一步检验。",
}
for idx, text in SUMMARY.items():
    ed.rewrite(E[idx], text)

# ---------------------------------------------------------------- 14/15 and the matching 7.1 item
ed.rewrite(E[1910], "（3）在透明评价方面，本文构建了融合渗流机理与空基巡检病害信息的堤防渗流安全透明评价方法。针对机理计算与现场观测相互割裂、综合得分容易掩盖临界指标、评价结论难以追溯和随工况更新等问题，本文建立了以证据层为核心的六层评价框架和包含5个准则层、29项指标的评价指标体系，以坡降比、抗滑安全系数等可由计算直接给出的物理量刻画渗流与稳定状态，并以导则优先级确定权重、以指标—失效模式关联识别主控失效模式；提出了无人机红外巡检方案与P2ES-YOLO管涌识别方法，通过空间配准与证据状态规则将算法检出、人工复核与现场确认分开处理，使巡检结果以指标输入、等级约束和复核触发三种方式进入评价；构建了物理规则链与随机森林相结合、以序数物理下限约束学习模型的评价模型，在不将不安全断面判为安全的前提下提高了判别精度。受控情景、工程历史险情断面、渗流计算成果接入与真实巡检候选接入等六个案例表明，评价结果能够同时给出安全等级、主控失效模式、触发原因与待补资料，并可随水位工况与巡检证据滚动更新，解决了传统评价结论难以追溯、难以随工况动态更新的问题。")
ed.rewrite(E[1915], "（2）构建了融合渗流机理与空基巡检病害信息的堤防渗流安全透明评价方法。针对机理计算与现场观测相互割裂、综合得分掩盖临界指标、评价结论难以追溯和更新等问题，本文融合了透明计算给出的坡降比、抗滑安全系数等机理指标与无人机红外巡检获取的实景病害证据，以证据状态统一表达两类信息的来源、时空范围与可信程度；融合了体现规范要求与专家经验的物理规则链和从情景样本中学习指标组合风险的随机森林，以序数物理下限约束学习模型只能调高、不能调低物理规则给出的等级，并以多目标策略评价选择运行参数，实现了理论风险与实景缺陷的相互印证、安全底线约束下评价精度的提升，以及评价结论从数据来源到等级判定的全过程可追溯与随工况动态更新。")
ed.rewrite(E[1921], "（3）在安全评价方面，评价模型的定量检验主要基于设定的受控情景，参考等级由情景设定给出，现场资料仅用于单个历史险情断面和一次白天巡检的接入检验；门控阈值、短板系数与预警分级主要依据规范允许值和工程经验确定，指标权重采用常权，尚未考虑指标之间的相关性及其随水位和时间的变化。后续需要积累带有独立鉴定结论、确认险情记录和时空配准信息的现场样本，对阈值与权重进行标定，引入变权与可靠度分析方法量化渗流失稳概率，并检验评价方法在不同流域、不同堤型条件下的适用性。")


# ================================================================ round 3 (2026-10-31): collaborator feedback and items 1-10
from omml import omath_para  # noqa: E402


def make_table(tmpl, widths, header, rows):
    """A three-line table built from the header and first data row of `tmpl`."""
    tbl = etree.Element(W + "tbl")
    tbl.append(copy.deepcopy(tmpl.find(W + "tblPr")))
    grid = etree.SubElement(tbl, W + "tblGrid")
    for w in widths:
        etree.SubElement(grid, W + "gridCol").set(W + "w", str(w))
    trs = tmpl.findall(W + "tr")
    for k, vals in enumerate([header] + rows):
        tr = strip_ids(copy.deepcopy(trs[0] if k == 0 else trs[1]))
        tcs = tr.findall(W + "tc")
        for tc in tcs[len(vals):]:
            tr.remove(tc)
        for j, (tc, val) in enumerate(zip(tr.findall(W + "tc"), vals)):
            tcpr = tc.find(W + "tcPr")
            tcpr.find(W + "tcW").set(W + "w", str(widths[j]))
            for gs in tcpr.findall(W + "gridSpan"):
                tcpr.remove(gs)
            ps = tc.findall(W + "p")
            for extra in ps[1:]:
                tc.remove(extra)
            p = ps[0]
            r0 = p.find(".//" + W + "r")
            tmpl_rpr = copy.deepcopy(r0.find(W + "rPr")) if r0 is not None else None
            for c in list(p):
                if etree.QName(c).localname != "pPr":
                    p.remove(c)
            ppr = p.find(W + "pPr")
            jc = ppr.find(W + "jc")
            if jc is None:
                jc = etree.Element(W + "jc")
                rp = ppr.find(W + "rPr")
                (rp.addprevious(jc) if rp is not None else ppr.append(jc))
            jc.set(W + "val", "left" if (j == 0 and k > 0) else "center")
            for r in make_runs(tmpl_rpr, val):
                p.append(r)
        if ed.track:
            trpr = tr.find(W + "trPr")
            if trpr is None:
                trpr = etree.Element(W + "trPr")
                tr.insert(0 if tr.find(W + "tblPrEx") is None else 1, trpr)
            trpr.append(ed._rev("ins"))
        tbl.append(tr)
    return tbl


def caption_pair(anchor, cn_tmpl, en_tmpl, cn, en):
    a = ed.new_paragraph_after(anchor, cn_tmpl.find(W + "pPr"), cn_tmpl.find(W + "r").find(W + "rPr"), cn)
    return ed.new_paragraph_after(a, en_tmpl.find(W + "pPr"), en_tmpl.find(W + "r").find(W + "rPr"), en)


def set_equation(tbl_idx, row, latex):
    p = E[tbl_idx].findall(W + "tr")[row].findall(W + "tc")[0].find(W + "p")
    for c in list(p):
        if etree.QName(c).localname != "pPr":
            p.remove(c)
    p.append(omath_para(latex))


# ---- item 2: Chapter 2 (2.2.1, 2.2.2) and the matching statements in 2.6
ed.rewrite(E[79], "透明评价是指将透明计算输出的坡降比、出逸梯度、抗滑安全系数等机理指标与透明巡检输出的现场病害信息统一表达为带有来源、时间、空间范围和证据状态的评价证据，按照规范规定的评价框架构建指标体系，通过失效模式关联、物理门控以及受物理规则约束的学习模型，对堤段的渗流安全状态作出判定，给出安全等级、主控失效模式及其判定依据。其核心目标是改变仅依赖规范赋分或仅依赖单一数值计算的静态评价方式，使机理推演与现场观测能够相互印证、滚动更新，并使每一项结论都能追溯到所依据的证据。")
ed.replace(E[86], "：若计算显示某断面渗透比降偏大而巡检未发现异常，说明可能存在覆盖层压重或反滤压盖；若巡检发现明显渗漏而计算比降不大，则可能是计算模型低估了局部渗透性或存在未知的渗漏通道。",
    "。二者不一致时不简单舍弃任何一方。若计算显示某断面坡降比偏大而巡检未发现异常，应保持计算给出的等级约束，因为渗漏迹象可能尚未显露，也可能受巡检时段与覆盖范围限制，覆盖层压重或反滤压盖等有利因素需经复核确认；若巡检确认明显渗漏而计算坡降比不大，则以确认事件给出等级下限，并提示计算模型可能低估了局部渗透性或存在未知的渗漏通道，需回溯地质与计算模型。具体处理规则见第5章表5-15。")
set_equation(153, 0, r"J_{\text{cr}}=(G_{\text{s}}-1)(1-n)=\frac{G_{\text{s}}-1}{1+e}")
ed.replace(E[154], "式中，Gs为土粒比重，n为孔隙率。",
    "式中，{i:G}{sub:s}为土粒比重；{i:n}为孔隙率；{i:e}为孔隙比，{i:n} = {i:e}/(1 + {i:e})。式（2-7）与第5章式（5-1）一致。")
ed.replace(E[155], "组合赋权方法", "赋权方法")
ed.replace(E[156], "[173]", "{sup:[136]}")
ed.replace(E[156], "[175]", "{sup:[137]}")
ed.rewrite(E[157], "各指标权重采用基于导则优先级的层次分析法（AHP）确定。具体做法是依据导则规定的评价要素优先级和研究区特点确定同一层级指标的重要性排序，按1～9标度构造两两判断矩阵，以方根法求得权重，经一致性检验后作为常权使用（见第5章5.2.3节）。主观赋权与熵权法等客观赋权相组合的方法能够兼顾专家经验与数据离散特征，组合权重为两类权重的加权平均：")
set_equation(158, 0, r"w_{j}=αw_{1j}+(1-α)w_{2j}")
ed.rewrite(E[159], "式中，{i:w}{sub:1{i:j}}、{i:w}{sub:2{i:j}} 分别为主观权重和客观权重；{i:α} 为主观权重偏好系数。客观赋权需要足够多的同类堤段实测资料，研究区目前尚不具备这一条件，因此本研究取 {i:α} = 1，即采用AHP常权；取得实测资料后，可在不改变评价模型结构的前提下引入客观权重。")
ed.replace(E[162], "当透明巡检发现新的病害点或上、下游水位发生变化时，相应指标的取值与权重随之更新，评价结果在数字孪生平台上滚动刷新。",
    "当临水侧水位发生变化，或透明巡检发现的新病害经人工复核确认后，相应指标的取值随之更新，评价结果在数字孪生平台上滚动刷新；未经复核的候选只触发复核任务，不直接改变指标取值。")
# ---- round 4: further alignment of 2.5 and 2.6 with Chapter 5
ed.replace(E[136], "根据普朗克黑体辐射定律，物体的辐射出射度与其绝对温度的四次方成正比",
    "根据斯特藩—玻尔兹曼定律（由普朗克黑体辐射定律对全波段积分得到），黑体的辐射出射度与其绝对温度的四次方成正比")
ed.replace(E[138], "当堤后存在渗漏出逸时，渗出的河水携带热量进入堤后浅表层，使局部地表温度与周围干燥土体形成差异。在昼夜温差与太阳辐射的共同作用下，这种温度差异在红外热像图上表现为局部异常亮斑或色带。",
    "当堤后存在渗漏出逸时，渗出的河水温度较为稳定、热容量大，使局部地表的温度变化速率与周围干燥土体不同，从而形成温度差异。这种差异的符号随时段而变化。白天太阳辐射使表层土体快速升温，渗水区相对偏冷，表现为低温斑块；夜间或阴雨天气下土体降温较快，渗水区相对偏暖，表现为高温异常（见第5章图5-4）。")
ed.replace(E[147], "为提升模型对小目标的感知能力，本研究在YOLOv8骨干网络中嵌入卷积块注意力模块（CBAM）。",
    "为提升模型对小目标的感知能力，本研究前期在YOLOv8骨干网络中嵌入卷积块注意力模块（CBAM），构成图2-4所示的检测框架。")
ed.insert_after(E[147], "对微弱温度异常的响应灵敏度显著提高。",
    "但CBAM主要作用于特征提取阶段，对小目标感知、边界框回归和背景热斑抑制的改善有限，因此第5章最终采用P2ES-YOLO模型{sup:[28]}，即增加4倍下采样的P2小目标检测分支、以EIoU损失替代CIoU损失，并在颈部网络的C2f模块中嵌入无参数的SimAM注意力模块。")
ed.replace(E[154], "当J/Jcr小于某一下限时认为渗流稳定，介于上下限之间时认为存在风险，超过上限则认为可能发生渗透破坏。",
    "第5章将计算水力比降 {i:i} 与临界水力比降 {i:i}{sub:cr} 之比记为风险比 {i:R}，{i:R} 达到0.8时认为渗流安全储备不足，评价等级不优于B级；{i:R} 达到1.0时认为达到渗透破坏临界，评价为C级。")
ed.replace(E[156], "构建覆盖工程质量、运行管理、防洪安全、渗流安全与结构安全五个准则层的三级递阶指标体系。",
    "构建覆盖工程质量、防洪安全、渗流安全、结构安全与运行管理五个准则层、共29项指标的三级递阶指标体系。")
ed.replace(E[161], "以关联强度系数rim表示指标i对失效模式m的贡献程度（0至3分）。",
    "以关联强度 {i:r}{sub:{i:jm}} 表示指标 {i:j} 与失效模式 {i:m} 的关联程度（0～3级）。")
ed.insert_after(E[161], "识别当前条件下的主控失效模式与主要风险贡献来源。",
    "为避免达到临界状态的指标被平均，综合风险中另设短板项，并以物理临界与巡检观测双重门控约束评价等级（见第5章5.3.1节）。")
ed.replace(E[170], "临界水力比降判据与组合赋权方法", "临界水力比降判据与基于导则优先级的赋权方法")
ed.replace(E[170], "YOLOv8结合CBAM注意力模块的检测框架", "YOLOv8结合CBAM注意力模块的检测框架及其向P2ES-YOLO的改进思路")

# ---- item 3: the reference that left the introduction is cited where the emphasis on seepage is argued
ed.insert_after(E[1166], "指标体系以渗流破坏为重点", "{sup:[206-207]}")

# ---- item 5: colour versions of Figures 5-1 to 5-3 (identical content)
for idx, name in ((1147, "fig5_1_framework.png"), (1167, "fig5_2_indicator_system.png"), (1205, "fig5_3_inspection_workflow.png")):
    rid = next(E[idx].iter(A + "blip")).get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
    shutil.copyfile(FIGDIR / name, root / "word" / next(r.get("Target") for r in rels if r.get("Id") == rid))

# ---- item 9 (part): symbols and abbreviations used before they are defined
ed.replace(E[1184], "抗滑稳定指标D1、D2以规范允许值", "抗滑稳定指标D1、D2以抗滑稳定安全系数（factor of safety，下文记为FoS）的规范允许值")
ed.replace(E[1319], "原模型将渗漏点匹配到最近的代表桩号", "原模型（前期建立的失效模式—安全屏障评价模型，即5.3.1节物理规则链的初始版本，下同）将渗漏点匹配到最近的代表桩号")
ed.replace(E[1386], "随机森林是以决策树", "随机森林（random forest，RF）是以决策树")
ed.replace(cell(1173, 0, 2), "[10]", "{sup:[145]}")

# ---- item 6: weights explained in 5.2.3, Table 5-5 moved there and given the second-level weights
ed.replace(E[1187], "各指标的评分规则、综合权重和主要数据来源见表5-5。由表5-5可知，C1、C4、C5",
    "各指标的评分规则与数据来源汇总于5.2.3节表5-5（表中同时列出权重）。其中，C1、C4、C5")
ed.rewrite(E[1194], "权重采用基于导则优先级的层次分析法确定。先依据《堤防工程安全评价导则》规定的核心控制要素优先级和研究区特点，确定同一层级指标的重要性排序；再按1～9标度构造判断矩阵，以方根法求权重，即取判断矩阵各行元素的几何平均值并归一化；最后进行一致性检验，一致性比率 CR 小于0.10时判断矩阵有效。一级权重的判断矩阵中，渗流安全相对于工程质量、防洪安全和结构安全的标度均取2，相对于运行管理取4；工程质量、防洪安全与结构安全两两同等重要，相对于运行管理均取2。该矩阵为一致矩阵（CR = 0），五个准则层的权重依次为0.1818、0.1818、0.3636、0.1818和0.0909。渗流安全权重最高，体现研究区砂、黏土互层堤基和管涌隐患突出的特点；运行管理主要承担巡查预警和应急处置作用，作为安全屏障参与风险修正，故权重较低。二级权重在各准则层内按同一方法计算，重要性排序依据导则的评价重点和各指标对失效过程的控制程度确定。渗流安全内，直接表征渗透破坏的C1、C5最重要，其次依次为C4、C6、C2和C3；防洪安全内依次为B1、B3、B2、B4；结构安全内依次为D1、D2、D5、D3、D4；工程质量内A2、A6最重要，其次为A7，A1、A3、A8相当，再次为A4、A5、A9；运行管理内依次为E4、E1、E5、E2、E3。指标的综合权重为所属准则层权重与二级权重之积，即 {i:g}{sub:{i:j}} = {i:W}{sub:{i:l}}{i:w}{sub:{i:j}|{i:l}}，各指标的二级权重与综合权重见表5-5。综合权重最高的是C1和C5（均为9.99%），其次为B1（8.78%）和D1（7.38%），与渗流破坏、漫顶和边坡失稳是堤防主要失效形式的工程认识一致。由于未开展专家问卷，上述权重为基于层次分析法的常权配置，取得专家判断后可在不改变模型结构的前提下替换。")
LOCAL = {"A1": "10.42", "A2": "20.53", "A3": "10.42", "A4": "6.04", "A5": "3.74", "A6": "20.53", "A7": "15.62", "A8": "10.42",
         "A9": "2.29", "B1": "48.32", "B2": "15.69", "B3": "27.17", "B4": "8.82", "C1": "27.47", "C2": "8.90", "C3": "6.00",
         "C4": "17.31", "C5": "27.47", "C6": "12.84", "D1": "40.60", "D2": "25.02", "D3": "11.54", "D4": "6.34", "D5": "16.51",
         "E1": "26.34", "E2": "9.75", "E3": "6.15", "E4": "41.74", "E5": "16.02"}
t55 = E[1190]
for g, w in zip(t55.find(W + "tblGrid").findall(W + "gridCol"), ["1000", "2400", "3406", "1300", "1300"]):
    g.set(W + "w", w)
for tr in t55.findall(W + "tr"):
    for tc, w in zip(tr.findall(W + "tc"), ["1000", "2400", "3406", "1300", "1300"]):
        tc.find(W + "tcPr/" + W + "tcW").set(W + "w", w)
ed.replace(cell(1190, 0, 3), "综合权重/%", "二级/综合权重（%）")
for r, tr in enumerate(t55.findall(W + "tr")[1:], start=1):
    code = ed.para_text(cell(1190, r, 1)).split()[0]
    p = cell(1190, r, 3)
    ed.replace(p, ed.para_text(p), f"{LOCAL[code]}/{ed.para_text(p)}")
ed.replace(E[1188], "评价指标的评分规则、综合权重与数据来源", "评价指标的评分规则、权重与数据来源")
ed.replace(E[1189], "Scoring rules, comprehensive weights and data sources", "Scoring rules, weights and data sources")
for el in (E[1191], E[1190], E[1189], E[1188]):     # caption, English caption, table and note follow the weights
    E[1194].addnext(el)

# ---- item 7: symbols of Eq. (5-3)
ed.replace(E[1201], "式中，分子为指标综合权重与关联强度乘积在模式 m 上的累加，分母为其在全部失效模式上的总和。",
    "式中，{i:W}{sub:{i:m}} 为失效模式 {i:m} 的权重；{i:g}{sub:{i:j}} 为指标 {i:j} 的综合权重（表5-5）；{i:r}{sub:{i:jm}}、{i:r}{sub:{i:jk}} 分别为指标 {i:j} 与失效模式 {i:m}、{i:k} 的关联强度（表5-6）；分子为指标综合权重与关联强度乘积在模式 {i:m} 上的累加，分母为其在全部失效模式上的总和。")

# ---- item 8: symbols written without subscripts in the text
ed.replace(E[1327], "式中，s、w、t、v 分别为堤段、水位工况、评价时刻和规则版本；1{·} 为示性函数，条件成立时取1，否则取0；Sj、Ss 分别为证据和堤段的空间范围；Tj 为证据有效期；vj≼v 表示证据版本与规则版本相容。",
    "式中，{i:s}、{i:w}、{i:t}、{i:v} 分别为堤段、水位工况、资料截止时间和规则版本；1{·} 为示性函数，条件成立时取1，否则取0；{i:S}{sub:{i:j}}、{i:S}{sub:{i:s}} 分别为证据和堤段的空间范围；{i:T}{sub:{i:j}} 为证据有效期；{i:v}{sub:{i:j}}≼{i:v} 表示证据版本与规则版本相容。")
ed.replace(E[1362], "式中，ρ 为综合风险；πm 为在有资料的模式上重新归一化的模式权重；α = 0.45 为短板系数；S 为综合得分。",
    "式中，{i:ρ} 为综合风险；{i:π}{sub:{i:m}} 为在有资料的模式上重新归一化的模式权重；{i:α} = 0.45 为短板系数；{i:S} 为综合得分。")
ed.replace(E[1362], "，α 越大评价越保守", "，{i:α} 越大评价越保守")
ed.replace(E[1364], "规则等级 yrule。", "规则等级 {i:y}{sub:rule}。")
ed.replace(E[1421], "学习模型 ℓ 包括", "学习模型 {i:ℓ} 包括")
ed.replace(E[1421], "阈值 τC、τB 在", "阈值 {i:τ}{sub:C}、{i:τ}{sub:B} 在")
ed.replace(E[1421], "φ 为下限方式", "{i:φ} 为下限方式")
ed.replace(E[1427], "式中，Lmax = 2NC，NC 为参考C级记录数", "式中，{i:L}{sub:max} = 2{i:N}{sub:C}，{i:N}{sub:C} 为参考C级记录数")
EQS = {
    (1183, 0): r"i_{\text{cr}}=\frac{G_{\text{s}}-1}{1+e},\quad R=\frac{i}{i_{\text{cr}}}",
    (1183, 1): r"S=\cases{100(1-R^{2}),&0≤R<1 \\ 0,&R≥1}",
    (1200, 0): r"W_{m}=\frac{\sum_{j}{g_{j}r_{jm}}}{\sum_{k}{\sum_{j}{g_{j}r_{jk}}}}",
    (1224, 0): r"\text{GSD}=\frac{Hp}{f}",
    (1239, 0): r"T_{\text{obj}}=\dl{[}{]}{\frac{T_{\text{m}}^{4}-(1-ε)T_{\text{refl}}^{4}}{ε}}^{1/4}",
    (1241, 0): r"ΔT=T_{\text{box}}-\text{median}\dl{(}{)}{T_{\text{ring}}}",
    (1250, 0): r"p_{2}^{\text{out}}=\text{Conv}\dl{(}{)}{\text{Concat}\dl{(}{)}{p_{2}^{\text{in}},\ \text{Upsample}\dl{(}{)}{p_{3}^{\text{in}}}}}",
    (1253, 0): r"\text{IoU}=\frac{\dl{|}{|}{B∩B^{\text{gt}}}}{\dl{|}{|}{B∪B^{\text{gt}}}}",
    (1253, 1): r"L_{\text{CIoU}}=1-\text{IoU}+\frac{d^{2}}{c^{2}}+αv,\quad v=\frac{4}{π^{2}}\dl{(}{)}{\text{arctan}\frac{w^{\text{gt}}}{h^{\text{gt}}}-\text{arctan}\frac{w}{h}}^{2}",
    (1253, 2): r"L_{\text{EIoU}}=1-\text{IoU}+\frac{d^{2}}{c^{2}}+\frac{\dl{(}{)}{w-w^{\text{gt}}}^{2}}{C_{w}^{2}}+\frac{\dl{(}{)}{h-h^{\text{gt}}}^{2}}{C_{h}^{2}}",
    (1256, 0): r"e_{t}=\frac{4\dl{(}{)}{σ^{2}+λ}}{\dl{(}{)}{t-μ}^{2}+2σ^{2}+2λ},\quad Y=\text{Sigmoid}\dl{(}{)}{\frac{1}{E}}⊙X",
    (1283, 0): r"\text{Pre}=\frac{\text{TP}}{\text{TP}+\text{FP}},\quad \text{Rec}=\frac{\text{TP}}{\text{TP}+\text{FN}}",
    (1283, 1): r"\text{AP}=\sum_{n}{\dl{(}{)}{\text{Rec}_{n}-\text{Rec}_{n-1}}\text{Pre}_{n}},\quad \text{mAP}=\frac{1}{K}\sum_{k}{\text{AP}_{k}}",
    (1316, 0): r"\dl{[}{]}{c^{-},\ c^{+}}=Π_{g}\dl{(}{)}{F}⊕\dl{[}{]}{-δ,\ δ}",
    (1318, 0): r"U\dl{(}{)}{e}=\dl{\{}{\}}{u:\dl{[}{]}{c_{e}^{-},\ c_{e}^{+}}∩\dl{[}{]}{c_{u}^{-},\ c_{u}^{+}}≠∅,\ g_{e}=g_{u}}",
    (1326, 0): r"a_{j}\dl{(}{)}{s,\ w,\ t,\ v}=\text{1}\dl{\{}{\}}{S_{j}∩S_{s}≠∅}·\text{1}\dl{\{}{\}}{t∈T_{j}}·\text{1}\dl{\{}{\}}{v_{j}≼v}",
    (1334, 0): r"D=\frac{100\sum_{k}{c_{k}w_{k}r_{k}}}{L}",
    (1340, 0): r"g^{-}=\text{max}\dl{(}{)}{G\dl{(}{)}{ρ^{-}},\ \maxl{m}{k_{m}^{\text{cert}}}},\quad g^{+}=\text{max}\dl{(}{)}{G\dl{(}{)}{ρ^{+}},\ \maxl{m}{k_{m}^{\text{poss}}}}",
    (1357, 0): r"R_{m}^{′}=R_{m}+λcR_{m}\dl{(}{)}{1-R_{m}}\dl{(}{)}{1-B}",
    (1361, 0): r"ρ=α\maxl{m}{R_{m}^{′}}+\dl{(}{)}{1-α}\sum_{m}{π_{m}R_{m}^{′}},\quad S=100\dl{(}{)}{1-ρ}",
    (1387, 0): r"p_{k}\dl{(}{)}{x}=\frac{1}{T}\sum_{t=1}^{T}{\text{1}\dl{\{}{\}}{h_{t}\dl{(}{)}{x}=k}},\quad k∈\dl{\{}{\}}{\text{A},\ \text{B},\ \text{C}}",
    (1398, 0): r"\text{Acc}=\frac{1}{N}\sum_{i}{\text{1}\dl{\{}{\}}{ŷ_{i}=y_{i}}},\quad \text{F1}_{k}=\frac{2\text{Pre}_{k}\text{Rec}_{k}}{\text{Pre}_{k}+\text{Rec}_{k}}",
    (1398, 1): r"\text{MacroF1}=\frac{1}{3}\sum_{k}{\text{F1}_{k}},\quad \text{BA}=\frac{1}{3}\sum_{k}{\text{Rec}_{k}},\quad R_{\text{C}}=\text{Rec}_{\text{C}}",
    (1400, 0): r"L_{\text{safe}}=2N\dl{(}{)}{\text{C→A}}+N\dl{(}{)}{\text{C→B}}",
    (1410, 0): r"ŷ_{\text{RF}}=\cases{\text{C},&p_{\text{C}}≥τ_{\text{C}} \\ \text{B},&p_{\text{C}}<τ_{\text{C}},\ p_{\text{B}}≥τ_{\text{B}} \\ \text{A},&\text{其他}}",
    (1414, 0): r"ŷ_{\text{H}}=\text{max}\dl{(}{)}{ŷ_{\text{RF}},\ y_{\text{rule}}}",
    (1420, 0): r"π=\dl{(}{)}{ℓ,\ τ_{\text{C}},\ τ_{\text{B}},\ φ}",
    (1426, 0): r"F\dl{(}{)}{π}=\dl{(}{)}{\text{MacroF1},\ \text{BA},\ R_{\text{C}},\ 1-L_{\text{safe}}/L_{\text{max}}}",
}
for (idx, row), latex in EQS.items():
    set_equation(idx, row, latex)

# ---- item 9: Table 5-19 (now 5-20) explanations
ed.replace(cell(1393, 1, 2), "m", "单位为m；受控记录的设计洪水位相同，堤顶高程的差异即超高的差异")
ed.replace(cell(1393, 2, 2), "归一化值为坡降除以0.25", "归一化值为坡降除以允许比降0.25")
ed.replace(cell(1393, 4, 2), "归一化值为深度除以1.0 m", "归一化值为冲刷深度除以1.0 m（D3评分的不利界限）")
ed.replace(cell(1393, 5, 1), "异常密度、证据等级（2项）", "加权渗漏点密度、观测证据等级（2项）")
ed.replace(cell(1393, 5, 2), "与C3同源", "单位分别为点/100 m和级（0～3级），与C3同源")

# ---- item 7: composition of the controlled records (new Table 5-19) and renumbering of the following tables
COMP = [
    ["安全基准", "堤基坡降；背水坡/临水坡FoS；护坡、内部隐患与变形状态逐档劣化", "0.10\n1.62/1.48", "0.15\n1.54/1.42", "0.17\n1.50/1.38", "0.19\n1.46/1.35", "0.21\n1.42/1.31"],
    ["漫顶", "堤顶高程与（设计洪水位＋超高）之差/m", "+0.8", "+0.2", "−0.2", "−0.9", "−1.8"],
    ["渗流", "堤基坡降比；巡检渗漏点密度/（点/100 m）", "0.35\n0", "0.55\n0.6", "0.75\n1.5", "0.95\n3.0", "1.15\n5.0"],
    ["边坡", "背水坡/临水坡FoS", "1.58/1.45", "1.43/1.32", "1.28/1.16", "1.08/1.04", "0.92/0.90"],
    ["冲刷", "冲刷深度/m", "0.20", "0.45", "0.75", "1.15", "1.60"],
    ["穿堤建筑物", "完好性、防洪标准、渗流稳定与结构安全状态", "一类\n完好", "一类\n完好", "三类\n待复核", "四类\n失效", "四类\n失效"],
    ["复合", "堤基坡降比；背水坡FoS；冲刷深度/m；全部定性指标同步劣化", "0.35\n1.50\n0.25", "0.55\n1.39\n0.50", "0.75\n1.28\n0.75", "0.95\n1.17\n1.00", "1.15\n1.06\n1.25"],
    ["参考等级", "—", "A", "A", "B", "C", "C"],
]
cap = caption_pair(E[1390], E[1391], E[1392], "表5-19　受控情景记录的构成", "Table 5-19 Composition of the controlled scenario records")
t519 = make_table(E[1434], [1150, 3006, 1050, 1050, 1050, 1050, 1050], ["情景类型", "主要改变的输入", "安全", "轻微", "中等", "严重", "临界"], COMP)
cap.addnext(t519)
ed.new_paragraph_after(t519, E[1435].find(W + "pPr"), E[1435].find(W + "r").find(W + "rPr"),
    "注：表中为各档的中心取值，同档25条记录在中心值附近随机扰动，7类情景、5档共875条；坡降比为堤基坡降与控制层临界坡降之比，堤身、接触面坡降分别按其0.85和0.95倍设定；漫顶情景同时改变风浪爬高与越浪量状态，渗流情景同时改变排水设施和穿堤渗流状态；严重、临界档另按整体劣化减小堤顶宽度、增大沉降。")
ed.replace(E[1391], "表5-19", "表5-20")
ed.replace(E[1392], "Table 5-19", "Table 5-20")
ed.replace(E[1432], "表5-20", "表5-22")
ed.replace(E[1433], "Table 5-20", "Table 5-22")

# ---- item 7/10: cases, their titles and data sources (new Table 5-21)
CASES = [
    ["案例一 受控情景下的模型对比", "9种评价方法的判别能力", "875条受控记录（表5-19）", "按规则设定"],
    ["案例二 受控情景的逐步评价", "单条记录的逐步计算过程", "4条典型受控记录", "按规则设定"],
    ["案例三 受控情景的多批次稳健性与策略选择", "结论稳定性与运行策略选择", "另5批受控记录（5个随机种子）", "按规则设定"],
    ["案例四 K45+500历史险情断面评价", "资料不完整、来源冲突时的追溯与敏感性分析", "断面资料、地勘参数和2017年管涌记录；35.90 m构造工况下的研究复算", "实际工程资料与复算"],
    ["案例五 渗流计算结果接入评价", "计算证据的接入", "第4章洞庭湖某垸断面Ⅰ、Ⅱ与三维计算域，30.00 m和33.89 m", "第4章计算成果"],
    ["案例六 真实巡检候选接入评价", "观测证据的接入与误报处理", "2025年8月28日现场巡检的2个候选（表5-12），以受控记录样本1为载体", "真实候选，设定载体"],
]
cap = caption_pair(E[1429], E[1432], E[1433], "表5-21　各案例的检验内容与数据来源", "Table 5-21 Purposes and data sources of the cases")
cap.addnext(make_table(E[1434], [2500, 2200, 3306, 1400], ["案例", "检验内容", "数据来源", "数据性质"], CASES))
ed.replace(E[1445], "案例二：典型情景的逐步评价", "案例二：受控情景的逐步评价")
ed.replace(E[1454], "案例三：多批次稳健性与策略选择", "案例三：受控情景的多批次稳健性与策略选择")
ed.replace(E[1463], "案例四：K45+500断面评价", "案例四：K45+500历史险情断面评价")
ed.replace(E[1486], "案例六：现场巡检结果接入评价", "案例六：真实巡检候选接入评价")

# ---- item 10: Case 4 states its data sources; no internal jargon ("交付")
ed.rewrite(E[1464], "前三个案例均基于受控情景，本案例转向实际工程的历史险情断面，检验评价链在实际资料不完整、来源存在冲突时的追溯与敏感性分析能力。K45+500断面位于一处匿名堤段2017年K44+500～K46+096的管涌险情段内，所用资料均为该断面的实际资料：断面尺寸取自断面资料，土层参数取自工程地质勘察报告的建议值，历史险情取自险情记录。渗流与边坡稳定计算采用研究复算成果，即按上述资料建立二维断面，以稳态有限差分法求解渗流场、以Bishop简化法复核边坡稳定；该成果并非第4章透明计算模型的输出，也不属于受控情景记录。该断面设计洪水位为33.89 m，评价水位取临水位35.90 m，高于设计洪水位约2.0 m、接近堤顶高程36.30 m，是为检验评价链在极端高水位下的表现而构造的不利工况，并非2017年险情发生时的实测水位。29项指标中14项有值、15项缺失，A8、A9、B2、D5在指标表与结果文件之间来源冲突；运行管理指标全部缺失，不施加屏障修正。主要指标及其证据状态见表5-24。")
ed.replace(E[1465], "表5-22", "表5-24")
ed.replace(E[1466], "Table 5-22", "Table 5-24")
ed.replace(cell(1467, 0, 1), "交付结果", "复算结果")
ed.replace(cell(1467, 1, 3), "计算值（交付摘录）", "计算值（复算）")
ed.replace(E[1468], "与交付结果一致", "与复算资料给出的结论一致")
ed.replace(E[1468], "表5-23和", "表5-25和")
ed.replace(E[1469], "表5-23", "表5-25")
ed.replace(E[1470], "Table 5-23", "Table 5-25")
ed.replace(cell(1471, 1, 0), "交付结果", "复算结果")
ed.replace(E[1475], "交付结果取深层", "复算结果取深层")
ed.replace(E[1477], "表5-24和", "表5-26和")
ed.replace(E[1478], "表5-24", "表5-26")
ed.replace(E[1479], "Table 5-24", "Table 5-26")

# ---- item 7: Case 6 says where the candidates come from
ed.replace(E[1487], "现场9个候选中", "5.2.4.11节现场巡检得到的9个真实候选中（表5-12）")
ed.replace(E[1487], "（0+001）", "（样本1）")
ed.replace(E[1487], "该记录仅作演示载体，不代表现场位置", "该记录仅作演示载体，不代表现场位置；候选所在堤段缺少完整的评价资料，因此借用受控记录比较两种规则的差异")

doc.write(str(doc_path), xml_declaration=True, encoding="UTF-8", standalone=True)
print(mode, "edits applied; revision ids up to", ed.nid)
