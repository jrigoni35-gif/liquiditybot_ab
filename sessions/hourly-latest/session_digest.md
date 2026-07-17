# Session digest

**Verdict: SD-007 audit chain broken**

- Window: 2026-07-13 10:33 UTC -> 2026-07-17 13:36 UTC (99.06h, ~1478 cycles)
- Equity: $800.00 -> $4,997.49 (range $4,201.35) | realized PnL $-2.01 | fees $1.58
- Activity: 5 open | 30 live labeled trades | 467 candidates | 12 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 30 | cold=True
- Audit: 651 records (232 non-routine) | dominant CG-000 (40% of non-routine) | chain_ok=False | retrain_requests 3
- Liquidity: spoofy 52% of classified cycles | feed errors 43

## Diagnostics
- [ERR]  **SD-007 audit chain broken**  -  hash chain first breaks at record 199  -  the trail was truncated, reordered, or corrupted past that point
- [ERR]  **SD-005 postmortem realized% contradicts its own excursions**  -  1 of 12 postmortem(s) report a realized loss (worst -6.9%) while max adverse excursion was ~0% - impossible for a real fill. The % is fabricated from a ~$0 notional (ml/postmortem.py entry_usd guard); do NOT let ml/monitor.py train or auto-adjust on these causes
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 52% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  CG-000 is 40% of 232 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
