---
title: Degrees-of-Freedom Budget
category: concept
summary: An explicit running budget of model-adjacent features spent against a rows-per-feature floor and a program-wide handful cap — re-derived 2026-08-08 in effective terms (hundreds of labels fund ~2-5 effective context features TOTAL; at 64 features vs ~61 fresh-era labels the ledger is CLOSED) — and RESTATED AS A MEASUREMENT 2026-08-09: on the repaired 690-row corpus the battery's own learning curve reads CLIMBING (delta_auc=+0.112, 'data-starved'), rows/feature 10.8 passes barely while dead_frac 0.95 fails, and OF-1 gaps got WORSE after the corpus was cleaned (+0.42..+0.50 vs the corrupted pool's +0.19..+0.27). The 8e9d7e6f exploration-phase gate policy does NOT relax this ledger — the readings are unchanged and still print every run; only the verdict's authority over CODE deploys was withdrawn. FALSIFIER ATTACHED the same day: 'data-starved' predicts gross edge > 0 that is merely hard to select on, and measured gross P&L before any fees is −11.66 (~0) against 382.59 of fees — falsified as a COMPLETE account; the ledger's readings and its two exits are unchanged, what is withdrawn is the licence to offer corpus growth as the reason the book loses money
tags: [features, budget, overfit, falsifiability]
sources: 8
updated: 2026-08-09
---

# Degrees-of-Freedom Budget

## Definition
Every candidate input carries an explicit **DoF cost**, tracked against the corpus size. OF-7 fails
below **10 rows/feature**; a 3,628-row corpus with 62 features sits at ~58.5.

## The binding constraint is not the floor
> "The binding constraint is not OF-7's floor but the program-wide 'handful' cap and the dead-feature
> check."

## The central encoding principle
> **"Slow context belongs in structural gates and the long book's admission rule, not in the 5m model
> matrix."**

Structural gates cost **zero model DoF**, though their thresholds remain tunables under config-guard
and plateau discipline. This is what lets the program adopt a great deal of slow context while spending
only 3-4 model-adjacent features.

## Standard kill: the cadence kill
Series whose native cadence is far slower than the decision cadence are **dead features by
construction** — a monthly series is stale for ~8,928 cycles against a 5-minute loop. This alone
rejects an 18-series macro set and every quarterly/annual institutional database.

## External corroboration kept
An automated factor-research system's headline — that it beat factor libraries using **">70% FEWER
factors"** — is retained specifically as outside support for the handful cap.

## The 2026-08-08 effective-DoF arithmetic — the ledger is CLOSED
The institutional/government data adjudication
([[sources/session-20260808-institutional-data-adjudication]]) re-derived the budget in
**effective** terms: a corpus of hundreds of labels funds **~2-5 effectively independent
context features TOTAL** (Peduzzi events-per-variable + DSR/PBO effective-trials accounting),
and mutually-correlated candidates collapse — **funding / basis / COT / DVOL together count
as ≈ 1.5 effective features**, not four. At **64 features vs ~61 fresh-era labels** the
ledger is not merely tight, it is **CLOSED: zero new model features until the label corpus
funds them.** Consequence: every 2026-08-08 adoption enters at **0 model DoF**
(telemetry → risk-gate consumers), and schema graduation happens only via schema-AB + era
stamp when labels fund it.

**First test of the closed ledger, passed the same day:** owed 41b (`64724480`,
[[sources/session-20260808-evening-availability-persistence]] §1) added **4 trailing
corpus columns** (`avail_web`/`avail_equity`/`avail_options`/`quotes_frozen`) at **zero
model DoF** — bookkeeping, never features, same class as the price anchors; `""` = UNKNOWN
vs `"0"` = measured down. The availability truth the model would *want* is now recorded
where a future schema-AB can adjudicate it, while the model matrix stays at 64 — recording
more while spending nothing is exactly the closed ledger's intended shape.

## The ledger restated by an independent instrument (2026-08-09)

The 08-08 arithmetic above was a **derivation**. On 2026-08-09 the overfit battery, run on
the **repaired** corpus, produced the same conclusion **as a measurement, in its own voice**
([[sources/session-20260809-corpus-corruption]] §8):

> **"CLIMBING (delta_auc=+0.112) — data-starved: more rows are still buying skill; corpus
> growth is the highest-leverage learning input right now."**

Supporting readings on **690 rows / 64 features**:

| Reading | Value | Verdict |
|---|---|---|
| OF-7 rows/feature | **10.8** | **PASSES — barely** (floor is 10) |
| OF-7 `dead_frac` | **0.95** | **FAILS** — 61 of 64 features near-zero importance |
| OF-1 gaps (logistic / gbt / mlp) | **+0.422 / +0.414 / +0.503** | **FAILS** |

