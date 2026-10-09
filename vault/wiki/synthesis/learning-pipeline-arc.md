---
title: The Learning-Pipeline Arc
category: synthesis
summary: The full chain from a bad label definition to the first live in-era rows, the discovery that the plumbing was never the binding constraint, the second discovery that the first "binding constraint" was measured on contaminated fills, the day both decisive tests came back null — and the chapter where the corpus itself was destroyed by this project's own migrator and then healed, ending 2026-08-09 with the pipeline re-deriving an honest champion by itself once the data was true (lesson 9 the counterpart to lesson 8) — and closing the same day with lesson 10, the audit of the arc's own framing: a working pipeline is not evidence of a working strategy, the honest pipeline is learning from a population whose gross mean is ~0 (−11.66 before any fees vs 382.59 of fees), and the economics were computable by one arithmetic identity the whole time — then LESSON 11 the same evening, sharper still: the arc has never had an honest instrument panel to read the strategy WITH, since two adversarial fleets found eleven distortions across every reporting surface running one direction (flattering, zero understating), three of them sitting directly on this arc including a go/no-go tool that has been printing the opposite of its own method's answer — CLOSED the same evening by LESSON 12: 415af0f9 repaired that tool and four others (geometry_search and random_entry_control are ON this arc, both having reasoned about 235 of 394 round trips), the two 08-02 nulls stand MORE firmly because the restored hedge legs are worse than the population searched, and the repaired panel reads a per-trade gross edge of −0.0019% at t=−0.332 — so a healthy pipeline, an honest champion and a repaired instrument panel are all necessary and none of them is evidence of a strategy
tags: [arc, labeling, corpus, narrative]
sources: 17
updated: 2026-08-14
---

# The Learning-Pipeline Arc

The longest and most instructive thread in the corpus. Each step was correct given what was known, and
each created the next problem.

## The chain
**07-19** — [[sources/weekend-labels]]: the corpus "knows ~7x less than its row count claims."
Uniqueness weighting ships. *The defect is in counting, not collecting.*

**07-24** — [[sources/goals-mindset-review]]: 77% of losses are "plain underperformance"; the champion
is a coin flip. **No mechanism named.**

**07-26 (am)** — [[sources/label-signal-quality]]: the mechanism. The label recorded **which exit fired**,
not whether the signal was good. **Barrier-alone AUC 0.769 beats the 62-feature model's 0.597.** Label
mode flips to triple-barrier. The old corpus is left in place and the exclusion question left **open**
— "excluding them would collapse the corpus below the evidence floors."

**07-26 (pm)** — [[sources/era-exclusion-decision]]: the operator closes that question **in the opposite
direction from the stated worry** — exclude everything old including live rows, but auto-arm at a
derived threshold so the collapse can never happen below the evidence floor.

**07-27** — [[sources/live-row-era-gap]]: measures the hole. **241 in-scope live rows, 100% old-era.**
Cause: live closes stamp a fixed barrier string.

**07-28** — [[sources/geometry-alignment-adjudication]]: declares the gap **closed by design**. Full
battery green, no gate moved. *The declaration was wrong, and the same task shipped a regression.*

**07-29** — [[sources/pt060-bracket-wedge]]: a live incident. Suppressing the no-progress overlay for
bracket positions left a **60-bar unprotected wedge**; one position realized **-1.69% against an
expected -0.08%**. The overlay is reclassified as a [[concepts/protective-senior-overlay]] — and its
closes deliberately keep the generic barrier tag "so there is no era contamination."

**07-29** — [[sources/training-anomaly-analysis]]: era exclusion is now ACTIVE and **broke three
consumers at once** — the evidence gate admits only the simplest family, the champion watermark exceeds
the whole corpus ([[concepts/deploy-deadlock]]), and the retrain flag can never clear.

