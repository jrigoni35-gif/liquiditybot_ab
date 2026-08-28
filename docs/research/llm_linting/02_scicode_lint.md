# 02 — scicode-lint: methodology bugs in scientific Python

**Citation**: Sergey V. Samsonau, "scicode-lint: Detecting Methodology
Bugs in Scientific Python Code with LLM-Generated Patterns",
arXiv:2603.17893 [cs.SE], v1 2026-03-18, v2 2026-06-01. PyPI tool.
FOUND.

## Claims

- Methodology bugs (leakage, wrong CV, missing seeds, numerical
  instability) are invisible to traditional linters; prior ML linters
  (dslinter, MLScent, mllint, DyLin) died of maintenance debt.
- Two-tier architecture: frontier models (Opus 4.6 / Sonnet 4.6)
  GENERATE 66 detection patterns at build time; local Qwen3-8B-FP8
  (20GB RTX 4000 Ada, vLLM) EXECUTES them at runtime. Library-version
  churn costs tokens, not engineering hours.
- Six-layer quality gate + feedback loop tripled precision (20%→62%)
  over three iterations.
- 75% of feedback-set and 71% of holdout papers-with-code had ≥1
  verified real methodology bug.
- Local-first, structured JSON for agents/CI, detection-only.

## Numbers

- 97.7% accuracy on its OWN test files (≥3 pos + ≥3 neg per pattern).
- Integration: 50 scenarios / 148 planted bugs → 85.1% recall, 58.0%
  precision, F1 69.1%.
- Kaggle (human-labeled, untuned): preprocessing leakage 65% P @ 100% R
  (F1 79%); multi-test leakage 80% P @ 18% R; **overlap leakage 0%**.
- Feedback set 62% precision (LLM-judged); by severity: critical 24%,
  high 68%, medium 72%.
- **Holdout 54% precision**; per category: sci-reproducibility 67%,
  ai-inference 62%, sci-performance 25%, **ai-training 11%**.
- Feedback loop: FP 408→111→45; valid 116→99→85; precision 20→45→62%.
- Runtime: >75% KV-cache hit from code-first prompt ordering; ~2.5 min
  per ~1,000 lines. Build cost: $100-200/mo flat Claude Code sub.

## Limitations

- Author-stated: single developer, no external validation; precision
  swings on prompt wording; non-deterministic; LLM-as-judge bias
  (only Kaggle human-labeled); single-file only; single runtime model.
- Extraction reading: the headline is the WEAK number — 54% holdout ≈
  coin-flip findings; ai-training (the category a trading repo needs)
  is the LEAST reliable at 11%.
- Feedback loop optimized against the feedback set, then holdout
  dropped 62→54% — mild selection overfitting, the exact pattern
  OF-3/PBO exists to name; no PBO-like computation on pattern
  selection.
- Critical-severity precision 24% — loudest where least trustworthy.
- No naive-frontier-prompt baseline: two-tier value on detection
  quality asserted, not measured.
- **Overlap leakage 0% recall** — temporal-overlap leakage is the
  dominant leakage class in financial time series; the class we care
  most about is the one it cannot see.

## GAP ANALYSIS

### ALREADY AHEAD

- **Dynamic beats static on its own target classes**: its defect
  classes (preprocessing leakage, bad CV) are what
  scripts/overfit_check.py verifies by ASKING THE RUNNING SYSTEM —
  OF-2 shuffled-label null (overfit_check.py:794), purged walk-forward
  with signal-time purging (overfit_check.py:248,711-715), OF-6 purge
  probe (overfit_check.py:19-20,75). Static pattern-matching measured
  54% holdout / 0% on overlap; our battery executes the pipeline.
- **Selection-overfit awareness**: their 62→54 feedback→holdout drop is
  un-named in the paper; OF-3 PBO on the DEPLOYED selection rule is our
  standing control for exactly that.
- **Severity-inverted-precision suspicion**: mindset rule 5 already
  requires more suspicion at higher asserted severity; their critical
  24% is corroborating data, not new law.

### ADOPTABLE (SAFE class)

1. **Frontier-build/local-run rule pack for our own scripts** — landing
   spot: codify USAGE.md rules j/k/l into a scripts-facing pattern:
   session model authors/updates check specs at build time; the
   operator's local-llm MCP server (mcp__local-llm__ask_local_model)
   executes mechanical screens at run time. Their measured >75%
   prefix-cache hit from code-first prompt ordering transfers directly
   to fan-out caching (USAGE.md rule l).
2. **Cheap static pre-commit tier over ml/ and scripts/** — landing
   spot: an advisory scan (never a gate) whose findings are hypotheses
   under instrument-first suspicion; validation gate before shipping:
   plant a known defect from our own history (the quarantined
   unit-mixing bug, data-quality audit) and show the scan fires, then
   report precision on OUR corpus, not the paper's.

### NOT APPLICABLE

- Adopting its detector for leakage control: 0% recall on overlap
  leakage disqualifies it for the one class that matters here; OF-6
  already covers it dynamically.
