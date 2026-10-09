---
title: The Money-Path Thesis
category: synthesis
status: SETTLED
summary: "Corrected 2026-08-02: cost is necessary but not sufficient — the binding defect is payoff asymmetry (0.561 vs 0.750 needed, n=217); bounded same day: no timing signal (random-entry control) and no surviving bracket (geometry search) — exit design minimizes bleed, cannot create edge. Panel-adjudicated 2026-08-07: the book's entire drawdown is fees (−384.67 vs fees_total 382.28, ~flat on price), the fee constant itself is falsified (25/40 matches no Kraken row; correction sequenced post-h432), and every dollar is sim-side of the paper/real boundary. DECOMPOSED AT LAST 2026-08-09: '~flat on price' is now an exact number — gross P&L before ANY fees is −11.66 over ~250 closed positions (~−$0.05/trade ≈ 0) against 382.59 of fees, so fees are 32.8x the absolute gross edge and 100% of the −394.25 all-in loss is costs; three unrelated instruments corroborate gross edge ≤ 0, and the sim's one-way optimism makes real gross WORSE. CONFIRMED THE SAME DAY BY A SECOND INDEPENDENT METHOD — a full-book fills reconstruction puts gross at −13.01 over 394 round trips, agreeing with the state identity to within 1.35 — and the thesis's dedicated instrument turned out to be answering its central question BACKWARDS: scripts/breakeven_test.py discards all 159 hedge round trips, flipping the median gross from −0.0303% to +0.0505% and with it the branch it prints. AS OF 2026-08-10 EVENING the thesis has its VERDICT INSTRUMENT: model-side investment is FROZEN and the pre-registered era-4 gate (NO_GROSS_EDGE / COST_BOUND / CONTINUE at n>=50, population cut max(B4_TS, CAPITAL_EPOCH_TS) = 2026-08-10T23:05:27Z) is the freeze's ONLY unfreeze trigger — accruing 0/50 under the $800 stressor, where the unscaled $15 ticket floor is 1.9% of equity and the truth arrives faster and louder. 2026-08-11: the Grand Synthesis standing directive routes THROUGH this thesis — its geometry work waits on the operator's cut-#7 adjudication, its algorithms are tested against the two nulls rather than assumed past them, and its one genuinely new input is the uncensored trade-path ledger (winners' heat profile, previously nonexistent on disk) — DELIVERED 2026-08-10 late: ledger shipped decontaminated (2602371b, owed 65 closed), both sweeps filed, battery 15 ALL GREEN BATCH_EXIT=0 verified directly, and the algorithm package is on file (grand-synthesis-algorithm-package) with Tier 2's geometry epoch still awaiting the operator's cut-#7 timing adjudication — the gate remains sole arbiter. ADJUDICATED SAME NIGHT: cut #7 MINTED at 2026-08-11T01:33:50Z (e7d5ca1a, the CDO-review split) — the book's ONE authorized geometry change since the 48-combo null is the Osler widen-beyond flip (direction-only) plus ALGO-6's pins; the reset was FREE (zero closes since the capital epoch, gate populations identical by construction, still 0/50); the widths and decay ladder wait on the ALGO-5 amendment (owed 67) at ~30 uncensored paths — the two nulls stand unmoved and the gate remains sole arbiter, unchanged in code. 2026-08-12: the stressor's first 25 hours produced ZERO entries from 118 candidates for a reason unrelated to edge (the un-re-anchored W33 loss-budget anchor read the $800 reset as an 82.7% loss; RP-041 vetoed all new risk until the budget_reanchor_week repair) — accrual 0/50 UNCHANGED, the cost was calendar; and SZ-023's honest breakeven refusals (p_win 0.34-0.40 vs the 0.69 bar, 21 of the 118) survive the repair — the thesis printed per-candidate. ⚠️ FOUR RETRACTIONS 2026-08-16, all of which pointed the SAME (pessimistic) way and none of which change the operative conclusion: (i) the '10 bps/side -> 65 bars' fee lever DOES NOT EXIST — no Kraken tier is 10 bps at any volume, an $800 book is Tier 1 40/80, so config's 25/40 UNDERSTATES fees and the correction runs the WRONG way (cost/sigma 0.82 -> 1.31 maker/maker, 2.11 at the observed 60.6% taker share); (ii) the 32.8x fee/edge multiple is STALE (98.6% of its 415 trips predate the current simulator; on the 14 that ran on it gross is POSITIVE +$0.82) and STATISTICALLY VOID (gross -11.89 +/- 19.4, z = -1.20, ratio CI [12.2x, +inf)) — do not quote it, and 368x inherits the same denominator problem; (iii) the 'three unrelated/INDEPENDENT instruments' shared ONE data path — 415af0f9 fixed the same one-line defect in breakeven_test.py, geometry_search.py and random_entry_control.py in a single commit four days AFTER the date they are cited under, and in breakeven_test it INVERTED the printed verdict; all three must be re-run before citation; (iv) the realized target-hit rate re-reads 0.291 not 0.225, and its implicit 0.000% null is the WRONG null for a censored sample. CORRECTED HEADLINE: gross edge is INDISTINGUISHABLE FROM ZERO IN BOTH DIRECTIONS — which is NOT 'there is no edge'. The verdict instrument still cannot resolve its own question at the pre-registered n. 2026-08-26 — THE INSTRUMENT FIRED: era-4 gate crossed n=50 (54 closes) and read COST_BOUND — gross positive on the clean cohort (+0.5172%/trip mean booked), net ≤ 0 at the honest ×1.979 fee constant (+$1.36 booked → −$5.36 true); decomposed and same-day validated as TUITION, NOT ALPHA DECAY (probe lane 49/54 nets −1.052%/trip at true fees p≈0.027 deflated; conviction n=5 clears the full stack, directional only; alt-tail split POST-HOC; ticket-size fee-floor claim REFUTED — fees are proportional, 65.2 vs 64.8 bps). The two nulls stand; the readout names the decision, the operator owns it (boundary #5 staged inert, ALGO-5, CONC-1). See sources/session-20260826-why-losing-deep-dive. [UPD 2026-08-30 RIDER, not a retraction: FEE-3 came back and FALSIFIED the fee anchor in the OTHER direction - the account is real Kraken Tier 3 = 22/38 bps, not the Tier-1 40/80 cut #8 booked as conservative. Cut #9 executed 2026-08-30T15:32:36Z (exec_era 9-16ec821e, commit 59bdcf87, ARM scoped fee correction only, dry_run untouched). The COST_BOUND readout STANDS as an era-4 reading and re-read COST_BOUND at both 120 and 60bps; what changed is MAGNITUDE not sign class (shortfall ~-79 -> ~-19 bps/trip; honest sign UNDETERMINED-leaning-NEGATIVE, CI spans zero, n_eff 25.83). What MOVED is the named lever: median trip +72.6bps CLEARS the real ~60bps rake, so the shortfall is the fat tail of losers = an ALGO-5 tail-control problem, the opposite lever from the fee fix and one cut #9 EXPLICITLY EXCLUDED. Era-6 accrual starts at ZERO from 15:32:36Z; no dollar figure on this page may be pooled with an era-6 row. See synthesis/comparability-boundaries row 9.]"
tags: [thesis, economics, cost, money-path, payoff-asymmetry, paper-mode, gross-vs-net, retracted-claims]
sources: 22
updated: 2026-08-30
---

# The Money-Path Thesis

