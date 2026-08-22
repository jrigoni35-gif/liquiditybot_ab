# Turbulence episode history — is the 2026-08-22 crisis stall self-resolving?

Measurement-only note. No engine/config/decision-path changes. Source:
`outputs/signal_history.csv` (14,464 rows, 2026-07-13 12:35:47 UTC →
2026-08-22 10:27:18 UTC). Script used (not checked in):
`/tmp/claude-0/-home-user-liquiditybot-ab/261db541-e46c-5c8c-8d66-fd7ab1553c4b/scratchpad/turb*.py`.

## Headline finding

**There is no historical precedent for this episode.** `turbulence_pct`
never crossed 0.95 at any point in the 37 days before 2026-08-20 (max
observed pre-onset: **0.940**, on 2026-07-13→2026-08-19). The entire
crisis-eligible history in this dataset is a single onset event that
began 2026-08-20 05:30 UTC and, as of the last row (2026-08-22 10:27
UTC), has not durably resolved. Any "how long do these last" question
therefore has an effective historical sample size of **~1 event**, not
a distribution — see §6.

## 1. Distribution of `turbulence_pct`

Row-level (14,464 rows, NOT independent — see §6):

| stat | value |
|---|---|
| mean | 0.368 |
| median | 0.270 |
| p75 | 0.612 |
| p90 | 0.964 |
| p95 | 0.984 |
| max (entire 40-day history) | **0.984** |
| % rows ≥ 0.95 | 10.3% |
| % rows ≥ 0.90 | 13.4% |
| % rows ≥ 0.75 | 17.2% |

`turbulence_pct` never takes a value above 0.984 anywhere in the
dataset (181 distinct values observed, in steps of ~0.004 — consistent
with a rank/N percentile off a ~250-point lookback, e.g. 246/250). It
is effectively rank-capped, not a continuous [0,1] score with headroom
above the current reading.

These "10.3% of rows ≥0.95" numbers are **misleading read as a base
rate**: restricting to the 37 days before 2026-08-20, the 99th
percentile of `turbulence_pct` was 0.928 and the max was 0.940 — i.e.
0% of that period was elevated. All of the ≥0.95 mass is packed into
the final ~53 hours (~5% of the dataset's calendar span, but a much
larger share of *row count* because sampling cadence roughly doubled
during the active period — see §6). This is a step change in regime,
not a stationary process with a 10% duty cycle.

## 2. Episodes (turbulence_pct ≥ 0.95)

**Gap rule chosen: bridge consecutive above-threshold readings
separated by ≤ 60 minutes of wall-clock time.** Rationale: within the
active window (≥2026-08-20), the inter-sample gap for the underlying
event-driven feed has p95 ≈ 24 min and p99 ≈ 70 min — 60 min sits above
normal sampling jitter, so it won't fragment one episode into many just
because the bot happened not to evaluate a signal for a few minutes.
It sits below all-but-one of the individually observed sub-threshold
readbacks (the deepest genuine reversions found were 1.18h and 1.34h),
so it does not paper over a real, sustained return to calm.

At this gap rule there are **2 episodes** in the entire dataset:

| # | start (UTC) | end (UTC, or "ongoing") | duration | peak |
|---|---|---|---|---|
| 1 | 2026-08-20 05:30:15 | 2026-08-21 03:02:15 | 21.53 h | 0.984 |
| 2 (current) | 2026-08-21 04:26:41 | 2026-08-22 10:27:18 (last row; still ≥0.95) | **30.01 h and counting (right-censored)** | 0.984 |

The gap between episode 1 and episode 2 was a single ~1.34h dip to
~0.524–0.744 — the *only* sustained (multi-sample) reversion below
0.95 anywhere in the record. Everything else that looks like a
"reversion" is much shorter.

**Sensitivity to the gap rule** (shown for transparency, not cherry-picked):
- Near-zero tolerance (bridge only true zero-width single-tick blips):
  **41 raw excursions**, all inside 2026-08-20 05:30 → 2026-08-22
  10:27; none before.
- ≥ 90 min tolerance: everything merges into **1** continuous 52.95h
  episode (2026-08-20 05:30 → 2026-08-22 10:27), because no genuine
  reversion in the record lasted that long.

Under every gap rule tried, the qualitative picture is the same: one
onset around 2026-08-20 05:30, and no confirmed durable return to calm
since.

## 3. Duration distribution — is the current episode typical?

Using the 60-min-gap definition, n=2 (1 completed + 1 ongoing) — too
small for a distribution. Using the strict/raw 41-run decomposition
(the internal micro-spikes of what is really one onset event, so these
are **not independent draws** — see §6), the 40 *completed* excursions
had:

| stat | value |
|---|---|
| median duration | 2.25 min |
| p75 | 26.7 min |
| p90 | 1.65 h |
| p95 | 2.43 h |
| max | 5.92 h |

