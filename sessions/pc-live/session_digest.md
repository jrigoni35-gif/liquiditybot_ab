# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-29 13:35 UTC (1205.69h, ~1624 cycles)
- Equity (current capital epoch): $800.00 -> $797.66 (range $10.12) | 5 epochs lifetime, range $99,208.70 | realized PnL (post-close-fee) $2.39 | fees (all legs) $8.30
- Activity: 5 open | 376 live labeled trades | 18831 candidates | 314 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 376 | cold=False
- Audit: 69736 records (30158 non-routine) | dominant SZ-047 (74% of non-routine) | chain=SEAMS(8, benign) | retrain_requests 162
- Liquidity: spoofy 74% of non-liquid cycles | feed errors 0
- Recent (48h lens): 585 audit records | dominant LB-010 (39% of non-routine) | retrain_requests 8 | spoofy 74% (non-liquid)

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 74% of NON-LIQUID cycles (last 48h; liquid cycles are unlogged, so this is a share of degraded cycles, not of all cycles - cross-check status regimes for absolute prevalence). Spoofy suppresses sizing/taker on the affected asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  LB-010 is 39% of 515 non-routine records (last 48h)  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
