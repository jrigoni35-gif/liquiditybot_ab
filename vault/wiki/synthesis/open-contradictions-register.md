---
title: Open Contradictions Register
category: synthesis
summary: "Claims in the corpus that conflict, with the resolution where one exists and the open status where none does — as of 2026-08-09 the incommensurable-champion-scores entry is instance-closed (ML-083 unwedged it without intervention) but class-OPEN; entry 21 is the framing contradiction ('data-starved' vs a measured gross P&L of −11.66 ≈ 0); and the adversarial audits added THREE more the same day — 22, a go/no-go tool whose METHOD and OUTPUT disagree because it discards 159 hedge round trips, so the corpus has been quoting the wrong one of its two hard-coded verdict branches; 23, decision-grade, where 'drawdown' names one quantity on the gauge and another in the hard stop that fires on it (a −20% book reads FULL GREEN); and 24, where the mixed-sample refusal exists in the ML-validation lane and is absent from the P&L-reporting lane NEW ENTRY 25, RESOLVED 2026-08-10 and kept because the retraction is the content: the corpus contradicted itself about its own fill simulator on three consecutive days - 08-07 named the double-count correctly, 08-08 disposed of it as a conservative floor, and 08-10 confirmed 08-07 was right (2f-f^2 = 21.96% vs an 11.66% target, 1.88x at the touch). The measurement never changed; the finding was lost at the DISPOSITION step, in a session careful enough to catch its own test-count error. Rule extracted: a disposition that closes a docket item deserves the same adversarial pass as the finding that opened it, and MORE when written beside a fix the author is pleased with."
tags: [register, contradictions, honesty, falsifiability]
sources: 32
updated: 2026-08-27
---

# Open Contradictions Register

Maintained deliberately. Some entries are resolved; the unresolved ones are the point.

## UNRESOLVED

### 1. Effective sample size vs the DoF ledger — the most consequential
[[sources/weekend-labels]]: Kish effective sample size **1,624 -> 239**; "the corpus knew ~7x less than
its row count claimed."
[[sources/compounder-context-evidence]] five days later computes the feature budget on **raw row count**:
3,628 rows / 62 features = ~58.5 rows/feature, "far above the OF-7 floor" of 10.

**If the ~7x overlap ratio still holds, effective rows/feature is nearer 8-9 — below the floor.** The
later document does not mention uniqueness or ESS at all. **Never reconciled.**

### 2. Three round-trip cost numbers in simultaneous use — now four
Label floor assumes **0.50%**; the pre-trade gate is configured at **0.65%**; measurement says **0.86%**
with a DANGEROUS verdict. The labeler floors barriers using a cost **23% below** the gate's and **42%
below** measured. **No document reconciles this.** See [[concepts/cost-truth]].
*08-02 addition:* per-fill attribution (`scripts/cost_attribution.py`, n=215, post-purge) measures
the fee term at **0.667%** per round trip — a fourth number, closest to none of the three, and the
first computed from clean fills with fees separated from slippage
([[sources/session-20260802-digest]]). The 0.86% DANGEROUS input file was also within the
contamination window. Still unreconciled.

### 2b. Win rate 5.5% vs 57.5% — same book, same week
**5.5%** (200 windowed trades, payoff 0.409, PF 0.024) was computed by grouping fills on
`position_id` while one position appeared under **16 ids**; **57.5%** (n=215 per-fill, post-purge,
payoff 0.560) is the clean measurement — re-confirmed **57.1% / payoff 0.561** at n=217 after the
addendum's residual quarantine (`483f6727`, 637/637 audit-crossref CLEAN). The grouping method is refuted — **never group fills by
`position_id`; key on the fill pattern** — so the per-fill numbers stand. Consequence: the
identification-impossibility argument (PF 1 needs 70.97% win rate, LR 42, ~1.7 effective
positives) does not survive on its exact numbers, though its conclusion — the model is not the
lever — re-derives cleanly ([[concepts/payoff-asymmetry]]). Any document quoting 5.5%/0.409 must
carry this note.
*08-04:* the defect class is now **named**, with a third instance (a substring path filter
turning the deploy gate red — fixed `242568fb`): **substring matching where identity was
required** — `position_id`, round-number, paths. See [[concepts/location-invariant-tests]].

### 3. A live config knowingly failing its own harness gate
The deployed exit geometry **fails G1** when mirrored into the harness. It is held at KEEP on the
argument that the harness overstates the effect ([[comparisons/harness-vs-live-cost-stack]]), pending a
live verdict armed for 2026-07-25. **No document in the corpus records that verdict's outcome.**

### 4. The same behavior ruled expected and patched on the same day
The probe/manipulation-shade interaction is classified **"(c) expected per config"** in one 07-29
document and **patched as a defect at both sizer call sites** in another 07-29 document.

### 5. A cost verdict computed on a stale file
The DANGEROUS cost-truth verdict was computed from a file later found **stale (17 rows, ending ~12 days
earlier)**, with the real 216-row series living elsewhere. The doc's own caveat (underperforming subset
by construction) **understates** the problem.

### 6. Two payoff/breakeven derivations, both presented as "the" number — NOW THREE (2026-08-09)
`b_net 0.628 / breakeven 0.614` in one document; `b_net 0.44877 / breakeven 0.69024` "re-derived to
1e-12" in another. Different geometries — but neither cross-references the other, so they are trivially
conflatable.

**A THIRD arrived 2026-08-09** ([[sources/session-20260809-turing-test-hedge-verdict]] §1.2): the
Turing-test behavioural sweep reports **win rate 58.3% on a payoff ratio of 0.670** (breakeven at
that win rate is **~0.715**). Set beside the figure [[concepts/payoff-asymmetry]] is written on —
**0.561 observed vs 0.750 needed at a 57.1% win rate, n=217 post-quarantine** — the two describe
the same book with a **materially smaller shortfall** (0.670-vs-0.715 is nearly closed;
0.561-vs-0.750 is not).

⚠️ **The corpus size and window behind 58.3% / 0.670 were NOT STATED at filing** — a direct breach
of domain rule 1, recorded rather than papered over. Until the populations are reconciled:

> **0.561 / 0.750 at n=217 remains the citable pair. 58.3% / 0.670 is a CITATION HAZARD and must
> never be quoted as "the" payoff without its corpus.**

**Status: UNRESOLVED, and now three-way.** *What would close it:* state the corpus, window and
execution-era side for each of the three derivations, then retain one and label the others by
population.

### 7. Stated invariants vs audited reality
Exits starvable, latched faults lost on reboot, unregistered codes, two fail-open entry paths. Fully
enumerated in [[comparisons/stated-invariants-vs-audited-reality]].

