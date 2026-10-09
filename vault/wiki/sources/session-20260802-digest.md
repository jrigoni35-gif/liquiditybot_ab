---
title: Session Digest (2026-08-02) — QA Root Cause, Corrected P&L, Forward Plan
category: source
summary: The QA-contamination root cause found and fixed (858c8d71), both prior binding-constraint headlines refuted by clean per-fill measurement — the real defect is payoff asymmetry (post-quarantine 0.561 vs 0.750 needed, materially unchanged) — and the forward plan of levers ranked by measured evidence. Addendum 2026-08-02: residual contamination quarantined (483f6727), fills.csv 637/637 audit-crossref CLEAN. Second addendum (late session): two decisive nulls — random-entry MFE control shows NO timing signal, pre-registered 48-combo geometry search shows NO surviving bracket (exit design minimizes bleed, cannot create edge) — plus the cost wedge quantified (25.1%). Final micro-addendum: geometry_search committed (663434ae, battery green), and the operator's wiki-is-truth directive filed as governance rule 12. Third addendum (follow-on session): HONEST FILLS SHIPPED (8e5455e8) — passive_base_prob 0.45→0.048 per XV-021's measured trade-through rate, an execution-regime boundary inside the 432 cohort; the risk-posture directive filed as synthesis/risk-posture-doctrine; deletion of learning data refused by design (quarantine re-check 0/136 wrongly convicted)
tags: [session, contamination, pnl, payoff-asymmetry, money-path, forward-plan]
sources: 1
updated: 2026-08-02
source_path: none — session work product (see Provenance)
source_date: 2026-08
authors: [operator, claude]
ingested: 2026-08-02
---

# Session Digest (2026-08-02)

## Provenance
This page summarizes a working session (id `63d8f842`), not a repo document — there is no `raw/`
snapshot. Ground truth is **re-runnable**: `scripts/breakeven_test.py` and
`scripts/cost_attribution.py` at commit `f0120393` (the P&L numbers; `outputs/fills.csv` grows live,
so re-run rather than quote), and `tests/test_qa_isolation.py` at commit `858c8d71` (the QA fix).
The session's own notes live in the project auto-memory files; the operator may snapshot them into
`raw/` if a frozen copy is wanted.

Three threads: the contamination root cause, the corrected P&L truth, and the forward plan.

---

## Thread 1 — QA contamination: root cause found and FIXED (commit 858c8d71)

`scripts/debug_cycle.py` builds the **real** `LiquidityBot` from the **real** `config.json` on
mocked feeds priced `ETH=2000.0 / BTC=60000.0`. It redirected the audit trail and ml paths **but not
`system.fills_ledger_path`**, so every simulated fill appended to the live `outputs/fills.csv` via
`main.py:1652 _ledger_fill`. The "impossible" ETH price was **fixture data**:
`arrival_ref = 2000.000000` is the mock, and the `1490.645739` stop fill is
`1491.018493 × (1 − 2.5bps)` — the fill simulator was correct; its reference price was fake.

**Why it was invisible:** `config.json` sets **no** `system.fills_ledger_path` and no
retrain-history key. The engine falls back to a hardcoded default that IS the production file, so
grepping config for the key finds nothing. **Absence of a key is not absence of a write.**
See [[concepts/default-path-fallback-writes]].

**This was the seventh occurrence of the class**, each found only after it corrupted a result, each
previously "fixed" by adding a line to `qa_redirect_paths` plus a comment claiming completeness:
`state.json` (deleted three real open positions) · postmortem summaries · retrain flags ·
`context_history.jsonl` (100+ rows) · `audit.jsonl` · `retrain_history.jsonl` (305 of 306 records
fixtures — measured in [[sources/test-suite-outputs-contamination]]) · `fills.csv`
(64 rows → P&L wrong by **27x**).

**A wrong theory held for four hours first** — fills re-logged on position restore — and drove a
diagnosis. Refuted by the timing: identical intra-block offsets (entry, then exits at +20/+25/+85
seconds) with identical prices to 10 significant figures and fresh `order_id`s; a restore cannot
reproduce that, and `append_fill` has exactly one caller. **Lesson: "same data twice" is not
evidence of re-logging; check whether the timing is deterministic.** Filed under
[[concepts/iron-law-of-debugging]].

