# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-07-22 03:42 UTC (283.82h, ~930 cycles)
- Equity: $25,000.00 -> $4,988.78 (range $99,208.70) | realized PnL $-5.88 | fees $12.27
- Activity: 5 open | 111 live labeled trades | 2327 candidates | 95 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 111 | cold=True
- Audit: 2029 records (803 non-routine) | dominant OM-000 (33% of non-routine) | chain_ok=False (tamper=False, seams=2) | retrain_requests 29
- Liquidity: spoofy 32% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=111, brier=n/a) yet retrain was requested 29x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 33% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  OM-000 is 33% of 803 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  2 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
