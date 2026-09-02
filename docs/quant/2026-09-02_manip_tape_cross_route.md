# SZ-045 / manip_suspect — cross-route check against the public trade tape

**Class: SAFE (measurement only).** No gate, threshold, config or decision path
was changed. Detection-side evidence for the open SZ-045 adjudication only.
No manipulation capability of any kind was built or described.

Scratch instruments (not shipped, not in the repo): `t5_tape_stats.py`,
`t5_analyze.py`, `t5_final.py`, `t5_verify.py`, `t5_recheck.py` (revision 2)
in the session scratchpad.
This memo is the only repo artifact.

## REVISION 2 (2026-09-02T02:40Z) - what review changed

Two corrections, both re-derived here; **Findings 1, 2 and 3 are NOT
re-derived** and remain as-of their 01:46-01:48Z snapshot (see the box under
Finding 0 for exactly what that now means).

1. **Finding 0 is no longer true.** It said FLOW "is unmeasurable (zero tape
   rows)" and that the route was "structurally blind to 98.8%". The FLOW
   backfill was IN FLIGHT while the memo was written and has since landed:
   FLOWUSD now holds **18,372 rows** to `t_max` 2026-09-02T01:44:39Z, and BTC
   reached 2,930,099 rows / 2026-09-02T01:59:31Z. Recounted on the current
   tape, tape-visible refused rows are **107, not 52**, and the blindness is
   **85.6%, not 98.8%**. The memo stamped its coverage correctly and never
   scored past its own `t_max` - the defect is that it presented a
   backfill-in-progress gap as a STRUCTURAL property of the route, with a
   growing-backfill caveat for BTC and none for FLOW.
2. **The SZ-045 disposition and the `manip_suspect` column are not the same
   object, and the memo never said so.** New section "Finding 0b".

## As-of stamps (live writers; values are as-of, never "current")

| Source | Read (UTC) | Value |
|---|---|---|
| `outputs/signal_history.csv` | 2026-09-02T01:46:32Z | 22,499 rows |
| `outputs/signal_history.csv` (re-read) | 2026-09-02T01:48:36Z | 22,505 rows (grew 6 rows in 124 s — runner live) |
| `outputs/audit.jsonl` | 2026-09-02T01:48:36Z | 76,429 lines / 24.9 MB |
| tape `--coverage` snapshot | 2026-09-02T01:46:25Z | table below |

Tape coverage, `python scripts/kraken_trades_backfill.py --coverage`, quoted
verbatim (rows / `t_max_utc`): XBTUSD 2,122,876 / 2026-08-23T14:53:38Z
(**PARTIAL, backfill live — grew 2,072,926 → 2,122,876 in 72 s**);
ETHUSD 1,207,483 / 2026-09-02T01:10:32Z; SOLUSD 1,023,613 / 2026-09-02T00:10:00Z;
XRPUSD 1,158,461; ADAUSD 556,533; LTCUSD 342,193; SUIUSD 342,902; XDGUSD 290,840;
LINKUSD 278,754; AVAXUSD 169,808; DOTUSD 169,080; PAXGUSD 114,684; ARBUSD 48,100;
MINAUSD 34,166; **FLOWUSD 0 (ABSENT)**. All `t_min_utc` = 2026-07-13T00:00Z.

## Method

Boundaries, exact and inclusive. For each row of `signal_history.csv` with
non-null `signal_ts`, the tape window is `[signal_ts - w, signal_ts)` for
`w` in {60, 300} seconds. A row is used only if its pair has tape rows and
`signal_ts - 300 >= t_min_s` and `signal_ts <= t_max_s` of the coverage snapshot
above (BTC therefore stops at 2026-08-23T14:53:38Z; 337 BTC signals dropped for
that reason). Ticks read via
`scripts.kraken_trades_backfill.TickStore().load(pair, start_s, end_s)`;
pair names via `kraken_pair()` (DOGE to XDGUSD, BTC to XBTUSD).

