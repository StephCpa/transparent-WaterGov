# Paper revision analyses (2026-10-05)

Scripts and outputs behind the statistics and data figures of the revised English
manuscript (`paper/english/transparent_levee_evaluation.tex`). All three scripts read
repository files only and reuse the unchanged model code of
`ml_baseline与多目标/run_ml_baselines.py` (class and function definitions are
extracted with `ast`, so that file's training side effects are not executed).

## Run

Python >= 3.10 with NumPy and Matplotlib; scikit-learn (1.9.1 used) for the comparison baselines; Liberation Sans (or Arial) for figure text.

```bash
python experiments/analysis/paper_revision/paper_statistics.py   # ~3 min, writes the JSON/CSV below
python experiments/analysis/paper_revision/baselines_and_pareto.py  # ~5 min, baselines and policy-space evaluation
python experiments/analysis/paper_revision/make_paper_figures.py # writes paper/english/figures/*.pdf
```

Setting `NATURE_FIGURE_SCRIPTS` to the `scripts/` directory of the nature-figure
skill enables the render-time panel-alignment gate before export.

## Outputs

| File | Content |
|---|---|
| `paper_statistics.json` | Original-batch metrics for all policies, hybrid-versus-rule and hybrid-versus-RF error decomposition, rule/RF C-error complementarity, exact McNemar tests, grouped paired bootstrap (2000 resamples over 722 feature-vector groups), C-only versus ordinal floor, inspection-feature ablation of the learned layer, per-target-mode accuracy, reproduced cost-weighted forests, the same analyses on the five additional seeds, and the Clopper-Pearson bound for 0/9 confirmed field candidates. |
| `per_record_predictions_875.csv` | Per-record reference class, rule grade, RF majority, RF threshold, ordinal floor, C-only floor and review-fallback decisions, and OOF class probabilities for the 875 original records. |
| `baselines_and_pareto.json` | Comparison baselines (learned-only, rule-aware fusion, every learner with the ordinal floor) with downward-override and new-error counts; policy-space evaluation of 4051 policies per batch (feasible counts, strict Pareto fronts with and without the physical-floor constraint, family hypervolumes, lexicographic and distance-to-ideal selections, transfer of the original-batch selection to the five seeds) for the original batch and five seeds. |
| `policy_cloud_875.csv` | Objectives, resources, feasibility and front membership of all 4051 policies on the original batch (Fig. 6). |
| `figure_qa/*.json` | Panel-alignment and rendered-collision audit reports for each figure (PNG/SVG previews are regenerated locally and not tracked). |

## Checks built into the scripts

* The cost-weighted forests are re-run with the original fold seeds and asserted to match `cost_sensitive_results.json`.
* The figure script asserts that no pure RF threshold pair on the 0.01 grid reaches zero direct C→A errors; the manuscript text depends on that result.
* Re-running `run_hybrid_veto.py` with the repository data reproduced `hybrid_veto_results.json` exactly.

## Findings added to the manuscript

* In the through-structure target mode all 125 records share one 14-feature vector (identical to the safe-reference vector), so the learned layer cannot separate their severities; all 50 direct C→A errors of the RF threshold policy occur there.
* The ordinal floor corrected 71 of the rule chain's 136 errors and introduced none (exact McNemar p < 1e-20); it introduced no new error relative to the rule chain in any of the five additional seeds.
* The RF threshold policy's accuracy gain over the rule chain was not significant within the original batch (125 vs 100 discordant records, p = 0.11) and reached p < 0.05 in one of five additional seeds.
* A C-only floor has higher accuracy but lower balanced accuracy and, in seed 20260932, issued three direct C→A decisions where the ordinal floor issued C→B.

## Revision V3 additions (2026-10-06)

`baselines_and_pareto.py` fixes every setting before evaluation (no hyperparameter search) and uses
the same features, grouped folds and reference labels as the RF. Its threshold grid is built exactly
as in `run_pareto_policy.py`, so the RF numbers reproduce the earlier results. Main findings:

* every learned-only learner issues at least 50 direct C→A decisions (the blind spot is in the features);
* the ordinal floor removes them for every learner and adds no error to the rule chain with the RF;
* the stacked RF (rule grade as input) is benchmark-optimal only because it lowers 50 rule grades;
* with the physical-floor constraint the selected policy is the stacked RF with the ordinal floor,
  which transfers to the five seeds at 0.939 ± 0.001 accuracy without a C-class underestimate.
