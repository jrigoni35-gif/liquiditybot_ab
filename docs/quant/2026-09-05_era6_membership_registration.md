# Era-6 cohort membership — REGISTERED 2026-09-05, before the readout

**Status: REGISTERED. Operator-adjudicated 2026-09-05. Rule: STAMP-PURITY.**

## Why this document exists, and why its date matters

The era-6 cohort (`exec_era 9-16ec821e`, accruing from the cut-#9 restart
2026-08-30T15:32:36Z) reaches its pre-registered n=50 in roughly six days.
Until 2026-09-05 **no document said which trips are members.**

That gap was not academic. `scripts/cohort_eval.py` reconstructs round trips
from `outputs/fills.csv` and stamps each with the set of `exec_era` values its
legs carry. Trips do not partition cleanly:

- some have every leg stamped `9-16ec821e`
- some **straddle** — opened under cut #8, closed under cut #9
- some carry a leg with **no stamp at all** (the stale-binary case this
  report already counts), or a **blank** stamp (pre-stamp rows)

Each choice yields a different n, a different readout date, and a different
cohort. Choosing after seeing the numbers is exactly the selection the
pre-registration discipline exists to prevent. **This is registered while the
cohort is short of its threshold**, which is the only moment the choice is
worth anything.

Measured at registration (2026-09-05T12:09:54Z, `outputs/fills.csv` live and
mutating — **re-derive, do not cite these**): 25 pure, 4 partial-stamp, 6
straddling, 1 fully unstamped, against a pooled era-4 population of 94.

## THE RULE

> **A trip is a member of era-6 if and only if EVERY leg of that trip carries
> the `exec_era` stamp `9-16ec821e`.**

Explicitly excluded, each for a stated reason:

| class | excluded because |
|---|---|
| **Straddling** (opened cut #8, closed cut #9) | Its entry decision was priced and sized under the superseded 40/80 fee booking. The moratorium's words are "nothing accruing now may be pooled with them" — importing the entry is pooling. |
| **Partial-stamp** (all stamped legs agree, but ≥1 leg unstamped) | "Every stamped leg agreed" is a weaker claim than "this trip is wholly inside the era". An unstamped leg is unattributable, not attributable-by-default. The stamp has failed before, so this class is not hypothetical. |
| **Fully unstamped** | Belongs to no era by construction. |

**Rationale.** The moratorium says accrual "begins at the cut #9 runner
restart, from zero". A trip only one of whose legs was granted by the cut-#9
binary was not, in any useful sense, produced from zero under cut #9. The
conservative reading is also the slower one — stamp-purity reaches n=50 later
than any-leg — which is the direction a registration should err, because the
cost of waiting is delay and the cost of pooling is an uninterpretable
readout.

**What this rule does NOT do.** It changes no selection predicate, no band,
and no verdict threshold. `era4_trips()` is untouched, and its headline
`accrual: N/50` remains the era-4 pre-registered population, which pools cuts
#7/#8/#9 by construction and must never be quoted as an era-6 figure. This
document names the SUBSET the era-6 readout is about; it does not alter the
machinery that produces it.

## Where the number comes from

`python scripts/cohort_eval.py` → **PER-ERA SEGMENTATION** → the line
`CURRENT-ERA ACCRUAL: n/50`. That block implements exactly this rule
(`homogeneity()`: a trip increments `by_era[e]` only when `len(eras) == 1`
**and** it carries no unstamped leg; otherwise it lands in `(partial)`,
`(straddling)` or `(unstamped)`). The buckets are asserted exhaustive against
n by `tests/test_cohort_era_segmentation.py`, including one pin that runs the
real ledger.

No count is written into this document as a live figure on purpose. Re-derive.

## Registered open question, NOT settled here

The era-4 readout decision table
(`docs/quant/2026-08-16_era4_readout_decision_table.md`) was scoped to "when
the era-4 cohort reaches n=50" — a gate that has already fired (COST_BOUND at
n=54). **Whether its three readout arms transfer to era-6 unchanged, or era-6
needs its own signed readout registration, is NOT decided by this document.**
This registration fixes MEMBERSHIP only. The readout rule is owed separately
and is owed before n=50.

## Honest limits

- Registration fixes the rule, not the interpretation. A cohort of 50 at
  mean uniqueness ~0.30 carries an effective n near 15; the readout names
  which decision became decidable, and never claims a resolved effect size.
- The population is ~100% probe admissions (`ml.exploration.p_win` exceeds
  the fee-derived entry bar, so a probe clears by construction). Era-6
  therefore measures the exploration constant, not the selector. That is a
  property of the cohort, not of this rule, and it is not fixed by choosing
  membership differently.
- Stamp correctness itself has never been verified against the binary that
  granted each fill — only self-consistency. This rule makes unstamped legs
  exclude a trip, which is the conservative response to that gap, not a
  repair of it.