### 17. The h432 realized ledger vs the recent-30 story — the panel's one unfinished item
`gate_stats` real_tot for `triple_barrier_h432` reads **6/11 net winners (54.5%)** — on a
**fully-net** fee basis (`main.py:1955-1971`) — while every lens and two judges repeated
"recent-30: wr 20%, PF 0.18, net −10.74, still losing." **Both cannot headline the same
book.** The 6/11 is the era-keyed realized ledger — the very instrument built for the h432
cohort. Different populations, fee bases and denominators are all candidate reconciliations;
**no judge adjudicated it** ([[sources/session-20260807-institutional-review]] §G). Until it
closes: display/quote **both**, with denominators declared. Owed item 37(e).

### 18. The fee ledger's $6.24 gap — RE-MEASURED 2026-08-09, still open, and now consequential
`fees_total` **382.28** (state) vs **376.04** (sum of `fills.csv` fees); the quarantined
08-01/02 fills carry **$7.21** — likely but not proven cause; **−$0.97 residual open**.
Declared by the panel as a condition; close or keep declaring it
([[sources/session-20260807-institutional-review]] §A.3).

**Re-summed at filing 2026-08-09** ([[sources/session-20260809-unbiased-economics]] §4):
`fills.csv` `fees_delta_usd` = **376.35** across **1,019 rows** vs `fees_paid_total` = **382.59**
— **gap 6.24 (1.6%)**. Both sides grew by ~0.31; **the gap is stable, not drifting**, which
weakens the quarantine explanation (a fixed historical cause should leave a fixed gap — it did —
but then the residual −0.97 should also be fixed, and it is unexplained either way).

> **Why this is no longer bookkeeping.** Every offline cost analysis built on `fills.csv` reads
> **optimistic by 1.6%** — and the proposed corpus `fees_usd` backfill (owed item **50**) sources
> **from exactly this file**. Filing a 1.6%-short fee column into the training corpus would bake
> the gap into the learner's view of its own costs. **Close it or declare it before the
> backfill**, not after.

### 21. "The corpus is data-starved" vs "there is no measured gross edge" — the framing contradiction
The corpus's standing account of its own performance is **cold-start / data-starved**: the
battery's learning curve reads **CLIMBING** (`delta_auc=+0.112`, *"corpus growth is the
highest-leverage learning input"*), the DoF ledger is **CLOSED**, and the exploration spend is
**tuition** ([[concepts/dof-budget]], [[concepts/priced-bleed]],
[[entities/overfit-check]]).

**Measured 2026-08-09** ([[sources/session-20260809-unbiased-economics]]), over ~250 closed
positions / 438 entry fills: **gross P&L before ANY fees = −11.66** (~−$0.05/trade,
indistinguishable from zero) against **382.59** of fees — **fees 32.8x |gross|, 100% of the
−394.25 all-in loss is costs.** Corroborated by two instruments sharing no mechanism with the
curve: **OOF AUC 0.43–0.48** (at/below chance) and champion **Brier 0.24728 vs 0.25** for a coin.

**Both cannot headline the same book.** "Data-starved" predicts **gross edge > 0** that is merely
hard to *select on*; the measurement says **there is no gross edge to be starved of**.

**Status: the framing side is FALSIFIED AS A COMPLETE ACCOUNT; the readings on both sides
stand.** The learning curve genuinely climbs; the gross mean is genuinely ~0. What is
contradictory is not the two measurements but the **inference** that has been drawn from the
first — and it survived because the vocabulary has no failure state
([[concepts/unfalsifiable-explanation]]).

**Why it is filed as UNRESOLVED rather than closed:** the *complete* account is not yet known.
"Gross edge ≤ 0 for this strategy as configured" is consistent with the data, but the decisive
disambiguation — **is there gross edge in ANY subpopulation** (asset / regime / horizon / signal
strength)? — **cannot be computed**, because `signal_history.csv` carries `net_pnl_usd` and no
gross and no per-row fee column ([[synthesis/owed-measurements]] item **50**). *Closes on* item
50 landing plus a gross-edge-by-subpopulation read; **until then quote BOTH, with the
falsifier attached.**

⚠️ **Self-flagged.** This entry was produced by the agent that authored the framing it
contradicts — twice in one session, including once **into this wiki**
([[sources/session-20260808-night-staleness-overfit]], corrected in place). Recorded here so the
correction is not mistaken for a position the corpus always held.

### 22. The go/no-go tool's verdict vs the tool's own method — the corpus has cited the wrong branch — **RESOLVED 2026-08-09 (`415af0f9`); left in place because the RETRACTION it carries is permanent**
`scripts/breakeven_test.py` exists to answer **one** question: *is there gross expectancy?* It
contains **two hard-coded verdict branches** and prints whichever the median gross selects.

Because `:126` counts only `purpose == "entry"` as the opening leg, **all 159 complete hedge round
trips are discarded** (as *"partial or malformed"* — none are malformed), and the median gross
reads **+0.0505%**. Re-running the tool's own accumulation with `purpose in {entry, hedge}`:
**394 closed / 6 skipped, median gross −0.0303%.**

| | printed |
|---|---|
| **shipped** (`:214-230`) | *"This is NOT 'no edge' … that is exit geometry … **fixable without touching the signal**"* |
| **corrected** (`:231-241`) | *"**GROSS EXPECTANCY IS NEGATIVE** … no execution change, holding period, gate, filter or model creates expectancy that is not in the entries."* |

**The contradiction is internal to one tool:** its **method** says one thing and its **output**
says the opposite, and the corpus has been quoting the output.

~~**Status: UNRESOLVED until the ~10-line fix lands and the tool is re-run**~~
**RESOLVED 2026-08-09 — SHIPPED as `415af0f9`** ([[synthesis/owed-measurements]] item 53).
**Consequence for this wiki:** any page citing the *"this is exit geometry, fixable without
touching the signal"* framing **from this tool** is citing the wrong branch, and that retraction
**stands permanently** — the tool no longer produces the line. Note it is **not** the only route
to that framing — the 08-02 bracket grid reached the same conclusion by a different method and is
unaffected ([[concepts/payoff-asymmetry]]).

**Which way it pointed:** the corrected branch **agrees** with the two independent gross
measurements (state identity **−11.66**, full-book reconstruction **−13.01**).
([[sources/session-20260809-adversarial-audits]] §4.1)

> **How it resolved, with two corrections to this entry's own text**
> ([[sources/session-20260809-turing-test-hedge-verdict]] §5):
>
> 1. **It was not a "~10-line fix" in one file — it was FIVE files.** `breakeven_test`,
>    `cost_attribution`, `cost_truth_report`, `geometry_search`, `random_entry_control` all
>    counted only `purpose == "entry"`. This entry underestimated the **blast radius**, not the
>    fix. *The estimate itself was a self-flattering number* ([[concepts/self-flattery-gradient]]).
> 2. **The shipped median gross is −0.0305%, not −0.0303%.** A 0.0002pp difference between the
>    audit's re-implementation and the shipped tool. Recorded rather than smoothed (domain rule
>    2); **−0.0305%** is the citable figure.
>
> **Residual, still open:** the **by-reason skip counter** did not ship. **6 skips remain
> un-itemised**, so *"partial"* and *"deliberately excluded"* can still share a bucket
> ([[concepts/uncounted-exclusion]]). Carried as **owed 53-residual**.

