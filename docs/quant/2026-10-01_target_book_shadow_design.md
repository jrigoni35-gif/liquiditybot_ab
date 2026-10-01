# Target-inventory basket book + market-reactive idea lab — SHADOW design record (2026-10-01)

**Class: SAFE (shadow).** No order, size, stop or fill changes. Decision
fingerprint unchanged: `config_fingerprint` and `code_fingerprint` were
measured identical before and after this change on this box (cfg
`6709bb70f73d`, code `f766b86ab726` under this box's Python; the PC's own
stamp is what its boot computes). Wiring is a separate, operator-adjudicated
step (§6).

## 1. Operator request (verbatim intent)

> "Missing: target weights, no-trade bands, the aim-portfolio blend, and
> cross-asset netting and rebalancing … build these based on a revolving
> market like the market presents; if it is receiving pressure that is
> causing errors, create an algorithm that continually generates new ideas
> based on how the market is reacting."

Context: fills/postmortem analysis the same day showed the trade book's loss
is friction, not direction (453 closed trades: gross −$8.16, fees $105.75;
two-thirds of postmortem trips never reached +0.45% MFE — the round trip at
15/30). The request is to stop paying a round trip per idea.

## 2. What shipped

| file | what |
|---|---|
| `core/target_book.py` | pure decision math: base weights (equal / inverse-vol), bounded tilt, Gârleanu–Pedersen aim blend, Janeček–Shreve no-trade band `δ = (3/(2γ)·λ·w²(1−w)²)^(1/3)`, trade-to-band-EDGE, one net order per asset, sells fund buys, buys clamped to cash, long-only, venue-minimum skip, asset drawdown floor; pressure overlay (fill ratio, adverse markout, vol shock, drawdown) that can only widen / slow / halt buys |
| `core/idea_lab.py` | finite pre-declared family (config grids: 3γ × 3 aim × 2 weighting × 3 tilt = 54); market reading (cross-sectional relative-return lag-1 autocorrelation at a 2/√n cut → reverting / trending / neutral; short/long σ → shock); births only on a reading change or baseline pressure, each id at most once; forward-only paper books (decide at close i on data ≤ i, maker limit filled on bar i+1 only on trade-through, mark at close i+1); graded against a buy-and-hold twin from birth; DSR-deflated over every idea ever born; retire on negative excess after `retire_after_steps`; **never promotes** |
| `scripts/target_book_replay.py` | grades buy_hold / no_band / target_book / the lab on Kraken PUBLIC OHLC (read-only); `--csv-dir` offline |
| `config.json` `target_book` | all knobs; `enabled:false`, `mode:"shadow"`; λ comes from `pretrade.maker_fee_bps` (single source) |
| `core/config_guard.py` `_target_book_checks` | FATAL on incoherent values and on any live claim (`enabled:true` / `mode != shadow`) |
| `core/codes.py` | TB-000..060, IL-000..030 |
| `core/cohort.py` | `target_book` in `NON_DECISION_SECTIONS` — justified ONLY by the pin below |
| tests | `test_target_book.py` (band closed form, edge-not-centre, netting, clamp, long-only, pressure de-risk-only), `test_idea_lab.py` (family = grid, birth/retire/reconcile, never promotes, two look-ahead pins), `test_target_book_shadow_pin.py` (no decision module references the book; section fingerprint-neutral only while shadow; guard FATALs; offline replay writes only to `--out`) |

**Mutation verification (bytecode cache disabled — a same-size, same-second
mutant otherwise re-uses the stale `.pyc`, which produced one false red and
could produce false greens):** five one-character look-ahead mutants —
decision price at i+1, `read_market` slice to i+2, σ slice to i+2, tilt at
i+1, settlement on i+2 — each turned its pin red; the restored file is
byte-identical and green. A decision-module reference to `target_book` turns
the shadow pin red. The first look-ahead pin as written did NOT catch the
decision-price peek (settlement legitimately reads i+1); `decide()` was split
from `step_book()` and pinned on truncated AND poisoned futures because of it.

## 3. First replay (Kraken public OHLC, BTC/ETH/PAXG/LINK, maker 15 bps, $800)

AS-OF 2026-10-01; re-derive with `python scripts/target_book_replay.py [--interval 1440]`.

| bars | arm | return | fees | traded | max DD |
|---|---|---|---|---|---|
| 4h, 677 steps (~113 d) | buy_hold | +44.51% | $1.08 | $0 | 12.0% |
| | no_band | +41.82% | $1.65 | $377 | 12.0% |
| | target_book | +44.82% | $1.11 | $21 | 12.0% |
| daily, 677 steps (~677 d) | buy_hold | +0.84% | $1.08 | $0 | 43.1% |
| | no_band | −25.39% | $3.46 | $1,588 | 43.2% |
| | target_book | −9.82% | $1.77 | $457 | 41.7% |