> [!success] **2026-08-26 — THE VERDICT INSTRUMENT FIRED: COST_BOUND at n=54.**
> The pre-registered era-4 gate crossed n=50 and named its arm — gross > 0,
> net ≤ 0 at the honest fee constant. The 2026-08-16 corrected headline
> (*"gross edge indistinguishable from zero in both directions"*) **moves on
> the era-4 cohort**: gross is measured positive there (mean +0.5172%/trip
> booked, gross win rate 63.0%, re-derived 2026-08-26T23:55:14Z), and the
> failure is the cost stack — +$1.36 net booked flips to **−$5.36 at the true
> ×1.979 fee anchor**. The mechanism is now decomposed and same-day
> statistically validated ([[sources/session-20260826-why-losing-deep-dive]]):
> **tuition, not alpha decay** — 91% of the cohort is probe trades whose gross
> (+0.283%/trip) sits structurally below the round trip they pay (probe net at
> true fees −1.052%, p≈0.027 after ×1.58 concurrency deflation), while the 5
> conviction trades clear the full true stack (+1.463%/trip, **directional
> only at n=5**). The two nulls stand unmoved; the readout **names which
> decision is decidable, it never decides** — boundary #5 (fee truth, staged
> inert), ALGO-5 geometry, CONC-1 and asset discipline all await the
> operator's cohort-resetting adjudication. Everything sim-side; fee truth
> conditional on FEE-3 (venue tier row never verified).