**The fix asserts the invariant, not the known cases.** `tests/test_qa_isolation.py` (10 cases)
walks the real config through the real redirect and fails on any `*_path`/`*_dir` still resolving
under `outputs/`. That immediately found **two more** — including a real one: seven of eight QA
entrypoints called `configure_registry()`; `debug_cycle.py` did not, so it also wrote the
production model registry.

**Still open — do not assume clean:** ~~past contamination in `horizon_shadow.csv`,
`meta_model.json` and `outputs/models/registry.jsonl` is **unassessed**. `fills.csv` was
quarantined by hand (64 rows → `outputs/fills.quarantine.csv`); `retrain_history.jsonl`'s 305/306
(measured 2026-07-31) was never cleaned.~~ **Superseded by the Addendum below** — the fills debt
is CLOSED (637/637 audit-crossref CLEAN) and the other files are assessed. Still true:
`calibrate_fills.py` reads `fills.csv` to tune the fill simulator, so contamination **has already
fed forward**; its re-run on clean fills remains owed.

---

## Thread 2 — Corrected P&L truth: the sizes are wrong, not the hit rate

**Corrected twice on 2026-08-02, both prior headlines from contaminated data.** First headline:
cost is the binding constraint ([[sources/cost-to-volatility-horizon-mismatch]]). Second: the
strategy "loses ~0.34% per trade with fees at zero," an entry-edge problem. Neither survived
measurement. The old numbers grouped fills by `position_id`, and one position appeared under 16 ids
— the −1.32% figure was wrong by **27x**, and the "net + assumed cost" method behind −0.34% could
not separate fees from slippage at all. **Never group fills by `position_id`; key on the fill
pattern.**

**Clean per-fill numbers** (`scripts/breakeven_test.py`, `scripts/cost_attribution.py`, commit
`f0120393`, n=215 — re-run, the file grows live):

```
mean gross -0.048%   median gross +0.049%   win rate 57.5%
mean win   +0.2625%  mean loss    -0.4685%  payoff ratio 0.560
```

*(Post-quarantine re-measurement in the Addendum below: n=217, mean gross −0.0501%, win 57.1%,
payoff 0.561 vs 0.750 needed — materially unchanged; every conclusion in this thread stands.)*

- **The hit rate is fine. The sizes are wrong.** Break-even payoff at a 57.5% win rate is
  **0.740**; observed is **0.560**. The average loser is **1.8x** the average winner — the AVERAGE
  loser, not a tail. See [[concepts/payoff-asymmetry]].
- **"Tail risk" is refuted.** Post-purge the distribution is near-symmetric (min −2.38%, max
  +1.87%; dropping the worst 5% moves the mean only to +0.031%). The tail read came entirely from
  one fabricated trade counted 16 times.
- **The decisive number:** win rate needed to break even holding sizes fixed,
  `p = (cost + L)/(W + L)`, is **IMPOSSIBLE (p > 1) at all three real fee schedules**, including
  Kraken maker/maker at 0.320%. Only at zero fees does it become finite, at **64.1%**.
- Therefore **raising the hit rate cannot fix this** — only shrinking the average loser or
  extending the average winner can. That is **exit geometry**: stop distance, target distance, time
  stop. **A better model is not the first move** (a model raises `p`, and `p` is not the binding
  term); same for gates, filters, and meta-labeling.
- Fees are still the larger term (**0.667%** measured fee term against a 0.048% gross gap), but
  cutting them to zero leaves −0.048%. **Cost levers are necessary and not sufficient.**

**Provenance caveat on the older windowed numbers.** Win rate 5.5% / payoff 0.409 / net −$50.44
over 200 windowed trades / profit factor 0.024 were computed under the refuted `position_id`
grouping. The identification-impossibility argument built on them (PF 1 requires 70.97% win rate;
LR 42; ~1.7 effective independent positives) does not survive on its exact numbers, but its
conclusion — no filter, model, or weighting scheme is the lever — re-derives from the clean
numbers above. Flagged in [[synthesis/open-contradictions-register]].

---

## Thread 3 — The forward plan

**One test still owed, decisive, never run:** the **random-entry control on MFE** — sample entries
uniformly at random at the same horizon, compute identical MFE statistics. If random entries also
reach positive MFE ~87% of the time, there is no signal and everything downstream is moot. Highest
information per hour available. (The second decisive test — break-even transaction cost — is what
Thread 2 reports; it is done.)
*(Run later the same day — **NULL, no timing signal**. See the Second Addendum below.)*

