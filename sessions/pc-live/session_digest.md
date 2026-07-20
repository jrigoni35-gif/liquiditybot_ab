# Session digest

**Verdict: SD-007 audit chain broken**

- Window: 2026-07-10 07:53 UTC -> 2026-07-20 14:41 UTC (246.8h, ~866 cycles)
- Equity: $25,000.00 -> $4,994.00 (range $99,208.70) | realized PnL $-2.72 | fees $5.53
- Activity: 3 open | 68 live labeled trades | 2018 candidates | 58 postmortems
- Model: level 2 | use_model=False | brier n/a | history_rows 68 | cold=True
- Audit: 1104 records (521 non-routine) | dominant OM-000 (33% of non-routine) | chain_ok=False | retrain_requests 23
- Liquidity: spoofy 35% of classified cycles | feed errors 0

## Diagnostics
- [ERR]  **SD-007 audit chain broken**  -  hash chain first breaks at record 505  -  the trail was truncated, reordered, or corrupted past that point
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=68, brier=n/a) yet retrain was requested 23x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 33% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  OM-000 is 33% of 521 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
