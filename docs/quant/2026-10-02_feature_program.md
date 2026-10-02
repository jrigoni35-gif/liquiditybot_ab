# Feature program: vol targeting, long-horizon signals, market-making viability, EDGE-1 (2026-10-02)

**Class: SAFE.** Shadow code, measurement tools and a pre-live checklist item.
No decision-module file is touched; the decision fingerprint is unchanged
(`target_book` stays in `NON_DECISION_SECTIONS` under its pin). Operator
direction, verbatim: *"All of them and correct anything it touches within
the original code."* Numbers are AS-OF 2026-10-02; re-derive with the
commands given.

## 0. Why these five (the deduction)

From `docs/quant/2026-10-02_alpha_decay_mu0_tau.md`: the bot's 18 features
carry **no market-relative edge** (every CI straddles 0; best Holm p 0.06);
their raw edge was one-regime market timing. A round trip needs IC ≥ 2c/σ_h:
**≈ 1.0 at 1 h, ≈ 0.2 at 24 h, ≈ 0.04 at a month** (σ BTC 41, ETH 55 bps/√h;
2c = 45 bps). Institutional signals run IC 0.02–0.05, so a trip edge, if
any exists, lives at weeks; otherwise positions must stop paying an exit per
idea. The five items follow from that.

## 1. Stop paying for trips that cannot win → EDGE-1 (pre-live gate)

`docs/law/pre_live_checklist.md` item 7: no live TRIP book unless a
registered signal reads `TRADEABLE AS TRIPS` in `scripts/alpha_decay_report.py`.
Reconciled with the 2026-09-28 ruling: dry-run exploration is paper tuition
that buys labels and is **not** gated. As of this record no signal passes.

## 2. Volatility targeting (risk lever, not alpha)

`core/target_book.vol_target_scale` (Moreira & Muir 2017): weight × min(cap,
target/σ_ann), cap ≤ 1 (never levered; guard FATAL above 1). Wired into
`core/idea_lab.decide`; config `vol_target_ann` = 0 keeps the registered
baseline; the validation battery grades a registered 40% arm (paired
30-bar block bootstrap) as ledger row A16.

| bars | Sharpe hold / book / book+vol | max DD hold / book / book+vol | A16 |
|---|---|---|---|
| daily, 719 d | 0.21 / 0.01 / **0.27** (diff CI +0.01, +0.68) | 42.7% / 41.9% / **25.1%** (diff CI −0.31, −0.08) | **SUPPORTED** |
| weekly, 2,527 d | 0.67 / 0.57 / 0.61 (diff CI −0.29, +0.41) | 71.9% / 55.2% / **32.2%** (diff CI −0.32, +0.01) | PARTIAL (drawdown) |

Single-asset check before it entered the battery (Binance daily 2023–26, 40%
target, 10-pt band): max DD ETH 68→55, SOL 76→58, LINK 75→54, XRP 72→58,
BTC 53→51%; Sharpe differences all inside their CIs.
Re-derive: `python scripts/target_book_validation.py`.

## 3. Timing as a tilt, not a trip

The only bot component with a CI above zero is top-confidence market TIMING
(B3 raw A +178.8 [+1.1, +288.0]; market-relative +38.0 [−45.2, +125.4];
13 weekly blocks, one regime). Registered for a forward read
(HANDOFF docket). If it holds, it enters as a bounded tilt on target weights
(`tilted_targets`, cap `tilt_cap`), which pays no exit per idea.

## 4. Long-horizon registered family (independent data)

Registered in `scripts/alpha_decay_report.py` before its data was fetched.
Events daily, horizons 1–28 d, 4-week blocks, 2c = 45 bps; GBM null with the
real external series: **1/50** upward false positives (instrument OK).

