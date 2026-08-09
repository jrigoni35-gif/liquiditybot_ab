# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-09 16:05 UTC (728.2h, ~795 cycles)
- Equity: $25,000.00 -> $4,617.69 (range $99,208.70) | realized PnL $-208.31 | fees $382.59
- Activity: 5 open | 306 live labeled trades | 9601 candidates | 264 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 306 | cold=True
- Audit: 38299 records (31318 non-routine) | dominant SZ-047 (71% of non-routine) | chain_ok=False (tamper=False, seams=6) | retrain_requests 94
- Liquidity: spoofy 42% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=306, brier=n/a) yet retrain was requested 94x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 71% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 71% of 31318 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  6 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
