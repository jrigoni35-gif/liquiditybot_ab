# Walk-forward tranche 2 — resampling the era-4 cohort without assuming independence

*Operator request 2026-08-22: "copious backtest and walk-forwards, as many
relevant formulas as improve this code in the most edge-fulfilling ways."
Tranche 1 (`2026-08-22_gate_power_analysis_mintrl.md`) applied PSR/MinTRL
in closed form. This tranche re-asks the same questions with methods that
do not assume iid returns, and adds the one the closed forms cannot state:
**how much cost can this edge carry?** New instrument:
`scripts/walkforward_lab.py` (report-only, SAFE, deterministic, wired into
`learning_panel`). It decides nothing and does not move `MIN_COHORT_N`.*

## The headline is a CORRECTION of tranche 1

Tranche 1 reported the gross edge as **settled** — MinTRL(95%) = 10 against
a cohort of 33 — and flagged in its caveats that this used nominal n. That
caveat is now measured, and it is not a footnote:

```
cohort carries n=33 trips but n_eff=9.92 trips' worth of information
  anchor                     SR   MinTRL(95%)   vs n   vs n_eff
  gross                  +0.4339      9.94      YES     NO   (margin -0.02)
  configured 25/40       +0.1876     62.09       no     NO   (margin  -52.17)
  T1 both-maker 40/40    +0.0401   1602.69       no     NO
  T1 maker-in/taker-out  -0.0204      never      no     NO
```

**The gross leg sits exactly ON its own power requirement.** 9.92 available
against 9.94 required is a margin of −0.02 — noise in both directions.
The honest statement is not "the edge failed" and not "the edge is
established": it is **precisely undetermined**. Tranche 1's claim that the
gross edge is answered rested on counting 33 observations that carry ten
observations' worth of information, and it does not survive here.

A nominal-n reading has been wrong here before — which is exactly why
`gate_truth_report` has carried the effective-n standard since 2026-07-29,
`cohort_eval` since 2026-08-15, `gate_efficacy_report` since `c4e4a599`
(today), and why the crisis-block audit reported n_eff **11.89** against a
nominal 1,485. Tranche 1 was written outside all of them and reproduced the
error they exist to prevent.

## Method, and why each piece

| § | method | why not the closed form |
|---|---|---|
| WF-1 | autocorrelation + Bartlett band; average-uniqueness effective n | two DIFFERENT dependences (sequential, concurrent); reporting one number for both double-counts |
| WF-2 | stationary bootstrap, Politis–Romano 1994, block length swept 1/2/3/5 + Politis–White 2004 automatic pick | returns are skewed +1.25, kurtosis 4.51; a normal SE is the wrong shape |
| WF-3 | iid bootstrap (b=1, the exact degenerate case of WF-2) | controlled contrast — the width gap IS the cost of assuming independence |
| WF-2b | bootstrap SE inflated by √(n/n_eff), re-formed as a normal interval | the bootstrap cannot see concurrency; overlapping trips are separate rows however you resample |
| WF-4 | deflated Sharpe across a trial grid, at nominal AND effective n | trials count is unmeasured here — the grid is the answer |
| WF-4b | MinTRL against both sample sizes | the comparison must not be makeable in only the flattering direction |
| WF-5 | cost-tolerance solve | the fee question stated as bps a venue table can be read against |
| WF-6 | anchored walk-forward inside the cohort | expectancy stability, pre-registered before readout |

## WF-1 — the two dependences, separated

```
autocorr(net) lags 1..10: +0.18 -0.06 +0.13 -0.04 -0.10 +0.13 -0.03 -0.15 -0.16 +0.03
Bartlett white-noise band +/-0.35  ->  NO lag resolvable at this n
concurrency: effective_n=9.92 of 33 (mean uniqueness 0.301, SE inflated x1.82)
```

**Sequential dependence is not detectable and is not the problem.**
Every lag sits inside the ±0.35 white-noise band, and the Politis–White
selector accordingly returns an expected block length of **1.3** — barely
distinguishable from iid. The block bootstrap was the obvious tool and it
turns out not to be the binding constraint.

