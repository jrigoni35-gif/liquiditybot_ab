# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-07-22 07:42 UTC (287.82h, ~1309 cycles)
- Equity: $25,000.00 -> $4,987.89 (range $99,208.70) | realized PnL $-6.13 | fees $14.13
- Activity: 5 open | 121 live labeled trades | 2408 candidates | 104 postmortems
- Model: level 2 | use_model=False | brier n/a | history_rows 121 | cold=True
- Audit: 2159 records (888 non-routine) | dominant OM-000 (33% of non-routine) | chain_ok=False (tamper=False, seams=2) | retrain_requests 29
- Liquidity: spoofy 37% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=121, brier=n/a) yet retrain was requested 29x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 33% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  OM-000 is 33% of 888 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  2 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
