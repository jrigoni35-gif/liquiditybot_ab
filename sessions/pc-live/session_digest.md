# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-02 16:58 UTC (561.08h, ~1025 cycles)
- Equity: $25,000.00 -> $4,936.92 (range $99,208.70) | realized PnL $-34.66 | fees $57.19
- Activity: 2 open | 287 live labeled trades | 8596 candidates | 246 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 287 | cold=True
- Audit: 28193 records (25479 non-routine) | dominant SZ-047 (87% of non-routine) | chain_ok=False (tamper=False, seams=6) | retrain_requests 68
- Liquidity: spoofy 42% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=287, brier=n/a) yet retrain was requested 68x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 87% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 87% of 25479 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  6 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
