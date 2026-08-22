# REG-6 pre-registered evidence: the crisis-window counterfactual

*Computed 2026-08-22. REPORT-ONLY — no engine, config, or decision-path file
was touched. Answers the criterion registered in
`docs/quant/2026-08-20_REG6_directional_crisis_prereg.md`; it does not decide.
Scripts were written under `/tmp/reg6/`, not the repo.*

---

## VERDICT UNDER THE PRE-REGISTERED RULE: **TIER 1 ONLY**

REG-6's criterion: *"crisis-window counterfactual win rate & net expectancy vs
baseline (Wilson intervals; n_eff not row count). Below baseline -> the block
is EARNING its keep; take Tier 1 only. Above baseline with net > 0 after the
cost stack -> Tier 2."*

**The crisis-window uplift does not survive an admissible baseline, and it does
not survive n_eff.** Against the repo's own era-hygiene convention (never
compare across label eras) the separation is +16.1pp and *not significant*; against
a time-matched control from the same rally it is **+0.7pp**; and against the
subgroup REG-6 actually proposes to trade (crisis_up longs) the crisis stamp
**underperforms its matched control by −14.2pp**. Tier 2's precondition
("above baseline") is not met.

| headline number | value |
|---|---|
| crisis-window win rate | **61.3%** (910 / 1,485) |
| Wilson 95%, **nominal** n=1,485 | [58.8%, 63.7%] |
| Wilson 95%, **effective** n=11.9 | **[34.3%, 82.8%]** |
| nominal n / effective n | 1,485 / **11.89** (mean uniqueness 0.0080, SE inflation **11.2x**) |
| separation vs repo blank-disp baseline (26.5%) | +34.7pp — **inadmissible, era-mixed** |
| separation vs like-for-like baseline (45.1%) | +16.1pp, z_eff +0.81, p~0.42 — n.s. |
| separation vs time-matched rally control (60.6%) | **+0.7pp**, z_eff +0.03, p~0.98 |
| net expectancy, crisis window, at measured cost | **+0.10 %/trade**, t_eff **+0.14** |

**Tier 3 is unreachable by construction.** REG-6 requires a *second independent
crisis-up window (n >= 30)*. The corpus contains **zero** crisis-stamped rows
before 2026-08-20 00:50Z; all 1,485 lie in one continuous 55-hour episode
across 14 assets. There is exactly one event. No numeric result in this
document could reach Tier 3, and none is offered toward it.

---

## 1. Method, and where it comes from

- **Wilson intervals**: `wilson()` transcribed verbatim from
  `scripts/gate_efficacy_report.py` (identical to `scripts/cohort_eval.py:130`).
- **Baseline / separation semantics**: `gate_efficacy_report.efficacy()` —
  `separation = cohort rate − baseline rate`, intervals disjoint = significant.
- **Effective n**: the concurrency math of `scripts/cohort_eval.py:484
  cohort_effective_n()` — a row's average uniqueness is the time-weighted mean
  of `1/c(t)` over its own label span, `n_eff` is their sum, SE scales as
  `1/sqrt(n_eff)`. Label span = `[signal_ts, ts]` (registration -> label write).
- **Cost**: `scripts/cost_truth_report.py`, run 2026-08-22 (below). No fee
  figure is assumed; `scripts/cost_attribution.py` was deliberately **not**
  used — CLAUDE.md records its hard-coded 2026-08-07 schedule as a known
  inverted-safety instrument.

**Instrument check (the method's first rule).** The vectorized ESS was
cross-checked against the repo's own `cohort_effective_n()` on three random
subsamples of the crisis rows (m=40/80/150): agreement to |Δ| <= 5.3e-15. The
number below is the repo's own estimator, computed faster, not a new one.

**Corpus**: `outputs/signal_history.csv`, 14,464 rows / 14,118 candidates.
Crisis rows: 1,485, **all** `source=candidate`, **all** `label_era =
triple_barrier_h432`, signal window 2026-08-20 00:50Z -> 2026-08-22 07:50Z, 14
assets. Zero live rows — the SZ-021 block means none were traded, so there is
no admission-selection confound on the counterfactual.

---

## 2. Effective sample size — the number everything rests on

| estimate | spans used | n | n_eff | mean uniqueness | SE inflation |
|---|---|---:|---:|---:|---:|
| **pooled (repo convention)** | `[signal_ts, ts]` | 1,485 | **11.89** | 0.0080 | **11.17x** |
| upper bound: per-asset ESS, summed | `[signal_ts, ts]`, within asset | 1,485 | 171.33 | 0.1154 | 2.94x |
| lower bound: full 36h horizon windows | `[signal_ts, signal_ts+432 bars]` | 1,485 | 2.53 | 0.0017 | 24.24x |

The pooled figure is the repo's own convention (`cohort_effective_n` pools all
trips) and is the one quoted in the headline. The per-asset sum is an
**upper bound only**: it credits 14 assets as 14 independent price paths during
a market-wide melt-up in which they visibly moved together — the same event
that put all of them into crisis at once. The 36h-horizon figure is the lower
bound if every label ran its full vertical.

