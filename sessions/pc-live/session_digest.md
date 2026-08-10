# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-10 15:06 UTC (751.22h, ~1063 cycles)
- Equity: $25,000.00 -> $4,610.59 (range $99,208.70) | realized PnL $-208.37 | fees $382.74
- Activity: 5 open | 307 live labeled trades | 9730 candidates | 265 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 307 | cold=True
- Audit: 38496 records (31488 non-routine) | dominant SZ-047 (71% of non-routine) | chain_ok=False (tamper=False, seams=6) | retrain_requests 97
- Liquidity: spoofy 44% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=307, brier=n/a) yet retrain was requested 97x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 71% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 71% of 31488 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  6 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