> [!warning] **[UPD 2026-08-30 — RIDER, NOT A DELETION: FEE-3 CAME BACK AND
> THE FEE ANCHOR ABOVE WAS ~2x TOO HIGH IN THE OTHER DIRECTION.]**
> The callout above ends *"fee truth conditional on FEE-3 (venue tier row
> never verified)."* **FEE-3 has now been verified, and it falsified the
> anchor.** The operator's Kraken app (2026-08-29) proves the account is
> real **Tier 3 = 22/38 bps** on $17,482 30-day spot volume — not the
> Tier-1 40/80 that cut #8 booked as "conservative" on a zero-volume
> assumption. **Cut #9, the Tier-3 fee correction, executed
> 2026-08-30T15:32:36Z** (`exec_era` `9-16ec821e`, commit `59bdcf87`,
> operator ARM scoped "fee correction only", `dry_run` untouched):
> [[comparability-boundaries]] **row 9**.
>
> **What this rider does NOT do — read this before quoting either reading.**
> It does **not** retract the COST_BOUND readout above. That readout was
> taken on the **era-4** cohort under its own pre-registered fee anchor and
> stays citable AS era-4; it read COST_BOUND at **both** 120 and 60 bps
> round-trip when re-run ([[sources/session-20260829-fee-tier-and-stream-audit]]
> §2). What the correction changed is the **MAGNITUDE, not the sign class**:
> the shortfall moves from ≈−79bps/trip to ≈**−19bps/trip**, and the honest
> sign becomes **UNDETERMINED-leaning-NEGATIVE** (CI spans zero, n_eff
> 25.83, P(net≤0)≈0.73) rather than confidently negative.
>
> **What it DOES do: it moves the thesis's named lever.** Median trip
> **+72.6bps clears the real ~60bps rake**; the shortfall is the **fat tail
> of losers**. That is an **ALGO-5 tail-control** problem — the *opposite*
> lever from the fee fix, and one cut #9 **explicitly EXCLUDED** (its net-CI
> spans zero on fills alone; it needs the candle re-sim). Correcting fees
> bought an **honest** readout, not a winning strategy.
>
> **And a boundary, binding:** era-6 accrual starts at **ZERO** from
> 15:32:36Z. Every dollar figure on this page — era-4's and era-5's alike —
> is on the far side of the fee correction and **may not be pooled with an
> era-6 row.** Era-5 (cut #8) never reached its n=50 readout at all.

> ⚠️ **CORRECTED 2026-08-02** ([[sources/session-20260802-digest]]). The claim below was the
> thesis as measured on 08-01. Clean per-fill measurement — n=215 post-purge of 64 fabricated
> fills, re-confirmed at **n=217** after the residual quarantine of 18 more fixture positions
> (72 rows, commit `483f6727`, `fills.csv` 637/637 audit-crossref CLEAN) — shows: **cutting fees
> to zero still leaves mean gross −0.0501%.** Cost is the larger term (0.667% measured fees vs a
> ~0.05% gross gap) and cost levers remain necessary — but **not sufficient**. The binding defect
> is [[concepts/payoff-asymmetry]]: win rate 57.1% (fine), payoff ratio 0.561 against 0.750
> needed; the average loser is ~1.8x the average winner. Break-even win rate at fixed sizes is
> **impossible (p > 1) at every real fee schedule** — so the lever is **exit geometry**, not the
> model, not the hit rate, and not fees alone. The 08-01 measurement was also fed by the
> contaminated `fills.csv` ([[concepts/default-path-fallback-writes]]).

> ⚠️ **Bounded again 2026-08-02 (late session)** — two decisive tests ran the same day
> ([[sources/session-20260802-digest]] second addendum). The **random-entry MFE control**:
> **no timing signal** — real entries' mean MFE percentile 0.516 [0.439, 0.594] against 200
> seeded matched controls each (n=51, commit `8062f46a`); the 87%-positive-MFE figure was
> diffusion. The **pre-registered 48-combo geometry search**: **no bracket survives**
> (Bonferroni z = 3.26, 222 real entries, config fees; commit `663434ae`, battery green; best
> combo h=432 tp=1% sl=2%: mean −0.400%, lower bound −1.124%). **Exit geometry can minimize bleed; it cannot create edge.**
> What remains standing as levers: the cost stack (maker-only, asymmetric banding) and pooling —
> with no demonstrated entry signal yet to amplify.

## The claim (2026-08-01, superseded in part)
> **"We pay 82% of one standard deviation in fees per round trip. No signal survives that. Every
> downstream symptom — the degenerate labels, the low win rate, the negative edge, the model losing to a
> base-rate null — is this ratio expressed in a different unit."**

## The chain of symptoms it unifies
| Symptom | Where recorded | Reduces to |
|---|---|---|
| Win rate ~10%, profit factor 0.044 | [[sources/goals-mindset-review]] | cost/sigma |
| 77% of closes attributed to "plain underperformance" | same | cost/sigma |
| Champion Brier ~ coin-flip | same | cost/sigma |
| Labels 87.8% time-outs | [[sources/cost-to-volatility-horizon-mismatch]] | cost/sigma |
| Stop hit **1.9x more often** than target | [[sources/live-label-era-deadlock]] | cost/sigma |
| **Every model rung loses to a constant** | same | cost/sigma |
| Barriers at 3.39 horizon-sigma vs a ~0.8 norm | 08-01 | cost/sigma |

> ⚠️ 08-02 caveat on this table: the win-rate and profit-factor rows were computed from fills
> grouped by `position_id` while one position appeared under 16 ids (the 27x error). Clean
> per-fill numbers: win rate **57.1%**, mean gross **−0.0501%** (post-quarantine n=217). The
> label-geometry rows (time-out mix, barrier width) are corpus measurements and stand.

## Why it went unseen for so long
1. **The battery does not measure it.** [[concepts/overfit-battery|OF-1..OF-8]] measures memorization,
   selection luck, leakage and degrees of freedom — all *relative* quantities. A battery can be
   5-of-8 green while every candidate is worse than a base-rate constant. Hence
   [[concepts/null-model-floor]].
2. **The plumbing was genuinely broken too.** A real six-link defect chain
   ([[synthesis/learning-pipeline-arc]]) absorbed weeks of attention and had to be fixed before the
   economic question was even visible.
3. **Sigma was never expressed in horizon units.** Barrier width only becomes comparable across studies
   once divided by `sigma_bar * sqrt(H)`. That single normalization is what made the finding legible.

## The three options — option 1 was taken, then demoted
1. **Lengthen the horizon to ~400 bars (~34h)** — cost/sigma falls to 0.20, but this **makes it a swing
   strategy**; label rate falls and corpus growth slows.
2. **Cut the cost stack** — maker-only entries and exits, fee-tier work, tighter spread gating, so
   barriers can come in to ~0.6%. Preserves the intraday character; hardest to execute.
3. **Select for volatility** — trade only names and regimes where sigma is high enough. At the 90th
   percentile of observed sigma, cost/sigma improves to 0.46 — "better, still not good."

"(2)+(3) together are roughly equivalent to (1)."

**What happened:** option 1 shipped 2026-08-01 as the **432-bar (36h) migration** (commit
`7566ea88`), a pre-registered experiment holding to **n=50 closed trades** (6/50 as of 08-02).
Research then ranked horizon extension the **weakest** of the mitigation levers (Novy-Marx &
Velikov 2016: reducing rebalance frequency ranks last, zero weight in their efficient portfolios;
Qian et al. 2007: zero gross benefit — the entire gain is the cost saving). It runs to n=50 anyway
because thrashing costs more than waiting. The levers now ranked above it: **maker-only execution**
(round trip 0.52% → 0.32%), **asymmetric entry banding** (41% turnover cut, 42% cost cut, gross
preserved), **pooling across ~50 symbols** (the only genuine ESS raiser). Details and citations in
[[sources/session-20260802-digest]].

## The explicit non-claims
- The triple-barrier method is **not** wrong; the **parameterization is outside the informative range**.
- Do **not** just widen the horizon and move on: "2 hours -> 1.5 days changes what strategy this is — an
  operator product decision, not a tuning knob."
- The 07-31 horizon change is **not to blame**. At the previous setting the ratio was 1.69 — better,
  still 2x the literature, and it carried the clock-inversion deadlock. **Neither setting was in range.**

## The strongest single lever

> [!error] **RETRACTED 2026-08-16 — THE 10 BPS TIER DOES NOT EXIST, AND THE CORRECTION RUNS THE WRONG WAY**
> The "10 bps/side → 65 bars" lever below rests on a **Kraken volume tier that does not exist at
> any volume**. The parenthetical *"(a Kraken volume tier)"* entered the corpus **uncited** in
> `docs/quant/2026-08-01_cost_to_volatility_horizon_mismatch.md` and was reused for five days.
> **The vault has held the true schedule since 2026-08-07**, triple-confirmed by three independent
> fetches ([[sources/session-20260807-institutional-review]] §C, carried correctly by
> [[concepts/cost-truth]] throughout):
> **Tier 1 ($0+) 40/80 · Tier 2 30/60 · Tier 3 22/38 · Tier 5 (~15/30) is the DEEPEST row.**
>
> **An $800 book is Tier 1**, so `config.json`'s 25/40 **UNDERSTATES** real fees and every
> cost/sigma figure on this page derived from it is **optimistic**:
>
> | premise | round trip | cost/sigma | breakeven hit rate |
> |---|---:|---:|---:|
> | 25 bps maker/maker (as configured) | 0.50% | 0.82 | 0.567 |
> | **Tier 1 maker/maker (40 bps)** | **0.80%** | **1.31** | **0.650** |
> | **Tier 1 @ observed 60.6% taker** | **1.285%** | **2.11** | **0.784** |
> | zero fees | 0.00% | 0.00 | 0.4286 |
>
> **The "cut fees to reach a 5.4-hour hold" lever does not exist.** The thesis is *stronger*, not
> weaker, for the correction. Filed [[concepts/no-orphan-claims]]: *an unsourced parenthetical is
> the cheapest way to manufacture vault knowledge* — six words, no citation, survived filing,
> indexing and five days of reuse.

~~**Fees.** At 10 bps/side instead of 25, the target cost/sigma needs a horizon of only 65 bars instead of
405. **Halving the fee buys the same improvement as a 6x longer horizon**~~ — and unlike the horizon, it
does not change what the product is.

*08-02 amendment:* still true as a cost statement, but no longer sufficient as a profit statement —
at zero fees the book still loses 0.0501% mean gross (post-quarantine n=217). Fees plus exit
geometry, not fees alone.

## Status
Was **"MEASURED, nothing shipped"** pending an operator debate. As of 08-02 (late): the horizon
experiment is in flight (**11/50**, post-432 window 0% wins Wilson [0, 25.9%] — unreadable, hold
— see [[comparisons/horizon-96-vs-24-bars]]), the binding-term diagnosis lives at
[[concepts/payoff-asymmetry]], and **both decisive tests are now run**: break-even transaction
cost (done — Thread 2 of the digest) and the **random-entry MFE control (done — NULL, no timing
signal)**. The pre-registered geometry search found **no surviving bracket**. The forward levers
are the cost stack and pooling ([[synthesis/owed-measurements]]).

*08-02 follow-on — the fill side of paper truth is now honest too:* `passive_base_prob`
0.45 → **0.048** (commit `8e5455e8`, the XV-021 measured trade-through rate) — pre-boundary
paper P&L was optimistic on the **fill** side as well as measured on a once-dirty ledger; the
paper entry rate will drop to the honest rate. ~~The **fee** side stays deliberately
pessimistic: constants held at 25/40 bps vs Kraken's published 16/26, because overstating cost
is the safe direction.~~ **Superseded 08-07: 25/40 matches NO row of Kraken's current schedule
(Tier 1 is 40/80) — for a fresh $5k account the constants UNDERSTATE cost ~1.6–2x, the
dangerous direction; the correction is sequenced behind the h432 verdict because the constant
is load-bearing in the label definition** ([[concepts/cost-truth]],
[[sources/session-20260807-institutional-review]] §C).

*08-05 late-evening addendum — a cash drain that was never in the thesis at all.* The profit-pool
skim ran **once per exit LEG** on a `net` that was **gross minus that leg's exit fee, not minus the
slice's pro-rata entry fees** — so it skimmed an **overstated base** *and* fired on **winning legs
of trades that ended up losing**: a **+$16 tier take on a trade netting −$80 still moved ~$4.80
into locked savings/reserve**, and **savings is never clawed back**. With **tiered exits the normal
trade shape**, trading cash **bled monotonically into locked pools as a function of gross winning
legs**. Fixed same day (`4799bfc7`, [[synthesis/owed-measurements]] item 30c —
[[sources/session-20260805-evening]] §5).

> **This changes no term of the thesis, and that is the point.** Cost/sigma, the payoff ratio and
> both nulls are unmoved. What it changes is the account those terms are measured on: capital was
> leaving the sizer's reach through a path that appears nowhere in the cost stack, the geometry, or
> the win rate. **A thesis about where the edge is does not automatically see where the cash
> goes** — and the drain was a function of *gross winning legs*, i.e. it grew with exactly the
> activity the thesis treats as progress.

*08-06 addendum — the cost thesis demonstrated in its purest form, by a bug.* For **24.65
minutes** the bot took **no position at all** and still lost **$303.07** of paper equity, of which
**$289.73 (95.60%) was fees**. The hedger opened and unwound one ADA/USD hedge **147 times** —
**294 fills, $72,433.15 of notional on a $4,933 book (14.7x equity), zero other fills in the
window** — because its open path and its unwind path measured two different correlations
([[sources/session-20260806-hedge-thrash]], [[concepts/two-paths-one-quantity]]).

> **Every term of the thesis is unmoved, and the demonstration is still worth filing.** This is
> the cost stack with the signal set to zero: **no entry decision, no exit geometry, no win rate,
> no model** — just execution, running at the 5-second cycle, converting **14.7x the account** into
> **80 bps per round trip**. It is the arithmetic the thesis has always asserted, run as an
> experiment nobody designed: *turnover alone, at this fee schedule, destroys the account on a
> timescale of minutes*.
>
> Three qualifications, all load-bearing. **(1)** It is **paper** (`system.dry_run = True`) and
> priced at the deliberately overstated **40 bps** taker constant; at Kraken's published 26 the
> same churn is **$188.33**. **(2)** All 294 fills were **`post_only=0`, marketable** — the one
> order class that is **not** subject to the post-`8e5455e8` honest passive fill probability
> (0.048), so this could never have happened at that rate through the maker path
> ([[synthesis/risk-posture-doctrine]]). **(3)** It reinforces the **ranked cost levers**, not the
> payoff-asymmetry diagnosis: nothing here says anything about win rate, payoff ratio, or either
> null.
>
> **The forward reading:** the ranked lever *maker-only execution* is not only a bps saving — it is
> also a **rate limit**. A maker-only path could not have executed 294 crossing fills in 25
> minutes; the honest fill probability would have starved the loop. **Cost discipline and churn
> containment are the same lever seen from two sides**, and the account had no separate churn
> breaker: `risk/circuit_breaker.py` is fed inside `if not pos.is_hedge:` (main.py:1588) and
> **never saw a single one of the 147 losing round trips** — [[synthesis/owed-measurements]]
> item 34.

*08-07 addendum — the panel verdict sharpens the thesis on both edges
([[sources/session-20260807-institutional-review]]).* Two corrections and one enlargement:
**(1)** the churn arithmetic above carries panel corrections — paired gross was **−13.37**
(~95.7% fees, not "no position at all / all fees"), the "$188.33 at published 26 bps"
counterfactual inherits a **falsified** fee premise, and the "two incidents" were **one
ledger event double-filed** (this page's 08-06 addendum and the 01:09Z window are the same
event). **(2)** The balance-sheet observation is now adjudicated, not just arithmetic:
**equity −384.67 from start vs `fees_total` 382.28 — the book's entire drawdown is fees, and
the book is approximately flat on price.** "We lose to the schedule, not the market" is the
panel's most actionable diagnosis — with the caveat that the schedule itself is now
**unverified in the dangerous direction** (Tier-1 real drag ~1.6–2x modeled → the drawdown is
a **floor**). *(Foundation verified 08-07 evening: `fees_total` is structurally the ONLY
complete fee ledger — one counter, exactly two writers, every leg of both books — so this
identity compares equity against the right series;
[[sources/session-20260807-evening-ops]] §4.)* **(3)** Every dollar in this thesis is **sim-side** of the
[[concepts/paper-real-boundary]]: fees are config constants, fills are RNG-at-limit, and the
panel killed the one "edge" reading (ETH/BTC maker markout) as simulator physics. The
thesis's terms — cost/sigma, payoff ratio, both nulls — survive because they are *relative*
measurements; the dollar magnitudes do not transfer to the venue and must never be quoted as
if they do. The fee-economics decision itself is opened and **sequenced post-h432**
([[synthesis/owed-measurements]] item 37).

*08-07 night addendum — the fleet sweep turns the boundary caveat into an inequality
([[sources/session-20260807-fleet-findings]]).* Two findings, one reframe:

**(1) The simulator's optimism now has a named mechanism and a magnitude.** `sf_base=0.048` was
calibrated at **n_bar=5 polls (25s)** but is drawn **per poll**, so the 6h long-book bids
compound to fill probability **≈1.0** — on top of a deterministic trade-through path measuring
the **same predicate the calibrator measured** (double-count), with no depth or queue
constraint. Since 08-03, **22/41 entry fills sit at exactly −50.0 bps** (the long book's full
configured offset, all post-only, BTC 13 / ETH 9), and pooled maker markout reads **positive**
where real passive fills mark out negative. The honest-fills commit `8e5455e8` fixed the *rate*
for 25s orders and left the *horizon* wrong for hour-lived ones. Fix = owed item **40**, the
**#1 P&L-integrity item**; it mints a third execution-era boundary when it lands.

**(2) The reframe — losing even with the gifts.** `performance.by_asset` at filing: **every
asset negative expectancy except AVAX (n=3)** — BTC **0/17 wins, −$0.83/trade**; ETH **3/26,
−$0.64/trade**; profit factors **0.0–0.119**. The two assets receiving the phantom −50 bps
entry gifts are the **worst books on the sheet**. So the fill-sim skew is **not manufacturing a
paper edge** — there is no paper edge to manufacture. Because the skew's direction is one-way
optimism, every paper number in this thesis becomes an **upper bound**: *real execution would
be worse than a book that already loses everywhere.* The thesis's relative terms survive
unchanged; the fee constants stay **HELD behind h432** (item 37a); and no long-book fill,
markout row, or per-asset stat may be cited even as honest-pessimistic paper until item 40
lands ([[concepts/paper-real-boundary]]).

*08-08 addendum — item 40 landed the next morning
([[sources/session-20260808-morning-batch]] §1).* Commit `3cfe0710` TTL-normalizes the passive
hazard (`_passive_poll_prob`: per-order fill probability TTL-invariant at the calibrated
F(25s); 25s book bit-identical, G1–G5 unchanged) and **mints execution-era boundary #3** —
after the QA quarantine and XV-021. Consequences for this thesis: **(1)** the phantom −50 bps
gift channel is **closed going forward** — from the 11:10 boot every long-book fill is priced
by the honest simulator, so the citation embargo above narrows to **pre-boundary** rows
(fills before 2026-08-08 remain uncitable; per-asset stats must cut at the boundary);
**(2)** the "upper bound" reframe **stands** — the book was losing even with the gifts, and
removing them can only lower paper P&L, never raise it; expect the long-book paper fill rate
to drop sharply, which is the honest rate, not a regression (the same reading discipline as
`8e5455e8`); **(3)** every dollar remains **sim-side** — the simulator is now honest at the
hazard layer for both books, and still a simulator; whether real 6h resting orders fill above
or below the F(25s) floor is XV-023 (owed 40b). No term of the thesis moves: cost/sigma, the
payoff ratio and both nulls were never conditioned on the long-book gift.

---

## 2026-08-09 — the decomposition the thesis had been asserting for a week

([[sources/session-20260809-unbiased-economics]]. All terms re-derived at filing from the live
`outputs/state.json`, not quoted from a report.)

The 08-07 panel line — *"the book's entire drawdown is fees, and the book is approximately flat
on price"* — was an **equity-vs-fees comparison**, not a decomposition. It had never been split,
because **49% of lifetime fees were in no P&L counter at all** (§6 of the source page). Split, it
reads:

> [!error] **THE 32.8x RATIO IS STALE AND STATISTICALLY VOID (2026-08-16)** — the decomposition below stands as an 08-09 reading; the RATIO does not travel.
> Two independent defects, either of which is sufficient:
> 1. **It is 98.6% pre-correction.** Of the **415** round trips in it, **218 predate the passive
>    fix** and **177 ran under the live double-count** (execution-era boundary #4, `aeeaae36`,
>    2026-08-10T11:03:35Z — [[synthesis/comparability-boundaries]]). **Only 14 ran on today's
>    simulator, and on those 14 gross is POSITIVE (+$0.82).** Pooling across boundary #4 is exactly
>    what that table forbids.
> 2. **It divides by a statistical zero.** Gross is **−11.89 ± 19.4** (z = **−1.20**), so the
>    ratio's confidence interval is **[12.2x, +∞)**. A ratio whose denominator's CI straddles zero
>    is not a magnitude, it is an artifact ([[concepts/ratio-aggregation-bias]]).
>
> **What survives:** *"there is no MEASURED gross edge"* — i.e. gross is **indistinguishable from
> zero**, which is **not** the same claim as *"there is no edge"*. See §The corrected headline below.
> **Do not quote 32.8x.** Re-derive on a single-era cohort or say the ratio is unavailable.

```
GROSS trading P&L, before ANY fees :   −11.66
total fees paid                    : −382.59   (opening 185.94 + closing 196.65)
NET realized, all-in               : −394.25   = −7.89% of the 5000.00 starting capital
fees as a multiple of |gross edge| :    32.8x     <-- STALE + VOID, see callout above
```

Over **~250 closed positions / 438 entry fills**: gross **−11.66 total ≈ −$0.05 per trade**,
indistinguishable from zero. **100% of the loss is costs.**

> **The upgrade in strength, stated plainly.** "Approximately flat on price" and **"there is no
> measured gross edge"** are different claims, and only the second one is now supported. The
> thesis has always said cost is the larger term; it now says the *other* term is **~0**.

**Corroborated by three unrelated instruments** — OOF **AUC 0.43–0.48** (at/below chance),
champion **Brier 0.24728 vs 0.25** for a coin, and postmortem **MFE median 0.18% / p90 0.55%**
against a **~0.65%** round-trip cost (*the median trade never moved far enough in its favour, at
its single best moment, to cover its own costs*).

> [!note] **CURRENCY + BASELINE CORRECTION (2026-09-05).** The conclusion holds and is
> re-derived on a **2.2x larger corpus**; one of its three corroborations was scored against
> the wrong constant.
> **The baseline.** "Brier 0.24728 **vs 0.25** for a coin" uses a **fair-coin** baseline on a
> label whose base rate is **not 0.5**. The honest constant is `p(1-p)`. Measured this session
> on the OOF rows themselves: base rate **0.4496** -> constant Brier **0.247458**. Against
> **0.25** the champion appears to win; against its own base rate it does not. The old
> comparison was *generous to the model*, so correcting it **strengthens** the thesis.
> **The re-derivation.** Deployed selection (`evaluate_and_select`, current corpus 14,915 rows
> / 12,425 OOF rows / 18 day-blocks, family `logistic`): model OOF Brier **0.248069** vs
> constant **0.247458**, **skill score −0.0025**, paired day-block bootstrap of the per-row
> Brier difference **95% CI [−0.0029, +0.0043]**.
> **State the verdict precisely: INDISTINGUISHABLE FROM THE CONSTANT, not "worse than".**
> The CI spans zero. A first pass this session read −2.72% "worse" by comparing `oof_brier`
> (the purged walk-forward OOF **subset**, `scripts/train_meta.py:379`) against `class_balance`
> (the **full** training matrix, `main.py:6734`) — **two different populations** in one ratio,
> which is [[concepts/the-method]] reading-discipline (a) exactly. Both numbers above are on
> one vector.
> **Second route, agreeing.** The artifact's stored walk-forward importance (OOS **AUC drop**
> under permutation): max **+0.0079** (`other_ret_6_dir`), **0 of 10** features above 0.01 —
> discrimination carried by nothing in particular.
> Re-derive, do not quote: `scratchpad/skill_score.py` pattern, or rebuild from
> `evaluate_and_select` + `cross_fitted_calibrated_oof`. See
> [[concepts/resolution-vs-direction-decomposition]].

