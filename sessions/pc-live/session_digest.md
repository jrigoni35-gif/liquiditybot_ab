# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-07-26 23:52 UTC (399.99h, ~486 cycles)
- Equity: $25,000.00 -> $4,965.55 (range $99,208.70) | realized PnL $-20.11 | fees $35.46
- Activity: 1 open | 242 live labeled trades | 4747 candidates | 205 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 242 | cold=True
- Audit: 13376 records (10816 non-routine) | dominant SZ-047 (80% of non-routine) | chain_ok=False (tamper=False, seams=2) | retrain_requests 43
- Liquidity: spoofy 56% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=242, brier=n/a) yet retrain was requested 43x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 80% of the audit trail
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 56% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 80% of 10816 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  2 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
