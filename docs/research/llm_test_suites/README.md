# LLM & test-suite literature pass — 2026-08-27

Purpose: six-paper readout on LLM-assisted test generation/triage/quality,
graded against this repo's house standards (CLAUDE.md DoD matrix; "a green
is only as big as its corpus"; mutation-kill as the bar for a good test).
One page per paper with GAP ANALYSIS (ALREADY AHEAD / ADOPTABLE / NOT
APPLICABLE); ranked adoption shortlist in `07_adoption_ranking.md`.
Extraction provenance and access caveats live on each page — two papers
were read through paywalls/403s and say so.

Standing rule for everything here: any test-generation adoption carries the
house rule — **generated tests are accepted only with mutation-kill
evidence, never on green alone.** Fine-tuning-of-LLMs angles are NOT
APPLICABLE across the board: the 2026-08-10 adjudication froze model-side
investment, and this repo fine-tunes no LLMs.

## Status table

| # | Paper | Found | Citation | One-line verdict |
|---|-------|-------|----------|------------------|
| 01 | E-Test (Qiu et al.) | FOUND | FSE Companion '25, arXiv:2506.11000 / 2510.19860 | Production-trace coverage triage works, but its own numbers (need-test recall 0.26, vanilla LLM comparable-to-or-worse-than random — version-dependent, see 01, amended 2026-08-27) argue for the repo's exhaustive-enumeration route over its classifier. |
| 02 | Chudic & Çalıklı | FOUND | ICPC 2026, DOI 10.1145/3794763.3794828, arXiv:2602.12256 | Suite enhancement = generate + cheap deterministic repair + coverage filter; measures only exercise, never kill — insufficient alone for this house. |
| 03 | Alomari et al. SLR | FOUND (paywalled; abstract+metadata) | IST Vol. 190 art. 107960, DOI 10.1016/j.infsof.2025.107960 | Field-scale confirmation that similarity-metric validation dominates and "LLM-refactored code is not reliable"; repo's C2 negative-arm standard is stronger. |
| 04 | Kyeremanteng et al. | FOUND (403; abstract+snippets) | Preprints.org, DOI 10.20944/preprints202607.0296.v1 | PRISMA map, not measurement; its contamination/agentic-risk vocabulary names what OF-2/OF-6 and the hard invariants already enforce mechanically. |
| 05 | Pratap et al. | FOUND (403; abstract+metadata) | NLP Journal Vol. 11 art. 100144, DOI 10.1016/j.nlp.2025.100144 | PEFT/quantization taxonomy survey; citable backing for the OF-7 DoF discipline, nothing to adopt. |
| 06 | Shang et al. | FOUND | ISSTA 2025 / PACMSE, DOI 10.1145/3728951, arXiv:2412.16620 | 37-model fine-tuning benchmark whose sharpest result is negative: best model exposes 8 of 163 bugs — pass rate is not fault-detection power. |

## Session defects (a–e) mapped onto the literature's taxonomies

Session findings, `.superpowers/sdd/progress.md` (2026-08-27):

**(a) Host-state-dependent greens** — veto-dashboard tests pass only where
a live bot's history exists on disk; fresh checkouts red on main tip.
Literature name: none. All six papers are silent on environment-dependence
of test verdicts; Chudic (02) concedes outright that nothing in it
transfers about suite-level hygiene, and E-Test (01) grades generated
tests only on compile/fail/coverage. The nearest relative is Shang's (06)
runtime-metric ladder (syntax→build→fail→pass→correct), which at least
insists verdicts come from execution in a defined environment — the
fresh-worktree CI leg (07, rank 1) is that ladder run where
`tests/conftest.py:95-99` says the honest environment is: a throwaway
worktree, because a populated `outputs/` tree blinds both the battery and
the snapshot sweep.

**(b) Unregistered supervisor stamp (`_VAULT_GUARD_STAMP`)** — real test
errors on fresh checkouts; 10th instance of the leak-class the
`_REDIRECTED_PATH_ATTRS` registry (conftest.py:93-104) exists to catch.
Literature name: none — this is the fixture-isolation/side-effect-hygiene
axis every extraction flags as unmeasured (01, 02, 03 all note generated
tests are never evaluated for side-effect hygiene). The repo's own
mechanism history is the instructive part: the value-matched LOG_PATH scan
(conftest.py:116-145) was built precisely because a name list "silently
missed one of them" — yet stamps are still a name list, and instance #10
is the bill. Same fix as (a): the environment that fires the leak is the
fresh worktree.

**(c) Order-dependent flake** — audit-chain state bleed across the full
run. Literature name: flakiness/order-dependence; explicitly absent from
all six evaluations (02 states tests were run in isolation per benchmark
problem). The literature offers no mechanism; the order-shuffle CI leg
(07, rank 3) is house-derived.

**(d) Two zero-coverage paths shipped green** — per-disposition confound
computation and `render()`; caught only by adversarial review. Literature
name: this is the one axis the literature is actually about —
coverage-gap discovery. E-Test's (01) framing fits exactly (observed
behavior the suite never exercises), and Chudic's (02) enhancement filter
is the generation-side counterpart. E-Test's numbers also say how to do it
here: its classifier's precision on the actionable classes is ~0.49, while
this repo's disposition space (`core/codes.py` reason codes) is finite —
exhaustive enumeration beats a coin-flip classifier (01's hooks; 07,
rank 2).

**(e) House standard = mutation-kill** (inverting the guarded operator
flips pins red), not mere execution. Literature name: the gap all six
share. 01: no mutation score, 83.2% is re-generation of known triggers.
02: coverage-only, mutation named as future work. 03: field validates
refactorings by BLEU/EM. 06: the direct measurement — best fine-tuned
model, 8/163 Defects4J bugs exposed. The literature's tests-that-exercise
regime is the thing the house standard was built against; nothing here
weakens it, and 06 is the citation for why it exists.
