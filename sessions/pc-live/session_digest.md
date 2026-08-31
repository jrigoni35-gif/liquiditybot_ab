# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-31 19:36 UTC (1259.72h, ~1182 cycles)
- Equity (current capital epoch): $800.00 -> $795.95 (range $12.30) | 5 epochs lifetime, range $99,208.70 | realized PnL (post-close-fee) $-0.73 | fees (all legs) $10.35
- Activity: 3 open | 389 live labeled trades | 21030 candidates | 326 postmortems
- Model: level 1 | use_model=True | brier n/a | history_rows 389 | cold=False
- Audit: 70489 records (30701 non-routine) | dominant SZ-047 (72% of non-routine) | chain=SEAMS(10, benign) | retrain_requests 171
- Liquidity: spoofy 64% of non-liquid cycles | feed errors 1059
- Recent (48h lens): 677 audit records | dominant LB-010 (26% of non-routine) | retrain_requests 8 | spoofy 64% (non-liquid)

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 64% of NON-LIQUID cycles (last 48h; liquid cycles are unlogged, so this is a share of degraded cycles, not of all cycles - cross-check status regimes for absolute prevalence). Spoofy suppresses sizing/taker on the affected asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  10 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
