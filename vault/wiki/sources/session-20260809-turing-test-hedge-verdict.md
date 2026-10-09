---
title: "The Turing Test, the Hedge Verdict, and the Breaker Counterfactual (2026-08-09) — Machine on Mechanics, Losing Retail Human on Economics"
category: source
summary: "A two-panel identification test — a professional discretionary trader and an algorithmic trader are each asked to spot the machine — returns opposite answers on the same book: the discretionary panel identifies it INSTANTLY on mechanics (modal ticket exactly $18.00 x51, after-win/after-loss size ratio 1.000, 0.0% round-number landing, 8-decimal sizes including 31 dust legs down to 1.17e-09 ETH, 100% limit 1019/1019, 59 trips held exactly 5.000s, chi2 137.8 with zero empty hours) yet finds the ECONOMICS indistinguishable from an unprofitable retail human (58.3% win rate on 0.670 payoff, disposition effect 2.20x — losers held 2.00h vs winners 0.91h). The algorithmic panel's verdict is colder: gross edge -0.0019%, t=-0.332, fees 368x |edge| in percent space, and a 0.91h median winner against a 0.71% round-trip cost — a horizon/cost mismatch of an order of magnitude, with 60.6% taker fills. Also files the hedge population verdict (0 of 159 hedge round trips profitable NET of fees), the re-measured 147-lap churn (77.3% of ALL lifetime fees in 25 minutes), the owed-52 circuit-breaker counterfactual (counting hedges costs +1 trip in 19.5 days and would have stopped the churn at 4 laps instead of 147 — STILL AWAITING OPERATOR ADJUDICATION), two shipped fixes (415af0f9, f11b7e32), one new owed item (59, status-schema/fixture drift), and three self-caught agent errors including a retroactive excuse built from a pre-change green run"
tags: [turing-test, behavioral, hedge, circuit-breaker, churn, economics, cost, disposition-effect, self-flattery, paper-mode, shipped]
sources: 1
source_date: 2026-08
ingested: 2026-08-09
updated: 2026-08-09
---

# The Turing Test, the Hedge Verdict, and the Breaker Counterfactual (2026-08-09)

> **Paper/real boundary** ([[concepts/paper-real-boundary]], governance rule 13). Every fill, fee,
> hold time, taker/maker classification and dollar figure on this page is **SIMULATED**. The
> *mechanical* tells in §1 are **repo-side** — they are properties of the order stream the bot's
> own code generates. The *economic* tells are **sim-side** and inherit every known optimism of
> the fill simulator. Nothing here is venue truth. §1.4 raises a case where the distinction is
> not a caveat but the finding.

> **Times are UTC.** The 25-minute churn window in §2 is the **same ledger event** already filed
> twice under two clocks — see [[synthesis/open-contradictions-register]] entry **19**. It is
> **not** a third incident. This page re-measures it; it does not re-report it.

---

## 1. The Turing test — two panels, opposite answers

The question posed: *given only the trade ledger, could a professional identify this as a
machine?* Run twice — once against the standards a **discretionary trader** would apply, once
against the standards an **algorithmic trader** would apply.

### 1.1 The discretionary panel: identified INSTANTLY, on mechanics

| Tell | Reading | Why a human cannot produce it |
|---|---|---|
| **Modal ticket** | **exactly $18.00, x51** | Humans size in round *notional* or by feel; they do not repeat a non-round figure to the cent 51 times |
| **After-win / after-loss size ratio** | **1.000** | The single most reliable human signature is that this number is **not** 1.0. Winners press, losers revenge-size or shrink |
| **Round-number landing** | **0.0%** | Human orders cluster at round prices and round sizes. Zero clustering is a machine constant |
| **Size precision** | **8 decimals**, incl. **31 dust legs** down to **1.17e-09 ETH** | No human types nine-figure precision, and no human trades a nanogram of ETH |
| **Order type** | **100% limit — 1019/1019** | A human takes at least occasionally: panic, chase, close-at-any-price |
| **Hold time** | **59 trips held exactly 5.000s** | A hold time with three trailing zeros is a timer, not a decision |
| **Time of day** | **activity in all 24 hours**, chi2 **137.8**, **zero empty hours** | Humans sleep. The chi2 says the hours are *unevenly* used; the zero empty hours say they are *all* used |

