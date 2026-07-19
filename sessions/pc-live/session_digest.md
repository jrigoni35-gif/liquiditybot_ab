# Session digest

**Verdict: SD-007 audit chain broken**

- Window: 2026-07-10 07:53 UTC -> 2026-07-19 13:40 UTC (221.79h, ~183 cycles)
- Equity: $25,000.00 -> $4,998.64 (range $99,208.70) | realized PnL $-0.78 | fees $1.30
- Activity: 5 open | 40 live labeled trades | 1594 candidates | 44 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 40 | cold=True
- Audit: 662 records (336 non-routine) | dominant OM-000 (30% of non-routine) | chain_ok=False | retrain_requests 20
- Liquidity: spoofy 39% of classified cycles | feed errors 0

## Diagnostics
- [ERR]  **SD-007 audit chain broken**  -  hash chain first breaks at record 505  -  the trail was truncated, reordered, or corrupted past that point
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=40, brier=n/a) yet retrain was requested 20x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 30% of the audit trail
