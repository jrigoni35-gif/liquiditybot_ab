# Turbulence instrument verification — `corr.state.turbulence_pct`

**Date:** 2026-08-22
**Scope:** REPORT-ONLY. No engine, config, `regime/`, `risk/`, `execution/` or
`ml/` file was modified. All harness code lives under `/tmp/turb/`.
**Trigger:** on 2026-08-22 every asset in the live universe was classified
`macro=crisis` (`allow_new: False`, `regime/macro_regime.py:53`), sidelining
the book feed-wide for 24h+ and stalling the era-4 cohort accrual. Standing law
(CLAUDE.md, "the instrument is the first suspect") says verify the instrument
before building a theory on its output.

---

## VERDICT

**DEFECTIVE AS DEPLOYED.**

Split the claim precisely, because the two halves have different answers:

* The **estimator** is a faithful Kritzman-Li (2010) financial-turbulence
  implementation. Timestamp-joined, forming-bar-excluded, shrunk covariance,
  full 250-return window in production, rank fidelity vs. an oracle that knows
  the true population Sigma = **Spearman +0.970**. It is not fabricating a
  number, and its current elevated reading is corroborated by a second,
  independent instrument (below). As an estimator of Kritzman-Li turbulence:
  **SOUND**.
* The **instrument as wired into the decision** — this statistic, against this
  threshold, broadcast to every asset — is **DEFECTIVE**. It fires on ~5% of
  days in a market containing no crises at all; it reads a coordinated
  market-wide crash as calm and a zero-net-move decorrelation as maximum
  crisis; and it converts one asset's idiosyncratic move into a feed-wide
  entry blackout. Defects D1–D4 below are decision-path defects with measured
  evidence, not stylistic objections.

The 2026-08-22 blackout is **not** an instrument fabrication. It is the
instrument doing exactly what it was built to do, applied to a decision it does
not support.

---

## 1. The computation, as found

Call chain, hourly:

```
main.py:6277   self.corr.update_turbulence(self.daily_candles)
main.py:6279   for asset in self.symbol_map:
main.py:6280       self.macro.update(asset, ..., self.corr.state.turbulence_pct)
regime/macro_regime.py:441-442
               if st.vol_percentile >= self.crisis_vol_pct or \
                  (turbulence_pct is not None and turbulence_pct >= self.crisis_vol_pct):
                      return "crisis"
regime/macro_regime.py:424   crisis bypasses the hysteresis confirm count
regime/macro_regime.py:53    crisis playbook -> allow_new: False
```

`regime/correlation.py:258-338`, step by step:

| Step | Line | What it does |
|---|---|---|
| Drop forming bar | `:276-283` | per asset, `candles[:-1]`; requires `len(candles) >= 61`, `len(by_ts) >= 60` |
| Day lattice | `:296-309` | median inter-bar step per series, then bucket `round(t / step)` — a *rounded* bucket, not an exact join |
| Intersection | `:310-316` | `shared` = buckets present for **every** asset; floor `len(shared) < 41` |
| Window | `:317` | `days = shared[-(turb_lookback + 1):]`, `turbulence_lookback_days = 250` (`config.json:305`) |
| Returns | `:318-322` | `R` = log returns, shape `(len(days)-1, A)`; floor `R.shape[0] < 40` (`:323`) |
| Covariance | `:325-327` | `np.cov(R)` over the **same** window, + 5% diagonal shrinkage (hardcoded `0.05`) |
| Statistic | `:332-333` | `d_i = (r_i - mu)' Sigma^-1 (r_i - mu)`; `turbulence = d[-1]` |
| Percentile | `:334` | `turbulence_pct = (d < d[-1]).mean() * 100` |

Three properties follow directly and are the root of everything below:

1. **`turbulence_pct` is a rank, not a level.** It is the position of today's
   Mahalanobis distance inside its own trailing window. `mu` and `Sigma` are
   estimated **in-sample over that same window**, including today.
2. **The window is rolling (250 returns), never growing.** So the statistic is
   scale-free: it cannot say "this year was calm." Whatever the year was, ~5%
   of its days sit above the 95th percentile of that year.
3. **`d` is one scalar per day, for the whole cross-section.** There is no
   per-asset decomposition and none is computed. `main.py:6280` broadcasts the
   identical scalar into all N per-asset macro regimes.

