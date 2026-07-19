# Session digest

**Verdict: SD-007 audit chain broken**

- Window: 2026-07-10 07:53 UTC -> 2026-07-19 14:40 UTC (222.79h, ~297 cycles)
- Equity: $25,000.00 -> $4,998.68 (range $99,208.70) | realized PnL $-0.78 | fees $1.30
- Activity: 5 open | 40 live labeled trades | 1602 candidates | 44 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 40 | cold=True
- Audit: 663 records (337 non-routine) | dominant OM-000 (29% of non-routine) | chain_ok=False | retrain_requests 20
- Liquidity: spoofy 41% of classified cycles | feed errors 0

## Diagnostics
- [ERR]  **SD-007 audit chain broken**  -  hash chain first breaks at record 505  -  the trail was truncated, reordered, or corrupted past that point
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=40, brier=n/a) yet retrain was requested 20x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 29% of the audit trail
