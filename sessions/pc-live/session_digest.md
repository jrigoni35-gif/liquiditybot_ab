# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-05 13:00 UTC (629.12h, ~2167 cycles)
- Equity: $25,000.00 -> $4,932.35 (range $99,208.70) | realized PnL $-44.28 | fees $61.29
- Activity: 4 open | 296 live labeled trades | 9129 candidates | 256 postmortems
- Model: level 1 | use_model=True | brier n/a | history_rows 296 | cold=True
- Audit: 28610 records (25855 non-routine) | dominant SZ-047 (86% of non-routine) | chain_ok=False (tamper=False, seams=6) | retrain_requests 79
- Liquidity: spoofy 41% of classified cycles | feed errors 2

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=296, brier=n/a) yet retrain was requested 79x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 86% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 86% of 25855 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  6 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
