# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-07-28 21:54 UTC (446.01h, ~432 cycles)
- Equity: $25,000.00 -> $4,962.94 (range $99,208.70) | realized PnL $-21.43 | fees $38.09
- Activity: 0 open | 250 live labeled trades | 5620 candidates | 209 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 250 | cold=True
- Audit: 20027 records (17461 non-routine) | dominant SZ-047 (87% of non-routine) | chain_ok=False (tamper=False, seams=5) | retrain_requests 50
- Liquidity: spoofy 59% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=250, brier=n/a) yet retrain was requested 50x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 87% of the audit trail
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 59% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 87% of 17461 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  5 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
