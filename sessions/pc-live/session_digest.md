# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-30 04:35 UTC (1220.7h, ~3390 cycles)
- Equity (current capital epoch): $800.00 -> $798.00 (range $10.12) | 5 epochs lifetime, range $99,208.70 | realized PnL (post-close-fee) $1.72 | fees (all legs) $8.72
- Activity: 5 open | 378 live labeled trades | 19104 candidates | 316 postmortems
- Model: level 1 | use_model=True | brier n/a | history_rows 378 | cold=False
- Audit: 70084 records (30351 non-routine) | dominant SZ-047 (73% of non-routine) | chain=SEAMS(9, benign) | retrain_requests 164
- Liquidity: spoofy 73% of non-liquid cycles | feed errors 0
- Recent (48h lens): 750 audit records | dominant LB-010 (36% of non-routine) | retrain_requests 7 | spoofy 73% (non-liquid)

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 73% of NON-LIQUID cycles (last 48h; liquid cycles are unlogged, so this is a share of degraded cycles, not of all cycles - cross-check status regimes for absolute prevalence). Spoofy suppresses sizing/taker on the affected asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  LB-010 is 36% of 551 non-routine records (last 48h)  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  9 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
