# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-14 21:56 UTC (854.05h, ~778 cycles)
- Equity: $25,000.00 -> $797.86 (range $99,208.70) | realized PnL $-1.17 | fees $1.86
- Activity: 4 open | 326 live labeled trades | 10222 candidates | 279 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 326 | cold=True
- Audit: 44973 records (35044 non-routine) | dominant SZ-047 (64% of non-routine) | chain_ok=False (tamper=False, seams=6) | retrain_requests 111
- Liquidity: spoofy 52% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=326, brier=n/a) yet retrain was requested 111x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 64% of the audit trail
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 52% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 64% of 35044 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  6 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
