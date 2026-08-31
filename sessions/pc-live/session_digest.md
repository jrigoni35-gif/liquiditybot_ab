# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-31 06:36 UTC (1246.71h, ~2781 cycles)
- Equity (current capital epoch): $800.00 -> $795.54 (range $12.30) | 5 epochs lifetime, range $99,208.70 | realized PnL (post-close-fee) $-0.24 | fees (all legs) $10.09
- Activity: 2 open | 387 live labeled trades | 20700 candidates | 324 postmortems
- Model: level 1 | use_model=True | brier n/a | history_rows 387 | cold=False
- Audit: 70432 records (30655 non-routine) | dominant SZ-047 (73% of non-routine) | chain=SEAMS(10, benign) | retrain_requests 169
- Liquidity: spoofy 67% of non-liquid cycles | feed errors 903
- Recent (48h lens): 767 audit records | dominant LB-010 (30% of non-routine) | retrain_requests 8 | spoofy 67% (non-liquid)

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 67% of NON-LIQUID cycles (last 48h; liquid cycles are unlogged, so this is a share of degraded cycles, not of all cycles - cross-check status regimes for absolute prevalence). Spoofy suppresses sizing/taker on the affected asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  LB-010 is 30% of 568 non-routine records (last 48h)  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  10 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
