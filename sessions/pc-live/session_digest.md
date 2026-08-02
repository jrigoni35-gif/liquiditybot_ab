# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-02 00:57 UTC (545.07h, ~2345 cycles)
- Equity: $25,000.00 -> $4,934.59 (range $99,208.70) | realized PnL $-34.01 | fees $56.49
- Activity: 2 open | 279 live labeled trades | 8186 candidates | 238 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 279 | cold=True
- Audit: 28031 records (25346 non-routine) | dominant SZ-047 (88% of non-routine) | chain_ok=False (tamper=False, seams=6) | retrain_requests 65
- Liquidity: spoofy 41% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=279, brier=n/a) yet retrain was requested 65x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 88% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 88% of 25346 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  6 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
