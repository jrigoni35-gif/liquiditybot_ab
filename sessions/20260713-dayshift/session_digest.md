# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-13 10:33 UTC -> 2026-07-13 23:12 UTC (12.65h, ~1375 cycles)
- Equity: $800.00 -> $798.78 (range $1.46) | realized PnL $-1.11 | fees $1.71
- Activity: 3 open | 10 live labeled trades | 12 candidates | 7 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 10 | cold=True
- Audit: 142 records (51 non-routine) | dominant OM-000 (80% of non-routine) | chain_ok=True | retrain_requests 0
- Liquidity: spoofy 79% of classified cycles | feed errors 1933

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 79% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  OM-000 is 80% of 51 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
