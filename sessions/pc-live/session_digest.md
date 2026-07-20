# Session digest

**Verdict: SD-007 audit chain broken**

- Window: 2026-07-10 07:53 UTC -> 2026-07-20 13:41 UTC (245.8h, ~762 cycles)
- Equity: $25,000.00 -> $4,995.17 (range $99,208.70) | realized PnL $-1.86 | fees $4.90
- Activity: 4 open | 63 live labeled trades | 1984 candidates | 55 postmortems
- Model: level 2 | use_model=False | brier n/a | history_rows 63 | cold=True
- Audit: 1072 records (500 non-routine) | dominant OM-000 (32% of non-routine) | chain_ok=False | retrain_requests 23
- Liquidity: spoofy 36% of classified cycles | feed errors 0

## Diagnostics
- [ERR]  **SD-007 audit chain broken**  -  hash chain first breaks at record 505  -  the trail was truncated, reordered, or corrupted past that point
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=63, brier=n/a) yet retrain was requested 23x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 32% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  OM-000 is 32% of 500 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
