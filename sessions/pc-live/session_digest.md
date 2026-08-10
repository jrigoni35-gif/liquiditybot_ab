# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-10 21:06 UTC (757.22h, ~1770 cycles)
- Equity: $25,000.00 -> $4,606.57 (range $99,208.70) | realized PnL $-208.26 | fees $382.81
- Activity: 4 open | 308 live labeled trades | 9788 candidates | 266 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 308 | cold=True
- Audit: 38627 records (31576 non-routine) | dominant SZ-047 (70% of non-routine) | chain_ok=False (tamper=False, seams=6) | retrain_requests 98
- Liquidity: spoofy 44% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=308, brier=n/a) yet retrain was requested 98x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 70% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 70% of 31576 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  6 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