### 23. Three derivations of one word — "drawdown" reports one quantity and fires on another
Both drawdown gauges (command board panel id 23; problem/solution board panel id 23) plot

```
drawdown_pct = (start − cash − savings) / start        # start-to-now, CASH-ONLY
```

while **the 15% hard-stop flatten and the throttle both read `drawdown_mtm_pct`** (peak-to-now,
mark-to-market). **Reproduced on live code:** a book **−20% on marks** fires
`hard_stop_triggered` (*"20.00% >= 15%"*) **while the gauge reads 0.0, FULL GREEN.** The inverse
is already pinned at `tests/test_audit_config_risk.py:281-288` — a **winning** account pegs the
same gauge at **15.0, red**.

**Neither quantity is wrong; the contradiction is that they share a NAME on the operator's
screen.** `runner.py:984` computes the MTM figure and **discards it as a local**; `gc_pusher`
carries only the cash-only one; **no board references the MTM series at all.**

**Status: UNRESOLVED, decision-grade** ([[synthesis/owed-measurements]] item 55). *Closes on*
exporting the MTM series, repointing both gauges, and **retitling the survivor** so the two
quantities keep two names. **This is the `decide` rung of [[concepts/two-paths-one-quantity]]:**
a divergence that is merely reported is cosmetic; one that a **flatten fires on** is not.
([[sources/session-20260809-adversarial-audits]] §3)

### 24. The mixed-sample refusal exists in the ML lane and not in the P&L lane
**`overfit_check.py:1031-1034` refuses to grade DSR on a mixed probe/conviction sample** — the
codebase's own statement that pooling two populations that differ by design produces a number
about neither. **`performance.overall` does exactly that**, count-weighted, and publishes the
result as the headline expectancy: **probe n=182 −0.1636**, **conviction n=17 −1.5840**,
**reported −0.2838** (a **5.6x** understatement of the conviction population).

**Status: UNRESOLVED as a system property, not as a disagreement of fact.** Both code sites are
individually defensible; what contradicts is **the project's stated statistical discipline vs its
published performance number**. *Closes on* [[synthesis/owed-measurements]] item 54.

> **The general form is worth naming:** *"we know better in one place"* is not *"the system knows
> better."* A third sibling of [[concepts/adoption-is-not-enforcement]] —
> [[concepts/pooled-populations]].

### 25. "The double-count is disposed by design, a conservative floor" (08-08) vs "the double-count was the whole defect, 1.88x" (08-10) — **RESOLVED 2026-08-10; kept because the RETRACTION is the content**

**The corpus contradicted itself about its own fill simulator on three consecutive days.**

| date | page | claim |
|---|---|---|
| **08-07** | [[sources/session-20260807-fleet-findings]] §1 | *"the calibrated trade-through frequency is **spent twice**"* — **correct** |
| **08-08** | [[sources/session-20260808-morning-batch]] §1 | *"(b) **disposed by design**: `_sim_maker_cross` = genuine trade-through, the calibrated hazard = a **conservative floor** on top"* — **wrong** |
| **08-10** | [[sources/session-20260810-fill-double-count]] | `2f−f² = 21.96%` vs an `f = 11.66%` target, ledger **22.30%**, **1.88x at the touch** — **08-07 was right** |

**RESOLVED in favour of 08-07.** The 08-08 framing fails on one structural fact: the hazard
**only ever ran inside `if book:`**, so it modelled nothing a snapshot could already show — it
was **purely additive to an observed cross**, not a floor under an unobserved one. And
`invert_base_prob` had already solved `sf_base` so **the hazard alone reproduces `f`**, which is
the very frequency the deterministic path fires on. Fixed by `aeeaae36`; **execution-era boundary
#4**.

> **Left in the register rather than filed away, because the failure mode is reusable.** This was
> not two documents disagreeing about a measurement — **the measurement never changed.** It was a
> correct finding **lost at the DISPOSITION step**, in a session that was otherwise unusually
> careful (it caught its own test-count error, 8 claimed vs 7 collected, in the same filing). The
> scrutiny went to the **numbers** and skipped the **adjudication**, and the adjudication was
> written next to a genuine win.
>
> **Rule extracted:** *a disposition that closes a docket item deserves the same adversarial pass
> as the finding that opened it* — and **more** when it is written in the same session as a fix
> the author is pleased with ([[concepts/self-flattery-gradient]],
> [[concepts/adversarial-verification]]). **Cost: two days, with a 1.88x bias live throughout.**

## RESOLVED, but the resolution must travel with the claim

### 8. "The 2026-07-26 baseline" is ambiguous
The same day produced both **5 passed / 3 failed** (4,692 rows) and **4 passed / 4 failed** (4,642 rows).
Not a contradiction — different corpora. **Always qualify a baseline by row count.**

### 9. Live rows never excludable vs excluded
An explicit, acknowledged **override**, not an accident — all measured live rows were themselves
old-era. The two filters remain distinct mechanisms.

### 10. "Excluding old eras would collapse the corpus" vs shipping exactly that
Defused by auto-arming only at a threshold equal to the evidence floor. Borne out: activation produced
rows/feature of 10.7 against a floor of 10 — **passing, but only barely.**

### 11. "Gap closed" (07-28) vs "gap fully open" (07-29, 07-31)
The closure was declared by design and **not verified on the live box**. Four days later the count was
still zero. See [[synthesis/learning-pipeline-arc]].

### 12. Barrier reachability — retracted in-document
"The barriers are unreachable by this strategy" was **retracted** as apples-to-oranges. Candidate rows
reach PT 17.9% / SL 34.5% / TIME 47.5%. **The barriers are reachable.**

### 13. A commit credited with a fix it did not make
A give-back cost-floor commit was recorded as having "unblocked the label stream." **It did not** — it
fixed a real but separate defect. Corrected in the record.

### 14. Three successive binding-constraint headlines in nine days
"Plain signal underperformance" (07-24) → "cost is the binding constraint, 82% of a sigma" (08-01)
→ "entry-edge problem, −0.34%/trade at zero fees" (08-02 interim) → **payoff asymmetry** (08-02,
standing). The first three were each computed on or alongside the contaminated `fills.csv`; the
last is post-purge and re-runnable — and it **survived the addendum's residual quarantine**
(18 more fixture positions / 72 rows removed at `483f6727`; post-quarantine n=217, win 57.1%,
payoff 0.561 vs 0.750 needed, materially unchanged). Resolution travels with the claim: cite
[[concepts/payoff-asymmetry]] whenever any of the earlier three appears.

### 15. "Tail risk" refuted — one fabricated trade counted 16 times
The heavy-left-tail reading of the loss distribution came entirely from one fixture trade appearing
under 16 `position_id`s. Post-purge: min −2.38%, max +1.87%, and dropping the worst 5% moves the
mean only to +0.031%. The distribution is near-symmetric; the asymmetry is in the *averages*
(loser 1.8x winner), not the tails. ([[sources/session-20260802-digest]])