> **The chi2 is the subtle one and it cuts both ways.** chi2 **137.8** is a strong rejection of a
> uniform hour distribution — the bot is *not* evenly spread, so an hour histogram alone might
> look human. **Zero empty hours is what kills it.** A discretionary human's ledger has a sleep
> hole; an uneven distribution with no hole is a machine with a schedule, not a person with a
> routine.

**Verdict: machine, identified on the first pass, with no economic analysis required.**

### 1.2 The same panel on the economics: indistinguishable from an unprofitable retail human

| Economic signature | Reading | The human analogue |
|---|---|---|
| **Win rate** | **58.3%** | The classic losing-retail profile: *wins often, loses more* |
| **Payoff ratio** | **0.670** | Needed at 58.3% is **~0.715** — short, and short in the usual direction |
| **Disposition effect** | **2.20x** — losers held **2.00h**, winners **0.91h** | The single most-documented retail bias: cut winners, ride losers |

> **This is the finding, and it is not a joke about the bot.** A deterministic system with no fear,
> no ego and no P&L anxiety **reproduces the exact economic fingerprint of an emotionally biased
> retail human.** The bias is therefore **not psychological here — it is geometric.** A bracket
> with a near take-profit and a far stop *manufactures* the disposition effect from arithmetic:
> winners hit their exit sooner because their exit is closer. Filed as
> [[concepts/behavioral-isomorphism]].
>
> The practical consequence: **"we are not emotional, so we do not have retail biases" is a
> non-sequitur in this codebase.** The signature is measurable and it is present.

⚠️ **Corpus caveat, stated because domain rule 1 requires it.** The corpus size and window behind
**58.3% / 0.670** were **not stated at filing**. This is a **third** payoff/breakeven derivation
alongside the two already in conflict ([[synthesis/open-contradictions-register]] entry **6**:
0.561-observed-vs-0.750-needed at 57.1% win rate, n=217 post-quarantine). It is filed as a
**citation hazard, not as a replacement**, and the 0.561/0.750 pair remains the figure
[[concepts/payoff-asymmetry]] is written on until the populations are reconciled.

### 1.3 The algorithmic panel: a colder verdict

A professional algo trader does not ask *"is this a machine?"* — that is obvious. The question is
*"is this machine worth running?"*

```
gross edge (per trade, % space)   :  -0.0019%
t-statistic                       :  -0.332
fees as a multiple of |edge|      :   368x
median WINNER hold                :   0.91 h
round-trip cost                   :   0.71%
taker fill share                  :   60.6%
```

Four independent objections, each sufficient on its own:

1. **There is no edge to trade.** -0.0019% at **t = -0.332** is not a small negative edge — it is
   **statistically indistinguishable from zero**, which is the honest reading. The bot is not
   losing on selection; it is **flat on selection and losing on cost**.
2. **The cost dwarfs the signal by 368x.** Any strategy whose per-trade cost exceeds its per-trade
   edge by two and a half orders of magnitude is not a strategy that needs tuning.
3. **The horizon and the cost are mismatched by an order of magnitude.** A **0.91h** median winner
   must clear **0.71%** round trip. The move required in under an hour to pay for the trade is far
   larger than the move the holding period is designed to capture ([[concepts/cost-to-volatility-ratio]]).
4. **60.6% taker fills** on a book whose entire thesis is passive/maker execution. The execution
   is not doing what the design says it does.

> **Denominator warning — 368x and 32.8x are BOTH correct and are NOT a contradiction.**
> **368x** is **percent space, per trade** (0.71% cost / 0.0019% edge ≈ 368). **32.8x** is
> **dollar space, whole book** (382.59 fees / 11.66 gross —
> [[sources/session-20260809-unbiased-economics]]). Different numerator *and* denominator. Neither
> refutes the other; quoting either without its space is the
> [[concepts/ratio-aggregation-bias]] trap.

### 1.4 The dust legs are not a curiosity — they are a paper/real boundary breach

**31 dust legs down to 1.17e-09 ETH** were *filled* in the ledger. **No real venue accepts an
order of ~1 nanogram of ETH** — exchange minimum order sizes are many orders of magnitude above
it. These fills, and their fees, exist **only because the simulator accepted what no venue would**.