**Concurrency is.** Mean uniqueness 0.301: the average trip shares ~70% of
its life with another open trip. That is the deflation that matters, and it
is the one the block bootstrap structurally cannot see.

## WF-2/2b/3 — intervals

| anchor | mean/trip | 95% CI (stationary bootstrap) | P(mean ≤ 0) | CI widened for concurrency |
|---|---:|---|---:|---|
| **GROSS** | +1.1820% | [+0.328%, +2.147%] | 0.0022 | **[−0.540%, +2.904%]** |
| configured 25/40 | +0.5117% | [−0.345%, +1.476%] | 0.134 | [−1.213%, +2.236%] |
| T1 both-maker | +0.1094% | [−0.746%, +1.074%] | 0.421 | [−1.615%, +1.834%] |
| T1 maker-in/taker-out | **−0.0556%** | [−0.912%, +0.909%] | 0.561 | [−1.780%, +1.669%] |

Two readings, both load-bearing:

1. **Block length changes almost nothing** (b=1 → b=5 moves the lower bound
   by ~0.15pp). The sweep is reported rather than a single pick precisely so
   this insensitivity is visible instead of hidden inside an automatic
   choice.
2. **Concurrency changes everything.** Once the SE carries ×1.82, even the
   GROSS interval crosses zero. At n=33 with 30% uniqueness, this cohort
   cannot yet distinguish its own pre-fee edge from nothing.

The maker-in/taker-out mean reproduces tranche 1's **−0.0556%** to four
decimals from an independently written code path. (Tranche 1 printed the
multiplier as "×1.85"; the exact ratio 120/65 = 1.84615 is what both used.)

### A corroboration this memo has to walk back

Tranche 1 wrote that its reconstructed **67.04 bps** round-trip
"independently confirms `cost_truth_report`'s measured **66.76 bps** — the
two routes agree, so the fee arithmetic rests on measurement." **The
agreement is real; the word "independently" is not.**

`cost_truth_report` derives its figure as *configured 65.00 bps + mean
postmortem overrun 1.76 bps*, over 281 lifetime postmortem-triggered
trades. The 67.04 figure is booked fees over 33 era-4 trips — and in
DRY_RUN those fees are **booked from the same configured 25/40 stack**.
Different populations, different arithmetic, one shared anchor. What their
agreement establishes is that **fee booking matches fee configuration**;
it establishes nothing about whether 65 bps is what the venue charges.

That is FEE-1 restated from a third direction, and it is the loop-alignment
audit's central finding arriving as a near-miss: two routes agreeing inside
a loop that shares one wrong constant is exactly the observation that reads
as confirmation and is not one. Re-run `cost_truth_report` and note its own
first section: **`[1] OM-080 has never fired, n_records=0`** — the venue
leg of this measurement does not exist yet.

## WF-5 — cost tolerance, the new number

```
booked round-trip (this cohort)      67.04 bps
mean GROSS per trip                  +1.1820%
point-estimate breakeven cost       118.20 bps  (x1.76 booked)
bootstrap 95% lower-bound breakeven  43.44 bps  (x0.65 booked)
...widened for concurrency            0.00 bps  — the GROSS edge itself is
                                                  not distinguishable
  configured 25/40         67.04 bps -> positive but INDISTINGUISHABLE
  T1 both-maker 40/40     107.26 bps -> positive but INDISTINGUISHABLE
  T1 maker-in/taker-out   123.76 bps -> NEGATIVE expectancy
```

Because net(m) = gross − m·fee is linear in the multiplier, the crossing is
solved exactly on a fixed resample matrix rather than searched.

**What it says.** In point estimate the strategy carries **118 bps** of
round-trip cost — comfortably above every anchor except maker-in/taker-out.
Demand statistical distinguishability instead and the tolerance collapses to
**43 bps**, which is *below the cost the cohort already booked*. Add
concurrency and there is no positive cost the edge demonstrably survives.

This is the same conclusion as tranche 1 arriving through a different door,
and it sharpens the pre-registered arm: not "the edge is dead" but **the
cohort cannot yet prove any tolerance at all**, and the point estimate that
looks comfortable is resting on ten trips' worth of information.

## WF-6 — anchored walk-forward