### 16. "42.9% chance of hitting PT" vs a ~31% label rate — different quantities
The funnel doc's **42.9%** is the geometric first-touch null `sl/(pt+sl) = 6/14` from the 8:6
barrier config, and pooled first-touch **P(PT) measures 0.418 ≈ that null**. The **label rate
≈ 0.31** is a *different quantity*: **25.1% of winning PT touches fail the cost stack and label
0** — the cost wedge ([[concepts/cost-to-volatility-ratio]]). Reconciled 2026-08-02 (late
session), but a standing **citation hazard**: quoting 42.9% as an expected *label* rate conflates
touch space with label space. ([[sources/session-20260802-digest]] second addendum)
Proof the hazard is live: `geometry_search`'s own section 2 made exactly this conflation
(label-space vs touch-space) and was **corrected before commit** — the `663434ae` commit message
records the wrong-quantity mistake explicitly. The hazard bit the tool that quantified it.

### 19. "Two 147-lap hedge incidents" — ONE ledger event, double-filed under two clocks
The corpus filed a "08-06 20:09–20:34 thrash" ([[sources/session-20260806-hedge-thrash]],
−$303) and a "08-07 01:09–01:34Z incident #2, hours after #1's fix"
([[sources/session-20260807-hedge-churn-guards]], −$318) as **separate 147-lap events**.
**Resolved 2026-08-07** ([[sources/session-20260807-institutional-review]] §B, filing-session
measurement on a panel record note): `fills.csv` holds **159 lifetime hedge fills, all
08-07 UTC**; equity read 4,933.68 at 08-06 23:59:50Z; 20:09–20:34 **local (UTC−5)** ≡
01:09–01:34**Z** — the same wall-clock window, the same laps, tallied over slightly different
envelopes. **There was one 147-lap event plus a 12-lap warm-correlation residual tail
(01:56Z–11:35Z)**; the fix timeline is D3 committed 01:53Z (after the event ended), deployed
02:08Z; D4 deployed 19:04Z. The resolution must travel with every citation of "the two
churns": the corpus does not contain two 147-lap incidents, and any "incident #2 after #1's
fix" framing is refuted. What remains true: **two distinct MECHANISMS** (wrong-pair/cold-0.0;
open-variable vs unwind-variable with no deadband), each needing its own fix. Root cause of
the double-filing: **rendering epoch timestamps in two clock conventions without stamping the
zone** — a sibling of "qualify a baseline by row count"; qualify every incident window by
clock.

**RE-MEASURED 2026-08-09, and the resolution held on first contact**
([[sources/session-20260809-turing-test-hedge-verdict]] §2). A fresh sweep of the ledger returned
the window **2026-08-07 01:09–01:34Z**, **147 ADA/USD hedge round trips, all 2-leg**, **59 held at
exactly 5.000s**, **$36,210** notional, gross **−$12.77**, fees **$289.73** = **77.3% of ALL
lifetime fees** (denominator **$374.96**), **no recurrence in 56.5h**. The filing agent checked
this entry **before** writing and correctly declined to open a third incident page — **this entry
did its job.**

⚠️ **Two denominators now attach to this event and must not be merged silently:**
- **$289.73** = the **147 matched 2-leg round trips**.
- **$296.93** = [[sources/session-20260807-hedge-churn-guards]]'s figure for **01:09:45–01:34:19Z**
  over **290 fills** (open-leg $149.83 + exit-leg $147.10); the wider 00:50–02:00Z window holds
  **296** fills.
- The **$7.20** gap is **consistent with** unmatched or out-of-window legs falling outside the
  round-trip population — **an inference, not a measurement.** *What would close it:* itemise the
  fills in the wider window that are excluded from the 147 matched pairs.
- Likewise the **77.3%** share uses the **$374.96** corrected `breakeven_test` lifetime-fee total;
  against the **$382.59** state-identity total it reads **75.7%**. **Quote the share with its
  denominator or not at all** ([[concepts/ratio-aggregation-bias]]).

### 20. "The −50.0bps signature is benign" (08-03) vs "the −50bps fills are sim-manufactured" (08-07)
[[entities/long-book]] carries the 08-03 classification: the exact −50.0bps slip entries are
**benign by design** (the resting offset, order_ids audit-verified, not fixtures).
[[sources/session-20260807-fleet-findings]] §1 shows the same fills are **near-certain sim
gifts**: the per-poll fill hazard was calibrated at n_bar=5 (25s orders) and compounds to
**≈1.0 over the long book's 6h TTL**, on a double-counted trade-through predicate with no depth
constraint. **Resolved 2026-08-07 — both true, different layers.** 08-03 adjudicated
**provenance** (are these orders real? yes); 08-07 adjudicated **evidential weight** (does the
fill event mean anything about fill quality? no — its probability was ~1 by construction).
The resolution must travel with the claim: cite the signature as *benign provenance, skewed
evidence* — never as "verified benign" full stop. Fix owed as item 40; the two questions
separate cleanly on the [[concepts/paper-real-boundary]].

## CITATION HAZARDS (self-flagged)
- **"Fees are Nx the edge" is meaningless without its SPACE — 368x and 32.8x are both correct and
  are NOT a contradiction** (2026-08-09). **368x** is **percent space, per trade**: round-trip cost
  **0.71%** over per-trade gross edge **−0.0019%**
  ([[sources/session-20260809-turing-test-hedge-verdict]] §1.3). **32.8x** is **dollar space, whole
  book**: **382.59** fees over **−11.66** gross ([[sources/session-20260809-unbiased-economics]]).
  Different numerator *and* different denominator; neither refutes the other, and an unqualified
  "fees are Nx the edge" invites a reader to treat one as a correction of the other. **Always name
  the space.** ([[concepts/ratio-aggregation-bias]])
- **"58.3% win rate on a 0.670 payoff" has no stated corpus** — see entry **6**; it is a *third*
  payoff derivation, not a replacement for **0.561 / 0.750 at n=217**.
- **"Battery green" on a dev checkout does not certify the deploy gate's environment** — a
  location-variant test passes everywhere *except* the gate's outputs-nested worktree, and it
  stays invisible until the **first externally-pushed commit**, because a single-writer repo
  never exercises its own gate (local-ahead commits skip the battery). Green in every normal
  checkout, red exactly where deploys are decided (2026-08-04, fixed `242568fb` —
  [[sources/session-20260804-deploy-gate]], [[concepts/location-invariant-tests]],
  [[entities/auto-update]]). Corollary: another environment's "already done on your box" claim
  (the session-start-hook migration) is a claim about *its* environment until verified here.
- `retrain_history.jsonl` contamination counts read **305/306 fixtures** (measured 07-31) and
  **158/165 clean** (assessed 08-02) — **different snapshots; the counts are not comparable.**
  Always qualify by date. Neither number invalidates the other; no document reconciles the record
  count change. ([[sources/session-20260802-digest]] addendum)
