# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-13 10:33 UTC -> 2026-07-14 12:18 UTC (25.76h, ~2831 cycles)
- Equity: $800.00 -> $798.35 (range $1.94) | realized PnL $-1.36 | fees $2.90
- Activity: 5 open | 14 live labeled trades | 65 candidates | 9 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 14 | cold=True
- Audit: 253 records (90 non-routine) | dominant OM-000 (80% of non-routine) | chain_ok=True | retrain_requests 0
- Liquidity: spoofy 75% of classified cycles | feed errors 2338

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 75% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  OM-000 is 80% of 90 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
