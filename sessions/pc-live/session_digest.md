# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-01 10:56 UTC (531.05h, ~710 cycles)
- Equity: $25,000.00 -> $4,939.80 (range $99,208.70) | realized PnL $-33.05 | fees $54.80
- Activity: 2 open | 271 live labeled trades | 7762 candidates | 231 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 271 | cold=True
- Audit: 27828 records (25192 non-routine) | dominant SZ-047 (88% of non-routine) | chain_ok=False (tamper=False, seams=5) | retrain_requests 63
- Liquidity: spoofy 42% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=271, brier=n/a) yet retrain was requested 63x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 88% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 88% of 25192 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  5 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
