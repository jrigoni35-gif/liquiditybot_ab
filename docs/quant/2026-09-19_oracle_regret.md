# Oracle regret — did era-9 recognize the perfect decision, and would the judge's inventory agree? (2026-09-19, SAFE-class)

Measurement only. Oracle = perfect-hindsight enter/skip verdict at the bot's
OWN label geometry (+1.80% / −1.35%, 432×5m = 36h vertical), graded on the
Binance research corpus (~7-9 bps USD/USDT basis vs Kraken — shape, not
venue-exact). Companion: `2026-09-19_missed_positions.md`.
Charts: `outputs/reports/oracle_regret_2026-09-19.png`; grader:
`outputs/reports/oracle_regret_2026-09-19.py` (rerunnable scratch).

## Q1 — Do we even RECORD the decision population enough to recognize "perfect"?

**Mostly no.** Of 8,040 entry-sweep arrivals, the 6,643 signal-unconfirmed
skips (EN-030) exist ONLY as a cumulative count in EN-000 vectors — no
per-decision record (asset/ts/snapshot) exists to grade. The gradeable
population is what is individually logged:

| Population | n | Gradeable? |
|---|---|---|
| Actual entry fills | 58 | yes (asset, ts, fill price) |
| Conviction-stack evals (CV-000/010/030, report-mode) | 455 | yes (asset, ts) |
| Expired unfilled buy orders (OM-040) | 347 | yes (pair, created_ts) |
| Signal-unconfirmed skips (EN-030) | 6,643 | **NO — aggregate only** |

This is an intake defect, not a trading defect: 82.6% of the decision
population is invisible to any future judge. (SAFE fix when approved: log
EN-030 individually with asset/ts — measurement-plane only.)

## Q2 — Of what IS recorded, did decisions match the perfect ones?

**The bot's own entries (47 evaluable): oracle keeps 22, skips 25.** The
oracle's mix: BTC 6/16, ETH 8/13, LINK 7/9, **PAXG 1/11** — the held
inventory is tilted into the one asset whose sigma cannot cash the bracket.

**The report-mode conviction stack is INVERTED against the oracle:**
- CV-000 (admitted): 21/64 evaluable PT-first = **33%** — at/below the
  unconditional tape (24-37%).
- CV-010 (denied, agreement-low): 208/208 PT-first — **but all 208 are ONE
  ETH cluster on 2026-09-10** (median est_edge 107 bps vs the ~126 bps
  2×cost bar). n_eff ≈ 1 window, not 208 wins — the day-block lesson. What
  it proves: on 09-10 the stack repeatedly read a real, PT-delivering ETH
  move as "agreement 0.0" — the disagreement was with the gate stack's own
  terms, and the tape sided with the edge estimate.
- CV-030 (denied, regime-unknown): 21% PT-first — correctly refused.

**The expired unfilled orders are the largest clean miss pool:**
269/309 evaluable = **87% PT-first**. This is mechanical adverse selection,
not luck: post-only buy limits fill when price comes INTO them (the toxic
case) and expire exactly when price runs away (the winning case). The
execution layer systematically keeps the losing half and discards the
winning half of its own intentions.

## Q3 — The judge connection: what was beneficial for inventory?

Mapped to the judge rubric (`2026-09-19_institutional_judge_prep.md`):

- **Asset inventory / contribution:** oracle mix ≈ {LINK, ETH}-heavy,
  PAXG ≈ 0. Held mix carried PAXG 11 entries / 211 heat-hours / net-negative
  contribution; LINK was the best-held book (78% PT-first) but took the
  fewest entries of the three majors. A contribution-aware judge would flag
  the PAXG allocation as inventory mis-weighting, independent of any trade
  verdict.
- **Margin/heat:** ~769 heat-hours across 46 in-era closed trips; the 25
  oracle-skip entries occupied roughly half of that capacity while
  contributing losses — heat spent on positions the oracle refuses is the
  margin line item a judge should price first.
- **Profit pooling:** actual net stays the era readout's authority
  (−$17.20 banked on the SELECTED row); the oracle's label-geometry P&L on
  the same entries is an UPPER bound the shipped trail cannot realize
  (09-16 firing audit: the give-back overlay cannot pay a label-PT-sized
  win). The judge must read oracle numbers as direction, never as a
  capturable target.

## Honest limits

Binance tape basis (~7-9 bps); label-oracle ignores the 79% non-fill rate
and the exit overlay; CV-010's 100% is one clustered window (n_eff≈1);
era-9 is 11 days of one quiet-then-storm regime. Nothing here moves a
verdict alone — it prices WHERE the missed value lives: execution selection
(87% pool) > report-mode conviction (one proven-missed window) > inventory
mix (PAXG). Any remedy (fill logic, lane mode, bracket geometry, universe
weighting) is cohort-resetting — docket material for the 09-22 boundary.