**07-31** — [[sources/live-label-era-deadlock]]: **still 0 live in-era rows, four days after "closure."**
The investigation **retracts its own central claim**, then names the real mechanism:
[[concepts/clock-inversion]] — the overlay fires at bar 36, the label's vertical sits at bar 96.
The design choice made on 07-29 for good local reasons was the global cause.

Resolution verified live: **0 -> 3 live in-era rows.** And a second-order defect found **only because
the operator verified rather than assumed**: the era filter hardcoded the un-qualified era constant, so
the horizon fix made its own new rows invisible. "Left alone, `live_clean` would have stayed 0 forever
and the horizon fix would have been wrongly written off as a failure."

**08-01** — [[sources/cost-to-volatility-horizon-mismatch]]: the arc **reverses its own premise**. The
newly-unblocked geometry is **four times too wide**, and the plumbing was never the binding constraint.

**08-01 (pm)** — the **432-bar (36h) migration** ships (commit `7566ea88`) as a pre-registered
experiment: hold everything until 50 closed trades. The learning loop is confirmed repaired —
`live_clean` 0 → 24 after 13 days pinned at 0. **Repaired is not profitable: the two moved in
opposite directions the day it was fixed.**

**08-02** — [[sources/session-20260802-digest]]: the premise reverses **again**. The "cost is the
binding constraint" headline — and its successor "entry-edge problem" — were both computed from a
`fills.csv` carrying 64 fixture rows, one position under 16 ids, P&L wrong by **27x**
([[concepts/default-path-fallback-writes]], fixed `858c8d71`). Clean per-fill measurement (n=215):
win rate 57.5%, payoff ratio 0.560 vs 0.740 needed — the binding defect is
[[concepts/payoff-asymmetry]], and the lever is exit geometry. The migration holds at 6/50.

**08-02 (addendum)** — the diagnosis **survives its own stress test**. A residual sweep found and
quarantined 18 more fixture positions (72 rows, commit `483f6727`; attribution corrected to
**battery smoke runs**), leaving `fills.csv` **637/637 audit-crossref CLEAN** by the decisive
provenance signal — `order_id` membership in the hash-chained `audit.jsonl`. Post-quarantine
(n=217): win 57.1%, payoff 0.561 vs 0.750 needed — **materially unchanged; the payoff-asymmetry
thesis stands.** After three binding-constraint headlines that each died to dirty data, this is
the first one re-measured on a fully-verified ledger and confirmed.

**08-02 (late)** — the two decisive tests run **the same day the diagnosis stabilized, and both
come back null**. The **random-entry MFE control** (`scripts/random_entry_control.py`, commit
`8062f46a`): real entries' mean MFE percentile **0.516 [0.439, 0.594]** against 200 seeded
matched controls each — **no timing signal**; the 87%-positive-MFE figure was diffusion (caveat:
n=51 rules out a large edge only). The pre-registered **48-combo geometry search** (commit
`663434ae`, battery green): **no bracket
survives** (Bonferroni z = 3.26, 222 real entries, config fees; best mean −0.400%, LB −1.124%)
— **exit design can minimize bleed, not create edge**. The arc's endpoint sharpens: pipeline
repaired, ledger clean, diagnosis confirmed — and **neither entry timing nor bracket geometry is
the source of edge**. The **cost wedge** is also quantified: 25.1% of winning PT touches fail
the cost stack and label 0 ([[concepts/cost-to-volatility-ratio]]). What remains: the cost
stack, pooling, and the cohort verdict.

**08-02 (follow-on)** — the arc's honesty program reaches the **fill simulator**. XV-021 had
measured the market trade-through rate at **0.048** (22,854 resting-limit trials, Wilson
[0.046, 0.050]) against a configured `passive_base_prob` of 0.45 — the sim filled resting orders
**9x too often**. Shipped `8e5455e8` (battery green), consciously ahead of the post-cohort
docket: paper entries will drop sharply — **that IS the honest rate** — and the commit timestamp
is an **execution-regime boundary inside the 432 cohort** (first 11 closes under flattered
fills). The XV-022 caveat is carried: 0.048 is the conservative end of [0.048, 0.082] and the
exponential form itself is owed a replacement. After ledger cleanliness (`483f6727`) and cost
conservatism (fees held at 25/40 vs Kraken 16/26), this closes the third leg of the same
principle: **paper results may only err against the strategy**
([[sources/session-20260802-digest]] third addendum, [[synthesis/risk-posture-doctrine]]).

