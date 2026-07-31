# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-07-31 15:56 UTC (512.04h, ~1720 cycles)
- Equity: $25,000.00 -> $4,945.06 (range $99,208.70) | realized PnL $-27.33 | fees $50.27
- Activity: 3 open | 262 live labeled trades | 7098 candidates | 222 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 262 | cold=True
- Audit: 27585 records (24995 non-routine) | dominant SZ-047 (89% of non-routine) | chain_ok=False (tamper=False, seams=5) | retrain_requests 60
- Liquidity: spoofy 54% of classified cycles | feed errors 3

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=262, brier=n/a) yet retrain was requested 60x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 89% of the audit trail
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 54% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 89% of 24995 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  5 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
