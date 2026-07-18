# Session digest

**Verdict: SD-007 audit chain broken**

- Window: 2026-07-10 07:53 UTC -> 2026-07-18 23:40 UTC (207.78h, ~699 cycles)
- Equity: $25,000.00 -> $4,999.69 (range $99,208.70) | realized PnL $0.00 | fees $0.29
- Activity: 4 open | 35 live labeled trades | 1366 candidates | 39 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 35 | cold=True
- Audit: 597 records (283 non-routine) | dominant ML-031 (31% of non-routine) | chain_ok=False | retrain_requests 18
- Liquidity: spoofy 32% of classified cycles | feed errors 253

## Diagnostics
- [ERR]  **SD-007 audit chain broken**  -  hash chain first breaks at record 505  -  the trail was truncated, reordered, or corrupted past that point
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=35, brier=n/a) yet retrain was requested 18x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 31% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  ML-031 is 31% of 283 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
