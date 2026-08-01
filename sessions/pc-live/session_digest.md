# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-01 04:56 UTC (525.05h, ~3 cycles)
- Equity: $25,000.00 -> $4,940.51 (range $99,208.70) | realized PnL $-32.74 | fees $54.34
- Activity: 2 open | 268 live labeled trades | 7539 candidates | 228 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 268 | cold=True
- Audit: 27756 records (25133 non-routine) | dominant SZ-047 (89% of non-routine) | chain_ok=False (tamper=False, seams=5) | retrain_requests 62
- Liquidity: spoofy 33% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=268, brier=n/a) yet retrain was requested 62x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 89% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 89% of 25133 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  5 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
