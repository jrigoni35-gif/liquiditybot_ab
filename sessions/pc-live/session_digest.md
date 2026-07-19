# Session digest

**Verdict: SD-007 audit chain broken**

- Window: 2026-07-10 07:53 UTC -> 2026-07-19 22:40 UTC (230.79h, ~1210 cycles)
- Equity: $25,000.00 -> $4,998.21 (range $99,208.70) | realized PnL $-1.00 | fees $2.01
- Activity: 4 open | 45 live labeled trades | 1715 candidates | 49 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 45 | cold=True
- Audit: 816 records (376 non-routine) | dominant OM-000 (30% of non-routine) | chain_ok=False | retrain_requests 21
- Liquidity: spoofy 43% of classified cycles | feed errors 0

## Diagnostics
- [ERR]  **SD-007 audit chain broken**  -  hash chain first breaks at record 505  -  the trail was truncated, reordered, or corrupted past that point
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=45, brier=n/a) yet retrain was requested 21x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 30% of the audit trail