**The hold:** the 432-bar (36h) horizon migration shipped 2026-08-01 (commit `7566ea88`) as a
pre-registered experiment; at **6 of 50** closed trades on 2026-08-02. `scripts/cohort_eval.py`
refuses a verdict below 50 and that refusal is the point. **Do not change label horizon, barrier
geometry, or exit policy until the cohort fills** — changing geometry resets the era clock in three
places at once (cohort counter, era exclusion, era-keyed realized gate ledger). Expect 2–3 weeks.
Research corrected three of the migration's supporting claims and ranks horizon extension the
**weakest** lever (Novy-Marx & Velikov 2016, *RFS* 29(1); Qian et al. 2007, *JPM*: zero gross
benefit — the entire gain is the cost saving). It runs to n=50 because thrashing costs more than
waiting. See [[comparisons/horizon-96-vs-24-bars]].

**Levers ranked by measured evidence:**
1. **Maker-only execution.** Kraken 0.16% maker / 0.26% taker: round trip 0.52% → **0.32%, a 38%
   cut**, moving cost/sigma 0.23 → ~0.15 at 36h. Barber, Lee, Liu & Odean (2009, *RFS*
   22(2):609–632): "virtually all individual trading losses can be traced to their aggressive
   orders" while passive orders were profitable. Fill uncertainty changes label geometry — a real
   design change, not a config flip.
2. **Asymmetric entry banding** (high entry hurdle, low exit hurdle). 41% turnover cut, 42% cost
   cut, gross returns *not* significantly reduced — the only technique in Novy-Marx & Velikov
   producing consistent net gains (rescued a high-turnover combo from t=1.11 to **t=5.23**).
3. **Pool across symbols.** ~50 pairs gives contemporaneous rather than temporally-overlapping
   labels — the only method that genuinely RAISES effective sample size instead of redistributing
   it (Gu, Kelly & Xiu 2020, *RFS* 33(5)).
4. **Walk-forward validation, not CPCV** (Schnaubelt: rolling-origin bias −0.166 vs random CV
   −0.887). **Check (purge width x test events) / sample length BEFORE enabling purging** — at 432
   bars purging can starve training and inflate error estimates up to 65x.

**Ruled out with measured evidence — do not re-propose:** sequential bootstrap / uniqueness
weighting as a rescue (the one independent replication is null); SMOTE or any oversampling (AUC
0.95 on pure noise if applied before splitting); GAN/diffusion synthetic paths (five independent
negatives, 8% memorization); jitter/warp/rotate/permute augmentation (44 of 72 method-architecture
pairs harmful); MFE-quantile exit tuning (folklore, no peer-reviewed base); and meta-labeling /
abstention filters — see [[concepts/abstention-filters-ruled-out]].

**Tripwires, in priority order:** (1) `ml.gate_stats.realized_closed` climbing from 0 — stuck at 0
means `gates_passed` is not reaching the position and the realized-outcome loop is dead; (2)
`cohort_eval.py` progress toward 50; (3) `outputs/auto_update.log` showing `rev 162c595c`
deployed; (4) `liquiditybot_era_mix_alarm` — was firing on 2026-08-02.

---

## Addendum (2026-08-02, later session) — residual contamination quarantined, attribution corrected

**1. Residual contamination found and quarantined (commit `483f6727`).** Beyond the 64 rows purged
at `858c8d71`, **18 more fixture positions (72 rows)** were found in `fills.csv` — including one
block written by a battery run **before** the fix. All quarantined. `outputs/fills.csv` is now
**637/637 audit-crossref CLEAN**. The fills cleanup debt in [[synthesis/owed-measurements]] is
**CLOSED**.

**2. Attribution corrected.** The fixture blocks were written by **battery smoke runs** — not by
bot restarts, and not by `debug_cycle.py` alone. `debug_cycle.py` was the entrypoint that exposed
the mechanism; the battery's smoke runs were writers through the same default-path fallback
([[concepts/default-path-fallback-writes]]).

**3. New decisive provenance signal: `order_id` membership in the hash-chained `audit.jsonl`.**
QA always redirected the audit trail even while leaking fills — so a fill whose `order_id` appears
in the hash-chained audit log is live, and one absent is fixture. This is the crossref behind
"637/637 CLEAN" and the strongest single classifier for any future suspect row.

