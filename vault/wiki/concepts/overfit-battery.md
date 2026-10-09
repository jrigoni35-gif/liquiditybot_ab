---
title: The Overfit Battery (OF-1..OF-8)
category: concept
summary: Eight independent overfit checks whose passed/failed count is the project's standing learning-health baseline — and, as of 2026-08-09, a baseline that must be qualified by the GATE POLICY STATE as well as by corpus size and date, because OF-1 and OF-7's dead-feature check now report informationally while exploration is on (blast radius scoped, thresholds and printed numbers untouched)
tags: [overfit, gates, measurement, gate-policy]
sources: 8
updated: 2026-08-16
---

# The Overfit Battery (OF-1..OF-8)

> ⚠️ **OF-3 IS NOT READABLE AS A PASS/FAIL ON THIS CORPUS (2026-09-13,
> [[sources/session-20260913-guard-failopen-and-gauge]]).** The rung is
> DISCONTINUOUS in the corpus SIZE, measured deterministically (same array
> twice → identical pbo, so this is not RNG): **0.1857 at 18,018 rows,
> 0.9000 at 18,017, 0.6286 at 18,010** — a band of **0.714 over ten rows**,
> three of six readings each side of the `<=0.5` gate. Re-measured the same
> evening at T=18,043 the band was 0.186 with **0 of 6 RED**, so **the band
> itself is a function of T and decays as the corpus grows.** Any pbo figure
> in the table below, including the `pbo 0.03` at n=4,907, is a point estimate
> with an unquoted band and must not be read as a verdict about the strategy.
> Re-derive with `scripts/pbo_row_sensitivity.py` (committed that day
> precisely because the previous study's harnesses were lost to a temp
> directory); quote NEITHER the point NOR the band.

## The checks
- **OF-1** — memorization gap (train vs OOF) per family: logistic / gbt / mlp. **The standing failure
  trio throughout the corpus.**
- **OF-2** — shuffle null (a signal must beat a label-shuffled control).
- **OF-3** — [[concepts/pbo-and-cscv|PBO]] on the deployed selection rule.
- **OF-4** — plateau (do not tune to a backtest peak).
- **OF-5** — Deflated Sharpe Ratio.
- **OF-6** — purge (leakage across the train/test boundary).
- **OF-7** — degrees of freedom: rows/feature floor of 10, and dead-feature fraction against a 0.55
  gate.
- **OF-8** — the eighth check completing the battery.

## Standing baselines observed
| Corpus | Result | Notes |
|---|---|---|
| 3,651 | 3 passed / 5 failed | the PBO 0.56 breach |
| 4,642 | 4 passed / 4 failed | OF-1 trio + dead_frac 0.60 |
| 4,692 | 5 passed / 3 failed | OF-1 trio only |
| 4,907 | 5 passed / 3 failed | pbo 0.03; "PROGRAM FULLY CLOSED" |
| 661 (post-era-exclusion) | 3 passed / 4 failed | new series; rows/feature 10.7 |
| 690 (repaired era-3 corpus, 2026-08-09) | **3 passed / 4 failed** | first honest live grading; OF-1 +0.42/+0.41/+0.50, dead_frac 0.95, rows/feature 10.8 |
| 701 (same corpus, under the `8e9d7e6f` gate policy) | **3 pass / 0 fail** | **same readings**, OF-1 and OF-7-dead now **INFORMATIONAL** while exploration is on |

> **The last two rows are the same measurement.** Nothing about the corpus improved between
> them; what changed is which battery arm the verdict is permitted to stop. Quoting either
> without the policy state attached is a category error — see below.

## The gate policy (2026-08-09, `8e9d7e6f`) — what a battery result now means

**OF-1 and OF-7's dead-feature check are MODEL-READINESS gates.** They were being consumed
as **CODE-DEPLOY** gates via `auto_update.battery_passes`, so a data-starved corpus could
hold **code-safety fixes** hostage. The adjudication **scoped what the verdict BLOCKS and
left what it MEASURES untouched** ([[sources/session-20260809-gate-policy-and-self-heal]] §3,
[[entities/overfit-check]]).

The policy is one pure predicate — `gate_is_informational(explore_on, on_synthetic)` — with
four properties: informational **only** while `ml.exploration.enabled`; **fail-closed** on an
unreadable config; **hard on the synthetic benchmark always** (an instrument may not grade
itself leniently); **self-terminating** when exploration goes off.

**Consequences for how this page's numbers must be read, going forward:**

1. **A pass/fail count is now qualified by THREE things, not two** — corpus size, date, **and
   the gate policy state** (exploration on/off, live vs synthetic). The vault's standing rule
   *"never write a bare battery result"* extends accordingly.
