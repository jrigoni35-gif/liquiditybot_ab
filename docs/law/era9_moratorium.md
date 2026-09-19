## Accrual moratorium â€” era-9 (cut #12, FEE-4: the row the account holds, 2026-09-08)

**History in one line each, all citable AS their era, none poolable across a
cut:** era-4 CLOSED (COST_BOUND n=54); cut #8's 40/80 premise SUPERSEDED;
cut #9 (`9-16ec821e`) fees 22/38 â€” read from the operator's app and RIGHT;
cut #10 (`10-a5acfe2d`, 2026-09-06) six verified defects + E1, which
re-booked 20/35 on a LEGACY-ladder premise (era-7, 2 closed trips); cut #11
(`11-6e584923`, 2026-09-07) the COMMIT configuration â€” hedger OFF, majors
only, $60 probes (era-8; its closing count is whatever
`scripts/cohort_eval.py` reports at the cut-#12 restart â€” no count is
written into law on purpose). Records: `docs/HANDOFF.md` ERA sections,
`docs/quant/`.

**Cut #12 â€” FEE-4** (`exec_era` `12-10d4d0c2`) was minted 2026-09-08 under
operator approval, verbatim: *"Re-book now â€¦ Yes do a reset."* The account's
fee tier, read three ways (Kraken-app screenshot: **Tier 5, 30-day spot
volume $69,652.65, AoP $822.24**; the venue's fee page as raw text;
`core/venue_fees.binding_row`, which reproduces the app's next-tier
distances to the cent), is **15/30 bps**. The booked 20/35 was Tier 4 â€”
cut #10's E1 had booked it on the word of a reference table that was
Kraken's legacy ladder (`docs/quant/2026-09-08_fee_ladder_correction.md`,
the-method recurrence #13) â€” and over-stated the round trip by 10 bps. Six
keys moved, the cut-#9/#10 cascade and nothing else: `pretrade` and
`order_manager` maker/taker 20/35 â†’ **15/30**, `profit_taking.est_fee_bps`
35 â†’ **30**, `ml.label_round_trip_cost_pct` 0.55 â†’ **0.45**; derived entry
bar 0.6642 â†’ 0.6381. No other KEY moved â€” universe, hedger OFF, skimmer
OFF, $60 floor, budget, time-stop, give-back, the model and the 0.35 heat
cap ("I'll just wait it out"). **But the barrier geometry moves with the
cost by construction**, as it did at cuts #9 and #10 and was not said then:
`ml/labeling.barrier_geometry` floors Ïƒ at `pt_cost_multÂ·cost/pt_mult`, and
that floor binds at any 5 m Ïƒ below cost/2 (the normal case), so the
label's PT falls **220 â†’ 180 bps** and SL **165 â†’ 135 bps** (Ïƒ_bar 0.10%);
the live bracket calls the same helper on `est_cost_bps`, and the
break-even/trail floor (`2Â·est_fee + buffer`) drops 76 â†’ 66 bps â€” under the
same `label_era` name, which encodes the horizon only. dry_run STAYS true.
**The tier ROLLS** with the operator's real trading (Tier 3 on 08-29,
Tier 5 on 09-08; paper fills count toward nothing): book it from a fresh
reading at the boundary that adopts it, never chase it mid-era, re-read it
at every readout (`scripts/fee_drift_report.py --volume-30d <v> --aop-usd
<a>`) and name the drift. Decision record:
`docs/quant/2026-09-08_cut12_fee_rebook_adjudication.md` (Â§7 erratum);
stage `scripts/cut12_stage.py`; pins `tests/test_cut12_fees.py`.

**Era-9 accrual begins at the cut #12 runner restart**, from zero, on the
same pre-registered machinery (`scripts/cohort_eval.py` â€” untouched). Read
points are REGISTERED as at cut #11: **n=50 = the lean** (sign + CI, act
only if the CI excludes zero); **n=100 = the verdict** (CONTINUE iff net > 0
with CI excluding âˆ’fee; STOP on no-gross-edge or cost-bound â€” and STOP does
NOT revert to the hedged 12-asset book, which is the measured loss
channel). Expected under H0 (coin flip): âˆ’fee/trip â‰ˆ âˆ’$0.2851 at a $60
ticket (the era-MEASURED null the registration adopted 2026-09-15; the
âˆ’$0.27 cut-#12 figure is one generation stale â€” re-derive with
`scripts/era_readout.py`, never recall), â‰ˆ âˆ’$0.8/day at the ~3
entries/day observed on 09-08 (n=50 in ~2â€“3 weeks). The LONG BOOK (`long_book.enabled`, BTC/ETH accumulation with
12% thesis stops) shares the heat cap and the slot count with this book
and holds 2 of 5 slots at the cut; it is in no cut's "untouched" list and
is an operator docket item, not law. Until it reads out:

