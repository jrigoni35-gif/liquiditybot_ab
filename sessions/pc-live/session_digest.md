# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-07-22 14:42 UTC (294.82h, ~142 cycles)
- Equity: $25,000.00 -> $4,982.64 (range $99,208.70) | realized PnL $-8.57 | fees $21.25
- Activity: 2 open | 159 live labeled trades | 2637 candidates | 128 postmortems
- Model: level 2 | use_model=False | brier n/a | history_rows 159 | cold=True
- Audit: 2816 records (1146 non-routine) | dominant OM-000 (33% of non-routine) | chain_ok=False (tamper=False, seams=2) | retrain_requests 31
- Liquidity: spoofy 78% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=159, brier=n/a) yet retrain was requested 31x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 33% of the audit trail
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 78% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  OM-000 is 33% of 1146 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  2 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
