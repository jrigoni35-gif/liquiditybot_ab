# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-01 01:56 UTC (522.04h, ~2890 cycles)
- Equity: $25,000.00 -> $4,940.16 (range $99,208.70) | realized PnL $-32.74 | fees $54.29
- Activity: 1 open | 268 live labeled trades | 7434 candidates | 228 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 268 | cold=True
- Audit: 27734 records (25115 non-routine) | dominant SZ-047 (89% of non-routine) | chain_ok=False (tamper=False, seams=5) | retrain_requests 61
- Liquidity: spoofy 52% of classified cycles | feed errors 4

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=268, brier=n/a) yet retrain was requested 61x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 89% of the audit trail
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 52% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 89% of 25115 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  5 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
