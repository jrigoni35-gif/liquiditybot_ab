---
title: overfit_check (the battery runner)
category: entity
summary: "The offline script running OF-1..OF-8 and the project's standing learning-health baseline — with its synthetic→live switch stated correctly at last (len(X) >= len(FEATURE_NAMES)*10 = 640 over LOADED rows; there is no 60, and 'live rows' in its own output was a stale misnomer fixed 2026-08-09), its first honest live grading (3 pass / 4 fail on the repaired corpus), and the 8e9d7e6f gate policy that scoped what those verdicts BLOCK without touching what they MEASURE — yielding the first battery ever to go all-green while grading the LIVE corpus"
tags: [script, measurement, overfit, incident, gate-policy]
sources: 11
updated: 2026-08-09
---

# overfit_check (the battery runner)

The offline runner for the [[concepts/overfit-battery]]. Its passed/failed count is the project's
standing learning-health baseline and the subject of the longest-running document in the corpus.

## What it computes
Memorization gaps per family, a shuffle null, [[concepts/pbo-and-cscv|PBO]] on the deployed selection
rule, plateau, deflated Sharpe, purge/leakage, and degrees of freedom (rows-per-feature and
dead-feature fraction).

## Its most important property
It measures **the deployed rule**, not argmax. This is the constraint that makes it meaningful and the
one the [[concepts/gort-rule]] elevates to binding policy.

## The synthetic → live switch, stated correctly (corrected 2026-08-09)

The script grades against a **planted-signal synthetic benchmark** until the corpus is big
enough, then switches to **live grading**. The predicate is:

```python
min_rows = len(FEATURE_NAMES) * 10          # = 640
if not force_synthetic and len(X) >= min_rows and 5 <= y.sum() <= len(y) - 5:
```
(`scripts/overfit_check.py:180-182, :207`)

> ⚠️ **Two things about this were stated wrongly in the wiki for a day, and the script's own
> output is why** ([[sources/session-20260809-corpus-corruption]] §9):
>
> 1. **There is no 60.** A flat `60` existed once and was **deleted 2026-07-11 by
>    `7486ab29`** ("fix a live min_rows data-starvation bug"). It had not existed for a month.
> 2. **`len(X)` is LOADED rows — candidate + live, after every filter — NOT live rows.**
>
> **The script mislabelled its own quantity in two places** — the module docstring (`:9`) and
> the report string (`:216`) both called total loaded rows **"live rows"**. That is how a
> battery came to print **`live rows=467`** for a corpus holding **305 live rows total**
> that is **append-only** — an arithmetically impossible number that was read as growth
> instead of as the alarm it was. **Both strings fixed at source in `3c0debd7`**; the report
> now reads `live history ({len(X)} rows)`. Filed to
> [[synthesis/documentation-drift-register]].

**Why the distinction is load-bearing:** because `len(X)` counts **post-filter** rows, this
switch is coupled to [[concepts/era-exclusion]]. When the era filter **disarmed** on a
corrupted `label_era` column, `len(X)` jumped **467 → 9,739** — instantly crossing 640 and
flipping the whole battery to live grading. **The switch is not a function of how much
evidence exists; it is a function of how much the loader currently admits.** A filter
changing state moves it by thousands of rows in one step.

## Its first honest live grading — 3 pass / 4 fail on the REPAIRED corpus (2026-08-09)

**No threshold was moved** ([[concepts/never-widen-a-gate]]).

| Check | Reading | Verdict |
|---|---|---|
| **OF-1** memorization gap (logistic / gbt / mlp) | **+0.422 / +0.414 / +0.503** | FAIL |
| **OF-7** `dead_frac` | **0.95** (61 of 64 features near-zero) | FAIL |
| **OF-7** rows/feature | **10.8** (690 rows / 64 features) | **PASS — barely** |
| shuffle null | — | PASS |
| purge / leakage | — | PASS |

**The OF-1 gaps are WORSE on the clean corpus than on the corrupted pooled one**
(+0.42..+0.50 vs +0.19..+0.27) — **exactly as a smaller, cleaner corpus should read.** The
pooled figures were flattered by ~9,000 rows of other-era labels.

And the script's own learning-curve diagnostic states the
[[concepts/dof-budget]] conclusion **in its own voice, without having been told it**:

> **"CLIMBING (delta_auc=+0.112) — data-starved: more rows are still buying skill; corpus
> growth is the highest-leverage learning input right now."**

~~**Consequence:** every battery is red at the overfit stage until the corpus grows or the
feature count drops, so [[entities/auto-update]]'s deploy gate is blocked for any external
push. Three policy options are registered and **not decided**
([[synthesis/owed-measurements]] item 46).~~ **ADJUDICATED 2026-08-09, commit `8e9d7e6f` —
option (a); see below. The readings above are unchanged and still print every run.**

## The exploration-phase gate policy (`8e9d7e6f`, 2026-08-09)

**What the adjudication changed is the BLAST RADIUS of a verdict, never a threshold, and
never a measurement** ([[sources/session-20260809-gate-policy-and-self-heal]] §3).

