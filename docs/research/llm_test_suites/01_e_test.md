# 01 — E-Test: Ever-Improving Test Suites

**Citation.** Ketai Qiu, "Ever-Improving Test Suite by Leveraging Large
Language Models", FSE Companion '25, Trondheim, June 2025,
arXiv:2506.11000 / DOI 10.1145/3696630.3728614. Extended: Qiu, Di Grazia,
Mariani, Pezzè, "E-Test: E'er-Improving Test Suites", arXiv:2510.19860
(submitted ICSE 2026). Extraction basis: arXiv HTML of both versions via
summarizing fetch; ACM PDF not parsed; numbers cross-checked across
versions where both report them — most agree to rounding, but NOT the
vanilla-baseline figure (see Claims; provenance note corrected
2026-08-27: the versions do not "agree to rounding" on that number).

## Claims

- Production executions contain behaviors the suite never exercises; an
  LLM triages each observed scenario into already-tested / need-test /
  error-prone, then generates JUnit tests only for the untested classes —
  the suite improves from field data, not static coverage.
- Vanilla LLMs are COMPARABLE TO OR WORSE THAN random at this triage
  (the paper's own framing; amended 2026-08-27 — page previously claimed
  "WORSE than random (best vanilla F1 0.32 vs 0.33 random)": the 0.32
  reproduces in neither version. Extended body: GPT-3.5 Turbo 0.30 vs
  random 0.33; the extended ABSTRACT states vanilla max F1 0.39, ABOVE
  the random baseline — the figure is version-dependent); the machinery
  (fine-tune + 5-query ensemble + majority-vote) is what works, not the
  raw model.
- 5 heterogeneous queries + voting truth table beat any single query or
  3-query subset.
- LLM triage is 6–20x faster than computing branch coverage per scenario.
- The "+24%" headline is +24 percentage points over field-ready testing
  (54–55% vs 30%), not relative.

## Numbers

- Macro F1 0.55 on 1,975 scenarios (1,825 Defects4J, 150 recent GitHub),
  3-class; baselines FAST++ 0.34, field-ready 0.30, best vanilla 0.30
  extended-body (GPT-3.5 Turbo) / 0.39 extended-abstract max (page
  previously claimed 0.32 — reproduced by neither route; amended
  2026-08-27).
- Per-class: already-tested F1 .78; need-test P .49 / R .26 / F1 .34;
  error-prone P .49 / F1 .53.
- Query ablation: 5 queries 0.55; 3-query subsets 0.31–0.47; single 0.38.
  Few-shot no help (GPT-4 Turbo 3-shot 0.26). RAG: total F1 down
  (0.50 vs 0.55) but not-yet-tested up (0.53 vs 0.43).
- Generation on 673 Defects4J bugs with reachable trigger tests: 99.1%
  syntactically correct → 86% compile → 83.5% of bugs get a
  failure-revealing generated test (extended-version figures; page
  previously read "87% compile → 97% failure-revealing → 83.2%" —
  amended 2026-08-27 against arxiv.org/html/2510.19860).
- Efficiency: LLM 0.81–24.97 s vs branch coverage 5.12–168.14 s.
- Oddities: best temp 2.0; smaller model beats 70B (extended version
  cites DeepSeek R1 14B exceeding 70B; page previously said "8B beats
  70B" — amended 2026-08-27; inverse-scaling direction survives).

## Limitations

- Authors: Defects4J almost certainly in LLM training data; the
  leak-resistant slice (150 fresh scenarios) is 7.6% of corpus. Treat
  0.55 as in-distribution. Unit-level only; heterogeneous hardware taints
  the efficiency RQ.
- Extractor: need-test recall 0.26 — the class the pitch is about is the
  one it finds worst; ~0.49 precision on both actionable classes = half
  of flags mislabeled. "Error-prone" ground truth is known, reproduced
  Defects4J triggers, so 83.2% is test RE-generation, not bug discovery.
  No mutation-score evaluation of generated-test assertion strength.
  Temp-2.0 optimum and 8B>70B suggest shallow lexical cueing. Java/JUnit
  only; fine-tuned GPT-3.5 Turbo now deprecated.

## GAP ANALYSIS

**ALREADY AHEAD.**
- Leakage discipline: the paper's 7.6%-fresh mitigation would fail the
  OF-6 purge standard; read its 0.55 the way CLAUDE.md reads a
  synthetic-corpus overfit green — validates machinery, not claim.
- Instrument suspicion: vanilla-LLM comparable-to-or-worse-than-random
  (per the paper's own framing; exact figure version-dependent, see
  Claims — amended 2026-08-27) is
  direct literature confirmation of BACKPACK rule 2 — an LLM triage tool
  is an instrument whose output counts only after injection-verified
  failure.
- Assertion strength: house mutation-kill standard (session finding (e))
  is strictly stronger than anything the paper measures.

**ADOPTABLE (SAFE-class).**
- The framing, minus the LLM: diff observed disposition paths in the
  hash-chained audit/events record (core/runtime.py shared-state layer)
  against what tests/ asserts, to list dispositions no test pins. The
  reason-code registry in `core/codes.py` is a finite enumerable domain,
  so exhaustive enumeration beats a 0.49-precision classifier — this is
  the direct answer to session defect (d) (zero-coverage
  per-disposition-confound and render() paths shipped green). Landing
  spot: a `scripts/`-side SAFE measurement/report tool, never the
  decision path. Gate: full DoD matrix + planted-defect demonstration
  (remove one pin, show the report flags it) before its green counts.
  Any generated tests: mutation-kill evidence required, never green
  alone.

**NOT APPLICABLE.**
- Fine-tuning an LLM for triage: model freeze 2026-08-10, and this repo
  fine-tunes no LLMs. One line, closed.
- The paper is silent on fixture isolation, order-dependence, and
  readability of generated tests — no hook for session defects (a)–(c).
