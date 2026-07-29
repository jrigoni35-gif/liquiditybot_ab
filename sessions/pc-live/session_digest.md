# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-07-29 00:54 UTC (449.01h, ~772 cycles)
- Equity: $25,000.00 -> $4,962.87 (range $99,208.70) | realized PnL $-21.48 | fees $38.16
- Activity: 0 open | 251 live labeled trades | 5666 candidates | 210 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 251 | cold=True
- Audit: 20497 records (17930 non-routine) | dominant SZ-047 (87% of non-routine) | chain_ok=False (tamper=False, seams=5) | retrain_requests 50
- Liquidity: spoofy 59% of classified cycles | feed errors 1

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=251, brier=n/a) yet retrain was requested 50x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 87% of the audit trail
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 59% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 87% of 17930 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  5 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
