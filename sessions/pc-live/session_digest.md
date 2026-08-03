# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-03 09:59 UTC (578.09h, ~3009 cycles)
- Equity: $25,000.00 -> $4,931.25 (range $99,208.70) | realized PnL $-44.13 | fees $60.07
- Activity: 1 open | 293 live labeled trades | 8916 candidates | 253 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 293 | cold=True
- Audit: 28387 records (25652 non-routine) | dominant SZ-047 (87% of non-routine) | chain_ok=False (tamper=False, seams=6) | retrain_requests 70
- Liquidity: spoofy 44% of classified cycles | feed errors 1

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=293, brier=n/a) yet retrain was requested 70x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 87% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 87% of 25652 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  6 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