## Four lessons the arc teaches
1. **A locally-correct decision can be the global cause.** Keeping the generic barrier on overlay closes
   prevented label contamination *and* starved the era.
2. **"Closed by design" is not closed.** Four days of full-green batteries passed between the
   declaration and the measurement that refuted it. Only measurement closes a gap.
3. **Verify rather than assume** — the highest-value find in the corpus came from checking that a fix
   actually produced the rows it was supposed to produce.
4. **Fixing the pipeline reveals the economics.** The chain had to be repaired before the real
   constraint became visible. See [[synthesis/the-money-path-thesis]].
5. **Clean the data before naming the constraint.** Two successive binding-constraint claims (cost,
   then entry edge) died to the same 64 contaminated rows. The measurement scripts were fine; the
   ledger they read was not.
6. **Repetition is not evidence — timing structure is.** The residual sweep's first heuristic
   ("identical blocks = fixtures") convicted the live hourly retrain cadence (rows=2141 × 6 at
   3603 s gaps, CLEAN) and missed the actual suite burst (rows=60 × 7 at 548 s median,
   CONTAMINATED). See [[concepts/iron-law-of-debugging]].

## The filing layer, audited (2026-08-06) — the chain's foundation is sound

The arc's every claim rests on the corpus being an honest record of what was traded. That
assumption was finally **audited at the filing layer** ([[sources/session-20260806-geometry-filing]],
commit `ee0ac4ad`) and it **held**:

- **Rotation loses nothing** (13 `.bak` generations recovered, 0 rows missing).
- **The live `pt_frac`/`sl_frac` threaded into `log_close` IS the traded geometry** — **no
  recompute anywhere on the path**. This is the load-bearing one: it means the **geometry-search
  null** and the **432-bar cohort** are computed against brackets that were **actually placed**,
  not reconstructed ([[synthesis/the-money-path-thesis]], [[comparisons/horizon-96-vs-24-bars]]).
- **A suspected 10.9% ground-truth hole was not a hole** — 34 quarantined QA-harness fills plus 3
  `FEATURE_SCHEMA_VERSION` drops, and the drops matched **by position id**: exactly the 3
  positions open at the v8→v9 bump. **Nothing was bleeding.**

**Two consequences for the arc, both about instruments rather than data:**

1. **The `disp` column was truncated at 40 chars for the corpus's entire life** — **ZERO of 9,692
   rows retained a bracket payload** — and `gate_efficacy_report.py` **regex-scrapes that field**.
   Gate-efficacy conclusions drawn from the historical corpus read an amputated column, and **no
   re-run recovers it: the bytes were never written.**
2. **The labeled-vs-traded agreement gauge was a tautology** reading 1.0000 while **94.3%
   arithmetically incapable** of anything else ([[concepts/tautological-instrument]]). Post-fix
   the honest reading is **"not yet measured"** — the arc has *never* had a real measurement of
   whether the traded bet resolves where the label says it should.

> **Lesson 7, and it inverts lesson 5.** *"Clean the data before naming the constraint"* assumed
> the failure mode is dirty data. Here the **data was clean and the instruments were not** — a
> truncating writer and a definitionally-fixed gauge. **A pipeline can be honest and still be
> unable to tell you so.** The 08-06 pass spent its effort proving a negative, which was only
> expensive because [[entities/historystore]] had no ML-084 counter to answer it cheaply.

## The corpus itself became the failure (2026-08-08/09) — the arc's first self-inflicted data loss

