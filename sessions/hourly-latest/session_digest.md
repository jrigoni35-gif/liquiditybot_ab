# Session digest

**Verdict: SD-007 audit chain broken**

- Window: 2026-07-13 10:33 UTC -> 2026-07-16 22:02 UTC (83.49h, ~796 cycles)
- Equity: $800.00 -> $5,000.03 (range $4,201.35) | realized PnL $0.00 | fees $0.00
- Activity: 5 open | 19 live labeled trades | 354 candidates | 8 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 19 | cold=True
- Audit: 517 records (153 non-routine) | dominant CG-000 (45% of non-routine) | chain_ok=False | retrain_requests 3
- Liquidity: spoofy 69% of classified cycles | feed errors 11

## Diagnostics
- [ERR]  **SD-007 audit chain broken**  -  hash chain first breaks at record 199  -  the trail was truncated, reordered, or corrupted past that point
- [ERR]  **SD-005 postmortem realized% contradicts its own excursions**  -  1 of 8 postmortem(s) report a realized loss (worst -6.9%) while max adverse excursion was ~0% - impossible for a real fill. The % is fabricated from a ~$0 notional (ml/postmortem.py entry_usd guard); do NOT let ml/monitor.py train or auto-adjust on these causes
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 69% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  CG-000 is 45% of 153 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
