# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-07-21 13:42 UTC (269.81h, ~1447 cycles)
- Equity: $25,000.00 -> $4,991.65 (range $99,208.70) | realized PnL $-4.38 | fees $9.38
- Activity: 1 open | 94 live labeled trades | 2189 candidates | 81 postmortems
- Model: level 2 | use_model=False | brier n/a | history_rows 94 | cold=True
- Audit: 1543 records (686 non-routine) | dominant OM-000 (33% of non-routine) | chain_ok=False (tamper=False, seams=2) | retrain_requests 27
- Liquidity: spoofy 35% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=94, brier=n/a) yet retrain was requested 27x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 33% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  OM-000 is 33% of 686 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  2 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
