# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-08 06:03 UTC (694.17h, ~1295 cycles)
- Equity: $25,000.00 -> $4,615.92 (range $99,208.70) | realized PnL $-208.34 | fees $382.35
- Activity: 2 open | 305 live labeled trades | 9485 candidates | 263 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 305 | cold=True
- Audit: 34435 records (29278 non-routine) | dominant SZ-047 (76% of non-routine) | chain_ok=False (tamper=False, seams=6) | retrain_requests 89
- Liquidity: spoofy 42% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=305, brier=n/a) yet retrain was requested 89x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 76% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 76% of 29278 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  6 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
