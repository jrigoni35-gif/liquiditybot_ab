# Session digest

**Verdict: SD-007 audit chain broken**

- Window: 2026-07-10 07:53 UTC -> 2026-07-20 17:41 UTC (249.8h, ~1180 cycles)
- Equity: $25,000.00 -> $4,995.11 (range $99,208.70) | realized PnL $-2.35 | fees $6.24
- Activity: 0 open | 73 live labeled trades | 2060 candidates | 62 postmortems
- Model: level 2 | use_model=False | brier n/a | history_rows 73 | cold=True
- Audit: 1174 records (556 non-routine) | dominant OM-000 (32% of non-routine) | chain_ok=False | retrain_requests 23
- Liquidity: spoofy 33% of classified cycles | feed errors 0

## Diagnostics
- [ERR]  **SD-007 audit chain broken**  -  hash chain first breaks at record 505  -  the trail was truncated, reordered, or corrupted past that point
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=73, brier=n/a) yet retrain was requested 23x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 32% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  OM-000 is 32% of 556 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
