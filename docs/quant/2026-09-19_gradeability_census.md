# Gradeability census (run 2026-09-20T02:31:36Z, SAFE-plane)

Window since 2026-09-08T00:00:00Z (era-9 = 12-10d4d0c2).

| absorb key | count |
|---|---|
| EN-030 | 60574 |
| arrivals | 77676 |
| EN-010 | 1 |

- arrivals N = 77676
- gradeable (priced entries) g = 51
- lost forever L (EN-020+EN-030, no per-arrival record exists) = 60574
- deep pipeline D (gate stack reached, no priced entry) = 17051
- CV records carrying an asset (retro path via Kraken-OHLC proxy, Lane B) = 455
- DE-010 coverage (post-capture events) = 0
- DE-010 derived fields: asset, ts, decision_mid, mid_available, gates, absorb, direction, confidence

Reconciliation pins held: EN-020+EN-030 <= N, g <= N-EN-020-EN-030,
L+g+D == N. Unreconciled census = refused census.