Percentile basis and warm-up: the denominator is `len(d)` = number of returns
in the window. In the live corpus every observed value is an exact multiple of
0.004 = 1/250, so **production has been running the fully warm 250-return
window throughout the recorded history** — the current incident is not a
warm-up artifact. The code nonetheless permits a 40-return window
(`:312`, `:323`); see D8.

---

## 2. Empirical distribution — real corpus

`outputs/signal_history.csv`, 14,464 rows, `signal_ts` 2026-07-13T12:35Z →
2026-08-22T07:50Z. Note the column is the **ML-scaled** feature
(`turb_pct / 100.0`, `ml/features.py:391`; range pinned `(0, 1)` in
`ml/contracts.py:48`), so 0.972 = p97.2.

```
quantiles   p0 0.000  p5 0.004  p25 0.048  p50 0.270  p75 0.612
            p90 0.964  p95 0.984  p99 0.984  max 0.984
distinct values 181, all multiples of 0.004 (= 1/250)  -> window n = 250 always
frac >= 0.95 : 10.27 %      frac >= 0.99 : 0.00 %
```

* **Not pinned at a ceiling in the pathological sense**, but saturated at the
  top: the observed maximum is 0.984 (= 246/250) and 5.2% of all rows sit
  exactly there. Above p95 the statistic has ~3 distinguishable states, so
  "mildly unusual" and "worst day of the year" are the same reading to the
  consumer.
* **Not noisy.** Collapsed to one value per cycle (6,811 distinct `signal_ts`),
  lag-1 autocorrelation is **+0.988**, with 712 changes and a median 0.75h
  between changes — consistent with an hourly recompute of a daily statistic.
  This is *not* the `manip_suspect` failure mode (rho = +0.007); a single read
  here is a legitimate read.
* **The ≥0.95 condition is reachable in ordinary conditions, by construction.**
  10.27% of live rows cleared it. See D1 for the synthetic control.

**Unexplained instrument instability, 07-13 → 08-02 (open item).** A daily
statistic recomputed hourly should be piecewise constant across a day. In the
July segment it was not: median **intraday range 0.482**, up to 50 direction
reversals per day, 20–36 distinct values in a single UTC day (e.g. 2026-07-25
traversed 0.000 → 0.524 → 0.348 → 0.868 within the day). From ~2026-08-03
onward it settles to 1–4 distinct values per day, which is what the design
predicts. Git history is squashed (`1fee174e` is the only commit touching
`regime/correlation.py`), so this could not be attributed to a code change.
**Flagged, not explained.** It does not affect the current incident — on 08-21
the value held 0.984 all day and moved to 0.972 at 00:25 on 08-22 — but any
future read of the July-era `turbulence_pct` feature column should be treated
as suspect.

### Second route (corroboration, not the same instrument)

Per-asset intraday `vol_percentile` from `outputs/signal_history.csv`, prior
week vs incident window:

| asset | own vol_pct 08-12→08-20 | own vol_pct 08-20→now | crisis flag % (incident) |
|---|---|---|---|
| XRP | 0.079 | **0.925** | 98.1 |
| ADA | 0.199 | **0.915** | 91.7 |
| SUI | 0.043 | **0.854** | 97.3 |
| BTC | 0.100 | **0.870** | 95.3 |
| ETH | 0.107 | **0.803** | 91.8 |
| MINA | 0.015 | **0.717** | 91.8 |
| FLOW | 0.166 | 0.453 | 96.6 |
| DOT | 0.138 | 0.471 | 96.5 |
| **PAXG** | **0.535** | **0.519** | **92.2** |

`regime_crisis` one-hot: 0.0% of rows the prior week → 93.8% during the
incident. So: **the market genuinely did get more volatile** — an independent
instrument agrees, which is why this is not scored as fabrication. And
**PAXG's own volatility percentile did not move at all** (0.535 → 0.519) while
it carried the crisis flag on 92.2% of its rows. That is D3, measured on the
live corpus.

---

## 3. Injection tests against the real `CorrelationEngine`

Harness: `/tmp/turb/inject.py`, `/tmp/turb/inject2.py`, `/tmp/turb/inject3.py`.
Each imports the shipped `regime.correlation.CorrelationEngine` and feeds it
synthetic candle dicts with known ground truth. Nothing in the repo is touched.

