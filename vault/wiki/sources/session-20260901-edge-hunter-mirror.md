---
title: "Edge-hunter mirror — costs from fills, the empty offensive half, condensation, years of data, our own errors (2026-09-01)"
category: source
type: session
date: 2026-09-01
head: 1d751e22 (+ uncommitted working tree at write time)
summary: Six-part operator objective measured end-to-end; the one structural discovery is that Kraken's public /Trades endpoint reaches trade id 1 (2013) with native aggressor side, and the one deciding measurement so far says the stored L2 book feature is NOT reconstructable from that tape
tags: [markout, fees, features, data, tape, minbtl, instrument]
status: PARTIAL — ETH/BTC replication of the tape-proxy result and deep-research #3 angles 4–5 still owed
---

# Edge-hunter mirror (2026-09-01)

**Operator objective (verbatim intent):** "become more like a professional trader by knowing where the money comes from … mirror and capture what a pro edge-hunter's bot knows": (1) costs from fills not schedules; (2) fill the empty offensive half; (3) condense the 64-feature/1-bit model; (4) years of data across many assets against 50 loadable days; (5) inspect basic human/LLM error; (6) do not assume, study manipulation for detection only. Items 2/3 are decision-path → proposals for adjudication, not code. Everything below is SAFE-class measurement.

## Findings, with the artifact each rests on

| # | finding | artifact | tag |
|---|---|---|---|
| 1 | The champion is judged on **23.73 d** (12,066 rows, 2026-08-09T01:00Z → 09-01T18:35Z), not the 50.1 d in `1d751e22`'s subject (raw file span). SE of an annualized Sharpe at true zero ≈ 3.9. | `scripts/champion_skill_report.py --json` → `corpus_span_days` (double-derived via `HistoryStore.load_training_data`) | [K] |
| 2 | Markout decomposition (n=519 scored entries): arrival→fill **−15.1 bps** (maker −17.6 / taker +1.0), fill→1h **−4.1 bps (−0.7 SE)**, placebo shifts clean. Adverse component is mechanical limit distance; no post-fill toxicity at candle horizons. | `scripts/markout_report.py` (promoted from scratch `markout_candles.py`, byte-identical numbers) | [K] |
| 3 | Fee spend by purpose: hedge + hedge-unwind **$313.51 = 80.5% of $389.36 lifetime fees**, ALL from the 2026-08-07 ADA hedge churn (fixed `cf454d5e`). Strategy fees era 7/8/9 = $7.43/$0.98/$1.90. | `outputs/fills.csv` (1,201 rows, read 17:55Z); `cost_truth_report.py` is rate-based and uncontaminated | [K] |
| 4 | Fill-conditioning contrast: OM-040 expired n=463 vs filled 534 (fill ratio 0.54); ≤4h gap <1 SE; 24h **+75 bps (+2.2 SE) killed by its own time-shift placebo**. | scratch `unfilled_markout.py` (not promoted) | [K] |
| 5 | Feature-concentration scan: **0/64 features above the null band, every family ≤ 0**; greedy k=6 +0.0034 (search-biased). Condensation must change the TARGET, not the list. | scratch `feature_concentration.py`; capacity ladder in `champion_skill_report.py --ladder` | [K] |
| 6 | **Kraken `/0/public/Trades` with `since=0` returns XBTUSD trade id 1 (2013-10-06); every row carries aggressor side b/s and otype m/l.** Free signed tape for every pair. Research #2 had this UNVERIFIED and assumed tick-rule. | scratch `trades_reach.py`, 23:04Z; endpoint contract in `scripts/kraken_trades_backfill.py` docstring | [K] |
| 7 | Tape cost: window 2026-07-13→now over 14 filled pairs = **8.56M trades ≈ 8.6k calls**; lifetime ≈ 349M. Sustained rate limit **~1/s** (3/s tripped `EGeneral:Too many requests` after 66 calls at 23:09Z). | scratch `trades_volume.py`; backfill run log | [K] |
| 8 | Tool shipped: `scripts/kraken_trades_backfill.py` + 11 tests (int-only ns cursor, stall guard, idempotent month parquet, credential-free client). 12/14 pairs fully backfilled by 2026-09-02T01:00Z; ETH/BTC/FLOW relaunched after the first detached run died mid-ETH. | `outputs/ticks/kraken/<PAIR>/`, `--coverage` | [K] |
| 9 | **Tape-proxy, REPLICATED on 6 pairs: the stored L2 `imbalance_dir` is NOT reconstructable from the tape** — Spearman ≈ 0 at 60 s (−0.021…+0.058) and +0.055…+0.191 at 3600 s. The stored feature also scores AUC ≤ 0.50 vs label on all six. | scratch `tape_proxy.py` (ADA/SOL/XRP/DOGE/LINK/DOT) | [K] |
| 9b | **The one apparent tape lead was REFUTED the same session: barrier-geometry tautology.** `log n_60` (trade-count intensity) scores 0.52–0.58 vs the raw label, 4/6 CI-significant. Same feature, same rows, three targets: RESOLUTION (barrier hit at all vs time-out) mean AUC **0.616**; DIRECTION given resolution mean **0.510 with 0/7 pairs CI-significant**; raw label 0.539 = the blend. Activity predicts that the path resolves, not which way. Second instance of the shape that killed the T2 magnitude lead (`2f8550de`). | scratch `tape_tautology.py`, 7 pairs, triple-barrier eras | [K] |
| 10 | `ofi_dir` is zero on 19,661/22,442 rows: computed from EXTERNAL venue books only (`liquidity_model.py:338`) and OKX/Binance.US carry ETH/BTC only → structurally zero for 13/15 assets. Shadow feature by design; the feature count is ≤63 for most assets. | `signal_history.csv` groupby asset; `config.json` exchanges | [K] |
| 11 | `test_archetype_battery::test_battery_end_to_end_pins` flakiness = live-writer race: the runner appends to `outputs/audit.jsonl` (+752 B/30 s) during the ~26 s size compare. | agent measurement 18:12Z | [K] |
| 12 | Deep-research #3 (consequences) PARTIAL — 86/108 agents, synthesis failed on the account session limit; angles 4–5 UNRUN. Survivors: Suhonen et al **median 73%** backtest→live Sharpe deterioration; McLean–Pontiff 26%/58%; Dwork reusable holdout 63%-from-noise; Johari ~5× Type-I under continuous monitoring. | `raw/research/2026-09-01_deep_research_measurement_consequences.md` | [K] |

## What this does NOT establish
- **No tape-derived skill is claimed — the opposite.** The one candidate (activity intensity) was decomposed and died as a barrier-geometry tautology (finding 9b). The offensive half remains empty after the tape was brought in.
- **New standing rule earned here:** a feature scored against a triple-barrier label must be split into RESOLUTION (did the path reach a barrier before the time-out) and DIRECTION (given it did, which one). Only the second is an edge. A raw-label AUC blends them, and volatility loads the first.
- Nothing here changes the standing model freeze or the era-6 moratorium; the condensed-model proposal (target change) goes to the ALGO-5/GB-1 adjudication.
- The pasted "LLM inconsistency" claims remain unsourced (angle 4 unrun).

## Links
[[concepts/false-strategy-theorem-and-minbtl]] · [[concepts/the-method]] · [[concepts/label-era]] · [[concepts/partial-identification]] · raw: `raw/research/2026-09-01_deep_research_data_scarcity_historical_backfill.md`, `raw/research/2026-09-01_deep_research_measurement_consequences.md` · repo: `docs/HANDOFF.md` EDGE-HUNTER MIRROR block.
