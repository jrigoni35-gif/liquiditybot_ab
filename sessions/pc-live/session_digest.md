# Session digest

**Verdict: SD-007 audit chain broken**

- Window: 2026-07-10 07:53 UTC -> 2026-07-21 01:41 UTC (257.81h, ~55 cycles)
- Equity: $25,000.00 -> $4,993.64 (range $99,208.70) | realized PnL $-2.93 | fees $7.30
- Activity: 4 open | 80 live labeled trades | 2100 candidates | 66 postmortems
- Model: level 2 | use_model=False | brier n/a | history_rows 80 | cold=True
- Audit: 1280 records (602 non-routine) | dominant OM-000 (33% of non-routine) | chain_ok=False | retrain_requests 25
- Liquidity: spoofy 41% of classified cycles | feed errors 0

## Diagnostics
- [ERR]  **SD-007 audit chain broken**  -  hash chain first breaks at record 505  -  the trail was truncated, reordered, or corrupted past that point
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=80, brier=n/a) yet retrain was requested 25x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 33% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  OM-000 is 33% of 602 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
