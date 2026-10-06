# English LaTeX paper: version notes

## Revision of 2026-10-05 (V2)

Revision guided by the nature-skills writing, polishing, figure and reference-verification
workflows (paper type: methods; journal: generic, IEEE layout).

### Argument

One-sentence argument: in levee seepage grading, an ordinal physical floor lets a learned
layer improve a physics-based rule chain without creating false-safe downgrades, because the
composition underestimates only where both components do; we show this on a controlled
875-record benchmark and five additional generator seeds, and bound it by the shared generator
and the absence of field labels.

### Content changes

- Title rewritten around the demonstrated contribution (ordinal physical floor, evidence-state
  control); the earlier title promised geological integration that is not tested.
- Abstract rebuilt as an evidence chain and shortened from 304 to 242 words (IEEE limit 250).
- Introduction rebuilt as a funnel ending in three research questions; the gap is now stated as
  an unknown (how to compose learned and physical grades without false-safe downgrades) rather
  than as the absence of the method.
- Related work grouped by mechanism; each subsection ends with the limitation this paper addresses.
- Method: added Proposition 1 (error-set algebra of the ordinal floor) with proof; precise
  description of the NumPy CART/RF implementation, split-candidate rule, cost-weighted bootstrap
  and threshold-selection rule; defined the C-only floor and the offline review proxy.
- Protocol: added the statistical-analysis subsection (exact McNemar, grouped paired bootstrap,
  Clopper-Pearson) and grouped-CV leakage references.
- Results restructured as a claim ladder (rule chain -> learned layer -> floor -> robustness ->
  review -> inspection -> engineering trace). New evidence, all reproducible from
  `experiments/analysis/paper_revision/`:
  - all 50 direct C->A errors of the RF policy occur in the through-structure mode, where all
    125 records share one 14-feature vector (a feature blind spot, not a threshold problem);
  - the floor corrected 71 of 136 rule errors and introduced none (p < 1e-20), and introduced no
    new error in any additional seed; group-bootstrap intervals for the gains;
  - the RF threshold policy's accuracy gain over the rule chain is not significant (p = 0.11);
  - C-only versus ordinal floor ablation (C-only issued 3 direct C->A in seed 20260932);
  - inspection-feature ablation of the learned layer; inspection-channel ablation of the rule chain;
  - reviewer-stated causes of the 9 field false positives and a Clopper-Pearson bound (0.28);
  - K45+500 provenance table (15/29 indicators missing, 4 conflicts, code-version difference).
- Corrected a misleading statement: the majority-vote RF's lower C-underestimate count (51 vs 57)
  consisted entirely of direct C->A errors (safety loss 102 vs 57) and its C-recall gain did not
  replicate across seeds.
- Review-budget results reframed: with a rule-grade fallback, routing can only remove upward
  corrections, so the sweep measures the proxy, not engineering review.
- Discussion rewritten around anchor, positioning, rival explanations (generator-aligned gates;
  missing structure features), claim-specific limitations and discriminating next tests.
- Terminology ledger applied (rule chain; ordinal physical floor / floor hybrid labelled
  "RF + ordinal floor"; C-only floor; five additional generator seeds; one precision per metric).

### Presentation changes

- IEEEtran `journal` layout instead of `conference` (the conference layout had forced `\tiny`
  references and `\enlargethispage`). Revert with one line if a conference venue is chosen.
- New TikZ framework figure (Fig. 1).
- Four data figures regenerated as vector PDFs with one palette (red reserved for direct C->A),
  5 pt glyph floor, and passing panel-alignment and rendered-collision audits: error structure
  with per-mode error location (Fig. 2), quality versus direct C->A over all 10,000 thresholds
  (Fig. 3), multi-seed and review-budget panels (Fig. 4), inspection evidence states (Fig. 5).
  The four former PNG figures were removed.
- Tables: full-width main comparison with error-direction columns (Table II), multi-seed table
  including the C-only floor and both review thresholds (Table III), K45+500 provenance table
  (Table IV). All table values generated with half-up rounding from the stored outputs.
- References moved to BibTeX (37 entries, all cited).

### Reference verification

- Corrected GemPy author initials (M. de la Varga, A. Schaaf, F. Wellmann) and completed the
  author list of Xu et al. (B. Xu, Z. Liu, R. Pang, Y. Zhou).
- Chen et al. (2024) was listed but never cited; it is now cited in Related Work.
- Fourteen references added (piping statistics, backward erosion piping, PROV-DM, thermographic
  seepage detection, interpretable/theory-guided ML, cost-sensitive learning, reject option,
  selective classification, leakage, grouped CV, McNemar, Dietterich, Clopper-Pearson, bootstrap).
- `references.bib` marks each entry [V] verified or [C] check suggested. Hou et al. (2026): title,
  journal and year confirmed; author list, volume and pages could not be confirmed because the
  publisher sites were not reachable from the working environment. Crossref was also unreachable,
  so DOIs were confirmed by web search.