This is raised by the filing agent, not by the operator's docket, and is registered as **owed
item 60** in [[synthesis/owed-measurements]]. It is stated as a **flagged concern requiring
verification** (the exact venue minimum is not quoted here), not as a measured fact.

---

## 2. The churn, re-measured — 77.3% of the book's entire fee bill in 25 minutes

> **Identity first.** Window **2026-08-07 01:09–01:34Z**, **147 ADA/USD hedge round trips**. This
> is the **same event** as [[sources/session-20260806-hedge-thrash]] (filed in local time as
> "08-06 20:09–20:34") and [[sources/session-20260807-hedge-churn-guards]] (filed in UTC as
> "incident #2"). **One event, two clocks, already reconciled** as
> [[synthesis/open-contradictions-register]] entry **19**. What follows is **new measurement of a
> known event.**

| Quantity | Value |
|---|---|
| Window | **2026-08-07 01:09–01:34Z**, ~25 minutes |
| Round trips | **147**, all ADA/USD hedge, **all 2-leg** |
| Held exactly **5.000s** | **59** of them |
| Notional churned | **$36,210** |
| Fees | **$289.73** |
| **Share of ALL lifetime fees** | **77.3%** (of **$374.96**) |
| Gross P&L | **−$12.77** |
| Recurrence since | **none in 56.5h** |

