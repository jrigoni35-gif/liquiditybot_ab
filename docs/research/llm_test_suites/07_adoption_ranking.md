# 07 — Adoption ranking

Scoring = evidence grade × repo fit × cost. Evidence grade discounts
paywalled/single-route extractions and benchmark-only corpora; fit is
measured against the five session defects (a)–(e) (session findings,
`.superpowers/sdd/progress.md`, 2026-08-27); cost in engineering days and
governance load (everything below is era-4 SAFE-class — measurement,
tests, CI — nothing alters which orders are placed or how they fill).

Standing constraint on every item: **generated tests are accepted only
with mutation-kill evidence, never on green alone** (session finding (e);
papers 01/02/06 all lack this measurement — that is the gap, not a
license).

## Rank 1 — Fresh-worktree CI leg (answers defects (a) and (b))

Source: Shang (06) runtime-metric ladder + Kyeremanteng (04)
reproducible-build norm; house evidence is stronger than either —
conftest.py:95-99 already records that the stamp leak-class "was found by
running the battery in a FRESH worktree" and that a populated `outputs/`
blinds both the battery and the snapshot sweep; defect (b) is instance
#10 of exactly that class, and defect (a) is the same shape at suite
level (veto-dashboard greens require a live bot's on-disk history).
Sketch: a DoD/CI leg that clones to a throwaway worktree with no
`outputs/`, no vault, no bot history, and runs the full pytest matrix
there; red in the worktree is the verdict, green on the operator's
populated tree is not evidence. Cost: low (script + batch wrapper);
evidence: house-measured, literature-corroborated. Highest
value-per-cost on the board — it converts defects (a)/(b) from
adversarial-review catches into a standing gate.

## Rank 2 — Reason-code coverage-gap report (answers defect (d))

Source: E-Test (01) framing, minus its LLM — its own numbers (need-test
recall 0.26, precision ~0.49, vanilla LLM < random) argue for exhaustive
enumeration over classification, and `core/codes.py` is a finite domain.
Sketch: a SAFE `scripts/` report that enumerates registered reason codes
and disposition paths recorded in the hash-chained audit/events output
(core/runtime.py layer), diffs them against what tests/ actually asserts,
and lists dispositions and report/render paths no test pins — targeted
first at the measurement plane where defect (d) shipped (per-disposition
confound computation, `render()`). Admission gate per house law: a
planted-defect demonstration — remove one pin, show the report flags the
newly-unpinned path — before its green counts (instrument_contract C2
shape). Cost: moderate; evidence: strong-by-construction (enumeration,
not inference).

## Rank 3 — Order-shuffle CI leg (answers defect (c))

Source: none — all six papers are silent on order-dependence (02 says so
outright); this is house-derived, ranked on fit alone. Sketch: a CI leg
that runs the suite under randomized test order (fixed, printed seed for
replay) so the audit-chain state bleed behind defect (c) surfaces as a
deterministic repro instead of a flake; pairs with rank 1 (fresh worktree
+ shuffled order = the honest environment on both axes). Cost: low;
evidence for the mechanism: the defect itself, already measured.

## Below the line

- **Deterministic repair/triage layer for generated tests** (02): only if
  generation is ever adopted — 9-rule-equivalent post-processor + the
  existing ruff/pyright/test_import_integrity gates before human review.
  Blocked on a decision to generate at all; the papers' own yield numbers
  (2–10% coverage-improving, low end at this suite's maturity; 21–34%
  build errors, 06) say the expected value is small.
- **C2-smell triage over scripts/** (03): cheap pass listing self-tests
  without negative arms in the measurement plane; extends an earned
  contract, but rank-2's report covers the highest-value slice first.
- **Rejected**: SBST/Pynguin corpus for bigger coverage deltas (02 —
  bloat, error rates, no corpus here); any LLM fine-tuning (01/05/06 —
  the repo fine-tunes no LLMs; 2026-08-10 freeze); similarity-scored
  test review (06 — EM would have graded the comment-satisfied pin
  perfect).
