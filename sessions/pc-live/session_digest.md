# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-10 03:06 UTC (739.21h, ~2074 cycles)
- Equity: $25,000.00 -> $4,616.60 (range $99,208.70) | realized PnL $-208.31 | fees $382.59
- Activity: 5 open | 306 live labeled trades | 9681 candidates | 264 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 306 | cold=True
- Audit: 38364 records (31383 non-routine) | dominant SZ-047 (71% of non-routine) | chain_ok=False (tamper=False, seams=6) | retrain_requests 95
- Liquidity: spoofy 46% of classified cycles | feed errors 3

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=306, brier=n/a) yet retrain was requested 95x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 71% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 71% of 31383 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  6 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
