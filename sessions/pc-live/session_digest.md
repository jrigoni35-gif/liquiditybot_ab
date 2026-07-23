# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-07-23 20:43 UTC (324.83h, ~1393 cycles)
- Equity: $25,000.00 -> $4,965.98 (range $99,208.70) | realized PnL $-19.92 | fees $34.32
- Activity: 3 open | 237 live labeled trades | 3316 candidates | 203 postmortems
- Model: level 2 | use_model=False | brier n/a | history_rows 237 | cold=True
- Audit: 4518 records (1960 non-routine) | dominant OM-000 (27% of non-routine) | chain_ok=False (tamper=False, seams=2) | retrain_requests 35
- Liquidity: spoofy 77% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=237, brier=n/a) yet retrain was requested 35x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 27% of the audit trail
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 77% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  2 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
