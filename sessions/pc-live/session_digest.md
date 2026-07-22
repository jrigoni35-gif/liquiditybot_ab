# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-07-22 01:42 UTC (281.81h, ~749 cycles)
- Equity: $25,000.00 -> $4,989.89 (range $99,208.70) | realized PnL $-5.34 | fees $11.24
- Activity: 2 open | 106 live labeled trades | 2311 candidates | 92 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 106 | cold=True
- Audit: 1900 records (763 non-routine) | dominant OM-000 (33% of non-routine) | chain_ok=False (tamper=False, seams=2) | retrain_requests 28
- Liquidity: spoofy 30% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=106, brier=n/a) yet retrain was requested 28x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 33% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  OM-000 is 33% of 763 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  2 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
