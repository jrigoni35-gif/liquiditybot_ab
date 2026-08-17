# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-17 16:34 UTC (920.69h, ~2607 cycles)
- Equity: $25,000.00 -> $798.79 (range $99,208.70) | realized PnL $-0.05 | fees $3.13
- Activity: 3 open | 332 live labeled trades | 10545 candidates | 283 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 332 | cold=True
- Audit: 45225 records (35286 non-routine) | dominant SZ-047 (63% of non-routine) | chain_ok=False (tamper=False, seams=8) | retrain_requests 118
- Liquidity: spoofy 60% of classified cycles | feed errors 269

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=332, brier=n/a) yet retrain was requested 118x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 63% of the audit trail
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 60% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 63% of 35286 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
