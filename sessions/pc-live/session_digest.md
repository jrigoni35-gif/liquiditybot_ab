# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-07-24 17:44 UTC (345.84h, ~1546 cycles)
- Equity: $25,000.00 -> $4,965.86 (range $99,208.70) | realized PnL $-19.90 | fees $34.54
- Activity: 0 open | 240 live labeled trades | 3809 candidates | 204 postmortems
- Model: level 2 | use_model=False | brier n/a | history_rows 240 | cold=True
- Audit: 7165 records (4607 non-routine) | dominant SZ-047 (59% of non-routine) | chain_ok=False (tamper=False, seams=2) | retrain_requests 36
- Liquidity: spoofy 78% of classified cycles | feed errors 1

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=240, brier=n/a) yet retrain was requested 36x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 59% of the audit trail
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 78% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 59% of 4607 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  2 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
