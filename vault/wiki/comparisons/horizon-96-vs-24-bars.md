---
title: Label Horizon: 96 Bars vs 24 Bars
category: comparison
summary: "The horizon re-alignment that unblocked live labels, why neither setting was in the informative range, and the third setting (432 bars) now in flight as a pre-registered experiment — and, as of 2026-08-09, the project's ONE live lead now that measured gross edge is ~0: shadow win rate rises monotonically 22.3% → 30.4% → 35.4% at 108 → 216 → 432 bars, i.e. exits are early relative to the cost being paid. A GEOMETRY lead, not a model lead — and still not an expectancy result, since a rising p leaves the payoff ratio and the fee untouched. As of 2026-08-10 the cohort contains THREE execution-regime boundaries on the fill axis (8e5455e8 2026-08-02, 3cfe0710 2026-08-08, aeeaae36 2026-08-10T11:03:35Z), each strictly less generous than the last, so any trend across the cohort is confounded with the fill regime by construction - and every close so far is PRE-#4, carrying the ~1.88x near-touch fill bias. The 2026-08-10 evening capital epoch (23:05:27Z, the $800 stressor with venue floors unscaled) adds a fourth cut on the capital axis. The geometry hold is unchanged: none of the four moved a barrier, horizon or exit policy."
tags: [comparison, labeling, horizon, geometry]
sources: 7
updated: 2026-08-10
---

# Label Horizon: 96 Bars vs 24 Bars

| | 96 bars (8h) | 24 bars (2h) |
|---|---|---|
| Live rows entering the era | **0 of 256** | **3, then 7** |
| Protective overlay fires at | bar 36 — **before** the vertical | bar 36 — **after** the vertical |
| [[concepts/clock-inversion]] | **present** | resolved |
| Barrier width in horizon-sigma | **1.69** | **3.39** |
| Literature norm | ~0.8-1.0 | ~0.8-1.0 |
| Outcome mix | — | **87.8% time / 8.6% SL / 3.6% PT** |
| Training corpus | ~2,141 rows | 379 -> 606 rows |

## What the change fixed
The overlay fired at bar 36 while the vertical sat at bar 96, so live positions closed ~3x sooner than
the label's horizon and **could never resolve in-era**. Moving the vertical inside the overlay's clock
converts essentially every probe into an era-valid row at a quarter of the capital-time, **suppresses no
protective exit**, and leaves the cost floor intact. Verified live: live era rows 0 -> 3.

## What it cost
The corpus dropped ~2,141 -> 379 rows, because "the 2,146 rows labelled at a 96-bar horizon answer a
question the bot no longer asks." Accepted as [[concepts/priced-bleed|priced]] and reversible — exclusion
is a view, not a deletion.

## What it did not fix, and the explicit refusal to scapegoat it
The follow-up measurement is emphatic that the horizon change is **not to blame** for the geometry
problem: at 96 bars the barrier-to-sigma ratio was 1.69 — "better, still 2x the literature, and it
carried the clock-inversion deadlock." **Neither setting was in range.**

Shortening the horizon **worsened** the ratio (sigma scales with sqrt(H) while the cost-floored barrier
does not move), which is precisely how the change surfaced
[[concepts/cost-to-volatility-ratio|the real constraint]].

## The lesson
A fix can be **correct on its own terms and still leave the binding constraint untouched** — and can
make the underlying ratio worse while making the system observable enough to notice.

## The third setting: 432 bars (shipped 2026-08-01, in flight)
The money-path "lengthen the horizon" option shipped as the **432-bar (36h) migration** (commit
`7566ea88`), a pre-registered experiment at **17 of 50** closed trades as of 2026-08-05.
`scripts/cohort_eval.py` refuses a verdict below 50, and that refusal is the point. The post-432
window recorded its **first win on 2026-08-05**: win rate **5.9%, Wilson [1.0%, 27.0%]** —
still **unreadable**, and the verdict is still refused, correctly; the hold continues. (Trail:
0/11 [0, 25.9%] late 08-02 → 0/14 [0, 21.5%] 08-03 → 0/15 late 08-04 → **1/17 [1.0%, 27.0%]**
08-05 — the interval tightens as closes accrue, and the lower bound has just lifted off zero.)

