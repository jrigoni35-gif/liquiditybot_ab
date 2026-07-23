# Session digest

**Verdict: SD-005 postmortem realized% contradicts its own excursions**

- Window: 2026-07-13 10:33 UTC -> 2026-07-23 04:39 UTC (234.1h, ~1726 cycles)
- Equity: $800.00 -> $4,996.58 (range $4,201.35) | realized PnL $-3.42 | fees $2.07
- Activity: 0 open | 204 live labeled trades | 3015 candidates | 17 postmortems
- Model: level 1 | use_model=True | brier n/a | history_rows 204 | cold=True
- Audit: 1532 records (897 non-routine) | dominant OM-040 (22% of non-routine) | chain_ok=False (tamper=False, seams=4) | retrain_requests 120
- Liquidity: spoofy 44% of classified cycles | feed errors 70

## Diagnostics
- [ERR]  **SD-005 postmortem realized% contradicts its own excursions**  -  1 of 17 postmortem(s) report a realized loss (worst -6.9%) while max adverse excursion was ~0% - impossible for a real fill. The % is fabricated from a ~$0 notional (ml/postmortem.py entry_usd guard); do NOT let ml/monitor.py train or auto-adjust on these causes
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=204, brier=n/a) yet retrain was requested 120x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 22% of the audit trail
- [INFO] **SD-010 audit writer seam(s)**  -  4 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