2. **A green battery no longer implies OF-1 and OF-7-dead passed.** It implies they either
   passed or reported informationally. The numbers are still printed on **every** run, with
   the gap value and the re-arm condition, and a test enforces that they are.
3. **The synthetic benchmark is now the harder grader**, permanently. That inversion is
   deliberate: on synthetic, these checks validate the **instrument** against a planted
   signal with a known answer.

**No threshold moved. 0.12 and 0.55 are pinned by `test_thresholds_are_untouched`.** This is
a scoping decision, not a [[concepts/never-widen-a-gate]] breach — the distinction being that
the gate still measures and still reports exactly what it did; only its authority over an
unrelated verdict (code correctness) was withdrawn.

## Two demoted readings
Both **row count** and **single-seed `dead_frac`** are explicitly demoted as progress metrics — see
[[concepts/conscious-re-baseline]].

## The gap the battery does not close
It never reported that **every model rung loses to a base-rate constant**. That absence is the whole
motivation for [[concepts/null-model-floor]]: "the gate cannot keep hiding that every rung loses to a
constant."

## The battery is CURRENTLY on the synthetic benchmark (measured 2026-08-15)

The page above says the baseline must be qualified by corpus size. This records what that
qualification actually *is* right now — because "qualified by corpus size" and "not measuring the
market at all" are different claims, and only the second is true today.

`scripts/overfit_check.py` swaps in a **planted-signal synthetic benchmark** whenever loaded rows
fall under `len(FEATURE_NAMES) * 10` = **640** (the `min_rows` predicate in `load_dataset`). Run
from the real data root 2026-08-15, its header reads verbatim:

```
[OF-1] train/OOF gap  (SYNTHETIC benchmark (loaded rows=346 < 640)
                       - validating machinery, not market)
```

**346 loaded rows.** Every `passed 7, failed 0` recorded since era exclusion pushed the loaded
corpus under 640 has therefore been **instrument-validation, not a market read** — it is not, and
never was, evidence that the deployed strategy is un-overfit.

**The tool is honest; the READER was not served.** The caveat sits in the OF-1 header while
`passed N, failed 0` is the last line, and the repo's definition-of-done lists this script as a
gate. That is [[concepts/false-green]]'s subtlest form — an accurate instrument inside a checklist
implying a different claim. Fixed 2026-08-15 by printing the corpus on the **summary** line with an
explicit "validates the OVERFIT MACHINERY, not the market" banner; nothing about what runs or what
passes changed.

**Two rungs could not fire either**, same run:

- **OF-4 plateau — INERT.** All three probes (`position_sizer.min_p_win`,
  `profit_taking.chandelier_k`, `pretrade.min_edge_cost_ratio`) reported
  `flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) - parameter inert on this recording`.
  A plateau test over a recording that opens **zero positions** cannot tell a plateau from a cliff.
- **OF-5 DSR — DEFERRED**, 22 conviction-marked live trades against a floor of 30 (mixed n=327).

> **SUPERSEDED for OF-5 as of 2026-09-11 — the gate ARMED, FAILED, and its label was FALSE.**
> The conviction floor was reached and OF-5 now grades. It reads FAIL. **That FAIL is not a
> verdict on the deployed strategy**, for reasons measured the same day in
> [[sources/session-20260911-of5-dsr-reading]]:
> the label said `P(true SR > 0)` while the code computes `P(true SR > sr0)` with `sr0 > 0`;
> the sign reading is `PSR(SR*=0)` and it does **not** clear the bar the battery demands in the
> other direction; the gate's minimum detectable effect at this n is far above any edge this
> book targets; and the sample is **not era-scoped** — it pools every era it spans, because
> `signal_history.csv` carries no `exec_era` column at all. Re-derive all four from
> `python scripts/overfit_check.py`, which now prints the sign reading and the corpus span
> beside the verdict. No number from that day is copied here on purpose.
- **OF-6 names its own redundancy**: *"expanding-window design keeps boundary leak ~0 by
  construction; shuffle-null [OF-2] is the leak gate."*

**Third instance of one root cause.** Era exclusion is correct — refusing to pool label eras whose
base rates span 40x is not optional ([[concepts/era-exclusion]]). But the same shrinkage that fired
ML-083's unbounded unlock ([[concepts/deploy-deadlock]] §third polarity) also drops this battery to
synthetic. **One correct decision has now disabled two safeguards and starved a third.** The
argument is not against era exclusion; it is that these safeguards were never sized for a corpus
this small — the shape of [[synthesis/owed-measurements]] item 73.

