# 05 — The Fine Art of Fine-Tuning: a Structured Review

**Citation.** Pratap, Aranha, Kumar, Malhotra, Iyer, Shylaja S.S., "The
fine art of fine-tuning: A structured review of advanced LLM fine-tuning
techniques", Natural Language Processing Journal (Elsevier), Vol. 11,
June 2025, art. 100144, DOI 10.1016/j.nlp.2025.100144. CC BY 4.0 —
**yet full text unretrieved** (ScienceDirect/DOAJ/mirrors all 403);
extraction from verbatim DOAJ abstract + Crossref/S2 metadata +
reference list + indexed fragments. Citation count 33 as of 2026-08-27
[K, S2 snapshot].

## Claims

- Six-way taxonomy of fine-tuning efficiency techniques: training-method
  changes, adapter changes, quantization, parameter selection, MoE,
  application-based methods.
- PEFT (adapters on a frozen base) claimed comparable to full fine-tuning
  at a small fraction of trainable parameters.
- Quantization (Q8BERT, QLoRA, sub-4-bit) enables large-model tuning
  under memory constraints.
- Comparative-table survey collating OTHERS' benchmark results — not a
  new-method paper. The hint's "ontological reasoning / meta-training /
  enterprise" descriptors are secondary reference-list items, not the
  thesis.

## Numbers

- Six taxonomy categories [K, abstract]. Vol. 11, art. 100144, first
  available 2025-03-25/27 [K, Crossref].
- **No per-technique benchmark numbers retrievable** — the comparative
  tables (the paper's main quantitative payload) sit behind the 403;
  any specific figure attributed beyond the above would be fabrication.

## Limitations

- Access limitation is load-bearing: the collated tables are unverified.
- Author-stated scope: collates reported results without re-running under
  a common harness — cross-method comparisons inherit each source's
  train/test discipline; exactly the class of unvalidated headline
  numbers this repo treats as hypotheses.
- No leakage/overfitting audit of collated numbers; "comparable to full
  fine-tuning" claims come from large-n NLU benchmarks, not small-corpus
  regimes. Partially dated already.

## GAP ANALYSIS

**ALREADY AHEAD.**
- The survey's core argument (fewer trainable DoF on small corpora) is
  the weaker cousin of OF-7 DoF discipline:
  `scripts/overfit_check.py:919-941` (feature_dof_report, ≥10
  rows/feature floor) and `ml/models.py:834-841` (BlendModel's
  deliberately UNFITTED blend weight — "a tuned weight is one more degree
  of freedom to overfit"). Mechanism exists and is CI-pinned; the survey
  is citable backing, nothing more.
- Its tables are exercise-grade evidence with no kill-condition — the
  distinction OF-2/OF-3 already enforce; a number that reproduces only in
  its source repo's fixture is an un-pinned green (the corpus-line law),
  and, at literature scale, the same shape as session defects (a)/(b):
  a verdict that only holds in one host's state.

**ADOPTABLE.**
- Nothing mechanical. The one portable move — taxonomy-as-checklist,
  enumerating a technique space and marking what was measured where — is
  already shipped here (gate_truth_report effective-n standard,
  cohort_eval pre-registration). No new mechanism earned.

**NOT APPLICABLE.**
- The entire subject matter: this repo fine-tunes no LLMs, and model-side
  investment is frozen per the 2026-08-10 adjudication — every PEFT/
  quantization/MoE idea here is COHORT-IRRELEVANT and frozen. One line,
  closed. No hook for session defects (c)–(e) either — the paper is not
  about testing.
