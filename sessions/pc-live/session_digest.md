# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-07-21 22:42 UTC (278.81h, ~393 cycles)
- Equity: $25,000.00 -> $4,990.55 (range $99,208.70) | realized PnL $-5.01 | fees $10.39
- Activity: 4 open | 100 live labeled trades | 2244 candidates | 88 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 100 | cold=True
- Audit: 1778 records (737 non-routine) | dominant OM-000 (32% of non-routine) | chain_ok=False (tamper=False, seams=2) | retrain_requests 28
- Liquidity: spoofy 29% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=100, brier=n/a) yet retrain was requested 28x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 32% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  OM-000 is 32% of 737 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  2 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