Every earlier chapter of this arc is about a pipeline that was **honest and blocked**: a
label definition that could not resolve in-era, a clock inversion, a filter measuring
production's complement, instruments that could not read. **2026-08-09 added a chapter where
the pipeline was working and the CORPUS was destroyed** — by this project's own migrator,
triggered by this project's own schema commit
([[sources/session-20260809-corpus-corruption]]).

One non-idempotent line re-derived `label_era` on every migration pass, pooling **2,729
rows** across three incompatible label definitions ([[concepts/migration-idempotence]]).
The chain that followed ran entirely through mechanisms this arc had already built and
trusted:

`label_era` corrupted → [[concepts/era-exclusion]] **disarms** (690 → 42 current-era rows,
below the 150 floor) → the pooled corpus enters training (690 → 9,746) → `live_clean`
5 → 299 → **all four [[concepts/evidence-floors]] clear in one step** → **`gbt` deployed as
champion at 20:10:44 on a data bug** → and the same disarm flipped the overfit battery to
live grading, where it went red **for a reason that was then misdiagnosed for a day**.

> **Lesson 8 — the arc's mechanisms are chained, so a bad input does not produce a visible
> error; it produces a plausible DECISION.** Each link behaved exactly as designed. Era
> exclusion correctly stood down for what looked like a young era. The floors correctly
> admitted families that looked evidenced. The selector correctly picked the best-scoring
> model. **A pipeline built to make decisions automatically from corpus statistics will make
> a confident wrong decision from a corrupted corpus faster than any human can notice** —
> nine minutes, here. The instrumentation this arc spent weeks building measures whether the
> pipeline is *learning*; none of it measures whether the corpus still *means* what it did.

**What the arc gains from it.** The corpus survived — **zero rows lost**, repaired from
preserved backups by `position_id` join, because [[concepts/era-exclusion]]'s
*nothing-is-ever-deleted* bound meant only a derived tag was ever at risk. And on the
repaired corpus the battery restated this arc's own thesis in its own voice:
**"CLIMBING (delta_auc=+0.112) — data-starved: more rows are still buying skill; corpus
growth is the highest-leverage learning input right now"** — which is the
[[concepts/dof-budget]] conclusion, measured rather than derived, on **690 rows / 64
features** with `dead_frac` **0.95**.

~~**What it leaves open.** A champion promoted by the bug is now **WEDGED** — its 0.1537 was
scored on the corrupted corpus, so the clean-corpus challenger's 0.2714 loses a comparison
between incommensurable populations, and no honest challenger can dislodge it without a
conscious re-baseline ([[concepts/ghost-badge]], [[synthesis/owed-measurements]] item 47).
**The arc's first genuinely clean in-era corpus arrived with a model on top of it that was
selected by the corruption.**~~

## The chapter's ending — the pipeline healed itself (2026-08-09 02:56:04)

**It did not need the conscious re-baseline.** Roughly seven hours after the repair, the
[[entities/ml-governor]]'s own **ML-083 era-orphan branch** — adjudicated 2026-07-29 for the
*opposite* deadlock — fired on the repaired corpus: the champion's watermark (**9,708**, the
corrupted pooled population) **exceeded** the training matrix (**701** rows), so the badge was
**unfalsifiable by construction**, was **set aside entirely**, and `logistic` cleared the true
cold-start bar at **0.24728 < 0.25** and **deployed**
([[sources/session-20260809-gate-policy-and-self-heal]] §1). Verified live:
`meta_model.json` `kind=logistic rows=701 oof_brier=0.24728`; `status.json`
`model_kind=logistic`, era `armed=True`/`active=True`, load **701**, `live_clean` **6**.
**The arc's first genuinely clean in-era corpus now has an honestly-selected model on top of
it.**

