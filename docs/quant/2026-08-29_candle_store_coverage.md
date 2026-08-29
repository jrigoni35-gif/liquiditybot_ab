# Candle store — first real backfill, and what history we can actually obtain

**Class: SAFE.** Measurement only. This session fetched public OHLC from
three read-only venues into `outputs/candles/` and queried it. No decision
path, feature vector, veto, sizing rule, fill sim or order lifecycle was
touched or imported. `data/candle_journal.py` remains imported by nothing
under `main.py`, `runner.py`, `ml/`, `core/`, `execution/`, `risk/`,
`regime/`, `strategies/`, `sentiment/`, `api/`.

**The deliverable is the truth about reachable history, not a success
claim.** The headline is a limitation, and it is in §4.

---

## 0. Snapshot stamps and provenance

Every number below is tagged `[K]` (read from a running instrument this
session), `[I]` (inferred), or `[UNKNOWN]`. Live files mutate; each is
stamped with the epoch second it was read.

| artifact | read at (unix s) | read at (UTC) |
|---|---|---|
| `outputs/signal_history.csv` — asset census | 1788022394 | 2026-08-29T16:53:14Z |
| `outputs/signal_history.csv` — anchor sweep | 1788022648 | 2026-08-29T16:57:28Z |
| `outputs/signal_history.csv` — final row count | 1788022909 | 2026-08-29T17:01:49Z |
| `candle_store.py verify --deep` | 1788022856 | 2026-08-29T17:00:56Z |
| per-lane coverage table (§3) | 1788022869 | 2026-08-29T17:01:09Z |

`signal_history.csv` is written by the live runner and grew during the
session: 19,284 → 19,287 → 19,288 rows across those three reads `[K]`.
Percentages in §4 are computed against the 19,287-row snapshot and are
as-of that read, never "current".

**Store identity as of 1788022856** `[K]`:

```
segments          1        (outputs/candles/journal/2026-08.v1.csv)
bar_rows          89581
coverage_rows     82
conflicts         0
lanes             74
content_digest    e1d6ef6f60255a66511ac45b370b0e73f67cf8b2e55c940b11e2b72750040cae
canonical_digest  4d19029c411fbab27d4440125385d039b8ccf32386b147d3a8e53528f77ddb8b
deep_matches      true
```

`deep_matches: true` is the store's own instrument-verification hook: the
journal was recompacted into a throwaway directory and the incremental and
full canonical digests were asserted equal. On-disk size 10,964,092 bytes
across 48 files `[K]`, read 1788022909.

Re-derive all of it with `python scripts/candle_store.py verify --deep`.
Nothing volatile is asserted here as durable.

---

## 1. The asset list, derived not guessed

Assets were taken from the `asset` column of `outputs/signal_history.csv`,
read 1788022394 `[K]`. Fifteen distinct values, with row counts:

| asset | rows | asset | rows | asset | rows |
|---|---:|---|---:|---|---:|
| ETH | 3560 | PAXG | 1194 | XRP | 976 |
| BTC | 2125 | DOGE | 1183 | FLOW | 883 |
| DOT | 1620 | SUI | 1171 | SOL | 580 |
| ARB | 1614 | ADA | 1115 | AVAX | 476 |
| MINA | 1553 | LINK | 1036 | LTC | 198 |

Note this is **wider than `config.exchanges.kraken.trading_pairs`**, which
lists 7 `[K]`. Eight assets (DOT, DOGE, ADA, LINK, XRP, SOL, AVAX, LTC)
appear in the corpus without being configured trading pairs. All fifteen
were backfilled; deciding what that gap means is not this document's job.

**Corpus window** `[K]`, from the same column set, read 1788022648:
`signal_ts` ∈ [**1783946147**, **1787961000**] inclusive
= 2026-07-13T12:35:47Z → 2026-08-28T23:50:00Z = **46.47 days**.

## 2. Interval choice, and why

The consumer is horizon-stratified analysis over **hours to days** (the
liquidity-footprint thesis; `docs/quant/2026-08-29_fee_dominance_diagnosis.md`).

