# Session digest

**Verdict: SD-007 audit chain broken**

- Window: 2026-07-13 10:33 UTC -> 2026-07-17 12:52 UTC (98.33h, ~1441 cycles)
- Equity: $800.00 -> $4,998.07 (range $4,201.35) | realized PnL $-1.57 | fees $1.36
- Activity: 4 open | 29 live labeled trades | 466 candidates | 12 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 29 | cold=True
- Audit: 644 records (227 non-routine) | dominant CG-000 (40% of non-routine) | chain_ok=False | retrain_requests 3
- Liquidity: spoofy 53% of classified cycles | feed errors 39

## Diagnostics
- [ERR]  **SD-007 audit chain broken**  -  hash chain first breaks at record 199  -  the trail was truncated, reordered, or corrupted past that point
- [ERR]  **SD-005 postmortem realized% contradicts its own excursions**  -  1 of 12 postmortem(s) report a realized loss (worst -6.9%) while max adverse excursion was ~0% - impossible for a real fill. The % is fabricated from a ~$0 notional (ml/postmortem.py entry_usd guard); do NOT let ml/monitor.py train or auto-adjust on these causes
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 53% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  CG-000 is 40% of 227 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