Idea lab: 4h — 33 of 54 born (12 alive + 21 retired, reconciles), best DSR
0.50, **0 EVIDENCE**; daily — 28 born (10 + 18), best DSR 0.33, **0 EVIDENCE**.

**Read (measurement, not verdict):**
1. **The band does what it was built for — fees.** Fees are dollars, not the
   $105.75 the trip book paid; the band cut traded notional 18× (4h) and
   3.5× (daily) against no-band.
2. **The rebalancing premium was NEGATIVE over the daily window.** The four
   assets trended apart (PAXG up, LINK/ETH down); equal-weight rebalancing
   kept buying the loser. The band limited the damage (−9.8% vs −25.4%) but
   holding beat both. The premium needs relative mean reversion; this
   universe did not supply it over ~2 years.
3. **Inverse-vol ideas led the daily lab** (heavier gold, lighter alts) —
   consistent with (2), and not evidence: best DSR 0.33 against a 0.95 bar.
4. **One window per interval, one universe, one fill model.** No claim
   survives that. 113 days of 4h bars is one regime.

## 4. Honest limits

- Fill model: maker at the decision close, trade-through on the next bar,
  no queue, no partials, no adverse-selection beyond what the next close
  shows. Optimistic on fill rate, pessimistic on price improvement.
- Books are seeded at target on their birth close (maker fee paid) so a
  grade measures the policy, not a cash ramp. A live book would ramp.
- The band formula is the single-asset small-cost asymptotic applied per
  asset — an approximation for a correlated basket.
- Kraken's public OHLC returns the last 720 bars only: 4h ≈ 120 days, daily ≈
  2 years. Longer history needs the candle journal or another read-only source.

## 5. Registration (set BEFORE any further look)

- Unit: a STEP is one bar decided and settled; an IDEA is one family member
  born. Reconciliation printed every run: born = alive + retired.
- `min_evidence_steps` 360 and `dsr_bar` 0.95 are measurement standards,
  not tunables (guard: `min_evidence_steps ≥ retire_after_steps`,
  `dsr_bar ∈ [0.5, 1)`). Never lowered to make a row read EVIDENCE.
- The family is the config grid. Widening it after looking is a new
  registration, and its size raises the DSR trial count.

## 6. What wiring would take (NOT done — operator decision)

Wiring the book into the order path forks the decision cohort on the sizing,
exit-geometry and order-lifecycle axes. It needs: (a) an operator decision
record naming the book, its capital share, and its interaction with the
heat cap / slot count / long book (the long book is the nearest existing
mechanism — post-only averaging accumulation in BTC/ETH); (b) routing every
order through PositionSizer × RiskProtocolStack, the firewall and the
pretrade gate (architecture law — new position logic goes through these, not
beside); (c) removing `target_book` from `NON_DECISION_SECTIONS` and the
guard's live-claim FATAL in the same commit; (d) its own n=50 / n=100
registration. Promotion of any lab idea follows the shadow-policy promotion
pattern (`docs/law/shadow_policy_promotion.md`): sample, sign with CI,
beats what trades, overfit battery green, operator record.

## 7. Validation battery (same day, operator: "backtest, forward walks, Brownian test, Markov chain; if anything is assumed, reverse-engineer it")

