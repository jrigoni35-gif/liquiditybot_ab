# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-06 06:02 UTC (646.14h, ~867 cycles)
- Equity: $25,000.00 -> $4,938.35 (range $99,208.70) | realized PnL $-44.30 | fees $62.01
- Activity: 4 open | 298 live labeled trades | 9252 candidates | 258 postmortems
- Model: level 2 | use_model=False | brier n/a | history_rows 298 | cold=True
- Audit: 28864 records (26029 non-routine) | dominant SZ-047 (86% of non-routine) | chain_ok=False (tamper=False, seams=6) | retrain_requests 81
- Liquidity: spoofy 46% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=298, brier=n/a) yet retrain was requested 81x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 86% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 86% of 26029 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  6 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
