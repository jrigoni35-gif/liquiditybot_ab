# Cut #11 — the COMMIT configuration (era-8) — operator adjudication

**Date:** 2026-09-07
**Class:** COHORT-RESETTING. Mints `exec_era` `11-<sha>`; era-8 accrual
begins from zero at the runner restart. Era-7 (2 closed trips at staging)
stays citable AS era-7.
**Authority:** operator, 2026-09-07, verbatim: *"Okay then let's take the
concept of my perfection of zero and get the bot to try and not get 0"* and
*"No matter whether it's negative or positive. Make it do things that would
make it have to either end with a positive or negative PnL."*
**Stage:** `scripts/cut11_stage.py --apply` (config half); the code commit
carries the stamp. Built on branch `cut11`; goes live only on merge + restart.

---

## 0. In plain language

The bot has read "zero" three measurement periods in a row. Three things in
it are *built* to produce zero and have nothing to do with the model: a
hedge leg that opens against every bet and cancels it, tiny $18 tickets
whose wins and losses are cents, and a basket of small coins that lose on
their own. This cut removes those three and changes nothing else — how it
picks moments, where it takes profit or cuts losses, what it pays in fees,
the model — all untouched. Then it trades the four big coins only, without a
hedge, at $60 a ticket, about four times a day.

**What to expect.** If the bot really can't tell direction (the evidence so
far), it will lose about the fee on every trade — roughly **$1.30 a day**,
*more* than today's ~$0.94, because the tickets are bigger. That is the price
of a real answer. If the four majors are slightly better than a coin flip
(what the last two months faintly suggest), it comes out slightly ahead.
Either way the sign will be visible: a lean after 50 trades (~2 weeks), a
verdict after 100 (~4 weeks).

## 1. What the design pass recommended, and why it was overridden

A five-lead, three-judge design pass (`wf_83900ef6-2d2`) recommended **trade
only the four majors AND cut the trade budget from 5 to 2 per day**, because
with a coin-flip model the only lever that makes *expected* net positive is
paying fees less often (H0: −$0.94/day → −$0.22–0.41/day; H1: +$0.05–0.08/day).
Its arithmetic is right. Its objective is not the operator's: it makes the
bot *smaller and more zero-shaped* (best case five cents a day, hedger on,
scratches on). The operator's instruction is decisiveness — accept negative,
force a sign. The universe cut is kept (it is evidence-backed and cheap);
the budget cut is rejected (it delays the verdict); decisiveness is added.

## 2. The change — config half (`cut11_stage.py`, FROM-checked)

```
exchanges.kraken.trading_pairs  [PAXG,ETH,BTC,SUI,ARB,MINA,FLOW] -> [PAXG,ETH,BTC,LINK]
skimmer.enabled                 true  -> false   (else the universe re-widens at every boot)
hedging.enabled                 true  -> false   (a hedged bet cannot end clearly +/-)
position_sizer.min_ticket_usd   15    -> 60      (x4 on the probe floor)
```

Code half: `core/fill_ledger.py` `EXEC_ERA` `10-a5acfe2d` → `11-<sha>`.

**Why these four, each with its number.**

| | measured | source |
|---|---|---|
| alts are the loss channel | −$3.67 on 27 trips; 15/22 era-9/10 alt exits are `tb_sl` vs 1/5 majors; majors +$4.56 on 18 | 2026-08-26 dive; design pass `class_split.py` |
| hedges cancel the bet and cost 40% of all fees | 159 of 1,245 fills; $157.84 of $392.66; 40.0 bps/fill (taker) | E1, `fills.csv` 2026-09-06T21:20Z |
| probes sit on the floor | median ticket $18 = `max(min_ticket 15, min_order × 1.2)`; `size_scale` clamped to [0.01, 1.0] and already 1.0 | `position_sizer.py:595`, `main.py:1066` |
| no hedge is open at staging | `is_hedge` False on all 5 open positions | `state.json` 2026-09-07 |

**Why NOT the other decisiveness levers.**
- *Take-profit width* (240 bps sits above the majors' 36 h median oracle move
  of 132–178): the label-era name encodes the horizon only (`label_era_of`),
  so changing barrier width would silently mix two geometries under one era
  in the training corpus. Deferred with that reason; it is also ALGO-5-
  adjacent. If the sign is still unreadable at n=100, this is next.
