# Session digest

**Verdict: SD-007 audit chain broken**

- Window: 2026-07-10 07:53 UTC -> 2026-07-20 06:41 UTC (238.8h, ~2082 cycles)
- Equity: $25,000.00 -> $4,997.30 (range $99,208.70) | realized PnL $-1.42 | fees $3.33
- Activity: 3 open | 55 live labeled trades | 1868 candidates | 52 postmortems
- Model: level 2 | use_model=False | brier n/a | history_rows 55 | cold=True
- Audit: 913 records (432 non-routine) | dominant OM-000 (32% of non-routine) | chain_ok=False | retrain_requests 22
- Liquidity: spoofy 39% of classified cycles | feed errors 2

## Diagnostics
- [ERR]  **SD-007 audit chain broken**  -  hash chain first breaks at record 505  -  the trail was truncated, reordered, or corrupted past that point
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=55, brier=n/a) yet retrain was requested 22x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 32% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  OM-000 is 32% of 432 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