> ⚠️ **Do not "repair" any of this by lowering a floor.** 640 here, `SG_MIN_ROWS`=100 in
> `gate_truth_report`, and n=50 at the era-4 gate are **measurement standards, not tunables** —
> `gate_truth_report`'s own docstring says exactly that. Moving one so a gate reads "real" is
> precisely [[concepts/never-widen-a-gate]]. The correct response to a degraded gate is to say so
> out loud and treat what it was meant to prove as unproven.
> — [[sources/session-20260814-cohort-instruments]]

### Still SYNTHETIC, and the door is un-fenced (2026-08-16)

**The state has not changed, and that is the finding.** The battery is still on the planted-signal
synthetic benchmark; every `passed 7, failed 0` recorded since era exclusion pushed the corpus
under the floor has validated the **INSTRUMENT, not the STRATEGY**.

**The floor, double-derived:** `len(FEATURE_NAMES) * 10`, where `FEATURE_NAMES` in `ml/features.py`
holds **64** entries (counted by AST, not by grep — [[concepts/iron-law-of-debugging]]'s
AST-over-prose discriminator) ⇒ **640**.

**Last recorded run** — `outputs/overfit_report.md` read **2026-08-16, in the 20:55–21:05Z window**;
the report's own header is stamped **2026-08-15 16:13 UTC**, i.e. *no battery has run in over a
day*. Header and summary line now agree verbatim:

```
Dataset: SYNTHETIC benchmark (loaded rows=347 < 640) — validating machinery, not market
Corpus:  SYNTHETIC benchmark (loaded rows=347 < 640) — validating machinery, not market
> **This green validates the OVERFIT MACHINERY, not the market.**
```

> **The loaded-row count is a LIVE number and is deliberately not frozen here.** Recorded readings
> span **346 / 347 / 353 / 365** across 2026-08-15 alone — the corpus grows between runs. **Read
> the summary line of the run in front of you**; do not quote this page for it. What is stable is
> the *relation*: `loaded < 640` ⇒ SYNTHETIC.

**The structural cause is now named, and it is a designed-in window, not an accident.**
`ml.era_exclusion.min_new_era_rows = 150` sits **BELOW 640**, guaranteeing a
`150 ≤ new_era_rows < 640` band in which the era filter is **armed** and the battery is
**simultaneously synthetic**. **We are inside that band now, and it recurs at every horizon
migration.** Era exclusion is the **transmission**, not the trigger: the counterfactual on a frozen
corpus loads **5,287 rows REAL** over a mature era, so the filter alone can never drive a
>640-row corpus under the floor — **the trigger is the era RESET**.

**The companion hole — REAL WHEN FOUND, FIXED INSIDE THE SAME WINDOW.** `core/config_guard.py`
gave `ml.era_exclusion.forced_on` a semantic check while `forced_off` carried **only a type check**
— and `forced_off` is the lever with the **larger blast radius**, because it is the one that
silently makes the corpus **BIGGER**: flipping it moves the battery **365 → 10,534 rows** and
**SYNTHETIC → REAL** across a corpus mixing **five label eras whose base rates span ~40x**
(`exit_sim_time_stop` 0.65% … `legacy` 26.1%). That is the widening `CLAUDE.md` forbids **by
floors**, reached through a **config flag** instead.

**Closed by `7f48f6ea` (2026-08-15T22:35:06Z, inside the gap; verified at head `c4272391`)**, which
added *both* fences: a **WARN on the `150 < 640` window** whose text forbids moving either number,
and **parity semantics on `forced_off`** — as a **WARN, not a FATAL**, because `true` is a
legitimate rollback mode and *"a FATAL would make the pre-exclusion view unreachable, which is the
one thing a rollback lever may never be."* Full treatment, including why that WARN/FATAL choice is
this doctrine going right: [[concepts/never-widen-a-gate]] §a third road into the forbidden move.

> ⚠️ **Correction recorded per [[synthesis/governance-doctrine]] rule 16.** The 08-12..16 catch-up
> filed this hole as **"fenced but NOT fixed"**. It was reading a **pre-`7f48f6ea` tree** — a state
> already repaired by a commit **inside the very window the catch-up existed to cover**. *A finding
> is as stale as the tree it was measured on, and "still broken" needs re-derivation exactly as
> much as "now fixed" does* ([[concepts/session-identity-is-not-stable]]).

> ⚠️ **What is still true, and still owed:** the `150 < 640` window is **disclosed, not eliminated**
> — the numbers did not move and must not. **The battery is synthetic right now.** Disposition is
> **OPERATOR adjudication**; registered as owed, **not started**.
> — [[sources/session-20260816-catchup-08-12-to-08-16]]
