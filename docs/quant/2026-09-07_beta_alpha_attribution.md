# Beta / alpha attribution of every closed trip — what the bot was hedging against (2026-09-07)

**Class:** measurement, SAFE. **Instrument:** `scripts/beta_alpha_decomposition.py`
(12 pins, mutation 8/8 red). **Data as-of:** fills to 2026-09-07T07:40Z; 5m store
refreshed to 2026-09-07T19:25Z (`kraken_trades_backfill` → `tape_to_candles`
→ `candle_store compact`, MANIFEST 19:33:26Z). **Raw:** vault
`raw/quant/2026-09-07_beta_alpha_attribution.json`; refutation verdict
`raw/audits/2026-09-07_beta_alpha_refutation_verdict.md`. Re-derive with
`python scripts/beta_alpha_decomposition.py` — every number below is as-of.

## 1. The question

Operator, 2026-09-07: *does the bot have a way to learn what it is hedging
against?* A professional answers by attribution: regress each closed trip's
gross return on what a market basket did over the same window. The slope is
**beta** (the share of the bet that was the market); the intercept is **alpha**
(what the coin did relative to the market — Jensen's alpha). A hedge strips the
market part and keeps alpha; it earns its cost only where alpha is clear of
zero AND positive.

## 2. The instrument was wrong first — eight ways

The first build printed *beta 1.01, alpha +3 bps* and was refuted by a
five-lens workflow (`wf_ab66965a-c0c`) before any number was filed. Every
defect was silent — a wrong figure indistinguishable from a right one:

| # | defect | effect | fix |
|---|---|---|---|
| D0 | alpha = mean residual of an intercept fit (≡ 0) | "alpha 0.0" everywhere, on any input | intercept |
| D1 | store ended 09-02 01:55Z; fills ran to 09-07 | **22 trips dropped silently — the losing ones** (mean gross −51.8 bps; era-9 20/29, era-10 2/2); ALL alpha +3.2 → −0.0 | store refreshed; every unpriced trip counted by era + reason, with its mean gross and the tape's end |
| D2 | anchor = close of the bar CONTAINING the fill (prints ≤ 5 min AFTER it; 96% of anchors) | look-ahead at both ends; LINK p 0.018 → 0.16 | prior-CLOSED bar; the old pin *asserted* the defect and is inverted; injection pin |
| D3 | day-block percentile CI ~2× anti-conservative at G ≤ 15 (false exclusion 4–15%; P(≥1 of 10 per-asset CIs excludes 0 \| H0) = 0.62) | spurious per-asset "findings" | CR1 cluster-robust t (exact table — scipy is not in the venv) + exact 2^G sign-flip p; "clear" needs all three |
| D4 | PAXG in the basket (5m sd ≈ half a crypto major); membership drifted on gaps | beta 1.01 vs 0.85–0.90 crypto-only | crypto-only default; strict membership |
| D5 | one day = 47% of Sxy; n_eff 8.2 of 39 days | over-stated precision | n_eff printed, flagged < 10; leave-one-day-out range |
| D7 | `day_block_ci` dead; live bootstrap an inline copy | tests exercised nothing live | one bootstrap; a pin binds the helper to `decompose()` |
| D9 | (mine, on reading the table) "clear" tested `min(ci)·sign > 0` — every negative interval passes | ARB/DOT printed clear on CR1 [−149, +12] | `alpha_clear()` with hand-valued pins |

Recurrence shape: the-method #1 (a confident instrument, nothing flagging
it) and the 2026-08 "pin satisfied by a comment" — here a pin satisfied by
the defect it was named against.

## 3. Readout (crypto basket BTC+ETH+LINK minus the traded coin; 329/329 trips priced; 45 days, n_eff 9.3)

| group | n | beta [CR1] | R² | gross bps | = market | + alpha | boot CI | CR1 CI | p_flip | clear |
|---|---|---|---|---|---|---|---|---|---|---|
| **ALL** | 329 | 0.894 [0.64, 1.15] | 0.385 | −0.8 | +4.3 | **−5.1** | [−20.3, +10.7] | [−19.0, +8.9] | 0.49 | no |
| era:(blank) | 239 | 0.734 | 0.348 | −3.3 | −0.4 | −2.9 | [−12.7, +8.6] | [−12.0, +6.2] | 0.56 | no |
| era-7 (`7-e7d5ca1a`) | 56 | 0.817 | 0.278 | +58.6 | +43.4 | +15.2 | [−44.8, +104] | [−64, +94] | 0.69 | no |
| **era-9 (`9-16ec821e`)** | 29 | 1.270 [1.02, 1.52] | 0.722 | −70.5 | −16.7 | **−53.7** | [−82.7, −22.4] | [−93.8, −13.6] | **0.008** | **YES (negative)** |
| BTC | 38 | 0.968 [0.90, 1.04] | 0.955 | +14.5 | +19.1 | −4.6 | [−17.6, +2.0] | [−13.7, +4.5] | 0.21 | no |
| ETH | 58 | 0.905 | 0.647 | +21.6 | +22.6 | −1.0 | [−16.4, +22.6] | [−18.8, +16.8] | 0.96 | no |
| LINK | 26 | 0.816 | 0.067 | +35.1 | −8.2 | +43.3 | [−4.4, +181] | [−47, +134] | 0.26 | no |
| ARB | 13 | 0.486 | 0.053 | −81.9 | +5.6 | **−87.6** | [−185, −23] | [−180, +4.4] | 0.008 | no (CR1 straddles by 4 bps) |
| DOGE | 29 | 0.892 | 0.361 | −22.5 | +2.4 | −24.9 | [−86, +9] | [−73, +23] | 0.20 | no |
| SUI | 39 | 1.417 | 0.354 | −17.1 | −17.8 | +0.7 | [−35, +47] | [−39, +40] | 0.97 | no |
| XRP | 36 | 1.030 | 0.711 | −2.6 | +4.6 | −7.2 | [−24, +18] | [−27, +12] | 0.45 | no |
| long | 180 | 0.917 | 0.413 | −1.7 | +7.1 | −8.8 | [−34, +14] | [−29, +12] | 0.43 | no |
| short | 149 | 0.827 | 0.310 | +0.2 | +1.0 | −0.8 | [−19, +18] | [−18, +17] | 0.93 | no |

