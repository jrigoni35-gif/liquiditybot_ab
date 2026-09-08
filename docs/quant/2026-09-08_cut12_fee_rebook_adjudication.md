# Cut #12 — FEE-4: book the fee row the account actually holds (era-9) — 2026-09-08

**Class:** COHORT-RESETTING (fee booking). **Operator approval, verbatim
(2026-09-08):** *"Re-book now: era-8 has 2 entries and 0 closed trips — a
boundary today resets about one day of accrual, nearly free, and era-8 then
runs at the fees you actually pay. Yes do a reset."* `dry_run` STAYS true.
**Stage:** `scripts/cut12_stage.py` (FROM-checked, guard-swept, refuses
unless `core.venue_fees.binding_row` at the reading equals the staged row).
**Pins:** `tests/test_cut12_fees.py`. This record is committed ALONE and
FIRST; its sha is the era stamp `EXEC_ERA = "12-<sha>"`.

## 1. The fact — three routes

| route | read | says |
|---|---|---|
| operator's Kraken app, screenshot | 2026-09-08 17:51 device time | **Tier 5**; 30-day spot volume **$69,652.65**; AoP **$822.24**; "30,348.35 more volume or 199,178.76 more AoP to the next tier" |
| venue fee page, raw text (no summarizer) | 2026-09-08T20:15:29Z | Tier 5 = **0.15% / 0.30%** at $50K+ volume or $100k AoP; Tier 6 at $100K+ / $200k |
| `core.venue_fees` (the corrected table) | 2026-09-08T22:52Z | `binding_row(69652.65, aop_usd=822.24)` → **(15, 30)**; next-tier distances reproduce the app's figures to the cent |

Vault: `raw/quant/2026-09-08_kraken_fee_tier_reading.md` + screenshot.

## 2. What was booked, and why it was wrong

Cut #10's E1 (2026-09-06) booked **20/35** on the word of a reference table
that turned out to be Kraken's LEGACY ladder (`docs/quant/2026-09-08_fee_ladder_correction.md`,
the-method recurrence #13). On the 08-29 reading (Tier 3, $17,482) that
under-stated cost by 5 bps; on today's reading (Tier 5) it **over-states the
round trip by 10 bps (55 vs 45; 22.2%)** — $0.06 on every $60 round trip
the sim charges itself that the venue would not.

## 3. The cut — six keys, the cut-#9/#10 cascade, nothing else

| key | from | to | why |
|---|---|---|---|
| `pretrade.maker_fee_bps` | 20.0 | **15.0** | pricing (pre-trade EV gate) |
| `pretrade.taker_fee_bps` | 35.0 | **30.0** | pricing |
| `order_manager.maker_fee_bps` | 20.0 | **15.0** | booking (fills ledger) |
| `order_manager.taker_fee_bps` | 35.0 | **30.0** | booking |
| `profit_taking.est_fee_bps` | 35 | **30** | break-even floor for the profit tiers (taker) |
| `ml.label_round_trip_cost_pct` | 0.55 | **0.45** | = (15 + 30) / 100; the label's cost term |

Derived entry bar (`position_sizer.p_bar_mode = derived`): printed by the
stage at apply time, falls with the cost — recorded in the code commit.
`allow_sub_floor_fees` stays true (15/30 sits below the Tier-1 40/80
tripwire; it is a published discount row — Tier 5 — which is what the flag
exists for). The not-a-row WARN does not fire: 15/30 is a row.

**UNTOUCHED, on purpose:** universe (PAXG/ETH/BTC/LINK), hedger OFF, skimmer
OFF, `min_ticket_usd` 60, stop/TP geometry (240 bps TP is still the
pre-named next lever — deferred for the same reason as before: a width
change would mix two geometries under one label era), exploration budget,
time-stop, give-back, the model (frozen), the heat cap 0.35 (operator:
"I'll just wait it out"). The signal-quality study running in parallel is
measurement; anything it proposes is a later boundary with its own record.

## 4. Era accounting

- **Era-8 CLOSES** at the cut #12 runner restart with 2 entries and 0 closed
  trips (`11-6e584923`) — citable as era-8, unpoolable, and too small to say
  anything.
- **Era-9 accrues from zero** on the same pre-registered machinery
  (`scripts/cohort_eval.py`, untouched): **n=50 lean, n=100 verdict** as
  registered at cut #11; STOP never reverts to the hedged 12-asset book.
- Under H0 (coin flip) the expected net is −fee/trip ≈ −$0.27 at a $60
  ticket (45 bps), ~−$1.1/day at the heat-capped rate — smaller in dollars
  than era-8's −$0.33/trip.
- Open positions (5 at staging: ETH ×2, BTC ×2, PAXG short) carry across;
  their exits book at 15/30 (straddlers, as at cut #10).

## 5. The rule this cut adds

**The tier rolls.** It is the best of the operator's real 30-day spot volume
and assets on platform; the bot's paper fills count toward neither. Tier 3
on 08-29, Tier 5 on 09-08. Book from a fresh reading at the boundary that
adopts it — this one — never chase it mid-era; **re-read it at every cohort
readout** (`scripts/fee_drift_report.py --volume-30d <v> --aop-usd <a>`) and
name the drift on the readout. If the tier falls below 5 during era-9 the
readout is optimistic by the difference; if it rises, conservative.

## 6. Go-live (era-cut procedure, as cuts #10/#11)

Record commit (this file, alone) → `EXEC_ERA = "12-<sha>"` + pins + CLAUDE.md
moratorium block + HANDOFF ERA-9 header in the code commit on branch `cut12`
→ full DoD → `--ff-only` merge to main → push → **runner restart via
`ControlChannel("outputs/control").send("stop")` + supervisor relaunch**
(a push restarts nothing on this box) → verify from the NEW pid's boot line
`fees=15/30bps`, never from status.json alone.
