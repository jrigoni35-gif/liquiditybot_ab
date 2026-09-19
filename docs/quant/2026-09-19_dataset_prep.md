# Dataset prep for the 09-22 opening — swing-mechanics corpus (built 2026-09-19, SAFE-class)

**Classification: SAFE** — measurement/research data intake only. Binance is a
sanctioned READ-ONLY data venue (hard invariant 3 unaffected; Kraken remains
the sole execution venue). Nothing in the engine, config, or decision path
reads these files; nothing was imported by shipped code.

## What was downloaded and where

Root: `research/corpus/binance_vision/` (589 MB total).

| Artifact | Content |
|---|---|
| `raw_zips/` (100 MB) | 200 original monthly/daily zips from data.binance.vision, kept for provenance |
| `klines_1m_{BTC,ETH,LINK,PAXG}USDT.parquet` (~336 MB) | Native 1-minute klines, consolidated, deduped, timestamp-normalized |
| `klines_5m_{*.parquet` (~51 MB) | 5-minute resample — **the bot's decision cadence**; includes `source_bars` so partial bars are visible |
| `manifest.json` | Build stamp, source, job list, quality audit |
| Builder | `scripts/fetch_binance_vision_1m.py` (idempotent; re-run to extend) |

**Coverage:** 2024-01-01 00:00Z → 2026-09-18 23:59Z, all four era-9 core
pairs (universe per cut #11, 2026-09-07: PAXG/ETH/BTC/LINK — config `symbols`
+ liquidity-tier `_doc`). **1,428,480 1m rows / 285,696 5m bars per symbol.
Quality audit: 0 missing files of 200, 0 duplicate rows, 0 gaps on the 1m
grid for all four symbols.**

Columns per 1m row: OHLC, base/quote volume, trade count, **taker-buy
volumes** (aggressor split — the raw material for "how a swing happens":
initiated-buy imbalance vs price response), close_time. Timestamps
normalized to ms (Binance switched ms→us in 2025; the script handles both).

## Why this dataset suits this bot

1. **Cadence match.** Entries are 5-minute; the 5m parquet is the native
   frame. 1m is kept for fill-adjacent work (arrival→fill distance, the
   −15.1 bps mechanical component HANDOFF's edge-hunter section measured).
2. **Universe match.** Exactly the four core pairs — no irrelevant breadth,
   and PAXG (gold, near-zero crypto beta, `_paxg_doc`) gives the corpus a
   second regime family, which swing-failure analysis needs.
3. **Regime variety.** 2024 range → 2024-Q4 breakout → 2025 trends → 2026
   tape: enough swing anatomy (markup/markdown, failed breakouts, squeeze
   reversals) to study "what happens if you messed up" per swing type.
4. **Cost realism.** The bot's binding constraint is fees (null −0.273
   $/trip in force). Klines carry no fee/depth fields; cost modeling stays
   on the booked tier (15/30) and Kraken-side depth recordings. This corpus
   answers the *price-path* question, not the *executability* question —
   those stay separated by design.

## Venue cross-check (Kraken vs Binance, live pull 2026-09-19T~20Z)

Recent 5m closes, 467–468 matched bars per pair:

| Pair | median |Kraken−Binance| | max |
|---|---|---|
| BTC | 8.74 bps | 13.12 bps |
| ETH | 8.57 bps | 17.45 bps |
| LINK | 7.43 bps | 25.45 bps |
| PAXG | 8.87 bps | 26.47 bps |

A persistent ~7–9 bps offset (USD vs USDT quote basis), small against the
1.80% PT / 1.35% stop geometry but NOT negligible against the 30 bps taker
fee. **Consequence: use this corpus for swing *shape* and relative-path
research; venue-exact levels for any threshold work must come from Kraken**
(paginate `https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=1&since=`
— 720 candles/call; ccxt 4.5.64 is in the venv and wraps this).

## Intake map (how this meets the data we already compute)

- `outputs/fills.csv` (lifetime ledger, 1,371 legs at build) = what we
  *did*; this corpus = what the market *was* around and before it. Join key:
  UTC timestamp; era stamps via `exec_era`.
- `HistoryStore.load_training_data` teaches the model from labeled
  internal rows only; rows stamped with the live EXEC_ERA key
  (`python -c "from core.fill_ledger import EXEC_ERA; print(EXEC_ERA)"`)
  are dropped at the training filter at a 47.4% rate when filed with
  barrier='realized' under label_era='exit_sim' — re-derive with
  `scripts/discard_ledger.py`. This corpus is the external context those
  labels sit in; whether any of it enters a *training* corpus is a
  corpus-composition adjudication, not done here.
- Watch-lane precedent (`core/watch_lane.py`): external observations stay in
  a separate corpus with leak channels mutation-pinned. The same discipline
  applies to this dataset until the operator rules otherwise.

## Refresh

Re-run the script; it caches zips and picks up new completed months/days.
Current month is covered by daily files through yesterday (2026-09-18).