**HOLD — do not change label horizon, barrier geometry, or exit policy until the cohort fills.**
A geometry change resets the era clock in three places at once: the cohort counter, era exclusion,
and the era-keyed realized gate ledger. Expected fill time: 2–3 weeks at the observed close rate.

> ⚠️ **Execution-regime boundary INSIDE this cohort (2026-08-02, commit `8e5455e8`).** Honest
> fills shipped mid-cohort: `passive_base_prob` 0.45 → **0.048** (the XV-021 measured
> trade-through rate — [[sources/session-20260802-digest]] third addendum). The **first 11
> closes were earned under fills 9x too generous** to resting orders; closes after the commit
> are under the honest rate. The cohort's n=50 verdict **must be read across this boundary** —
> the two sub-samples are not the same experiment on the fill axis, and the close rate (hence
> the 2–3 week estimate) will slow under honest fills. The geometry hold itself is unchanged:
> `8e5455e8` moves no barrier, horizon, or exit policy.

> ⚠️ **THIS COHORT NOW CONTAINS THREE EXECUTION-REGIME BOUNDARIES, NOT ONE.** Two more landed
> after the note above, both on the **fill axis**, neither moving a barrier, horizon or exit
> policy — so the **hold stands unchanged**, and the *readability* of the eventual n=50 verdict
> degrades again:
>
> | # | commit | stamp | what changed |
> |---|---|---|---|
> | **2** | `8e5455e8` | 2026-08-02, ts~1785717000 | `passive_base_prob` 0.45 → 0.048 — fills were **9x** too generous before it |
> | **3** | `3cfe0710` | 2026-08-08 | TTL normalization — a 6h long-book bid had compounded to fill prob **≈1.0** |
> | **4** | `aeeaae36` | **2026-08-10T11:03:35Z** | double-count removal — resting orders had **two chances at one event**, `2f−f² = 21.96%` vs an `f = 11.66%` target, **1.88x at the touch** ([[sources/session-20260810-fill-double-count]]) |
>
> **Consequence for the verdict, stated before the data arrives rather than after.** The cohort's
> closes are now spread across **four fill regimes** (pre-#2, #2→#3, #3→#4, post-#4), each
> strictly less generous than the last. **A trend in win rate or close rate across this cohort is
> confounded with the fill regime by construction** — and the confound runs one way: later
> sub-samples fill less. Any read of "the cohort is getting worse" must first exclude "the
> simulator stopped paying."
>
> **And every close in the cohort so far is PRE-#4** — the ledger's last row predates `aeeaae36`,
> so there is **no post-#4 sub-sample yet at all**. The n=50 verdict will therefore be dominated
> by rows carrying the ~1.88x near-touch fill bias unless the cohort runs long enough to accrue a
> meaningful post-#4 population. **The 2–3 week estimate slows again**, for the third time and for
> the third time honestly ([[synthesis/owed-measurements]] item 1b).
>
> **What this does NOT license.** Owed 57's embargo is explicit: propagation into the cohort
> verdict is **DIRECTIONALLY SUPPORTED but UNMEASURED**, and **may not be cited against the
> 432-bar hold**. The hold is decided by the pre-registered n=50 rule, not by an argument about
> fill realism ([[concepts/never-widen-a-gate]], and the mirror — no silent tightening either).
>
> **(2026-08-10 evening: a FOURTH cut, on a different axis.** The **capital epoch**
> `2026-08-10T23:05:27Z` — the $800 stressor reset,
> [[sources/session-20260810-stressor-epoch]] — sits inside this cohort too. Capital 5000 →
> 800 with venue floors deliberately unscaled moves the $15 ticket floor from 0.3% to **1.9%
> of equity**, which shifts the gross% distribution through sizing floors. Any within-cohort
> trend is now confounded with the fill regime **and** the capital regime. The full cut table
> is [[synthesis/comparability-boundaries]]; the separate era-4 verdict gate reads only
> `max(B4_TS, CAPITAL_EPOCH_TS)` and is not this cohort's n=50 rule.)*

**First honest-fills day measured (2026-08-03, [[sources/session-20260803-bug-sweep]]):**
**~8 positions/day vs ~16 before** — the predicted drop, and it is half, not zero. Exits flow on
the honest side: 2 stale-loser purges (including a 100h ETH position) and `tb_time` verticals
firing. The cohort advanced 11 → 14 across the first honest-fills day, then **14 → 15 on
08-04** (~5 fill rows since morning — the honest cadence continues,
[[sources/session-20260804-deploy-gate]] §6), then **15 → 17 by 08-05** with `fills.csv` at
**668 rows (+8/day)** — the honest-fills cadence steady at the measured rate.

> ⚠️ **Second, unpriced throughput cost surfaced 2026-08-05 — candidate-pool saturation
> (report-only; the hold is unchanged).** The 08-05 debug sweep
> ([[sources/session-20260805-debug-sweep]], finding 4, MEDIUM · probable): with
> `multi_horizon.enabled: true` (horizons `[108,216,432]`), a decided candidate holds its
> `_cands` slot until the **full** horizon so shadows complete — retention grew **~2h → 36h
> (18x)** against a fixed `max_open_candidates: 200`. A saturated pool evicts the **newest**
> pending candidate (`self._cands.pop()` — correct when eviction was rare; at 36h retention
> eviction is the steady state), giving a candidate-label ceiling **≈ 200/36h ≈ 5.5/h** and
> inverting label sourcing toward exactly the quiet-hour bias the eviction choice was built
> to avoid. This is **distinct from the documented 18x live-label slowdown** — it throttles
> **candidate** labels, the dataset multiplier, and was not priced when the migration
> shipped. Per this page's hold: **no retune** — filed as
> [[synthesis/owed-measurements]] item 29 for fix adjudication.

### The hold held against a new input (2026-08-05 evening)
When PAXG and the haven gradient shipped (`717b2e39`,
[[synthesis/tangible-value-doctrine]]), the obvious next move — feeding the gradient to the model
— was **refused by this hold, explicitly and in the commit**: *"No feature-vector change: the
model schema is frozen mid-migration (the 432-bar cohort) and widening it for a signal with zero
track record would invalidate the in-flight experiment."* The instrument is **report-only**,
pinned by a parsed-AST test.

> **This is what the hold is for.** A pre-registered experiment is only pre-registered if the
> schema it runs on stops moving — and the pressure to widen it always arrives dressed as a good
> new idea. Worth recording that the refusal cost something real: the gradient will accrue its
> track record with **no model exposure at all** until the cohort verdict, which is the slower
> path and the correct one ([[concepts/shadow-first-adoption]]).

Second-order note: PAXG's arrival moved `skimmer.max_extra` **6 → 5** (the REST-fallback envelope
FATALs at 13 pairs), so the **discretionary** slots that feed candidate sourcing dropped by one —
a small further squeeze on the same throughput axis as the candidate-pool saturation above, and
another reason the cohort's fill estimate is a floor rather than a forecast.

Known costs and corrected claims ([[sources/session-20260802-digest]]):
- **Uniqueness gets worse, not better**: ~18x concurrency drives mean uniqueness from 0.156 toward
  ~0.009; the hard ceiling on independent evidence is `total_bars / 432` (~487 windows for two
  years).
- Three claims once offered in support were corrected: "median loss exceeds worst adverse
  excursion" (MAE is gross, P&L is net — the honest version is *the typical adverse excursion is
  smaller than the fee; the loss IS the fee*); "87% of trades reached positive MFE" (uninformative
  without a random-entry control); "kappa rises with horizon" (observed 48→96 kappa 0.736 sits at
  the sqrt(h1/h2)=0.707 no-predictability null — consistent with pure path overlap).
