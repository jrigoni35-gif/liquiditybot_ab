# Expectancy by environment — is value consistent across regimes, sides, eras? (item 5, 2026-09-02)

**Class: SAFE (measurement-only; no code, config, or `outputs/` written).** Scratch instruments:
`scratchpad/s5_expectancy.py` (tables) and `s5_checks.py` (verification) — session scratch, not committed;
re-derive from the recipe below, never cite these digits as current.

**Snapshot.** `outputs/signal_history.csv` md5 `92422784e71255f08bf9fdc0d7b64f5c`, `outputs/fills.csv` md5
`c1e19e7443b8790c2da1d0f7f7668ac2`, both read **2026-09-02T23:08:50Z**. The runner was writing: a re-read at
23:11Z found 6,048 population-A rows vs 6,042 — every number here is **as-of 23:08:50Z**.

## Populations (kept separate; never pooled)

**A — candidate counterfactuals.** Filter: `label_era == "triple_barrier_h432"` AND `source == "candidate"` AND
`label_ret_pct` non-empty → **6,042 rows** (route 1 pandas; route 2 `csv` module: 6,042 at the same instant — the 6,048
seen later is drift, not a parse defect). `label_ret_pct` is **net of `label_round_trip_cost_pct` (0.6%) + capped spread**
(`ml/history.py:312-322, 377-380`); live rows are net of BOOKED fees and are a different cost basis, so the 36 live
labelled rows (20 h432 + 16 exit_sim) are EXCLUDED from A. Span: signal_ts 1787562300–1788380400 = **10 UTC day blocks,
2026-08-24 … 2026-09-02** (this is the whole h432 label era with the column populated; label_ret_pct is blank before
2026-08-24 by schema, `ml/history.py:312`). Regime = the single `regime_*` flag set to 1 (asserted exactly one per row).
"Win" = `label_ret_pct > 0.6` (clears the round-trip cost a second time; the base is all rows in the cell).
CI = day-block bootstrap, 2,000 draws; **cells with < 5 distinct days are REFUSED** (no CI, no MDE).
MDE = 2.8 × bootstrap SD (80% power, α=.05 two-sided) — **calibrated by planting** (below).

