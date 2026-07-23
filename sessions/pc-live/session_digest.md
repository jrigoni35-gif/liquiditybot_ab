# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-07-23 09:43 UTC (313.83h, ~174 cycles)
- Equity: $25,000.00 -> $4,973.02 (range $99,208.70) | realized PnL $-14.78 | fees $28.61
- Activity: 5 open | 204 live labeled trades | 3015 candidates | 173 postmortems
- Model: level 2 | use_model=False | brier n/a | history_rows 204 | cold=True
- Audit: 3844 records (1542 non-routine) | dominant OM-000 (30% of non-routine) | chain_ok=False (tamper=False, seams=2) | retrain_requests 34
- Liquidity: spoofy 76% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=204, brier=n/a) yet retrain was requested 34x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 30% of the audit trail
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 76% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  OM-000 is 30% of 1542 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  2 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