**4. Lesson: repetition is not evidence — timing structure is.** Two repeated-block groups, opposite
verdicts: `rows=2141` × 6 at **3603 s gaps** is the live hourly retrain cadence on an era-frozen
corpus — **CLEAN**; `rows=60` × 7 at **548 s median** spacing is a suite burst — **CONTAMINATED**.
The first heuristic ("identical blocks = fixtures") **convicted the wrong group**. Filed under
[[concepts/iron-law-of-debugging]].

**5. Assessment sweep of the other suspect files** (updates [[synthesis/owed-measurements]]):
- `fills.csv` — **CLOSED**, 637/637 audit-crossref CLEAN.
- `retrain_history.jsonl` — assessed **158/165 records clean** (this snapshot; the 07-31 count of
  305/306 fixtures was a different snapshot — qualify by date, the counts are not comparable).
- `outputs/models/registry.jsonl` — **97/129 records are fixtures**; mitigation is
  **filter-at-read-time**, not a rewrite.
- `horizon_shadow.csv` — **58.8% proven clean**; the rest is **undecidable** (no order_id to
  crossref).
- `calibrate_fills.py` re-run on the clean ledger — **still owed**.

**6. Post-quarantine P&L: materially unchanged — the payoff-asymmetry thesis stands.**

```
n=217   mean gross -0.0501%   median gross +0.0469%
win rate 57.1%                payoff ratio 0.561 vs 0.750 needed
```

Removing 72 contaminated rows moved no conclusion: the hit rate is still fine, the sizes are still
wrong, and the lever is still exit geometry ([[concepts/payoff-asymmetry]]).

## Second addendum (2026-08-02, late session) — two decisive nulls, the cost wedge, per-asset cells

**1. The random-entry MFE control was RUN — NO TIMING SIGNAL.** `scripts/random_entry_control.py`
(commit `8062f46a`): **51 real trades vs 200 seeded matched controls each**, replayed on real
recorded 5-minute Kraken OHLC. Real entries' mean MFE percentile **0.516 [0.439, 0.594]** —
indistinguishable from 0.5; control median MFE **+0.285%** vs real **+0.246%**. The
"87% of trades reached positive MFE" figure was **diffusion, exactly as the null predicted**.
Closes [[synthesis/owed-measurements]] item 0 — the test named "highest information per hour
available." *Caveat:* n=51 rules out a **large** timing edge only; the bound tightens as
recordings accrue.

**2. Pre-registered geometry search — NO GEOMETRY SURVIVES.** `scripts/geometry_search.py`: a
pre-registered **48-combination bracket grid** (Bonferroni-corrected acceptance z = 3.26),
replayed on real OHLC over **222 actual entries** with config fees. Best combination
(h=432, tp=1%, sl=2%): mean **−0.400%**, lower bound **−1.124%**. **Exit design can minimize
bleed; it cannot create edge.** This bounds the [[concepts/payoff-asymmetry]] prescription:
"the lever is exit geometry" now reads *exit geometry is where the bleed is set, not where edge
comes from*. (Committed `663434ae`, battery green — see the final micro-addendum below;
resolved from "pending the battery at session close.")

**3. The cost wedge, quantified.** **25.1% of winning PT touches** in `horizon_shadow` still
label 0 because the touch fails the cost stack. Pooled first-touch **P(PT) = 0.418**,
statistically at the geometric null **0.429** (= sl/(pt+sl) = 6/14 from the 8:6 barrier config),
while the **label rate ≈ 0.31**. The funnel doc's 42.9% and the label rate are **different
quantities** — now reconciled; citation hazard filed in
[[synthesis/open-contradictions-register]] #16. See [[concepts/cost-to-volatility-ratio]].

**4. Per-asset ladder vs the null.** The only cells above the 0.429 first-touch null:
**BTC h=48: 0.482 [0.448, 0.517]** and **BTC h=96: 0.479 [0.448, 0.510]** — multiple-testing
caveat, two cells out of a ladder. Below null: **LTC h=48/96 ≈ 0.10**, **FLOW ≈ 0.33**. The
per-asset-tuning claim in [[sources/mdpi-label-driven-mhs]] has something to grab **only in the
BTC cells**.

**5. Fill-simulator calibration is off 9x.** XV-021: `passive_base_prob` **measured 0.048 vs
configured 0.450** — the sim fills resting limit orders **9x too often**, so paper P&L is
optimistic on the fill side. ~~**Deliberately not changed mid-cohort**; docketed for after the
cohort fills.~~ *Overridden in the third addendum below — shipped `8e5455e8` mid-cohort with the
execution-regime boundary recorded* ([[synthesis/owed-measurements]]).

