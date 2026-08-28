# 01 — LintLLM: Verilog linting via LLMs

**Citation**: Zhigang Fang, Renzhi Chen, Zhijie Yang, Yang Guo, Huadong
Dai, Lei Wang. "LintLLM: An Open-Source Verilog Linting Framework Based
on Large Language Models." arXiv:2502.10815 (2025-02-15); GLSVLSI 2025,
DOI 10.1145/3716368.3735198. Code:
github.com/fangzhigang32/Static-Verilog-Analysis. FOUND.

## Claims

- Hierarchical "Prompt of Logic-Tree" (role/task root, strictly ordered
  algorithm-step children) lets LLMs lint Verilog RTL more accurately
  than commercial EDA linters.
- "Defect Tracker" separates root-cause from cascade noise: detect all,
  repair each candidate alone, re-detect; the repair minimizing
  remaining defects marks the root.
- Best LLM (o1-mini) beats best commercial EDA by +18.89pt correct rate
  / -15.56pt false-positive rate on their 90-design benchmark.
- LLM linting < 1/10 commercial licensing cost; breakeven only above
  ~4,800M lines/yr.
- Released benchmark: 90 verified GitHub Verilog designs, defects
  planted by 13 mutation rules across 11 categories.

## Numbers

- o1-mini 83.33% CR / 12.22% FR; DeepSeek V2.5 81.11/18.89; GPT-4o
  73.33/26.67; GPT-4 66.67/33.33; Llama-3.1 68.89/31.11.
- Commercial EDA best 64.44/27.78; Verilator 62.22/32.22.
- Headline deltas = 17/90 and 14/90 designs; percentage POINTS.
- 90 designs from 150 screened; 30/30/30 simple/medium/complex; one
  injected defect location per design; scored by line-number match.
- Cost ~$20 per 80k lines ($3/$12 per 1M in/out); $0.285/detection on a
  1,000-line CPU-control case at 87.78% CR.

## Limitations

- Logic-Tree + Defect Tracker combined RAISES FP on GPT-series models
  (authors only speculate why).
- n=90, single-line injected defects, no CIs, no resampling of
  stochastic outputs — headline is an unvalidated point estimate by
  this repo's standard.
- Ground truth is mutation-injected, not natural: the 13 rules define
  the defect distribution (structural circularity), likely favoring
  pattern-matching LLMs.
- Line-number scoring brittle both ways (adjacent-line correct = wrong;
  real latent issue in "verified" base = FP).
- Cost model asymmetric ($1.2M/yr license vs API tokens only, no triage
  time); o1-mini closed — reproducibility vendor-bound.
- Contamination unaddressed: GitHub base designs likely in pretraining;
  mutations of memorized code are easy targets.

## GAP ANALYSIS

### ALREADY AHEAD

- **Mutation-injected known-answer benchmarking**: our standing law,
  not a novelty. scripts/overfit_check.py:141-177 runs a planted-signal
  `synthetic_benchmark()` whose comment (lines 114-116) states it
  "validates the INSTRUMENT (planted signal, known answer)"; backpack
  rule 2 orders MUTATION/INJECTION first; vault_guard's 2026-08-23
  rebuild added a bypass corpus for the same reason. LintLLM's 13-rule
  battery is our doctrine applied to a linter.
- **Headline-number discipline**: their +18.89pt with no null/CI would
  fail our standard outright — OF-2 shuffle-null and effective-n
  reporting (gate_truth_report.py policy, CLAUDE.md) exist precisely to
  block citing such numbers as settled.
- **Referee-that-disagrees ≠ referee-that's-right**: their GPT-series
  regression (combined methods raising FR) is the 2026-08-21
  diode-vs-Python incident (16 vs 21, diode wrong) in miniature —
  CLAUDE.md mindset rule 5 already encodes the lesson.

### ADOPTABLE (SAFE class)

1. **Mutation-rule battery for our own referee scripts** — landing
   spot: a small planted-defect corpus per measurement script
   (session_digest, cohort_eval readers, gate_truth_report), each check
   required to fire on its plant before its green counts. Extends the
   overfit_check pattern sideways to the least-governed plane, which
   CLAUDE.md's MINDSET names as the structural exposure.
2. **Fix-one-re-detect root-cause triage** — landing spot: documented
   triage procedure (focused-fix protocol appendix) for multi-gate red
   states: when several DoD gates trip, repair one candidate, re-run
   the battery, and rank candidates by remaining reds. Procedure text
   only; no code.

### NOT APPLICABLE

- Replacing ruff/pyright/bandit with an LLM lint pass: deterministic
  linters are DoD gates; a stochastic model can never be a gate whose
  release condition it controls (four-incident coordination rule).
  Advisory side-channel at most, and nothing here earns even that yet.
