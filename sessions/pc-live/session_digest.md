# Session digest

**Verdict: SD-007 audit chain broken**

- Window: 2026-07-10 07:53 UTC -> 2026-07-19 06:40 UTC (214.79h, ~1479 cycles)
- Equity: $25,000.00 -> $4,999.42 (range $99,208.70) | realized PnL $0.00 | fees $0.40
- Activity: 5 open | 35 live labeled trades | 1476 candidates | 39 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 35 | cold=True
- Audit: 617 records (302 non-routine) | dominant ML-031 (30% of non-routine) | chain_ok=False | retrain_requests 19
- Liquidity: spoofy 38% of classified cycles | feed errors 253

## Diagnostics
- [ERR]  **SD-007 audit chain broken**  -  hash chain first breaks at record 505  -  the trail was truncated, reordered, or corrupted past that point
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=35, brier=n/a) yet retrain was requested 19x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 30% of the audit trail
