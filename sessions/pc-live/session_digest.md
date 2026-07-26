# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-07-26 16:52 UTC (392.99h, ~1494 cycles)
- Equity: $25,000.00 -> $4,965.99 (range $99,208.70) | realized PnL $-20.08 | fees $34.85
- Activity: 1 open | 241 live labeled trades | 4625 candidates | 205 postmortems
- Model: level 2 | use_model=False | brier n/a | history_rows 241 | cold=True
- Audit: 12278 records (9719 non-routine) | dominant SZ-047 (79% of non-routine) | chain_ok=False (tamper=False, seams=2) | retrain_requests 42
- Liquidity: spoofy 60% of classified cycles | feed errors 4

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=241, brier=n/a) yet retrain was requested 42x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 79% of the audit trail
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 60% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 79% of 9719 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  2 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
