# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-13 21:55 UTC (830.04h, ~891 cycles)
- Equity: $25,000.00 -> $798.07 (range $99,208.70) | realized PnL $-1.25 | fees $1.26
- Activity: 4 open | 322 live labeled trades | 10111 candidates | 278 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 322 | cold=True
- Audit: 44796 records (34908 non-routine) | dominant SZ-047 (64% of non-routine) | chain_ok=False (tamper=False, seams=6) | retrain_requests 107
- Liquidity: spoofy 57% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=322, brier=n/a) yet retrain was requested 107x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 64% of the audit trail
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 57% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 64% of 34908 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  6 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