> **Lesson 9 — the counterpart to lesson 8, and the more useful half.** Lesson 8 says a
> chained pipeline turns a bad input into a **confident wrong decision** in nine minutes.
> Lesson 9 is the same property read forward: **the chain runs in the good direction too, at
> the same speed, with no human in it.** The corpus repair was the **necessary and sufficient**
> intervention — every downstream mechanism had been correct all along, operating on a
> corrupted input. **Fix the data and the decisions re-derive themselves.**
>
> The operational instruction that follows: **when a chained pipeline is producing wrong
> decisions, look for ONE corrupted input, not N broken mechanisms** — and then **wait one
> full cycle before intervening downstream**, because an intervention that pre-empts the
> self-correction is indistinguishable from one that was needed. Here the gate was
> deliberately **not** overridden, and that restraint is the only reason the self-heal is
> *observable* rather than merely *hypothetical* ([[concepts/false-green]] §positive
> instance).

**What it actually leaves open.** Two things, both smaller than the wedge:
(1) the detection was a **row-count proxy** — a corrupt population that happened to be
*smaller* than the clean matrix would still compare "successfully", so the missing
**provenance stamp on the stored watermark** is still owed; and (2) the
[[synthesis/owed-measurements]] **item 49** asymmetry — `scripts/train_meta.py` lacks the
era-orphan branch, so the **CLI rejects what the runner accepts**, and the bot's own ML-032
message tells the operator to run the CLI.

## The arc's own framing, audited (2026-08-09) — lesson 10

([[sources/session-20260809-unbiased-economics]].) This page is the corpus's **narrative
spine**, and the same day the pipeline healed itself, the narrative it is written in was
measured against the money.

**The measurement.** Over ~250 closed positions: **gross P&L before ANY fees = −11.66**
(~−$0.05/trade ≈ 0) against **382.59** of fees — **32.8x**, **100% of the −394.25 all-in loss
is costs**. Corroborated by OOF **AUC 0.43–0.48**, champion **Brier 0.24728 vs 0.25**, and
postmortem **MFE median 0.18%** against a **~0.65%** round-trip cost.

**What that does to this arc.** Every chapter above is a **plumbing** chapter: a bad label
definition, a clock inversion, a contaminated ledger, a non-idempotent migrator, a wedged
champion. Each was real, each was correctly diagnosed, and **fixing all of them was necessary**.
The arc's implicit promise — *once the pipeline is honest, the learning can begin* — has now
been half-answered: the pipeline **is** honest (lesson 9), and the honest pipeline is learning
from a population whose **gross mean is ~0**.

> **Lesson 10 — a working pipeline is not evidence of a working strategy, and the arc was
> quietly conflating them.** Nine lessons of hard-won plumbing discipline created a strong prior
> that the *next* fix would unlock the learning. That prior is exactly what made
> "cold-start" and "data-starved" feel like conclusions rather than hypotheses. **The economics
> were computable the entire time** — one arithmetic identity over `state.json` — and were never
> computed, because the arc always had a plumbing defect to point at instead.

**This is not a retraction of the arc.** Every fix stands, every mechanism was real, and lesson 8
(*a passing pipeline can be running on destroyed data*) and lesson 9 (*the model layer heals
itself once the data is true*) are unaffected. What lesson 10 adds is a **boundary on what the
arc can conclude**: it is the history of making the instrument honest, and an honest instrument
is a precondition for measuring edge — **not evidence that edge exists**.

**The rule that follows** is filed as [[concepts/unfalsifiable-explanation]]: house vocabulary
must carry its falsifier. Two of this arc's own terms have already been tested — *"data-starved"*
(falsified as a complete account) and *"exploration is tuition"* (not yet: OOF AUC < 0.5 after
305 live labels). Both keep their pages; neither keeps its authority over the economics.

## Lesson 11 (2026-08-09, later) — the instruments that would have told you were broken, and all in one direction

([[sources/session-20260809-adversarial-audits]].) Lesson 10 said *a working pipeline is not
evidence of a working strategy*. The same day supplied the sharper form: **the arc has never had
an honest instrument panel to read the strategy WITH.**

Two adversarial fleets — 22 agents on the Grafana panel/metric chain, 25 on a self-flattery hunt
— found **eleven distortions across every reporting surface**, and:

