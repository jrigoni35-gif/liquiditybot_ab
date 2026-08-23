# Session digest

**Verdict: SD-007 audit chain broken**

- Window: n/a -> n/a (0.0h, ~0 cycles)
- Equity: $0.00 -> $0.00 (range $0.00) | realized PnL $0.00 | fees $0.00
- Activity: 0 open | 348 live labeled trades | 14494 candidates | 283 postmortems
- Model: level None | use_model=None | brier n/a | history_rows 348 | cold=True
- Audit: 0 records (0 non-routine) | dominant None (0% of non-routine) | chain_ok=False (tamper=True, seams=0) | retrain_requests 0
- Liquidity: spoofy 0% of classified cycles | feed errors 0

## Diagnostics
- [ERR]  **SD-007 audit chain broken**  -  hash chain first breaks at record None  -  a record was edited or removed (own-hash mismatch or dangling prev) past that point