**6. NVIDIA ai-model-distillation blueprint — irrelevant.** Analyzed (cloned to
`Documents/liquiditybot/`): LLM distillation for financial **news classification** on NeMo
microservices; no price-series content; its data flywheel pattern is already implemented by the
bot's retrain governor and model registry. Only hypothetical fit: serving a news classifier IF
sentiment features are ever enabled. No adoption.

**7. Cohort: 11/50; the post-432 window is unreadable.** Post-432 wins **0%, Wilson
[0, 25.9%]** — no verdict possible; the hold continues
([[comparisons/horizon-96-vs-24-bars]]).

**8. `label_transfer_filter` repaired — verdict NO ANALOGUE.** The filter now refuses
non-analogue transfer: the closest old-era/new-era pair is **4.5x off the 18x concurrency
target**. A **Kish-on-uniform bug** was fixed (the ESS check had applied the Kish formula to
uniform weights, which just returns the raw count; corrected to the weight sum).
**[[concepts/era-exclusion|Era exclusion]] stands** — no old-era rows enter the new era.

**9. Injection policy restated (binding).** The wiki gets findings; the corpus gets **nothing
synthetic and nothing relabeled, ever**; config geometry is unchanged (cohort hold + no
surviving candidate from the geometry search). See [[synthesis/governance-doctrine]].

**10. Sources ingested** to `raw/research/`: the MDPI label-driven MHS paper
([[sources/mdpi-label-driven-mhs]]), the Lund meta-labeling thesis
([[sources/lund-meta-labeling]] — evidence FOR the standing rejection in
[[concepts/abstention-filters-ruled-out]]), and a failed-SSRN-fetch marker (SSRN 4032018, bot
wall — [[concepts/availability-failure-mode]]).

**11. Repo state.** Commits today: `f0120393`, `858c8d71`, `483f6727`, `8062f46a`, and
(final micro-addendum) `663434ae` — `geometry_search.py`, battery green; the pending-battery
note is resolved. **Local is AHEAD of origin — deploys stall until the operator pushes.**

## Final micro-addendum (2026-08-02, session close)

**1. `geometry_search.py` committed — `663434ae`, battery green.** The second addendum's
"commit pending the battery" note is resolved. The full commit list for the day is
`f0120393`, `858c8d71`, `483f6727`, `8062f46a`, `663434ae` — all **local-only until the
operator pushes**.

**2. Operator directive — the wiki is the truth (filed as binding governance).** Issued
verbatim this session:

> "From now on the corpus's Wiki is the truth and everything that is determined correct or has
> been determined correct needs to be injected into the corpus's wiki."

Filed as [[synthesis/governance-doctrine]] **rule 12**, with the operating clauses: every
**confirmed** finding — measured, battery-green, committed — is filed into this wiki
**same-session**; **hypotheses enter only as owed measurements**
([[synthesis/owed-measurements]]), never as facts; and the wiki is **not** the training corpus —
rule 11 still holds: nothing synthetic or relabeled ever enters `signal_history`.

**3. Cost-wedge correction provenance.** `geometry_search`'s own section 2 initially conflated
**label-space with touch-space** — the exact wrong-quantity mistake that
[[synthesis/open-contradictions-register]] #16 warns about — and was **corrected before commit**;
the `663434ae` commit message records the mistake explicitly as a citation hazard. The hazard is
real enough to have bitten the tool that quantified it.

## Third addendum (2026-08-02, follow-on session) — honest fills shipped, risk-posture directive, deletion refused

**1. HONEST FILLS SHIPPED — commit `8e5455e8`, battery green (pytest 3289/1, smoke 219,
assurance 49).** `order_manager.sim_fill.passive_base_prob` **0.45 → 0.048** — the XV-021
**measured market trade-through rate** (22,854 resting-limit trials, Wilson **[0.046, 0.050]**).
The sim no longer fills resting orders **9x too often**. This closes
[[synthesis/owed-measurements]] item 13b **ahead of its original post-cohort trigger** — a
conscious override, recorded with its consequences:

- **Paper entry rate will drop sharply — that IS the honest rate.** A starving paper book under
  honest fills is a **truthful outcome**, not a regression to fix by re-flattering the simulator.