```
fold 1: IS n=8   -1.2058%  ->  OOS n=8   +1.1456%   SIGN FLIPS
fold 2: IS n=16  -0.0301%  ->  OOS n=9   +0.6411%   SIGN FLIPS
fold 3: IS n=25  +0.2115%  ->  OOS n=8   +1.4496%   sign holds
pooled OOS +1.0613% (n=25) vs full-sample +0.5117%; sign agreement 1/3
```

OOS *exceeds* IS in all three folds. That is not skill and must not be read
as generalisation: the cohort is time-ordered, so the later folds contain
the 08-20 melt-up window whose base rate was 0.613 against 0.262 elsewhere
— an operator-adjudicated outlier. **The walk-forward is measuring regime
composition, not out-of-sample durability**, and at 8-trip folds it could
not resolve durability even without that confound. Filed pre-readout so the
shape is on the record before anyone is tempted to read it after.

## WF-4 — deflated Sharpe, and an unmeasurable input

At one trial, DSR is PSR: gross 0.9991 nominal, **0.9505 on effective n** —
again exactly at the conventional line. At 25 trials the SR0 threshold rises
to +0.867 and every anchor collapses.

But the trial count is **not measured anywhere in this repo**, and neither
is the across-trial SR dispersion the deflation scales by (`deflated_sharpe`
falls back to var = SR², an assumption). Picking a trial count would be
inventing evidence, so the grid is printed and the gap is named:

> **New docket item, TRIALS-1 (SAFE):** there is no ledger of how many
> strategy configurations were evaluated before the deployed one. Without
> it, DSR cannot be computed for this strategy — only tabulated against
> hypotheses about N. A trials ledger is cheap and purely additive.

## What changes, and what does not

**Does not change:** any engine path, any threshold, `MIN_COHORT_N`, the
pre-registered era-4 population, or the readout arms. Nothing here is
cohort-resetting; the instrument reads `fills.csv` and prints.

**Changes:**

1. **Tranche 1's "gross edge is established" is withdrawn.** The correct
   statement is *undetermined on effective n*. The memo stays on file with
   this correction noted; it is not deleted, because the closed forms in it
   are right and only the sample-size basis was wrong.
2. **FEE-3 keeps its priority but loses its exclusivity.** Knowing the true
   tier still discriminates the worlds — but at 43 bps of demonstrable
   tolerance, *no* anchor is cleanly survivable, so the fee call cannot by
   itself produce a CONTINUE.
3. **Effective n belongs on every cohort statistic, not some.** Two of the
   four routes now carry it (`gate_truth_report`, `cohort_eval`, and
   `gate_efficacy_report` as of `c4e4a599`). `cost_truth_report`,
   `fill_hazard_report`, and `corpus_linkage_report` still do not.
4. **A concurrency question is now on the docket, and it is not a
   measurement question.** Mean uniqueness 0.301 means this cohort buys
   information at roughly a third of nominal rate. That is a property of how
   many positions run concurrently — a SIZING/CONCURRENCY decision, hence
   **cohort-resetting and inadmissible before readout**. Logged as
   **CONC-1** for boundary #6, not proposed now.

## Caveats — all of them cut against the flattering reading

- The concurrency-deflated intervals (WF-2b, WF-5) are a **normal-SE
  approximation** that assumes the two deflations compose independently.
  They always widen, never narrow, so the error is conservative — but the
  exact rows are the raw percentile ones.
- Effective n is average-uniqueness (AFML ch.4). It is one estimator among
  several; a different one would move 9.92, though not to 33.
- The T1 anchors rescale a **booked** fee by Kraken's **published** bottom
  tier. This account's tier remains unverified (FEE-3).
- DRY_RUN fees are simulated: this measures whether the modelled strategy
  survives live cost, not realised P&L.
- n=33 of a pre-registered 50. Everything above is a statement about an
  **incomplete** cohort and none of it is a verdict.

## Re-run

`python scripts/walkforward_lab.py` (also runs inside
`scripts/learning_panel.py`). Deterministic under the default seed; pinned
by `tests/test_walkforward_lab.py`, which asserts identities rather than
values so the pins do not rot as fills accrue.
