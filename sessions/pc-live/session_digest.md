# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-30 23:36 UTC (1239.71h, ~1953 cycles)
- Equity (current capital epoch): $800.00 -> $795.25 (range $11.66) | 5 epochs lifetime, range $99,208.70 | realized PnL (post-close-fee) $0.19 | fees (all legs) $9.85
- Activity: 2 open | 386 live labeled trades | 20605 candidates | 323 postmortems
- Model: level 1 | use_model=True | brier n/a | history_rows 386 | cold=False
- Audit: 70389 records (30616 non-routine) | dominant SZ-047 (73% of non-routine) | chain=SEAMS(9, benign) | retrain_requests 167
- Liquidity: spoofy 68% of non-liquid cycles | feed errors 1
- Recent (48h lens): 816 audit records | dominant LB-010 (32% of non-routine) | retrain_requests 7 | spoofy 68% (non-liquid)

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 68% of NON-LIQUID cycles (last 48h; liquid cycles are unlogged, so this is a share of degraded cycles, not of all cycles - cross-check status regimes for absolute prevalence). Spoofy suppresses sizing/taker on the affected asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  LB-010 is 32% of 605 non-routine records (last 48h)  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  9 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
