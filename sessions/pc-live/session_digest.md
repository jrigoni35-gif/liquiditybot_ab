# Session digest

**Verdict: SD-007 audit chain broken**

- Window: 2026-07-10 07:53 UTC -> 2026-07-21 02:42 UTC (258.81h, ~167 cycles)
- Equity: $25,000.00 -> $4,993.30 (range $99,208.70) | realized PnL $-3.59 | fees $7.67
- Activity: 0 open | 84 live labeled trades | 2103 candidates | 68 postmortems
- Model: level 2 | use_model=False | brier n/a | history_rows 84 | cold=True
- Audit: 1308 records (616 non-routine) | dominant OM-000 (33% of non-routine) | chain_ok=False | retrain_requests 25
- Liquidity: spoofy 38% of classified cycles | feed errors 0

## Diagnostics
- [ERR]  **SD-007 audit chain broken**  -  hash chain first breaks at record 505  -  the trail was truncated, reordered, or corrupted past that point
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=84, brier=n/a) yet retrain was requested 25x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 33% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  OM-000 is 33% of 616 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
