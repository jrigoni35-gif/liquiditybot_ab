# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-07-31 06:55 UTC (503.04h, ~701 cycles)
- Equity: $25,000.00 -> $4,960.48 (range $99,208.70) | realized PnL $-21.72 | fees $39.61
- Activity: 3 open | 255 live labeled trades | 6811 candidates | 215 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 255 | cold=True
- Audit: 27486 records (24908 non-routine) | dominant SZ-047 (89% of non-routine) | chain_ok=False (tamper=False, seams=5) | retrain_requests 58
- Liquidity: spoofy 57% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=255, brier=n/a) yet retrain was requested 58x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 89% of the audit trail
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 57% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 89% of 24908 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  5 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
