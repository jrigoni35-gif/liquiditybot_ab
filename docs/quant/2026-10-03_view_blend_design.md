# View blend: one known algorithm that holds every signal (2026-10-03)

**Class: SAFE** (shadow research: `core/view_blend.py` is imported by no
decision module - `tests/test_target_book_shadow_pin.py` now pins
`view_blend` by name; new paper arms; no order path touched; decision
fingerprint unchanged - `core/` is outside `core.cohort.DECISION_MODULES`).
Operator, verbatim: *"Let's comprise a algorithm that is known that can
incorporate all of these within itself."*

## 1. The algorithm

Black-Litterman views on the vol-targeted basket, traded with
Garleanu-Pedersen partial adjustment inside Janecek-Shreve no-trade bands -
the standard institutional multi-signal construction:

| stage | method | where |
|---|---|---|
| prior | the vol-targeted basket; reverse optimisation pi = delta Sigma w | `view_blend.implied_returns` |
| views | each signal a row of P with q = IC x sigma x z (Grinold) | `view_blend.View`, `grinold_q` |
| confidence | Idzorek omega from c; **c from FORWARD evidence only** (LIVE or EDGE BELOW ROUND TRIP), capped 0.5 | `confidence_from_status` |
| posterior | Black-Litterman mean; no views -> exactly the basket | `posterior`, `blend` |
| constraints | long-only, each asset <= 2x basket, total <= basket total | `weights_from_mu` |
| risk switches | implied/realised vol, crowding: de-risk only, missing = neutral | `risk_scale` |
| trading | aim + band + netting, unchanged | `core/target_book.py` |

The property that makes it safe to hold every signal: **an unproven view
has zero weight**. The algorithm can carry all inputs at once without
trusting any of them, and each earns influence only as its own forward
evidence crosses the ledger's line.

## 2. Instrument checks (before any read)

- No views / no promoted views -> the posterior weights equal the basket
  exactly (`test_no_views_returns_the_basket_exactly`); on the paper book
  `bl_gated` equals `bl_window_vol40` to the cent (scratch replay of 60 days
  of real Kraken 4h bars: $998.26 both, 19 fills both).
- Posterior equals the textbook's second closed form for one view.
- Views read bars up to the decision bar only (poisoned-future test).
- Evidence is TIMESTAMPED: forward_reads appends every status to
  `outputs/reports/forward/evidence_log.jsonl`; the gated arm uses, at each
  bar, only evidence recorded before that bar's close - a later promotion
  never rewrites a closed bar (pinned).
- Four mutations (gate, long-only clip, Idzorek omega, de-risk-only) each
  turned the suite red; restored.
- Measured hypersensitivity, pinned: a hand-sized 1 % view on ~2 %-vol
  assets saturates the caps at any confidence - views must be sized by
  `grinold_q`.
- The ungated diagnostic on the same 60 days concentrated the book (LINK
  32 %, BTC 2 %) and traded 5x as much ($5.75 vs $1.35 fees, $953 vs $998).
  One sample; it is the reason the gate exists, not a verdict on the views.

## 3. Paper arms (REGISTERED 2026-10-03, start 2026-10-04T00:00Z)

`bl_gated` (evidence-earned confidence), `bl_ungated_c25` (all views at
0.25 - diagnostic, never promotes anything), `bl_window_vol40` (same-start
comparator). Views wired now, from the paper book's own bars and linked to
registered hypotheses: **P5** cross-sectional 7 d momentum (relative),
**L2** 28 d time-series momentum (absolute, per asset). IC prior 0.02;
covariance 180 bars shrunk 50 % to the diagonal. Read points: the paper
book's registered n = 180 / 540 steps, each arm vs `bl_window_vol40`.

## 4. Next inputs - rules REGISTERED HERE, before their data is fetched

Each becomes a view or a risk switch only through the same machinery; none
is fetched yet.

| id | input (public source) | rule | role |
|---|---|---|---|
| R1 iv_rv | Deribit DVOL (BTC, ETH) vs 30 d realised vol of the same asset | ratio > 1.5 -> `risk_scale` shrinks the vol target toward 0.5 (`iv_rv_hi / ratio`) | risk switch; validity test = does a high ratio predict HIGHER 7 d realised vol (not returns) |
| R2 crowding | Binance + OKX perp open interest, 7 d log change z vs prior 90 d, combined with funding z | \|z\| > 2 -> `risk_scale` toward 0.5 | risk switch; validity = larger forward 7 d drawdown |
| V-L5 | DefiLlama total stablecoin supply (already L5) | sign(z) of 7 d change, \|z\| > 1, absolute market view on every asset | view, gated by L5's forward status |
| V-L3 | perp funding 7 d mean z (already L3) | -sign(z), \|z\| > 1, absolute per-asset view | view, gated by L3's forward status |
| V-B3 | the bot's own top-confidence timing (already B3) | market-wide absolute view | view, gated by B3's forward status |

Calendar flows (quarter-hour C1, funding settlement C2, options expiry, CME
gaps) act at minutes-to-hours; they belong to execution timing of the
book's rebalance orders, not to 4 h views - deliberately excluded here.

## 5. Re-derive

`python -m pytest tests/test_view_blend.py tests/test_target_book_paper.py`;
the paper status `outputs/target_book/paper/target_book_paper.json`
(off-box: `outputs/imported_sessions/pc-live/target_book_paper.json`).