| signal | events | blocks | A = μ₀τ (bps) | halves | verdict |
|---|---|---|---|---|---|
| L1 btc_tsmom_168 | 1,308 | 48 | −17.8 [−207.9, +155.3] | −65.1 / +23.4 | NO EDGE |
| L2 tsmom_672 | 25,417 | 48 | +6.4 [−241.7, +233.2] | −50.0 / +60.4 | NO EDGE |
| L3 funding_crowd | 10,007 | 46 | −287.9 [−842.0, +164.0] | −595.5 / +25.6 | NO EDGE |
| L4 oi_crowd (BTC, ETH) | 693 | 46 | −137.7 [−586.2, +82.2] | +31.1 / −321.2 | NO EDGE |
| L5 stable_flow | 9,876 | 47 | **+253.5 [−52.5, +892.3]** | +24.4 / **+664.1** | NO EDGE (Holm p 0.23) |

L5 is the strongest candidate found anywhere in this program: drift-adjusted
CAR +141 bps at 7 d and +244 bps at 21 d after a 1-σ rise in total
stablecoin supply. It is NOT evidence: the CI includes zero and the second
half carries it. **Registered forward:** frozen as defined, read on data
after 2026-08 (unseen by the panel) with this tool. If it holds it is a
market-wide TIMING signal, i.e. a tilt candidate, not a trip signal.
Funding and OI crowding point opposite to the contrarian priors; neither is
significant.

## 5. Market making - not viable at this fee tier

`scripts/mm_viability_report.py`: per maker fill, net = half-spread (the
bot's own Kraken `spread_bps`, median/2) + 5-minute-resolution adverse
selection on Binance (reusing `scripts/adverse_selection.py`'s sign
convention and day-cluster bootstrap; that tool's 1 h grid could not see
sub-hour pick-off) − maker fee 15 bps. 622 post-only legs, 618 marked.

- Observed half-spreads are **0.0–1.8 bps** (BTC median spread 0.00, ETH
  0.01, widest FLOW 3.6 bps). Units verified against the full distribution.
- Pooled adverse selection after a maker fill: −1.5 (5 min), −3.6 (15 min),
  **−8.8 (60 min)** bps; 60-min CI [−21.8, +1.1].
- Break-even half-spread per asset **12–64 bps**; no asset viable (0 of 14).
  Maker economics need near-zero maker fees (top volume tiers), not this one.
  Paper fills from the dry-run simulator - a limit stated, not hidden.

*Correction (same day, code review): the first run counted 622 post-only
partial LEGS; per CS-1 the unit is the maker ORDER (partials aggregated).
Corrected: 443 orders (`n=443 = marked 439 + outside_price_data 4 [OK]`),
60-min adverse selection −5.5 [−11.5, −0.4] bps, break-even half-spread
still 12-64 bps, viable 0 of 14 - the conclusion stands.*

## 6. Carry (funding/basis) - not built

Requires perpetuals: a new product type, outside the bot's current spot/margin
execution path. Invariant-level operator decision; nothing built here.

## 7. Corrections made to code this program touched

1. `scripts/target_book_validation.py` and `scripts/target_book_replay.py`
   passed the config's 240-minute bar interval to the book for daily and
   weekly bars. Harmless until vol targeting annualised with it; both now
   pass the interval actually loaded.
2. Validation ledger A15 measured the drift spread over the full series but
   the gap it explains over the book's post-warm-up window. Now both over the
   book's window: **6.82 vs 1.99** (daily) and **26.25 vs 17.36** bps/bar
   (weekly) - consistent with the 10-01 record's 6.47 / 26.28 (data
   refreshed between runs). The 10-01 record §7 carries this correction.
3. `vol_target_scale` failed the shipped-scope pyright ratchet on first
   push (Optional division); fixed in the next commit, ratchet back at 0.

## 8. What to do next (operator)

- Keep the trip book in dry-run exploration (ruling stands); EDGE-1 blocks
  a live trip book until a signal passes.
- If a live path is ever wanted, the evidence favours a **vol-targeted,
  band-rebalanced holding book** with any validated timing signal as a tilt.
  Wiring it is a cohort fork needing its own record (target-book docket).
- Two forward reads are registered: B3 timing and L5 stablecoin flow.
