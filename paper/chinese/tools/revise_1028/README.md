# 1028 版论文修改脚本

在 `堤防渗流安全全链条透明化方法及其数字孪生技术研究_1028修改.docx` 上复现两个输出文件（修订说明见 `../../1028修改说明.md`）。

```bash
unzip -q 1028修改.docx -d unpacked && python3 <docx-skill>/scripts/merge_runs.py unpacked/
cp -r unpacked work_track && cp -r unpacked work_clean
python3 revise.py work_track track ../../chapters/figures_ch5_thesis/fig5_devices_field.png ../../chapters/figures_ch5_thesis/fig5_typical_records.png
python3 revise.py work_clean clean ../../chapters/figures_ch5_thesis/fig5_devices_field.png ../../chapters/figures_ch5_thesis/fig5_typical_records.png
(cd work_track && zip -q -X -r ../修订痕迹.docx .) ; (cd work_clean && zip -q -X -r ../修订稿.docx .)
```

`revise.py` 按 1028 原稿 `word/document.xml` 的正文元素序号定位段落，并在修改前核对原文（找不到或不唯一时报错），只适用于该底稿。
`docxedit.py` 为通用的按字符区间替换工具，`track` 模式下以 `w:ins`/`w:del` 记录修订。
