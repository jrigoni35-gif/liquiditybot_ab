# Session digest

**Verdict: SD-007 audit chain broken**

- Window: 2026-07-13 10:33 UTC -> 2026-07-17 11:44 UTC (97.19h, ~1355 cycles)
- Equity: $800.00 -> $4,998.34 (range $4,201.35) | realized PnL $-1.57 | fees $1.23
- Activity: 4 open | 28 live labeled trades | 463 candidates | 12 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 28 | cold=True
- Audit: 624 records (216 non-routine) | dominant CG-000 (41% of non-routine) | chain_ok=False | retrain_requests 3
- Liquidity: spoofy 56% of classified cycles | feed errors 38

## Diagnostics
- [ERR]  **SD-007 audit chain broken**  -  hash chain first breaks at record 199  -  the trail was truncated, reordered, or corrupted past that point
- [ERR]  **SD-005 postmortem realized% contradicts its own excursions**  -  1 of 12 postmortem(s) report a realized loss (worst -6.9%) while max adverse excursion was ~0% - impossible for a real fill. The % is fabricated from a ~$0 notional (ml/postmortem.py entry_usd guard); do NOT let ml/monitor.py train or auto-adjust on these causes
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 56% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  CG-000 is 41% of 216 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
