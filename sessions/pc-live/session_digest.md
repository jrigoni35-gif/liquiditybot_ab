# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-07-21 11:42 UTC (267.81h, ~1222 cycles)
- Equity: $25,000.00 -> $4,992.08 (range $99,208.70) | realized PnL $-4.18 | fees $9.10
- Activity: 1 open | 92 live labeled trades | 2175 candidates | 80 postmortems
- Model: level 2 | use_model=False | brier n/a | history_rows 92 | cold=True
- Audit: 1493 records (669 non-routine) | dominant OM-000 (33% of non-routine) | chain_ok=False (tamper=False, seams=2) | retrain_requests 26
- Liquidity: spoofy 35% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=92, brier=n/a) yet retrain was requested 26x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 33% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  OM-000 is 33% of 669 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  2 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
