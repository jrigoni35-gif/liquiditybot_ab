# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-13 10:33 UTC -> 2026-07-13 20:52 UTC (10.32h, ~1113 cycles)
- Equity: $800.00 -> $798.89 (range $1.31) | realized PnL $-1.11 | fees $1.55
- Activity: 0 open | 10 live labeled trades | 12 candidates | 2 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 10 | cold=True
- Audit: 115 records (46 non-routine) | dominant OM-000 (83% of non-routine) | chain_ok=True | retrain_requests 0
- Liquidity: spoofy 80% of classified cycles | feed errors 1929

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 80% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
