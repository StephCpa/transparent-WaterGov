# Transparent levee evaluation: English LaTeX manuscript

Main source: `transparent_levee_evaluation.tex` (IEEEtran journal layout, BibTeX
references in `references.bib`, IEEEtran bibliography style).

Build:

```bash
pdflatex transparent_levee_evaluation && bibtex transparent_levee_evaluation \
  && pdflatex transparent_levee_evaluation && pdflatex transparent_levee_evaluation
```

Figures:

* Fig. 1 (framework) is drawn in TikZ inside the `.tex` file.
* Figs. 2-5 are vector PDFs in `figures/`, generated from repository data by
  `experiments/analysis/paper_revision/make_paper_figures.py`; the statistics they
  use come from `experiments/analysis/paper_revision/paper_statistics.py`.

Status: internal working draft (revision of 2026-10-05). Author metadata, funding,
target journal and a final reference check remain open; see `VERSION_NOTES.md`.

Evidence boundary: the 875-record benchmark and the five additional seed batches
are controlled synthetic experiments from one generator; the nine field inspection
detections are a manual-review subset (0/9 confirmed piping), not a field-wide
accuracy estimate; the K45+500 case is a provenance trace, not a blind validation.
Multi-seed artifacts are under `experiments/analysis/875多种子稳健性/`.
