# Session digest

**Verdict: SD-007 audit chain broken**

- Window: 2026-07-13 10:33 UTC -> 2026-07-17 17:31 UTC (102.98h, ~1561 cycles)
- Equity: $800.00 -> $4,996.58 (range $4,201.35) | realized PnL $-3.42 | fees $2.07
- Activity: 0 open | 35 live labeled trades | 482 candidates | 15 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 35 | cold=True
- Audit: 680 records (261 non-routine) | dominant CG-000 (40% of non-routine) | chain_ok=False | retrain_requests 3
- Liquidity: spoofy 48% of classified cycles | feed errors 69

## Diagnostics
- [ERR]  **SD-007 audit chain broken**  -  hash chain first breaks at record 199  -  the trail was truncated, reordered, or corrupted past that point
- [ERR]  **SD-005 postmortem realized% contradicts its own excursions**  -  1 of 15 postmortem(s) report a realized loss (worst -6.9%) while max adverse excursion was ~0% - impossible for a real fill. The % is fabricated from a ~$0 notional (ml/postmortem.py entry_usd guard); do NOT let ml/monitor.py train or auto-adjust on these causes
- [WARN] **SD-004 audit trail dominated by one code**  -  CG-000 is 40% of 261 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
