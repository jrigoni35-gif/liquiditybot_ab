# Institutional diagnosis — the bot from a mile away (2026-09-19)

**Purpose:** framing memo for the 2026-09-22 era-9 readout. Not a
decision document; nothing here moves a number the registration reads.
It exists so the STOP/CONTINUE ruling sits next to the structural
context instead of in a chat thread. Every quantitative claim below was
verified today against `scripts/era_readout.py --json` (AS-OF
2026-09-19T18:48Z) or cites the record named; re-derive before citing.

**One-sentence verdict.** A market-making-shaped strategy paying retail
taker-shaped economics, wrapped in exchange-grade governance around an
$800 research account, currently measuring a control arm its own model
doesn't drive.

## 1. The economics are the strategy's ceiling — and they're venue-set

At a $60 ticket the booked tier costs ~45.5 bps round trip (era-measured,
adjudicated 09-15) plus the measured ~15.1 bps arrival→fill adverse
component (edge-hunter, 09-01: mechanical limit distance, clean placebos).
~60 bps of friction against a **median gross of ~3 bps** ($0.02 on $60;
readout JSON: `net_median 0.0221`). Institutional rule of thumb: no desk
trades where friction exceeds expected gross by an order of magnitude.
The majors' 36h median oracle move is 132–178 bps, so the gross available
at this horizon on these pairs does not clear the cost stack at this
ticket size. Market-making firms at this shape are **paid rebates**
(0 to −2 bps) for posting limit liquidity; the bot pays 15/30. On
Kraken's tier schedule, this account is fee revenue, not fee-optimized
flow. **The venue's fee table, not the signal, sets the break-even bar —
and the bar is above the strategy's head.**

## 2. An experiment no institution would run serially in live

A prop research team asking "does this lane have edge?" runs it in
simulation at high parallelism, then promotes a winner to a small live
validation book. This program runs **one configuration at a time, live,
on the era clock**, where each abandoned era costs 1–3 calendar weeks
plus censoring. Twelve boundaries in 37.9 days (median 2.43 d, measured
2026-09-19 from fills stamps) is the classic **strategy-hopping failure
mode** — no configuration reaches statistical maturity, so the program
learns about its own process noise. The moratorium's 14-day minimum and
the n=50/n=100 registration are the correct institutional fix, adopted —
at boundary #12, after 11 immature eras. The serial-live design makes
the **process itself the most expensive instrument in the building**;
the scarce resource was never the $800, it is calendar days, and the fee
schedule consumes them through forced short eras.

## 3. Research P&L and live P&L are different strategies

47.4% of era-12 live closes are filed `barrier='realized'` /
`label_era='exit_sim'` and dropped by the training filter (era_readout,
09-16). The give-back trail can never bank a labelled-PT win (arithmetic,
not statistics: 10.6:1 trail/bracket asymmetry, RECENTLY SETTLED 09-16).
The model's calibrated probability cannot reach the forced 0.85 admit
at the shipped shrinkage, so no retrain changes which trades are taken.
An institutional model-validation team calls this **backtest/live
mismatch and stops the deployment** — it does not record it as a result.
Whatever era-9 concludes, it concludes about the probe lane, not the
model; the model is being *evaluated* on trips it never took through
exits it never fires.

## 4. Governance is real — and mis-scaled, which the law already measured

Hash-chained audit, era registrations, priced mints, adversarial panels,
fence tests: regulator-grade control infrastructure of the kind an
institution wraps around a $100M book. Around an $800 account whose
plausible monthly P&L is smaller than the operating cost of one
law-audit session, the control plane costs more than the book it
governs. The 09-16 "price of a mint" amendment is the correct instinct —
unpriced actions get consumed — and it made the pattern measurable:
governance overhead was consuming the serial calendar, not capital.
That trade is now explicit, which is itself the institutional behavior.

## 5. What an institution would do with this book

1. **Fix economics before signal.** Qualify for a maker-rebate tier, or
   accept that this venue/fee table cannot host a 5m strategy at $60
   tickets; the 12% thesis-stop long book amortizes the same fees far
   better than the 5m book ever can.
2. **Move era testing to simulation at scale**; reserve live eras for
   validation. `dry_run` already exercises the identical engine on
   recorded feeds — the era machinery works unchanged.
3. **Unify label and traded exit** (persist peak unrealized, close the
   47.4% filing gap) so the model learns what the account experiences.
4. **One change per era, eras to completion** — the rule now in force;
   the 11 immature eras are the cost of learning it late.

## The irony, stated plainly

The weakest part of this project is the trading, and the trading was
never the point. The process being this good is precisely why the
answer — STOP, on current evidence (flip needs +$2.92/trip on the last
ten, a ~3.9σ event, HANDOFF 09-22 pre-staging) — will be believable when
it lands. Most $800 bots fail silently. This one fails with a signed
decision record, a priced mint, and a docket for what happens next.
That is an asset no fee tier sells.
