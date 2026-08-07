# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-07 02:02 UTC (666.15h, ~127 cycles)
- Equity: $25,000.00 -> $4,619.36 (range $99,208.70) | realized PnL $-207.93 | fees $363.85
- Activity: 5 open | 302 live labeled trades | 9390 candidates | 261 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 302 | cold=True
- Audit: 29523 records (26661 non-routine) | dominant SZ-047 (84% of non-routine) | chain_ok=False (tamper=False, seams=6) | retrain_requests 84
- Liquidity: spoofy 40% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=302, brier=n/a) yet retrain was requested 84x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 84% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 84% of 26661 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  6 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