The current (still-open) excursion is **23.28 h** on the raw/strict
clock, or **30.0+ h** on the 60-min-gap clock. Either way it is already
**4–5× longer than the single longest completed excursion ever
recorded** (5.92 h raw, or 21.53 h for the one completed 60-min-gap
episode) and it is still open at the moment the data was pulled — a
clear outlier by duration, and one where the outlier-ness is
understated because it hasn't finished yet.

## 4. Decay behavior

Two distinct behavioral phases are visible inside the single onset event:

- **2026-08-20 05:30 → ~2026-08-21 07:00 ("flicker" phase, ~29 h):**
  turbulence repeatedly spiked to 0.964–0.984, then dropped fast — most
  reversions were minutes, essentially all under ~2.4 h (p95 above).
  Decay, when it happened, was **fast** (single-digit minutes to low
  single-digit hours).
- **~2026-08-21 07:11 / 11:10 → 2026-08-22 10:27 (current, ~23–30 h):**
  zero reversions below 0.95. The last 203 consecutive readings range
  0.956–0.984, with **64% of them sitting exactly at the series' global
  ceiling (0.984)**. This is not a metric hovering near a noisy
  boundary — it is pinned at (or within one tick of) the maximum value
  the instrument has ever produced in 40 days of data.

So: decay **was** fast during the flicker phase, but that pattern
**broke** roughly a day ago and has not resumed since. Extrapolating
the early fast-decay behavior onto the current stretch is not supported
by the last 23+ hours of readings — the current tail looks
qualitatively different (locked at ceiling, not a boundary bounce).

## 5. `regime_crisis` vs `turbulence_pct ≥ 0.95`

Row-level cross-tab (14,464 rows):

|  | turb < 0.95 | turb ≥ 0.95 |
|---|---|---|
| `regime_crisis`=0 | 12,979 | 0 |
| `regime_crisis`=1 | 0 | 1,485 |

**100% agreement, both directions**, in this dataset: every
`regime_crisis==1` row has `turbulence_pct≥0.95` and vice versa. Among
crisis rows, only **6.6%** also have the asset's own `vol_percentile ≥
0.95`. In the history captured here, the cross-asset turbulence term is
the dominant — in fact, in this sample, the *exclusive observed*
trigger of `regime_crisis`; own-asset volatility essentially never
independently produces a crisis label. (This is a description of what
happened in this window, not a claim about the code path's logic,
which was not inspected here.)

## 6. Statistical honesty / effective-N caveats

- **14,464 rows are not 14,464 independent observations.** Rows are
  event-driven, multiple assets share a timestamp, and `turbulence_pct`
  is a single cross-asset scalar duplicated across every asset row at
  that instant (median distinct-value count per timestamp: 1). The
  true unit of observation for turbulence is **one number per unique
  `ts`** — 7,236 unique timestamps, still highly autocorrelated in
  time (adjacent readings are nearly identical).
- **Sampling cadence is not stationary.** Rows/day ranged ~16–367
  before 2026-08-20 and jumped to ~87–298/day during the active window
  — part of the apparent "10.3% of rows are crisis" figure is an
  artifact of denser sampling during the crisis itself, not a
  time-stationary duty cycle. Read §1's calendar-time framing, not the
  row-count framing, as the meaningful number.
- **Effective episode count ≈ 1.** Every quantity in §3–§4 about "how
  episodes behave" is drawn from the *same* onset event (its internal
  micro-spikes are correlated bounces within one evolving transition,
  not independent trials). The "40 completed excursions, median 2.25
  min" statistic describes the flicker phase of this one event, not a
  population of historically distinct crises. Treat any decay-time
  estimate as **anecdote from n=1**, not an interval with real
  coverage.
- **The current episode is right-censored.** Its true duration is
  unknown and at least 23.3–30.0 h as of the data cutoff; it may be
  materially longer by the time this is read.

## Answer: is the stall self-resolving?

**The data does not support a confident yes or no, and says so
honestly rather than pattern-matching to the early fast bounces.**
There is exactly one turbulence excursion above 0.95 in this bot's
entire 40-day recorded history — this one, currently in progress — so
there is no base rate to forecast a resolution time from. What can be
said with the available evidence:

- The *early* hours of this same event did resolve repeatedly and fast
  (median ~2 min, 95th pct ~2.4 h) — if the current stretch behaved
  like that, self-resolution would already have happened many times
  over.
- It has not. For the last 23–30 hours running, turbulence has shown
  **zero reversions** and has spent most of that time pinned at the
  instrument's observed ceiling (0.984). That is a different regime
  than the flicker phase, not a continuation of it.
- Given n_effective≈1 event with no completed analogue this long, any
  ETA for self-resolution — hours vs. days — would be extrapolation
  past the data, not a measurement. The honest statement is: **no
  evidence of imminent self-resolution as of 2026-08-22 10:27 UTC; the
  only comparable behavior on record (the flicker phase) stopped
  applying about a day ago, and nothing in the series since then points
  to when or whether it starts applying again.**

This is a description of the `turbulence_pct` series only. Whether that
is itself the right signal to trust here is a separate question the
operator adjudicates (see CLAUDE.md "the instrument is the first
suspect" — this note characterizes the instrument's own history, it
does not corroborate it against an independent route).