- **COHORT-RESETTING â€” forbidden without operator adjudication** (any of
  these mints the next boundary and restarts accrual): changes to entry
  decisioning, position sizing, stop/exit geometry (placement, nudges, time
  limits), the fill simulator, fee booking, the order lifecycle, the
  universe, the hedger, the probe ticket, or the heat cap. **The one thing
  not to touch during the run is anything.** Take-profit width (label PT
  180 bps at the cut-#12 cost floor â€” 220 at cut #10, "240" was cut #9's
  world â€” vs the majors' 36 h median oracle move of 132â€“178) is the
  PRE-NAMED next lever, deferred because the label-era name encodes the
  horizon only and a DELIBERATE width change would mix two geometries under
  one era; CONC-1 behind it. Other candidates live on the HANDOFF docket,
  never here.
- **THE PRICE OF A MINT â€” read this before calling one (added 2026-09-16).**
  This file enumerates exhaustively what IS cohort-resetting and, until this
  bullet, never once said what calling one COSTS. Twelve boundaries in 37.9
  days at a median 2.43-day interval is the measured behaviour of a system
  with an UNPRICED action: every other rule here assumes a boundary is rare,
  and nothing made it rare. (As of 2026-09-18 the 12/37.9/2.43 figures and
  the censoring ladder below have NO committed derivation in docs/quant â€”
  the git-pickaxe route was tried and did NOT reproduce them; they stand as
  recall pending an owed measurement. Re-derive before citing them.) A mint
  costs three things, all measured
  2026-09-16 and all AS-OF â€” re-derive with `scripts/discard_ledger.py`,
  `scripts/era_readout.py` and `scripts/cohort_eval.py`, never quote these:
  (1) **the accrual clock goes to zero** â€” 1 of 6 closed eras has ever
  reached the n=50 lean and **ZERO has ever reached the n=100 verdict**, the
  longest era ever run being 16.1 days against the ~26.6 a verdict needs;
  (2) **trips already banked leave the gate** â€” measured 77.9â€“78.2% of every
  trip carrying a stamp, by two independent reconstructions; (3) **trips in
  flight are CENSORED, at a rate that rises as eras shorten** â€” 11.1% lost at
  a 16.1-day era, 57.1% at 2.6 days, 83.3% at 2.2, 100.0% at 1.1. Rate and
  era length are NOT independent: a short era does not merely accrue less, it
  throws away most of what it did accrue.
  **THEREFORE, binding:** a mint must be JUSTIFIED IN WRITING against that
  price, in the same decision record that authorises it, and an era runs a
  **MINIMUM OF 14 DAYS** (the lean needs ~12.7â€“13.5 at the measured rate)
  before a discretionary boundary may be called. Exactly two things break the
  minimum â€” a **SAFETY INVARIANT** (hard invariants 1â€“7 above) and a **WRONG
  VENUE CONSTANT** making the bot trade on a false cost. Nothing else, and
  "we learned something interesting" is not a safety invariant.
  **Why this bullet exists:** four of the last five boundaries were fee
  re-bookings, and three of those were the MEASUREMENT PLANE correcting its
  own earlier misreading of a venue constant â€” not the strategy changing. The
  law did not require those resets; the absence of a price permitted them.
  Note the interaction with the fee rule above: the tier rolled Tier 3 â†’ Tier
  5 in the ten days 2026-08-29 â†’ 2026-09-08, so under the practice this
  bullet replaces, **the fee tier moves faster than a cohort can finish.**
  Deferring a known-wrong fee to the next boundary carries a real, named cost
  (~10 bps per round trip of conservative bias); carry it deliberately rather
  than paying the reset instead.
- **SAFE**: measurement/report tools, dashboards, tests, wiki, telemetry
  export, and bug fixes that do not alter which orders are placed or how
  they fill.
- Do not read the accruing gate numbers as a trend; do not retune on
  them. The registration is the law; the readout names which decision has
  become decidable â€” it never decides.
- Model-side investment is FROZEN per the 2026-08-10 operator
  adjudication (no new families, features, or meta-labeling); the
  retrain loop itself continues by design.
- **WHAT THE LAW DOES NOT NAME (mirrored 2026-09-18, from HANDOFF's
  09-16 firing audit).** The 09-16 audit found ZERO hard-invariant
  breaches and stated the drift precisely: *"the bot is SAFE and is
  not running the experiment the law describes."* Four mechanisms
  shape live outcomes without being named anywhere above â€” the
  **grid entry ladder** (`execution/grid_ladder.py`, GL-* codes), the
  **inventory-derisk overlay**, the **watch lane**, and the **circuit
  breaker**. Every era-12 5m entry is a grid-ladder exploration probe
  admitted at forced p_win=0.85 with the profit gates bypassed;
  realized tickets ran $35.29â€“$114.70 against the registered $60 null;
  LB-031's 12% thesis stop has fired zero times ever. This file governs
  the rails it names; those four are real, load-bearing, and live
  OUTSIDE the text above. Read HANDOFF's ERA-9 WATCH and OPEN DOCKET
  before citing this law as a complete description of the running
  system; the law-vs-reality gap is documented drift, not violation.

