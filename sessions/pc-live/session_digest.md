# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-13 05:55 UTC (814.03h, ~1820 cycles)
- Equity: $25,000.00 -> $798.26 (range $99,208.70) | realized PnL $-0.78 | fees $0.73
- Activity: 5 open | 317 live labeled trades | 10046 candidates | 273 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 317 | cold=True
- Audit: 44658 records (34802 non-routine) | dominant SZ-047 (64% of non-routine) | chain_ok=False (tamper=False, seams=6) | retrain_requests 105
- Liquidity: spoofy 50% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=317, brier=n/a) yet retrain was requested 105x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 64% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 64% of 34802 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  6 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