* **3600 s (1h)** — the finest grid whose anchor error (≤ 59 min) is small
  against a 24 h horizon. The primary study grid.
* **14400 s (4h)** — chosen *after* measuring Kraken's cap (§4). At 720
  bars, 4h reaches 120 days on the **execution venue at the correct
  quote**, where 1h reaches only 30. It buys corpus coverage with anchor
  precision.
* **86400 s (1d)** — multi-day context and the 720-day regime backdrop.

300 s (5m) was **not** fetched: at Kraken's 720-bar cap it reaches 2.5
days, which answers nothing this study asks, and it is the grid
`scripts/candle_collect.py` accumulates forward at zero API cost.

---

## 3. ACTUAL COVERAGE — per (source, quote, interval)

Read 1788022869. Every lane holds **one contiguous coverage window**;
`holes_in_covered` is **0 across all 74 lanes** `[K]`.

| source/quote | interval | lanes | bars | earliest bar open | latest bar open | span | holes |
|---|---:|---:|---:|---|---|---:|---:|
| kraken/USD | 1h | 15 | 10,804 | 1785427200 · 2026-07-30T16:00Z | 1788015600 · 2026-08-29T15:00Z (11 lanes)<br>1788019200 · 2026-08-29T16:00Z (4 lanes) | 30.0 d | 0 |
| kraken/USD | 4h | 15 | 10,800 | 1777651200 · 2026-05-01T16:00Z | 1788004800 · 2026-08-29T12:00Z | 119.8 d | 0 |
| kraken/USD | 1d | 15 | 10,800 | 1725753600 · 2024-09-08T00:00Z | 1787875200 · 2026-08-28T00:00Z | 719 d | 0 |
| okx/USDT | 1h | 15 | 43,188 | 1777654800 · 2026-05-01T17:00Z | 1788015600 · 2026-08-29T15:00Z (12 lanes)<br>1788019200 · 2026-08-29T16:00Z (3 lanes) | 119.9 d | 0 |
| binanceus/USD | 1h | 14 | 13,989 | see §5 — **two disjoint populations** | | | 0 |

All fifteen assets are present in every kraken and okx lane group `[K]`.

**Ragged right edge is expected, not a fault.** A multi-lane run that
straddles an hour boundary leaves earlier lanes one bar shorter than later
ones. Measured directly: the second pass started 1788022785
(16:59:45Z) and ended 1788022826 (17:00:26Z), so 4 of 15 kraken 1h lanes
(AVAX, FLOW, LTC, SOL) and 3 of 15 okx lanes (BTC, ETH, SUI) picked up the
16:00Z bar and the rest did not `[K]`. **Any statistic pooled across lanes
must clamp to the minimum right edge, or the last bar is a lane-selection
artifact.**

*(An arithmetic prediction of 89,592 rows was made before reading the
store and was WRONG; the store's 89,581 is right. The 11-row gap is
exactly the 11 kraken 1h lanes that had not yet crossed the hour boundary
— 11×720 + 4×721 = 10,804. Recorded because the reconciliation is what
established the count, not the prediction.)*

### 3b. Independent corroboration that these are real prices

The store's own report is a claim about the store. Two second routes:

1. **Cross-venue basis.** ETH kraken/USD vs okx/USDT, 1h, over the full
   720-slot overlap: median basis **+0.0865 %**, range **[−0.0979 %,
   +0.1662 %]**, n=720 `[K]`. Two independent venues agree to within 17 bps
   — the USDT/USD basis, exactly the residual expected if both are real.
2. **Against the bot's own recorded prices.** For every corpus row with a
   positive `entry_price`, is that price inside the hourly bar containing
   its `signal_ts`? kraken/USD: **9,836 of 9,929 = 99.06 %** inside;
   the 93 outside have median |dev| 0.339 %, max 1.622 %. okx/USDT:
   **89.81 %** inside (median |dev| of the misses 0.0513 %) — lower
   precisely because of the quote basis `[K]`.

