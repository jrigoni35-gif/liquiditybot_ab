# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-01 03:56 UTC (524.05h, ~3123 cycles)
- Equity: $25,000.00 -> $4,940.44 (range $99,208.70) | realized PnL $-32.74 | fees $54.29
- Activity: 1 open | 268 live labeled trades | 7503 candidates | 228 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 268 | cold=True
- Audit: 27747 records (25125 non-routine) | dominant SZ-047 (89% of non-routine) | chain_ok=False (tamper=False, seams=5) | retrain_requests 62
- Liquidity: spoofy 51% of classified cycles | feed errors 5

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=268, brier=n/a) yet retrain was requested 62x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 89% of the audit trail
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 51% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 89% of 25125 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  5 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