**Saturation is the tell.** ESS on a random 40-row subsample of the same window
is 8.88; on all 1,485 rows it is 11.89. Adding 1,445 rows bought ~3 units of
independent information. The corpus grew 13x since registration (110 -> 1,485
rows) and learned almost nothing new: **this is one episode sampled densely,
not many episodes.**

Mechanism, and it is not subtle: `regime/macro_regime.py:_ensemble_label` fires
crisis on `vol_percentile >= 95` **or** `turbulence >= 95`. Every crisis row
here carries `turbulence_pct` in {0.964, 0.972, 0.984} (>= the 95 threshold)
while median `vol_percentile` is 0.746 — **far below it**. The stamp came from
the cross-asset turbulence scalar: one market-wide number, three distinct
values over three days, applied to 14 assets x 559 signal timestamps. The
crisis strata is a shared switch, which is precisely why row count and
information content diverge by 125x.

---

## 3. Win rate vs baseline — and which baseline is admissible

| cohort | n | n_eff | win rate | Wilson (nominal) | Wilson (on n_eff) |
|---|---:|---:|---:|---|---|
| **crisis candidates** | 1,485 | 11.89 | **61.3%** | [58.8%, 63.7%] | **[34.3%, 82.8%]** |
| B1 blank-disp baseline (repo default, **all eras**) | 2,061 | — | 26.5% | [24.7%, 28.5%] | — |
| B1b all non-crisis candidates (all eras) | 12,633 | — | 26.4% | [25.6%, 27.1%] | — |
| **B2 like-for-like: non-crisis, `triple_barrier_h432`** | 2,654 | 12.56 | **45.1%** | [43.3%, 47.0%] | [22.2%, 70.4%] |
| **B3 time-matched: B2 restricted to signal >= 08-18** | 1,572 | 7.03 | **60.6%** | [58.2%, 63.0%] | [27.6%, 86.2%] |
| B3b tighter: B2 restricted to signal >= 08-19 | 950 | — | 67.6% | [64.5%, 70.5%] | — |

| separation | value | z on n_eff | p |
|---|---:|---:|---:|
| crisis − B1 (blank-disp, era-mixed) | +34.7pp | +2.45 | 0.014 |
| crisis − B1b (all non-crisis, era-mixed) | +34.9pp | +2.47 | 0.013 |
| crisis − B2 (like-for-like era) | +16.1pp | +0.81 | 0.42 |
| crisis − B3 (time-matched rally) | **+0.7pp** | +0.03 | 0.98 |

**B1 is not an admissible baseline here and the +34.7pp headline should not be
quoted.** The crisis cohort is 100% `triple_barrier_h432`; B1 is a mixture of
five label eras with different horizons and different labelers
(`triple_barrier` 5,290 / `h432` 4,139 / `exit_sim` 2,496 / `legacy` 1,734 /
`exit_sim_time_stop` 459). The repo built the whole `label_era` machinery
(`ml/history.py:249-400`) and the era-exclusion rule to forbid exactly this
comparison. Mechanically: the crisis window contains **1** vertical-barrier
(`tb_time`) resolution out of 1,485, while B1's eras carry thousands of
`tb_time` / `sl` / `time_stop` rows that label near-0 by construction — a
vertical tape resolves every barrier fast, so the crisis cohort is a
*decisive-outcome* sample compared against a *mixed* one. Most of the +34.7pp
is that artifact.

Against the two admissible baselines the effect is +16.1pp (not significant on
n_eff) and **+0.7pp (nothing)**.

---

## 4. Cost stack — measured, not assumed

`scripts/cost_truth_report.py`, run 2026-08-22:

