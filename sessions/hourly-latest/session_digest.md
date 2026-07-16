# Session digest

**Verdict: SD-007 audit chain broken**

- Window: 2026-07-13 10:33 UTC -> 2026-07-16 19:14 UTC (80.69h, ~550 cycles)
- Equity: $800.00 -> $800.61 (range $2.25) | realized PnL $0.66 | fees $2.24
- Activity: 3 open | 19 live labeled trades | 345 candidates | 8 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 19 | cold=True
- Audit: 492 records (134 non-routine) | dominant CG-000 (45% of non-routine) | chain_ok=False | retrain_requests 3
- Liquidity: spoofy 70% of classified cycles | feed errors 2

## Diagnostics
- [ERR]  **SD-007 audit chain broken**  -  hash chain first breaks at record 199  -  the trail was truncated, reordered, or corrupted past that point
- [ERR]  **SD-005 postmortem realized% contradicts its own excursions**  -  1 of 8 postmortem(s) report a realized loss (worst -6.9%) while max adverse excursion was ~0% - impossible for a real fill. The % is fabricated from a ~$0 notional (ml/postmortem.py entry_usd guard); do NOT let ml/monitor.py train or auto-adjust on these causes
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 70% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  CG-000 is 45% of 134 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
