# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-29 04:35 UTC (1196.69h, ~564 cycles)
- Equity (current capital epoch): $800.00 -> $797.88 (range $10.12) | 5 epochs lifetime, range $99,208.70 | realized PnL (post-close-fee) $2.88 | fees (all legs) $8.14
- Activity: 5 open | 375 live labeled trades | 18770 candidates | 313 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 375 | cold=False
- Audit: 69621 records (30059 non-routine) | dominant SZ-047 (74% of non-routine) | chain=SEAMS(8, benign) | retrain_requests 160
- Liquidity: spoofy 70% of non-liquid cycles | feed errors 0
- Recent (48h lens): 586 audit records | dominant LB-010 (38% of non-routine) | retrain_requests 7 | spoofy 70% (non-liquid)

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 70% of NON-LIQUID cycles (last 48h; liquid cycles are unlogged, so this is a share of degraded cycles, not of all cycles - cross-check status regimes for absolute prevalence). Spoofy suppresses sizing/taker on the affected asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  LB-010 is 38% of 527 non-routine records (last 48h)  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
