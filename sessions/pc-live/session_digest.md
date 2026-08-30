# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-30 21:36 UTC (1237.71h, ~1717 cycles)
- Equity (current capital epoch): $800.00 -> $797.29 (range $10.12) | 5 epochs lifetime, range $99,208.70 | realized PnL (post-close-fee) $0.54 | fees (all legs) $9.76
- Activity: 2 open | 385 live labeled trades | 20341 candidates | 322 postmortems
- Model: level 1 | use_model=True | brier n/a | history_rows 385 | cold=False
- Audit: 70347 records (30582 non-routine) | dominant SZ-047 (73% of non-routine) | chain=SEAMS(9, benign) | retrain_requests 167
- Liquidity: spoofy 71% of non-liquid cycles | feed errors 1
- Recent (48h lens): 798 audit records | dominant LB-010 (33% of non-routine) | retrain_requests 8 | spoofy 71% (non-liquid)

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 71% of NON-LIQUID cycles (last 48h; liquid cycles are unlogged, so this is a share of degraded cycles, not of all cycles - cross-check status regimes for absolute prevalence). Spoofy suppresses sizing/taker on the affected asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  LB-010 is 33% of 595 non-routine records (last 48h)  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  9 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