- The pre-quarantine per-fill numbers (n=215, win 57.5%, payoff 0.560 vs 0.740) and the
  post-quarantine numbers (n=217, win 57.1%, payoff 0.561 vs 0.750) are both clean-era
  measurements on different ledger states; **quote the post-quarantine set**, and re-run rather
  than quote — `fills.csv` grows live.
- **"87% of trades reached positive MFE" must carry the random-entry-control result** — it is
  diffusion (real entries' mean MFE percentile 0.516 [0.439, 0.594] vs 200 matched controls each,
  n=51, commit `8062f46a`); never cite it as evidence of timing skill.
- **"The lever is exit geometry" must carry the geometry-search bound** — the pre-registered
  48-combo bracket grid (Bonferroni z = 3.26, 222 real entries, config fees; commit `663434ae`,
  battery green) found **no combination with positive expectancy** (best h=432 tp=1% sl=2%:
  mean −0.400%, lower bound −1.124%). Exit design minimizes bleed; it does not create edge.
- **The BTC h=48/96 above-null cells carry a multiple-testing caveat** — two cells out of a
  per-asset ladder; do not cite them as a demonstrated per-asset edge.
- **42.9% is a touch-space null, not a label rate** — see #16 above.
- A monotone-constraint result **must not** be cited as "measured against the ladder predecessor and
  lost" — the measured pairing confounds architecture with hyperparameters, and the clean comparison was
  never run.
- **"Do not quote the Gaussian touch probability as a prediction"** — observed touch rates run ~50x the
  Gaussian implication; only the *ratio* comparisons are safe.
- Live-label counts read 240, 241, 242, 251, 253 and 256 across documents — **different snapshots**, not
  a discrepancy, but never the same number twice.
- **Static metric-name scans over `gc_pusher` produce phantom ghosts** — a naive regex scan
  reports 92 "displayed-but-not-emitted" metrics and 16 "non-snake_case" names, **all
  dynamic-name artifacts** of f-string metric construction; the repo's own source-matching
  test (**ghosts = 0**, green) is the authority. Never cite raw emitted/displayed set
  differences without resolving dynamic names. (2026-08-05,
  [[sources/telemetry-stack-audit]], [[concepts/iron-law-of-debugging]])
- ~~**"Hash-chained" is true of `audit.jsonl` and NOT of `ml/registry.py`'s ledger** — the
  registry's `verify()` compares **one unauthenticated sha256 from the last matching row**, so
  edits, deletions and reordering are undetectable, and deleting `registry.jsonl` downgrades every
  load to "unknown provenance" which `reload()` **accepts**. The corpus's decisive provenance
  argument (`order_id` membership in the hash-chained audit trail) **does not transfer** to the
  model registry on the strength of the shared adjective.~~ **RESOLVED same day, commit
  `4799bfc7`** — the registry is now genuinely chained (`prev` + `seq` + content hash, the **same
  construction as `core/audit.py`**), `verify_chain()` walks the links, and **a broken chain FAILS
  the load gate instead of authorizing it**; 9 tests incl. a rewritten row minting provenance for a
  swapped artifact. The phrase is now safe to extend. **The general hazard it taught survives the
  fix: a shared adjective is not a shared property — check the construction, not the vocabulary.**
  (2026-08-05 evening, [[sources/session-20260805-evening]], [[synthesis/owed-measurements]] item
  30a, [[comparisons/stated-invariants-vs-audited-reality]])
- **The monitor's "15-loss streak kills an honest model" example was WRONG and must not be
  requoted** — owed item 30b originally put an all-loss 15-close window at "**~4-9%** at this
  corpus's base rates". Against a **promised 0.30** it is `0.70^15 ≈ **0.5%**`, so **convicting is
  correct** on that example. The two underlying defects were real and are fixed (a Wilson guard
  that could never veto; an in-window-oracle baseline). Cite the **mechanism** — an honest ~0.18
  promise survives an unlucky streak, and the same shortfall is harder to indict at small n — never
  the retracted worked example. (2026-08-05 late evening,
  [[sources/session-20260805-evening]], [[entities/ml-governor]])
- **The tangible-value ladder is a TENDENCY, not a law — never cite the gradient as a rule** —
  its own first live reading was `flight_to_quality` at **+2.00** (PAXG +4.7% / BTC +0.8% /
  ETH +2.1% / ALT −1.3% over 24h) **with `BTC-ETH` NEGATIVE in the same reading**. Cite the
  per-rung detail, not the state label. The falsifiable vol-ordering prediction is the part that
  was measured and held (PAXG 0.075% < BTC 0.093% < ETH 0.120% ~ SUI 0.116% < ARB 0.160%); the
  directional claim about capital flow has **no track record against realized outcomes yet**, and
  the instrument is report-only until it does. (2026-08-05,
  [[synthesis/tangible-value-doctrine]])
- **"The dark metrics are boarded" is not "the dark metrics are visible"** — the newly-boarded
  `gate_divergence` panel shipped with a **bare `max()`** over a per-gate labeled series, plotting
  a flatline over the exact trend it exists to show; caught one commit later (`46cdc19a`). When
  citing owed item 26 as closed, cite the **fixed** panel (`max by (gate)`), and remember the
  general form: emitted ≠ boarded ≠ displayed. (2026-08-05 evening,
  [[entities/observability-sidecars]])
- **NEVER cite `bracket_divergence_rate = 1.0000` as evidence that labels and trades agree** —
  it was a **tautology**. A `tb_time` record's counterfactual **IS its realized value**, so its
  delta is **0 by construction** and it always "agrees"; **33 of 35 records over the instrument's
  entire production lifetime (94.3%) were `tb_time`**, making the gauge **94% arithmetically
  incapable of reading anything else**. Any statement of labeled-vs-traded bracket agreement
  sourced from a **pre-`ee0ac4ad`** reading is **definitional, not empirical**. Post-fix, cite
  `agree_rate` **only alongside `n_priced`** — the rate is computed over the priced subset
  (`tb_pt`/`tb_sl`) and is **`None` until one exists**. **As of the fix, the honest reading of
  this instrument is "not yet measured," not "in agreement."** (2026-08-06,
  [[concepts/tautological-instrument]], [[sources/session-20260806-geometry-filing]])
- **NO corpus row written before `ee0ac4ad` contains bracket geometry in its `disp` column** —
  the field was capped at **40 chars** against a **113-char** SZ-023 disposition, so it ended at
  `'(net break'`. Measured: **2,614 SZ-023 rows** lost `[bracket pt=..% sl=..% b=..]`, **1,052
  SZ-030 rows** lost their net breakeven and `b_net`, and **ZERO of 9,692 rows** retained a
  bracket payload. **`scripts/gate_efficacy_report.py` regex-scrapes this exact field** — so any
  gate-efficacy conclusion drawn from the veto-reason column on the historical corpus was drawn
  from a **truncated** field, and **no amount of re-running recovers it: the bytes were never
  written.** Only rows written **after** the fix carry the geometry. (2026-08-06,
  [[entities/historystore]], [[sources/session-20260806-geometry-filing]])
