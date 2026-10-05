from pathlib import Path

tex_path = Path(r'PROJECT_ROOT\英文论文_LaTeX_V1\transparent_levee_evaluation.tex')
text = tex_path.read_text(encoding='utf-8')
replacements = [
(r'''A performance-priority threshold policy reached 0.8731 accuracy and 0.8584 macro-F1 in the same controlled batch, but introduced 50 direct C-to-A underestimates. A safety-priority class-weighted policy removed all class-C underestimates at the cost of reducing accuracy to 0.7074 and increasing class-A overestimates to 179.''',
 r'''A performance-priority threshold policy reached 0.8731 accuracy and 0.8584 macro-F1 in the same controlled batch, but introduced 50 direct C-to-A underestimates. A physical-veto hybrid that imposed the rule-model grade as a lower risk bound reached 0.9257 accuracy, 0.9119 macro-F1, and 1.0000 class-C recall with zero C-class underestimates in the controlled batch. A safety-priority class-weighted policy also removed all class-C underestimates, but reduced accuracy to 0.7074 and increased class-A overestimates to 179.'''),
(r'''The paper makes four contributions. First, it formalizes an evidence-state and provenance model for integrating geological, seepage-field, and UAV inspection information. Second, it defines a reproducible benchmark in which duplicate physical feature vectors are grouped during cross-validation and target labels are derived from the frozen scenario severity rather than from delivered model outputs. Third, it compares a shallow decision tree and a random forest with the reproduced rule baseline and evaluates threshold policies through Pareto dominance and a safety loss. Fourth, it reports the current boundary of field evidence: nine reviewed field detections were false positives, while the remaining images and validation images do not yet provide a complete image-level truth set.''',
 r'''The paper makes five contributions. First, it formalizes an evidence-state and provenance model for integrating geological, seepage-field, and UAV inspection information. Second, it defines a reproducible benchmark in which duplicate physical feature vectors are grouped during cross-validation and target labels are derived from the frozen scenario severity rather than from delivered model outputs. Third, it compares a shallow decision tree and a random forest with the reproduced rule baseline and evaluates threshold policies through Pareto dominance and a safety loss. Fourth, it introduces a physics-veto hybrid that prevents the learned policy from lowering an existing physical risk grade. Fifth, it reports the current boundary of field evidence: nine reviewed field detections were false positives, while the remaining images and validation images do not yet provide a complete image-level truth set.'''),
(r'''Physical hard gates and evidence completeness checks have priority over the learned policy.''',
 r'''Physical hard gates and evidence completeness checks have priority over the learned policy.

\subsection{Physics-veto hybrid policy}
The grade labels are ordinal for decision purposes, with A, B, and C encoded as 0, 1, and 2. Let $\hat y_{\mathrm{RF}}$ be a learned prediction from Eq.~(\ref{eq:threshold}) and let $y_{\mathrm{rule}}$ be the final grade returned by the existing physics-based rule chain. We define a monotone physical-veto hybrid as
\begin{equation}
\hat y_{\mathrm{hyb}}=\max\left(\hat y_{\mathrm{RF}}, y_{\mathrm{rule}}\right).
\label{eq:veto}
\end{equation}
The operation is a decision-layer lower bound: the learned model may escalate a rule result, but it cannot make the result safer. It does not retrain either component and it leaves the evidence trace and triggered physical gate intact. As an operational variant, predictions with $\max_c p_c<0.60$ are routed to review and use $y_{\mathrm{rule}}$ as a fallback. The review rate and the fallback metrics are reported separately from the hybrid's closed-set classification metrics.'''),
(r'''All machine-learning results in the main text are controlled-batch results; a five-outer by three-inner grouped nested validation prototype is reported as a robustness check.''',
 r'''All machine-learning results in the main text are controlled-batch results; a five-outer by three-inner grouped nested validation prototype is reported as a robustness check. The physical-veto hybrid uses the fixed delivered rule output only at the decision layer and uses the OOF learned prediction for each held-out fold.'''),
(r'''RF safety weight 6 & .7074 & .7009 & .6829 & 1.0000 & 0 & 179 \\''',
 r'''RF safety weight 6 & .7074 & .7009 & .6829 & 1.0000 & 0 & 179 \\
RF + physical veto & .9257 & .9119 & .9276 & 1.0000 & 0 & 54 \\
RF + veto + review & .9109 & .8964 & .9143 & .9657 & 12 & 54 \\'''),
(r'''Thus, the machine-learning layer is useful as a nonlinear comparator and probability estimator, but not as a direct replacement for the physical rule chain.''',
 r'''Thus, the machine-learning layer is useful as a nonlinear comparator and probability estimator, but not as a direct replacement for the physical rule chain. The physical-veto hybrid retained the safety direction of the rule chain while correcting a subset of its A/B errors: it reached 0.9257 accuracy, 0.9119 macro-F1, 0.9276 balanced accuracy, and 1.0000 C recall, with zero C underestimates and a safety loss of zero. It changed 154 of the 875 decisions relative to the RF threshold policy. The uncertainty-review fallback routed 62 records (7.09\%) to the rule-based fallback and achieved 0.9109 accuracy, 0.8964 macro-F1, 0.9657 C recall, and 12 C-to-B underestimates, with no direct C-to-A errors.'''),
(r'''The persistence of direct C-to-A errors shows that selecting a C-recall constraint alone is insufficient. A safety-aware deployment policy must impose a direct C-to-A hard constraint, use a reject/manual-review state, or introduce a substantially higher safety loss.''',
 r'''The persistence of direct C-to-A errors shows that selecting a C-recall constraint alone is insufficient. The physical-veto hybrid demonstrates one auditable implementation of a direct C-to-A hard constraint, while the review fallback quantifies the associated manual-review burden. Because both policies are evaluated on the same controlled generator, they should be treated as architecture evidence rather than as independent field performance.'''),
(r'''The Pareto analysis changes the interpretation of ``improvement.'' The performance-priority policy improves accuracy and macro-F1 in the controlled batch, but it converts adjacent C-to-B errors into direct C-to-A errors.''',
 r'''The Pareto analysis changes the interpretation of ``improvement.'' The performance-priority policy improves accuracy and macro-F1 in the controlled batch, but it converts adjacent C-to-B errors into direct C-to-A errors. The physical-veto hybrid shows how this failure can be blocked without discarding the learned probability surface: the learned component remains responsible for upward corrections, while the rule chain supplies a safety floor.'''),
(r'''Random-forest probabilities enabled a performance-priority policy with 0.8731 accuracy and 0.8584 macro-F1, but the policy introduced 50 direct C-to-A underestimates. A safety-priority policy eliminated C underestimates at the cost of substantially more conservative escalations.''',
 r'''Random-forest probabilities enabled a performance-priority policy with 0.8731 accuracy and 0.8584 macro-F1, but the policy introduced 50 direct C-to-A underestimates. The physical-veto hybrid raised the controlled-batch accuracy to 0.9257 and macro-F1 to 0.9119 while keeping C recall at 1.0000 and C underestimates at zero; the optional review fallback retained zero direct C-to-A errors with a 7.09\% review rate. A safety-priority policy eliminated C underestimates at the cost of substantially more conservative escalations.'''),
]
for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'Expected one match, found {count}: {old[:80]}')
    text = text.replace(old, new)
tex_path.write_text(text, encoding='utf-8')
print('patched', tex_path)
