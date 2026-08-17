# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-17 10:34 UTC (914.69h, ~1901 cycles)
- Equity: $25,000.00 -> $798.66 (range $99,208.70) | realized PnL $-0.05 | fees $3.03
- Activity: 1 open | 332 live labeled trades | 10470 candidates | 281 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 332 | cold=True
- Audit: 45203 records (35266 non-routine) | dominant SZ-047 (63% of non-routine) | chain_ok=False (tamper=False, seams=6) | retrain_requests 117
- Liquidity: spoofy 57% of classified cycles | feed errors 269

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=332, brier=n/a) yet retrain was requested 117x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 63% of the audit trail
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 57% of classified cycles, which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 63% of 35266 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  6 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