- Horizon extension ranks **last** among measured mitigation levers (Novy-Marx & Velikov 2016;
  Qian et al. 2007: zero gross benefit). It runs to n=50 because thrashing costs more than waiting.

## Per-asset ladder vs the first-touch null (2026-08-02 late)
Against the geometric first-touch null **P(PT) = 0.429** (= sl/(pt+sl) = 6/14 from the 8:6
barrier config), the only cells above null are **BTC h=48: 0.482 [0.448, 0.517]** and
**BTC h=96: 0.479 [0.448, 0.510]** — *multiple-testing caveat*, two cells out of a ladder.
Below null: **LTC h=48/96 ≈ 0.10**, **FLOW ≈ 0.33**. The per-asset-tuning claim in
[[sources/mdpi-label-driven-mhs]] has something to grab **only in the BTC cells**.

And no bracket geometry rescues any horizon: the pre-registered **48-combo geometry search**
(commit `663434ae`, battery green)
found nothing survives (Bonferroni z = 3.26, 222 real entries, config fees; best combo h=432
tp=1% sl=2%: mean −0.400%, lower bound −1.124%) — exit design minimizes bleed, it does not
create edge ([[sources/session-20260802-digest]] second addendum,
[[concepts/payoff-asymmetry]]).

## 2026-08-09 — this is now the project's ONE live lead, and it is a GEOMETRY lead