Route 2 also measures the problem the store exists to solve: only **9,929
of 19,287** corpus rows (51.5 %) carry a usable positive `entry_price`
`[K]`. The self-join route is missing on ~48 % of rows before any
horizon arithmetic begins.

---

## 4. VENUE REACH vs CORPUS NEED — the headline limitation

### Reach, measured (not read off a docstring)

| venue | endpoint behaviour | measured reach at 1h |
|---|---|---|
| Kraken | 720 bars/interval, `since` does not page backward | **30.0 days** `[K]` |
| Kraken @ 4h | same 720-bar cap, coarser grid | **119.8 days** `[K]` |
| Kraken @ 1d | same cap | **719 days** `[K]` |
| OKX | `/market/history-candles`, `after` cursor pages backward | **119.9 days at `--total 2880`** `[K]`; deeper on request, not tested |
| Binance.US | shipped client sends symbol/interval/limit only — one page | **41.6 days** (999 bars, cap 1000) `[K]` |

### The need

The corpus spans **46.47 days** (§1), and a 7-day horizon needs another 7
days of forward bars beyond the last anchor.

### THE LIMITATION, STATED LOUDLY

> **KRAKEN — THE EXECUTION VENUE, AT THE QUOTE THE BOT ACTUALLY TRADES —
> CANNOT SERVE THE CORPUS WINDOW AT 1-HOUR RESOLUTION. Its 720-bar cap
> stops at 2026-07-30T16:00Z; the corpus begins 2026-07-13T12:35:47Z. The
> first 17.1 days of the corpus — 6,956 of 19,287 rows, 36.1 % — are
> UNREACHABLE at 1h on kraken/USD and will never become reachable: `since`
> does not page backward, so this history is gone unless a venue that
> keeps it is used instead.**
>
> **BINANCE.US IS ALSO SHORT.** Through the shipped client its 41.6-day
> reach stops at 2026-07-19T01:00Z — still 5.7 days after the corpus
> begins.

Measured anchor reachability, all 19,287 corpus anchors floored onto each
lane's grid, read 1788022648 / 1788022751 `[K]`:

| lane | H=4h | H=24h | H=72h | H=7d |
|---|---:|---:|---:|---:|
| **kraken/USD 1h** | 63.9 % | **63.8 %** | 56.9 % | 40.6 % |
| **kraken/USD 4h** | 100.0 % | **99.8 %** | 93.0 % | 76.7 % |
| **okx/USDT 1h** | 100.0 % | **99.8 %** | 93.0 % | 76.7 % |
| **binanceus/USD 1h** | 64.8 % | 64.8 % | 61.0 % | 51.4 % |

Reason decomposition at H=24h, kraken/USD 1h: `OK` 12,300 ·
`anchor_BEFORE_LEFT_EDGE` 6,956 · `forward_BEYOND_RIGHT_EDGE` 31 `[K]`.
Nothing is `NO_BAR_IN_COVERED_WINDOW` — there are no holes, only an edge.

The 7-day column's loss is **right-censoring, not a hole**, and it is
identical across the two full-coverage lanes: 19,287 − 14,794 = **4,493**
anchors in both, the corpus rows within 7 days of the right edge `[K]`.
That two independently-built lanes lose the *same* 4,493 rows is itself a
check that the censoring accounting is correct.

### The consequence for the horizon study — a three-way trade-off

There is no lane that is simultaneously (a) the execution venue at the
traded quote, (b) 1-hour granular, and (c) corpus-complete. Pick two:

| want | lane | what you give up |
|---|---|---|
| right venue + right quote + full corpus | **kraken/USD 4h** | anchor precision: floor error up to 3 h 59 m (≈16 % of a 24 h horizon) |
| right venue + right quote + 1h precision | **kraken/USD 1h** | 36.1 % of anchors — and the missing 36.1 % is the *oldest* third, i.e. missing-not-at-random in time |
| 1h precision + full corpus | **okx/USDT 1h** | the quote confound: USDT ≠ USD, measured basis median +0.087 %, range 26 bps |

