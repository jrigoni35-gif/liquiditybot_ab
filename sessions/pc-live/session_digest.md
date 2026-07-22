# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-07-22 12:42 UTC (292.82h, ~1793 cycles)
- Equity: $25,000.00 -> $4,983.69 (range $99,208.70) | realized PnL $-8.24 | fees $19.30
- Activity: 5 open | 145 live labeled trades | 2506 candidates | 122 postmortems
- Model: level 2 | use_model=False | brier n/a | history_rows 145 | cold=True
- Audit: 2545 records (1062 non-routine) | dominant OM-000 (33% of non-routine) | chain_ok=False (tamper=False, seams=2) | retrain_requests 30
- Liquidity: spoofy 42% of classified cycles | feed errors 117

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=145, brier=n/a) yet retrain was requested 30x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 33% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  OM-000 is 33% of 1062 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  2 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
