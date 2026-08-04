# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-04 10:59 UTC (603.1h, ~2414 cycles)
- Equity: $25,000.00 -> $4,931.01 (range $99,208.70) | realized PnL $-44.07 | fees $60.64
- Activity: 5 open | 294 live labeled trades | 8996 candidates | 254 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 294 | cold=True
- Audit: 28536 records (25783 non-routine) | dominant SZ-047 (86% of non-routine) | chain_ok=False (tamper=False, seams=6) | retrain_requests 75
- Liquidity: spoofy 41% of classified cycles | feed errors 1

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=294, brier=n/a) yet retrain was requested 75x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 86% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 86% of 25783 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  6 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
