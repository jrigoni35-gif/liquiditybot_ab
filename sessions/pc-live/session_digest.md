# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-03 13:59 UTC (582.09h, ~3479 cycles)
- Equity: $25,000.00 -> $4,930.86 (range $99,208.70) | realized PnL $-44.13 | fees $60.12
- Activity: 2 open | 293 live labeled trades | 8935 candidates | 253 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 293 | cold=True
- Audit: 28424 records (25678 non-routine) | dominant SZ-047 (87% of non-routine) | chain_ok=False (tamper=False, seams=6) | retrain_requests 71
- Liquidity: spoofy 44% of classified cycles | feed errors 1

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=293, brier=n/a) yet retrain was requested 71x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 87% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 87% of 25678 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  6 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
