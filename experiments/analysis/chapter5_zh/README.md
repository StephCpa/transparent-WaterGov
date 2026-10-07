# 第5章 Word 稿的生成（2026-10-07）

本目录生成 `paper/chinese/chapters/chapter5_transparent_evaluation.docx`（第5章 融合渗流机理与空基巡检病害信息的堤防渗流安全透明评价）及其插图 `paper/chinese/chapters/figures_ch5/`。

## 运行

```bash
python3 experiments/analysis/chapter5_zh/prepare_cjk_fonts.py      # 一次性：从 fonts-noto-cjk 提取简体中文字形到 ~/.cache/ch5_cjk_fonts
python3 experiments/analysis/chapter5_zh/make_chapter5_schematics.py # 图5.1、图5.3（方法示意图）
python3 experiments/analysis/chapter5_zh/make_chapter5_figures.py    # 图5.2、图5.4—图5.6（数据图）
python3 experiments/analysis/chapter5_zh/build_chapter5_docx.py      # 生成 docx
```

依赖：Python ≥ 3.10、NumPy、Matplotlib、fontTools，以及 Liberation Serif 与 Noto Serif CJK 字体。数据图只读取仓库文件（`paper_revision/` 的统计结果、`ml_baseline与多目标/cost_sensitive_results.json`、`inspection/audit/` 审计表及现场红外图像文件名），作图逻辑与断言沿用英文稿的 `make_paper_figures.py`，所绘数值与英文稿一致。

## 文件

| 文件 | 内容 |
|---|---|
| `chapter5_source.txt` | 章节正文、表格、公式与图题的源文本（简单行标记，见 `build_chapter5_docx.py` 文件头） |
| `build_chapter5_docx.py` | 以第2章 docx 的样式、主题、字体表与设置为模板，逐段写入与第1、2章相同的直接格式 |
| `make_chapter5_schematics.py` | 评价决策链（图5.1）与多目标策略评价体系（图5.3） |
| `make_chapter5_figures.py` | 巡检候选与采集时刻（图5.2）、错误结构（图5.4）、质量—安全权衡（图5.5）、策略空间评价（图5.6） |
| `prepare_cjk_fonts.py` | 从 Noto CJK 字体集合中提取简体中文字形并转为 TrueType 轮廓 |

## 格式约定（与第1、2章一致）

Letter 纸、四边 2.5 cm；正文宋体/Times New Roman 小四、1.5 倍行距、首行缩进 2 字符；章标题黑体四号加粗居中，节标题黑体小四加粗；图题置于图下、表题置于表上，五号；三线表；引文为上标 [n]；公式居中并按（5-n）右侧编号。

## 需在统稿时处理

* 参考文献编号：沿用第1章的编号引用其已有文献（如 [28]、[125]、[136]），本章新增文献从 [192] 起编（第2章止于 [191]）；第3、4章定稿后需统一重排。
* 改进检测器（P2ES-YOLO 等）的训练集、测试集与对比实验不在本资料包中，5.3.2 节已注明待巡检子课题提交后补入。
* 页数以 LibreOffice（Noto 字体替代宋体）渲染约 20 页，按第1、2章的换算关系在 Word 中约 18—19 页。
