# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-07-21 19:42 UTC (275.81h, ~37 cycles)
- Equity: $25,000.00 -> $4,991.27 (range $99,208.70) | realized PnL $-4.55 | fees $9.79
- Activity: 4 open | 96 live labeled trades | 2226 candidates | 84 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 96 | cold=True
- Audit: 1665 records (719 non-routine) | dominant OM-000 (32% of non-routine) | chain_ok=False (tamper=False, seams=2) | retrain_requests 27
- Liquidity: spoofy 27% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=96, brier=n/a) yet retrain was requested 27x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 32% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  OM-000 is 32% of 719 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  2 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
