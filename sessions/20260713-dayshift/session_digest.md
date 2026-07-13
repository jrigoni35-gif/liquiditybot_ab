# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-13 10:33 UTC -> 2026-07-13 13:37 UTC (3.07h, ~350 cycles)
- Equity: $800.00 -> $799.96 (range $0.33) | realized PnL $0.09 | fees $0.61
- Activity: 5 open | 4 live labeled trades | 0 candidates | 0 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 4 | cold=True
- Audit: 70 records (19 non-routine) | dominant OM-000 (90% of non-routine) | chain_ok=True | retrain_requests 0
- Liquidity: spoofy 83% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 83% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