**Recommended primary: `kraken/USD` @ 4h**, with `okx/USDT` @ 1h as the
precision cross-check and the two required to agree in sign before any
conclusion is drawn. Rationale: a 26-bps quote confound is a *bias* that
survives resampling, while the 4h floor error is *noise* that a
sign-consistency check exposes. Neither substitutes for the other.

---

## 5. VENUE PATHOLOGY FOUND — Binance.US serves a delisted pair's frozen tail

Not anticipated by any survey; found by running it `[K]`.

* `MINAUSD` → **HTTP 400 Bad Request**. Recorded `status=EMPTY`, coverage
  claims nothing, `covered_windows == []`, queries return `NOT_COVERED`.
  Correct behaviour: a failed fetch never widens coverage.
* `ARBUSD`, `PAXGUSD`, `FLOWUSD` → **HTTP 200 with 1,000 bars from
  2023**. Window `1684234800` → `1687831200`
  (2023-05-16T11:00Z → 2023-06-27T02:00Z). These USD pairs were delisted;
  the klines endpoint still serves the frozen final page and **says nothing
  about it**. Requesting the most recent 1,000 bars returns three-year-old
  data with a 200 status and a well-formed body.

**This is the exact "confident instrument, wrong, nothing flagging it"
shape CLAUDE.md's mindset section names.** A store without honest coverage
bookkeeping would have written 2023 prices into a lane an analyst reads as
"recent", and every ARB/PAXG/FLOW horizon number would have been silently
wrong.

**The store contained it. Verified by query, not by reading the code**
`[K]`:

```
ARB  binanceus/USD 1h  window (1684234800, 1687831200)
  forward_return(1785427200 = 2026-07-30T16:00Z, 24h) -> (None, 'anchor_BEYOND_RIGHT_EDGE')
MINA binanceus/USD 1h  window []
  forward_return(1785427200, 24h)                     -> (None, 'anchor_NOT_COVERED')
```

No number was returned. The five-way epistemic split earned its keep on
its first contact with a real venue.

**NAMED TRAP for the next reader:** `candle_store.py lanes` shows
`ARB/PAXG/FLOW binanceus/USD` with ~1,000 rows each. **They are 2023 data.**
A lane being populated is not a lane being current — read `t_min_s`/
`t_max_s`, never the row count. Those rows are kept, not deleted: the store
is append-only by design, and a delisting is a fact about the venue that
analysis should be able to see.

---

## 6. IDEMPOTENCY — proven on real venue data

**Test A — byte identity, single lane.** ETH kraken/USD 1h backfilled at
1788022427, re-run at 1788022441 (14 s later, different wall clock, so
`ingest_s` would differ on any appended row) `[K]`:

| file | sha256 (run 1) | bytes | sha256 (run 2) | bytes |
|---|---|---:|---|---:|
| `journal/2026-08.v1.csv` | `8fb8eee7…049fd6` | 74,292 | `8fb8eee7…049fd6` | 74,292 |
| `coverage/2026-08.v1.csv` | `1c98cfde…a228d0` | 312 | `1c98cfde…a228d0` | 312 |

Second run report: `offered 720, accepted 0, dup 720, conflict 0`.
**Zero bytes appended to either file.**

**Test B — 48 lanes over an overlapping range.** All 45 kraken lanes
(15 assets × 1h/4h/1d) plus 3 okx lanes re-run at 1788022785–1788022826
`[K]`. Result: every 4h lane and every 1d lane reported
`accepted 0, dup 720` and appended nothing. The 1h lanes reported
`dup 719, accepted 1` — the run crossed 17:00Z and the 16:00Z bar had
newly committed. **That is coverage widening, not a duplicate**, and it is
the discriminating outcome: the mechanism accepted exactly the one bar that
was genuinely new and rejected all 719 it already held, at a completely
different `ingest_s`.

Store-wide digests bracketing test B `[K]`:

```
before  read_at_s 1788022778
  content_digest    9b11eddc…3a658    journal 8,937,218 B
  canonical_digest  e01d1cd0…f43bd
after   read_at_s 1788022826
  content_digest    e1d6ef6f…040cae   journal 8,937,914 B   (+696 B)
  canonical_digest  4d19029c…7ddbd
```