> [!warning] **"THREE INDEPENDENT REFUTATIONS" WERE NOT INDEPENDENT (2026-08-16)**
> The phrase has been used on this page and downstream for a **third** trio — `breakeven_test.py`,
> `geometry_search.py` and `random_entry_control.py`. Commit **`415af0f9` (2026-08-09)** fixed the
> **same one-line defect in all three at once**, which is the definition of a shared data path —
> and it landed **four days AFTER the 2026-08-05 date they are cited under**. In
> `breakeven_test.py` the defect **INVERTED the printed verdict** (hedge legs discarded flipped
> median gross **−0.0303% → +0.0505%**).
> **All three must be RE-RUN post-`415af0f9` before being cited again.** Until then their agreement
> is evidence about one bug, not about the book ([[concepts/two-paths-one-quantity]]).

**And the caveat runs against the bot, as always on this page:** the fill simulator is
one-way optimistic (full quoted offset, no queue, no depth, pooled maker markout **+3.58 bps @5s**
where real passive fills mark out negative). **Real-execution gross would be WORSE than −11.66.**
The defensible statement is **gross edge ≤ 0**, sim-side of [[concepts/paper-real-boundary]].

### What moves, and what deliberately does not

- **[[concepts/payoff-asymmetry]] is relocated, not refuted.** 0.561-vs-0.750 describes the
  **shape** of the gross distribution; this describes its **mean**, and the mean is ~0. The
  asymmetry remains the correct account of *why losses exceed wins*; it is no longer the deepest
  layer.
