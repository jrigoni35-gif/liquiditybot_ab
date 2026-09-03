# Session digest

**Verdict: SD-007 audit chain broken**

- Window: n/a -> n/a (0.0h, ~0 cycles)
- Equity (current capital epoch): $0.00 -> $0.00 (range $0.00) | realized PnL (post-close-fee) $0.00 | fees (all legs) $0.00
- Activity: 0 open | 399 live labeled trades | 23187 candidates | 0 postmortems
- Model: level None | use_model=None | brier n/a | history_rows 399 | cold=True
- Audit: 0 records (0 non-routine) | dominant None (0% of non-routine) | chain=UNREADABLE(unreadable) | retrain_requests 0
- Liquidity: spoofy 0% of non-liquid cycles | feed errors 0
- Eras: current 9-16ec821e | signal_history exec_era: unavailable (signal_history.csv has no exec_era column (95 columns; label_era present=True, a label-definition axis, not the execution era)) | fills per exec_era: {} (0 rows) | pooling_hazard=False (source None)
- RAW signal-file span (signal_ts, all 23586 rows on disk): 2026-07-13T12:35:47Z -> 2026-09-03T10:30:00Z (51.91d) - NOT the TRAINED corpus span: era exclusion + the label_era filter drop rows, so the span the champion is SCORED on is shorter. For that one (the MinBTL / Sharpe-SE denominator) run scripts/champion_skill_report.py --json -> corpus_span_days

## Diagnostics
- [ERR]  **SD-007 audit chain broken**  -  hash chain first breaks at record None  -  a record was edited or removed (own-hash mismatch or dangling prev) past that point
