# Session digest

**Verdict: SD-005 postmortem realized% contradicts its own excursions**

- Window: 2026-07-13 10:33 UTC -> 2026-07-31 01:16 UTC (422.72h, ~1726 cycles)
- Equity: $800.00 -> $4,996.58 (range $4,201.35) | realized PnL $0.00 | fees $0.78
- Activity: 2 open | 294 live labeled trades | 9057 candidates | 17 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 294 | cold=True
- Audit: 1572 records (937 non-routine) | dominant OM-040 (22% of non-routine) | chain_ok=False (tamper=False, seams=4) | retrain_requests 121
- Liquidity: spoofy 44% of classified cycles | feed errors 70

## Diagnostics
- [ERR]  **SD-005 postmortem realized% contradicts its own excursions**  -  1 of 17 postmortem(s) report a realized loss (worst -6.9%) while max adverse excursion was ~0% - impossible for a real fill. The % is fabricated from a ~$0 notional (ml/postmortem.py entry_usd guard); do NOT let ml/monitor.py train or auto-adjust on these causes
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=294, brier=n/a) yet retrain was requested 121x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 22% of the audit trail
- [INFO] **SD-010 audit writer seam(s)**  -  4 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