Statistics per window: `n` (trade count); `run` (longest run of consecutive
same-side trades, `side` 'b'/'s'); `run_frac` = `run / n`; `mkt_share` = share of
`otype == 'm'`; `burst` = max trades in any 5 s sub-bin / mean per 5 s bin (bins
aligned to window start); `size_cv` = `std(volume, ddof=1) / mean(volume)`.
Windows with `n < 2` yield NaN for all but `n`.

**SZ-045 flag — needle and join rate, double-derived.** Route A:
`signal_history.csv` column `disp`, needle `startswith("SZ-045")` -> **744 rows**
(all exactly the string `SZ-045`). Route B: `grep -c 'SZ-045' outputs/audit.jsonl`
-> **3 lines**, all `code = "LB-010"`, `src = "long_book"`, payload keys
`{asset, kind:"manip", manip_score}`, all `asset = "BTC"`, ts range
1787704479.156 - 1788099057.588. **The two routes disagree by 248x.** The audit
does not record the sizer's SZ-045 dispositions; those 3 lines are long-book veto
events, a different emitter. There is no signal-row id in that payload, so **no
join to signal rows is possible on the audit route at any tolerance** — join rate
0/744. All SZ-045 numbers below come from Route A (`disp`), the only route
carrying one row per disposition. [K]

Statistics: Spearman via `pandas.rank().corr()` (no scipy). CIs are day-block
bootstraps (calendar-day blocks, `signal_ts // 86400`, 400 reps, 2.5/97.5
percentiles); day count reported per row. Agreement nulls are per-asset
**stratified** permutations (2,000 reps).

## Finding 0 (dominates everything below): the tape route is blind to most of SZ-045 - 85.6% as re-read at 02:33Z, not the 98.8% first published

> **RE-DERIVED 2026-09-02T02:33:03Z** (`t5_recheck.py`, `signal_history.csv`
> 22,554 rows, needle `disp == "SZ-045"`, window and coverage rule verbatim
> from Method):
> `disp=='SZ-045'` = **744** rows, unchanged, {FLOW 451, MINA 284, BTC 4,
> DOT 3, ETH 1, ARB 1}. In-coverage rows 22,549 of 22,554; visible
> (`n_300 >= 5`) **15,996**; refused in coverage **744**; refused VISIBLE
> **107** {FLOW 51, MINA 47, BTC 4, DOT 3, ETH 1, ARB 1} across **24**
> distinct days. Blindness **637/744 = 85.6%**. FLOW: 451 refused, all in
> coverage, 385 with zero trades in the 60 s window, 228 with zero in 300 s,
> `n_300` median 0.0 - FLOW is now *measurable* and turns out to be the
> thinnest tape in the set, which is a finding, not a gap.
> **Consequence for Findings 1-3: their populations are STALE.** They were
> computed on 15,524 visible rows / 52 refused / 25 matched pairs / 13 day
> blocks; the same construction today would use 15,996 / 107 / more pairs /
> 24 blocks, with FLOW's 51 refused rows entering a sample that had none.
> Nothing below has been re-run - treat every SZ-045-specific n in Findings
> 2 and 3 as a snapshot of a population that has since roughly doubled, and
> re-run before citing any of it as settled.

SZ-045 refusals by asset, full file, `disp` route, read 2026-09-02T01:48:36Z [K]:

| asset | SZ-045 rows | tape rows |
|---|---|---|
| FLOW | 451 | **0 (no tape at all)** |
| MINA | 284 | 34,166 (thinnest covered pair) |
| BTC | 4 | 2.12M (partial) |
| DOT | 3 | 169,080 |
| ETH | 1 | 1.21M |
| ARB | 1 | 48,100 |
| **total** | **744** | |

FLOW + MINA = 735/744 = **98.8%** AS OF 01:48Z. FLOW was unmeasurable then (zero tape rows) and is not now - 51 of its 451 refusals clear the visibility floor at 02:33Z, which is what takes the blindness to 85.6% (box above). On MINA
the tape is near-empty exactly when SZ-045 fires: of the 289 refused rows inside
coverage, **224 have zero trades in the 60 s window** and 106 have zero in the
300 s window; 256/289 have `n_60 < 2` and 164/289 have `n_300 < 2`, i.e. no
computable run/burst/CV. MINA `n_300` median is 1.0 (mean 3.99, n=1,884). [K]

