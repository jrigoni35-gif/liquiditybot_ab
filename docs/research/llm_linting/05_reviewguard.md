# 05 — ReviewGuard: deficient peer-review detection

**Citation**: Zhang, Li, Shrestha, Mamidala, Putta, Aggarwal, Xiao,
Ding, Chen — "ReviewGuard: Enhancing Deficient Peer Review Detection
via LLM-Driven Data Augmentation", arXiv:2510.16549 (v1 2025-10-18, v2
2025-11-20), ACM/IEEE JCDL 2025. Code:
github.com/haoxuan-unt2024/ReviewGuard. FOUND.

## Claims

- Deficient reviews (6 types: unconstructive, superficial,
  harsh/malicious, cursory, uninformed, other/bias) detectable at scale
  via scrape → GPT-4.1 annotation + human validation → synthetic
  augmentation → fine-tuned classifiers.
- Deficient-review signature: LOWER rating, slightly HIGHER
  self-reported confidence, lower structural complexity (fewer
  sentences/tokens, lower readability), MORE NEGATIVE sentiment.
- Synthetic augmentation lifts minority-class recall/F1 (Qwen 3-8B
  recall 0.5499→0.6653, F1 0.5606→0.7073).
- AI-generated review text rising since ChatGPT, present in BOTH
  sufficient and deficient reviews — AI use ≠ deficiency.

## Numbers

- Corpus: 24,657 real reviews (86.89% sufficient / 13.11% deficient)
  from 6,634 conflicting-review papers; 46,438 synthetic.
- Annotation agreement: round 1 Cohen kappa 0.4899; round 2 (refined
  rubric, n=100) 0.8774.
- Binary (train real+synthetic / **test REAL**): Qwen 3-8B P 0.8110 /
  R 0.6653 / F1 0.7073 — the clean headline.
- Multi-label F1 0.8738 — tested on real+synthetic, partially graded
  on its own augmentation distribution — quarantine it.
- Features: rating rho=0.256 (5.37 vs 3.74); confidence rho=-0.046
  (3.68 vs 3.75, tiny but higher in deficient); sentences 24.61 vs
  19.43; tokens 425.47 vs 318.44; negative sentiment 4-5x more
  frequent in deficient (both venues p<0.001).

## Limitations

- Authors: synthetic generated from abstracts not full texts; ML/AI
  conferences only; generation prompts admittedly rough.
- Extraction reading: annotation circularity — GPT-4.1 defines ground
  truth for a detector partly aimed at LLM-offloaded reviews; a GPT
  blind spot propagates into labels, training, and eval unflagged
  (instrument-is-first-suspect shape).
- Round-1 kappa ~0.48 shows "deficient" is fuzzy until rubric-tightened;
  0.88 is agreement WITH the rubric on n=100, not objectivity.
- No temporal/venue-held-out split; base rate 13.11% means P 0.81 still
  yields nontrivial FP volume at scale; no calibration analysis.
- Zero adversarial robustness: an evaluator instructed to pad structure
  defeats every feature found.

## GAP ANALYSIS

### ALREADY AHEAD

- **Read-the-corpus split on headlines**: the paper's own numbers
  divide into a clean one (binary, real test) and a leakage-adjacent
  one (multi-label, synthetic-contaminated test) — the discipline
  CLAUDE.md's DoD green-line law and OF-6 purge hygiene already
  enforce. Cite the 0.7073, quarantine the 0.8738.
- **Referee suspicion architecture**: the lattice
  (docs/quant/2026-08-19_referee_lattice.md; HANDOFF.md:219) keeps
  evaluators blind, cross-checked by differential matrix, and cut off
  from the learner — ReviewGuard has no equivalent of any of the three
  and its annotator circularity shows why they exist.
- **Anomaly-telemetry-not-authentication framing**: CLAUDE.md already
  notes manip_suspect needs smoothing and one read ≠ trend; ReviewGuard
  signals rate the same — telemetry, never a gate.

### ADOPTABLE (SAFE class)

1. **Deficient-verdict screen for lattice/panel transcripts** — landing
   spot: a zero-model textstat-style lint over referee/grader outputs
   before a grade enters the vault: sentence count, token count,
   specificity markers, confidence-vs-substance mismatch. Their best
   detector is an 8B fine-tune but the feature-level screen captures
   most of the signal at zero model calls — matches USAGE.md tiering
   and our corpus reality (referee transcripts far below any fine-tune
   floor). Constraints from the paper's own weaknesses: adopt the
   STRUCTURAL/confidence features, NOT the sentiment direction — their
   deficient reviews skew negative, our measured failure mode per the
   graded-review commits (cb0a2461, 5d5c4e40) is sycophantic-positive
   rubber-stamping; validate direction on our own graded-review corpus
   before wiring any threshold (no fitted literals, config-lifted with
   config_guard checks). Effective-n: their reviews cluster per paper,
   ours cluster per session — report it.

### NOT APPLICABLE

- Fine-tuning a classifier on our transcripts: corpus orders of
  magnitude below any fine-tune floor, and model-side investment is
  FROZEN (2026-08-10 adjudication) — the freeze covers the trading
  learner, but the corpus argument alone kills this.
- Their sentiment-direction feature: measured on academic peer review;
  direction likely inverted for our failure mode (see above).