**B — live round trips.** `scripts.cohort_eval.era4_trips(fills.csv, since=0.0)`: entry-opened, fully closed (exit size
within 2% of entry), hedge-opened trips excluded, duplicate fill patterns dropped. **326 trips** of 331 entry position_ids
(pairing rate 0.985). Cross-implementation (independent `csv` pairing + `(sign·(exit_notional−entry_notional) − fees)/entry_notional`):
326 trips, identical pid set, **max |net diff| = 0.0000 bps**. Regime join to `signal_history` live rows by position_id:
323/326. Era = the trip's own stamped `exec_era` set (`eras`); blank-stamp trips are "pre-stamp" (fills before the stamp
existed, eras ≤7 pooled, older fee bookings) and are shown for context only. Trips whose legs straddle a cut are shown as
MIXED and pooled with nothing (3 straddle the cut-#9 fee correction). Boundary is clean: 0 era-9 legs before
2026-08-30T15:32:36Z, 0 era-8 legs after. Effective n = `cohort_effective_n` on [t_open, t_close] spans; **floor =
2 × SE × se_inflation** as cohort_eval prints it.

## Table A — candidate net expectancy (% of notional, net of 0.6% cost), regime × side, with FLOW / ETH / BTC

Format: `mean [95% day-block CI] · n · days · MDE · P(win>0.6%)`. REF = refused (<5 day blocks; raw mean shown in the
scratch output only). No cell in this table clears zero on the positive side.

| regime × side | POOL | FLOW | ETH | BTC |
|---|---|---|---|---|
| ALL × ALL | −0.71 [−1.03,−0.39] n6042 d10 MDE 0.48 Pw .39 | −1.53 [−2.15,−0.95] n348 d10 MDE 0.84 Pw .31 | −1.10 [−1.52,−0.69] n602 d9 MDE 0.59 Pw .34 | −0.82 [−1.05,−0.56] n290 d9 MDE 0.35 Pw .27 |
| ALL × long | −0.83 [−1.61,−0.16] n3404 MDE 1.05 | −2.23 [−3.37,−0.94] n214 MDE 1.76 | −1.19 [−2.59,+0.15] n312 MDE 1.95 | −1.12 [−1.91,−0.34] n169 MDE 1.12 |
| ALL × short | −0.55 [−1.15,−0.08] n2638 MDE 0.80 | −0.39 [−1.69,+0.74] n134 MDE 1.74 | −1.01 [−1.83,+0.20] n290 MDE 1.46 | −0.41 [−1.19,+0.27] n121 d8 MDE 1.04 |
| bear × ALL | −0.53 [−1.02,+0.10] n793 d9 MDE 0.84 | −1.24 [−2.46,−0.23] n149 d7 MDE 1.60 | REF (n44, 1 day) | none (n0) |
| bear × long / short | −0.67 [−1.81,+0.35] n475 / −0.33 [−1.48,+0.73] n318 | −1.31 [−3.47,+0.69] n105 / −1.08 [−3.19,+1.32] n44 | REF / REF | none |
| bull_quiet × ALL | −0.89 [−1.47,−0.37] n1737 d10 MDE 0.77 | −1.39 [−2.25,−0.58] n114 d5 MDE 1.21 | −1.16 [−1.72,−0.61] n454 d9 MDE 0.82 | −0.96 [−1.17,−0.70] n206 d9 MDE 0.34 |
| bull_quiet × long / short | −0.88 [−1.99,−0.20] n1007 / −0.89 [−1.67,−0.15] n730 | −3.86 [−4.06,−3.62] n50 d5 (37/50 tb_sl, sl_frac 2.5–5.4%) / +0.54 [−0.74,+1.86] n64 MDE 1.98 | −0.95 [−2.95,+0.63] n215 / −1.34 [−2.05,−0.21] n239 | −1.23 [−1.94,−0.42] n118 / −0.59 [−1.49,+0.11] n88 |
| bull_vol × ALL | −0.79 [−1.44,−0.33] n861 d10 MDE 0.80 | none (n0) | none (n0) | REF (n16, 1 day) |
| bull_vol × long / short | −0.62 [−1.81,+0.59] n442 / −0.96 [−2.37,+0.08] n419 | none | none | REF / REF |
| crisis × ALL | REF (n687, **3 days**; raw −0.86) | REF (n34, 1 d) | REF (n78, 2 d) | REF (n23, 1 d) |
| range × ALL | −0.54 [−0.86,−0.20] n1964 d10 MDE 0.48 | −2.10 [−2.96,−1.06] n51 d7 MDE 1.37 | REF (n26, 4 d; raw −0.69) | REF (n45, 4 d; raw −0.02) |
| range × long / short | −0.70 [−1.82,+0.15] n1019 / −0.37 [−0.97,+0.15] n945 | −2.53 [−3.31,−1.03] n38 / REF (n13) | REF / REF | REF / REF |

Resolution / direction split (rule 4), POOL by regime — resolution = share not `tb_time`; direction = `tb_pt` share of
resolved: bear .651/.562 · bull_quiet .788/.406 · bull_vol .763/.454 · crisis .991/.423 · range .734/.420. Crisis
loads RESOLUTION (99% of paths hit a barrier) but not direction; bear is the only regime with direction > 0.5 and its
mean is still negative after cost. FLOW/ETH/BTC resolution split per regime not tabulated (cells too thin).

**MDE calibration (two-level day bootstrap: outer day-resample = fresh sample, plant shift, inner CI, 200 reps).**
Detection rate at 0 / MDE/2 / MDE: POOL .10/.34/.81 · FLOW .02/.34/.80 · ETH .03/.35/.87 · BTC .01/.36/.92. The
2.8×SD rule delivers ~80–90% power at the stated MDE and ~2–10% false-positive at 0 (POOL's .10 is above nominal .025 —
10 blocks is a coarse resample; treat POOL CIs as slightly optimistic). A first single-level plant (shift on the same
rows, no outer resample) read 1.0/0.0/0.0 — deterministic, not a power curve; discarded.

## Between-regime vs within-regime (population A, placebo = regime label shuffled WITHIN day, 500 draws)

| slice | max−min of regime means (%) | placebo p | placebo 95th pct | regime means |
|---|---|---|---|---|
| POOL | 0.36 | **0.18** | 0.43 | bear −0.53 · range −0.54 · bull_vol −0.79 · crisis −0.86 · bull_quiet −0.89 |
| FLOW | 1.12 | 0.33 | 1.36 | bear −1.24 · bull_quiet −1.39 · range −2.10 · crisis −2.36 |
| ETH | 0.47 | 0.39 | 0.84 | range −0.69 · crisis −0.95 · bear −1.05 · bull_quiet −1.16 |
| BTC | 1.19 | 0.09 | 1.28 | range −0.02 · crisis −0.91 · bull_quiet −0.96 · bull_vol −1.21 |

Positive control: planting +1.0% on `range` alone drives placebo p to 0.000 (obs spread 1.35) — the placebo can see a
regime effect of the size the operator hypothesises.

> **REPAIR 2026-09-02 (verification finding, WARNING, applied 23:24Z; scratch `s6r_s5spread.py`, `signal_history.csv`
> re-read 2026-09-02T23:24:23Z, 6,049 population-A rows / 10 days, 500 within-day shuffles, seed 7).** The table above
> admits EVERY regime cell with n ≥ 1 into the max−min spread — including cells this memo REFUSES for CI (BTC bull_vol
> n16 / 1 day, BTC crisis n23 / 1 day). The inclusion rule was unstated and the BTC placebo p is rule-dependent:
>
> | rule | POOL obs / p / null95 | FLOW | ETH | BTC |
> |---|---|---|---|---|
> | all cells (table above) | 0.36 / .16 / 0.42 | 1.12 / .27 / 1.40 | 0.47 / .40 / 0.85 | 1.19 / .11 / 1.31 |
> | cells with n ≥ 20 | 0.36 / .18 / 0.44 | 1.12 / .32 / 1.46 | 0.47 / .35 / 0.84 | **0.94 / .02 / 0.88** (verifier's run: p .043) |
> | CI-eligible cells only (≥ 5 days) | 0.36 / .16 / 0.42 | 0.86 / .06 / 0.88 | one cell — spread undefined | one cell — spread undefined |
>
> Under the n ≥ 20 floor BTC's spread (0.94 = range −0.02 minus bull_quiet −0.96) is nominally outside its null, and
> it is driven entirely by the `range` cell (n45, 4 days) that is itself CI-refused. BEFORE: "inside its shuffled
> null in every slice". AFTER: inside the null for POOL, FLOW and ETH under every rule; for BTC the statement holds
> under the all-cells rule and FAILS (p .02–.04) under an n ≥ 20 floor, on a 4-day cell — UNDETERMINED for BTC, not
> null. Verdict unchanged: no cell is positive under any rule.

Verdict: **the between-regime spread is inside its shuffled null for POOL, FLOW and ETH under every inclusion rule,
and for BTC only under the all-cells rule** (see REPAIR); the sign is negative in every regime that has a CI, and no
single regime carries a positive expectancy. BTC's `range` mean (−0.02, n45, 4 days) is the only near-zero cell and it
is REFUSED for CI.

**Long vs short** (same placebo): POOL spread 0.28, **p 0.000** (null95 0.19); FLOW 1.84, p 0.000; BTC 0.71, p 0.000;
ETH 0.18, p 0.27. Shorts lose less than longs everywhere except ETH — a real difference in the magnitude of the loss over
these 10 days, **not** a sign change: short cells' upper CI bounds sit at +0.74 (FLOW), +0.27 (BTC), −0.08 (POOL). Ten
days of one direction of drift can produce this; it is not evidence of a short edge.

## Table B — live round trips, net bps of entry notional, by exec era × side, FLOW / ETH / BTC

Format: `mean bps · n / eff_n · floor bps (2·SE·infl) · [day-block CI if ≥5 days]`. **FLOW: 0 fills, 0 trips, in every
era** — 472 of 1,067 FLOW signal rows carry SZ-045 (read 23:10Z); FLOW is unmeasurable on realized trades because the
gate never lets it trade (FINDING, not a null).

| era × side | POOL | FLOW | ETH | BTC |
|---|---|---|---|---|
| **7** (`7-e7d5ca1a`) ALL | −21.9 · 60/25.6 · floor 97.5 · [−97.5,+67.4] d15 | none | +65.8 · 10/9.0 · floor 187.6 · [−93,+271] | +80.4 · 5/4.6 · floor 271.0 · [−86,+345] |
| 7 long | −6.7 · 35/20.4 · floor 129.2 | none | +83.4 · 9/8.3 · floor 203.1 | +114.6 · 4/4.0 · floor 322.5 (REF <5 d) |
| 7 short | −43.2 · 25/15.2 · floor 86.3 · [−111,+30] | none | −92.8 · n1 | −56.4 · n1 |
| **8** (`8-ca55e2ba`, fees booked at over-stated 40/80) ALL | −345.2 · 3/1.4 · floor 257.3 · REF (2 d) | none | −325.9 · n1 | none |
| **9** (`9-16ec821e`, corrected 22/38) ALL | −146.2 · 15/6.9 · floor 123.7 · REF (4 d) | none | −93.1 · 2/1.2 | none |
| 9 long / short | −169.7 · 9/6.3 · floor 124.8 / −111.0 · 6/3.9 · floor 183.8 | none | −257.6 n1 / +71.3 n1 | none |
| pre-stamp (eras ≤7 pooled, context only) ALL | −70.2 · 239/80.2 · floor 13.9 · [−83.7,−59.3] d21 | none | −66.7 · 45/30.3 · floor 18.3 · [−82,−50] | −86.0 · 32/23.2 · floor 18.6 · [−122,−69] |
| MIXED 8/9 (straddle the fee correction; not pooled) | −75.5 · n3 | — | — | — |

By regime (join rate 323/326): era 7 — bear −32.6 (18/11.7, floor 150) · bull_quiet +65.8 (8/7.0, floor 126) · bull_vol
−167.6 (9/6.8, floor 132) · range +10.1 (25/17.6, floor 130); era 9 — bull_quiet −168.2 (3/3.0, floor 173) · range −140.7
(12/6.6, floor 134). Era-7 regime spread 233 bps, shuffled-regime placebo p **0.087** (n60); era-7 side spread 36.5 bps,
p 0.60. **No era-7/8/9 cell clears its floor on the positive side.** The one `clears=True` in the raw scratch table
(MIXED 8/9 long, n2, 1 day) is a degenerate cell and is disregarded.

**Era question.** Δ(7−8) = +323 bps vs floor 275 — nominally outside the floor but era 8 has n=3 on 2 days (REFUSED);
Δ(7−9) = +124 bps vs floor 158 — **unresolved**; Δ(8−9) = −199 vs floor 286 — unresolved. Era 8 was accrued at the
over-stated 40/80 booking and era 9 at the corrected 22/38; they are not netted here and must not be. The only
population that clears any floor is the pre-stamp pool (−70 bps, floor 14) — and it clears it **negative**, on
fills whose booked fee schedule predates both the cut-#8 and cut-#9 corrections.

## Verdict

**No.** There is no environment — regime, side, asset, or exec era — in which this bot has a measured positive net
expectancy that clears its own floor. In population A every cell with a CI is negative or straddles zero, the
between-regime spread is inside the shuffled-label null in POOL, FLOW and ETH under every cell-inclusion rule (POOL p
.18, FLOW .33, ETH .39) and rule-dependent for BTC (.09 all cells; .02–.04 with an n ≥ 20 floor, driven by a 4-day
refused cell — UNDETERMINED, see REPAIR),
and the only real between-cell difference is long-vs-short *magnitude* (shorts lose less, p<.001 in POOL/FLOW/BTC),
not sign. In population B, era 7 (60 trips, eff n 25.6) is −22 bps against a 98 bps floor, era 9 (15 trips, eff n 6.9,
4 days) is −146 bps against a 124 bps floor with no CI, era 8 is 3 trips. The triad: **FLOW** is the worst environment
on candidates (−1.53%, CI entirely below −0.9%, longs −2.23%) and has never traded, so its live expectancy does not
exist; **ETH** is −1.10% on candidates and +66 bps on 10 era-7 trips against a 188 bps floor — unresolved; **BTC**
earns "reliable" only in the narrow sense of the *tightest candidate CI* (MDE 0.35%, the smallest of the three) — and
that tight CI says −0.82% [−1.05, −0.56], i.e. BTC is the most *reliably negative* of the three at the labeler's
geometry; on live trips BTC is 5 era-7 trips and none in era 9. Unresolved at this sample: crisis (3 day blocks),
bull_vol for FLOW/ETH (n0) and BTC (1 day), every era-8/9 cell, every ETH/BTC live cell, and every candidate cell
below 5 days. The measured answer to "consistent to money in all environments" is: consistently negative or
unresolved, nowhere positive, on 10 days of candidates and 60 era-7 trips.

## What this could not see

- A is the labeler's counterfactual at the bot's own barrier geometry (PT 8σ / SL 6σ, 36 h), on **10 days** of one
  market; it is not a backtest and cannot speak to any other geometry or any period before 2026-08-24.
- B's regime is the signal-row regime at entry; regimes during the hold are not tracked.
- Day blocks assume no dependence across UTC midnight; 36 h labels straddle days, so A's CIs are still somewhat optimistic.
- Not run: per-regime resolution/direction split for FLOW/ETH/BTC (cells too thin); finer-than-day blocks;
  `label_decomposition_report --power-calibration` (its planted effect targets the label, not `label_ret_pct`).
- Boundary changes implied: none required by these numbers. A future fee-correction or geometry cut re-partitions B.
