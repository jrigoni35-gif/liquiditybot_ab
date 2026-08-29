# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-29 19:35 UTC (1211.7h, ~2330 cycles)
- Equity (current capital epoch): $800.00 -> $798.51 (range $10.12) | 5 epochs lifetime, range $99,208.70 | realized PnL (post-close-fee) $2.39 | fees (all legs) $8.30
- Activity: 5 open | 376 live labeled trades | 18959 candidates | 314 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 376 | cold=False
- Audit: 69812 records (30234 non-routine) | dominant SZ-047 (74% of non-routine) | chain=SEAMS(9, benign) | retrain_requests 163
- Liquidity: spoofy 72% of non-liquid cycles | feed errors 0
- Recent (48h lens): 587 audit records | dominant LB-010 (38% of non-routine) | retrain_requests 8 | spoofy 72% (non-liquid)

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 72% of NON-LIQUID cycles (last 48h; liquid cycles are unlogged, so this is a share of degraded cycles, not of all cycles - cross-check status regimes for absolute prevalence). Spoofy suppresses sizing/taker on the affected asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  LB-010 is 38% of 534 non-routine records (last 48h)  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  9 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
