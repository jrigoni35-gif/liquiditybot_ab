# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-13 10:33 UTC -> 2026-07-14 07:32 UTC (20.98h, ~2310 cycles)
- Equity: $800.00 -> $798.45 (range $1.77) | realized PnL $-1.40 | fees $2.68
- Activity: 5 open | 12 live labeled trades | 12 candidates | 9 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 12 | cold=True
- Audit: 231 records (80 non-routine) | dominant OM-000 (82% of non-routine) | chain_ok=True | retrain_requests 0
- Liquidity: spoofy 76% of classified cycles | feed errors 1944

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 76% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  OM-000 is 82% of 80 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
