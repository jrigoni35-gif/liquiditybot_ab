# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-07-23 03:43 UTC (307.83h, ~1573 cycles)
- Equity: $25,000.00 -> $4,974.38 (range $99,208.70) | realized PnL $-13.80 | fees $27.77
- Activity: 5 open | 197 live labeled trades | 2895 candidates | 165 postmortems
- Model: level 2 | use_model=False | brier n/a | history_rows 197 | cold=True
- Audit: 3746 records (1479 non-routine) | dominant OM-000 (31% of non-routine) | chain_ok=False (tamper=False, seams=2) | retrain_requests 33
- Liquidity: spoofy 74% of classified cycles | feed errors 3

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=197, brier=n/a) yet retrain was requested 33x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 31% of the audit trail
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 74% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  OM-000 is 31% of 1479 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  2 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
