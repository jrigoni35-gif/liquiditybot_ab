# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-07-23 23:43 UTC (327.84h, ~1724 cycles)
- Equity: $25,000.00 -> $4,965.79 (range $99,208.70) | realized PnL $-19.97 | fees $34.47
- Activity: 1 open | 239 live labeled trades | 3364 candidates | 204 postmortems
- Model: level 2 | use_model=False | brier n/a | history_rows 239 | cold=True
- Audit: 4989 records (2431 non-routine) | dominant SZ-047 (28% of non-routine) | chain_ok=False (tamper=False, seams=2) | retrain_requests 35
- Liquidity: spoofy 76% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=239, brier=n/a) yet retrain was requested 35x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 28% of the audit trail
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 76% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  2 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
