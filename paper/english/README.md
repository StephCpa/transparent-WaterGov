# Transparent levee evaluation: English LaTeX working draft

Main source: `transparent_levee_evaluation.tex`.

The paper uses the IEEEtran conference class and four copied figures under `figures/`. The current manuscript is an internal V1 draft. It now includes a physics-veto hybrid and an uncertainty-review fallback in addition to the RF/Pareto comparison. Author metadata, funding, final references, and target-journal formatting still need to be completed.

Evidence boundary: the 875-record results are controlled synthetic experiments; the nine field inspection detections are a manual-review subset (0/9 confirmed piping), not a field-wide accuracy estimate; the K45+500 case is a provenance trace, not a blind validation.

Robustness update: five additional generator seeds (20260930--20260934) were evaluated with the same grouped OOF protocol. Their aggregate results and per-seed artifacts are under `分析工作区/875多种子稳健性/`; these runs test within-generator reproducibility and do not establish field generalization.

