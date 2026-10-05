# English LaTeX paper V1: revision notes

## Scope

This is a method-oriented working manuscript for the transparent evaluation component of the five-transparent levee framework. It is intentionally written as a research paper rather than as a direct translation of the Chinese chapter.

## Evidence used

- Reproduced rule baseline on 875 controlled synthetic scenarios.
- Grouped five-fold OOF decision-tree and random-forest comparisons.
- Exploratory Pareto threshold policies, a 5-outer x 3-inner nested-validation prototype, and a physical-veto hybrid policy.
- UAV/infrared inspection records: 114 field images, 9 reviewed field detections (all false positives), 13 artificial validation images and 14 output boxes.
- K45+500 delivery case as a provenance/interface trace, not independent blind validation.

## Claims deliberately bounded

The controlled benchmark is generated from a prescribed severity design and is not a field truth set. The physical-veto hybrid combines the held-out random-forest prediction with the delivered physical-rule grade at the decision layer; its 0.9257 accuracy and zero C underestimates are architecture evidence from the same controlled batch, not an independent engineering gain. The manuscript does not report field-wide inspection accuracy, early-warning lead time, or a validated digital-twin closed loop. The representative RF threshold policy is explicitly not presented as the engineering deployment policy because it creates direct C-to-A underestimates.

## Next revision gates

1. Replace placeholder author and funding metadata.
2. Confirm target journal and switch IEEEtran conference layout to the required template if needed.
3. Verify every bibliographic record against the source paper and add DOI/URL fields where required.
4. Five additional generator seeds (20260930--20260934) have now been evaluated with the same feature exclusions, grouped OOF protocol, RF thresholds, and physical-veto policy. The seed results are stored under `分析工作区/875多种子稳健性/`; they support within-generator reproducibility but do not replace independent field labels.
5. Obtain independent field labels and run the safety-constrained reject/manual-review protocol before claiming field generalization.
6. After the English argument is accepted internally, translate the final version into Chinese and keep the Chinese chapter synchronized through the same terminology ledger.



Additional ablation: a 10,000-point, 0.01-step pure-RF threshold sweep found no policy with zero direct C-to-A errors. The zero-C-to-A result therefore belongs to the explicit physical-veto decision layer rather than RF thresholding alone.
- A review-budget sweep over uncertainty thresholds was added. The exploratory u=0.50 point meets review-rate <=5% and safety-loss <=6 on all five additional seeds; it is a protocol candidate, not an externally validated operating point.