- *Turning off the time-stop / give-back*: a 40 h time-out closes at market —
  a real ± outcome, not a scratch; the give-back arm is cost-floored (1.27%).
  Neither manufactures zero.
- *Cutting the trade budget*: delays the verdict; rejected (§1).

## 3. Pre-registration (written before era-8 data exists)

**Hypothesis.** H1: with hedges off and majors only, per-trip net at $60
tickets is > 0. H0: per-trip net = −fee (≈ −$0.33 at 55 bps × $60).

**Population.** Entry-opened closed round trips with every leg stamped
`11-…` (`cohort_eval` stamp-purity), hedge legs excluded (there will be
none), straddling trips excluded.

**Primary metric.** Net $/trip at booked fees (Σsell − Σbuy − Σfees), 95%
day-block bootstrap CI (UTC day of closing fill, 4,000 reps, seed 7).
Co-primary: gross %/trip, same CI — separates "no edge" from "edge eaten
by fees".

**Read points and rule.**
- **n = 50 (~2 weeks at ~4/day): the LEAN.** Report sign and CI. No action
  either way unless the CI excludes zero — in which case act on it.
- **n = 100 (~4 weeks): the VERDICT.** CONTINUE iff net mean > 0 with the
  CI excluding −fee. STOP iff gross mean ≤ 0 and median ≤ 0 (no edge), or
  gross > 0 and net ≤ 0 (cost-bound). STOP does not revert to the 12-asset
  hedged book — that is the measured loss channel; it goes to the operator
  as "this strategy class, at this size, on this venue, does not pay."
- **Power** [I]: per-trip sd at $18 tickets was $0.46 (era-9); at $60,
  ≈ $1.5. SE at n=50 ≈ $0.21, at n=100 ≈ $0.15. Under H0 (−$0.33): z ≈ −1.6
  at 50, −2.2 at 100. Under a modest H1 (+$0.16, the era-7 probe gross of
  +81 bps less fees): z ≈ 0.8 at 50, 1.1 at 100 — a positive result this
  small will *not* clear the CI by n=100 and would read UNDETERMINED → extend
  to 200. Say so now: the test is powered to catch losing, not to certify
  small winning.

**The one thing not to touch during the run:** anything. No retune, no
feature, no geometry, no budget change, no re-enabling the hedger "just
for this position." Every one of those restarts the count.

## 4. What this cannot see

- Ticket size interacts with the risk stack: at $60 × several open positions
  the heat cap (RP-051) or CVaR cap may veto entries the $18 book took.
  Fewer fills than ~4/day would lengthen the read; watch `RP-05x` reasons in
  the first days.
- Disabling the hedger removes the delta cap it enforced
  (`max_net_delta_pct_of_equity 20`). Net exposure can now reach the sizer's
  own caps (25% per position, heat cap). In paper this is the point; before
  any live consideration it is a risk-control decision of its own.
- LINK joins the core universe on offline pair meta; its live book depth is
  not re-verified here.
- The alt-vs-major split is a post-hoc reading of two short eras (z ≈ 1.6
  pooled). It is a hypothesis generator; era-8 is the test.

## 5. Provenance ledger

| claim | source | tag |
|---|---|---|
| hedge legs 159 / $157.84 / 40 bps | `fills.csv` E1 pass, 2026-09-06T21:20Z | [K] |
| median ticket $18; floor formula | `position_sizer.py:595`, `config.json` | [K] |
| `size_scale` clamp [0.01, 1.0] | `main.py:1066` | [K] |
| alts −$3.67/27, majors +$4.56/18 | `docs/quant/2026-08-26_why_losing_deep_dive.md` | [K] |
| 15/22 alt exits `tb_sl` | design-pass selection lead, `fills.csv` 2026-09-07 | [K] |
| no open hedge | `state.json`, 2026-09-07 | [K] |
| hedger disabled → no actions incl. unwinds | `execution/hedging.py:171` | [K] |
| skimmer re-widens at boot | `runner.py:105-121` | [K] |
| design-pass recommendation and arithmetic | `wf_83900ef6-2d2` synthesis | [K] |
| expected net under H0/H1 | §3, arithmetic shown | [I] |
