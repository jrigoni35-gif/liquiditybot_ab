# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-11 03:07 UTC (763.24h, ~2417 cycles)
- Equity: $25,000.00 -> $800.00 (range $99,208.70) | realized PnL $0.00 | fees $0.00
- Activity: 0 open | 313 live labeled trades | 9852 candidates | 269 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 313 | cold=True
- Audit: 39060 records (31865 non-routine) | dominant SZ-047 (70% of non-routine) | chain_ok=False (tamper=False, seams=6) | retrain_requests 98
- Liquidity: spoofy 43% of classified cycles | feed errors 1

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=313, brier=n/a) yet retrain was requested 98x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 70% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 70% of 31865 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  6 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
