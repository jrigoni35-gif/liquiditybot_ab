# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-06 12:02 UTC (652.14h, ~1575 cycles)
- Equity: $25,000.00 -> $4,936.04 (range $99,208.70) | realized PnL $-44.10 | fees $62.40
- Activity: 3 open | 300 live labeled trades | 9325 candidates | 260 postmortems
- Model: level 2 | use_model=False | brier n/a | history_rows 300 | cold=True
- Audit: 28933 records (26083 non-routine) | dominant SZ-047 (85% of non-routine) | chain_ok=False (tamper=False, seams=6) | retrain_requests 82
- Liquidity: spoofy 47% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=300, brier=n/a) yet retrain was requested 82x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 85% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 85% of 26083 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  6 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
