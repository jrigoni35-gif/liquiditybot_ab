# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-13 10:33 UTC -> 2026-07-13 23:32 UTC (12.99h, ~1413 cycles)
- Equity: $800.00 -> $798.84 (range $1.46) | realized PnL $-1.11 | fees $1.75
- Activity: 4 open | 10 live labeled trades | 12 candidates | 7 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 10 | cold=True
- Audit: 149 records (53 non-routine) | dominant OM-000 (79% of non-routine) | chain_ok=True | retrain_requests 0
- Liquidity: spoofy 78% of classified cycles | feed errors 1933

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 78% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  OM-000 is 79% of 53 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
