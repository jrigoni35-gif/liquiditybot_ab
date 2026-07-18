# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-13 10:33 UTC -> 2026-07-14 02:51 UTC (16.3h, ~1777 cycles)
- Equity: $800.00 -> $798.55 (range $1.73) | realized PnL $-1.42 | fees $2.47
- Activity: 3 open | 11 live labeled trades | 12 candidates | 9 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 11 | cold=True
- Audit: 222 records (75 non-routine) | dominant OM-000 (81% of non-routine) | chain_ok=True | retrain_requests 0
- Liquidity: spoofy 77% of classified cycles | feed errors 1944

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 77% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  OM-000 is 81% of 75 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
