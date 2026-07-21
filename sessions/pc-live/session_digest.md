# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-07-21 17:42 UTC (273.81h, ~1884 cycles)
- Equity: $25,000.00 -> $4,991.39 (range $99,208.70) | realized PnL $-4.51 | fees $9.59
- Activity: 2 open | 95 live labeled trades | 2215 candidates | 83 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 95 | cold=True
- Audit: 1617 records (715 non-routine) | dominant OM-000 (32% of non-routine) | chain_ok=False (tamper=False, seams=2) | retrain_requests 27
- Liquidity: spoofy 33% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=95, brier=n/a) yet retrain was requested 27x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 32% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  OM-000 is 32% of 715 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  2 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
