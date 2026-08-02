# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-02 22:58 UTC (567.08h, ~1729 cycles)
- Equity: $25,000.00 -> $4,940.12 (range $99,208.70) | realized PnL $-34.74 | fees $57.69
- Activity: 3 open | 289 live labeled trades | 8745 candidates | 249 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 289 | cold=True
- Audit: 28289 records (25564 non-routine) | dominant SZ-047 (87% of non-routine) | chain_ok=False (tamper=False, seams=6) | retrain_requests 69
- Liquidity: spoofy 42% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=289, brier=n/a) yet retrain was requested 69x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 87% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 87% of 25564 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  6 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
