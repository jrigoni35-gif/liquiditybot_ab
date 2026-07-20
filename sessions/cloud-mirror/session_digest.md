# Session digest

**Verdict: SD-007 audit chain broken**

- Window: 2026-07-13 10:33 UTC -> 2026-07-20 10:21 UTC (167.8h, ~1726 cycles)
- Equity: $800.00 -> $4,996.58 (range $4,201.35) | realized PnL $-3.42 | fees $2.07
- Activity: 0 open | 68 live labeled trades | 2018 candidates | 17 postmortems
- Model: level 1 | use_model=True | brier n/a | history_rows 68 | cold=True
- Audit: 1396 records (761 non-routine) | dominant OM-040 (26% of non-routine) | chain_ok=False | retrain_requests 3
- Liquidity: spoofy 44% of classified cycles | feed errors 70

## Diagnostics
- [ERR]  **SD-007 audit chain broken**  -  hash chain first breaks at record 199  -  the trail was truncated, reordered, or corrupted past that point
- [ERR]  **SD-005 postmortem realized% contradicts its own excursions**  -  1 of 17 postmortem(s) report a realized loss (worst -6.9%) while max adverse excursion was ~0% - impossible for a real fill. The % is fabricated from a ~$0 notional (ml/postmortem.py entry_usd guard); do NOT let ml/monitor.py train or auto-adjust on these causes
