# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-06 11:02 UTC (651.14h, ~1456 cycles)
- Equity: $25,000.00 -> $4,935.77 (range $99,208.70) | realized PnL $-44.20 | fees $62.24
- Activity: 4 open | 299 live labeled trades | 9309 candidates | 259 postmortems
- Model: level 2 | use_model=False | brier n/a | history_rows 299 | cold=True
- Audit: 28925 records (26076 non-routine) | dominant SZ-047 (85% of non-routine) | chain_ok=False (tamper=False, seams=6) | retrain_requests 82
- Liquidity: spoofy 47% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=299, brier=n/a) yet retrain was requested 82x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 85% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 85% of 26076 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  6 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