- **The commit timestamp is an execution-regime boundary INSIDE the 432-bar cohort.** The first
  11 closes were earned under flattered fills; the cohort's n=50 verdict **must be read across
  this boundary** ([[comparisons/horizon-96-vs-24-bars]]).
- **The XV-022 form-misspecification caveat is carried, not resolved:** 0.048 is the
  **conservative end of the [0.048, 0.082] band**, and the exponential fill-probability form
  itself needs replacement eventually — new owed item
  ([[synthesis/owed-measurements]] 13c).

**2. Four QA harnesses were silently riding the shipped constant.** They had declared
"deterministic fill" via `queue_aware=False` while inheriting whatever `passive_base_prob`
shipped — the same **absence-of-a-key lesson class** as the path-fallback contamination
([[concepts/default-path-fallback-writes]]): absence of a pinned value is not absence of a
dependency. Fixed by pinning `passive_base_prob=1.0` explicitly alongside `queue_aware=False`;
fill realism keeps dedicated coverage in `test_sim_fill_queue`.

**3. Deliberately NOT changed: fee constants stay 25/40 (bps) vs Kraken's published 16/26.**
Overstating cost is the **safe direction** — the one-directional logic of
[[concepts/cost-truth]] (only *under*-pricing reality earns a DANGEROUS verdict). Fill
probability had to move because there the error was in the *flattering* direction.

**4. Operator directive — RISK POSTURE (filed as doctrine).** Issued 2026-08-02, verbatim
intent: the bot must trade **as if real rent-money is on the line at all times**, vigilant to
never miss rent from a bad trade, **AND** must know rent gets paid **through profitable
trades**, so it cannot be afraid of calculated risk. Filed as
[[synthesis/risk-posture-doctrine]] — survival floor inviolable and already mechanized; idle
capital also fails the rent test; calculated risk = EV-positive by measurement, never a
loosened floor.

**5. Session Q&A — nothing deletable would help; deletion refused by design.** Operator asked
whether any convicted/quarantined records were recoverable or wrongly convicted, and whether
deleting anything from the bot's data or session memory would help profit. Answers, measured:
**none recoverable, none wrongly convicted** — audit-crossref re-check of the quarantined rows:
**0/136** live (64 + 72 quarantined rows, all confirmed fixture); **nothing deletable from bot
or session memory would help profit**; and **deletion of learning data is refused by design**
([[synthesis/governance-doctrine]] rule 8 — nothing is ever deleted; corrections are
reweightings and load-time views).

**6. Repo state.** Seven commits today: `f0120393`, `858c8d71`, `483f6727`, `8062f46a`,
`663434ae`, `8e5455e8`, plus one from the earlier session. **All local-only until the operator
pushes — deploys stall.**

## What this supersedes
- [[synthesis/the-money-path-thesis]] — "cost is the binding constraint" corrected: necessary, not
  sufficient. The binding term is [[concepts/payoff-asymmetry]].
- [[sources/goals-mindset-review]]'s attribution to "plain signal underperformance" — the per-fill
  hit rate is 57.5%; the signal is not the defect, the sizes are.
- The tail-risk reading of the loss distribution — fabricated-trade artifact.
- "The three options, none taken" — option 1 (lengthen horizon) was taken 2026-08-01 as the
  pre-registered 432-bar experiment, before research ranked it the weakest lever. It holds to n=50.
- *(Second addendum)* the "87% positive MFE" figure — diffusion per the random-entry control;
  never cite as evidence of timing skill.
- *(Second addendum)* "the lever is exit geometry" read as an edge source — bounded: exit design
  minimizes bleed, does not create edge (no surviving bracket in the pre-registered grid).
- *(Third addendum)* the second addendum's "XV-021 deliberately not changed mid-cohort; docketed
  post-cohort" — **consciously overridden**: honest fills shipped `8e5455e8` mid-cohort, with the
  execution-regime boundary recorded so the cohort verdict is read across it.
- *(Third addendum)* any pre-`8e5455e8` paper fill-rate or entry-rate statistic — measured under a
  fill simulator 9x too generous to resting orders; qualify by regime side.

## Related
[[sources/test-suite-outputs-contamination]] · [[concepts/default-path-fallback-writes]] ·
[[concepts/payoff-asymmetry]] · [[concepts/abstention-filters-ruled-out]] ·
[[concepts/iron-law-of-debugging]] · [[synthesis/learning-pipeline-arc]]