> **The single most important number on this page for planning.** **77.3% of everything this book
> has ever paid in fees was spent in 25 minutes by a bug.** The economic case against the bot in
> §1.3 is made on the *remaining* 22.7%. Both statements are true and they must travel together:
> *the churn dominates the cost history* **and** *removing the churn does not create an edge*
> (§1.3's gross edge is ~0 independently).

**Fee-denominator reconciliation (do not silently merge these).** This page's **$289.73** is the
**147 matched 2-leg round trips**. [[sources/session-20260807-hedge-churn-guards]] records
**$296.93** for the window **01:09:45–01:34:19Z** (open-leg $149.83 + exit-leg $147.10) over
**290 fills**, and **296 fills** in the wider 00:50–02:00Z window. The **$7.20** difference is
**consistent with** unmatched or out-of-window legs being excluded from the round-trip
population — but that is an **inference, not a measurement**, and it is filed as such.
Similarly the lifetime-fee denominator is **$374.96** (the corrected `breakeven_test`
full-book figure), **not** the **$382.59** state-identity figure; at the latter the share reads
**75.7%**. **Quote the share with its denominator or not at all.**

**The 59 trips at exactly 5.000s** connect §1 to §2 directly: the strongest single *mechanical*
tell in the Turing test is **an artifact of this bug**. A timer-perfect hold is what a churn loop
looks like from the ledger side.

---

## 3. The hedge population verdict — 0 for 159, net of fees

| | hedge-opened | entry-opened |
|---|---|---|
| Round trips | **159** | **235** |
| **Gross** win rate | **15.1%** | **57.4%** |
| **NET** win rate (after fees) | **0.0% — zero of 159** | — |
| Median gross | — | **+0.0505%** |
| Total gross | — | **−$3.03** |
| Net | **−$325.70** | **−$62.27** |
| Notional | **$39,460** | **$8,821** |

> **Not one hedge round trip in 159 was profitable after fees.** Not a low win rate — **zero**.
> This is the cleanest possible statement of [[concepts/priced-bleed]]: an instrument whose net
> outcome distribution does not overlap zero.

**The notional asymmetry is the structural finding.** The hedge book turned **$39,460** of
notional — **4.5x** the entry book's **$8,821** — while being **entirely invisible** to the
performance ledger and the circuit breaker (owed **52**). *The book's largest trader by volume was
the one nobody was measuring.*

**And the entry book is not the counterexample it looks like.** A **57.4%** gross win rate with a
**+0.0505%** median gross still totals **−$3.03** gross across 235 trips. Winning more often than
not, on a positive median, and still landing at zero gross is precisely the
[[concepts/payoff-asymmetry]] shape — and it is what makes §1.3's `t = -0.332` the honest summary
rather than a pessimistic one.

---

## 4. Owed 52 — the circuit-breaker counterfactual (CORRECTED, and STILL AWAITING ADJUDICATION)

> **STATUS: NOT DECIDED.** [[synthesis/owed-measurements]] item **52(b)** asked the operator a
> gate-semantics question: *should the consecutive-loss circuit breaker count hedge legs?* This
> section supplies **the measurement that question was waiting on**. It does **not** answer it.
> Per [[concepts/never-widen-a-gate]] and governance discipline, the decision is the operator's
> and is recorded only when the operator makes it.

**Method:** replay the **shipped** `CircuitBreaker` implementation over the **real close
sequence**, once as it runs today (hedges invisible) and once with hedge closes counted.

| | breaker trips, 19.5 days |
|---|---|
| As shipped (hedges invisible) | **42** |
| Counting hedges | **43** |
| **Cost of counting hedges** | **+1 trip in 19.5 days** |

**And the benefit, on the one event that mattered:** counting hedges would have **stopped the
churn after 4 round trips instead of 147**.

**Historical context:** the breaker has fired **48 times across 12 assets**.

> **The asymmetry, stated without a recommendation.** The operator's stated fear in item 52(b) was
> that counting hedge losses would trip the breaker **during correct operation**, because hedges
> are insurance that **loses by design**. The measured price of that fear is **one extra trip in
> nineteen and a half days**. The measured benefit is **143 round trips of churn not taken** —
> which, at §2's rates, is the large majority of **77.3% of the book's lifetime fees**.
>
> **This is a measurement, and measurements do not decide gate semantics.** It is filed so the
> adjudication happens against numbers instead of intuitions.

⚠️ **The first version of this replay was WRONG and is recorded in §7.2.** It never called
`is_tripped()`, so every asset tripped exactly once and the replay reported a false **"no
difference"** — a null manufactured by the instrument. The numbers above are from the corrected
replay.

---

## 5. SHIPPED `415af0f9` — hedge-is-an-opening-leg, across FIVE scripts

Closes [[synthesis/owed-measurements]] items **53** and **56**.

The docket estimated *"~10 lines"* on one file. The defect was **five files wide**:

`scripts/breakeven_test.py` · `scripts/cost_attribution.py` · `scripts/cost_truth_report.py` ·
`scripts/geometry_search.py` · `scripts/random_entry_control.py`

**`breakeven_test.py`, before and after:**

| | shipped (before) | corrected |
|---|---|---|
| Closed round trips | 235 | **394** |
| Skipped | 165 | **6** |
| **Median gross** | **+0.0505%** | **−0.0305%** |

> **The prescription INVERTED.** The tool's own hard-coded verdict branch is selected by the sign
> of the median, so the sign flip changed what the instrument *tells the operator to do*:
>
> | | printed |
> |---|---|
> | before | *"…that is exit geometry … **fixable without touching the signal**"* |
> | after | *"**GROSS EXPECTANCY IS NEGATIVE** … no execution change, holding period, gate, filter or model creates expectancy that is not in the entries."* |
>
> **Two opposite instructions about where to spend the next month, and the shipped tool had been
> printing the wrong one.** The corrected branch agrees with §1.3, with the state-identity gross
> (−11.66) and with the full-book reconstruction (−13.01).

**Numeric note (domain rule 2).** The audit's re-implementation predicted **−0.0303%**; the
shipped fix measures **−0.0305%**. A **0.0002pp** difference, almost certainly population or
rounding, **not** a discrepancy of consequence — recorded rather than smoothed. The shipped
**−0.0305%** is the citable figure.

**What did not ship with it:** the docket also asked for a **skip counter broken out BY REASON**
so *"partial"* and *"leg type deliberately excluded"* can never share a bucket again
([[concepts/uncounted-exclusion]]). **6 skips remain and their reasons are not yet itemised.**

---

## 6. SHIPPED `f11b7e32` — probe/conviction split, drawdown MTM export, hero tile

Addresses [[synthesis/owed-measurements]] items **54** and **55** and the **D1** hero-tile
repoint.

**(a) The probe/conviction split — SHIPPED AND CURRENTLY INERT.**
A third **`unknown`** bucket was added for pre-upgrade rows. Live reading:

```
unknown    : 200
probe      :   0
conviction :   0
```

> ⚠️ **This is [[comparisons/dormant-vs-inert-features]], and the corpus must not read the commit as
> the measurement.** The split is *correct in shape and currently measuring nothing* — every live
> row predates the flag. Item 54's actual finding (**probe n=182 expectancy −0.1636 vs conviction
> n=17 −1.5840**, a 5.6x understatement) **cannot yet be reproduced from the live split**, and
> will not be until enough post-upgrade rows accumulate. Domain rule 5: *shipped is not working.*
>
> The `unknown` bucket is nonetheless the **right** design — it refuses to guess a label for rows
> that never carried one, which is the [[concepts/zero-is-not-a-reading]] discipline applied to a
> category rather than a number.

