# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-07-23 21:43 UTC (325.83h, ~1501 cycles)
- Equity: $25,000.00 -> $4,965.90 (range $99,208.70) | realized PnL $-19.97 | fees $34.40
- Activity: 2 open | 238 live labeled trades | 3332 candidates | 204 postmortems
- Model: level 2 | use_model=False | brier n/a | history_rows 238 | cold=True
- Audit: 4685 records (2127 non-routine) | dominant OM-000 (25% of non-routine) | chain_ok=False (tamper=False, seams=2) | retrain_requests 35
- Liquidity: spoofy 76% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=238, brier=n/a) yet retrain was requested 35x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 25% of the audit trail
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 76% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  2 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
