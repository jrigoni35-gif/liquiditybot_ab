# Session digest

**Verdict: SD-007 audit chain broken**

- Window: 2026-07-13 10:33 UTC -> 2026-07-17 04:08 UTC (89.59h, ~1217 cycles)
- Equity: $800.00 -> $4,999.05 (range $4,201.35) | realized PnL $-0.31 | fees $0.45
- Activity: 5 open | 22 live labeled trades | 422 candidates | 9 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 22 | cold=True
- Audit: 574 records (184 non-routine) | dominant CG-000 (43% of non-routine) | chain_ok=False | retrain_requests 3
- Liquidity: spoofy 65% of classified cycles | feed errors 23

## Diagnostics
- [ERR]  **SD-007 audit chain broken**  -  hash chain first breaks at record 199  -  the trail was truncated, reordered, or corrupted past that point
- [ERR]  **SD-005 postmortem realized% contradicts its own excursions**  -  1 of 9 postmortem(s) report a realized loss (worst -6.9%) while max adverse excursion was ~0% - impossible for a real fill. The % is fabricated from a ~$0 notional (ml/postmortem.py entry_usd guard); do NOT let ml/monitor.py train or auto-adjust on these causes
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 65% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  CG-000 is 43% of 184 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