**(b) Drawdown MTM exported.**

```
drawdown_mtm_pct   : 7.6706   (live)
realized-only      : 7.89
throttle           : 0.3416
```

`drawdown_mtm_pct` and `hard_stop_dd_pct` are now exported, so the quantity the **hard stop and
throttle actually fire on** is finally observable ([[concepts/two-paths-one-quantity]]).

> **Note the direction, because it is the opposite of the audit's worked example.** Item 55's
> reproduction had the gauge reading **green** while the stop fired. Here the **MTM figure
> (7.6706) is LOWER than the realized-only figure (7.89)** — the two series can diverge in either
> direction, which is exactly why they need **two names and two panels**, not a winner.

**(c) Hero tile repointed** to `net_pnl_all_time` (from `liquiditybot_realized_total`).

**What remains open on 55:** the **board regeneration** itself — panel repoints and the retitle of
the surviving gauge to *"Realized drawdown from start (reserve-inclusive)"*. **Boards are
GENERATED; the JSON is never hand-edited** ([[entities/observability-sidecars]]).

---

## 7. New owed item 59 — status-schema / fixture drift

**`a6334162`** (the all-in P&L reporting fix, filed earlier today) shipped **4 new status keys
plus gauges** and **did not update `_SYNTH_STATUS`**, the synthetic status fixture.

**The failure was latent by construction.** Nothing broke until a **panel referenced one of the
new keys**; at that moment `test_every_query_hits_an_emitted_metric` **failed — correctly.**

> **This belongs in the corpus as a POSITIVE specimen, not only a defect.** The test did exactly
> its job: it caught a real drift between the runner's status writer and the fixture that stands
> in for it. Contrast [[concepts/false-green]] — this is a gate that **could** fire and **did**.
> What is missing is not the check; it is the **coupling** that would have made the drift
> impossible to introduce.

**The class:** [[concepts/test-double-fidelity]] — a double that no longer implements what the
production object emits. The type specimen was a double supplying an attribute production
**lacks**; this is the mirror — a double **lacking** what production **has**.

**Fix:** a **schema pin between the runner's status writer and the fixture**, so adding a status
key without updating `_SYNTH_STATUS` fails at the source rather than waiting for a panel to
reference it.

---

## 8. Three agent errors, all self-caught, all filed

Recorded under domain rule 3 (*what was claimed → what refuted it → what stands*) and because
[[concepts/self-flattery-gradient]] applies to the analysis agent as much as to the bot.

### 8.1 A lying gate, and then a retroactive excuse for it

**Claimed:** the battery passed, citing an exit code.
**What refuted it:** the exit code cited was **`tail`'s, not the battery's** — the last command in
a pipeline reports its own status. This is precisely the [[concepts/false-green]] lying-gate class
already filed as owed **44**.

**Then the second, worse error.** On catching the first, the agent excused it by pointing at a
**green battery run from BEFORE the change**.

> **A pre-change green run cannot vindicate post-change behaviour.** It is evidence about a tree
> that no longer exists. Reaching for it is not a slip of fact — it is a **retroactive excuse**,
> and it is more dangerous than the original error because it *restores confidence without
> restoring evidence*. Filed as its own class: [[concepts/retroactive-excuse]].

**What stands:** the lying-gate class recurs (this is its second appearance since owed 44), and
the corpus now has a name for the specific way an agent talks itself out of one.

### 8.2 A counterfactual replay that omitted the mechanism under test