Groups under 10 trips (era-8 3, era-10 2, AVAX 3, LTC 7, MINA 5, PAXG 6) are
skipped. Every per-asset group carries the n_eff < 10 flag.

**Basket sensitivity** (`--basket BTC,ETH,LINK,PAXG`, 325 priced, 4 dropped on
PAXG gaps): ALL beta 1.065, alpha −2.5 [−17.7, +15.1]; era-9 beta 1.54,
alpha −55.9 [−86, −23] still clear-negative; ARB −87.8 unchanged. Beta is
FACTOR-RELATIVE (0.89 crypto-only, 1.07 with gold, 0.76–1.10 across the
refuters' variants); alpha's verdicts do not move with the basket.

**Independent second route — the hedge book as practised** (159 hedge
positions from `fills.csv`, grouped by position, all closed): notional
$39,455; gross −$9.97 (−2.5 bps); fees $315.72 (80.0 bps); **net −$325.70
(−82.5 bps)**; hold median 0.1 min, p75 0.1 min, max 76 min; **147 of 159
hedges lived under one minute.** Refuters' route K: gross −1.7 / fees 80.0 /
net −81.7 bps — agrees.

## 4. What it means (operator-facing)

1. **Pooled alpha is zero on every route** — bootstrap, CR1, sign-flip,
   two baskets, 307 and 329 trips. The bot's bets were the market (beta
   ≈ 0.9 on a crypto basket); there was no coin-specific edge to hedge
   *around*, so the hedger had nothing to protect and cost 80 bps a leg for a
   position it held for six seconds. Cut #11's "hedger off" is corroborated
   by attribution as well as by the fee ledger.
2. **The two alphas that ARE clear are NEGATIVE**: era-9 (−54 bps/trip,
   8 of 8 days negative; the 22/38-fee era with alts and the hedger on) and,
   on two routes of three, ARB (−88 bps/trip; an illiquid pair, 8 of 13 exits
   trailed or stopped). A negative alpha is not a hedging problem — a hedge
   strips the market part and KEEPS the loss — it is a selection/exit
   problem: adverse selection at entry and stop-outs. This corroborates the
   universe cut (ARB is gone) and points, as before, at the pre-named TP-width
   lever — not at re-hedging.
3. Beta ≈ 0.9 explains only ~39% of trip variance (BTC 96%, ETH 65%,
   alts 5–36%). Sixty percent of what a trip does is idiosyncratic noise —
   neither hedgeable nor alpha. That is what a coin-flip model on a 240 bps
   barrier looks like in attribution.
4. LINK's apparent +43 bps was a look-ahead artifact (p 0.018 → 0.26 on the
   corrected anchor). DOT's was the min-rule bug. Neither is a finding.

## 5. Caveats, binding

- **Power.** ±15 bps/trip pooled, ±10 BTC, ±40–180 per alt. "No measured
  alpha" ≠ "no alpha".
- **n_eff 9.3 of 45 days** pooled; per-asset 3.7–8.7. Read CR1 and p_flip,
  not the bootstrap, wherever the `!` prints.
- **Multiplicity.** ~15 per-asset comparisons; one exclusion among fifteen is
  chance. Era-9 and ARB carry p ≈ 0.008 each — below a Bonferroni 0.05/15 =
  0.0033? **No.** They survive at 5% and at 1%, not at 0.33%. Treat them as
  strong candidates consistent with the fee ledger and the exit tally, not
  as pre-registered findings.
- **Era-9 is accruing-adjacent history**, not era-8. Report; do not retune.
  Era-8 (cut #11) has 3 closed trips — unreadable. Re-run this tool at the
  registered era-8 read points (n=50, n=100).
- **Duration form.** Windows are 6 min to 40 h; a single slope across them
  is the simplest model, not the right one. Untested.
- **The tape is a store, not the venue.** Bars are rebuilt from the local
  trade tape; the refuters' scratch bars for 09-02→09-07 and the compaction
  pipeline's agree on the headline within rounding (−4.6 vs −5.1 bps).

## 6. Owed

- Re-run at era-8 n=50 and n=100 (`cohort_eval` read points); file both.
- If the TP-width lever is ever armed (ALGO-5), attribution per era before
  and after is the cheapest test that it changed the residual, not the beta.
- ARB stays out of the universe; nothing here argues for any alt's return.
