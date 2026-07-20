# Session digest

**Verdict: SD-007 audit chain broken**

- Window: 2026-07-10 07:53 UTC -> 2026-07-20 03:41 UTC (235.8h, ~1747 cycles)
- Equity: $25,000.00 -> $4,997.91 (range $99,208.70) | realized PnL $-0.84 | fees $2.60
- Activity: 5 open | 49 live labeled trades | 1849 candidates | 49 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 49 | cold=True
- Audit: 867 records (407 non-routine) | dominant OM-000 (30% of non-routine) | chain_ok=False | retrain_requests 21
- Liquidity: spoofy 40% of classified cycles | feed errors 1

## Diagnostics
- [ERR]  **SD-007 audit chain broken**  -  hash chain first breaks at record 505  -  the trail was truncated, reordered, or corrupted past that point
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=49, brier=n/a) yet retrain was requested 21x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 30% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  OM-000 is 30% of 407 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
