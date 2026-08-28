# 03 — LLMs for Integrated Business Intelligence (BDCC 2026)

**Citation:** Theodorakopoulos, L., Karras, A., Theodoropoulou, A.,
Klavdianos, C. (2026). "LLMs for Integrated Business Intelligence: A
Big Data-Driven Framework Integrating Marketing Optimization, Financial
Performance, and Audit Quality." Big Data and Cognitive Computing
(MDPI), 10(4), 110. DOI: 10.3390/bdcc10040110. Submitted 2026-01-16,
accepted 2026-03-23, published 2026-04-05.

**Status: FOUND — ABSTRACT ONLY.** MDPI full text returned HTTP 403 on
every route tried (html, /pdf, DOI redirect, ouci mirror,
ResearchGate); abstract + metadata via Semantic Scholar API (CorpusId
287237300). Methods/validation sections UNREAD — every number below is
an abstract-level claim, tagged unvalidated.

## Core claims (abstract-level)

- Unifying marketing/finance/audit decisioning in one Big Data
  framework yields large joint gains in budget allocation and risk
  assessment.
- Five-module architecture: (1) LLM segmentation + CLV prediction,
  (2) attention-weighted marketing mix modeling, (3) multi-agent LLM
  hierarchical budget optimization with game-theoretic reasoning,
  (4) attention-informed Markov multi-touch attribution, (5) LLM-
  augmented audit quality scoring.
- Claimed validation on one e-commerce dataset improves five
  heterogeneous metrics simultaneously — a breadth-of-wins pattern
  that, absent visible holdout discipline, is itself a red flag under
  this repo's standard.

## Key numbers (all [K abstract, unvalidated])

- Dataset: 2.8M customers, USD 156M marketing spend, single dataset,
  provenance unstated.
- Marketing ROI 4.2 → 6.78 (+61.4%); forecasting MAPE 12.8% → 4.7%
  (−63.3%); fraud detection accuracy +29.8% relative (base rate
  unstated — "accuracy" on imbalanced fraud data is vacuous); Audit
  Quality Index 0.951 (self-defined composite, no external anchor);
  CLV accuracy 76.4% → 91.3% (metric for a continuous target
  unstated).
- Review timeline: 6-day revision-to-accept, ~10 weeks total.

## Limitations

- Limitations section itself unread (403-blocked).
- No visible out-of-sample discipline in the abstract: no holdout, no
  temporal split, no purging, no multiple-comparison correction across
  five simultaneously-improved metrics. Against OF-1..OF-7, every
  headline number is a hypothesis.
- Single, apparently proprietary dataset; no replication path.
- Opaque baselines — "ROI 4.2 → 6.78" vs an unspecified incumbent
  invites weak-baseline inflation.
- LLM-scored AQI: the instrument grading the system is part of the
  system — exactly the instrument-first suspicion CLAUDE.md's MINDSET
  codifies.
- 6-day revision-to-accept (confirmed real: revised 2026-03-17,
  accepted 2026-03-23): low prior on deep vetting. *(Softened
  2026-08-27: page previously characterized the venue as a
  "High-throughput framework-paper lab (Univ. of Patras)" — an uncited
  characterization exceeding what the page verifies; only the timeline
  observables are kept.)*
- Domain gap: e-commerce spend allocation, not adversarial markets or
  microstructure.

## GAP ANALYSIS

### ALREADY AHEAD

- **Audit**: hash-chained JSONL audit trail with registered reason
  codes (CLAUDE.md invariant 6) is deterministic verifiability; the
  paper's LLM-scored AQI 0.951 is strictly weaker — model-graded
  quality, self-defined composite. Deliberate rejection.
- **Multi-agent budget optimization**: the paper's module 3 has no
  cost accounting for its own agent layer; USAGE.md rules h–m are a
  measured tiering discipline (born of the 61-agent / ~5.6M-token
  monoculture incident) with explicit spend rules where the paper has
  game-theoretic hand-waving. Nothing to adopt.
- **Evaluation standard**: five simultaneous wins with no visible
  leakage controls is precisely what OF-2 shuffle-null and OF-3 PBO
  exist to catch; effective-n reporting (`gate_truth_report.py`,
  `cohort_eval.py`) exceeds the paper's row-count metrics. The repo's
  fresh REG-6 era-confound episode (HANDOFF 2026-08-27:
  CONFOUNDED_BASELINE rendering in `gate_efficacy_report.py`) shows the
  house standard actively refusing exactly this class of comparison.

### ADOPTABLE

- **Calibration specimen only**: cite as the anti-pattern example when
  grading incoming literature — any adopted external claim must first
  clear the repo's own battery before informing a tunable. Placement:
  this page + optional vault concepts reference. No code, no gate.
- Nothing else. If attention-weighted attribution were ever trialed as
  a fill-attribution lens, placement would be SAFE measurement plane
  (beside `scripts/cohort_eval.py` class tooling), inheriting the
  effective-n standard — but no such trial is proposed; file-and-hold.

### NOT APPLICABLE

- CLV/segmentation/marketing-mix modules — no customers, no channels;
  domain has no mapping to liquidity provision.
- The CLV "add LLM features" claim — even a validated version is
  non-actionable under the model freeze until the era-4 readout.
- Every headline number — unread methods, unvalidated; cite none.

**Net verdict: FOUND but LOW-VALUE** — a framing/anti-pattern citation,
not a source of mechanisms; no validation gate scheduled because
nothing is proposed for adoption.
