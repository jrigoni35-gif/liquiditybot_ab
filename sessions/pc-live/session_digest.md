# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-31 23:36 UTC (1263.72h, ~1651 cycles)
- Equity (current capital epoch): $800.00 -> $795.22 (range $12.30) | 5 epochs lifetime, range $99,208.70 | realized PnL (post-close-fee) $-0.73 | fees (all legs) $10.40
- Activity: 4 open | 389 live labeled trades | 21076 candidates | 326 postmortems
- Model: level 1 | use_model=True | brier n/a | history_rows 389 | cold=False
- Audit: 70606 records (30728 non-routine) | dominant SZ-047 (72% of non-routine) | chain=SEAMS(10, benign) | retrain_requests 171
- Liquidity: spoofy 64% of non-liquid cycles | feed errors 1059
- Recent (48h lens): 735 audit records | dominant LB-010 (23% of non-routine) | retrain_requests 7 | spoofy 64% (non-liquid)

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 64% of NON-LIQUID cycles (last 48h; liquid cycles are unlogged, so this is a share of degraded cycles, not of all cycles - cross-check status regimes for absolute prevalence). Spoofy suppresses sizing/taker on the affected asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  10 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
