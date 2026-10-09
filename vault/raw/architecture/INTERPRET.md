# Post-hoc interpretability — the argued design

`ml/interpret.py` + `scripts/interpret_report.py`. Report-only: nothing
here writes config, state, or the decision path.

## The schools, argued

- **Lundberg (TreeSHAP, arXiv 1802.03888)**: Shapley values are the
  unique consistent additive attribution; for trees the INTERVENTIONAL
  (marginal) variant is the one that keeps consistency — the fast
  path-dependent variant is neither marginal nor conditional and can
  re-rank features between two trees computing the same function.
  *Verdict: adopted — and because our GBT grows depth≤2 trees (≤3
  features per tree), we compute interventional Shapley EXACTLY by
  subset enumeration against a history-spanning background stashed in
  the model artifact. No `shap` dependency, no kernel, no sampling.*
- **Slack et al. (Fooling LIME/SHAP, arXiv 1911.02508)**: perturbation-
  sampled explainers probe off-manifold points a scaffolded model can
  detect and deceive. *Verdict: the attack surface is the sampler; exact
  enumeration has none. The report re-proves fidelity every run via the
  additivity audit: |base + Σφ − margin| at machine epsilon.*
- **Rudin (arXiv 1811.10154)**: an explanation that cannot be faithful
  breeds misplaced trust; prefer models interpretable by construction.
  *Verdict: half-adopted. The ladder already prefers simple models
  (logistic rung, simplicity-ladder OF discipline). Where exactness
  exists (logistic, gbt) we explain; where it does not (mlp/ensemble)
  we REFUSE rather than guess. Refusal is a feature.*
- **Hooker & Mentch (arXiv 1905.03151) + López de Prado (clustered
  MDA)**: permute-and-predict importance forces extrapolation when
  features correlate, and substitution effects split credit until two
  informative twins both look useless. MDI/gain importance cannot say
  "nothing matters" (it normalizes to 100%). *Verdict: permutation runs
  on CORRELATION CLUSTERS as a block, on a time-ordered held-out tail,
  Brier as the metric — and it can (and does) call clusters useless.*

## What the report emits (outputs/interpret_report.{md,json})

1. Clustered permutation importance — OOS Brier delta per cluster.
2. Attribution fingerprint — share of mean |φ| per feature, exact.
3. Additivity audit — hard proof the explainer is exact on THIS model.
4. Attribution drift — fingerprint cosine between eval halves; reasons
   can rotate before scores move (labels not required).

## Hardening interplay

- The background sample rides the artifact (`background` key), so any
  deployed champion is explainable without its training corpus.
- Fingerprint drift complements ML-031 input drift: PSI watches the
  INPUTS, the fingerprint watches the REASONS.
- Findings feed conscious schema revisions and the gated tuning pass —
  never mid-flight feature surgery (overfit discipline unchanged).

## Sources

- Lundberg, Erion, Lee — Consistent Individualized Feature Attribution
  for Tree Ensembles: <https://arxiv.org/abs/1802.03888>
- Rudin — Stop Explaining Black Box ML Models for High Stakes
  Decisions: <https://arxiv.org/abs/1811.10154>
- Slack, Hilgard, Jia, Singh, Lakkaraju — Fooling LIME and SHAP:
  <https://arxiv.org/abs/1911.02508>
- Hooker, Mentch — Please Stop Permuting Features:
  <https://arxiv.org/abs/1905.03151>
- López de Prado — Clustered Feature Importance (Machine Learning for
  Asset Managers): <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3517595>
- Molnar — Interpretable Machine Learning (SHAP chapter):
  <https://christophm.github.io/interpretable-ml-book/shap.html>
- Attribution-distribution model monitoring (label-free):
  <https://arxiv.org/abs/2501.10774>