([[sources/session-20260809-unbiased-economics]] §5.) The whole-book decomposition put **gross
P&L before any fees at −11.66 (≈0)** against **382.59** of fees — no measured gross edge, and
therefore **no model lead**. Against that background, the horizon ladder is the only place where
something moves **monotonically with a knob**:

| Horizon | Shadow win rate |
|---|---|
| 108 bars | **22.3%** |
| 216 bars | **30.4%** |
| 432 bars | **35.4%** |

**Monotone across three settings.** The natural reading: **exits are early relative to the cost
being paid** — trades are closed before the move that would cover the round trip has had time to
happen, which is the same statement as the postmortem MFE finding (**median 0.18% / p90 0.55%**
against a **~0.65%** round-trip cost) seen from the time axis instead of the price axis.

> **Read it as GEOMETRY, not as a model result.** Nothing here is a prediction improving; it is
> the **barrier configuration** interacting with the cost floor. That matters for what gets
> worked on next: it points at tiers/stop/horizon, not at features or model families — and it
> agrees with `config_guard`'s standing warning, computed from **tiers, stop and fees alone with
> no model or corpus involved**: *derived entry bar **0.990** > 0.90 — "fix the geometry, the bar
> is only reporting it"* ([[entities/config-guard]]).

**Three cautions, all of which cut against over-reading it:**

1. **A rising win rate is not a rising expectancy.** Longer horizons raise `p` while the payoff
   ratio and the fee per round trip are untouched — and `p` is not the binding term
   ([[concepts/payoff-asymmetry]]). 35.4% is still far below the ~99% the derived bar demands.
2. **The 48-combo geometry search already found no surviving bracket**, with the *best* combo at
   **h=432** (mean −0.400%, lower bound −1.124%). The monotone ladder and that null are
   consistent: h432 is the least-bad cell of a grid with no positive cell.
3. **Shadow, and paper.** These are shadow win rates, sim-side of
   [[concepts/paper-real-boundary]], and the fill simulator is one-way optimistic. The h432
   cohort experiment holds to **n=50** regardless — no geometry change until it reads out.

**What would make this a real lead rather than a suggestive slope:** a gross-edge-by-horizon
read, which **cannot currently be computed** — `signal_history.csv` has no gross and no per-row
fee column ([[synthesis/owed-measurements]] item **50**). Until then the slope is a
**hypothesis with a mechanism**, not a measurement of edge.


## Related
[[sources/session-20260810-fill-double-count]] · [[concepts/paper-real-boundary]] ·
[[synthesis/owed-measurements]] · [[concepts/never-widen-a-gate]] ·
[[concepts/payoff-asymmetry]] · [[entities/config-guard]]
