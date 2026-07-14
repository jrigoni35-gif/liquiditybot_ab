# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-13 10:33 UTC -> 2026-07-14 22:09 UTC (35.6h, ~1442 cycles)
- Equity: $800.00 -> $800.66 (range $2.25) | realized PnL $0.66 | fees $2.10
- Activity: 0 open | 19 live labeled trades | 119 candidates | 7 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 19 | cold=True
- Audit: 171 records (71 non-routine) | dominant OM-000 (79% of non-routine) | chain_ok=True | retrain_requests 1
- Liquidity: spoofy 78% of classified cycles | feed errors 1941

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 78% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  OM-000 is 79% of 71 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