Applying a visibility floor of `n_300 >= 5` leaves 15,524 of 21,143 in-coverage
rows but only **52 of 289 refused rows** (ARB 1, DOT 3, ETH 1, MINA 47). Every
SZ-045-specific result below rests on those 52 rows across 13 distinct days.
That is the real sample size **as of 01:48Z**; at 02:33Z it is 107 rows across
24 days (box above), and the 52-row results were not recomputed.

## Finding 0b - the SZ-045 disposition and the `manip_suspect` score disagree on a quarter of refusals

Read 2026-09-02T02:33:03Z, `outputs/signal_history.csv`, 22,554 rows,
`manip_suspect` non-null on all of them [K]:

| set | rows |
|---|---|
| `disp == "SZ-045"` | 744 |
| `manip_suspect >= 0.90` | 1,028 |
| `manip_suspect >= 0.90` AND `disp != "SZ-045"` | **484** |
| `disp == "SZ-045"` AND `manip_suspect < 0.90` | **200** (26.9% of refusals) |

Refused rows' `manip_suspect`: min **0.2126**, median 0.9499, max 1.0000.

The audit line states the rule verbatim - `LB-010: BTC: manip suspect 1.00 >=
veto 0.90 (SZ-045)` - so a reader is entitled to assume the refusal set is
`{score >= 0.90}`. It is not: two hundred refusals sit BELOW that threshold
(the sizer's veto is not the long-book veto, and the score a row carries in
`signal_history` is not necessarily the score the disposition was taken on),
and 484 rows at or above it were not refused. **This matters for how the rest
of this memo reads:** Finding 1 correlates the CONTINUOUS column, Findings 2
and 3 use the `disp` FLAG, and those are two different objects that agree on
about three quarters of the refusal set. Any statement of the form "the score
tracks X, therefore the refusals track X" needs the join re-established
first; this memo does not establish it.

## Finding 1 — Spearman, tape statistic vs `manip_suspect` (continuous), tape-visible rows

Pooled over 15,524 rows / 51 day-blocks (`n_300 >= 5`). The "per-asset signs"
column counts the 11-13 per-asset rhos (assets with >=200 non-null rows).

| statistic | rho | day-block 95% CI | n | per-asset signs |
|---|---|---|---|---|
| `n_60` | +0.1838 | [+0.1232, +0.2370] | 15,524 | 11 pos / 2 neg |
| `n_300` | +0.2101 | [+0.1535, +0.2662] | 15,524 | **13 pos / 0 neg** |
| `run_60` | +0.1410 | [+0.0985, +0.1783] | 12,027 | 10 pos / 1 neg |
| `run_300` | +0.1584 | [+0.1146, +0.2002] | 15,524 | **13 pos / 0 neg** |
| `run_frac_60` | -0.1215 | [-0.1678, -0.0770] | 12,027 | **0 pos / 11 neg** |
| `run_frac_300` | -0.1751 | [-0.2319, -0.1244] | 15,524 | 2 pos / 11 neg |
| `mkt_share_60` | +0.1386 | [+0.1150, +0.1651] | 12,027 | 10 pos / 1 neg |
| `mkt_share_300` | +0.1197 | [+0.0877, +0.1482] | 15,524 | 10 pos / 3 neg |
| `burst_60` | -0.1012 | [-0.1477, -0.0550] | 12,027 | **0 pos / 11 neg** |
| `burst_300` | -0.1587 | [-0.2004, -0.1130] | 15,524 | 1 pos / 12 neg |
| `size_cv_60` | +0.1568 | [+0.1075, +0.2015] | 12,027 | 9 pos / 2 neg |
| `size_cv_300` | +0.1856 | [+0.1332, +0.2403] | 15,524 | **13 pos / 0 neg** |