> **Every one runs the same direction: flattering. Zero understate the bot.**
> ([[concepts/self-flattery-gradient]])

Three of them sit directly on this arc:

1. **The go/no-go tool has been answering the arc's central question backwards.**
   `scripts/breakeven_test.py` discards all 159 hedge round trips (as *"partial or malformed"* —
   none are malformed), which moves the median gross from **−0.0303% to +0.0505%** and **selects
   the opposite one of its two hard-coded verdict branches**: *"this is exit geometry, fixable
   without touching the signal"* instead of *"gross expectancy is negative."*
2. **The performance ledger the arc reads for expectancy cannot see the hedge book** — the entire
   **−325.70** of it — and neither can the consecutive-loss breaker, which is why **159
   consecutive losing hedge round trips never tripped it.**
3. **The headline expectancy pools 91% EV-gate-bypassed probes with conviction trades**, so the
   number the arc has been tracking (**−0.2838**) understates the population the strategy is
   about (**−1.5840**, n=17) by **5.6x** — while the codebase's own ML lane
   (`overfit_check.py:1031-1034`) has refused to do exactly this for months
   ([[concepts/pooled-populations]]).

**The lesson, stated for reuse:**

> **Before trusting a learning arc's readings, audit the arc's instruments for DIRECTION, not
> just for defects.** A single broken instrument is noise; **a population of broken instruments
> that all err the same way is a bias**, and it will survive every honest attempt to learn from
> the numbers it produces.

**What it does NOT change:** the pipeline itself is still sound — lesson 9's self-healing
champion, the repaired corpus, the era filter, the gates. **And the economics do not improve**:
the corrected instrument agrees with the state identity (gross **−13.01** vs **−11.66**), and
because every error flatters, **the honest picture is worse, not better** — real gross would be
below the simulated figure, not above it ([[concepts/paper-real-boundary]]).

## What is still open
**The economics are now the arc's open question, not the plumbing.** The decisive next
measurement — **is there gross edge in ANY subpopulation** — is **blocked**: the corpus carries
`net_pnl_usd` and **no gross and no per-row fee column**, and the binary win/loss label
**conflates "signal was wrong" with "costs ate it" at the point where the model learns**
([[synthesis/owed-measurements]] item **50**, HIGH; [[entities/historystore]]). The one live lead
is **geometric** — shadow win rate rising monotonically 22.3% → 30.4% → 35.4% across 108 → 216 →
432 bars ([[comparisons/horizon-96-vs-24-bars]]) — and the **9,570 free candidate rows have never
been searched** (item 51).

The **20-36 minute probe-close cohort remains unexplained**, with the instrument armed. Under the
[[concepts/iron-law-of-debugging]], no fix may be chosen for it until the mechanism is named.
The **432-bar cohort** must reach 50 closed trades before any geometry change (11/50 late on
08-02; the post-432 window reads 0% wins, Wilson [0, 25.9%] — unreadable), and its verdict must
now be **read across the `8e5455e8` fill-regime boundary**. The **random-entry
MFE control has now been run — NULL** ([[synthesis/owed-measurements]] item 0, CLOSED); the
**XV-021 fill-sim recalibration has now SHIPPED** (`8e5455e8`, item 13b CLOSED). Still owed on
the economics side: the **XV-022 fill-probability form replacement** (0.048 is the conservative
end of [0.048, 0.082]; item 13c) and the `calibrate_fills.py` re-run on the clean ledger (23b).

## Lesson 12 (2026-08-09, evening) — lesson 11's worst instrument is FIXED, and the reading it now gives is the arc's verdict

([[sources/session-20260809-turing-test-hedge-verdict]].)

**Lesson 11's headline specimen — a go/no-go tool printing the opposite of its own method — is
discharged.** `415af0f9` shipped, and the defect was **five scripts wide**, not one:
`breakeven_test`, `cost_attribution`, `cost_truth_report`, `geometry_search`,
`random_entry_control`. **`geometry_search` and `random_entry_control` are on this arc** — the two
tools that ran the arc's decisive geometry and entry-timing searches had both been reasoning about
**235 of 394** round trips.

