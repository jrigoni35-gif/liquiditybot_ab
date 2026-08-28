# 03 — Using LLMs to Enhance Code Quality: an SLR

**Citation.** Alomari, Redah, Ashraf, Alshayeb (KFUPM), "Using LLMs to
enhance code quality: A systematic literature review", Information and
Software Technology, Vol. 190, art. 107960 (issue Feb 2026, online
2025-11-20), DOI 10.1016/j.infsof.2025.107960. NOTE: venue is IST, not
JSS as the hint said. **Full text PAYWALLED** — extraction from abstract
+ indexed highlights + OpenAlex/Semantic Scholar metadata only.

## Claims

- 49 primary studies through Sept 2024; refactoring most-studied task,
  smell detection second.
- Prompting > fine-tuning in frequency; few-shot the leading prompting
  method; open-source/general-purpose models preferred; static validation
  datasets the primary validation approach.
- Java and Python most represented; F1/P/R/Accuracy dominate detection,
  BLEU/Exact-Match dominate refactoring evaluation.
- Headline negative: "refactored code by LLMs is not reliable" — behavior
  preservation not assured.

## Numbers

- n=49 studies, cutoff Sept 2024; QA threshold 50%, 2 assessors [K].
- cited_by_count = 2, OpenAlex read 2026-08-27 [K, snapshot-stamped].
- Rank orders only — no percentages recoverable behind the paywall; no
  per-study effectiveness numbers reported here rather than estimated
  [UNKNOWN].

## Limitations

- Access: everything above from abstract/highlights/metadata; per-RQ
  breakdowns and the 49-study list unverified. Ranks solid, magnitudes
  unavailable.
- Corpus predates the 2025 model generation entirely.
- Extractor: the field's metrics (BLEU/EM/F1) are similarity/label
  metrics, not behavior-preservation proofs — by this repo's standard the
  corpus has not established reliability either way, which explains the
  "not reliable" verdict. Its smell taxonomy is design-level (god class,
  long method) and does not cover this repo's dominant defect class:
  confidently-wrong measurement instruments.

## GAP ANALYSIS

**ALREADY AHEAD.**
- Validation regime: BLEU/EM validation of refactorings is the
  literature-scale version of tests-that-exercise. The house standard is
  C2 SELF-TEST POWER (`scripts/instrument_contract.py:33-43`): an
  instrument must FIRE on a planted defect; a null arm "never shows it
  can detect anything". The comment-satisfied constant-time pin
  (CLAUDE.md MINDSET) is the concrete counterexample to
  similarity-metric validation. Session finding (e) is this, codified.
- Refactoring reliability: C1 ROOTEDNESS (`instrument_contract.py:25-31`)
  already enforces that the automated admission path runs EVERY DoD gate
  — the mechanism the SLR's verdict says the field lacks.
- Side-effect hygiene: `tests/test_qa_isolation.py:217-225` pins
  configure_audit/configure_registry (SD-007 class) — an axis the
  surveyed corpus never evaluates; directly the mechanism family for
  session defects (a)/(b).

**ADOPTABLE (SAFE-class).**
- One targeted idea: a cheap triage pass over `scripts/` (the
  least-governed measurement plane, where the 2026-08-23 session found 7
  instrument defects and zero in the governed path) for the C2-shaped
  smell — self-tests without negative arms. Extends an already-earned
  mechanical contract; findings are SAFE-class. If it emits tests,
  house rule applies: **mutation-kill evidence, never green alone.**
- Cheap pre-adoption experiment the SLR's corpus lacks: generate tests
  for one measurement script, mutation-score them against hand-written
  equivalents (break the instrument, count which suite goes red) before
  any wider adoption.

**NOT APPLICABLE.**
- Fine-tuning-for-us: the repo fine-tunes no LLMs and model-side
  investment is frozen (2026-08-10). One line, closed.
- LLM refactoring of decision-path code: COHORT-RESETTING under the
  era-4 moratorium even if behavior-preserving in intent — forbidden
  until readout regardless of what the literature says.
