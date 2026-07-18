# Session digest

**Verdict: SD-007 audit chain broken**

- Window: 2026-07-10 07:53 UTC -> 2026-07-18 19:40 UTC (203.78h, ~271 cycles)
- Equity: $25,000.00 -> $5,000.00 (range $99,208.70) | realized PnL $0.00 | fees $0.00
- Activity: 0 open | 35 live labeled trades | 1299 candidates | 39 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 35 | cold=True
- Audit: 572 records (265 non-routine) | dominant ML-031 (33% of non-routine) | chain_ok=False | retrain_requests 17
- Liquidity: spoofy 32% of classified cycles | feed errors 0

## Diagnostics
- [ERR]  **SD-007 audit chain broken**  -  hash chain first breaks at record 505  -  the trail was truncated, reordered, or corrupted past that point
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=35, brier=n/a) yet retrain was requested 17x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 33% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  ML-031 is 33% of 265 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