**Two details are worth keeping.**

**First, the OF-1 gaps got WORSE after the corpus was CLEANED** — +0.42..+0.50 on the clean
690-row corpus against +0.19..+0.27 on the corrupted 9,746-row pooled one. That is the
correct direction: pooling three label definitions inflated the row count without adding
information, and the memorization gap was **flattered by rows that should never have been
there**. **A bigger corpus made the model look better while making it worse** — the exact
failure the DoF ledger exists to price, arriving as an accident rather than a decision.

**Second, rows/feature passing at 10.8 while `dead_frac` fails at 0.95 is the ledger's own
"binding constraint is not the floor" claim, measured.** The floor is satisfied; the
**dead-feature check** is what fails. Both stated exits from the red are the ledger's own two
levers, in its own units: **grow the corpus** (the learning curve says rows are still buying
skill) or **cut the feature count** (item 45f's schema-AB prune experiment — 61 dead features
is a large target).

*(Boundary: this is a repo-side grading of a corpus whose live rows are
sim-execution-conditioned. It says the corpus cannot fund 64 features; it says nothing about
whether the features would work on real fills.)*

> **The 2026-08-09 gate policy does NOT relax this ledger** (`8e9d7e6f`,
> [[sources/session-20260809-gate-policy-and-self-heal]] §3). OF-1 and OF-7's dead-feature
> check now report **informationally** while `ml.exploration.enabled` — but the readings are
> **unchanged, still computed, and still printed every run** with the gap value and the
> re-arm condition, pinned by test; **0.12 and 0.55 are pinned against edits**. What was
> withdrawn is the verdict's authority over **code deploys**, which it was never evidence
> for. **The ledger's two exits are exactly as before: grow the corpus, or cut the feature
> count.** Reading the policy as "the DoF pressure is off" inverts it — the policy exists
> *because* the pressure is real and was being applied to the wrong thing.

## The falsifier "data-starved" now carries (2026-08-09)

The battery's own learning curve prints **CLIMBING** (`delta_auc=+0.112`, *"data-starved: corpus
growth is the highest-leverage learning input"*), and this page restates it as a measurement. That
reading is real and unretracted. **What it is not permitted to do any longer is stand as the
explanation for the economics.**

Stated as a falsifiable claim, **"data-starved" predicts there IS gross edge > 0 that is merely
hard to select on.** Measured the same day
([[sources/session-20260809-unbiased-economics]]), over ~250 closed positions:

```
GROSS trading P&L, before ANY fees : −11.66   (~−$0.05/trade — indistinguishable from zero)
total fees paid                    : −382.59  → fees are 32.8x |gross edge|
```

> **FALSIFIED as a complete account.** There is **no measured gross edge to be starved OF.** A
> learning curve can only climb toward something; nothing in the corpus currently demonstrates
> that the something is above zero. Corroborated by two instruments that share no mechanism with
> the curve: **OOF AUC 0.43–0.48** (at/below chance) and champion **Brier 0.24728 vs 0.25** for a
> coin.

**The ledger itself is unchanged.** Rows/feature 10.8, `dead_frac` 0.95, OF-1 gaps
+0.42..+0.50, the two exits (grow the corpus, or cut the feature count) — all stand exactly as
written above. What changes is the **inference licence**: "the corpus needs to grow" may no
longer be offered as the reason the *book loses money*, because the book's gross P&L is ~0 and
**more rows of a zero-mean population is more of the same population.**

⚠️ **This term is house vocabulary and now carries its falsifier by rule**
([[concepts/unfalsifiable-explanation]]). Note the sharper consequence for **corpus growth as a
strategy**: the corpus carries `net_pnl_usd` and **no gross column**, so the binary win/loss label
**conflates "signal was wrong" with "signal was right and costs ate it" at the point where the
model learns** — a distinction no number of additional rows can teach
([[synthesis/owed-measurements]] item 50). And the cheapest test of the starvation claim is
**free**: the **9,570 CANDIDATE rows cost zero fees** against 305 live rows that cost ~382.59.

## Measured by
[[entities/overfit-check]]

## The unresolved tension
The DoF ledger is computed on **raw row count**, not on the uniqueness-adjusted effective sample size.
If the ~7x overlap ratio from [[concepts/average-uniqueness-and-ess]] still holds, effective
rows/feature is nearer ~8-9 than 55+ — **below OF-7's floor**. The two documents never reconcile. See
[[synthesis/open-contradictions-register]]. *(The 08-08 arithmetic above sides firmly with
the effective view — it is the first budget statement computed in effective units end-to-end.)*
