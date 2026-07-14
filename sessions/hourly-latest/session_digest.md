# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-13 10:33 UTC -> 2026-07-14 16:47 UTC (30.25h, ~195 cycles)
- Equity: $800.00 -> $797.93 (range $2.27) | realized PnL $-2.07 | fees $3.20
- Activity: 0 open | 19 live labeled trades | 116 candidates | 14 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 19 | cold=True
- Audit: 386 records (111 non-routine) | dominant OM-000 (72% of non-routine) | chain_ok=True | retrain_requests 1
- Liquidity: spoofy 66% of classified cycles | feed errors 226

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 66% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  OM-000 is 72% of 111 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