**These twelve rows are not twelve channels; they are close to one.** `burst` and
`run_frac` are mechanically anti-correlated with `n` (Spearman `burst_300` vs
`n_300` = **-0.4548**, `burst_60` vs `n_60` = **-0.3591**, n as above): with few
trades in a 300 s window the 5 s-bin max/mean ratio is largely `1/density`, and a
2-trade window is trivially one-sided. The sign pattern is exactly what a single
**activity** channel produces — `manip_suspect` rises with trade count and size
dispersion and falls with the two statistics that fall mechanically as count
rises. The direction is also the opposite of the naive archetype: the book-only
score is *higher* in busier, *less* one-sided, *less* bursty tape.

## Finding 2 — SZ-045-refused vs matched non-refused (same asset, nearest `signal_ts` within +/-3600 s)

Tape-visible only. **25 matched pairs across 13 day-blocks.** Six of the twelve
statistics had fewer than 20 usable pairs at `w=60` (n=6) and were not computed.

| statistic | refused mean | control mean | difference | day-block 95% CI | n pairs |
|---|---|---|---|---|---|
| `n_60` | 4.92 | 2.92 | +2.00 | [-1.41, +6.48] | 25 |
| `n_300` | 25.16 | 29.44 | -4.28 | [-19.40, +11.56] | 25 |
| `run_300` | 10.28 | 14.48 | -4.20 | [-11.37, +2.63] | 25 |
| `run_frac_300` | 0.6517 | 0.6640 | -0.0123 | [-0.1157, +0.1422] | 25 |
| `mkt_share_300` | 0.1513 | 0.1922 | -0.0409 | [-0.1546, +0.0622] | 25 |
| `burst_300` | 28.61 | 26.74 | +1.87 | [-4.19, +6.87] | 25 |
| `size_cv_300` | 1.2246 | 1.2316 | -0.0070 | [-0.2839, +0.3121] | 25 |
| `run_60`, `run_frac_60`, `mkt_share_60`, `burst_60`, `size_cv_60` | — | — | not computed | n=6 < 20 | 6 |

**Every interval contains zero.** No difference survives.