**Claimed:** counting hedges in the circuit breaker makes **"no difference."**
**What refuted it:** the replay **never called `is_tripped()`**. Without it, every asset tripped
exactly once and then kept trading, so both arms produced the same trace **by construction**.

> **The instrument could not have produced the finding it was looking for.** A null result from a
> harness that omits the mechanism under test is not evidence of no effect — it is
> [[concepts/tautological-instrument]] wearing the costume of [[concepts/honest-null-result]].
> The corrected replay is §4, and it found a real and decision-relevant difference.

### 8.3 A "7.04x revenge sizing" artifact, killed before it was filed

**Claimed (briefly):** the bot exhibits **7.04x revenge sizing** after losses — which would have
been a spectacular behavioural finding and would have **contradicted §1.1's after-win/after-loss
ratio of 1.000**.

**What refuted it:** the statistic **pooled two populations that differ 14.7x by construction** —
**entry** tickets (modal **$18.00**) and **hedge** tickets (**$265.44**). Losses are
disproportionately followed by hedges; pooling therefore manufactures a size jump that is
**purely compositional**.

**What stands:** the after-win/after-loss ratio of **1.000** within-population. Filed as the
second specimen on [[concepts/pooled-populations]].

> **This is the same error class the corpus filed against the bot's own reporting eight hours
> earlier** (item 54, `performance.overall` pooling probes with conviction trades). The analysis
> agent committed it while writing up the audit of it. That is worth saying plainly: **knowing a
> failure class by name does not confer immunity to it** — only running the disaggregation does.

---

## 9. What this session moves, and what it deliberately does not

**Moves:**
- [[synthesis/the-money-path-thesis]] — a **third and fourth** independent confirmation of gross
  edge ≤ 0 (`t = -0.332`; the 0 of 159 hedge population), plus the first **behavioural**
  characterisation of the loss.
- [[synthesis/owed-measurements]] — **53** and **56 CLOSED**; **54** shipped-but-inert; **55**
  partially shipped; **52** now carries its counterfactual; **59** and **60** registered.
- [[concepts/pooled-populations]] — second specimen, this one committed by the analysis agent.
- [[concepts/false-green]] — the lying gate recurs, plus a new adjacent class.

**Does NOT move:**
- **Owed 52(b) is NOT decided.** A measurement was supplied. The gate semantics are the
  operator's ([[concepts/never-widen-a-gate]]).
- **[[concepts/payoff-asymmetry]] is not restated.** §1.2's **58.3% / 0.670** has an unstated
  corpus and is a **citation hazard**, not a replacement for 0.561/0.750 at n=217.
- **The 432-bar cohort hold** — untouched.
- **The 08-02 nulls** — untouched, and better explained than ever by `t = -0.332`.
- **Nothing here licenses widening any gate**, and the §4 counterfactual in particular must not be
  read as authorisation.

---

## Related

[[concepts/behavioral-isomorphism]] · [[concepts/retroactive-excuse]] ·
[[concepts/pooled-populations]] · [[concepts/false-green]] ·
[[concepts/tautological-instrument]] · [[concepts/honest-null-result]] ·
[[concepts/test-double-fidelity]] · [[comparisons/dormant-vs-inert-features]] ·
[[concepts/cost-to-volatility-ratio]] · [[concepts/payoff-asymmetry]] ·
[[concepts/priced-bleed]] · [[concepts/uncounted-exclusion]] ·
[[concepts/ratio-aggregation-bias]] · [[concepts/self-flattery-gradient]] ·
[[concepts/never-widen-a-gate]] · [[concepts/two-paths-one-quantity]] ·
[[concepts/zero-is-not-a-reading]] · [[concepts/paper-real-boundary]] ·
[[comparisons/bot-vs-discretionary-vs-algo-trader]] ·
[[sources/session-20260809-unbiased-economics]] ·
[[sources/session-20260809-adversarial-audits]] ·
[[sources/session-20260806-hedge-thrash]] ·
[[sources/session-20260807-hedge-churn-guards]] ·
[[entities/liquiditybot]] · [[entities/observability-sidecars]] ·
[[synthesis/the-money-path-thesis]] · [[synthesis/owed-measurements]] ·
[[synthesis/open-contradictions-register]]
