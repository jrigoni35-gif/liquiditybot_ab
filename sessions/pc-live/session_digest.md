# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-31 04:36 UTC (1244.71h, ~2544 cycles)
- Equity (current capital epoch): $800.00 -> $795.11 (range $12.30) | 5 epochs lifetime, range $99,208.70 | realized PnL (post-close-fee) $-0.24 | fees (all legs) $10.09
- Activity: 2 open | 387 live labeled trades | 20688 candidates | 324 postmortems
- Model: level 1 | use_model=True | brier n/a | history_rows 387 | cold=False
- Audit: 70429 records (30652 non-routine) | dominant SZ-047 (73% of non-routine) | chain=SEAMS(10, benign) | retrain_requests 168
- Liquidity: spoofy 68% of non-liquid cycles | feed errors 329
- Recent (48h lens): 808 audit records | dominant LB-010 (30% of non-routine) | retrain_requests 8 | spoofy 68% (non-liquid)

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 68% of NON-LIQUID cycles (last 48h; liquid cycles are unlogged, so this is a share of degraded cycles, not of all cycles - cross-check status regimes for absolute prevalence). Spoofy suppresses sizing/taker on the affected asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  LB-010 is 30% of 593 non-routine records (last 48h)  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  10 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