**D1 — unconditional firing rate on a market with no crises in it.**
Stationary correlated Gaussian returns, 12 assets, rho 0.6, constant vol, no
fat tails, no clustering, no regime change of any kind:

```
window n=250 : P(turbulence_pct >= 95) = 7.00 %   (21/300 draws)
window n=120 : P(turbulence_pct >= 95) = 4.33 %
window n= 60 : P(turbulence_pct >= 95) = 4.00 %
```

~5% is the *designed* answer for a rank threshold at the 95th percentile of its
own window. It is not a bug in the arithmetic; it is what "rank >= 95th
percentile" means. But it is wired to `allow_new: False` feed-wide with no
hysteresis (`regime/macro_regime.py:424`), so **the deployed configuration
carries a built-in ~5% duty cycle of total book sidelining in a market that is
doing nothing at all.** The live corpus shows 10.3%, consistent with ~5%
baseline plus genuine volatility clustering.

**D2 — the statistic measures atypicality of the co-movement *pattern*, not
stress.** Final-day shock injected into an otherwise stationary market:

```
ALL 12 assets crash -3 sigma TOGETHER          pct median  80.0   fires   0.0 %
ALL 12 assets crash -5 sigma TOGETHER          pct median  99.6   fires 100.0 %
6 up +2s / 6 down -2s, ZERO net market move    pct median  99.6   fires 100.0 %
ONE asset +3 sigma, other 11 exactly flat      pct median  93.6   fires  34.5 %
ALL 12 assets exactly flat (dead calm)         pct median   0.0   fires   0.0 %
```

A broad correlated selloff — the thing an operator means by "crisis" — reads
**80.0 and never fires**, because a common move is *typical* under the fitted
Sigma. A zero-net-move decorrelation reads **99.6 and always fires**. This is
Kritzman-Li behaving exactly as designed; the defect is that
`regime/macro_regime.py:441` consumes it as if it meant "the market is
stressed, stop taking risk."

**D3 — one asset's idiosyncratic move blacks out the whole book.**

```
1 of 12 assets moves  3 sigma, other 11 EXACTLY 0.00 %  -> pct median 93.6, fires  26.7 %
1 of 12 assets moves  5 sigma, other 11 EXACTLY 0.00 %  -> pct median 99.6, fires 100.0 %
```

Combined with the broadcast at `main.py:6280`, a single asset decoupling sets
`macro=crisis` on **every** asset, including the eleven that did not move. That
is the PAXG observation reproduced in a controlled setting, and it matches the
live corpus (PAXG own-vol unchanged, crisis flag 92.2%).

**D4 — asset-set instability.** Drop one asset's daily feed (the routine
"one venue 404'd this hour" case; `main.py:6255-6272` silently falls back and
keeps the previous candle list when all three venues return nothing):

```
|delta turbulence_pct| : median 4.8, p90 12.0, max 58.8 percentile points
crisis verdict FLIPS on the missing feed alone : 2.5 % of draws
```

The asset set, the covariance dimension, and the shared-day lattice are all
re-derived from whatever the feeds happened to return this hour. Nothing
asserts continuity, nothing logs the asset set or the realised `n`.

---

## 4. Config lift and guard coverage

| knob | lifted? | guarded? |
|---|---|---|
| `regime.crisis_vol_pct` = 95 | yes, `config.json:259` | **NO** — zero occurrences in `core/config_guard.py` |
| `correlation.turbulence_lookback_days` = 250 | yes, `config.json:305` | **NO** |
| `correlation.lambda_fast/lambda_slow/shift_threshold` | yes, `config.json:302-304` | **NO** — the entire `correlation` block is unguarded |

Verified by `grep -n "crisis_vol_pct\|turbulence\|correlation\." core/config_guard.py`
→ no matches. `config_guard` does bound the neighbouring
`regime.momentum_bear_max` / `regime.momentum_bull_min` and all of
`vol_regime.*`, so the omission is a gap, not a policy.

**Hardcoded literals remaining in the decision path** (`regime/correlation.py`):

