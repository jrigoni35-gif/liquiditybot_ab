# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-13 10:33 UTC -> 2026-07-13 15:23 UTC (4.84h, ~550 cycles)
- Equity: $800.00 -> $799.84 (range $0.41) | realized PnL $0.15 | fees $0.79
- Activity: 4 open | 6 live labeled trades | 0 candidates | 0 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 6 | cold=True
- Audit: 77 records (24 non-routine) | dominant OM-000 (92% of non-routine) | chain_ok=True | retrain_requests 0
- Liquidity: spoofy 83% of classified cycles | feed errors 1

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 83% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
