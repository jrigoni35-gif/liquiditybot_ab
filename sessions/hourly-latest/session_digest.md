# Session digest

**Verdict: SD-007 audit chain broken**

- Window: 2026-07-13 10:33 UTC -> 2026-07-16 13:40 UTC (75.12h, ~101 cycles)
- Equity: $800.00 -> $800.66 (range $2.25) | realized PnL $0.66 | fees $2.10
- Activity: 0 open | 19 live labeled trades | 338 candidates | 8 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 19 | cold=True
- Audit: 425 records (120 non-routine) | dominant OM-000 (47% of non-routine) | chain_ok=False | retrain_requests 3
- Liquidity: spoofy 80% of classified cycles | feed errors 2

## Diagnostics
- [ERR]  **SD-007 audit chain broken**  -  hash chain first breaks at record 199  -  the trail was truncated, reordered, or corrupted past that point
- [ERR]  **SD-005 postmortem realized% contradicts its own excursions**  -  1 of 8 postmortem(s) report a realized loss (worst -6.9%) while max adverse excursion was ~0% - impossible for a real fill. The % is fabricated from a ~$0 notional (ml/postmortem.py entry_usd guard); do NOT let ml/monitor.py train or auto-adjust on these causes
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 80% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  OM-000 is 47% of 120 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