* `:276` `len(candles) < 61` — per-asset minimum candle count
* `:284` `len(by_ts) >= 60` — per-asset minimum distinct days
* `:312` `len(shared) < 41` — minimum shared days
* `:323` `R.shape[0] < 40` — minimum returns
* `:327` `* 0.05` — covariance shrinkage intensity
* `:335` `>= 95` — **a second, independent copy of the crisis threshold**, used
  for the only operator-visible warning. It is not read from
  `regime.crisis_vol_pct`, so changing that config value silently desynchronises
  the log from the decision.

None of these are fitted-looking in the "peak of a backtest" sense; they are
round structural floors. But per CLAUDE.md overfit discipline they are knobs in
a decision path with no config key and no guard, and `:335` is a duplicated
threshold, which is the classic drift source.

---

## 5. Remaining defects

**D5 — semantic conflation at the comparison site.**
`regime/macro_regime.py:441-442` applies the *same* constant `crisis_vol_pct`
to two statistics that share nothing but a percentile scale:
`st.vol_percentile` (per-asset daily Parkinson vol rank, `:389`) and
`turbulence_pct` (cross-asset Mahalanobis rank). Different distributions,
different meanings, different appropriate cut points, one constant named after
only the first of them. There is no `crisis_turbulence_pct` key anywhere.

**D6 — silent stale-hold, no age, no reason code.** Five early returns hold the
previous reading indefinitely: `:287` (<2 usable assets), `:303` / `:307`
(no usable day step), `:316` (<41 shared days), `:324` (<40 returns). Only
`:313` logs, and at DEBUG. `CorrState` (`:30-46`) carries no `turbulence_ts`,
no sample count, no staleness flag, and there is no `VN-*`/`RP-*` code for a
held reading. A feed outage freezes the scalar — possibly frozen at a crisis
value — and nothing surfaces it. *Not the cause of the current incident*: the
value moved 0.948 → 0.984 → 0.972 across 08-21/08-22, so it is live.

**D7 — no operator-visible gauge.** `grep -rn "turbulence" core/ api/` returns
nothing. The scalar is absent from the `status.json` schema. The only surfaces
are the WARNING at `regime/correlation.py:336` and the ML feature column. The
number that sidelined the entire book is not on the board.