- **The two 08-02 nulls are unmoved and better explained.** A search for entry timing or bracket
  geometry inside a population whose gross mean is ~0 is *expected* to return null. They were
  never underpowered — they were looking for structure in a population that has none measured.
- **The ranked cost levers survive but change meaning.** Halving fees on a book with **zero gross
  edge** converts a −394.25 loss into a smaller loss, **not into a profit**. Cost work is now
  **necessary and provably insufficient** — the sharpest form of the 08-02 correction.
- **The h432 lead is the one live thread, and it is GEOMETRY.** Shadow win rate rises monotonically
  **22.3% → 30.4% → 35.4%** at 108 → 216 → 432 bars — exits are early relative to the cost being
  paid ([[comparisons/horizon-96-vs-24-bars]]). And `config_guard` has been saying the verdict out
  loud: **derived entry bar 0.990 > 0.90**, *"fix the geometry, the bar is only reporting it"*
  ([[entities/config-guard]]). **A required win probability of ~99% is not a modelling problem.**
- **The free population is the honest next search space.** **9,570 CANDIDATE rows cost zero
  fees**; the 305 live rows cost ~382.59. Any proposal of the form *"trade more to learn more"*
  now owes an argument for why the **31x-larger free sample cannot answer the same question**.

### The framing correction this measurement forced

The thesis is written in this project's house vocabulary, and that vocabulary was found to be
**absorbing results rather than being tested by them**. "Data-starved" predicts a gross edge > 0
that is merely hard to select on; **measured gross is ~0, which falsifies it as a complete
account.** The governing rule is now filed as
**[[concepts/unfalsifiable-explanation]]** — *an explanation that cannot be wrong is not an
explanation* — and every house term on this page carries its falsifier from here on.

### The blocker on the obvious next question

The most decision-relevant open question — **is there gross edge in ANY subpopulation** (asset,
regime, horizon, signal strength)? — **cannot currently be asked.** `signal_history.csv` carries
`net_pnl_usd` and **no gross and no per-row fee column** (verified: 93-column live header), so no
row can distinguish *"the signal was wrong"* from *"the signal was right and costs ate it"* — and
the **binary win/loss label conflates the two at the point where the model learns**, so corpus
growth cannot fix it. [[synthesis/owed-measurements]] item **50**, HIGH.

---

## 2026-08-09, later — CONFIRMED BY A SECOND INDEPENDENT METHOD, and the go/no-go tool was printing the opposite

([[sources/session-20260809-adversarial-audits]] §4.1, §5. Sim-side dollars; repo-side defects.)

### Two methods, no shared mechanism, one answer

| Method | Gross P&L before any fees | Population |
|---|---|---|
| **State identity** — `start + realized − cash − savings − reserve` | **−11.66** | ~250 closed positions |
| **Full-book `fills.csv` reconstruction** — independent accumulation over the fill ledger | **−13.01** | **394** closed round trips |

against **382.59** of fees. **Agreement to within 1.35 on a book that paid 382.59 in costs.**

This matters because of **how** the second number arrived: it was **a by-product of fixing a
bug**, not an attempt to reproduce the first. The audit re-implemented
`scripts/breakeven_test.py`'s own accumulation with the hedge leg restored, and the gross fell
out. **An independent check that nobody set out to run is the strongest kind available.**

### The go/no-go tool has been printing the wrong branch

`scripts/breakeven_test.py:126` counts **only `purpose == "entry"`** as the opening leg, so **159
complete hedge round trips** are discarded as *"partial or malformed"* (**none are malformed**).
That moves the **median gross from −0.0303% to +0.0505%** — **a sign flip** — and the sign
**selects which of two hard-coded verdict branches the tool prints:**