+696 bytes for 18 genuinely-new bars (15 kraken 1h that had crossed the
hour + 3 okx) ≈ 38.7 B/row `[K]` — consistent with the row format, and
with the 30 lanes that crossed no boundary appending nothing at all.

**What this proves:** re-running a backfill over an already-covered range
appends zero bytes. **What it does not prove:** that a run appends nothing
*ever* — a lane whose venue has committed a new bar since the last run
will and must grow.

---

## 7. WHAT THIS STORE CANNOT ANSWER

Read this before quoting any number the store produces.

1. **Anything before 2026-07-30T16:00Z at 1h on the venue the bot trades.**
   36.1 % of corpus anchors. Not curable by re-running: Kraken's `since`
   does not page backward. The only routes are a coarser Kraken grid (4h,
   which we took) or a different venue at a different quote.
2. **Anything before 2026-05-01T16:00Z at any sub-daily resolution, on any
   venue reached here.** Sub-daily history older than ~120 days does not
   exist in this store. `[UNKNOWN]` whether OKX would serve deeper than the
   2,880 bars requested — not tested, and it is a `--total` change away
   from being answerable.
3. **A USD price before 2026-07-30 at 1h.** Only okx/**USDT** covers that
   window at 1h. The basis is small (median +0.087 %) but it is a *bias*,
   not noise, and it is exactly the two-disjoint-populations-under-one-name
   shape the era-confound rules refuse. The store keeps the quote in the
   lane key so this cannot be pooled by accident.
4. **A forward return within 7 days of the right edge.** 4,493 corpus
   anchors are right-censored at H=7d. That is missing-not-at-random on the
   *trailing* edge; excluding them silently biases any long-horizon
   statistic toward whatever regime the older rows sat in.
5. **Sub-hour price paths.** The finest grid stored is 1h. Intrabar
   sequencing — which barrier a triple-barrier label touched first — is
   **not answerable**, and no OHLC store can answer it. The bot's live
   labeler works on a 5m grid; this store does not reconstruct that.
6. **Anything about a bar's interior.** `close` is the price at
   `t_open_s + interval_s`; `high`/`low` bound the interval but carry no
   timestamp. A 24h forward return from a 4h anchor carries up to 3 h 59 m
   of anchor error and the store cannot narrow it.
7. **Whether a price is what the bot could have transacted at.** These are
   public OHLC prints. Spread, depth, slippage and fees are not here and
   must come from the fill ledger and `cost_truth_report`. A gross forward
   return from this store is *gross* — under the cut-#8 fee truth (40/80
   bps, 1.2 % round-trip) it is roughly 120 bps away from anything
   decision-relevant.
8. **The eight non-configured assets' tradability.** DOT, DOGE, ADA, LINK,
   XRP, SOL, AVAX and LTC appear in the corpus but not in
   `config.exchanges.kraken.trading_pairs` `[K]`. The store holds their
   prices; whether the bot could have traded them is `[UNKNOWN]` here.
9. **Volume comparability across sources.** `volume` is stored per venue
   and is not normalised. Kraken and OKX report different quantities on
   different bases; the config's own candle note cites external reported
   volume being >70 % fabricated. Treat cross-venue volume as
   `[UNKNOWN]`, not as a series.
10. **Any pooled statistic across lanes without clamping the right edge**
    (§3) — the last bar is present in some lanes and not others.

---

## 8. Commands to re-derive everything above

```bash
python scripts/candle_store.py verify --deep
python scripts/candle_store.py lanes
python scripts/candle_store.py coverage --symbol ETH --interval 3600 \
    --source kraken --quote USD --from-s 1785427200 --to-s 1788015600
python scripts/candle_backfill.py --dry-run --venue kraken --quote USD \
    --symbols ETH --interval 3600
```

No count in this document is durable. Every one of them is stamped in §0
and re-derivable with the commands above; where they disagree with a later
run, the later run is right.
