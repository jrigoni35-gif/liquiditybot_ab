# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-13 10:33 UTC -> 2026-07-13 20:04 UTC (9.52h, ~1044 cycles)
- Equity: $800.00 -> $799.08 (range $1.12) | realized PnL $-0.42 | fees $1.27
- Activity: 5 open | 10 live labeled trades | 12 candidates | 2 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 10 | cold=True
- Audit: 106 records (39 non-routine) | dominant OM-000 (85% of non-routine) | chain_ok=True | retrain_requests 0
- Liquidity: spoofy 82% of classified cycles | feed errors 1924

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 82% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