- configured `pretrade.maker_fee_bps=25` / `taker_fee_bps=40` -> round-trip
  assumption **65.0 bps**.
- measured round-trip from 281 unique postmortem trades: mean overrun
  **+1.76 bps** -> **66.76 bps**, +2.7% vs configured, **within** spec-D4's
  +/-20% tolerance [XV-031].
- OM-080 venue fee reconciliation: **n=0 records**. No independent venue
  measurement of the fee tier exists. Absence is not agreement.
- The postmortem source is the *underperforming subset* (only triggered
  postmortems), never a population average. Both caveats are the script's own.

**The labels are already net of cost.** `ml/labeling.py:triple_barrier` labels
`1` only when `ret − cost_pct > 0`, and the candidate labeler's `_cost_pct`
charges `ml.label_round_trip_cost_pct = 0.50%` plus the asset's own spread
capped at `label_spread_cap_bps = 60` — mean charged cost on the crisis rows is
**0.508%**. Barriers are cost-floored at `label_pt_cost_mult = 4.0`, so
PT >= 2.0% by construction. So 61.3% is already a net-of-cost win rate; it is
not a gross hit rate awaiting a haircut.

**Cost stress.** The label charges 50 bps of fee where the measured round trip
is 66.76 bps. Re-pricing every row at the measured figure:

| cohort | n | E[net]/trade @0.50% | E[net]/trade @0.6676% | SE on n_eff | t_eff |
|---|---:|---:|---:|---:|---:|
| crisis, all | 1,484 | +0.268% | **+0.101%** | 0.741 | **+0.14** |
| crisis_up longs (REG-6 Tier 2/3 target) | 1,022 | +1.067% | **+0.899%** | 0.713 | **+1.26** |
| crisis, everything else | 462 | −1.499% | −1.667% | 0.563 | −2.66 |
| B2 like-for-like non-crisis | 2,653 | −0.282% | −0.449% | — | −0.49 |
| B3 time-matched rally control | 1,571 | +0.161% | −0.006% | — | +0.21 |

Zero labels flip under the stressed cost (0 of 909 `tb_pt` wins; the 2% cost
floor is 3x the round trip), so the *win rate* is cost-robust — but
**expectancy is not distinguishable from zero on effective n**: t_eff = +0.14
for the crisis window, +1.26 for crisis_up longs. REG-6's Tier 2 clause
requires "above baseline **with net > 0** after the cost stack". The point
estimate is positive; the evidence for it is not.

---

## 5. Stratification — is it broad, or is it the tape?

**By direction (crisis rows).** longs 79.6% (n=1,126) vs shorts 3.9% (n=359).
Everything the crisis window "earned" is the long side of a melt-up.

**By REG-6's own proposed split (`crisis_up` = mom_dir >= 0).**

| subgroup | n | n_eff | win rate | nominal 95% | on-n_eff 95% |
|---|---:|---:|---:|---|---|
| crisis_up, longs | 1,023 | 10.83 | 78.4% | [75.8%, 80.8%] | [48.6%, 93.3%] |
| crisis_up, shorts | 43 | 7.17 | 0.0% | [0.0%, 8.2%] | [0.0%, 34.9%] |
| **crisis_down, longs** | 103 | 8.78 | **91.3%** | [84.2%, 95.3%] | [58.7%, 98.7%] |
| crisis_down, shorts | 316 | 12.80 | 4.4% | [2.7%, 7.3%] | [0.5%, 29.4%] |

**This falsifies the discriminator REG-6 proposes.** Longs stamped
`crisis_down` won *more* (91.3%) than longs stamped `crisis_up` (78.4%). The
momentum sign at classification time separates nothing; **being long in a
rising tape** does all the work, and the tape kept rising through both momentum
states. A split built on `mom_dir` would not have selected the winners.

**Against the matched control — the decisive cut.**

| | n | win rate |
|---|---:|---:|
| crisis_up LONGS (what Tier 3 would permit) | 1,023 | 78.4% |
| non-crisis h432 LONGS, same rally window (>= 08-18) | 1,020 | **92.5%** |
| separation | | **−14.2pp** (z_eff −0.88) |

Candidates the crisis stamp blocked did **worse** than comparable long
candidates the bot was free to take in the same tape. Under REG-6's own words —
*"below baseline -> the block is EARNING its keep"* — this reads as the block
earning its keep, not costing money. (The separation is itself not significant
on n_eff; the honest statement is that no uplift is demonstrated, not that a
penalty is.)