## Open items before submission

1. Replace placeholder author, affiliation and funding metadata.
2. Confirm the target journal and its template, length and reference style.
3. Confirm the [C] fields of Hou et al. (2026) and the page/article numbers of Roscoe and Hanea
   (2015) and Kumar et al. (2025).
4. Obtain independent field labels and run the floor and review protocol on them before any
   claim of field generalization (see Discussion).
5. Synchronize the Chinese chapter through the same terminology ledger once the English
   argument is accepted.

## Follow-up revision (2026-10-05)

- Added a concise operational decision protocol that freezes the evaluation key, assigns evidence states, preserves model and gate traces, applies the ordinal floor, and separates review routing from grade publication.
- Tightened the Pareto definition with a strict-improvement clause; macro-F1, balanced accuracy and critical-class recall are maximized while safety loss is minimized. The pure-RF front is reported as having no quality--safety trade-off, and escalation rate remains an operational resource coordinate.
- Corrected the inspection statement to report the exact one-sided 95% upper bound of 0.28 for 0/9 confirmed candidates.
- Clarified that safety loss is an offline evaluation metric requiring a reference class, and removed the internal negative-spacing layout adjustment. Recompiled the IEEE journal manuscript to 9 pages with no fatal, undefined-reference or overfull-box diagnostics in the final local build.

## Decision-algorithm and evaluation-system revision (2026-10-06, V3)

Requested additions: a schematic of the multi-objective evaluation system, sections on the decision
algorithm and the evaluation system with an explicit statement of what lacks validation, and
comparison baselines. The manuscript grew from 9 to 13 pages.

### Added

- New Section IV, "Decision Algorithm and Multi-Objective Evaluation System": policy space
  (learner x threshold pair x floor scope, Eq. 6), four-objective vector and strict dominance
  (Eqs. 7-9), resource coordinates kept out of dominance, two declared constraint sets (benchmark
  constraints; physical-floor constraint), lexicographic safety-first selection with a
  distance-to-ideal check, family hypervolume (Eq. 10), transfer test, Algorithm 1 (offline
  calibration and selection), Algorithm 2 (online grading; replaces the former operational
  protocol paragraph), baseline definitions, and Table II (validation status of every component).
- Fig. 2: TikZ schematic of the evaluation system (`figures/fig_evaluation_system.tex`).
- Fig. 6: policy-space evaluation (all 4051 policies; feasible set; hypervolume by learner and floor).
- Table V: eight new baselines (LR, ordinal LR, SVM, GBDT, expected-cost RF, soft vote, confidence
  switch, stacked RF) plus every learned-only baseline with the ordinal floor, on the original batch
  and five seeds, with downward-override and new-error counts.
- Table VI: policies selected by the evaluation system, in batch and in transfer.
- Seven verified references (stacking, ordinal classification, gradient boosting, SVM, scikit-learn,
  two hypervolume/performance-assessment papers).

### Findings reported (all reproducible with `experiments/analysis/paper_revision/baselines_and_pareto.py`)

- Every learned-only baseline issued at least 50 direct C->A decisions; RF and GBDT assign
  p_C = 0 and <= 1.1e-6 to all through-structure records, so no threshold or expected-cost rule helps.
- The ordinal floor removed C->A for every learner in all six batches; it inherits each learner's
  overestimates (new errors relative to the rule chain: LR 47, SVM 28, GBDT 1, RF 0, stacked RF 0).
- The stacked RF (rule grade as input) reached 0.994 accuracy only by lowering 50 rule grades, all
  seepage- and mixed-mode A records that the rule chain escalated; correct on benchmark labels,
  untested on field labels.
- Evaluation system: under benchmark constraints the selected policy is the stacked RF without a
  floor (transfer accuracy 0.996 +/- 0.001, 50 downward overrides per seed); with the physical-floor
  constraint it is the stacked RF with the ordinal floor (transfer 0.939 +/- 0.001, no C-class
  underestimate), 1.8 points above the declared RF + floor. Both selection rules agree in all six
  batches. The price of the physical-floor constraint within the generator is 5.7 points of accuracy.
- Learned-only families never dominate the rule chain (hypervolume 0.42-0.59 vs 0.545); with the
  ordinal floor, hypervolume is 0.73-0.88 for every learner.

### Still unvalidated (stated in Table II and the Discussion)

Objective set and the 2:1 weight in L_safe, constraint thresholds, the lexicographic order, the
review gate, and above all the safety of learned downward overrides, which only field labels can
test. The Chinese manuscript (`paper/chinese/`) has not yet been synchronized with this revision.

## Earlier version (V1)

Internal V1 draft: rule baseline, grouped OOF tree and forest comparisons, Pareto threshold
policies, nested validation, physical-veto hybrid, five additional generator seeds, a 10,000-point
threshold audit and a review-budget sweep. Multi-seed artifacts are under
`experiments/analysis/875多种子稳健性/`.