Tool: `scripts/target_book_validation.py` (thresholds registered in its
docstring BEFORE the first run: α 0.05, 5 expanding folds after 40% train,
argmax selection, PBO CSCV 8 blocks, 200 null paths, seed 7). Run
2026-10-01T23:07Z on Kraken public OHLC: daily 720 bars (719 d) and weekly
362 bars (2,527 d, since PAXG's listing). AS-OF; re-derive with
`python scripts/target_book_validation.py`. Output JSON under
`outputs/reports/target_book/validation_*.json`.

**An instrument failed first, and was fixed before any reading was used.**
The lab's market-state classifier (1/√n cut) fired on **14.2%** of 4,000
pure-GBM windows against a 4.6% design rate (true spread 0.107 vs assumed
0.078: relative returns sum to zero across assets and the pooled ratio is
dominated by the highest-vol asset). Replaced with the self-normalised
statistic z = Σc_k/√Σc_k²; measured **4.0% / 4.1%** (n=2,000 each) in the
battery, 4.7% on 4,000 in isolation. Pinned by
`test_state_classifier_false_positive_rate_on_noise`, which the naive cut
fails at 21.9%. Every idea-lab birth before this fix reacted to noise ~3×
too often.

| # | claim | daily (719 d) | weekly (2,527 d) |
|---|---|---|---|
| A1 | `plan()` implements constant-mix rebalancing | **PROVEN** (err 2.9e-15) | **PROVEN** (1.6e-15) |
| A2 | constant-mix growth = Σw(μ+σ²/2) − ½w'Σw | **PROVEN** (z +1.86) | **PROVEN** (z −0.60) |
| A3 | Janeček–Shreve width near-optimal (CRRA CE, 50 bps, ×0/0.5/1/2/4) | NOT REFUTED — best ×0.5, its CI vs ×1 includes 0; ×0 and ×4 clearly worse | NOT REFUTED — same shape; ×2, ×4 clearly worse |
| A4 | classifier fires ~4.6% on noise | **PROVEN after the fix** (4.0%) | **PROVEN** (4.1%) |
| A5 | gap to holding = rebalancing against the trend | **SUPPORTED**: −$86.28; ETH −$50.02, LINK −$29.59 (book held MORE of the fallers); residual −$0.69 | **SUPPORTED**: −$1,171; BTC −$900, ETH −$550 (book held LESS of the risers); residual −$2.07 |
| A6 | fees are not the loss | **PROVEN** ($1.77) | **PROVEN** ($3.15) |
| A7 | robust to fill model and seeding | **PROVEN** (penetration 0/5/20 bps identical; ramp −0.082 vs −0.113) | **PROVEN** (ramp −0.627 vs −0.477) |
| A8 | the ORDER of returns (trend/reversion) decided it | NOT PROVEN (time-shuffle p 0.27) | NOT PROVEN (p 0.76) |
| A9 | consistent with a correlated random walk | **CONSISTENT** (GBM pct 0.21) | **CONSISTENT** (pct 0.56) |
| A10 | walk-forward selection beats the fixed baseline | registered rule says SUPPORTED (4/5, PBO 0.30), but 4/5 is p 0.375 and selected beat HOLD 3/5 — not evidence | NOT SUPPORTED (2/5; **PBO 0.83 — selection anti-selects**) |
| A11 | bar states have memory (Markov) | NOT PROVEN (G 8.2; GBM p 0.99, perm p 0.94; dwell 1.3–1.4 bars = iid) | NOT PROVEN (G 10.1; p 0.69) |
| A12 | a reversal state predicts the next bar's rebalancing payoff | NOT PROVEN (rev−cont +0.04 bps, p 0.89) | NOT PROVEN (−4.93 bps, p 0.15) |
| A13 | the lab's state changes are signal, not window overlap | NOT PROVEN — stay rate 0.988 vs GBM 0.984 | NOT PROVEN — 1.000 vs 0.985 |
| A14 | relative prices mean-revert (rebalancing's premise) | NOT PROVEN — no pair VR(4) rejects a random walk | NOT PROVEN — only BTC/PAXG VR(16) z +2.30 (trending), 1 of 40 tests |
| A15 | holding wins because the drift spread exceeds the diversification return | **PROVEN**: spread 6.47 vs 2.01 bps/bar | **PROVEN**: 26.28 vs 17.31 bps/bar |

**The reverse-engineered mechanism (A5 + A9 + A8 + A15 together).** The
loss needs no trend, no regime and no market structure at all: a pure
correlated random walk with these four drifts reproduces it (real result at
the 21st / 56th GBM percentile; GBM null means are themselves negative,
−0.035 and −0.570). Holding lets weight drift into whichever asset has the
highest drift; rebalancing caps that and is paid the diversification return
instead. Here the best asset out-grew the basket by 3.2× (daily, PAXG) and
1.5× (weekly, BTC) the diversification return, so rebalancing had to lose,
and the per-asset attribution shows exactly where (97–99% of the gap
explained per asset). Shuffling time does not change the answer, so
trend/reversion timing is not the cause.

**What this means for the design.**
1. The execution layer is proven: `plan()` is exact constant-mix, the
   band is near-optimal under its own model, fees are dollars, fills and
   seeding do not move the verdict.
2. The *premise* of a rebalancing book (relative mean reversion) is not
   present in this universe at daily or weekly horizons, and the drift
   spread beats the diversification return in both windows.
3. The idea lab's reactive birth trigger has nothing to react to:
   per-bar states carry no memory beyond a random walk, do not predict the
   rebalancing payoff, and the lab's rolling-state persistence is window
   overlap. Weekly walk-forward selection anti-selects (PBO 0.83).
4. Daily inverse-volatility ideas "won" (27 of the 34 winners) because the
   lowest-vol asset, gold, was also the best performer in that window: a
   coincidence of the period, not a mechanism. Weekly, where BTC led, every
   one of the 54 ideas lost to holding.

**Not claimed.** No statement here is a verdict on the live 5m trip book or
on any cohort; this is a shadow book graded on two windows of one universe.
Multiple comparisons: 8 state×interval payoff cells were tested; one (weekly
rev-hi, −10.2 bps, CI excludes 0) is within the ~0.4 false discoveries
expected at α 0.05.
