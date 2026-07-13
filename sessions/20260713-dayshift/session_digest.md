# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-13 10:33 UTC -> 2026-07-13 17:29 UTC (6.94h, ~784 cycles)
- Equity: $800.00 -> $799.75 (range $0.45) | realized PnL $0.15 | fees $0.83
- Activity: 5 open | 6 live labeled trades | 0 candidates | 0 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 6 | cold=True
- Audit: 81 records (25 non-routine) | dominant OM-000 (92% of non-routine) | chain_ok=True | retrain_requests 0
- Liquidity: spoofy 82% of classified cycles | feed errors 4

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 82% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
