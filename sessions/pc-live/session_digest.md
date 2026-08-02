# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-02 07:58 UTC (552.07h, ~3162 cycles)
- Equity: $25,000.00 -> $4,939.78 (range $99,208.70) | realized PnL $-34.30 | fees $56.75
- Activity: 4 open | 282 live labeled trades | 8362 candidates | 242 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 282 | cold=True
- Audit: 28109 records (25405 non-routine) | dominant SZ-047 (88% of non-routine) | chain_ok=False (tamper=False, seams=6) | retrain_requests 66
- Liquidity: spoofy 42% of classified cycles | feed errors 213

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=282, brier=n/a) yet retrain was requested 66x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 88% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 88% of 25405 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  6 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
