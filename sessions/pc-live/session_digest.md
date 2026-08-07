# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-07 17:02 UTC (681.16h, ~1894 cycles)
- Equity: $25,000.00 -> $4,613.67 (range $99,208.70) | realized PnL $-208.22 | fees $382.28
- Activity: 3 open | 304 live labeled trades | 9445 candidates | 262 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 304 | cold=True
- Audit: 30827 records (27397 non-routine) | dominant SZ-047 (81% of non-routine) | chain_ok=False (tamper=False, seams=6) | retrain_requests 87
- Liquidity: spoofy 45% of classified cycles | feed errors 7

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=304, brier=n/a) yet retrain was requested 87x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 81% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 81% of 27397 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  6 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
