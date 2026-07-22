# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-07-22 17:42 UTC (297.82h, ~488 cycles)
- Equity: $25,000.00 -> $4,980.11 (range $99,208.70) | realized PnL $-9.71 | fees $23.55
- Activity: 5 open | 169 live labeled trades | 2691 candidates | 138 postmortems
- Model: level 2 | use_model=False | brier n/a | history_rows 169 | cold=True
- Audit: 3135 records (1246 non-routine) | dominant OM-000 (32% of non-routine) | chain_ok=False (tamper=False, seams=2) | retrain_requests 31
- Liquidity: spoofy 75% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=169, brier=n/a) yet retrain was requested 31x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 32% of the audit trail
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 75% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  OM-000 is 32% of 1246 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  2 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