**Placebo** (refused rows' timestamps shifted +/-86,400 s, same tape): of 558
placebo windows computed, only 108 clear the `n_300 >= 5` visibility floor — the
placebo arm is thinner than the live arm. Placebo means at `w=300`: `n_300` 28.38
(-24 h, n=55) / 13.85 (+24 h, n=53) vs refused 25.16 and control 29.44;
`burst_300` 25.86 / 27.35 vs refused 28.61 and control 26.74; `run_frac_300`
0.6437 / 0.6509 vs refused 0.6517. The placebo windows are indistinguishable from
the true windows on every statistic. Given the CIs above this is consistent with
nothing time-locked existing, and equally consistent with the sample being too
small to detect it; **the placebo does not discriminate at this n**.

## Finding 3 — agreement between the SZ-045 flag and a base-rate-matched tape flag

Tape flag = top-k per asset by the named statistic, with k = that asset's SZ-045
count on tape-visible rows (total k = 52, matching the 52 refused rows). Null =
permute the flag within each asset (2,000 reps) — the **stratified** null, because
both flags concentrate heavily in MINA. 2x2 over 15,524 visible rows.

| tape flag metric | both | SZ-045 only | tape only | Jaccard | stratified-null mean `both` | p(>=obs) |
|---|---|---|---|---|---|---|
| `burst_300` | 12 | 40 | 40 | 0.1304 | 7.29 | **0.026** |
| `burst_60` | 8 | 44 | 44 | 0.0833 | 7.32 | 0.455 |
| `run_frac_60` | 8 | 44 | 44 | 0.0833 | 7.38 | 0.473 |
| `run_frac_300` | 8 | 44 | 44 | 0.0833 | 7.22 | 0.428 |
| `size_cv_300` | 7 | 45 | 45 | 0.0722 | 7.21 | 0.618 |
| `mkt_share_300` | 2 | 50 | 50 | 0.0196 | 7.38 | 0.999 |

Six metrics were tried; `burst_300`'s nominal p = 0.026 becomes ~0.16 under a
Bonferroni correction for six and is **not significant**. Every other metric sits
on its null.

**Correction to my own first pass, recorded because it changes the reading.** A
pooled independence expectation (52 x 52 / 15,524 = 0.17 expected overlaps) made
`both = 8` look 46x above chance. That expectation is wrong: it ignores that both
flags concentrate in MINA. The correct stratified null expects ~7.3, and the
observed overlap is ordinary. The apparent agreement was an artifact of the wrong
null.

**The tape's own definitions disagree with each other about as much as they
disagree with SZ-045**, which caps how much any of them can arbitrate:
`burst_60` vs `run_frac_60` Jaccard 0.300; `run_frac_60` vs `run_frac_300` 0.238;
`burst_300` vs `run_frac_300` 0.182; `burst_60` vs `burst_300` 0.143; `burst_60`
vs `run_frac_300` 0.095; `burst_300` vs `run_frac_60` 0.106. Against the standing
book-only Jaccard of 0.462 between the two book instruments, the tape route agrees
with SZ-045 *less* (0.02-0.13) than the two book instruments agree with each
other, and no better than its own two definitions agree with each other.

Note on a coincidence that looked like a bug: `burst_60` and `run_frac_60` produce
identical 2x2 counts (8/44/44). Their flags are **not** identical — they overlap
on 24 of 52 rows; the counts merely coincide. MINA has 107 tape-visible rows tied
at `run_frac_60 = 1.0` and 38 tied at max `burst_60`, so top-k selection there is
largely tie-breaking by row order — itself a limitation of the flag on thin tape.

## Instrument verification (separating "0 findings" from "the scan is broken")

Run before any of the above was read as a result (`t5_verify.py`):

| control | expected | observed | verdict |
|---|---|---|---|
| Positive: planted rank signal vs `burst_300` | rho >> 0 | **+0.9990** | Spearman path recovers a real effect |
| Positive: flag vs itself, agreement code | Jaccard 1.0 | **1.0** (k=52) | 2x2 / Jaccard path correct |
| Negative: random flag at the same per-asset base rate | Jaccard ~ null | **0.0297**, both=3 | no spurious agreement |

**The scan works.** The nulls in Findings 2 and 3 are measurements, not a broken
instrument. What is *not* established as a null is the FLOW and MINA-thin
population: there the instrument is genuinely blind, and blindness is reported as
blindness, not as absence.

## What the tape route can and cannot separate

**Can:** who actually aggressed, at what size, in what sequence, in the seconds
before a signal — an independent physical record, not derived from our own book
snapshots, sharing no failure mode with the book-only score.

**Cannot, and this is the binding limit:** the tape records only **executed**
trades. It contains no cancelled or resting quotes. Layering and spoofing are, by
construction, patterns in orders that are placed and withdrawn *without
executing* — a spoof that works leaves no trade to record. The tape can therefore
never confirm the spoof component of `manip_suspect`; at most it observes the
aggression that follows one. A null on this route is not evidence that no spoofing
occurred. Symmetrically it cannot distinguish honest repricing from layering
either, since neither leaves a print — the exact separation the paired-injection
test already found the book route unable to make. Two routes that both lack the
discriminating channel do not become one route that has it.

Three further limits: (a) most SZ-045 fires on FLOW and MINA, whose windows
are near-empty — 85.6% of refusals are below the visibility floor as re-read
at 02:33Z (98.8% at the 01:46Z snapshot, when FLOW had no tape at all) — so
the route is thin exactly where the flag lives, and FLOW's thinness is now a
measurement rather than an absence; (b) BTC coverage was partial and still
growing, so BTC rows stopped at 2026-08-23T14:53:38Z in Findings 1-3 and any
later BTC refusal is outside those numbers (the tape has since reached
2026-09-02T01:59:31Z); (c) `burst` and `run_frac`
degenerate toward `1/density` on thin windows, so on exactly the pair that matters
they are activity proxies rather than shape statistics.

## Interpretation (confined to what survived)

What survived: (1) the SZ-045 disposition exists in `signal_history.disp` and
**nowhere joinable in the audit trail** — 744 rows vs 3 unjoinable long-book
lines, a gap worth naming independently of anything about manipulation;
(1b) the `disp == SZ-045` refusal set and the `manip_suspect >= 0.90` score
set are NOT the same rows - 200 of 744 refusals score below the quoted 0.90
veto and 484 rows at or above it were not refused (Finding 0b), so the
continuous-score result and the flag results below are about two different
objects;
(2) `manip_suspect` has a real, day-block-robust, sign-consistent-across-assets
association with tape **activity** (`n_300` rho +0.2101, 13/13 assets positive;
`size_cv_300` +0.1856, 13/13 positive), with the run/burst statistics moving the
way a `1/n` artifact of that same activity channel would move — one channel, not
six, and an activity channel carries no manipulation content; (3) on the 52
tape-visible refused rows, refused windows are **indistinguishable** from
time-matched non-refused windows on every computable statistic (all CIs span
zero), and a base-rate-matched tape flag agrees with SZ-045 at chance under the
correct stratified null. What did not survive: my own first-pass claim of
above-chance agreement, an artifact of a pooled null that ignored asset
stratification. The honest summary is that the tape route **did not corroborate
and did not refute** the book-only manipulation score: on the 1.2% of refusals it
can see it finds nothing, on the rest (98.8% at 01:48Z, 85.6% at 02:33Z) it could not see at all, and on the spoof
component it structurally cannot see anything by construction. SZ-045 remains
unresolved in both directions and this route cannot resolve it AT THIS
SAMPLE. The most economical reading of the whole table is the boring one -
the CONTINUOUS SCORE tracks how busy the tape is, and the assets the
DISPOSITION fires on are the ones that barely trade; those are two statements
about two objects that overlap on ~73% of refusals (Finding 0b), and this
memo does not join them. The blindness that made the route unusable has also
halved since it was written (85.6% at 02:33Z against 98.8% at 01:46Z, FLOW's
backfill having landed), so the honest status of Findings 2 and 3 is
"under-powered on a population that has since doubled", not "settled null".

**No gate change, threshold, or tuning is proposed by this memo.**

---

## ADDENDUM (2026-09-02T03:03:56Z, added after the backfill completed)

The coverage caveats above are **stale, and the correction strengthens the memo's
verdict while refuting its stated reason.**

At the time of measurement FLOW had zero tape rows and BTC was partial, and the memo
attributed the 98.8% blindness to that. The backfill has since completed: FLOW now
holds 18,372 rows and BTC 2,930,099, both reaching 2026-09-02T~02:00Z. Re-measured on
full coverage:

| asset | refusals | inside tape coverage | with >=5 trades in the prior 300 s |
|---|---|---|---|
| FLOW | 451 | 451 | **51** |
| MINA | 284 | 284 | **47** |
| BTC | 4 | 4 | 4 |
| DOT | 3 | 3 | 3 |
| ARB | 1 | 1 | 1 |
| ETH | 1 | 1 | 1 |
| **total** | **744** | **744** | **107 (14.4%)** |

Tape-visible refusals doubled, from 52 (7.0%) to 107 (14.4%). **The remaining blindness
is not a data gap and cannot be closed by more backfilling.** Every refusal is now
inside the tape window; what stops the measurement is that FLOW prints roughly fifteen
trades an hour, so a 300-second window usually contains fewer than five. SZ-045
refusals concentrate on precisely the illiquid assets whose tape is too sparse to
characterise — 735 of 744 are FLOW and MINA.

That is a fact about **what the gate refuses**, not about our data collection, and it
makes the memo's verdict firmer rather than weaker: the tape route cannot adjudicate
SZ-045, now or later. Do not re-run this analysis "after more backfill".
