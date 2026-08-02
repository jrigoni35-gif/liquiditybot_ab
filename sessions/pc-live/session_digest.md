# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-02 11:58 UTC (556.08h, ~439 cycles)
- Equity: $25,000.00 -> $4,935.00 (range $99,208.70) | realized PnL $-34.50 | fees $57.01
- Activity: 3 open | 285 live labeled trades | 8447 candidates | 244 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 285 | cold=True
- Audit: 28147 records (25437 non-routine) | dominant SZ-047 (88% of non-routine) | chain_ok=False (tamper=False, seams=6) | retrain_requests 67
- Liquidity: spoofy 40% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=285, brier=n/a) yet retrain was requested 67x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 88% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 88% of 25437 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  6 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
