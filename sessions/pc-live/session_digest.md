# Session digest

**Verdict: SD-007 audit chain broken**

- Window: 2026-07-10 07:53 UTC -> 2026-07-20 07:41 UTC (239.8h, ~103 cycles)
- Equity: $25,000.00 -> $4,996.78 (range $99,208.70) | realized PnL $-1.30 | fees $3.46
- Activity: 3 open | 56 live labeled trades | 1873 candidates | 53 postmortems
- Model: level 2 | use_model=False | brier n/a | history_rows 56 | cold=True
- Audit: 932 records (442 non-routine) | dominant OM-000 (32% of non-routine) | chain_ok=False | retrain_requests 22
- Liquidity: spoofy 37% of classified cycles | feed errors 0

## Diagnostics
- [ERR]  **SD-007 audit chain broken**  -  hash chain first breaks at record 505  -  the trail was truncated, reordered, or corrupted past that point
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=56, brier=n/a) yet retrain was requested 22x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 32% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  OM-000 is 32% of 442 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