- **A pre-`ee0ac4ad` "TAMPERED" verdict on `audit.jsonl` may be crash damage, not tampering** —
  an `OSError` part-way through `f.write` left orphan bytes while `_synced` stayed `True`, so the
  next append welded on and `verify_chain` classified the result **`torn=False` → `tamper=True`,
  permanently**. The classification is trustworthy going forward (the fix re-arms `_adopt_tail`),
  but a **historical** tamper verdict must be qualified by this window before it is cited as
  evidence of interference. Note the direction of the error: this is the corpus's **provenance
  spine** ([[entities/reason-code-registry]]) producing a **false positive against itself**.
  (2026-08-06, [[comparisons/stated-invariants-vs-audited-reality]],
  [[concepts/torn-append-fusion]])
- **`asset_live_counts` / `regime_live_count` readings taken after a corpus schema rotation and
  before `ee0ac4ad` are unreliable** — the rotation stamped the new file's `(mtime_ns, size)` key
  onto counts describing the **old** corpus, and the cache then **refused to re-scan**.
  **Reproduced as a 6x asset overcount.** These are **not telemetry**: `asset_live_counts` is
  **`n_a` in SPB-R scarcity pricing (position SIZING)** and `regime_live_count` **gates the
  regime-coverage admission hold** — so the hazard reaches sizing and admission decisions, not
  just panels. (2026-08-06, [[entities/historystore]])
- **The desk's "NET P&L (ALL TIME)" tile is NOT the all-time P&L — never quote −56.91 as
  lifetime** — the tile renders `liquiditybot_perf_net_usd`, a **rolling last-200 NON-HEDGE
  window** (full and truncating since 07-22; hedge exclusion `main.py:1588`), under a panel
  description (*"Cumulative realized P&L across every closed trade"*) that is **false on two
  axes**. The all-time number is the monotonic, unexported `realized_pnl_total` (**−208.22** at
  verification, 3.7x the tile). Every displayed P&L figure requires a **named-series
  translation** before belief: period counters (daily/weekly/monthly, UTC resets) ≠ the rolling
  perf window ≠ the monotonic total — and **entry/hedge OPEN-leg fees are in NONE of them**
  (cash-only via `record_entry_fee`; visible only in equity and `fees_total` — the −318
  equity-vs-daily-−164 gap is that channel, not a bucketing error). Owed items 36(a)/(b).
  (2026-08-07, [[sources/session-20260807-pnl-reconciliation]])
- **Never attribute the desk's 8.0% win rate / 57-loss streak to the hedge-churn incidents** —
  the performance ring **excludes hedges by construction** and contains **ZERO churn-window
  entries** (verified against the persisted ring; nearest neighbors 08-06 21:22Z / 08-07
  06:11Z). The panel reading is **"not an incident artifact"** — ~~"the organic picture"~~ was
  judge-corrected as a provenance overreach — and the pre-incident baseline was *worse* (7.07%
  win, PF 0.026 over the 198 prior trades); the only two post-incident trades were wins.
  Standing caveat that must travel with the 8.0%: **66.5% of the ring is a 07-22/23 cluster of
  unadjudicated provenance** (owed 36(c)); the recent-30 window reads wr 20%, PF 0.18, net
  −10.74 — better, still losing — and **contradicts the era realized ledger's 6/11 until
  adjudicated (#17)**. (2026-08-07, panel-amended,
  [[sources/session-20260807-pnl-reconciliation]],
  [[sources/session-20260807-institutional-review]])
- **The churn was NOT "100% fees / gross 0.00"** — position-paired recomputation: **gross
  −13.37 on 149 laps, fees 301.31** (~95.7% fees, ~4.3% crossing cost, mean slip 1.87 bps).
  Cite the paired numbers; the canonical window is **01:09:00–01:34:59Z = 294 fills = 147
  laps**, all other counts are envelope variants. (2026-08-07,
  [[sources/session-20260807-institutional-review]] §A)
- **NEVER cite the fee constants as "conservative" or quote "Kraken's published 16/26"** —
  triple-confirmed 2026-08-07: **25/40 bps matches no row of Kraken's current schedule**
  (Tier 1 40/80 … Tier 5 ~15/30). For a fresh $5k account the constants **understate** cost
  ~1.6–2x (the dangerous direction) and the paper drawdown is a **floor**. The correction is
  **sequenced post-h432** (label-geometry coupling, `ml/labeling.py:45-52`) — do not
  re-propose an immediate constant change; and never cite the $97k 30-day notional as a
  Tier-5 argument (**77.6% of it is churn flow**). ([[concepts/cost-truth]],
  [[sources/session-20260807-institutional-review]] §C)
- **No markout number from this book is venue truth, and the ETH/BTC "quoter edge" is
  simulator physics** — DRY_RUN passive fills are granted by an unconditioned RNG **at the
  limit price** (no trade-through condition, `order_manager.py:1237-1260`), harvesting the
  resting distance as phantom favorable markout; signature: flat across horizons (BTC
  +11.21/+11.26/+11.28). The same artifact voids ARB's −14/−18 "red flag" (~5 events with
  duplicates). Markout conclusions are **sim-conditioned** —
  [[concepts/paper-real-boundary]]. (2026-08-07,
  [[sources/session-20260807-institutional-review]] §F)
- **"Champion Brier 0.2478 vs constant-baseline ≈0.164" carries a population-splice caveat** —
  the deploy-time badge and the cross-era monitor pool are different populations
  (Judge 4, two judges with evidence). The direction (champion ≈ coin-flip, no demonstrated
  skill) stands; the exact spread does not survive as a single-population comparison. Cite
  "no skill demonstrated," not the subtraction. (2026-08-07,
  [[sources/session-20260807-institutional-review]])
