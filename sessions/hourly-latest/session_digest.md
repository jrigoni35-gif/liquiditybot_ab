# Session digest

**Verdict: SD-007 audit chain broken**

- Window: 2026-07-13 10:33 UTC -> 2026-07-17 16:08 UTC (101.59h, ~1538 cycles)
- Equity: $800.00 -> $4,997.32 (range $4,201.35) | realized PnL $-2.41 | fees $1.76
- Activity: 3 open | 32 live labeled trades | 480 candidates | 15 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 32 | cold=True
- Audit: 670 records (251 non-routine) | dominant CG-000 (40% of non-routine) | chain_ok=False | retrain_requests 3
- Liquidity: spoofy 49% of classified cycles | feed errors 67

## Diagnostics
- [ERR]  **SD-007 audit chain broken**  -  hash chain first breaks at record 199  -  the trail was truncated, reordered, or corrupted past that point
- [ERR]  **SD-005 postmortem realized% contradicts its own excursions**  -  1 of 15 postmortem(s) report a realized loss (worst -6.9%) while max adverse excursion was ~0% - impossible for a real fill. The % is fabricated from a ~$0 notional (ml/postmortem.py entry_usd guard); do NOT let ml/monitor.py train or auto-adjust on these causes
- [WARN] **SD-004 audit trail dominated by one code**  -  CG-000 is 40% of 251 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
