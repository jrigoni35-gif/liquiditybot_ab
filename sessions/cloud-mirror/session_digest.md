# Session digest

**Verdict: SD-005 postmortem realized% contradicts its own excursions**

- Window: 2026-07-13 10:33 UTC -> 2026-07-21 15:13 UTC (196.67h, ~1726 cycles)
- Equity: $800.00 -> $4,996.58 (range $4,201.35) | realized PnL $-3.42 | fees $2.07
- Activity: 0 open | 99 live labeled trades | 2236 candidates | 17 postmortems
- Model: level 1 | use_model=True | brier n/a | history_rows 99 | cold=True
- Audit: 1404 records (769 non-routine) | dominant OM-040 (26% of non-routine) | chain_ok=False (tamper=False, seams=4) | retrain_requests 3
- Liquidity: spoofy 44% of classified cycles | feed errors 70

## Diagnostics
- [ERR]  **SD-005 postmortem realized% contradicts its own excursions**  -  1 of 17 postmortem(s) report a realized loss (worst -6.9%) while max adverse excursion was ~0% - impossible for a real fill. The % is fabricated from a ~$0 notional (ml/postmortem.py entry_usd guard); do NOT let ml/monitor.py train or auto-adjust on these causes
- [INFO] **SD-010 audit writer seam(s)**  -  4 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
