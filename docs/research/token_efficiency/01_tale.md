# 01 — TALE: Token-Budget-Aware LLM Reasoning

**Citation**: Han, Wang, Fang, Zhao, Ma, Chen. "Token-Budget-Aware LLM Reasoning."
arXiv:2412.18547 (v1 2024-12-24, v5 2025-06-02), ACL 2025 Findings. Code:
github.com/GeniusHTX/TALE. Nanjing Univ. / Rutgers / UMass Amherst.

## Claims

- CoT traces are unnecessarily long; a prompt-stated token budget ("use less than N
  tokens") compresses reasoning substantially with small accuracy loss — IF the budget is
  well-chosen per problem.
- **Token elasticity**: budgets below a problem-dependent feasible range backfire — the
  model ignores the constraint and reverts to long reasoning, so realized cost goes UP.
  Cost-vs-budget is non-monotonic with an interior optimum.
- **TALE-EP**: one zero-shot call estimates the budget the specific problem needs; the
  estimate is spliced into the CoT prompt. Training-free, works on closed API models.
- **TALE-PT**: internalize budget awareness via SFT/DPO on budget-optimal traces found by
  binary→greedy search (correct AND cheaper than prior budget).

## Numbers

- Headline (TALE-EP, GPT-4o-mini, avg over datasets): −67% output tokens, −59% expense,
  <3% accuracy drop vs vanilla CoT (81.03% acc / 148.72 tok vs 83.75% / 461.25 tok).
- GSM8K: TALE-EP 84.46% @ 77.26 tok vs CoT 81.35% @ 318.10 (accuracy UP +3.11pt at 4.1x
  fewer tokens). Direct-answer baseline collapses to 28.29% — reasoning is load-bearing.
- GSM8K-Zero: 98.72% @ 22.67 tok vs 99.50% @ 252.96 (11x cut, −0.78pt).
- MathBench-College worst case: −8pt accuracy for 2.6x cut (GPT-4o-mini). o3-mini
  compresses only ~42% vs ~62% for GPT-4o-mini on the same dataset (MathBench-College,
  Table 4: o3-mini 41.8%, 1163.55→677.65; GPT-4o-mini 61.6%, 675.78→259.85);
  GPT-4o-mini reaches ~76% on easier sets (GSM8K, Table 3, 318.10→77.26) —
  reasoning-class models resist prompt-level budget compression. *(Corrected
  2026-08-27: page previously paired o3-mini's MathBench figure against
  GPT-4o-mini's GSM8K figure ("~42% vs ~76%") — cross-dataset mispairing;
  direction survives, the 34pt gap does not.)*
- TALE-PT Llama-3.1-8B: GSM8K-Zero SFT +13.4pt AND 3.2x cut — CoT overthinks trivia.
- Estimator-call overhead is why expense (−59%) lags tokens (−67%); on short tasks the
  estimator call dominates (GSM8K-Zero: 22.67 output tok but 276.12 expense units).

## Limitations

- Math-QA benchmarks only; no agentic/tool-use evidence — transfer to a trading-analysis
  agent is an assumption, not a result.
- <3% accuracy figure is an average hiding an 8pt hard-dataset tail.
- Budget adherence is soft (prompt-level, no decoding enforcement); mis-set budgets
  actively backfire (elasticity).
- Single global compression setting is its own overfit risk (per-dataset variance).
- TALE-PT requires white-box fine-tuning.

## APPLICABILITY

- **TALE-PT: NOT APPLICABLE** — fine-tuning; we do not run inference infrastructure.
- **TALE-EP: applicable as a delegation pattern.** USAGE.md rules j/k (model/effort per
  agent) are a hand-set coarse TALE; the paper says a cheap zero-shot call estimates
  per-task budget better than a fixed setting. The rule-i prior-art Haiku pass can double
  as the effort/model estimator at ~zero marginal cost → plan item 3.
- **Elasticity = the warning against over-tightening effort='low'** on verify/judge
  stages: below feasible range costs MORE (retries, rework — the 5-of-9-wrong-numbers
  incident shape). Matches USAGE.md rule 5's measured rework rationale.
- Direct-answer collapse (28% vs 84%) is the quantitative case for the existing split:
  mechanical extraction → haiku/low, synthesis/adversarial-verify → session model. Keep.
- o3-mini result: budget-prompting a Fable-class model buys less than downshifting the
  stage to Haiku — tier the model first, budget-prompt second.
- Output-side compression cannot recover input-side fixed tolls (skill catalog,
  always-loaded files) — rtk and catalog trimming attack the side TALE ignores.
- Budget search harness (sweep budget, accept correct-and-cheaper) = the backpack's
  replay-across-a-swept-parameter rule; usable to calibrate per-stage effort empirically.
- No repo code implied; nothing touches hard invariants / era-4 / overfit gates. Any
  adopted triage rule is validated by measured $/workflow, not paper averages.
