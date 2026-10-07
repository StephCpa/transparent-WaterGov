# 第5章 Word 稿的生成（2026-10-07）

本目录生成 `paper/chinese/chapters/chapter5_transparent_evaluation.docx`（第5章 融合渗流机理与空基巡检病害信息的堤防渗流安全透明评价）及其插图 `paper/chinese/chapters/figures_ch5/`。

## 章节结构

按审阅意见重组为“评价框架—指标体系—巡检信息获取—评价方法—评价标准—评价流程与算例”：

| 节 | 内容 |
|---|---|
| 5.1 | 引言 |
| 5.2 | 评价对象与结论（表5.1）、总体框架（图5.1）、“透明”的含义与四项创新 |
| 5.3 | 指标体系：层次结构（图5.2、表5.2）、量化方法、权重与失效模式关联 |
| 5.4 | 透明巡检：作用与要求、巡检方案（表5.3）、红外预处理、P2ES-YOLO识别算法与对比实验设计（表5.4，数据待补）、现场结果（图5.4）、空间配准 |
| 5.5 | 评价理论与方法：模型结构（图5.5）、证据状态（创新一）、巡检“输入—约束—触发”（创新二）、规则链、随机森林、序数物理下限（创新三）、多目标策略评价（创新四，图5.6） |
| 5.6 | 评价标准与阈值：等级划分、门控阈值、巡检证据判定与预警分级 |
| 5.7 | 实施流程（表5.11）与五个算例：受控基准方法对比（图5.7）、典型情景逐步评价、对比基线与策略选择、K45+500全过程与证据敏感性、现场巡检结果接入对比 |
| 5.8—5.9 | 适用条件与局限、小结 |

共7幅图、16个表、20个编号公式，新增第192—217号参考文献。正文中以【待补】标出的三处（辐射温度图的温度反演与温差统计、训练/验证/测试数据与标注一致性、后处理步骤对误报的影响）及表5.4的数值，待巡检子课题提交资料后补入。

## 运行

```bash
python3 experiments/analysis/chapter5_zh/prepare_cjk_fonts.py        # 一次性：从 fonts-noto-cjk 提取简体中文字形到 ~/.cache/ch5_cjk_fonts（约2—3分钟）
python3 experiments/analysis/chapter5_zh/make_chapter5_schematics.py # 图5.1—图5.3、图5.5、图5.6（示意图）
python3 experiments/analysis/chapter5_zh/make_chapter5_figures.py    # 图5.4、图5.7 及两幅补充图（数据图）
python3 experiments/analysis/chapter5_zh/case_analyses.py            # 5.7节算例的逐步数值，写入 case_analyses.json
python3 experiments/analysis/chapter5_zh/build_chapter5_docx.py      # 生成 docx
```

依赖：Python ≥ 3.10、NumPy、Matplotlib、fontTools，以及 Liberation Serif 与 Noto Serif CJK 字体。数据图只读取仓库文件（`paper_revision/` 的统计结果、`ml_baseline与多目标/cost_sensitive_results.json`、`inspection/audit/` 审计表及现场红外图像文件名），作图逻辑与断言沿用英文稿的 `make_paper_figures.py`，所绘数值与英文稿一致。`case_analyses.py` 调用 `data/875_benchmark/3_样本生成与参考规则/` 中未改动的交付评价代码，并断言复现 K45+500 的交付得分。

## 文件

| 文件 | 内容 |
|---|---|
| `chapter5_source.txt` | 章节正文、表格、公式与图题的源文本（简单行标记，见 `build_chapter5_docx.py` 文件头） |
| `build_chapter5_docx.py` | 以第2章 docx 的样式、主题、字体表与设置为模板，逐段写入与第1、2章相同的直接格式 |
| `make_chapter5_schematics.py` | 总体框架（图5.1）、指标体系（图5.2）、巡检与识别流程（图5.3）、评价模型结构（图5.5）、多目标策略评价流程（图5.6） |
| `make_chapter5_figures.py` | 现场候选与采集时刻（图5.4）、错误结构（图5.7）；补充图 `fig5_supp_safety_tradeoff`（支撑5.7.2节“10 000组阈值”的断言）与 `fig5_supp_policy_evaluation`（5.7.4节多目标评价结果，未放入正文） |
| `case_analyses.py`、`case_analyses.json` | 5.7.3节四条典型记录、5.7.5节K45+500的四种证据处理方式、5.7.6节巡检候选接入对比的计算 |
| `prepare_cjk_fonts.py` | 从 Noto CJK 字体集合中提取简体中文字形并转为 TrueType 轮廓 |

## 格式约定（与第1、2章一致）

Letter 纸、四边 2.5 cm；正文宋体/Times New Roman 小四、1.5 倍行距、首行缩进 2 字符；章标题黑体四号加粗居中，节标题黑体小四加粗；图题置于图下、表题置于表上，五号；三线表；引文为上标 [n]；公式居中并按（5-n）右侧编号。

## 需在统稿时处理

* 参考文献编号：沿用第1章的编号引用其已有文献（如 [28]、[125]、[136]），本章新增文献从 [192] 起编（第2章止于 [191]）；第3、4章定稿后需统一重排。
* 改进检测器（P2ES-YOLO 等）的训练集、测试集与对比实验不在本资料包中，5.4.3、5.4.4节与表5.4已列出提纲与实验设计，待巡检子课题提交后补入。
* K45+500 算例（5.7.5节）表明结论对 C1 取值部位敏感（深层黏土层坡降比1.045为C级，出逸区粉细砂层0.410为B级），建议在专业复核前按等级范围“B—C级”报告。
* 页数：LibreOffice（Noto 字体替代宋体）渲染30页；按第1、2章在同一环境下的渲染页数与 Word 页数之比（约0.94—0.97），在 Word 中约28页。【待补】内容补齐后还会增加。
