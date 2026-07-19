# Session digest

**Verdict: SD-007 audit chain broken**

- Window: 2026-07-10 07:53 UTC -> 2026-07-19 20:40 UTC (228.79h, ~981 cycles)
- Equity: $25,000.00 -> $4,998.27 (range $99,208.70) | realized PnL $-1.04 | fees $1.70
- Activity: 1 open | 45 live labeled trades | 1696 candidates | 49 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 45 | cold=True
- Audit: 784 records (365 non-routine) | dominant OM-000 (29% of non-routine) | chain_ok=False | retrain_requests 21
- Liquidity: spoofy 43% of classified cycles | feed errors 0

## Diagnostics
- [ERR]  **SD-007 audit chain broken**  -  hash chain first breaks at record 505  -  the trail was truncated, reordered, or corrupted past that point
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=45, brier=n/a) yet retrain was requested 21x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 29% of the audit trail
