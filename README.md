# Transparent WaterGov: safety-aware levee seepage evaluation

This repository contains a de-identified research release for a transparent levee seepage-stability evaluation study.

## Contents

- paper/english/: IEEE-style English LaTeX manuscript, figures, PDF, and references.
- paper/chinese/: Chinese working manuscripts and chapter drafts.
- data/875_benchmark/: controlled 875-scenario benchmark and reference-rule implementation.
- data/supplementary/: indicator definitions, sensitivity analyses, parameter files, and engineering-case materials.
- experiments/analysis/: reproducible scripts, logs, metrics, figures, and multi-seed robustness analyses.
- inspection/audit/: de-identified inspection audit tables and summaries.
- inspection/raw/: image and text materials with image metadata stripped where possible.
- notes/ and research/: protocols, manifests, and reproducibility notes.
- outputs/: selected non-identifying rendered figures and tables.

## Scope and evidence boundary

The benchmark and additional seed batches are controlled generator realizations. They support reproducibility and decision-layer ablations, not independent field generalization. The inspection package contains candidate and review states; it should not be interpreted as a complete image-level truth set.

## De-identification

Institution, project-owner, account, password, absolute workstation path, and other direct organizational identifiers were removed or replaced in text metadata. Office documents, source PDFs with embedded affiliations, and compressed archives were excluded when they could not be safely de-identified without altering the underlying source. Raw images were copied without EXIF metadata where the image library permitted it.

## Reproduction

See the scripts and protocol notes under experiments/analysis/ and notes/. The English manuscript is paper/english/transparent_levee_evaluation.tex.
