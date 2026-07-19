# Session digest

**Verdict: SD-007 audit chain broken**

- Window: 2026-07-10 07:53 UTC -> 2026-07-19 15:40 UTC (223.79h, ~412 cycles)
- Equity: $25,000.00 -> $4,998.43 (range $99,208.70) | realized PnL $-0.87 | fees $1.55
- Activity: 3 open | 43 live labeled trades | 1615 candidates | 44 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 43 | cold=True
- Audit: 674 records (347 non-routine) | dominant OM-000 (30% of non-routine) | chain_ok=False | retrain_requests 20
- Liquidity: spoofy 42% of classified cycles | feed errors 0

## Diagnostics
- [ERR]  **SD-007 audit chain broken**  -  hash chain first breaks at record 505  -  the trail was truncated, reordered, or corrupted past that point
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=43, brier=n/a) yet retrain was requested 20x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 30% of the audit trail
