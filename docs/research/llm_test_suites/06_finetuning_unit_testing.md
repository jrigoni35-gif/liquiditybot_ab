# 06 — Fine-tuning LLMs for Unit Testing: a Large-scale Empirical Study

**Citation.** Shang, Zhang, Fang, Gu, Zhou, Chen, "A Large-scale
Empirical Study on Fine-tuning Large Language Models for Unit Testing",
ISSTA 2025 / PACMSE, DOI 10.1145/3728951; arXiv:2412.16620. Replication:
github.com/iSEngLab/LLM4UT_Empirical. (Hint said "ACM 2026"; actual is
the 2025 ISSTA cycle — same paper.) Full text via arXiv v1 HTML through a
summarizing fetch; table cells are single-route reads, low-digit
transcription error possible.

## Claims

- Fine-tuned open LLMs beat prior task-specific SOTA on test generation,
  assertion generation, and test evolution on nearly all of 8 metrics.
- Decoder-only wins overall but at equal scale encoder-decoder is better
  — capacity, not architecture, drives the lead.
- Zero-shot prompting (GPT-3.5) beats fine-tuned small models on
  generation correctness but collapses on assertion exact-match (2.97%
  vs 71.42%) — project-specific FORM needs fine-tuning, general
  competence favors big prompted models.
- Text similarity (BLEU/CodeBLEU) is unreliable for judging tests;
  compile+run evaluation mandated.
- **Generated tests exercise but barely pin: best model found 8 of 163
  Defects4J bugs.**

## Numbers

- 37 LLMs, 3 tasks, 5 benchmarks, 8 metrics, >3,000 A100 GPU-hours.
- Test generation, Defects4J, best (DeepSeek-Coder-6b): 33.68% correct,
  21.36% build error, 33.62% syntax error. Repair-loop baselines above it
  (ChatUniTest 40.14%, CasModaTest_GPT3.5 77.16%).
- Assertion generation best (CodeLlama-7b): EM 71.42% vs ATLAS 31.42%.
  Test evolution best: EM 35.58% vs Ceprot 12.3%.
- Zero-shot GPT-3.5: generation 49.16% correct (> fine-tuned 33.68%);
  assertion EM 2.97%.
- Bug detection: 8/163 Defects4J bugs (headline). The paper's stated
  0.74% is a PRECISION metric over generated tests — a differently
  composed denominator — not the bug-exposure rate (8/163 is 4.9%).
  *(Relabeled 2026-08-27: page previously wrote "8/163 Defects4J bugs
  (~0.74% as reported)", presenting the precision figure as if it were
  the ratio.)*

## Limitations

- Authors: 3 tasks only; Defects4J pretraining-leakage risk mitigated
  only by one unauditable proprietary dataset; zero-shot-only prompting
  understates prompt-engineering ceilings; fine-tuning insufficient for
  SOTA without post-processing.
- Extractor: "correct" = compiles + passes on the fixed version — says
  nothing about assertion strength; no mutation score anywhere except the
  weak 8/163 probe, so 33.68% conflates exercise with pin. EM/BLEU on
  assertions rewards verbatim reproduction — penalizes stronger valid
  oracles, cannot detect vacuous ones. All Java/JUnit; transfer to
  Python/pytest numeric-tolerance quant code asserted nowhere.

## GAP ANALYSIS

**ALREADY AHEAD.**
- 8-of-163 is the literature's own proof of the house doctrine (session
  finding (e)): a green suite proves little about fault detection;
  mutation-kill, not execution, is the bar. This paper is the citation
  for why that bar exists.
- EM-based assertion scoring would have graded the comment-satisfied
  constant-time pin (CLAUDE.md MINDSET) as a perfect assertion — direct
  confirmation that text-match oracles are the wrong instrument. Keep
  behavioral/injection pins; reject similarity-scored test review.
- Its Defects4J-leakage caveat is structurally what OF-6 purge and the
  era-4 registration guard against; their proprietary cross-check is a
  weaker, unauditable purged walk-forward.

**ADOPTABLE (SAFE-class).**
- The runtime-metric ladder (syntax → build → fail → pass → correct) as
  the grading rubric for any generated-test PR: "correct" here = passes
  in a FRESH checkout under `.\test_windows.bat` — which is exactly the
  environment session defects (a)/(b) prove is the honest one
  (host-state-dependent greens; `_VAULT_GUARD_STAMP` erroring only on
  fresh checkouts; conftest.py:95-99 "the throwaway worktree is the
  honest environment"). Landing spot: a fresh-worktree DoD/CI leg — see
  07, rank 1. Any generated test additionally needs mutation-kill
  evidence (break the fix, watch the pin go red) — never green alone.
- Scoped realism: 21–34% build-error rates for the best 6–7B models argue
  against wholesale generation; the viable slice is boilerplate expansion
  around existing fixtures in tests/ with strong local form — never new
  oracle invention, and never for closing core//risk/ coverage gaps
  (the paper measures nothing about WHICH code gets tested).

**NOT APPLICABLE.**
- Fine-tuning-for-us: this repo fine-tunes no LLMs and model-side
  investment is frozen (2026-08-10). One line, closed.
- Session defect (c) (order-dependence): unmeasured by the paper.
