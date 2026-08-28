# Session digest

**Verdict: SD-004 audit trail dominated by one code**

- Window: 2026-08-27 14:16 UTC -> 2026-08-27 19:21 UTC (5.08h, ~0 cycles)
- Equity (current capital epoch): $0.00 -> $0.00 (range $0.00) | realized PnL (post-close-fee) $0.00 | fees (all legs) $0.00
- Activity: 0 open | 373 live labeled trades | 17842 candidates | 0 postmortems
- Model: level None | use_model=None | brier n/a | history_rows 373 | cold=True
- Audit: 1974 records (1974 non-routine) | dominant LB-010 (31% of non-routine) | chain=OK | retrain_requests 0
- Liquidity: spoofy 0% of non-liquid cycles | feed errors 0
- Recent (48h lens): 1974 audit records | dominant LB-010 (31% of non-routine) | retrain_requests 0 | spoofy 0% (non-liquid)

## Diagnostics
- [WARN] **SD-004 audit trail dominated by one code**  -  LB-010 is 31% of 1974 non-routine records (last 48h)  -  consequential dispositions are buried; rate-limit that emitter
