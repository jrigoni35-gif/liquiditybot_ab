# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-03 03:58 UTC (572.08h, ~2306 cycles)
- Equity: $25,000.00 -> $4,933.92 (range $99,208.70) | realized PnL $-35.11 | fees $57.96
- Activity: 3 open | 291 live labeled trades | 8886 candidates | 251 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 291 | cold=True
- Audit: 28366 records (25632 non-routine) | dominant SZ-047 (87% of non-routine) | chain_ok=False (tamper=False, seams=6) | retrain_requests 69
- Liquidity: spoofy 43% of classified cycles | feed errors 1

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=291, brier=n/a) yet retrain was requested 69x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 87% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 87% of 25632 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  6 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