- **Qualify every incident window by CLOCK (zone-stamp it)** — the one-event double-filing
  (#19) was manufactured entirely by rendering the same epochs in local time and UTC. A
  window without a zone is not a window. (2026-08-07)
- **NEVER cite any corpus-derived number measured between 2026-08-08 20:01:46 and the
  2026-08-09 repair** — the `label_era` corruption pooled **three incompatible label
  definitions** (96/24/432-bar) into one bucket, so the loaded corpus in that window was
  **9,746 rows of mixed label meaning**, not a corpus. **Specifically embargoed:** the
  deployed `gbt` champion's OOF Brier **0.1537** (item 47), the 08-08-night OF-1/OF-7
  readings (train_auc ~0.70–0.77 / oof ~0.51, `dead_frac` 0.97 — struck on
  [[sources/session-20260808-night-staleness-overfit]] §2), and any `live_clean` or
  row-count figure printed in that window. The clean replacements are on
  [[sources/session-20260809-corpus-corruption]] §8. Same discipline as the pre-boundary
  fill statistics — **a number is embargoed by the corpus that produced it, not by whether
  it looks wrong.** (2026-08-09)
- **"There is a 60-row synthetic→live threshold in `overfit_check`" is FALSE and must not be
  re-filed** — the predicate is **`len(X) >= len(FEATURE_NAMES)*10` = 640** over **LOADED**
  rows (candidate + live, post-filter); the flat `60` was **deleted 2026-07-11 by
  `7486ab29`**. This claim reached the wiki once, on 2026-08-08, and was corrected in place
  the next day. Its source was the script's own output calling total rows "live rows" — both
  strings now fixed ([[synthesis/documentation-drift-register]]). **Killing citation:**
  `scripts/overfit_check.py:180-182, :207`. (2026-08-09)
- **PARTIALLY RESOLVED — the champion gate is comparing scores across incommensurable
  corpora** — challenger OOF Brier **0.2714** (clean 692-row corpus) vs champion **0.1537**
  (corrupted pooled 9,708-row corpus). Both numbers are internally valid; **neither is
  comparable to the other**, and the gate has no field that would let it know. Consequence:
  the bug-promoted `gbt` was **WEDGED in place**. **Deliberately not overridden** — and that
  restraint is what resolved it. ~~resolution requires a conscious operator re-baseline
  (item 47)~~
  **THE INSTANCE RESOLVED ITSELF 2026-08-09 02:56:04** without any re-baseline: as the corpus
  grew to **701** rows the **ML-083 era-orphan branch** fired (watermark **9,708** > matrix
  **701**), declared the badge **unfalsifiable**, **set it aside**, and deployed `logistic` at
  **0.24728** against the cold-start bar
  ([[sources/session-20260809-gate-policy-and-self-heal]] §1, [[concepts/ghost-badge]]).
  **THE CONTRADICTION ITSELF REMAINS OPEN**, and this resolution sharpens rather than closes
  it: **a stored watermark records a score and not the corpus that produced it**, so
  *"champion beats challenger"* is an unfalsifiable claim whenever the corpus has changed
  underneath it. ML-083 caught this case by a **row-count proxy** — it fired only because the
  corrupt population was **larger** than the clean matrix. **A corrupt population that
  happened to be SMALLER would compare "successfully" and pass unremarked.** *What would
  close it:* provenance (corpus revision, era set, row count) on the champion record.
  (2026-08-09, instance closed / **class OPEN**)

  ***THE CLASS FIRED AGAIN, IN THE OTHER DIRECTION — 2026-08-14, STILL OPEN.*** The entry
  above worried about the *silent* case: a divergent population that is SMALLER would compare
  "successfully" and pass unremarked. What happened instead is the loud case with no ceiling.
  ML-083's row-count proxy fired correctly at **10,217 vs 211 (a 48x orphan ratio, against the
  3.2x its own comment records it was built for)** — and, *having fired*, set the badge aside
  and applied the bare cold-start bar `Brier < 0.25`. A logistic trained on **2.0%** of the
  incumbent's data deployed at 0.21887 while its own `family_brier` was **0.33105 — worse than
  a constant p=0.5 predictor.** So the proxy is not the weak link; **the unlock it triggers has
  no floor.** The register's own framing is what generalizes: an unfalsifiable claim is not made
  falsifiable by refusing to evaluate it — refusing merely moves the unfalsifiability from the
  comparison into the *bypass*. *Partial progress toward the stated closing condition:*
  `61c3b5c1` now writes a `deployed` lifecycle row carrying **rows, family and oof_brier** (the
  registry previously held 134 `registered` events and ZERO `deployed`), which is some of the
  provenance this entry asks for — **corpus revision and era set are still absent.**
  ([[sources/session-20260814-cohort-instruments]] Finding 2, [[concepts/deploy-deadlock]]
  §third polarity)

