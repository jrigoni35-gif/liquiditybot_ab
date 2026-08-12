# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-12 08:09 UTC (792.27h, ~556 cycles)
- Equity: $25,000.00 -> $799.91 (range $99,208.70) | realized PnL $0.06 | fees $0.31
- Activity: 3 open | 314 live labeled trades | 9976 candidates | 270 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 314 | cold=True
- Audit: 44598 records (34751 non-routine) | dominant SZ-047 (64% of non-routine) | chain_ok=False (tamper=False, seams=6) | retrain_requests 103
- Liquidity: spoofy 49% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=314, brier=n/a) yet retrain was requested 103x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 64% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 64% of 34751 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  6 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
