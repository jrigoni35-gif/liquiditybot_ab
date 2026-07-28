# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-07-28 02:53 UTC (427.0h, ~1830 cycles)
- Equity: $25,000.00 -> $4,964.13 (range $99,208.70) | realized PnL $-20.34 | fees $36.99
- Activity: 1 open | 246 live labeled trades | 5270 candidates | 207 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 246 | cold=True
- Audit: 17026 records (14462 non-routine) | dominant SZ-047 (85% of non-routine) | chain_ok=False (tamper=False, seams=5) | retrain_requests 47
- Liquidity: spoofy 60% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=246, brier=n/a) yet retrain was requested 47x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 85% of the audit trail
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 60% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 85% of 14462 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  5 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