| | printed |
|---|---|
| **shipped** | *"This is NOT 'no edge' … that is exit geometry … **fixable without touching the signal**"* |
| **corrected** | *"**GROSS EXPECTANCY IS NEGATIVE** … no execution change, holding period, gate, filter or model creates expectancy that is not in the entries."* |

> **The thesis's central question has had a dedicated instrument the whole time, and that
> instrument has been answering it backwards.** The corrected branch is the one that agrees with
> both gross measurements above.

**What this does NOT change:** the *"exit geometry"* framing did not originate with this tool. The
08-02 pre-registered 48-combo bracket grid reached a bounded version of it by an independent
method and is **unaffected** ([[concepts/payoff-asymmetry]]). What is retracted is any citation of
**this tool's verdict line** as evidence that the problem is fixable without touching the signal.
Registered as [[synthesis/open-contradictions-register]] entry **22** and
[[synthesis/owed-measurements]] item **53**.

### The direction of every remaining error is known

A 25-agent adversarial sweep of every reporting surface found **eleven distortions and ZERO that
understate the bot** ([[concepts/self-flattery-gradient]]). Combined with the fill simulator's
measured optimism (**22.30% per-order fill against an 11.66% calibration target**, resting orders
getting two chances per event — **mechanism derived and FIXED 2026-08-10, `aeeaae36`, execution-era
boundary #4: `2f−f² = 21.96%` against the `f = 11.66%` target, 1.88x at the touch**,
[[sources/session-20260810-fill-double-count]]), the thesis's economic statement tightens to its
final form:

> **Gross edge ≤ 0, and every known measurement error points the same way — toward the reported
> figure being the FLATTERING one.**

The practical consequence for planning is unchanged in kind and stronger in degree: **cost work is
necessary and provably insufficient**, and **no reporting fix on this docket can improve the
book** — every one of them, when landed, moves a published number **down**.

---

## 2026-08-09, evening — the tool was FIXED, and two more independent methods agree

([[sources/session-20260809-turing-test-hedge-verdict]]. Sim-side dollars; repo-side defects.)

### The instrument now prints the branch the thesis has been arguing for

**`415af0f9`** shipped *hedge-is-an-opening-leg* — and the defect was **five files wide**, not one:
`breakeven_test`, `cost_attribution`, `cost_truth_report`, `geometry_search`,
`random_entry_control`. All five had been reasoning about **235 of 394** round trips.

| `breakeven_test.py` | before | after |
|---|---|---|
| closed / skipped | 235 / 165 | **394 / 6** |
| **median gross** | **+0.0505%** | **−0.0305%** |

**The prescription INVERTED**, from *"that is exit geometry … fixable without touching the
signal"* to *"**GROSS EXPECTANCY IS NEGATIVE** … no execution change, holding period, gate, filter
or model creates expectancy that is not in the entries."*

> **The retraction registered as [[synthesis/open-contradictions-register]] entry 22 is now
> discharged in code.** Every citation of the old verdict line stays retracted; the tool no longer
> produces it. Owed items **53** and **56 CLOSED**.

*(Numeric note: the audit predicted −0.0303%, the shipped fix measures **−0.0305%** — 0.0002pp,
recorded rather than smoothed. **−0.0305%** is citable.)*

### Method three: the t-statistic. Method four: a population with no overlap at zero.

| Method | Result |
|---|---|
| **Per-trade gross edge, % space** | **−0.0019%**, **t = −0.332** |
| **Hedge round trips profitable NET of fees** | **0 of 159** |

**`t = −0.332` is the cleanest statement the thesis has ever had.** Not *"a small negative edge"* —
**statistically indistinguishable from zero**. Four methods now agree (state identity −11.66;
full-book fills −13.01; `t = −0.332`; and three corroborating instruments at/below chance):

> **The book is FLAT ON SELECTION and losing entirely on COST.**

And **0 of 159** is the strongest form of [[concepts/priced-bleed]] available: the hedge
population's net outcome distribution **does not overlap zero at all** (gross win rate 15.1%, net
win rate **0.0%**), on **$39,460** of notional — **4.5x** the entry book's **$8,821**, and
**invisible to the performance ledger and the circuit breaker** the entire time.

Meanwhile the entry book won **57.4%** of the time on a **+0.0505%** median and still totalled
**−$3.03** gross over 235 trips. **Winning most trades, on a positive median, and arriving at
zero** is exactly the [[concepts/payoff-asymmetry]] shape — and it is why `t = −0.332` is the
honest summary rather than a pessimistic one.

### The cost history is dominated by one 25-minute bug — and that does NOT rescue the thesis

**77.3% of ALL lifetime fees** (**$289.73** of **$374.96**) were spent in **25 minutes** on
**2026-08-07 01:09–01:34Z**: **147** ADA hedge round trips, **$36,210** notional, gross
**−$12.77**. No recurrence in **56.5h**.

> **Both halves must travel together.** *The churn dominates the fee history* **and** *removing the
> churn does not create an edge*. The `t = −0.332` verdict is computed on the book, and the
> **gross** term — the one that would have to be positive for any of this to work — is ~0
> **independently of the churn**, which was itself only **−$12.77** gross.

*(This is the already-reconciled single ledger event of
[[synthesis/open-contradictions-register]] entry 19 — **not** a third incident. Quote the 77.3%
with its **$374.96** denominator; at the $382.59 state-identity figure it reads **75.7%**.)*

### What is genuinely new: the loss now has a BEHAVIOURAL description

A Turing-test framing found the book **mechanically inhuman and economically retail**
([[comparisons/bot-vs-discretionary-vs-algo-trader]]): identified as a machine within seconds on
order mechanics (**after-win/after-loss size ratio 1.000**, modal ticket **exactly $18.00 x51**,
**0.0%** round-number landing, **100%** limit 1019/1019, **59** holds at exactly **5.000s**), yet
carrying the full economic signature of an unprofitable retail human — **58.3%** win rate on a
**0.670** payoff with a **2.20x disposition effect** (losers **2.00h**, winners **0.91h**).

**The resolution is [[concepts/behavioral-isomorphism]]: the bias is geometric, not
psychological.** A near take-profit with a far stop manufactures the disposition effect by
arithmetic. This matters to the thesis in one specific way:

> **It supplies a natural WRONG prescription, and the thesis must refuse it.** *"Stop cutting
> winners early"* is the correct reading of a human with these numbers. On this book it is ruled
> out — **there is no expectancy for better exits to harvest.** The discretionary reading
> diagnoses the symptom the corpus chased for a week; the algorithmic reading (**368x** cost/edge
> in percent space, **0.91h** median winner against **0.71%** round-trip cost, **60.6%** taker
> fills on a maker-thesis book) rules it out as a lever.

