# 02 — Automated Test Suite Enhancement with Few-shot Prompting

**Citation.** Alex Chudic (freetobook), Gül Çalıklı (Univ. of Glasgow),
"Automated Test Suite Enhancement Using Large Language Models with
Few-shot Prompting", ICPC 2026, DOI 10.1145/3794763.3794828;
arXiv:2602.12256 (2026-02-12). Read from arXiv HTML v1.

## Claims

- Few-shot example SOURCE matters: human-written examples → best
  standalone coverage; SBST (Pynguin) examples → most coverage-IMPROVING
  tests when enhancing an existing suite.
- Raw GPT-4o output largely non-executing (0.56–6.07% pass on HumanEval)
  but failures are mechanical; 9 rule-based repairs lift pass to 76–84% —
  value is generation + cheap deterministic repair.
- TF-IDF retrieval selection (problem+code) beats random on correctness
  and coverage; best-coverage cell UNSETTLED as of 2026-08-27: page
  previously quoted 96.3% branch / 99.3% line (HumanEval, human
  examples), a second full-text read gives 96.9%/99.6% for human
  examples under source-code-similarity selection — likely different
  table rows, both reads single-route summarizer extractions. Re-derive
  the cell from the PDF table before quoting it anywhere downstream
  (07 does not lean on it; keep it that way).
- LLM tests are for SUITE ENHANCEMENT, not replacement: only 1.3–23.3%
  of generated tests improve coverage after filtering.
- Quality cost small: cognitive complexity barely moves; Pynguin-example
  tests add the most cyclomatic bloat (+102/+185).

## Numbers

- Pass before/after repair, HumanEval: human 0.57%→81.18%, Pynguin
  6.07%→76.11%, ChatGPT 0.56%→76.49%. ClassEval after: 84.34/82.19/84.33%.
- Enhancement, HumanEval: coverage-improving 1.33/1.73/10.33% of
  generated (human/ChatGPT/Pynguin); branch delta +2.7/+5.6/+26.9%.
  ClassEval: 2.46/4.88/23.33%; branch +0.7/+6.2/+23.9%.
- Corpus: HumanEval + ClassEval only, GPT-4o only, ~900–1,600 generated
  tests per config. No mutation testing.

## Limitations

- Authors: coverage is the only effectiveness proxy — no mutation, no
  fault detection ("test quality" = exercises, never pins). Toy-to-small
  benchmarks, no real repos. Shot count fixed at 5; zero-shot example
  corpus was itself GPT-4o-generated.
- Extractor: headline deltas measured against benchmark reference suites,
  not mature suites near saturation — expected yield on a 3,880-function
  suite is at the LOW end of 1.3–23.3%. No oracle-correctness analysis:
  a generated test can pass by asserting current (wrong) behavior — in a
  live repo that freezes bugs in place. The optimization filter keeps
  tests solely for marginal coverage, biasing toward exercisers over
  pinners. No flakiness/order/fixture-isolation evaluation — tests ran in
  isolation per problem; nothing transfers about suite hygiene.

## GAP ANALYSIS

**ALREADY AHEAD.**
- Acceptance bar: the paper's coverage filter is strictly weaker than the
  house standard (session finding (e): mutation-kill;
  `scripts/instrument_contract.py:148` "theatre — caught by mutation").
  Its own authors concede mutation testing is future work.
- Oracle risk: for SAFE-class measurement code, a test generated against
  current code enshrines instrument bugs — CLAUDE.md "the instrument is
  the first suspect" already demands the second route the paper lacks.

**ADOPTABLE (SAFE-class).**
- Enhancement pipeline shape, if ever wanted for defect (d)-class gaps:
  run coverage, feed uncovered-branch context + retrieved similar
  existing tests (its best selector = problem+code TF-IDF over this
  repo's own 364 test files) as few-shot examples, keep only
  coverage-improving output. Expect to keep ~2–10%, low end here.
  Landing spot: offline `scripts/` tool emitting candidate tests for
  human review. Gate: full DoD matrix, era-4 SAFE only, and each adopted
  test demonstrated to kill a planted defect before merge — the paper's
  filter alone is insufficient evidence; **no generated test is accepted
  on green alone.**
- Cheap transfer: the 9-repair-rule finding (76–84% of raw failures are
  mechanical) → deterministic triage layer (import fixes + this repo's
  existing ruff/pyright/test_import_integrity gates) before any human
  reads a generated test.
- Deliberate rejection: do NOT build an SBST/Pynguin corpus for the
  bigger coverage deltas — cyclomatic bloat, highest error rates, and
  this repo has no such corpus.

**NOT APPLICABLE.**
- Fine-tuning angles: none in the paper (prompting only), and the repo
  fine-tunes no LLMs regardless (2026-08-10 freeze).
- Session defects (a)–(c): the paper is silent on host-state dependence,
  leak-class stamps, and order-dependence — no hook.