> ⚠️ **This does NOT reopen the two 08-02 nulls, and the reason matters.** Both nulls were
> *negative* results, and the hedge legs excluded from them are **worse** than the population that
> was searched (0 of 159 profitable net of fees). Restoring them cannot turn a null into a
> finding. **The nulls stand, and stand more firmly.**

**The reading the repaired instrument gives** — median gross **−0.0305%**, and independently a
per-trade gross edge of **−0.0019% at t = −0.332** — is the arc's answer to lesson 10's question:

> **The pipeline is learning from a population that is statistically indistinguishable from zero
> on selection.** Not a weak signal buried in noise — **no measured signal**. Every plumbing
> victory in this arc was real, and none of them could have produced expectancy that is not in the
> entries.

**Lesson 12, stated for the next session:** *a healthy pipeline, an honest champion and a repaired
instrument panel are all necessary and none of them is evidence of a strategy.* The arc has now
achieved all three, and the economics did not move.

**What this adds to "what is still open":** item **50** remains the blocker (no gross, no per-row
fee column), and item **54**'s probe/conviction split **shipped but is INERT** (live: `unknown 200
· probe 0 · conviction 0`), so the arc still cannot read its own populations apart
([[concepts/pooled-populations]], [[comparisons/dormant-vs-inert-features]]).

## Lesson 13 (2026-08-14) — the pipeline re-derived a champion by itself again, and this time it was worse

Lesson 9 recorded the arc's best moment: *the pipeline re-derived an honest champion by itself
once the data was true.* The same machinery ran unattended on 2026-08-14 and produced the
inverse, by exactly the same property — **autonomy**.

The chain, every link individually correct:

1. The h432 geometry cut left **259** current-era rows — **2.5%** of a 10,559-row corpus.
2. [[concepts/era-exclusion]] refused to pool them with retired geometries whose base rates
   span **40x** (0.0065 → 0.2611). Correct; refusing would have been indefensible.
3. That left a **211-row** training matrix against a champion trained on **10,217** — a **48x**
   orphan ratio, which fires ML-083's unlock ([[concepts/deploy-deadlock]] §third polarity).
4. The unlock has **no floor**. Badge set aside, bare cold-start bar `Brier < 0.25` applied.
5. A logistic deployed at 0.21887 whose own `family_brier` was **0.33105 — worse than a
   constant p=0.5 predictor** — **inside the accruing era-4 window**.
6. Post-deploy the gate then **defended** it: a better challenger (**0.17959**) was rejected by
   the like-for-like branch for having no shared row set.

**Lesson 13:** *a self-improving loop is only as safe as its worst permitted promotion.* Lesson
9's healing and this regression are **the same capability** — a loop that can re-derive a
champion without an operator can also install one without an operator, and the arc has now done
both. What distinguished the good case was not the loop; it was that the **data** had been
repaired first. Autonomy is a multiplier on corpus quality, in whichever sign the corpus has.

**What the arc can now read that it could not:** `outputs/models/registry.jsonl` held **134
`registered` events and ZERO `deployed`** ones until `61c3b5c1`, so this promotion — like every
promotion before it — left no lifecycle record. The `deployed` half is now wired at both
cutover sites. **Corpus revision and era set are still absent**, which is the residue of the
open incommensurable-scores contradiction.

**And the arc's live half is now a probe lane.** Over the exact 24h window
`[1786664298, 1786750698]`: 123 labels, **4 live**, of which **3 are `probe=1`** — the gate
itself produced one entry (BTC, `label=0`, −$0.42), 24h net **−$0.15**. Item 54's split is
therefore **populating, not inert** — the counter above is superseded — but at n=4 it closes
nothing ([[concepts/probe-livelock]] §terminal state).
— [[sources/session-20260814-cohort-instruments]]