*(**368x** and the **32.8x** above are **not** in conflict — percent-space-per-trade vs
dollar-space-whole-book. [[concepts/ratio-aggregation-bias]].)* **— 2026-08-16: moot. The 32.8x is
retracted (stale across execution-era boundary #4, and dividing by a statistical zero), and 368x
inherits the same denominator problem. Neither multiple may be quoted; the surviving statement is
that gross is indistinguishable from zero.**

### What this section does NOT do

- **Does not restate [[concepts/payoff-asymmetry]].** The **58.3% / 0.670** pair has an **unstated
  corpus** and is filed as a **citation hazard**, a *third* derivation beside 0.561-vs-0.750 at
  n=217 — not a replacement.
- **Does not decide owed 52(b).** The breaker counterfactual is measured (**+1 trip in 19.5 days**
  to count hedges; the churn stopped at **4 laps instead of 147**; breaker has fired **48 times
  across 12 assets**) and the gate semantics remain the operator's
  ([[concepts/never-widen-a-gate]]).
- **Does not touch the 432-bar hold or the 08-02 nulls** — the latter are now better explained than
  ever: a search for structure inside a population with **t = −0.332** is *expected* to return
  null.

---

## 2026-08-10 — the fill flattery is now MEASURED and REMOVED, and the thesis does not move

([[sources/session-20260810-fill-double-count]]. Sim-side instrument change; repo-side fix.)

Owed 57 closed as **execution-era boundary #4**. The mechanism behind the *"resting orders get two
chances per event"* clause above is now derived rather than inferred: `calibrate_fills.py` measures
`f` = how often the market crossed a hypothetical resting limit, `invert_base_prob` solves
`sf_base` so **the hazard alone reproduces `f`**, and `_poll_dry` **also** filled deterministically
on that same crossing — with the hazard running **only inside `if book:`**, making it purely
additive. `1−(1−f)² = 2f−f² = **21.96%**` against the **11.66%** target, versus the **22.30%**
measured here: **0.34 pp**, from two computations with no shared mechanism.

**Why the thesis is unchanged, and why that is the point.**

> Every number in this thesis was computed **under** the flattered simulator. Removing flattery
> can only move them **DOWN**. **Gross edge ≤ 0 was measured with the bot's thumb on the scale;
> taking the thumb off does not create edge.**

The **direction-of-error** section above is strengthened, not revised: the largest single
distortion on the 08-09 docket is now **quantified at 1.88x near the touch** and **removed**, and
the population it distorted is the modal one — **57.2% of 402 `post_only` fills rest within 5 bps**
and **38.4% of all 401 positions** were opened by a near-touch `post_only` leg.

**The one forward-looking consequence worth planning around:** the config states the expected
effect as *"the paper fill rate roughly HALVES near the touch."* The book will trade **less**.
Under [[synthesis/risk-posture-doctrine]] that is a **truthful outcome, not a regression** — and it
is the **third** time this project has shipped a fill correction whose visible effect is fewer
trades, each time with the drop written down in advance. **A thinner honest book is the correct
consequence of a book with no gross edge**; the answer is still not more fills.

> **What may NOT be concluded from this.** Propagation into the 305 live corpus rows and the
> 432-bar cohort verdict remains **DIRECTIONALLY SUPPORTED but UNMEASURED** and **may not be cited
> against the hold** (owed 57's own embargo). And the corpus is **entirely pre-boundary** — the
> last ledger row predates the commit — so **there is not yet a single honest-fill trade to
> reason from.** Every dollar figure in this thesis still carries the ~1.88x near-touch fill bias.

## 2026-08-10, evening — the thesis gets its verdict instrument, and the book gets a stressor

([[sources/session-20260810-stressor-epoch]]. Repo-side registration; sim-side dollars.)

**The go/no-go question this thesis has been circling is now a pre-registered instrument.** The
CAIO adjudication (operator: *"apply them"*) **froze model-side investment** and moved the
strategy verdict to the **era-4 gate** (`d6112bca`): on the first cohort of honest-fill closes —
population cut `max(B4_TS, CAPITAL_EPOCH_TS)` = **2026-08-10T23:05:27Z**, entry-opened round
trips reconstructed from `fills.csv`, hedges excluded — the readout at **n≥50, never before**
is **NO_GROSS_EDGE** (gross mean AND median ≤ 0 → the stop-strategy question goes to the
operator), **COST_BOUND** (gross > 0, net ≤ 0 → the h432 fee levers become the live
discussion), or **CONTINUE** (net > 0). The tool never decides — it names which decision has
become decidable. **The freeze's ONLY unfreeze trigger is this readout.** Its epistemics are
printed on its face: at n=50 the SE of mean gross is ~0.07%, so only |edges| beyond ~0.14% are
resolvable — an order of magnitude above the −0.0019% this book has exhibited; the gate is a
decision trigger, not an effect measurement.

**And the cohort it reads accrues under the $800 stressor** (operator-adjudicated; capital
5000 → 800, goals $100/month with the RP-072 ×1.5 ratchet, venue floors deliberately unscaled
so the $15 ticket is **1.9% of equity**). The honesty line is part of the record: **nothing in
the config makes a book with no measured gross edge earn $100/month** — the expected outcome
is this thesis's truth arriving **faster and louder**, which is what a stressor is for.
Accrual restarted **0/50** at the epoch; the three post-#4 pre-epoch closes were excluded
(honest fills, wrong capital regime). Every number in this thesis above this section is
**pre-epoch as well as pre-#4** ([[synthesis/comparability-boundaries]]).

## 2026-08-11 — the Grand Synthesis directive routes THROUGH this thesis, not around it

([[sources/directive-20260811-grand-synthesis]]. Operator-side directive; filed 2026-08-10.)

The operator's standing directive — all open issues in one frame, bot-specific algorithms
parameterized only from the bot's own uncensored data, "lead the corpus unto a path of profit"
— **changes the work plan, not the verdict structure.** Its own execution plan sequences every
phase through the standing laws: the geometry-epoch package (Phase C, the one place exit
geometry may change) waits on operator timing adjudication and mints
[[synthesis/comparability-boundaries|cut #7]]; model-frozen items stay frozen; and the honesty
line is on the directive's face — **the sequencing maximizes P(finding edge if it exists) and
speed-of-knowing if it does not; the era-4 gate remains this thesis's sole arbiter.** One new
input this thesis has never had: `outputs/trade_paths.csv`, the **uncensored** excursion ledger
(winners included — the winners' heat profile previously did not exist on disk), which is what
any evidence-derived stop geometry will be parameterized from — **after** it is decontaminated
(a QA fixture row was in it at filing; [[synthesis/owed-measurements]] item 65). The two
decisive nulls stand unmoved: exit design minimizes bleed, it does not create edge — the
directive's algorithms will be tested against that boundary, not assumed past it.

**Delivered 2026-08-10 (late session).** The trigger satisfied and the package filed:
[[synthesis/grand-synthesis-algorithm-package]]. The ledger **shipped decontaminated**
(`2602371b`, owed 65 closed — the QA row quarantined, battery 14 correctly RED on it, battery
15 ALL GREEN with `BATCH_EXIT=0` verified directly). What the package does to THIS thesis:
Tier 1 is measurement only; Tier 2 (ALGO-5 counterfactual stop replay, ALGO-6 time-decay
ladder + hard time limit against the 2.20x holding asymmetry, ALGO-7 mark-triggered
off-round-number stops) **waits on the operator's cut-#7 timing adjudication** and would be
this book's one authorized geometry change since the 48-combo null. The academic sweep's
load-bearing result (Kaminski-Lo: stops add value under momentum, pure tax under random walk)
and its evidence lean (**NOT widen** — [[sources/sweep-20260811-academic-stops]]) are both
consistent with the nulls: nothing in the literature or the package claims exit design
creates edge — the era-4 gate remains this thesis's sole arbiter, unchanged.

## 2026-08-11, later the same night — cut #7 minted; the one authorized geometry change lands

([[sources/session-20260811-cut7-geometry-epoch]]. Repo-side commits; all placed stops sim-side.)

The operator's timing adjudication arrived as a **CDO-review split**, and **cut #7 is minted**
at `2026-08-11T01:33:50Z` (`e7d5ca1a`) — this book's **first and only authorized geometry
change since the 48-combo null**, and a deliberately narrow one: the **Osler widen-beyond
flip, direction-only** (the shipped nudge had held the opposite, tighten-above semantics — and
was nearly dormant and reading a phantom config block, so the *measured* book largely never
had round-number hygiene at all), plus **ALGO-6 as pins over machinery that already existed**
(`tb_time` + PT-060). **What did NOT land is the point**: no stop width, no decay table — the
replay-parameterized halves wait on the ALGO-5 amendment at ~30 uncensored paths
([[synthesis/owed-measurements]] item 67), the pre-named next boundary. **The reset was
free**: zero closes existed between the capital epoch and the deploy, so era-4 gate accrual is
still **0/50** and `max(B4_TS, CAPITAL_EPOCH_TS)` selects the same population as "after cut
#7" by construction. Nothing about the verdict structure moved: the two nulls stand, the
freeze stands, and the widen-beyond direction is itself **on trial at the gate** — its
falsifier is the post-#7 cohort readout, not anyone's confidence in Osler.

## 2026-08-12 — 25 of the stressor's first hours produced zero evidence, for a reason unrelated to edge

([[sources/session-20260812-weekly-anchor-lockout]]. Sim-side dollars; the lockout itself
box-real.)

From the capital epoch to `2026-08-12T00:14:10Z` the book generated **zero entry orders from
118 candidates** — not because the cost math refused (though for 21 of them it also did:
SZ-023's p_win 0.34–0.40 against the honest **0.69 breakeven bar** survives the repair —
that IS this thesis, printed per-candidate) but because the un-re-anchored W33 loss-budget
anchor read the $800 reset as an 82.7% trading loss and **RP-041 vetoed everything**. Era-4
accrual stands **0/50 unchanged** — the population is untouched (nothing traded), the cost
was **calendar**: 25 of the stressor's first ~168 hours bought no evidence. One label-side
lead filed where mid-accrual reads go: the 118 dead candidates' h432 sim labels resolve
**62W/56L = 52.5%** — small n, sim-side, a lead and not a trend; the gate remains sole
arbiter.

## 2026-08-14 — the geometry's own arithmetic, upstream of every model question

The thesis has been decomposed to *gross edge ≈ 0 against ~~32.8x~~ fees* (**the 32.8x multiple is
retracted 2026-08-16 — stale and statistically void, see the callout above the decomposition
block; the "gross edge ≈ 0" half stands, and its honest form is "indistinguishable from zero in
BOTH directions"**). A cheaper statement of
the same fact is now measurable directly from the label geometry, **with no model in it at
all**: a triple barrier pays gross only if the target is hit at least `sl/(pt+sl)` of the time.

On all `triple_barrier_h432` rows (n=259, snapshot 2026-08-14T23:38:18Z; n=262 thirty minutes
later — live file, values as-of):

| quantity | value |
|---|---:|
| median `pt_frac` | **2.064%** |
| median `sl_frac` | **1.548%** |
| payoff | **1.333** |
| barriers | `tb_pt` **41** · `tb_sl` **141** · `tb_time` **77** |
| **breakeven target-hit rate** | **0.429** |
| ~~**realized target-hit rate**~~ | ~~**0.225**~~ **STALE — see callout** |
| gross expectancy | **−0.734% / barrier-resolved path, pre-cost** |

> [!warning] **0.225 IS STALE BY 47%, AND ITS IMPLICIT NULL IS THE WRONG NULL (2026-08-16)**
> The **realized target-hit rate re-reads 0.291**, not 0.225 — the row was a live-file snapshot and
> was quoted downstream as settled. Separately, the deficit-against-0.429 reading carries an
> **implicit 0.000% null** that is **wrong for a censored sample**: these barriers are censored at a
> vertical barrier with `a/b = 1.333`, so censoring removes profit-target-bound paths
> **preferentially** and the conditioning **manufactures** the deficit's sign. The correct driftless
> null falls with censoring — exact lattice DP, self-validating (it converges to the closed-form
> **0.4286 = 1.548/3.612** at ~0% censoring): **0.3758 at 48.6% censoring, 0.2351 at 86.4%**
> ([[sources/cost-to-volatility-horizon-mismatch]], [[concepts/wrong-null-calibration]],
> [[concepts/tautological-instrument]]).
> **The geometry statement survives; the deficit magnitude does not.** Re-derive from
> `scripts/cohort_eval.py`'s LABEL-GEOMETRY BREAKEVEN section — it is a live file.

**Model-independent.** No selector rescues a geometry whose own barriers pay −0.734% before a
cent of cost — which is why this belongs on the thesis rather than in the ML lane, and why it
sits *upstream* of the entire model-freeze question. It also sharpens the two 08-02 nulls
rather than disturbing them: *exit design minimizes bleed, it does not create edge* — here the
bleed is arithmetic in the geometry itself.

**Two caveats printed on the instrument's face**, per domain rule 1: the **77** time-stopped
paths resolve at neither barrier and are excluded from the ratio (never silently), and **119 of
123** recent rows are `source=candidate`, so this is the geometry's **counterfactual**
expectancy — **sim-side**, and **not** the era-4 verdict. It is context for the ALGO-5
adjudication, **not** its trigger: that trigger is the ALGO-4 ledger at **10 of ~30**
([[synthesis/owed-measurements]] item 67, where this session's own claim that it had fired is
retracted).

Now emitted every run by `scripts/cohort_eval.py`'s LABEL-GEOMETRY BREAKEVEN section
(`61c3b5c1`, report-only, pt/sl untouched and frozen).

**What did move on the verdict instrument, and it is not a number.** The era-4 population is
no longer known-homogeneous: **4 of 13 trips carry a stale-binary leg** and **6 of 13 straddle
a mid-flight champion deploy** ([[synthesis/owed-measurements]] item 74). The gate remains sole
arbiter — but *what it will arbitrate over* is now an open operator question, and it compounds
at ~3–4 closes/day.
— [[sources/session-20260814-cohort-instruments]]

## 2026-08-16 — the verdict state, and the instrument's own resolution floor

**Re-derived by RUNNING `scripts/cohort_eval.py` at 2026-08-16T21:01:13Z** (head `c4272391`).
Everything above dated 08-14 is an **as-of** reading; this supersedes the counts, **not** the
conclusions.

| quantity | value |
|---|---:|
| era-4 | **n = 16 / 50**, `verdict_available` **false** |
| effective n · mean uniqueness · SE inflation | **5.249648119206663** · **0.32810300745041643** · **×1.7458016289694764** |
| observed gross mean / trade | **+0.6576563162731225 %** |
| per-trade sd (double-derived, `gross_se_pct × √16`) | **2.559127919795581 %** |
| composition | probe **14/16 (87.5%)** · `exit_sim` **8** / `h432` **8** · stale-binary leg **4/16** · `exec_era 7-e7d5ca1a` **15/16** · straddling a deploy **9/16** |
| **LEGACY 2026-08-02 gate** | **42 / 50** — it **reads out FIRST, 26 closes ahead of era-4** |

> **THE INSTRUMENT CANNOT RESOLVE ITS OWN QUESTION, AND THE PROBLEM IS UNDERSTATED.** At the
> pre-registered n=50 the registration assumed a per-trade sd near **0.5%**; the measured value is
> **2.559128%** — **5.1x**. With `n_eff@50 = 16.405150`, SE = **0.631832%**, so the resolvable
> floor is **1.263665%** at **2·SE** — **1.92x** the observed gross mean — and **1.770132%** at
> **80% power, two-sided 5%** (multiplier **2.801585**) — **2.69x**. The two conventions differ by
> **40.08%**, and the 527-line **UNSIGNED** decision table **names neither** while its signature
> section commits the operator to the resulting numbers.
>
> **This is not an argument to move n=50** ([[concepts/never-widen-a-gate]]). It is the statement
> that at n=50 the CONTINUE branch is, in the decision table's own words at `:336`, **"a trigger,
> not a measurement."** [[synthesis/owed-measurements]] item **82**.

**And the geometry row keeps moving, which is why it is not frozen here:** realized target-hit
reads **0.2804878** at n=442 (this run) against a breakeven of **0.4285675** and payoff
**1.3334** — where the 08-14 table said 0.225 and the decision table said 0.291 at n=371.
**Re-derive it; do not quote it.**
— [[sources/session-20260816-catchup-08-12-to-08-16]]