**By asset** (crisis, all): ARB 64.0% (261), PAXG 77.8% (153), ETH 52.7% (146),
MINA 61.4% (145), SUI 63.2% (144), BTC 50.0% (102), XRP 54.9% (102), DOGE 51.7%
(89), ADA 62.1% (66), AVAX 53.0% (66), FLOW 59.6% (57), DOT 76.4% (55), SOL
71.7% (53), LINK 52.2% (46). Broad, not one-asset-driven — but every asset is
in the *same* 55-hour window, so 14 consistent readings are 14 views of one
event, not 14 replications. Note PAXG (gold) at 77.8% with n_eff = 2.2, and
100% on crisis_up longs — a supposed risk-off asset winning inside a crypto
melt-up is a composition marker, not a signal.

**By turbulence band** (the trigger variable — only three distinct values
exist): 0.964 -> 65.0% (n=565), 0.972 -> 53.5% (n=172), 0.984 -> 60.3%
(n=748). No monotone dose-response in the variable that *caused* the stamp.

**By `vol_percentile` quartile**: 74.0% / 64.5% / 56.7% / 49.7% — win rate falls
**monotonically as volatility rises**, i.e. as the row looks more like the
crisis the playbook was written for. The uplift lives in the *low*-vol rows
that got swept in by the shared turbulence scalar.

**By day**: 08-20 65.0% (565) -> 08-21 59.8% (734) -> 08-22 55.9% (186), decaying
toward the ordinary base rate as the melt-up cools.

---

## 6. The single biggest caveat

**The uplift is compositional: it measures the melt-up, not the crisis label.**
The pre-crisis rally days carry the same win rates with no crisis stamp
anywhere — non-crisis h432 candidates ran 50.0% on 08-18 and **67.4% on 08-19**,
against a corpus base rate of 26.4%. The crisis window's 61.3% sits *inside*
that band and slightly *below* its neighbours. Every knife-edge cut points the
same way: matched non-crisis longs beat crisis_up longs; `crisis_down` longs beat
`crisis_up` longs; the win rate declines as `vol_percentile` rises and as the
episode ages. A regime label that fires off one shared cross-asset scalar,
inside one 55-hour rally, on candidates whose labels overlap so heavily that
1,485 rows carry ~12 rows' worth of independent information, cannot distinguish
"crisis was wrong" from "everything was a winner that week." **The corpus is
consistent with the crisis block being harmless-to-mildly-helpful in this
episode, and it is equally consistent with it being useless. It is not
consistent with a demonstrated edge.**

Secondary, and worth naming: this evidence cannot speak to the fill geometry
REG-6 itself flags. The counterfactual labels price a bracket bet from
`signal_ts`; a Tier 3 limit-only long in vertical tape fills on retraces or not
at all. Nothing here measures the fill rate of the orders Tier 3 would place.

---

## 7. What the pre-registered rule therefore returns

- **Tier 1 (semantic split only, playbooks unchanged)** — supported. The defect
  REG-6 names is real and is a *semantics* defect: a melt-up inherited a crash
  playbook, and the label carried no direction term. Splitting the word fixes
  the strata and the taxonomy at zero behavior change. This evidence neither
  supports nor is needed for it.
- **Tier 2 (crisis_up exploration probes)** — **not supported.** Its
  precondition ("above baseline") fails against both admissible baselines, and
  its second condition ("net > 0 after the cost stack") is a point estimate with
  t_eff = +0.14 (all-crisis) / +1.26 (crisis_up longs). On the repo's own
  n_eff standard this is not evidence.
- **Tier 3 (crisis_up real entries)** — **unreachable by construction.** One
  episode. REG-6 requires a second independent crisis-up window of n >= 30; the
  corpus contains zero crisis rows before 2026-08-20. Per the operator's own
  rule, one event never decides — and this is one event however the numbers
  had landed.

If a second crisis-up episode ever accrues, the honest re-run is this document
with a **time-matched control** as the primary baseline (B3), not the era-mixed
blank-disp default — and with n_eff, which after two independent episodes will
still be closer to 25 than to 3,000.

*No floor was moved, no gate widened, no threshold tuned. `SG_MIN_ROWS`, the
overfit row floor, and the era-4 n=50 are untouched. Any tier is
cohort-resetting (new execution era, accrual restart) and remains an operator
adjudication.*
