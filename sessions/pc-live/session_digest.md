# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-08 02:03 UTC (690.16h, ~844 cycles)
- Equity: $25,000.00 -> $4,615.25 (range $99,208.70) | realized PnL $-208.22 | fees $382.28
- Activity: 3 open | 304 live labeled trades | 9477 candidates | 262 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 304 | cold=True
- Audit: 33343 records (28718 non-routine) | dominant SZ-047 (78% of non-routine) | chain_ok=False (tamper=False, seams=6) | retrain_requests 88
- Liquidity: spoofy 35% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=304, brier=n/a) yet retrain was requested 88x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 78% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 78% of 28718 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  6 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
