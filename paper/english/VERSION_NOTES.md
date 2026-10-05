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
- Tightened the Pareto definition: macro-F1, balanced accuracy and critical-class recall are maximized while safety loss is minimized; escalation rate is reported as an operational resource coordinate.
- Corrected the inspection statement to report the exact one-sided 95% upper bound of 0.28 for 0/9 confirmed candidates.
- Recompiled the IEEE journal manuscript to 9 pages with no fatal, undefined-reference or overfull-box diagnostics in the final local build.

## Earlier version (V1)

Internal V1 draft: rule baseline, grouped OOF tree and forest comparisons, Pareto threshold
policies, nested validation, physical-veto hybrid, five additional generator seeds, a 10,000-point
threshold audit and a review-budget sweep. Multi-seed artifacts are under
`experiments/analysis/875多种子稳健性/`.