- **`gate_efficacy_report` IS NOT MEASURING GATE SELECTIVITY — its intervals are ~8x too
  narrow (2026-08-15, class OPEN).** Measured on `outputs/signal_history.csv`, whole corpus,
  with the same average-uniqueness algorithm `scripts/gate_truth_report.py` has used since
  2026-07-29: **n = 10,567 spans, effective n = 162.2, mean uniqueness = 0.0154, SE inflation
  ×8.07.** Every Wilson interval in that report's ~29-row per-rule table is computed at
  **nominal n**. The `ANTI-SELECTIVE` flags, the per-rule CIs and the headline separation are
  therefore artifacts of counting rows as though they were independent facts.
  *What this retires, both in circulation:* **"the gate selects against itself, −2.3%"** — which
  is ALSO era-confounded, since `gate_efficacy_report.py:105` bins on disposition only and never
  reads `label_era` (0 occurrences in the file), leaving a baseline arm that is 84.1% `legacy`
  with zero `triple_barrier` against an admitted arm with zero `legacy`; and **"`SZ-023: p 0.28
  below bar 0.55` is ANTI-SELECTIVE +17.5%"**, whose intervals overlap once deflated.
  *Era-matched, re-derived:* `exit_sim` **−1.57pp** (31/247 vs 351/2485) · `triple_barrier`
  **−18.71pp** (3/46 vs 1333/5282) · `h432` −7.90pp at n=6. **The eras disagree by an order of
  magnitude, so there is no single separation number** — the defect is not a wrong value, it is
  that a pooled statistic is computed at all, in the one report that grades the gate
  ([[concepts/pooled-populations]]).
  *Why OPEN rather than resolved:* the fix is not a corrected figure. It is per-era rows plus a
  refusal to pool when era mixes are disjoint, and **deflating (k, n) before `wilson()`** — none
  of which is written yet. Three independent attempts at this one statistic in a single day
  produced three different answers, every time by the same mechanism.
  ([[sources/session-20260815-scans-and-corrections]] §2)
  *2026-08-27 addition — one sub-claim resolved, the other reconfirmed CURRENT, both against a
  concrete new instance:* the **nominal-n sub-claim (SE inflation ×8.07) is RESOLVED**
  (`c4e4a599`, 2026-08-22T21:04:05Z, "effective-n reaches gate_efficacy" — verified on-tree by
  re-running `git show -s c4e4a599`; `by_code`'s Wilson intervals now run on effective n
  everywhere). The **era-confound sub-claim was NOT touched by that fix and is CURRENT** — measured
  directly against the still-live corpus, 2026-08-27 ~21:35–22:10 UTC: `SZ-021`'s pooled rows are
  **100% `triple_barrier_h432`** against a baseline still 84.1% `legacy` / 15.9% `exit_sim` / 0%
  `triple_barrier*` (0 baseline rows written since 2026-07-20) — **zero `label_era` overlap**. The
  commit that shipped `by_code` as a Grafana-exported significance claim
  (`5e785c16`, "the veto counters learn whether the vetoes were right") published SZ-021 as
  **"ANTI-SELECTIVE at significance"** (0.509 [0.439, 0.580] vs frozen baseline 0.265
  [0.192, 0.354], disjoint) into `docs/HANDOFF.md` REG-6 UPDATE and `liquiditybot_veto_cf_rate` —
  built directly on the unresolved half of this entry without revisiting it. Re-derived against a
  **contemporaneous, same-window comparator** (everything else the pipeline saw in SZ-021's own
  active window, n=1,772, rate 0.440 [0.369, 0.514]): SZ-021's [0.439, 0.580] **overlaps** — the
  "significant" qualifier does not survive an era/time-matched baseline. Direction is
  **unresolved, not refuted**. *Fix, same session:* `gate_efficacy_report.py` (commit
  `a94b5751`, "fix(telemetry): gate_efficacy_report refuses significance across disjoint
  label_era") now implements exactly the remedy this entry called for above — `_row_era` +
  `ERA_OVERLAP_FLOOR` (5%, policy floor, not fitted) + a `comparison` field that reads
  `CONFOUNDED_BASELINE` instead of asserting `anti_selective`/`selective` whenever a code's own
  `label_era` mix shares under 5% overlap with the baseline sample; rates/CIs stay printed,
  unsuppressed. Injection-tested (disjoint-era corpus → `CONFOUNDED_BASELINE`; same-era corpus →
  normal verdict still fires) and mutation-verified (inverting the floor comparison flips 3 pins
  red, including a pre-existing one). Live re-run against the corpus above: `SZ-021` and `SZ-023`
  (the "sits AT baseline" claim in `docs/HANDOFF.md` REG-6 UPDATE, 2026-08-26) both now read
  `CONFOUNDED_BASELINE` (era_overlap 0.000 and 0.008 respectively); `SZ-030` stays legitimately
  `selective`
  (era_overlap 0.685) — the guard does not blanket-suppress. Whether this closes the OPEN class is
  an operator call for the next currency pass, not asserted here.
  ([[sources/session-20260815-scans-and-corrections]] §2, `docs/HANDOFF.md` REG-6 CAVEAT
  2026-08-27)
  *2026-08-27 second addition, same session — the hardened guard supersedes the previous
  paragraph's SZ-030 clause and widens the finding to EVERYTHING:* a user-invoked `/code-review`
  on `a94b5751` found the overlap test was one-directional SET membership (a single contaminating
  baseline row bought an era full credit); the fix-wave (`62ab10c0`, ~23:10Z) replaced it with
  WEIGHTED (histogram-intersection) overlap + a 50% majority line (`ERA_OVERLAP_MAJORITY`,
  `PARTIAL_OVERLAP` between the floors) and guarded the admitted-vs-baseline HEADLINE too (it had
  no guard at all — same confound species). Live re-run under the weighted guard (read
  2026-08-27T22:48:57Z, `raw/audits/2026-08-27_sdd_verification/ger_live_20260827T2248Z.json`):
  **every `by_code` row AND the headline read `CONFOUNDED_BASELINE` or `PARTIAL_OVERLAP` — none
  clears to COMPARABLE.** "`SZ-030` stays legitimately selective at 0.685" above is
  **SUPERSEDED**: 0.685 was the membership artifact; weighted overlap is **0.1586608442503639**
  → `PARTIAL_OVERLAP` (SZ-021 0.0 · SZ-023 0.0082 · SZ-045 0.0842 · SZ-022 0.0737 · SZ-030/
  SZ-046/SZ-020/SZ-050 0.1587 · headline 0.1587). Mechanism, and why this is the guard working
  rather than over-tuned: the frozen baseline's own composition (84.1% `legacy` / 15.9%
  `exit_sim` / 0% `triple_barrier*`) caps every code's MAXIMUM weighted overlap near 0.159
  unless the code is itself majority-`legacy` — none is. **The frozen 2026-07-20 baseline cannot
  honestly vouch for ANY of today's corpus; every veto-quality verdict is now confounded pending
  a live baseline.** Class stays **OPEN** — the instrument now refuses honestly, but no verdict
  (SZ-021's direction included) can be rendered until a contemporaneous baseline exists: owed
  **104** in [[synthesis/owed-measurements]]; a control-arm stratification-tag prototype (the
  root cure) is in the isolated sandbox worktree, NOT merged, operator adjudication required.
  ([[sources/session-20260827-sdd-verification-and-era-confound]] §2, `docs/HANDOFF.md` REG-6
  CAVEAT fix-wave hardening 2026-08-27)
  *2026-08-28 third addition — the final review found the guard's own HEADLINE speaking the
  wrong language, and the whole chain is now pushed:* final-review **F1** (`0084c16d`): the
  admitted-vs-baseline headline had reached the confound states by calling `_comparison` with
  `is_veto=True` — a lie to the parameter that leaked the VETO significance tokens **inverted**
  onto a TAKEN sample (admitted 0.90 vs baseline 0.10, same era, exported `anti_selective` —
  the harm word for brilliant selection). `_comparison` gains a keyword-only `admitted=` flag;
  the admitted headline now speaks **`selects_winners` / `adverse_selection`**; veto tokens
  untouched; pinned both directions in tests. **Vocabulary-currency note:** any enumeration of
  the comparison states predating `0084c16d` — including this register's paragraphs above and
  the 08-27 raw audit snapshot, both dated-correct — lacks the two admitted-side tokens.
  Commit currency: `a94b5751` · `62ab10c0` · `0257fd59` · `cd84c2aa` · `f17e28b5` · `52315a57`
  · `0084c16d` · `22d789ce` are ALL on `origin/main` (ancestry verified 2026-08-28); the
  filing-time LOCAL/UNPUSHED caveat is retired. Class stays **OPEN** on owed **104** exactly as
  above — F1 changes what the instrument says, not what it can know.
  ([[sources/session-20260827-sdd-verification-and-era-confound]] §2 RE-STAMP, T5 doc
  `docs/quant/2026-08-28_session_synthesis_T5.md`)

- **`exec_era` ABSENT vs `exec_era` BLANK — the boundary table's decision rule is correct for
  one class and wrong for another (2026-08-14, QUALIFIED not overturned, class OPEN).**
  [[synthesis/comparability-boundaries]] states: *"pre-schema rows are deliberately blank =
  decide by row timestamp against this table… a feature of the schema, not a gap in it."* True
  for rows a stamp-aware writer emitted. **False for rows a stale binary emitted**, where the
  field is *missing* rather than empty: `fills.csv` width histogram **`{17: 1059, 16: 6}`**,
  `exec_era` being column index **16 — the LAST of 17**. Deciding those six by ts returns
  **era-7** while their fill physics is **pre-boundary-#4** (written at `21769fb8`, of which
  boundaries #3, #4 and cut #7 are all **non-ancestors** — TTL-hazard bug and ~1.88x
  near-touch double-count both live). **4 of 13 accruing era-4 trips carry such a leg.**
  *Why it stays OPEN:* the read is now correct in `cohort_eval` (three-way, pinned by
  `tests/test_cohort_homogeneity.py`), but **whether a cohort containing 4 stale-binary trips
  and 6 deploy-straddling trips may still serve the pre-registered n=50 verdict is an operator
  adjudication that has not been taken.** *What would close it:* that adjudication, on the
  record. Note the shape it shares with the entry above — **both are cases where provenance
  the system genuinely had was not carried to the place that needed it.**
  ([[sources/session-20260814-cohort-instruments]] Finding 1)
