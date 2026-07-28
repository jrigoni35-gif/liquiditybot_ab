# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-07-28 14:54 UTC (439.01h, ~1308 cycles)
- Equity: $25,000.00 -> $4,963.58 (range $99,208.70) | realized PnL $-20.97 | fees $37.49
- Activity: 1 open | 248 live labeled trades | 5466 candidates | 208 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 248 | cold=True
- Audit: 18903 records (16337 non-routine) | dominant SZ-047 (86% of non-routine) | chain_ok=False (tamper=False, seams=5) | retrain_requests 49
- Liquidity: spoofy 56% of classified cycles | feed errors 1

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=248, brier=n/a) yet retrain was requested 49x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 86% of the audit trail
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 56% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 86% of 16337 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  5 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