**D8 — the permitted minimum window is under-determined.** `:312`/`:323` allow
a 40-return window for an A-dimensional covariance (A = 15 in the live corpus,
7 in `config.json`'s `kraken.trading_pairs`). Measured rank fidelity against an
oracle with the true Sigma:

```
n=250 : spearman +0.970,  mean |err| 4.9 pctile pts
n=120 : spearman +0.942,  mean |err| 7.4 pctile pts
n= 60 : spearman +0.899,  mean |err| 9.8 pctile pts
```

At the floor, percentile granularity is ~2.4 points, so ">= 95" degrades to
"the single most unusual day of the last 42". Production is currently at n=250
(verified: all corpus values are multiples of 1/250), so this is latent.

**D9 — cross-venue day-window misalignment (measured, with an honest negative).**
`config.json` routes ETH and BTC to OKX (`exchanges.okx.symbols`), whose `1D`
bar opens 16:00 UTC, while the remaining Kraken pairs fall through to
`interval=1440` bars opening 00:00 UTC (`main.py:6255-6272`,
`data/okx_feed.py:123-128`, `data/kraken_feed.py:343-348`). The
`round(t / step)` bucketing at `regime/correlation.py:308-309` joins them
anyway — by design, per the comment at `:293-296`. Measured cost, hourly
simulation aggregated into the two real day conventions:

```
true daily corr, two aligned assets              : +0.526
measured corr, one aligned / one 8h-offset asset : +0.370   (-30 %)
```

So the covariance the Mahalanobis inverse is built from is materially wrong for
every ETH/BTC-vs-rest pair — and cross-asset correlation breakdown between the
majors and the alts is precisely what this index exists to detect.
**Honest negative:** this does *not* inflate the firing rate. Because the
percentile is self-normalising over a window built from the same misaligned
data, `P(pct >= 95)` on a stationary market is 4.4% both aligned and mixed. It
degrades information content, not calibration.

**Latent, and untested:** the bucketing is safe only while a venue's day-roll
is within ±12h of UTC midnight. OKX at −8h rounds into the same bucket; a venue
at +16h (or any roll past the midpoint) shifts an entire asset by one full
bucket — a true one-day shear, the exact failure mode M7 exists to prevent:

```
6/12 assets at +16h : |delta pct| median 15.2, p90 47.7, max 91.2
                      crisis verdict FLIPS in 9.0 % of draws
```

`tests/test_audit_regime_strategy.py:225-233`
(`test_m7_venue_day_boundary_offset_still_joins`) pins the **−8h** case, which
sits on the safe side of the rounding boundary. The shear case is unpinned.

---

## 6. What was checked and came back clean

Recorded so a later session does not re-litigate:

* Units are consistent. `turbulence_pct` is 0–100 (`:334`) and `crisis_vol_pct`
  is 95 (`config.json:259`) — no 0–1 vs 0–100 bug at
  `regime/macro_regime.py:442`. The 0–1 values in `signal_history.csv` are the
  ML-scaled feature (`ml/features.py:391`), not the decision input.
* The forming bar is genuinely excluded (`:276-283`), and
  `tests/test_audit_regime_strategy.py:206-212` pins it.
* The join is on bar timestamp, not list position (M7), and the fixture at
  `tests/test_audit_regime_strategy.py:178-180` is a real test.
* Covariance shrinkage is applied and the inverse falls back to `pinv` on
  `LinAlgError` (`:328-331`).
* The statistic is smooth, not noisy: lag-1 autocorrelation +0.988 on the live
  cycle series. A single read is a legitimate read.
* The elevated reading is corroborated by an independent instrument (per-asset
  intraday `vol_percentile`, section 2). The market really is more volatile.

**Harness self-correction, per the method.** My own measurement instrument was
wrong twice before it was right, and both errors would have produced confident
false findings: (a) the first shock-injection run put the shock on the bar that
`update_turbulence` drops as forming, producing a clean "shock timing does not
matter" null; (b) the first venue-offset run used an epoch anchor whose
fractional part masked the bucket shift, producing an exact `delta = 0.0` for
all 200 draws. Both were caught by disbelieving a suspiciously clean null. The
numbers in this document are post-correction.

---

## 7. Consequence for the current blackout

Nothing here says the reading is fake. It says the reading does not mean what
the consumer assumes. Specifically, for 2026-08-20 → now:

1. The market is genuinely more volatile (independent corroboration).
2. `turbulence_pct` is at 97.2–98.4, i.e. among the ~4 most atypical
   cross-sectional days of the last 250 — which is a **rank**, and would be
   reached on ~5% of days regardless.
3. That single scalar is broadcast to every asset (`main.py:6280`), so the
   crisis label is uniform by construction, not by evidence. PAXG's own
   volatility percentile is flat at 0.52 across the boundary.
4. Crisis bypasses hysteresis (`regime/macro_regime.py:424`) and sets
   `allow_new: False` (`:53`), so there is no confirm requirement and no
   graceful decay — a single hourly read flips the whole book off.

**The evaluation-gate stall is therefore an expected output of the current
wiring, not an anomaly.** Any remedy touches entry decisioning and is
**COHORT-RESETTING** under the era-4 moratorium — it requires operator
adjudication and would mint a new execution-era boundary. No change is proposed
here, and none was made.

Candidate directions, for the adjudication docket only, not endorsed:
a separate `crisis_turbulence_pct` key distinct from `crisis_vol_pct`; a
per-asset Mahalanobis contribution so the overlay is scoped to assets that
actually moved; an absolute-level floor alongside the rank so the trigger can
say "this year was calm"; `config_guard` bounds on `regime.crisis_vol_pct` and
the `correlation` block; a `turbulence_ts` + staleness code on `CorrState`; and
export of the scalar into the `status.json` schema (the last two are SAFE class
and independent of the moratorium).

---

## Reproduction

```
/tmp/turb/an.py      distribution of the live turbulence_pct column
/tmp/turb/an2.py     change-point / dwell / autocorrelation, per-UTC-day table
/tmp/turb/an3.py     collapsed-by-cycle series, intraday range, July instability
/tmp/turb/an4.py     per-day range, max step, direction reversals, day traces
/tmp/turb/corrob.py  second-route corroboration vs per-asset vol_percentile
/tmp/turb/inject.py  tests A/B/C/E/F against the shipped CorrelationEngine
/tmp/turb/inject2.py tests D (corrected)/G/H
/tmp/turb/inject3.py production-shaped venue-misalignment test
```

Run with `.venv/bin/python`. All are read-only against the repo.