**The diagnosis:** OF-1 and OF-7's dead-feature check are **MODEL-READINESS** gates that
were being consumed as **CODE-DEPLOY** gates — the battery stage feeds
`auto_update.battery_passes`, so a **data-starved corpus was holding code-safety fixes
hostage**. On the night before, a critical staleness fix could not ship because the model
needed more rows.

**The predicate** (`scripts/overfit_check.py:101`):

```python
def gate_is_informational(explore_on: bool, on_synthetic: bool) -> bool:
    return bool(explore_on) and not bool(on_synthetic)
```

One pure function, called by **both** OF-1 (`:745`) and OF-7's dead-feature check (`:943`),
*"so the two gates can never drift apart, and … so the policy is unit-testable instead of
only observable through a 40s CLI run."* Four deliberate properties:

| Property | Why |
|---|---|
| **Informational only while `ml.exploration.enabled`** | the **OF-5/DSR precedent** — the corpus is dominated by EV-mixed PT-050 probe/candidate rows **bought to acquire labels**, so OF-1 is grading the acquisition phase |
| **FAIL-CLOSED** | a caller that could not read the config passes `explore_on=False` and gets the **full gate** |
| **HARD on SYNTHETIC, always** | there OF-1/OF-7 validate the **INSTRUMENT** against a planted signal with a known answer — *an instrument may not grade itself leniently* |
| **SELF-TERMINATING** | flip exploration off and both re-arm — **no stamp, no operator memory** |

**Pinned so it stays scoped:** `test_thresholds_are_untouched` fails if **0.12** or **0.55**
is edited; `test_informational_lines_still_report_the_number` asserts the gap value **and**
the re-arm condition still print (*a softened gate that stops printing its measurement is
how a red goes invisible*); `test_both_gates_use_the_one_predicate` prevents OF-1 and OF-7
diverging. 8 tests in `tests/test_overfit_gate_policy.py`.

### The defect this work exposed in the script itself

**`_explore_on` was derived TWICE** — once at the config block (`:693`, through
`main.load_config`) and once **inside the DSR block from a SECOND direct read of the repo's
`config.json` that BYPASSED `main.load_config`**, so an **injected config could not
influence OF-5's phase**. Now derived **once**, through the injectable path, with `:999`
carrying an explicit comment that it is not re-derived. This is the night's second instance
of [[concepts/two-paths-one-quantity]] — **inside a single file** — which is why the new
policy was built as one shared predicate rather than two call sites.

It also exposed a **brittle assertion** in `tests/test_audit_ml_offline.py`: a bare
substring check read `"2|0 live labeled trades"` as the `"0 live labeled trades"` it meant
to forbid, so the test **FAILED on a report that proves the fix**. Now word-boundary
anchored ([[synthesis/documentation-drift-register]]).

### The battery this unblocked

**pytest 3473 + 1 skipped parallel / 19 serial timing / smoke 219 / assurance 49 /
overfit 3 pass 0 fail / ruff / pyright / bandit / compileall / quant G1–G5.**

> **The first fully-green battery since the incident — and the FIRST EVER in which the
> overfit stage grades the LIVE corpus rather than falling back to synthetic.** Every
> all-green battery before this one was green at a stage measuring a **planted signal**,
> because `len(X) >= 640` was never satisfied on a clean corpus. This green is strictly
> stronger than its predecessors, and it was reached **without moving a number**.

## Its consistency requirement
It must load the corpus through the **same filters as the production trainer**. When a filter existed
that only the trainer applied, an adoption reading taken under that mismatch "would certify a selection
process the bot no longer trains on."

## What it has never reported
That **every model rung loses to a base-rate constant** — the gap motivating
[[concepts/null-model-floor]].

## Fixes it received
Deflated-Sharpe sample moments (`ddof=1`), exact inverse-normal quantiles in the expected-maximum term,
and an extras-liveness diagnostic added as report-only info lines.

## Its tests as a load hazard (2026-08-08)
The pytest tests that drive `overfit_check` as a **CLI subprocess** carry hard **120s wall
timeouts** — calibrated for a quiet machine, blown intermittently under the battery's 8-way
`-n 8` saturation (`subprocess.TimeoutExpired`; also the 3 failures of the ~1.7x-overhead
coverage run on 08-07). Six of them (`test_pbo_variants` CLI ×3, `test_overfit_check_ci`
subprocess ×3) are the largest bloc of the 17-test `@pytest.mark.timing` family that
`be341867` moved into the battery's **serial pass**, where the wall is judged on the load
profile it was calibrated for ([[sources/session-20260808-battery-split-freeze-gate]] §1,
owed item 44). The script itself is unchanged — the hazard was the harness's clock, not the
battery's math.

**The split's first multi-battery day held:** the 08-08 evening ship cycle ran **four
batteries with zero timing-family flakes**, while its **three reds were all legitimate
downstream schema pins** of the 41b corpus change — including the pin that exposed
`core/persistence.py`'s fixed-shape pending-tuple rebuild before it could eat the new
9th slot on restart ([[sources/session-20260808-evening-availability-persistence]] §1).
One day in: flakes scheduled away, honest reds still biting — exactly the division of
labor the split promised.
