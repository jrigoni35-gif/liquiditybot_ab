# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-07-21 04:42 UTC (260.81h, ~398 cycles)
- Equity: $25,000.00 -> $4,993.30 (range $99,208.70) | realized PnL $-3.59 | fees $7.67
- Activity: 0 open | 84 live labeled trades | 2122 candidates | 72 postmortems
- Model: level 2 | use_model=False | brier n/a | history_rows 84 | cold=True
- Audit: 1359 records (627 non-routine) | dominant OM-000 (32% of non-routine) | chain_ok=False (tamper=False, seams=2) | retrain_requests 25
- Liquidity: spoofy 38% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=84, brier=n/a) yet retrain was requested 25x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 32% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  OM-000 is 32% of 627 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  2 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
