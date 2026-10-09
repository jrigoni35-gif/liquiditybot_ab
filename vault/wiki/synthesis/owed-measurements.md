---
title: Owed Measurements
category: synthesis
summary: "Every explicitly deferred, unverified, or unresolved measurement in the corpus, with what would close it — as of 2026-08-10 the ADVERSARIAL-AUDIT DOCKET runs 52-61, every item of which points the same flattering direction. ITEM 57 CLOSED 2026-08-10 by aeeaae36 as EXECUTION-ERA BOUNDARY #4, the docket's largest single distortion: the fill sim modelled ONE market crossing with TWO mechanisms (calibrate_fills.py measures f = how often the market crossed a hypothetical resting limit, invert_base_prob solves passive_base_prob so the HAZARD ALONE reproduces f, and _poll_dry then ALSO filled deterministically on the very event f counts — and because the hazard only ran INSIDE `if book:` it was purely additive, never the 'conservative floor' the 08-08 filing called it). 1-(1-f)^2 = 2f-f^2 = 21.96% vs an 11.66% target against a ledger-measured 22.30%, 1.88x at the touch and approaching 2x as f FALLS. THE 08-08 DISPOSITION OF ITEM 40(b) IS RETRACTED — the double-count had been correctly named on 08-07 and was talked away the next morning, so the self-flattery gradient reached the ADJUDICATION, not just the measurement. Two residuals: 57b (recalibrate conditional on no cross — folds into 40b/XV-023, no new code minted) and NEW 61 (MP-7 queue gating is now INERT, created by the fix and deliberately unfixed so the change axis stays single). THE DOCKET NOW RUNS 52-64 (2026-08-10 evening, the $800-stressor session): 62 = the fills.csv restart-replay duplicate guard, registered and SHIPPED the same day (6fe6d98d, OM-085); 63 = the raw websocket book capture, the ONLY instrument that can measure intra-poll fill bias (challenge hardening #1 closed as an HONEST NEGATIVE — the recordings sit inside the same 5.00s fast poll), REGISTERED not started; 64 = the month-rollover→ratchet escalation-loss crash window, documented and deliberately unfixed (benign: detectable as RP-071 without RP-072, conservative: under-escalates). Still open: 52 (perf ledger AND breaker blind to the hedge book — counterfactual MEASURED, gate semantics OPERATOR-OWNED), 54 (probe/conviction split SHIPPED and INERT), 55 (PARTIAL — board regeneration owed), 59 (status-schema/fixture drift), 60 (31 dust legs to 1.17e-09 ETH), 61 (its fix now explicitly fenced by the era-4 accrual moratorium — it mints a boundary), 63, 64. CLOSED 2026-08-09 by 415af0f9: 53 and 56; a by-reason skip counter survives both as 53-residual. CLOSED 2026-08-10: 62 (same-day ship). EXTENDED TO 52-66 at the Grand Synthesis filing (directive-20260811): 65 = the trade-path ledger's paths_path fallback left five harnesses writing to the production default and a QA fixture row (2000,p1,ETH — the test_telemetry_fixes F1 thesis, byte-for-byte) is ALREADY IN outputs/trade_paths.csv, found by the filing's own verification — Phase B parameterizes from that exact file, so battery 14 must not land green over it; 66 = the synthesis trigger itself (academic sweep, engineering-precedents sweep, battery 14 — none landed at filing, the directive does not fire until all three do). CLOSED 2026-08-10 late: 65 (2602371b, same commit as the ledger — row QUARANTINED not deleted (trade_paths.csv.quarantine_qa_1786), five harnesses to tmp_path, and battery 14 did NOT land green over it: RED via the conftest production-outputs tripwire, the tripwire's FIRST confirmed catch, so the contamination was caught twice independently). 66 SATISFIED 2026-08-10 → SYNTHESIS DELIVERED: both sweeps filed (sweep-20260811-academic-stops, sweep-20260811-engineering-precedents), battery 15 ALL GREEN with BATCH_EXIT=0 verified directly, and the deliverable is grand-synthesis-algorithm-package (ALGO-1..4 Tier-1 SAFE with ALGO-4 shipped; ALGO-5..7 the geometry-epoch package PENDING the operator's timing adjudication = future cut #7; five NOT-ADOPTED with reasons). Filed with it per rule 16: the session first read battery 14's TASK-wrapper exit instead of BATCH_EXIT — owed-44's lying-gate class, SECOND occurrence that night, self-caught; both markers now checked. EXTENDED TO 52-67 at the cut-#7 session (2026-08-11): the geometry-epoch adjudication LANDED as the CDO-review split — cut #7 MINTED 2026-08-11T01:33:50Z (e7d5ca1a: Osler widen-beyond flip + ALGO-6 pins, at the free cohort reset, zero closes since the capital epoch) — and NEW 67 = the ALGO-5 amendment (replay-parameterized stop widths + the time-decay ladder at ~30 uncensored trade paths), PRE-NAMED in the moratorium law (ee7a94a2) as the next boundary-minting adjudication; battery 16's false RED (a pin threshold from a head-truncated grep) filed with owed-44's class as EVIDENCE TRUNCATION, both polarities now on record. EXTENDED TO 52-69 at the 2026-08-11 since-6am audit (wf_54d5cbd8-caf): 68 = long-book live rows missing post-migration schema columns (the ledger audit's one OPEN anomaly — the others adjudicated: 138s equity lag BENIGN, PAXG tb_time/h432 BY DESIGN, orphan-close postmortem undercount FIXED same-audit with degraded orphan_close rows); 69 = the h432 anti-momentum pattern (momentum-agreeing trades win LESS in both direction cohorts — found by the failed data-lens refuter of the backwards-derivative claim) owed a re-measurement on the post-epoch cohort, disaggregated, before anything consumes it. APPLY-BATCH 66744ed1 (battery 19 green, 3602 tests, deployed): 68 CLOSED — the diagnosis sharpened to a DISCARDED VALUE (the long-book entry path computed _feature_extras and threw it away, so every long-book live row shipped blank avail_*/quotes_frozen); meta[avail] now threads from the SAME extras dict the features were built from, pinned in test_long_book_integration.py; the audit's two blank ETH/BTC rows were ALSO legacy tuple-shape, but the writer defect was real and current. 69 INSTRUMENTED, STILL OPEN — defensive_cadence_report.py §2b prints the split with the side-relative caveat and lifetime-POOLED vs since-capital-epoch tables; first run h432-only pooled: MONOTONE gradient both directions (longs 30.9/35.3/41.8, shorts 25.9/37.1/47.4), STEEPER than the audit's all-era numbers, while the post-epoch clean cohort (n=36) leans OPPOSITE (longs-with 81.8% n=11) — a LEAD until clean accrual is real. Still open after the batch: 52, 54, 55, 59, 60, 61, 63, 64, 67, 69. EXTENDED TO 52-72 at the 2026-08-12 lockout filing (the 25-hour RP-041 no-trade incident, session-20260812-weekly-anchor-lockout): 70 = the 60 'capped' can_enter=False dispositions of the incident's 118-candidate veto-stack read — source unpinned, and the buckets sum to 113 of 118 so the residual 5 belong to the same diagnosis; 71 = the SZ-050 anomaly (dd 7.9% while flat at $800, MTM base ~737 unexplained, single occurrence — WATCH item); 72 = the reset-completeness test enumerating every calendar/dollar-anchored persisted section (the reset sweep's THIRD member in three days — money counters, perf window, now loss-budget anchors, the last found by 25h of production silence; concepts/reset-completeness). Still open: 52, 54, 55, 59, 60, 61, 63, 64, 67, 69, 70, 71, 72. EXTENDED TO 52-83 at the 2026-08-16 catch-up filing (session-20260816-catchup-08-12-to-08-16): 78 = CUT7_TS is 400 SECONDS early (1786411630.0 is 01:27:10Z, not the 01:33:50Z its comment certifies; correct value 1786412030.0) so every geometry-side statistic defensive_cadence_report cuts there is cut 6m40s early, and item 69's split was measured through it; 79 = cohort_eval's capital-epoch amendment states '3 closes' where six re-derive (benign reading available, NO effect on n, registered because it is a PRE-REGISTRATION); 80 = the red-team panel is NOT MANDATED anywhere (zero hits in CLAUDE.md / settings / hooks / README) so the anti-agreement mechanism binds nothing — a LAW change, operator-owned; 81 = the era-4 readout needs a recorded RUNNING-BINARY sha (the live tree sat at 21769fb8 until the 08-12 fast-forward and boundaries #3/#4 + cut #7 are not its ancestors) and max_concurrent_positions is declared EPOCH-MINTING because it sets n_eff and therefore the resolution floor; 82 = DECISION-GRADE — at n=50 on today's measured sd 2.559128% (vs the ~0.5% the registration assumed, 5.1x) the resolvable floor is 1.263665% at 2*SE and 1.770394% at 80% power against an observed gross mean of +0.657656%, so the gate fires on a quantity 1.92x (or 2.69x) BELOW ITS OWN NOISE, and the source document never names which statistical convention its signature line commits to (the two differ by 40.1%); 83 = two [MEASURED] tags disagree (-0.4981% vs -0.4975%) on the SAME read and nobody re-ran it. ALSO CORRECTED 2026-08-16: item 2 (the anti-predictive selection result) is REFUTED, not open — wrong null for a censored sample. AMENDED THE SAME DAY BY THE CORRECTION PASS: 82(b) NEW — cohort_eval's gross_se_pct uses a POPULATION (n-denominator) sd, a SECOND optimism independent of the nominal-vs-effective-n one, understating the resolution floor by 3.28% in the FLATTERING direction (2*SE ratio 1.9215x -> 1.9845x, so item 82 gets STRONGER); it must be NAMED in the readout, never patched mid-accrual, because the registration is a measurement standard. 83 NARROWED — the two figures are NOT era-4 net mean but geometry_breakeven.expectancy_pct, read from the LIVE outputs/signal_history.csv (cohort_eval.py:390/:648), which grew between two reads 34 seconds apart: 371 rows/-0.4975% -> 435/-0.5048% -> 446/-0.5385%; era-4's ACTUAL net mean is -0.030137595811143666% with NO prior published comparison point [UNKNOWN]; the drift supplies a candidate MECHANISM [I] for two documents disagreeing under one copied stamp, and the residue (why they differ at all) stays OPEN. Still open: 52, 54, 55, 59, 60, 61, 63, 64, 67, 69, 70, 71, 72, 78, 79, 80, 81, 82, 82(b), 83. EXTENDED TO 94-96 at the 2026-08-21 manip-gate filing (session-20260821-manip-gate-and-live-readiness): 94 = the SZ-045 STAMP and the manip_suspect FEATURE disagree on the same row (Jaccard 0.462; 25.6% of stamped rows record a sub-threshold feature) so NO efficacy claim about the gate can be made from signal_history until the two are reconciled at write time; 95 = a DISCRIMINATING FEATURE for the spoof detector, which failed paired injection (honest repricing and true layering both score 0.949/spoofy at matched cadence) — BOUNDARY class, readout docket, never a mid-era edit; 96 = the PRODUCTION FREQUENCY of that trend-shaped false positive, unmeasured (the injection proves capability, not rate; the 2026-08-20 melt-up is the natural window). Also recorded there: item 82's shape RECURRED at n=33 with the opposite sign — effective n 9.9 of 33, resolvable floor ~1.7033% vs observed gross +1.1820%. EXTENDED TO 97-100 the same day by the rule-21/METHOD filing: 97 = close the cost-stack investigation (434 positions, mean gross +0.0733% POSITIVE vs a 0.717% configured fee stack, net -0.6440% - single-route, uncut against the boundaries, no effective n, no snapshot stamp, refuters R1-R5 unrun; it is the settle-condition of a PROVISIONAL page and reframes the money-path thesis); 98 = SAFE, the STRUCK 16/26 Kraken schedule is still hard-coded at scripts/cost_attribution.py:76-77 driving two counterfactual rows against a schedule that does not exist, with a :74-75 comment asserting a conservatism direction that is INVERTED at the true Tier-1 40/80 - third recurrence, and the correction makes 97 WORSE (~16x not ~10x); 99 = the 3.7bps implied-fee residual plus a 60% taker share sitting ABOVE the 50% structural ceiling of a limit-only-entry bot (vs 41.87% measured 2026-08-02, a +18pp mix drift); 100 = declare a status on the ~204 UNDECLARED pages PAGE BY PAGE as each is next touched - deliberately NOT a bulk pass, because bulk-stamping SETTLED is the orphan-claim failure at scale. EXTENDED TO 52-106 at the 2026-08-28 cut-#8 prestige filing: 104 → MERGED-LIVE at the boundary (control-arm tag 7b19181d + shadow learner d64ad030 inside the 4e502478 bundle; first live tagged row NOT yet observed — owed poll — then CTRL-2 + accrued minority-arm rows close it); 106 = QT-1, the quant_trials fee mirror (TIER_CFG est_fee_bps 40 vs deployed 80 — measured: mirroring FAILS G5 0.574 vs 0.606, the #103 T6 shape; conscious re-baseline adjudication owed, and until it lands G1-G5 greens are not deployed-geometry evidence). EXTENDED TO 52-111 at the 2026-08-30 cut-#9 / audit-wave filing: 106 gains a RIDER (cut #9 moved deployed est_fee_bps 80 -> 38, so the harness-vs-deployed drift NARROWED 40bps -> 2bps and the harness is near-coherent again BY ACCIDENT, not by adjudication - but the G5 0.574-vs-0.606 failure was measured against the 80bps mirror and has NOT been re-run at 38, so the gate effect is [UNKNOWN] and the item stays OPEN); 107 = ERA6-COUNT-1 (no tool computes era-6 accrual; cohort_eval prints accrual 72/50 at printed line 39 of 144 which is the pre-registered era-4 population pooling cuts 7/8/9 - NOT to be fixed by filtering the pre-registered gate; correction against the item own interest: MIXED(both) prints at line 40, one line below the headline, so the reader-never-sees-it argument is weaker than first written); 108 = MLSEC-1 [HIGH], ml/registry.py _record_hash is an UNKEYED public sha256 so a forged well-formed chained row makes verify_chain report ok=True chain intact and verify() ok=True - the swapped artifact is POSITIVELY ATTESTED, so reject-on-ok-is-not-True DOES NOT CLOSE IT (keyed MAC class only); severity rests on a PARTIAL-WRITE threat model, COHORT-RESETTING, NOT fixed; 109 = PAGER-ROOT-1, the Grafana root route still points at receiver empty (0 integrations) so the rule-#5 trap is ARMED - OPERATOR DECISION OWED, plus the residual that error=None proves mailer ACCEPTANCE, not inbox-vs-spam; 110 = ERA6-MEMBERSHIP-1 (4 trips under stamp-purity AND entry-time, SET-EQUAL; 7 under any-leg AND close-time - operator owns the rule); 111 = ATLAS-REDERIVE-1 (the public-record atlas stats came from a session-scoped scratchpad script that is not in the repo and will be GC-ed; closed forms recorded inline on the page so the numbers can be regenerated)"
tags: [register, open-questions, backlog]
sources: 60
updated: 2026-09-18
---

# Owed Measurements

What the corpus itself says is not yet known. Ordered by consequence.

## Tier 1 — decides the product
0. ~~**The random-entry control on MFE.** Sample entries uniformly at random at the same horizon;
   compute identical MFE statistics. If random entries also reach positive MFE ~87% of the time,
   **there is no signal and everything downstream is moot.** Named "highest information per hour
   available" and never run.~~ **CLOSED 2026-08-02 (late session) — NULL.**
   `scripts/random_entry_control.py` (commit `8062f46a`): 51 real trades vs **200 seeded matched
   controls each** on real recorded 5-minute Kraken OHLC. Real entries' mean MFE percentile
   **0.516 [0.439, 0.594]**; control median MFE **+0.285%** vs real **+0.246%**. **No timing
   signal** — the 87%-positive-MFE figure was diffusion, as the null predicted. *Caveat:* n=51
   rules out a **large** edge only; the bound tightens as recordings accrue.
   ([[sources/session-20260802-digest]] second addendum)
1. **The money-path decision.** ~~Lengthen horizon / cut costs / select for volatility — pending an
   operator debate and vote.~~ **PARTIALLY CLOSED 2026-08-02:** option 1 shipped 2026-08-01 as the
   pre-registered 432-bar migration (commit `7566ea88`, holding at 6/50 closed trades) — before
   research ranked horizon extension the weakest lever. Still owed: the decision on the levers now
   ranked above it — maker-only execution, asymmetric entry banding, pooling across ~50 symbols —
   and on **exit geometry**, which [[concepts/payoff-asymmetry]] names as the binding lever.
1b. **The 432-bar cohort verdict.** `scripts/cohort_eval.py` renders nothing below 50 closed
   trades; at **17/50 on 08-05** — **first win recorded** (post-432 win rate **5.9%, Wilson
   [1.0%, 27.0%]**, was 0/15) — still unreadable, verdict still refused, correctly; the hold
   continues. *08-02 follow-on:* the honest-fills commit `8e5455e8`
   (`passive_base_prob` 0.45 → 0.048) is an **execution-regime boundary inside this cohort** —
   the first 11 closes were earned under fills 9x too generous; the n=50 verdict must be read
   across the boundary, and close rate will slow under the honest fill rate. *08-08 sequel:*
   the cohort now contains a **second** execution boundary — `3cfe0710` (era boundary #3, the
   fill-sim TTL normalization, item 40): closes entered before 2026-08-08 could carry
   compounding-simulator long-book fills; the n=50 verdict must be read across **both** cuts
   ([[sources/session-20260808-morning-batch]] §1).
   Tripwires while waiting, in priority order (statuses per
   [[sources/session-20260803-bug-sweep]]):
   1. ~~`ml.gate_stats.realized_closed` climbing from 0 (stuck at 0 = the realized-outcome loop is
      dead again). **08-03: still 0 after the first post-restart closes — WATCH ARMED, not
      adjudicable**: nearly all overnight closes were old-runner entries with no gates attached,
      plus one ambiguous ADA probe-path case. **Discriminator: the next few closes of organic
      post-restart entries** — 0 after those = fired; climbing = loop alive. **08-04: still
      armed, unchanged** — no organic post-restart closes yet
      ([[sources/session-20260804-deploy-gate]]).~~ **RESOLVED 08-04 late — WORKING.** The
      discriminator fired the good way: an **organically-entered post-restart position closed
      and `note_realized` credited it** — `realized_closed` moved **0 → 1**, proving the
      realized-outcome loop (`07d38a51`/`162c595c`) wired **end-to-end in production**:
      gates → `order.meta` → position → close → era-keyed ledger. `realized_active` is
      **correctly False** (1/25 toward activation). The earlier zero was old-runner entries
      carrying no gates — **exactly as hypothesized** on 08-03. *08-05: the ledger is
      accruing* — `realized_closed` **3** (was 1), `realized_base_rate` **0.3333**, **3/25
      toward activation**.
   2. Cohort progress — **17/50 (08-05), first win**: post-432 win rate 5.9%, Wilson
      [1.0%, 27.0%].
   3. ~~`outputs/auto_update.log` showing `rev 162c595c` deployed~~ — **SATISFIED 08-03**: the
      deploy chain is fully live and pushed, head = remote = `d67fd6a5`. *08-04 sequel:* the
      gate red-rejected the first external commits twice on a location-variant test — fixed
      same day (`242568fb`, [[concepts/location-invariant-tests]]); runner bounced via
      ControlChannel, **watcher confirmation pending**, gate expected to read current next
      cycle ([[sources/session-20260804-deploy-gate]]).
   4. `liquiditybot_era_mix_alarm` — **no longer firing on 08-03** (stood down, cause never
      named; was firing unexplained on 08-02).
2. > [!error] **REFUTED 2026-08-16 — WRONG NULL. Item 2 is CLOSED as a finding; what remains is the correction, not the measurement.**
   > `b/(a+b)` is the first-passage probability for an **unbounded-time** walk. These labels are
   > **censored at a vertical barrier** and the profit target sits FARTHER out (`a/b = 1.333`), so
   > it takes longer to reach and **censoring removes PT-bound paths preferentially**. Conditioning
   > on resolution **manufactures the negative sign** — [[concepts/tautological-instrument]]'s
   > fourth specimen class, in its purest form.
   > **Correct driftless null by exact lattice DP**, self-validating (it converges to the
   > closed-form **0.4286** at ~0% censoring): **0.3758 at 48.6% censoring · 0.2351 at 86.4%**.
   > The h24 sample was **87.8% censored**, so the observation is **ABOVE chance**, and z **flips
   > sign**. With the correct null AND the project's own effective-n standard applied: h24
   > **−7.05 → +0.58**, h432 **−4.21 → −1.47**, pooled **−3.24 → −0.63, p = 0.53**.
   > **The labeled bet is INDISTINGUISHABLE FROM CHANCE, not worse than it.** A residual h432
   > negative drift may exist (z = −1.47 at effective n) but is not significant, is measured on the
   > **fee-free candidate stream**, and has never been shown to transfer to the live book.
   > Method note kept because it is the reason to believe the refutation: the refuter attacked its
   > **own** method too — fitting sigma to observed censoring could in principle absorb a real
   > drift, so it checked, and `P(PT|resolved)` is **9.9x more drift-sensitive than the censoring
   > rate**, making the calibration a valid nuisance-parameter fit rather than a circular one.
   > — [[sources/cost-to-volatility-horizon-mismatch]] · [[concepts/wrong-null-calibration]] ·
   > [[sources/session-20260816-catchup-08-12-to-08-16]]

   ~~**The anti-predictive selection result.** Observed 29.7% profit-target-first vs a 42.9% chance
   baseline (z = -2.28), **at n=74, candidate-only** — the 7 live rows in the era have **zero
   resolutions**. Closes on live resolutions. "A flag, not a verdict."~~
   *08-02 late note — largely defused by the cost-wedge reconciliation:* pooled first-touch
   **P(PT) = 0.418 ≈ 0.429 null** (larger n, `horizon_shadow`), and the label rate ≈ 0.31 is
   depressed *mechanically* — **25.1% of winning PT touches fail the cost stack and label 0**.
   The 42.9% figure and the label rate are **different quantities**
   ([[synthesis/open-contradictions-register]] #16). Remaining question: whether any per-asset
   cell beats the touch null — only BTC h=48/96 do, multiple-testing caveat.
3. **The null-model floor.** Adjudicated **SHIP**, not yet shipped. Until it exists, nothing in the
   battery reports that every rung loses to a constant.

## Tier 2 — blocks a known fix
4. **The 20-36 minute probe-close cohort.** Three of eight bracket probes died too early for every known
   overlay, and no brief can name the mechanism. Instrument armed; under the
   [[concepts/iron-law-of-debugging]] no fix may be chosen until it fires.
5. **The harness G1 verdict** armed for 2026-07-25. **No document records its outcome.** Until then the
   live geometry runs on an unclosed argument.
6. **The entry collapse attribution.** Entries/day fell ~90% from 07-24 (27 -> 0 -> single digits). The
   proposed attribution to two gate codes is **explicitly not independently verified** — those codes are
   gate-path counters absent from the audit trail.
7. **Population-wide cost measurement.** ~~The DANGEROUS verdict rests on **n=16** from a file
   later found stale.~~ **LARGELY CLOSED 2026-08-02:** `scripts/breakeven_test.py` and
   `scripts/cost_attribution.py` now measure per-fill on the fully-quarantined ledger
   (post-`483f6727`, n=217 and growing): fee term 0.667% per round trip, mean gross −0.0501%,
   win 57.1%, payoff 0.561 vs 0.750 needed. Re-run rather than quote — `fills.csv` grows live.
   Remaining gap: reconciling this fourth cost number with the 0.50 / 0.65 / 0.86 trio
   ([[synthesis/open-contradictions-register]] #2).

## Tier 3 — instruments exist, data does not
8. **Fill-hazard time consistency.** Returned INSUFFICIENT_EVIDENCE; **366 of 366 tapes excluded**, zero
   fitted. The ~3.5x sim optimism remains unmeasured. Closes on recordings polled **at engine cadence**
   with enough polls to cover the timeout horizon. See [[concepts/honest-null-result]].
9. **The maker-leg venue fee tier** — n=0, unmeasurable without live credentials.
10. **The clean same-hyperparameter monotone-constraint comparison** — explicitly owed; the measured
    pairing confounds architecture with hyperparameters.

## Tier 4 — deferred with a named trigger
11. **Markout notional weighting** — needs a versioned persistence migration.
12. **Missing-data indicator columns** — a schema bump "not earned at 253 live rows"; gated on the
    liveness diagnostic showing the feeds alive.
13. **Measured Kelly shrinkage** — inert while sizing is floor-dominated; adopt when it leaves the floor.
13b. ~~**XV-021 fill-simulator calibration** — `passive_base_prob` **measured 0.048 vs configured
    0.450**: the sim fills resting limit orders **9x too often**, so paper P&L is optimistic on
    the fill side. **Deliberately not changed mid-cohort**; trigger = the 432-bar cohort
    filling.~~ **CLOSED 2026-08-02 (follow-on session) — SHIPPED ahead of trigger, commit
    `8e5455e8`, battery green.** `passive_base_prob` 0.45 → **0.048**, the XV-021 measured
    market trade-through rate (**22,854 resting-limit trials, Wilson [0.046, 0.050]**).
    Consequences recorded: paper entry rate will drop sharply (**that IS the honest rate**);
    the commit timestamp is an **execution-regime boundary inside the 432 cohort** (first 11
    closes under flattered fills — read the n=50 verdict across it, item 1b). The form caveat
    is carried, not resolved → item 13c.
    ([[sources/session-20260802-digest]] third addendum)
13c. **XV-022 fill-probability form replacement.** The shipped 0.048 is the **conservative end
    of the [0.048, 0.082] band** — the exponential fill-probability form itself is misspecified
    and needs replacement eventually. Closes on a re-derived functional form fitted to the
    trade-through data (and interacts with 23b's `calibrate_fills.py` re-run).
14. **Sequential bootstrap** — gated on a bagged family winning selection on merit.
15. **Per-asset win-rate-aware probe decay** — a named design gap; the existing breaker is only a rate
    limiter.
16. **CVaR return-deque persistence** — a ~10h post-restart warmup remains live.
17. **Multi-day risk-horizon extension** — flagged as a boundary, not planned.

## Tier 5 — research questions with no owner
18. **The strain-vs-rational-choice persistence test.** A stated "testable divergence" with **no
    experiment proposed**. See [[concepts/persistence-curve]].
19. **A shadow-vs-advise A/B on the one live detector** — called "the honest next step," not yet run.
20. **Whether a volatility estimator should be replaced** given observed touch rates ~50x the Gaussian
    implication.
21. **Whether cadence-pause gates earn their cost** — needed before adding more of them.

## Structural / hygiene
22. **Subprocess writes remain invisible** to the in-process write guard; the snapshot diff is the
    acceptance check. (The isolation *invariant* is now pinned by `tests/test_qa_isolation.py` —
    see [[concepts/default-path-fallback-writes]] — but that guards future writes, not past data.
    *08-05:* the invariant's reach widened to the replay family — replay/sweep/replay_gate now
    walk the one redirect, item 29a.)
23. ~~**Already-contaminated copies are not cleaned.**~~ **CLOSED for `fills.csv`, assessed for the
    rest (08-02 addendum, commit `483f6727`):**
    - `fills.csv` — **CLEAN, 637/637** rows crossref the hash-chained `audit.jsonl` by `order_id`
      (the decisive provenance signal — QA always redirected audit even while leaking fills).
      Total quarantined: 64 rows at `858c8d71` + **18 positions / 72 rows** in the residual sweep,
      attribution corrected to **battery smoke runs**.
    - `retrain_history.jsonl` — assessed **158/165 clean** on the 08-02 snapshot. (The 07-31 count
      of 305/306 fixtures was a different snapshot; the counts are not comparable — qualify by
      date.)
    - `outputs/models/registry.jsonl` — **97/129 fixtures**; mitigation is **filter-at-read-time**,
      not a rewrite.
    - `horizon_shadow.csv` — **58.8% proven clean; the rest undecidable** (no `order_id` to
      crossref). Treat undecidable rows as suspect. *(08-05: the still-open candidate writer —
      the un-isolated replay family — was closed by item 29a's fix `e7ebbf60`; this bounds
      future writes only, the past-rows assessment stands.)*
    - `meta_model.json` — not reported in the addendum sweep; status unchanged (unassessed).
23b. **`calibrate_fills.py` must be re-run on clean fills — STILL OWED.** It read the contaminated
    `fills.csv` to tune the fill simulator, so contamination **already fed forward** into simulator
    parameters; how far is unmeasured. The blocker is gone (the ledger is now 637/637 CLEAN); the
    re-run has simply not happened. *Note (08-02 follow-on):* the shipped `passive_base_prob`
    0.048 came from **XV-021's direct market trade-through measurement** (22,854 trials), not
    from `calibrate_fills.py` — so the honest-fills commit does not discharge this item.
24. **A pre/post-exclusion statistics mix** in the load-stats payload.
25. **A conscious re-decision** is explicitly owed on whether a missing status file should alarm or stay
    silent.
26. ~~**Dark-metrics boarding** (2026-08-05 telemetry audit, [[sources/telemetry-stack-audit]]) —
    ~2 dozen metrics are emitted but on no Grafana board. Priority order: (a) the audit-health
    pair `audit_dropped_writes` + `audit_tail_truncations` **and** `gauges_dropped_nonfinite`
    onto VITALS — the hash chain's own failure counters currently have no visual alarm;
    (b) `gate_divergence` (the `07d38a51` reward-misspecification watch, never displayed);
    (c) the era trio `era_rows`/`era_reason_rows`/`era_excl_armed` onto LEARNING BRAIN.~~
    **CLOSED (a) + (b) 2026-08-05 evening, commit `bc198aa5`** ([[sources/session-20260805-evening]]):
    the operator-ordered boards redesign gave `problem_solution` an **AUDIT & TELEMETRY INTEGRITY
    row** — `audit_dropped_writes`, `audit_tail_truncations`, `gauges_dropped_nonfinite` as PROBLEM
    tiles and **`gate_divergence` as a trend panel**, boarding the `07d38a51` **KNOWN-GAP
    instrument** for the first time. Through the **board generator**, as required; UIDs unchanged.
    Two follow-ons recorded rather than lost:
    - **The fixture gap, in reverse.** The synthetic status fixture **predated** the
      `gate_divergence` instrument, so `test_every_query_hits_an_emitted_metric` read the metric
      as *never emitted* and did not protect it. Fixture now carries the entry — the
      phantom-ghost lesson inverted (a stale fixture erases a metric that exists, where a static
      scan invents metrics that do not).
    - **The panel was wrong on arrival, and an adversarial pass caught it** (`46cdc19a`): the new
      `gate_divergence` panel wrapped a **bare `max()`** while `gc_pusher` emits the metric
      **per gate with a `{gate}` label** — one gate trending to −0.4 while another sits at +0.05
      plots the **+0.05 flatline**, hiding exactly the sustained trend the panel's own description
      tells the operator to watch for. Fixed to `max by (gate)` with a `{{gate}}` legend, pinned
      by a test so a bare `max()` cannot come back.
    **STILL OPEN: (c)** — the era trio `era_rows`/`era_reason_rows`/`era_excl_armed`
    ([[concepts/era-exclusion]]) is **not yet boarded**; closes on the same terms (generator only).
    Empty-panel hazard unchanged: an absent metric is indistinguishable from zero.
27. **The per-gate conversion instrument** (`07d38a51`'s own KNOWN GAP, corroborated by the
    telemetry audit) — the exploration-admission trio (SZ-047/SZ-051/SZ-049) is ≈47% of the
    recent audit stream while the gate→order conversion rate it implies is measured nowhere.
    Closes when a report-only per-gate conversion counter ships (instrument first, per the
    [[concepts/iron-law-of-debugging]] instrument pattern).
28. **Log-volume diet** — last 8k events 99.8% INFO with `regime` + `strategies` at 73% of
    Loki volume; owed a demotion/sampling decision for the two chatty namespaces. Closes on a
    conscious keep-or-diet decision recorded here (shipping cost + query noise vs diagnostic
    value).
29. ~~**The 2026-08-05 debug-sweep fix docket** ([[sources/session-20260805-debug-sweep]],
    report-only — every sub-item closes on an explicit fix/defer/won't-fix decision).~~
    **ADJUDICATED AND SHIPPED same day (2026-08-05): 7 of 8 FIXED in two battery-green
    commits — `e7ebbf60` (29a/29b) and `b409a24b` (29c/29e/29f/29g/29h) — head = remote =
    `b409a24b`; 29d DEFERRED, the docket's only open residue.** 8 new tests all written
    red-first against the unfixed code; battery **3310 passed / 1 skipped**, smoke 219,
    assurance 49, ruff + compileall clean. Full mechanisms on the source page's
    fix-disposition section; per-sub-item decisions:
    - **29a FIXED (`e7ebbf60`)** — replay/sweep/replay_gate now route through the canonical
      `qa_redirect_paths` via new `prepare_replay_config` (**one list, never two** — the
      hand-rolled replay list is gone), and `sweep.py` gained the
      `configure_audit`/`configure_registry` isolation it **never had**: until this fix a
      sweep run appended replayed dispositions to the **production audit trail and model
      registry**. Pinned by new replay-family tests in `test_qa_isolation.py` (real config
      through the real replay preparation, all five known-leak keys + the retrain rebind);
      docstring updated to **EIGHT** instances. The 8th instance of
      [[concepts/default-path-fallback-writes]] is **CLOSED — the first caught before
      corrupting a result**. Going forward this also closes the "still-open candidate
      writer" on `horizon_shadow.csv` (item 23's *past-data* assessment unchanged).
    - **29b FIXED (`e7ebbf60`)** — `train_meta.py` `_deploy_challenger` now **re-reads the
      freshest `state.json` at persist time and mutates only the monitor section**; the
      runner's next snapshot supersedes even that one read-write pair. *Accuracy
      correction found during implementation:* the sweep's "minutes of training" window
      was wrong — `load_raw` happens **post-training**, so the actual window was the
      **seconds of rescore+gate+save**; still a real clobber window vs the runner's 30s
      cadence, now shrunk to one read-write pair.
    - **29c FIXED (`b409a24b`)** — the fast_cycle close-out block factored **verbatim**
      into `_close_periods`, which **snapshots the moment a week/month boundary fires** —
      close + rollover land on disk together; the double-reserve-refill window is gone;
      mid-period cycles snapshot nothing extra.
    - **29d DEFERRED — the only open residue.** Per the standing 432-migration hold
      ("hold, do not retune"): candidate-pool saturation is a property of the in-flight
      experiment; stays a **report-only watch item** on
      [[comparisons/horizon-96-vs-24-bars]]; the fix-vs-accept decision re-opens
      post-cohort.
    - **29e FIXED (`b409a24b`)** — `SingleInstanceLock` stale-reclaim **re-reads the lock
      record immediately before the unlink and backs off on ANY change** — the
      unlink-after-recreate TOCTOU is closed.
    - **29f FIXED (`b409a24b`)** — two guards: a **rejected exit now counts an escalation
      attempt** (the ladder cannot freeze at rung 0), and a **non-finite computed exit
      price falls back mark → ref → entry** so `FW_INVALID_PRICE` is unreachable for
      exits — invariant #5 restored in the poisoned-feed corner
      ([[comparisons/stated-invariants-vs-audited-reality]]).
    - **29g FIXED (`b409a24b`)** — `gc_log_pusher.tick()` **drains the rotated
      `events.jsonl.1` tail before the offset reset**, provenance-checked via saved inode
      (a foreign `.1` is never guessed at), same at-least-once contract.
    - **29h FIXED (`b409a24b`)** — `append_fill` **heals a torn tail** (terminates the
      fragment so it isolates as one junk row csv consumers skip) and **fsyncs each row**,
      shrinking the torn window to the single row being written.

    **Two residual edges on 29g and 29h, found the same evening by an ADVERSARIAL review of
    these very fixes — both FIXED in `46cdc19a`** ([[sources/session-20260805-evening]]).
    Round-1 verdict first: **all seven fixes HOLD** under adversarial review. The residue:
    - **29h neighbor — `fills.csv` could still be born HEADERLESS** (`core/fill_ledger.py`).
      The heal covers a **torn final row**, not the **create-to-first-flush window**: a kill
      there leaves a 0-byte file, the next append saw `path.exists() == True`, skipped the
      header and wrote a **data row first**. `csv.DictReader` then silently **adopts that FILL
      as the header** and every consumer (`breakeven_test`, `cost_attribution`,
      `calibrate_fills`, `provenance_audit`, `random_entry_control`, `geometry_search`)
      misparses the whole ledger **with no error raised** — the same book of record behind the
      **27x** error ([[concepts/default-path-fallback-writes]]). Fixed: `new_file` counts
      **size 0 as new**.
    - **29g neighbor — `gc_log_pusher` saved new-generation offsets under the OLD inode.**
      `tick()` stat'd the file once, then `_drain_rotated` spends **seconds of network time**
      before the main file is opened; a rotation inside that window persisted the offsets
      against the **previous** inode, so the **next** tick's drain seeked `.1` at a **foreign
      offset and skipped its head** — a smaller instance of the hole 29g closed, and one
      **invisible to 29g's own provenance check**. Fixed: provenance from `os.fstat` on the
      **opened handle**.

30. ~~**The 2026-08-05 debug round-2 residue — the findings NOT fixed, filed with file:line
    and mechanism so they are not lost.**~~ **CLOSED 2026-08-05 (late evening) — ALL TEN FIXED
    in one commit, `4799bfc7`, head = remote.** Battery **pytest 3376 passed / 1 skipped, smoke
    219, assurance 49, ruff + compileall clean**. **Every sub-item carries a test written
    red-first against the unfixed code** — 44 new tests across seven new files plus one added to
    an existing file. Full narrative: [[sources/session-20260805-evening]] §5.

    *Filing context, preserved.* Round 2 ran **five parallel area agents** (data · risk · ml ·
    runner/deploy · order_manager) plus **A** (adversarial pass over the session's own commits)
    and **H** (board restructure), returning **27 findings**. The **five HIGH** ones shipped in
    `f3253f0d` (R2-1 remote-control terminal-state liveness · R2-2 `take_deferred` with zero
    production callers · R2-3 silent GTC venue orphans + new code **OM-090** · R2-4 in-sample CLI
    deploy gate · R2-5 deploy-seam model-verify race). The ten below were **deliberately not
    batched into a fix commit that would stop being reviewable** — and were then closed as their
    own commit, which is the same discipline applied in the other direction.

    **30a. ~~`ml/registry.py` has NO real hash chain.~~ FIXED — and it found an ELEVENTH bug.**
    *What was claimed:* `verify()` compared **one unauthenticated sha256 from the last matching
    row**, so deleting, reordering or editing the ledger was **undetectable**, and deleting
    `registry.jsonl` entirely downgraded every load to **"unknown provenance"** — which
    `reload()` **accepted**. The **ML-011 tamper gate degraded to a log line.**
    *What stands:* the ledger is now **genuinely hash-chained** — `prev` + `seq` + content hash,
    built the **same way [[entities/liquiditybot]]'s `core/audit.py` builds it**, not merely
    described with the same adjective. New `verify_chain()` walks the links, and **a broken chain
    now FAILS the load gate instead of authorizing it**. Pinned by `tests/test_registry_chain.py`
    (**9 tests**): edited row · deleted row · reordered rows · and the sharp one — **a rewritten
    row minting provenance for a swapped artifact**.
    > **The eleventh bug, found by a test for a different property.** Writing the torn-row case
    > surfaced a defect **nobody was looking for**: the registry ledger had the **same torn-row
    > fusion defect as the fills ledger** — a crash mid-append leaves a fragment, and the next
    > write **welds onto it**, taking a good record down with the bad one. Same heal applied
    > (terminate the torn tail, then fsync). This is the **THIRD instance** of the class
    > (`fills.csv` 29h · the fills create-window in `46cdc19a` · the registry here) and it now has
    > its own page: [[concepts/torn-append-fusion]].
    **This closes the citation hazard** that [[comparisons/stated-invariants-vs-audited-reality]]
    and [[synthesis/open-contradictions-register]] both carried: *"hash-chained"* is now true of
    `registry.jsonl` as well as `audit.jsonl`, by construction and by test.

    **30b. ~~`ml/monitor.py:206-219` — the Wilson credibility guard is ALGEBRAICALLY DEAD, and the
    baseline is an in-window oracle.~~ FIXED (both defects).**
    - *The dead guard.* `hit_deficit = raw_gap > max AND (promised − wilson_lcb) > max`. Since
      **`wilson_lcb ≤ observed` always**, `promised − lcb ≥ promised − observed = raw_gap`, so the
      second conjunct was **implied by the first and could never veto** — and it grew **MORE
      permissive as n fell**, inverting its own stated purpose. *Fixed* with a new
      **`wilson_ucb()`**: the promise must clear **even the most optimistic reading of outcomes**.
      That condition **implies** the raw-gap clause (so it can actually bind) and is correctly
      **HARDER at small n**, which is the direction the guard was written to want.
    - *The oracle baseline.* `baseline_brier` scored a constant equal to **the window's OWN
      realized mean** — an in-window oracle. An **all-loss 15-close window handed the baseline a
      clairvoyant 0.05** and convicted an honestly-calibrated model on its **first** evaluation.
      *Fixed* with new **`_prior_base_rate()`**, computed from **rows PREDATING the window only**,
      falling back to a neutral **0.5 at cold start** — a **weaker** baseline, therefore **slower
      to convict**, which is the right direction when the false positive is **killing a working
      model**.
    Pinned by `tests/test_monitor_credibility.py` (**9 tests**).
    > ⚠️ **Correction to this item's own filing — the 15-loss premise was WRONG.** The original
    > text above (and the first draft of the test) asserted that an ordinary **15-loss streak**
    > (put at "**~4-9%** at this corpus's base rates") kills an honest model. Against a **promised
    > 0.30**, fifteen straight losses is `0.70^15 ≈ **0.5%**` — a ~1-in-200 event **under the
    > model's own claim** — so **convicting is CORRECT there**, not a false positive. The test was
    > rewritten to pin the **actual** mechanism: an honest **~0.18** promise **survives** an
    > unlucky streak, and **the same shortfall is harder to indict at small n**. The defects were
    > real; the worked example filed alongside them was not. Filed per the vault rule that
    > retractions are first-class content — cf. [[concepts/wrong-null-calibration]], whose shape
    > this still is (the *baseline* was a null the model was never asked to beat).
    > **A test depended on the bug:** `tests/test_monitor_deescalate_deadband.py` needed a new
    > `_seeded()` helper, because its fixture had been passing on the **old oracle baseline**.

    **30c. ~~`risk/capital_manager.py:81` + `main.py:1965` — the profit-pool skim runs PER EXIT
    LEG, on entry-fee-inclusive `net`.~~ FIXED — the money item, and it was worse than filed.**
    *What was claimed:* the skim fired per leg on `net` rather than per trade, so a **+$16 tier-1
    leg on a trade that nets −$80 still moved ~$4.80 into locked savings/reserve**.
    *What the fix found:* **two fused defects, not one.** The per-leg `net` is **gross minus that
    leg's exit fee — NOT minus the slice's pro-rata entry fees** — so the skim ran on an
    **overstated base** *and* fired on **winning legs of trades that ended up losing**. Savings is
    **never clawed back**. With **tiered exits the normal trade shape**, trading cash bled
    **monotonically into locked pools as a function of gross winning legs**.
    *What stands:* the two concerns are **separated**. Cash still settles **per LEG** via
    `record_realized_profit(net, state, skim=False)` — correct, because entry fees already left
    cash at fill time via `record_entry_fee` — while the **three-way split now runs ONCE per
    closed trade** on the fully-net `total_net`, through new **`CapitalManager.skim_trade()`**,
    called in `_finalize_position` and **guarded like every other close-path step**. Pinned by
    `tests/test_pool_skim_per_trade.py` (**6 tests**) including **equity-conservation** and
    **no-double-booking** pins. Interaction with [[concepts/payoff-asymmetry]] closed: the book
    that is losing on payoff ratio is **no longer also draining trading cash into locked pools**.

    **30d. ~~`data/okx_feed.py:158` — deep history >2000 bars silently truncated.~~ FIXED.**
    `clean_candles`' **live-fetch cap** applied to **deliberate paginated requests** too, so
    `train_meta`'s bootstrap **asked ~10 days of 5m bars and got ~7 — with no log line**. Fixed
    with `max_n=len(raw)` for deliberate paginated requests (the live-fetch cap is untouched).
    `tests/test_deep_history_not_truncated.py` (**3 tests**).

    **30e. ~~`data/ws_feed.py:584` — the book is published to the live cache BEFORE checksum
    verification.~~ FIXED.** During the **post-mismatch resubscribe backoff**, every update frame
    **rebuilt from empty and republished**, serving a **phantom 1-5-level book stamped fresh** to
    stop and imbalance logic **on every frame**. `_verify_checksum` now **returns bool** and the
    caller **publishes only on True**. Unverifiable frames — **no checksum, or depth < 10** —
    publish as before, so the fix narrows to exactly the frames that can be judged.
    `tests/test_ws_verify_before_publish.py` (**6 tests**).

    **30f. ~~`scripts/auto_update.py:249` — `_FORCE_KILL_AFTER_SEC = 45` is shorter than the
    runner's OWN measured worst-case cycle stalls.~~ FIXED — grace **45s → 150s**.**
    `runner.py:386` documents **MEASURED** stalls of **88.1s / 55.5s / 50.2s** — **every one
    exceeded the 45s grace**, so deploys `taskkill`ed **HEALTHY** runners mid-cycle. This remains
    the **likely origin of the `audit_tail_truncations` counter** newly boarded by `bc198aa5`
    (item 26) — the *cause* now fixed after 29b/29h had shrunk the *consequences*
    ([[entities/auto-update]], [[entities/observability-sidecars]]).

    **30g. ~~`core/skimmer.py:251` — replace-hysteresis voids on every restart.~~ FIXED.**
    Sharper than filed: scores **were persisted but never read back**, so **every incumbent
    compared as 0.0** and a **0.55 candidate evicted a 0.90 incumbent — every 15-minute deploy**.
    The hysteresis was **void after every restart**, not merely weakened. Fixed by restoring the
    persisted scores; `tests/test_skimmer_hysteresis_restart.py` (**6 tests**). Consequence
    sharpened by the same evening's slot change: `max_extra` **6 → 5** for PAXG
    ([[synthesis/tangible-value-doctrine]]) means each remaining rotating slot matters more.

    **30h. ~~`scripts/session_import.py:261` — within-bundle duplicates both merge permanently.~~
    FIXED.** The seen-set was **never updated with accepted keys**, so two duplicates inside one
    bundle **both merged**; the corpus is **append-only, so nothing heals it**, and
    `corpus_sync --apply` runs **hourly, unattended**. `tests/test_session_import_dedupe.py`
    (**4 tests**).

    **30i. ~~`scripts/remote_control.py:324` — a transient `git-show` failure permanently rejects
    a valid command.~~ FIXED.** The exactly-once ledger recorded a **read** failure as a terminal
    **REJECT**. Read failures are now **left unledgered and retried**, bounded by the command's
    **own 30-minute expiry** — so a momentary git hiccup no longer consumes an emergency command,
    and a genuinely bad one still ages out. New test in `test_remote_control.py`. Same family as
    the R2-1 class fixed in `f3253f0d`: **an emergency command that silently does not run**
    ([[comparisons/stated-invariants-vs-audited-reality]]).

    **30j. ~~`runner.py:429` — a boot hang holds the lock FOREVER.~~ FIXED.** The heartbeat
    refreshed **unconditionally while `_last_progress_ts is None`**, so a runner wedged during
    boot looked alive indefinitely and **no supervisor or operator relaunch could reclaim the
    lock**. Now a **bounded boot grace measured from process start** — config key
    **`lock_boot_max_stall_sec`**, defaulting to **2x the running stall bound** (a normal engine
    build takes tens of seconds, so it only fires on a genuine hang). Compare
    [[concepts/liveness-by-output-cadence]] — liveness judged by a signal the wedged process is
    still emitting; here the signal is now **time-boxed**.

    **Near-misses verified OK in round 2 (record so they are not re-investigated):** walkforward
    boundary purge · labeling edge cases · `rescore_frozen` watermark · `_close_periods` vs fills
    snapshot · exit-price fallback vs firewall · the 29h heal's `\r\n` vs strict readers ·
    `SingleInstanceLock` livelock bound · Kraken forming-bar cut · OKX pagination cursor · torn
    bundle materialization · status/equity atomicity.

    **Clean areas (a positive result worth filing):** `ml/labeling.py` and `ml/walkforward.py`
    came back **CLEAN — no reportable bugs**, as did `data/_http.py` and `data/recording.py`.
    The labeling and validation core is the part of the engine the corpus leans on hardest
    ([[entities/lopez-de-prado]], [[concepts/triple-barrier-labeling]]); a two-agent adversarial
    pass finding nothing there is evidence, not silence.

31. ~~**The torn-append sweep across ALL append-only writers.**~~ **CLOSED 2026-08-06, commit
    `ee0ac4ad`** — and closed in the exact form [[concepts/torn-append-fusion]] had named:
    *"a sweep that asserts the invariant across all append-only writers — rather than fixing them
    one crash at a time."* The heal is now **one primitive**, `core/runtime.durable_append`,
    placed beside `atomic_write_json` as its append-mode sibling, and **adopted by eight writers**
    (`signal_history.csv` via both of its independent appenders, `horizon_shadow.csv`,
    `retrain_history.jsonl`, `context_history.jsonl`, `equity.csv`, `postmortem_summary.csv`, and
    the weekly/monthly period ledgers). **All ten files clean on disk at the sweep** — 9,692
    corpus rows · 145,576 equity rows · 29,013 audit records · 25,039 events · 44 rotated
    generations, **zero fusions**. **Preventive, not remedial.**
    ~~**Residual, smaller than what closed:** the invariant is enforced by **adoption, not by a
    gate**… **What would close it:** a repo-wide static assertion that no bare `open(..., "a")`
    exists outside `core/runtime`.~~ **RESIDUAL CLOSED 2026-08-06, same day, commit `0e30ca09`**
    — `tests/test_append_invariant.py` is that static assertion, AST-based over the repo's ten
    non-test packages plus `main.py`/`runner.py`, with a **13-entry reasoned allowlist**, proven
    to bite by injecting a bare append into `ml/interpret.py`. **`core/events.jsonl` is now a
    reasoned exemption** (calling the primitive inside a logging handler would re-enter it), not
    an unexplained hole. **Battery 3406 passed / 1 skipped, 8 new; gate re-run at filing: 8
    passed.** ([[sources/session-20260806-append-gate]])

    > **The gate's first run found a live instance the sweep had missed** —
    > `scripts/session_import.py:366`, a **THIRD independent appender to `signal_history.csv`**,
    > bare append + the size-0 header bug, running **hourly and unattended** under
    > `corpus_sync --apply`. The residual had been written as a *discipline* gap; it was also a
    > **coverage** gap. See [[concepts/adoption-is-not-enforcement]].

    **New residual, smaller again — three named holes in the gate itself, none measured:**
    (a) the allowlist is **per-file, not per-call-site**, so `scripts/corpus_sync.py` — exempt for
    its text log while being the corpus's **second data appender**, and **absent from the positive
    `durable_append` assertion list** — could have that call replaced by a bare append with the
    **battery still green**; (b) `SCANNED_DIRS` is a **hardcoded tuple**, correct today, so a new
    top-level package is unscanned until someone adds it; (c) `tests/` is **deliberately excluded**
    (a test that fabricates a torn tail must append), which is exactly where
    [[concepts/default-path-fallback-writes]] lives. **What would close (a):** add `corpus_sync`'s
    data site to the positive list, or make the allowlist key on `(file, lineno)`. **What would
    close (b):** derive the scan scope from the filesystem and assert the derived set matches a
    pinned list. **(c) is a conscious deviation, not an omission** — recorded so it is not
    re-discovered as a bug.

    > **(a) HALF-CLOSED the next day, `5c111962`** — carried in the hedge-thrash commit, unrelated
    > to its subject ([[sources/session-20260806-hedge-thrash]] §7b). The positive
    > `durable_append` assertion list gained **`scripts/corpus_sync.py`**, plus `core/runtime.py`
    > and `main.py`, with a docstring stating exactly why the list is **not** the complement of the
    > allowlist: `corpus_sync` is exempt **per-FILE** for its `:57` text log while being the
    > corpus's **second independent data appender at `:160`**, so the negative gate alone would
    > stay green if that data append regressed. **The named exposure is now covered; the
    > per-file-vs-per-call-site granularity that created it is unchanged**, and `core/fill_ledger.py`,
    > `ml/registry.py` and `core/audit.py` remain wholesale-exempt while writing the three most
    > valuable ledgers in the repo. **(b) and (c) stand.**

32. **ML-084's first live readings.** The new `ML_UNLABELED_CLOSE` counter
    ([[entities/reason-code-registry]]) makes ground-truth attrition visible for the first time —
    but **it has no baseline yet**. The 08-06 audit established the *historical* answer by forensic
    reconstruction (**34 quarantined QA fills + 3 `FEATURE_SCHEMA_VERSION` drops, nothing
    bleeding**); the instrument itself has produced **no reading**. **What would close it:** a
    week of live cadence with the counter's value recorded, establishing whether the steady-state
    rate is **zero** — as the reconstruction implies it should be, since every known cause is a
    deliberate schema bump — or whether an unexplained residue exists. **Until then, do not cite
    the 08-06 reconstruction as a rate**; it is a one-time census, not a monitored quantity.

33. **A priced bracket-divergence reading.** The labeled-vs-traded agreement instrument is
    **honest but empty**: after `ee0ac4ad` it reports `agree_rate: None` until a **`tb_pt`/`tb_sl`**
    close exists, and only **2 of 35 lifetime records** were priced
    ([[concepts/tautological-instrument]]). So the corpus currently has **no measurement at all**
    of whether the traded bet resolves where the label says it should — it previously had a
    **1.0000 that was 94.3% definitional**, which is worse than nothing but reads as better.
    **What would close it:** enough priced barrier closes for a first honest `agree_rate` with its
    `n_priced` beside it. Note the coupling: priced closes are **bracket** closes, and bracket
    close cadence is governed by the **432-bar cohort hold** ([[comparisons/horizon-96-vs-24-bars]])
    and the post-`8e5455e8` honest fill regime — so this item **fills on the same clock as the
    cohort**, and will not be closeable early by any change that does not also break the hold.

34. **The hedge thrash's four residuals — none measured, none gated** (`5c111962`,
    [[sources/session-20260806-hedge-thrash]]). The fix ended the loop; it left four things open,
    smallest first. **(a) No gate for the class.** The shared `_exposure_by_asset()` helper is a
    **convention**; `test_exposure_helper_excludes_hedges_and_is_shared` asserts sharing **in its
    name only** — it calls the helper directly and never checks that either path uses it.
    *What would close it:* an AST call-site assertion that both branches invoke the helper (same
    technique as `test_append_invariant.py`), **or** the behavioural version — apply the returned
    actions to the book across iterations and assert a **fixed point**
    ([[concepts/two-paths-one-quantity]], [[concepts/adoption-is-not-enforcement]]).
    ~~**(b) The commit's headline test is vacuous.** Verified at filing: run against the parent's
    module, **3 of 5 tests fail and 2 pass** — and one of the two passing is
    `test_open_and_unwind_agree_across_repeated_evaluations`, the one whose docstring says *"the
    actual money bug."* `evaluate()` is a pure function of a state the test never mutates, so its
    `seen` set holds one element for **any** implementation. *What would close it:* the same
    fixed-point rewrite as (a) — the two items close together.~~ **CLOSED 2026-08-07, commit
    `af544d4c`** — the fixed-point rewrite, exactly as specced: `_run_loop` now **applies the
    returned actions to the book between evaluations**, and the red-check was run against the
    **genuine parent engine** (`git show 0e30ca09:execution/hedging.py` loaded as a scratch
    module — the earlier `git stash` red-check was a no-op once the fix was committed): pre-fix
    **13 opens / 12 unwinds alternating** over 25 cycles, post-fix **1 / 0**; a cold-matrix
    convergence case added. Note (a) did **not** close with it — the AST call-site assertion
    remains unwritten; the behavioural pin now exists, the structural one does not.
    ([[sources/session-20260807-hedge-churn-guards]] §4)
    ~~**(c) No churn breaker anywhere, and the one breaker that exists is blind to hedges.**
    `_run_hedge_pass` runs **every ~5 s**; `orders.has_open(asset, "hedge")` blocks only
    **concurrent** duplicates, never **sequential** re-opens. `risk/circuit_breaker.py` (4
    consecutive full-trade losses → veto new entries) is fed inside **`if not pos.is_hedge:`**
    (`main.py:1588`), deliberately — *a hedge's P&L is not a verdict on the gates that opened the
    position it protects* — so **147 consecutive losing round trips on one symbol were invisible
    to the mechanism whose stated purpose is to pull a misbehaving symbol off the sheet.** The
    exclusion is right for **attribution** and leaves a hole for **churn**. *What would close it:*
    a per-symbol round-trip-rate or fills-per-window breaker that counts hedge legs, with the
    threshold derived from the normal hedge cadence (which is **not** measured yet — that
    baseline is part of the item).~~ **FIRED, THEN CLOSED 2026-08-07.** The residual fired **~12
    hours after being filed**: incident #2, 01:09:45–01:34:19Z — 147 more laps of the same ADA
    hedge, this time from a **cold post-restart EWMA** flapping |rho|≈1 ↔ 0.0 (the 08-06 shared
    pair held; the *reading* oscillated). Closed by `cf454d5e` (cloud session): warmup gate
    (`corr_min_samples` 12 on the exact open pair), per-asset `rehedge_cooldown_sec` 600, and
    the **FW-070 churn latch** (3 unwinds / 900s → re-hedging frozen, auto-release on
    window + warm) — **opens only, unwinds never gated**, per the
    [[concepts/deadlock-discipline]]. Deploy-gate battery on the merged tree **3423 / 1
    skipped**; live 19:04:16Z. ([[sources/session-20260807-hedge-churn-guards]])
    **(d) The hedge asset is still chosen alphabetically.** `hedge_asset = others[0]` — ADA was
    hedged with because **A sorts first** in a seven-asset universe. The fix makes both paths
    **agree about an arbitrary choice**; it does not make the choice good. *What would close it:*
    a measurement of whether selecting the **highest-|corr| eligible** asset beats the alphabetical
    pick on realized hedge effectiveness — **noting that this is a behaviour change and therefore
    sits behind the 432-bar hold**, and that agreement, not selection, was the money bug.
    **Deliberately NOT owed:** the surviving `net` vs `signal_net` asymmetry between the open and
    the unwind is **documented hysteresis** installed by the *first* thrash's fix. Unifying it
    would reinstate that bug.

35. **The churn-guard follow-ups (`cf454d5e`, [[sources/session-20260807-hedge-churn-guards]]) —
    the fix's own two half-shipped edges, both verified.**
    **(a) The estimator's warmth is NOT persisted.** HANDOFF deadlock rule 3 explicitly required
    it (*"Persist the correlation estimator's sample count too"*); shipped: the hedger's guard
    clocks (`last_unwind`/`unwind_ts`/`latched`) ride the snapshot, but `samples` appears
    **nowhere in `core/persistence.py`** — every boot re-colds the estimator and the 12-tick
    warmup is re-earned per process life (median uptime 0.5h). Direction safe (blocks opens
    only; the empty-dict boot corner is backstopped by `corr()` reading 0.0 < floor). *What
    would close it:* persist the sample counts beside the hedger section, **plus the missing
    baseline — measured time-to-warm per boot**, so the share of process life spent unable to
    hedge stops being unquantified. *(08-07 panel: the floor is now computed — 12 ×
    `candle_refresh_sec` 150s = **30 min = exactly the median uptime**, refuting "reachable
    well inside"; roughly half of process lives never warm, and the guards also suppress
    TRIMS — [[sources/session-20260807-institutional-review]] §D, item 37(b).)*
    **(b) The FW-070 latch is telemetry-dark, and the class-level alarm is unbuilt.** Latch and
    release emit one `log.warning` each; **no gauge, no board tile, no alert** (verified by grep
    of `gc_pusher.py` — the firewall latched-fault gauge is a different mechanism). The
    HANDOFF's own fix part 3 ("surface on the incident board") did not ship. **Task #148**
    (>2 hedge unwinds/hour on ANY asset = the class-level alarm) is owned by the cloud session
    per the resolution notice. *What would close it:* a `hedge_churn_latched{asset}` gauge + an
    unwind counter through the board generator, and #148 landing — a breaker trip is precisely
    the moment a human must look; a silent breaker is half a breaker.

36. **The P&L reconciliation's three confirmed defects
    ([[sources/session-20260807-pnl-reconciliation]]) — the books are right; these are the
    screens and the bookkeeping.**
    ~~**(a) The "NET P&L (ALL TIME)" tile is mislabeled on two axes.** It renders
    `liquiditybot_perf_net_usd` — a **rolling last-200 NON-HEDGE window** (−56.91, window full,
    oldest 07-22) — under a description claiming *"cumulative realized P&L across every closed
    trade"*, while the true monotonic `realized_pnl_total` (−208.22) is **unexported**. *What
    would close it:* retitle honestly + export/board `realized_pnl_total` — board-generator
    only, no engine change.~~ **CLOSED 2026-08-07 night, commit `486a6891` (boards v37,
    [[sources/session-20260807-closing-batch]] §6):** the hero tile now reads
    **`realized_total`**, the ring is retitled **"last 200 closes"**, and **`fees_total` gets
    its own tile** — the invisible open-leg fee channel (36(b)) finally visible on screen.
    *Correction to this item's own filing:* "unexported" was **wrong** — `realized_total` has
    been in `build_status` since the initial commit (`runner.py:1163`) and in the pusher's ship
    list since `9b035996`; the real gap was **display and labeling**, which is what closed.
    **(b) Entry/hedge OPEN-leg fees enter NO P&L series.** `record_entry_fee`
    (`state.py:172-178`) debits cash and books nothing; on 08-07 that channel was **−157.84**
    visible only as the equity-vs-daily gap. A conscious decision is owed: book open-leg fees
    into a parallel counter (daily/weekly/total) or explicitly accept the equity-only channel —
    either way the Δequity identity should be decomposable **on the screen**, not only in a
    forensic session.
    **(c) The performance ring's July cluster is of unadjudicated provenance.** 133/200 ring
    entries (66.5%) date to 07-22/07-23 (wr 6.0%) — inside the era of the since-fixed QA-harness
    output pollution; whether that cluster is fully organic is **UNVERIFIED** (the perf-ring
    ground report's only PARTIAL). *What would close it:* a read-only cross-reference of ring
    timestamps against the harness-pollution windows and the audit chain — **label, never
    delete**. Until then, quote the ring's 8.0% with this caveat attached. *(08-07 panel
    amendment: GR2's verdict-word "organic" was struck as an overreach pending exactly this
    item; "not an incident artifact" is the part that stands.)*

37. **The institutional-review conditions register
    ([[sources/session-20260807-institutional-review]]) — 5-0 APPROVED_WITH_CONDITIONS on all
    six areas; these ARE the conditions, none closed by the verdict itself.**
    **(a) The sequenced fee-economics decision — the panel's sharpest ruling.** The 25/40
    constant is triple-confirmed to match no Kraken row, but the constant feeds the labeler's
    cost floor (`ml/labeling.py:45-52`, binds 100% of brackets) — a live change is a
    **disguised label-geometry retune breaching the 432-hold**. Owed NOW (analysis-only):
    stamp the fee assumption on P&L panels; give `fee_recon` (OM-080) a read-only-keys
    DRY_RUN path; run the battery at 40/80 and ~15/30 and record which admits flip. Owed AT
    the h432 verdict / era mint: the conscious constant decision (operator commit, per
    [[concepts/cost-truth]]'s own policy). **Do not change the constants before then.**
    **(b) The `cf454d5e` record correction — owed follow-up to the cloud session.** Four
    false counts (samples persistence; trims gated contradicting "opens only"; warmup floor =
    median uptime, 12×150s; deploy-gap timeline). Concrete residue beyond the record: persist
    `CorrState.samples` per HANDOFF rule 3 (extends 35(a)); a conscious decision whether
    trims should clear the churn guards at all (`hedging.py:239-291` vs `main.py:2634-2646`);
    warmth/uptime telemetry so "structurally unable to hedge" stops being unquantified.
    **(c) The interim-containment rule.** A subsystem with a **measured active control-loop
    failure** gets config-disabled while its fix is in flight (`hedging.enabled` was a
    one-line toggle nobody flipped for ~17h of exposure). Closes on a written rule in the
    repo's governance docs + a wiki note here.
    **(d) The 6/11-vs-recent-30 adjudication** ([[synthesis/open-contradictions-register]]
    #17): reconcile the era realized ledger (6/11 fully-net winners) with the recent-30
    still-losing story; display both with denominators until then.
    **(e) The exploration-path funnel-coverage decision.** 1,100+ ML-070/ML-072 exploration
    admissions bypass the conviction seam that renders 0/0 — decide whether the funnel should
    count them or the panel should say "conviction-gated flow only" on its face.
    **(f) The Virtu alerting spec** — AlertSink is complete and switched OFF
    (`config.json:1077-1078`); derived rules already specced: P&L-velocity page ~1%/15m,
    fee-velocity page $10/15m, unwind-rate/latch page (= task #148), fill-rate page,
    freshness meta-alert with noDataState=Alerting, restart/version warns. Every threshold
    derives from measured cadences; prerequisite gauges (fills-per-window, unwind counter,
    latch state, boot counter, running rev) are part of the item.
    **(g) The Two Sigma seam items** — persist `ret_pct` at the labeler seam
    (`ml/history.py:2389` currently discards the magnitude; ~97% of the corpus is sign-only;
    additive column, partial backfill possible from `pt_frac`/`sl_frac`); export Kish ESS
    (computed and logged, never emitted — `gc_pusher.py:688`); an evidence-runway panel
    (live_clean/60 + ETA per rung — ~3 months to gbt at the current rate, and no panel says
    so); add `triple_barrier_h432` to `_ERA_KNOWN` (`gc_pusher.py:100-101` — the current era
    cannot appear on its own era panels); persist the bracket-divergence window via the
    markout template (extends item 33 — the h432 hold's key instrument currently resets to
    n=0 every boot).
    *(Register note: 37(a)-(g) are decisions/instruments, not facts — nothing here asserts an
    outcome. The panel's corrected numbers themselves are filed as facts on the source page.)*

38. **The capacity sweep's deferred half — four items, none measured** (`00bd0e52` + `101f7436`,
    [[sources/session-20260807-capacity-sweep]] §4; all repo-side, nothing sim-conditioned).
    The sweep's throughput/hygiene half shipped and measured (xdist −n 8, BelowNormal battery,
    compileall −j 0, both lying DoD gates repaired); these are what it consciously deferred:
    ~~**(a) The Windows Defender exclusion A/B.** Requires admin elevation, and the tradeoff is
    real — an AV exclusion over the repo/venv is a **supply-chain exposure**. The owed thing is
    the *measurement* (battery wall time with vs without the exclusion); the adoption decision
    then prices speedup against exposure. Not to be adopted unmeasured.~~ **CLOSED 2026-08-07
    night ([[sources/session-20260807-closing-batch]] §1) — measured, and the decision landed
    the OPPOSITE way the item feared.** Event log 5007 proved a **years-old broad exclusion
    over `Documents\liquiditybot` already existed unpriced** (no add event in retention; only
    today's removal at 21:18:19 local, via the operator's `Remove-BroadExclusion.cmd`), so
    **every historical battery timing baseline ran effectively unscanned**. A/B: **3438/0/1 in
    401.30s scanning-on vs 375.39s baseline = +6.9%**, caveated — a same-night scanning-on run
    came in at 359.13s, so the pair delta is inside same-posture spread. **Final posture
    ADOPTED: source tree scanned; only `.venv` + pytest-temp excluded** (both added 21:14:50,
    per 5007). Documented, revertible; the supply-chain exposure retired. New standing timing
    baseline per [[concepts/conscious-re-baseline]].
    ~~**(b) `runner.log` rotation at the supervisor spawn boundary.** **153.8 MB** and growing;
    the live process **holds an append handle**, so in-place rotation is unsafe — the safe
    rotation point is the supervisor's spawn boundary between process lives.~~ **CLOSED
    2026-08-07 same evening, commit `48a63610`** ([[sources/session-20260807-evening-ops]] §1):
    rotation shipped at exactly the named boundary (64 MB cap / keep 2, best-effort by
    contract, 5 tests red-first) **and verified live 15 minutes later** — supervisor log
    `19:49:32 rotated runner.log (64MB cap)`, the ~154 MB archive on disk as `runner.log.1`,
    fresh log growing. Closed by measurement, not by ship.
    ~~**(c) The pytest-cov coverage baseline.** Line/branch coverage of shipped scope has **never
    been measured** — 3,400+ tests and no coverage number anywhere in the corpus; this is the
    sweep's entire unstarted second half. Closes on a first measured baseline filed with its
    scope stated (shipped packages, not tests/), after which coverage joins the battery's
    reported numbers.~~ **CLOSED 2026-08-07 night ([[sources/session-20260807-fleet-findings]]
    §7)** — first baseline measured and re-verified from the box's `.coverage`: **17,789
    statements, 88%** (shipped scope). Least-covered shipped modules ≥50 stmts:
    `api/grpc_server.py` 26% · `data/kraken_feed.py` 49% · `data/binanceus_feed.py` 59% ·
    `sentiment/scanner.py` 59% · `execution/algos.py` 60%. Caveat carried: the instrumented
    run's 3 failures were `overfit_check` subprocess 120s timeouts under ~1.7x coverage
    overhead — green in the clean battery; an overhead artifact. Residue: whether coverage
    joins the battery's *reported* numbers is a separate decision, not yet made.
    ~~**(d) venv pruning of the retired streamlit/pandas UI stack.** **~150–250 MB** of installed
    packages with **zero importers verified** in shipped scope. Closes on removal plus a green
    battery (or a reasoned keep). Verification of zero importers is already done; only the
    removal and the re-verify remain.~~ **CLOSED 2026-08-07 night — executed, and the item's
    premise partly REFUTED by the execution** ([[sources/session-20260807-closing-batch]] §4).
    The prune ran; **"zero importers verified" was WRONG for pandas** — the moomoo SDK
    runtime-requires it and **hard-exits at import** (`site-packages/moomoo/__init__.py`
    prints `Missing required package pandas`, `sys.exit(1)`), a requirement **never declared
    to pip**, so `pip check` stayed silent. Cost: a ~4-minute degraded/crash-loop window
    22:21–22:25 local, graceful exits, recovered on reinstall 22:26. **Ledger amended: pandas
    is a KEEP (moomoo); the other six removals stand** (streamlit verified absent at filing).
    Lesson filed as the fourth [[concepts/false-green]] specimen: **static grep of our sources
    ≠ the runtime import graph — vendor SDKs hide requirements**; the only conclusive
    verification is booting the pruned venv.

39. ~~**The REST `_deny` RST class — root cause named, fix decision owed**
    ([[sources/session-20260807-evening-ops]] §3; repo-side, harness-plane). The recurring
    `test_audit_security` flake (latest:
    `test_control_refuses_html_form_text_plain_post`, 1/3427 in the `48a63610` battery)
    **survived the 30s-timeout fix (`00bd0e52`), which rules the timeout class out.** Named
    mechanism: `_deny` (`api/rest_server.py:109-121`) closes with the refused POST body
    **unread** — a deliberate anti-smuggling choice (`ab76cdfb`, 08-01) — and close-with-
    unread-data aborts via **TCP RST**, which can destroy the client's in-flight response;
    under `-n 8` saturation the race intermittently lands while the server's own log shows the
    refusal fired correctly (REST-002/003 captured in the failing test's output). *What would
    close it:* a conscious decision between a **bounded drain-then-close** in `_deny`
    (cap the drained bytes so the anti-smuggling property is kept) and **harness-side RST
    tolerance** (retry/accept-connection-error on refusal cases) — either way with a red-first
    test pinning the chosen behavior. Until then the class stays an honest red flake; the
    hazard is alarm fatigue, not a wrong gate. **Do not widen the gate** by blanket-retrying
    the whole file ([[concepts/never-widen-a-gate]]).~~ **CLOSED 2026-08-07 night, commit
    `1e7f882c` ([[sources/session-20260807-closing-batch]] §6) — the bounded-drain option,
    exactly as specced.** `_deny` drains **≤64KB** of unconsumed declared body before
    responding; `do_POST` refuses declared bodies **>1MB with 413 (REST-004) BEFORE reading**
    — anti-smuggling kept on both edges. Red test reproduced the exact abort
    (`ConnectionAbortedError` in `_deny`'s write). Battery **3430/0/1 in 375s — first fully
    clean parallel run of the day**; the class is dead.
    *Successor registered in the load-marginal timing family:*
    `test_feed_concurrency::test_fetch_is_concurrent_not_serial` flaked **1x under `-n 8`**
    in the `915b362f` battery, passes solo in 1.6s — honest red, watch, no blanket retry.
    *Second member registered 2026-08-08
    ([[sources/session-20260808-morning-batch]] §3):*
    `test_pbo_variants::test_schema_ab_flag_adds_no_new_gating_check_and_is_info_only` failed
    under `-n 8` (inner overfit subprocess `passed 7, failed 1` at 33s), **passes solo in
    60.33s on the same tree** — load-marginal, same disposition. Its one red is also the
    failure that exposed the battery's dead pytest gate (specimen #5) — the flake earned its
    keep.
    *Third member + escalation 2026-08-08 afternoon
    ([[sources/session-20260808-budget-reanchor]] §5):* the `f07d60f8` ship cycle's batteries
    went **red · clean · red** on ROTATING members — the pbo schema-AB test again (18/18 solo
    beside a running battery), then `test_concurrency_throttle` burst (4/4 solo in 7.7s) —
    each red solo-green on the same tree. **The family is now the batteries' binding
    constraint** under the honest gate; structural response registered as **item 44** (no
    blanket retries in the meantime, per [[concepts/never-widen-a-gate]]).

40. ~~**The fill-sim TTL skew fix — the #1 P&L-integrity item**
    ([[sources/session-20260807-fleet-findings]] §1; sim-side by construction). Two verified
    defects in the fill simulator: **(a) horizon mismatch** — `sf_base=0.048` was calibrated at
    `n_bar=5` polls (25s life) but is drawn **per poll**, so any order living longer inherits a
    compounded fill probability the calibration never priced; a 6h long-book bid (~4,320 polls)
    compounds to **≈1.0** — verified arithmetically against `outputs/fill_calibration.json`
    (per-poll 0.028 at d_bar=0.54 → 1−(1−0.028)^5 = 0.131 = f_hat). **(b) double-count** —
    `_sim_maker_cross` (`order_manager.py:1085`, called at `:1220`) deterministically fills full
    remaining on the **same trade-through predicate** `calibrate_fills.py` measured, with **no
    depth/queue constraint**, and the stochastic draw runs on top. *What would close it:* a
    **time-normalized hazard** (per-poll p derived from the order's OWN ttl: p = 1−(1−f_hat)^(1/n_polls(ttl)))
    **or per-TTL n_bar recalibration**, plus removal of the double-count (calibrate the residual
    hazard *conditional on no deterministic cross*, or drop one path) — with a red-first test
    pinning compounded fill prob per TTL class. **Sequencing warning:** this is an
    execution-regime change — it mints a **third era boundary** (after `8e5455e8`) inside the
    432 cohort (item 1b) and interacts with 13c (form replacement) and 23b (calibrator re-run);
    land it deliberately and stamp the boundary timestamp here when it ships. Until it lands,
    **no long-book paper fill, markout row, or per-asset stat containing one may be cited even
    as honest-pessimistic paper** ([[concepts/paper-real-boundary]]).~~
    **CLOSED 2026-08-08, commit `3cfe0710`, pushed, deployed 11:10 local
    ([[sources/session-20260808-morning-batch]] §1) — the time-normalized-hazard option,
    exactly as specced for (a).** `_passive_poll_prob` (`execution/order_manager.py:61-100`):
    `p = 1−(1−sf_base·exp(−d/σ))^min(cal_life/ttl, 1.0)` — poll cadence cancels, per-ORDER fill
    probability is **TTL-invariant at the calibrated F(25s)**; `ttl == cal_life` is
    **bit-identical** (5m book + G1–G5 unchanged, **no re-baseline**); exponent clamped at 1.0
    (shorter orders fill less, never more); `sf_base=1.0` = deterministic test-mode bypass
    (Wilson can never emit boundary values). Config `sim_fill.calibration_life_sec=25.0` with
    the era declaration in its `_doc`. Red-first `tests/test_fill_ttl_normalization.py` —
    **7 tests** (the batch and commit message claimed 8; collection says 7, and
    3438+11=3449 confirms it), incl. an AST pin that `_poll_dry` calls the helper. Battery
    through the HONEST gate — the same session repaired the battery's pytest arm, which had
    **never been able to fire** (false-green specimen #5, `050421a7`,
    [[concepts/false-green]]): **3449/0/1 in 349.51s, smoke 219, ALL GATES PASS**.
    **EXECUTION-ERA BOUNDARY #3 MINTED** (after the QA quarantine and XV-021 ts~1785717000):
    corpus rows before `3cfe0710` (2026-08-08) were filled under the compounding simulator —
    label cohorts treat this date as a regime cut (item 1b). The §1-embargo sentence above
    lifts for **post-boundary** fills only; pre-boundary long-book rows stay uncitable.
    ~~**(b) disposed by design, not dropped:** `_sim_maker_cross` is retained as *genuine
    trade-through against the live book* with the calibrated hazard as a conservative floor;
    the calibrate-conditional-on-no-cross refinement folds into 40b.~~

    > ⚠️ **THE (b) DISPOSITION IS RETRACTED — 2026-08-10, `aeeaae36`, item 57.** The hazard was
    > **NOT a conservative floor.** A floor models something the observation cannot see; this ran
    > **only when the observation was present** (`if book:`). And `invert_base_prob` had already
    > solved `sf_base` so **the hazard alone reproduces f** — so adding it on top of the
    > deterministic cross did not add conservatism, it **spent the calibrated frequency twice**:
    > `2f−f² = 21.96%` against an `f = 11.66%` target, **1.88x at the touch**, against a
    > ledger-measured **22.30%**.
    >
    > **The (b) sub-item was therefore not disposed — it was the whole defect, deferred under a
    > wrong framing, for two days after [[sources/session-20260807-fleet-findings]] §1 had already
    > named it correctly** (*"the calibrated trade-through frequency is **spent twice**"*).
    > Filed as [[synthesis/open-contradictions-register]] entry **25** and as a first-class
    > retraction per domain rule 3. **A finding can survive discovery and still be lost at the
    > DISPOSITION step** — especially when the disposition is written in the same session as a
    > celebrated fix, by an author with a motive to close the docket.
    >
    > **Only (a) — the TTL normalization — was genuinely closed on 08-08.** Item 40's closure
    > stands **for (a) alone**; (b) closes on **2026-08-10** with item 57.

40b. **XV-023 — per-TTL fill recalibration** (declared `core/fill_calibration.py:17`;
    sim-side). The TTL normalization holds the calibrated F(25s) as a **floor estimate** for
    long lives; whether real 6h resting orders fill more or less than that floor is
    **unmeasured** — all recorded trials were ~25s lives. *What would close it:* re-run
    `calibrate_fills.py` with **per-TTL buckets** once recordings gain long-life resting-order
    coverage, and calibrate the stochastic residual **conditional on no deterministic cross**
    (the 40(b) refinement). Interacts with 13c (XV-022 form replacement) and 23b (calibrator
    re-run on clean fills) — one calibration campaign should close all three.

41. **The input-feed integrity docket** ([[sources/session-20260807-fleet-findings]] §3;
    repo-side defects on real feeds). Four verified sub-items, each closing on its own fix or a
    reasoned won't-fix: ~~**(a)** moomoo market-hours/staleness guard — `moomoo_feed.py:218-272`
    appends frozen closed-market quotes unconditionally (verified live: identical +3.60% basket
    for hours, z collapsed to +0.00; ~62h weekend of it ahead); close by suppressing appends
    when the snapshot is unchanged/market closed, or by an explicit closed-market sentinel.
    *41(a) in-flight note, 2026-08-08 — DO NOT LOSE: the red-first freeze-gate tests are
    WRITTEN and PARKED* as `test_feed_freeze_gate.py.parked` in the 08-08 session scratchpad
    (`…\Temp\claude\c--Users-haird-Documents-liquiditybot\63d8f842-…\scratchpad\`; full path
    on [[sources/session-20260808-budget-reanchor]] §6 — **session-scoped storage, copy out
    before cleanup**). The moomoo gate implementation resumes next; **the parked file returns
    to `tests/` when it does** — the tests are owed alongside the fix, not superseded by it.~~
    **(a) CLOSED 2026-08-08, commit `01d59908` — the append-suppression option, exactly as
    specced** ([[sources/session-20260808-battery-split-freeze-gate]] §2): a **FULL-basket
    per-ticker-return repeat vs the previous poll** is the closed-market signature (one name
    moving ≠ freeze); frozen polls do **not** append, so **z holds its last honest value
    instead of decaying** (+0.39→0.00 was the defect); `available` stays True and the
    snapshot gains **additive `quotes_frozen`**; **DF-010/DF-011** latched transition codes
    (registry 187→189); options gate on raw `(pcr, oi_pcr)` equality. Red-first
    `tests/test_feed_freeze_gate.py` (4) — **the parked file returned to `tests/` and is
    COMMITTED in the fix; the scratchpad note is moot.** Two deferrals held deliberately:
    **41(c) persistence stays sequenced AFTER this gate** (persisting a polluted window
    would carry stale-repeat decay across restarts and mask it), and `status.json`'s moomoo
    block does **not** yet carry `quotes_frozen` (verified by grep) — operator visibility
    rides with **41(b)**'s availability wiring. At filing the gate was
    **committed-not-running** (pushed 13:56; the 14:10 auto_update cycle was watched
    bounce **pushers only** for `01d59908`, runner untouched — the local-commit blind
    spot behaving exactly as [[entities/auto-update]] files it); the runner bounce is a
    manual stop → supervisor-relaunch — deploy-before-US-close is the session's stated
    intent, confirmation owed. **Both deferrals discharged the same day (evening):**
    41(c) shipped `e22df720` after the gate exactly as sequenced, `status.json`'s
    `quotes_frozen` landed with 41(b)'s `64724480`, and the runner bounce onto
    `e22df720` was sent ~17:4x local (supervisor relaunch pending at the evening
    filing) — carrying 41a+41b+41c into the ~62h weekend window
    ([[sources/session-20260808-evening-availability-persistence]] §3).
    *(Re-lettering note, 2026-08-08 evening: the docket's canonical letters — the ones the
    queue and the 08-08 filings use — are (b) availability wiring, (c) window persistence,
    (d) sentiment saturation, (e) the skew clip rail. The original 08-07 letters are
    re-filed below under the canonical scheme: the original (d) "feed failure ≡ neutral"
    is absorbed into (b)'s closure, the original (e) warm-start into (c)'s.)*
    **(b) CLOSED 2026-08-08 evening, commit `64724480` — availability recorded on every
    corpus row at ZERO model DoF**
    ([[sources/session-20260808-evening-availability-persistence]] §1): `_feature_extras`
    captures the `{web, equity, options, frozen}` truth dict and rides gate_components'
    proven plumbing (candidate dict, all three order-meta stashes incl. ladder rungs via
    threaded `feat_avail`, pending 9-tuple) into **4 trailing bookkeeping columns**
    `avail_web`/`avail_equity`/`avail_options`/`quotes_frozen`; **`""` = UNKNOWN strictly
    distinguished from `"0"` = measured down**; DF-020/DF-021 latched episode codes
    (registry 189→191); the runner status moomoo block now carries `quotes_frozen`
    (41(a)'s visibility deferral discharged). This closes the original "feed failure ≡
    neutral" defect **at the record layer** (the live half of item 12): the row now says
    which world it was written in. The **model input is deliberately unchanged** — the
    DoF ledger stays CLOSED ([[concepts/dof-budget]]); any decision-path consumption of
    availability is a schema/DoF change sequenced behind h432. The battery earned its
    keep on the way: the first red run exposed `core/persistence.py`'s FIXED-SHAPE
    pending-tuple rebuild (would have silently dropped the 9th slot on every restart —
    the class that ate gate_components pre-T4), fixed + pinned; `migrate_history.py`
    pads the 4 columns blank; the three red batteries were ALL legitimate downstream
    schema pins, zero timing-family flakes across all four runs (the item-44 split
    holding).
    **(c) CLOSED 2026-08-08 evening, commit `e22df720` — moomoo z-windows + freeze state
    persist across restarts** (same source §2): `MoomooFeed.to_dict/from_dict` + a
    StateStore `"moomoo_state"` section (method-guarded for close()-only doubles;
    fail-soft `from_dict` — partial garbage resets clean); poll timestamps deliberately
    NOT persisted (an immediate re-poll is wanted; the restored `_last_per` classifies
    it); **the 41a×41c composition pinned by test** — the first post-restart poll of a
    still-frozen market reads frozen (no append, z holds) instead of re-seeding the empty
    window with the frozen quote, the audit's sequencing warning now enforced, not just
    honored by ship order. 5 tests in `test_moomoo_persistence.py`. Closes the
    fleet-measured **~3.5h/day** empty-window rebuild hole at the median-0.5h restart
    cadence (the original warm-start item; the sentiment volume history stays
    in-memory-only but is moot while (d)'s saturation stands — nothing measurable rides
    on it until (d) resolves).
    **(d) OPEN** *(re-lettered from the original (b))* — the sentiment volume gate is
    structurally dead — per-source caps saturate at items=200 every poll → vol_z ≡ 0 →
    fear/euphoria spikes **can never fire** (`scanner.py:275-292`); close by measuring
    volume on a quantity that can vary (pre-cap counts) or consciously retiring the spike
    gates. **(e) OPEN** *(re-lettered from the original (c))* — `opt_iv_skew` pinned at
    the −3.00 clip bound in the live log — decide whether the clip is hiding a real
    reading or the upstream ratio is broken; a value AT a rail is a label, not a
    measurement (interacts with 45f — the skew feature is a schema-AB prune candidate).

42. **The latency-truth docket** ([[sources/session-20260807-fleet-findings]] §4; repo-side).
    **TIER 1 SHIPPED 2026-08-07 night, commit `915b362f`
    ([[sources/session-20260807-closing-batch]] §2–3) — the deterministic-safe half: (b) and
    (c) CLOSED, (d) instrumented; (a) and the veto-grade responses remain the open half.**
    *(08-08 night update: (a) CLOSED — the open half is now (d)'s veto-grade response and (e).)*
    ~~**(a) STILL OPEN.** The pre-trade staleness veto is arithmetically dead — `book_ts` stamped
    with the same cycle-frozen `now` it is compared against (`main.py:2420` vs `:4403`), so
    `staleness_ms` ≈ 0 always against a 4000ms ceiling (`pretrade.py:96,236`); close by
    stamping `book_ts` from the **feed's own receive/exchange timestamp**, with a test that a
    stalled feed trips the veto. (This is a **decision path** — deliberately excluded from
    tier 1, which touched telemetry only.)~~ **(a) CLOSED 2026-08-08 night, commit `36fcfd6e` —
    the feed's-own-timestamp option, exactly as specced**
    ([[sources/session-20260808-night-staleness-overfit]] §1): books now carry a `recv_ts`
    **write stamp** — REST attaches it after `clean_book`, the ws manager attaches the cache's
    raw write stamp via new `LiveMarketCache.book_ts` (zero-caller accessor promoted) — and the
    engine stamps `book_ts = float(book.get("recv_ts") or now)` in `fast_cycle` + the runner
    PAUSED-flatten. Replay determinism **by construction**: FeedRecorder records returned dicts
    verbatim (extra-key pass-through pre-pinned by `test_recording`); stampless legacy books
    take the byte-identical fallback. 6 tests in `tests/test_staleness_truth.py` incl. the
    **write-time-not-read-time pin** and the two-writer source contract; 2 ws-manager shape
    pins updated, cache-layer pins untouched. Known limits documented at ship:
    content-frozen-through-a-live-socket is the **41(a) freeze-gate class, per-feed** (not this
    veto's job); the watchdog's `.get(a, now)` fail-open default is left for its own item.
    **Ship disclosure:** the battery's overfit stage was red at ship for the **item 46** corpus
    reason — diff proven orthogonal (zero ML paths; pytest 3458+17, smoke 219, assurance 49,
    ruff/pyright/bandit/compileall, quant G1–G5 all green); runner **deliberately NOT bounced**
    pending that adjudication.
    **⚠️ (a) REOPENED AS SUB-LIMITS 2026-08-09** — an adversarial audit of `36fcfd6e` found
    that the commit **introduced a CRITICAL-latent defect** and that **three of its claims
    do not hold** ([[sources/session-20260809-corpus-corruption]] §11). The **veto band is
    FIXED** in `3c0debd7`: `websockets.kraken_max_book_age_sec` **5.0 > 3.5**, plus a
    `config_guard` **FATAL on the relation itself** (verified two-sided) — at 5.0, once
    `book_ts` became data time, the ws cache **SERVED** books aged 4–5s that PT-020 then
    **VETOED**, and because `main.py` falls back to REST only when the ws returns `None`,
    that doomed book **PREEMPTED a fresh REST read** — exposure **~0.6–3% of entry
    evaluations**, worst on the thinnest pairs (**MINA 3.2% · FLOW 2.9% · PAXG/LINK 1.9% ·
    BTC 0.6%**), **skewing which assets can accumulate fill labels**; masked only because
    the book was full 5/5, and it would have armed the moment a position closed. The
    `config_guard:2835-2848` prose still **ASSERTED** the premise 42a falsified, and
    `tests/test_audit_fixes.py` **pinned that dead premise in its test NAME and assertion
    message** — both rewritten (filed to
    [[synthesis/documentation-drift-register]]). **Three OPEN sub-limits, the genuine gain
    being the WS path only:** **(a-i)** *REST-path sign inversion* — `now` is frozen at
    cycle start but `recv_ts` is stamped **after** the blocking fetch, so
    `staleness_ms <= 0` for any book fetched this cycle (a 50s hang reads **−50000ms**);
    42a buys **no new detection power on REST**; *closes on* a REST-side stamp taken
    against a per-call clock, or a conscious acceptance that REST staleness is
    unmeasurable here. **(a-ii)** *The pre-42a code was NOT tautological on the FAILURE
    path* — `book_ts` held the last successful cycle's `now` and grew **~5s/cycle**, which
    is precisely the path the commit message led with; the tautology was **success-path
    only** ([[concepts/tautological-instrument]] corrected). Recorded so the fix is not
    over-credited; nothing to close. **(a-iii)** *DL-10 cannot benefit* — the new
    measurement is **capped at `kraken_max_book_age_sec` (3.5s)** while DL-10/watchdog trip
    at `stale_critical_sec` = **120**; **a quantity capped at 3.5 cannot cross 120**;
    *closes on* a separate absent-book age measured outside the cache's own ceiling. ~~**(b)** `marks_age_sec` reads 0.0 by the same shape
    (`runner.py:1163` + `main.py:2402/2438`), and `.get(s, now)` makes a *missing* mark read
    fresh.~~ **(b) CLOSED** — telemetry-only `_mark_wall_ts` twins (`main.py:1234`) read by the
    runner's wall-clock `_marks_age_sec` helper; **no decision path touches the wall stamps,
    replay determinism intact**; proved non-tautological live (16.7s and climbing while the
    bot was STOPPED, 0.0 fresh). ~~**(c)** No cycle-duration telemetry exists (`cycle_lifetime`
    is a counter) while the runner documents measured 50–88s stalls; close with a
    cycle-wall-time gauge through the board generator.~~ **(c) CLOSED** —
    `_note_cycle_duration` (`runner.py:1057`) → `cycle_duration_sec`/`_max_sec` exported and
    pushed (`gc_pusher.py:253`); **caught the cold-boot warmup stall (45.56s) on its first
    boot**. **(d) INSTRUMENTED, response owed** — **FW-080** `_bar_age_check` (`main.py:468`,
    `core/codes.py:51`): warns once per stale episode per asset when the last committed bar
    lags **>1200s** (4 bars — thin pairs legitimately gap); **detection only, latched,
    re-armed on recovery**; the veto-grade response is consciously sequenced with (a), never
    bolted on. **(e) NEW — the restart-warmup race** (from the pandas incident,
    [[sources/session-20260807-closing-batch]] §4): cold warmup measured **~3.5 min** against
    the supervisor's **stale=120s** window — the supervisor declared a healthy warming runner
    stale/absent at 22:21:45 and displaced it (second firing of
    [[concepts/liveness-by-output-cadence]]; a [[concepts/deadlock-discipline]] rule-4 window
    never sized against its measured cadence). *What would close it:* a warmup-aware stale
    window (or a boot-grace signal from the runner), sized against measured cold-warmup
    durations — which the new `cycle_duration_max_sec` gauge now records. Positive result
    recorded so it is not re-audited: the main fill path is
    **look-ahead-free** — single `orders.poll` site (`main.py:2459`), entries submitted after;
    a dormant look-ahead seam exists in `execution/algos.py` **only if ever enabled**.

43. **The transcript-sweep registrations — the verified survivors of ~200 ledgered bugs**
    ([[sources/session-20260807-fleet-findings]] §6; repo-side; the refuted claims are on the
    source page and must not be re-filed). ~~**(a)** CRLF bundle-transport port unconfirmed — the
    Jul-18 zip fix never verifiably ported; current `.gitattributes` has no binary/-text pin
    for telemetry bundle paths, so byte-exact CSV transport through git is unpinned; close by
    pinning (or proving the transport path never crosses a text-conversion boundary).~~
    **(a) CLOSED 2026-08-07 night — the registration itself was the error**
    ([[sources/session-20260807-closing-batch]] §5): the pin exists at
    `scripts/telemetry_backup.py:246`, which writes a `.gitattributes` containing `* -text`
    **into the bundle worktree before `git add`** — per push, machine-independent, stronger
    than a repo-level pin — introduced `4a42d2c2`, **2026-07-18 20:14:56Z, the same day as the
    zip incident** (the port DID happen); `tests/test_telemetry_backup.py` covers the
    transport (committed-tree verifier). The sweep looked for a repo-level `.gitattributes`
    pin — right invariant, wrong layer.
    **(b)** Registry `ok=None` acceptance — a never-registered artifact loads with "unknown
    provenance — loudly logged, not blocked" (`ml/registry.py:84,244`); a conscious decision is
    owed on whether unknown provenance should fail closed now that the chain exists (30a).
    **(c)** `min_corr` hysteresis — open and unwind both compare the raw reading against the
    identical 0.55 (`hedging.py:44,208,294`); the cf454d5e guards bound the *rate*, not the
    flapping; close with a threshold band or a reasoned acceptance that cooldown+latch suffice.
    **(d)** GBT `l2=3.0` was hand-tuned against the overfit battery (`ml/models.py:501,508-513`
    — rev-4 defaults "memorized", shipped defaults chosen to pass) — OF-1 is **not independent
    evidence** for the GBT family; close by an out-of-battery validation of the GBT defaults or
    an explicit note in the battery docs that GBT hyperparameters are battery-conditioned.

44. ~~**The battery timing split — parallel pass + gated SERIAL pass for the load-marginal
    family** ([[sources/session-20260808-budget-reanchor]] §5; repo-side, harness-plane).
    With `050421a7`'s honest pytest gate live, the load-marginal timing family (item 39's
    successor register: `test_feed_concurrency` · `test_pbo_variants` schema-AB **twice** ·
    `test_concurrency_throttle` burst) is now the **batteries' binding constraint** — the
    `f07d60f8` ship cycle went red · clean · red on rotating members, every red solo-green on
    the same tree, each costing a full ~350s re-run. *What would close it:* mark the family
    `@pytest.mark.timing` and split the battery into a **parallel pass `-m "not timing"`
    (`-n 8`)** plus a **SERIAL pass `-m "timing"`** — timing-sensitive tests never judged
    under 8-way load — with the bat treating **both** passes as gated stages (per
    [[concepts/false-green]] design rules: hard-fail, failure arm proven two-sided) and the
    marker list pinned by a test so an unmarked new timing test cannot silently rejoin the
    parallel pass. Explicitly **not** a blanket retry and **not** a gate-widening
    ([[concepts/never-widen-a-gate]]) — the tests stay honest reds where they fail; they just
    stop being asked to pass under a load profile they were never calibrated for. Until it
    ships, the standing disposition holds: disclose the flake, verify solo, never retry-loop
    the battery to green.~~ **CLOSED 2026-08-08 (same day), commit `be341867` — exactly as
    specced** ([[sources/session-20260808-battery-split-freeze-gate]] §1). The family is
    **17 tests across 7 files, tagged by MECHANISM** (hard 120s subprocess wall timeouts on
    `overfit_check` CLI children = the TimeoutExpired class · burst/thread-gap compression
    from a worker descheduled between throttle release and stamp · upper-bounded elapsed
    asserts · a starvable heartbeat thread); lower-bounded elapsed tests deliberately stay
    parallel (load only grows them). `timing` is registered in `pyproject.toml` under
    **`--strict-markers`** (a typo'd mark is a collection ERROR, never a silent rejoin);
    the bat runs both passes behind their own honest `if errorlevel 1` gates, BelowNormal;
    the split is pinned by `tests/test_battery_gate.py` (now **5**: exactly two pytest
    passes · parallel excludes timing · timing pass serial · honest form both · construct
    ban). **First split battery fully green, zero flake: parallel 3445 passed / 1 skipped
    in 3:28, serial 17/17 in 3:07** — arithmetic closes exactly (3459 collected at the
    split commit + 4 freeze-gate tests = 3463 = 3445+1+17). The serial pass is a gated
    stage, so a genuine timing-family regression still stops the line — **scheduling
    changed, the gate did not.**
    **Addendum 2026-08-09 — the inventory was one test short (gap closed).**
    `tests/test_import_integrity.py` was **never tagged** and went red in the `3c0debd7`
    battery on `TimeoutExpired`. It is the **most SELF-saturating test in the suite** —
    **8 threads × ~100 fresh interpreter spawns**, each under a **hard 120s wall
    deadline**, inside the `-n 8` pass **alongside the live BelowNormal runner** — and it
    **passes solo in 4.3s**. Now serial: **timing family 17 → 18**, across 8 files. The
    *taxonomy* was right (it is the hard-subprocess-wall mechanism, same as the
    `overfit_check` CLI bloc); the *census* was incomplete, and `--strict-markers` cannot
    catch a test that was never marked at all — a small
    [[concepts/adoption-is-not-enforcement]] residue. *What would close the residue:* a
    check that flags **new** tests whose worst-case wall time is bounded, or that spawn
    interpreters, and are not marked `timing`.

45. **The institutional/government data queue — family 45a-45f, PROPOSED, all
    telemetry-first at 0 model DoF**
    ([[sources/session-20260808-institutional-data-adjudication]]; research-side/venue-data-side
    adjudication by three deep-research agents, endpoints live-verified; nothing here has
    shipped). **Sequencing is part of the item: the whole family sits BEHIND the
    currently-owed queue — 41(b) / 41(c) / 42(a) / 42(e) / 37(g) / 37(b) — and NOTHING in it
    touches the feature schema before the h432 verdict** *(queue update 2026-08-08
    evening: 41(b)/41(c) CLOSED — the queue ahead of this family is now
    42(a)/42(e) → 37(g) → 37(b),
    [[sources/session-20260808-evening-availability-persistence]] §4)* (item 1b); the 2026-07-24 DoF
    ledger stays CLOSED ([[concepts/dof-budget]]). Prerequisite for 45c/45e: the
    [[entities/contextfeed]] **UA config-lift with real operator contact** (gap (a)) —
    EDGAR 403s a "contact: none" UA by policy; 45f's weekly source also needs gap (b)
    (wider-than-3x grace for shutdown-class gaps).
    **45a. The basis+funding crash-risk dial** — CME front-month basis (Yahoo `BTC=F` vs
    Kraken spot) + perp funding EXTREMES; telemetry first, then the evidence-backed
    consumer that does not exist yet: **extreme positive funding → truncate/veto longs,
    asymmetric, down-only** ([[concepts/asymmetry-law]]) — a risk-gate build, 0 DoF
    (`funding_rate` is already a feature; the *consumer* is what is owed). *Closes on:*
    the dial emitting, then a shadow record of would-veto events before any influence.
    **45b. The BLS CPI/NFP calendar** into the existing FOMC event-gate machinery
    (calendar + `in_event_window` already wired, telemetry-only) — the adjudicated
    highest value-per-effort item. *Closes on:* CPI/NFP windows flowing through the same
    pause machinery, cadence-pause only, never a sign.
    **45c. The ETF-flow ContextFeed source** — Farside primary (browser UA) /
    SoSoValue backup; **publication-time stamps (evening/next-morning, NOT 4pm ET)** or
    the series is lookahead-poisoned; consume as 5-day z/streaks, never single prints.
    *Closes on:* the source live with honest stamps and the staleness discipline.
    **45d. The OFR FSI ContextFeed source** (daily CSV, T+2) — **conditional adopt**: the
    credit/funding sub-columns must show incremental value over the existing VIX-family
    dials or the source is dropped; FRED batch (NFCI/DFII10/BAMLH0A0HYM2, 120 req/min,
    release-calendar scheduling) rides along. *Closes on:* the incremental-value test,
    either way.
    **45e. The EDGAR 8-K watchlist flag** — `getcurrent` Atom + `efts` full-text,
    minutes-latency, 10 req/s ceiling; blocked on the UA lift. *Closes on:* the flag
    emitting for watchlist filings, telemetry-only.
    **45f. The schema-AB options-features prune experiment** — the adjudication found
    **ZERO evidence of any kind** for COIN/MSTR options→crypto transmission, making the
    three shipped model features **`opt_pcr_z` / `opt_oi_pcr_z` / `opt_iv_skew` PRUNE
    CANDIDATES** (one already rail-pinned, item 41(e) under the canonical re-lettering).
    **INFO-arm experiment first, no
    schema churn until h432** — this is the evidence-based route
    [[concepts/coverage-floor]] requires; dormancy alone never justified a prune.
    *Closes on:* the INFO-arm A/B reading, then a conscious keep/prune decision at the
    era boundary.
    **The TFF COT upgrade** (legacy COT source → TFF crypto categories, same Socrata
    `gpe5-46if`; weekly regime dial only, **never directional** — leveraged-fund net
    shorts are basis-trade mechanics) folds into whichever of 45a/45d lands first, and
    its ingester must tolerate multi-week shutdown gaps (gap (b)).

46. ~~**The overfit stage's live grading — OPERATOR ADJUDICATION OWED, blocking the deploy
    gate**~~ **CLOSED 2026-08-09, commit `8e9d7e6f` — option (a), exploration-phase
    informational grading, exactly as registered**
    ([[sources/session-20260809-gate-policy-and-self-heal]] §3).
    ([[sources/session-20260809-corpus-corruption]] §8; repo-side grading of a
    corpus whose live rows are sim-execution-conditioned).

    **The adjudication, in one sentence:** OF-1 and OF-7's dead-feature check are
    **MODEL-READINESS** gates that were being used as **CODE-DEPLOY** gates (the battery
    stage feeds `auto_update.battery_passes`), so a data-starved corpus was holding
    **code-safety fixes hostage**. The policy **scoped what the verdict BLOCKS, never what
    it measures** — which is why this is a scoping decision and not a
    [[concepts/never-widen-a-gate]] breach.

    **NOT DONE, each pinned by a test:**
    - **No threshold moved** — **0.12** and **0.55** unchanged;
      `test_thresholds_are_untouched` **fails if either literal is edited**.
    - **The numbers still print EVERY run**, labelled *"INFORMATIONAL (OVER the 0.12
      memorization band)"* with the gap value **and** the re-arm condition; pinned by
      `test_informational_lines_still_report_the_number` (*a softened gate that stops
      printing its measurement is how a red goes invisible*).
    - **Model TRUST untouched** — `ml.model_selection`'s [[concepts/evidence-floors]] still
      gate to `logistic` at live=6 (observed live, ML-016 02:56:04), and the live
      [[entities/ml-governor]] still kills a confidently-wrong model on realized outcomes.

    **DONE — four deliberate properties:** informational **ONLY** while
    `ml.exploration.enabled` (the **OF-5/DSR precedent** — the corpus is dominated by
    EV-mixed PT-050 probe/candidate rows bought to acquire labels, so OF-1 grades the
    **acquisition phase**); **FAIL-CLOSED** (unreadable config gates fully);
    **HARD on the SYNTHETIC benchmark always** (there the checks validate the **INSTRUMENT**
    against a planted signal with a known answer — *an instrument may not grade itself
    leniently*); **SELF-TERMINATING** (flip exploration off and both re-arm — no stamp, no
    operator memory).

    **Implementation:** a **pure predicate** `gate_is_informational(explore_on, on_synthetic)`
    (`scripts/overfit_check.py:101`) called by both OF-1 (`:745`) and OF-7 (`:943`), so the
    policy is unit-testable and **the two gates cannot drift apart**
    ([[concepts/two-paths-one-quantity]] applied *prospectively*). **8 tests** in
    `tests/test_overfit_gate_policy.py`.

    **BONUS DEFECT FIXED:** `_explore_on` was derived **TWICE** — once at the config block
    and once **inside the DSR block from a SECOND direct read of the repo's `config.json`
    that BYPASSED `main.load_config`**, so an injected config **could not influence OF-5's
    phase**. Now derived **once**, through the injectable path. This also exposed a brittle
    assertion in `tests/test_audit_ml_offline.py`: a **bare substring check** read
    `"2|0 live labeled trades"` as the `"0 live labeled trades"` it meant to forbid, so it
    **FAILED on a report that proves the fix** — now **word-boundary anchored**
    ([[synthesis/documentation-drift-register]]).

    **BATTERY ALL GREEN:** pytest **3473 + 1 skipped** parallel / **19** serial timing /
    smoke 219 / assurance 49 / **overfit 3 pass 0 fail** / ruff / pyright / bandit /
    compileall / quant G1–G5. **The first fully-green battery since the incident**, and
    **the first ever in which the overfit stage grades the LIVE corpus rather than falling
    back to synthetic** — a stronger green than any that preceded it, reached without moving
    a number.

    *Residue carried forward, not closed by this decision:* the corpus is still
    **data-starved** on the battery's own learning curve (delta_auc **+0.112**, CLIMBING),
    and the two named exits — **corpus growth** or **feature-count reduction** (item **45f**)
    — are unchanged ([[concepts/dof-budget]]). The policy stops a model-readiness reading
    from blocking code deploys; **it does not make the model ready.**

    *Original registration preserved below.*
    > ⚠️ **This entry is written for the first time on 2026-08-09, and its root cause is a
    > CORRECTION.** [[sources/session-20260808-night-staleness-overfit]] §2 registered
    > "item 46" but **never created the entry**, and the root cause it stated was **false
    > in both halves**: there is **no 60-row threshold** (the predicate is
    > `len(X) >= len(FEATURE_NAMES)*10` = **640**, `scripts/overfit_check.py:180-182,:207`;
    > the flat `60` was **deleted 2026-07-11 by `7486ab29`**), and `len(X)` counts
    > **LOADED** rows — candidate + live, after every filter — **not live rows** (the
    > corpus holds **305 live rows total** and is append-only, so that battery's printed
    > **"live rows=467" was arithmetically impossible**). The flip was the **era-filter
    > DISARM** caused by the `label_era` corruption: **33 rows appended (all candidate)
    > between the 17:06 and 23:30 batteries while the loaded count went 467 → 9,739.** Two
    > stale strings caused the misreading (docstring `:9`, report string `:216`, both
    > mislabelling total loaded rows as "live rows"); **both fixed at source in
    > `3c0debd7`**.

    **The honest state on the REPAIRED corpus: 3 pass / 4 fail, and NO THRESHOLD WAS
    MOVED** ([[concepts/never-widen-a-gate]]).
    - **OF-1 memorization gaps +0.422 / +0.414 / +0.503** (logistic / gbt / mlp) —
      **WORSE** than the pooled corpus's +0.19..+0.27, **exactly as a smaller, cleaner
      corpus should be**; the pooled reading was flattered by ~9,000 other-era rows.
    - **OF-7 `dead_frac` 0.95** — 61 of 64 features at near-zero importance.
    - **OF-7 rows/feature 10.8 — PASSES, barely** (690 rows / 64 features).
    - **shuffle and purge PASS.**
    - The audit's own learning-curve diagnostic: **"CLIMBING (delta_auc=+0.112) —
      data-starved: more rows are still buying skill; corpus growth is the
      highest-leverage learning input right now"** — the 2026-08-08
      [[concepts/dof-budget]] adjudication **restated by an independent instrument that
      was not told the answer.**

    **The battery cannot go green at the overfit stage until the corpus grows or the
    feature count drops** (item **45f**, the schema-AB prune experiment — the two named
    exits are the same two the DoF ledger names). **[[entities/auto-update]]'s deploy gate
    (`auto_update.battery_passes`) is blocked meanwhile**, for any external push regardless
    of its content.
    ~~**Policy options registered, NOT decided** — the operator's call, and gate-widening is
    forbidden without conscious re-baselining ([[concepts/conscious-re-baseline]]):
    **(a)** exploration-phase **informational** grading for OF-1/OF-7 (the DSR precedent —
    "informational not gating during exploration"); **(b)** **hard block** until the corpus
    grows past the honest thresholds; **(c)** **`--force-synthetic`** in the battery until
    era-3 matures (validates the machinery, not the corpus).
    *Closes on:* an operator decision recorded as a conscious re-baseline, **or** the
    corpus/feature-count change that makes the question moot.~~
    **DECIDED 2026-08-09: (a).** (b) was rejected because the thing being blocked was
    **code correctness**, which the corpus has no business gating; (c) was rejected because
    `--force-synthetic` would have **hidden the live reading entirely** — the opposite of
    the property the informational path was built to preserve.

47. ~~**The WEDGED CHAMPION — operator adjudication owed**~~ **CLOSED 2026-08-09 02:56:04 —
    RESOLVED WITHOUT INTERVENTION. No override, no re-baseline, no commit: the codebase's
    OWN already-adjudicated ML-083 doctrine handled it, and the restraint that left the gate
    alone is what allowed that to be visible**
    ([[sources/session-20260809-gate-policy-and-self-heal]] §1).

    **The audit-confirmed mechanism** (`outputs/audit.jsonl`, three records 4ms apart):
    **ML-016** 02:56:04.391 `admitted ["logistic"]`, live **6**, total **701** →
    **ML-083** 02:56:04.480 `trained_rows 9708 > corpus_rows 701`, `challenger_brier
    0.24727982125184214`, `n_oof 464` →
    **ML-040** 02:56:04.483 `decision DEPLOY`, **`ignore_champion: true`**.
    The **era-orphan branch at `main.py:6330`** fired: the champion's watermark
    (**9,708** — the corrupted pooled population) **EXCEEDED** the current training matrix
    (**701** rows, after the repair re-armed era exclusion), so the like-for-like fresh-row
    set is **empty BY CONSTRUCTION** and the badge is **unfalsifiable**. Per the
    **ML-076/ML-083 doctrine — *an unfalsifiable badge may not gate*** — the orphaned badge
    was **set aside entirely** and the challenger faced the **true COLD-START standard**:
    `Brier < 0.25` + `deploy_min_oof`. **`logistic` scored 0.24728 < 0.25 and DEPLOYED on
    701 clean rows.**

    **The arithmetic that PROVES the mechanism** (read off `ml/monitor.py:667-668`, not
    inferred from the outcome): under the **NORMAL** branch,
    `0.24728 < 0.1537 − 0.005` is **FALSE** and `champion_brier >= 0.25` is **FALSE** — so
    the normal branch would have **REJECTED**. **Only the ML-083 path deploys.**
    **The corpus repair is what made the watermark exceed the matrix, and therefore what
    triggered the self-heal.**

    **Verified live at filing:** `outputs/meta_model.json` `kind=logistic rows=701
    oof_brier=0.24728`; `outputs/status.json` `ml.model_kind=logistic`, era
    **`armed=True`/`active=True`**, load rows **701**, `live_clean` **6**.
    **THE BUG-PROMOTED GBT IS NO LONGER TRADING.**

    **The lesson, filed as a POSITIVE instance for [[concepts/false-green]] and the
    evidence concepts:** the **corpus repair was the necessary AND sufficient
    intervention** — the model layer **healed itself once the data was true**. Forcing the
    gate would have produced the same visible outcome while **masking that the system could
    reach it alone**, and would have spent a conscious-re-baseline decision that was never
    needed. **The system's own doctrine outperformed the proposed override**, and it did so
    on a polarity ML-083 was never written for, because it keys on the **structural**
    condition (`trained_rows > len(X)`) rather than on the story.

    *Structural residue, STILL OPEN and unchanged by this resolution:* **a stored watermark
    records a score and not the corpus that produced it.** ML-083 detected the orphaning via
    a **row-count proxy**; it would **not** have fired had the corrupted corpus happened to
    be smaller than the clean one. Adding provenance (corpus revision, era set, row count)
    to the champion record makes **both** spellings of this class detectable rather than
    incidentally caught. *Closes on:* that provenance stamp shipping.

    *Original registration preserved below.*
    `train_meta` on the repaired corpus **correctly** re-gated selection to
    **`['logistic']`** (live=6, total=692; `gbt`/`blend`/`mlp`/`adaptive_gbt` skipped —
    [[concepts/evidence-floors]] and the [[concepts/simplicity-ladder]] behaving exactly as
    designed). **But the champion gate REJECTED the swap: challenger OOF Brier 0.2714 vs
    champion 0.1537.** The champion's **0.1537 was measured on the CORRUPTED pooled
    9,708-row corpus** — so the gate is comparing scores computed on **incommensurable
    evaluation sets**, the **bug-promoted `gbt` is WEDGED in place**, and **no clean-corpus
    challenger can dislodge it**. A second, worse instance of [[concepts/ghost-badge]]
    (instance 1's badge described a real vanished population; this one describes a
    population that **never legitimately existed**) and the mirror polarity of
    [[concepts/deploy-deadlock]] (a champion locked **IN**, not challengers locked out).
    **The gate was deliberately NOT overridden** — CLAUDE.md forbids bypassing gates, the
    gate is correct given its inputs, and re-baselining is a **conscious operator act**.
    *Recommendation to adjudicate:* **retire the champion baseline as BUG-ATTRIBUTABLE and
    re-baseline on the clean corpus** — the same verb bug-attributable consumption earned
    in [[sources/session-20260808-budget-reanchor]]. *Safety net meanwhile:* the
    [[entities/ml-governor]] still grades the live model on **realized outcomes**, so a
    wedged champion that is genuinely bad is attenuated by measurement even while selection
    cannot move. *Closes on:* the recorded re-baseline decision (either way).
    *Structural residue, worth its own fix whichever way 47 is decided:* **a stored
    watermark records a score and not the corpus that produced it** — add provenance
    (corpus revision, era set, row count) to the champion record and **both** spellings of
    this class become detectable instead of arguable.

48. **The corpus-corruption incident's own residue** ([[sources/session-20260809-corpus-corruption]];
    repo-side/box-side). The defect is **FIXED** (`3c0debd7`: persisted `label_era` passed
    through, derive only when absent, in **both** `scripts/migrate_history.py:125` and
    `scripts/session_import.py:244` — the latter runs **hourly and unattended**) and the
    **corpus is REPAIRED** (2,729 cells restored by `position_id` join from two preserved
    backups, most-qualified-wins, **0 conflicts**, **0 rows added/removed/reordered**,
    concurrent-append-safe, pre-repair backup `signal_history.csv.prerepair_1786253662`
    retained; verified after: era `armed=True`/`active=True`, load **9,746 → 690**,
    `live_clean` **299 → 6**). **Re-corruption risk is CLOSED** — `pc_supervisor` spawns
    `corpus_sync` as a **fresh process** (`_spawn` at `:657`), so it picks the fixed
    migrator off disk; no stale in-memory code hazard. **Three tests pin it**
    (`tests/test_migrate_history.py`, red-first by construction): persisted-era preserved ·
    **migration is a fixed point** · legacy row still derives.
    **What remains OPEN is the generalization, not the instance:**
    **(a)** the fixed-point property is pinned for **this** migrator only — nothing stops a
    future migrator, importer or backfill from being non-idempotent
    ([[concepts/migration-idempotence]], [[concepts/adoption-is-not-enforcement]]);
    *closes on* a shared fixed-point contract or an AST/-property gate over every corpus
    rewriter, in the shape `test_append_invariant.py` set for the append class.
    **(b)** **every measurement taken between 2026-08-08 20:01:46 and the repair is
    corpus-conditioned and must not be cited** — including the deployed `gbt` champion's
    0.1537 (item 47) and the 08-08-night OF-1/OF-7 readings (item 46's struck numbers);
    *closes on* nothing — it is a standing citation embargo, recorded so the numbers are
    not innocently re-used, exactly like the pre-boundary fill statistics.
    **(c)** the **detector** is owed, not just the fix: nothing today alarms on *"the
    loaded corpus jumped by 9,272 rows while 33 were appended"* or on *"four evidence
    floors cleared in one step"* — both were present, both were readable, neither was read;
    *closes on* a load-time assertion that the current-era count cannot fall (an
    append-only corpus's era counts are **monotonic** absent corruption), which is a
    cheaper and more general tripwire than any of the above.

49. **The CLI/runner ML-083 ASYMMETRY — the bot's own instruction leads the operator to a
    verdict the bot itself would not reach** ([[sources/session-20260809-gate-policy-and-self-heal]]
    §2; repo-side. **Registered 2026-08-09 and deliberately NOT bundled into `8e9d7e6f`** —
    a gate-policy commit and a deploy-gate behaviour change are two reviewable things,
    not one).
    `scripts/train_meta.py:122` calls
    `monitor.should_deploy(challenger_brier, n_oof=n_oof)` **without the era-orphan
    detection `main.py:6330` has**. The CLI therefore applies the **stale incomparable
    badge** where the runner correctly **sets it aside** — so **the CLI REJECTS challengers
    the runner ACCEPTS**.
    **It bit live on 2026-08-09:** at **00:52** the CLI **REJECTED** `logistic` at
    **0.2714** on the badge comparison; at **02:56:04** the runner **DEPLOYED** `logistic`
    at **0.2473** via ML-083 against the **same wedged badge**. Two hours apart, same
    corpus, same doctrine, opposite verdicts.
    **The trap is sharp because the bot's OWN ML-032 message instructs the operator to run
    `python scripts/train_meta.py`** — and the CLI's rejection message asserts *"This
    mirrors the bot's own auto-retrain deploy gate"* (`train_meta.py:126`), a claim that is
    **false in exactly this case** ([[synthesis/documentation-drift-register]]: a string
    that ships inside a running instrument and is believed because it runs).
    *What would close it:* mirror `main.py`'s `int(champ.trained_rows) > len(X)` condition +
    the **ML-083 audit log** + `ignore_champion=True`, with a red-first test pinning that the
    two paths agree on an era-orphaned badge. Note this item is itself an instance of
    [[concepts/two-paths-one-quantity]] — **one decision, two derivations** — so the
    preferred shape is **one shared gate function both callers invoke**, not a second copy
    of the condition.

50. **THE CORPUS CANNOT SEE ITS OWN COSTS — HIGH** ([[sources/session-20260809-unbiased-economics]]
    §3; repo-side, verified against the live 93-column header. **Registered 2026-08-09.**)

    `outputs/signal_history.csv` carries **`net_pnl_usd`** (column 69) and **NO gross column**
    and **NO per-row fee column**. It is the only fee-adjacent field in the file. Therefore:

    **(a)** **No row can distinguish "the signal was wrong" from "the signal was right and costs
    ate it."** Two opposite diagnoses with two opposite fixes, recorded identically.

    **(b)** **No offline analysis can compute gross edge by subpopulation** — asset, regime,
    horizon, signal strength. This is **the single most decision-relevant question currently
    open** ([[synthesis/open-contradictions-register]] item 21 cannot be resolved without it),
    and it is not merely unanswered — it is **unaskable from this file**.

    **(c)** **`ml/postmortem.py` cannot decompose either.** Its terminal fallback bucket
    (`postmortem.py:334`, `return "underperformance"` — *"closed below expectation without a
    single dominant cause"*) absorbs **202 of 264 postmortems = 76% of trades die undiagnosed.**
    The taxonomy's other buckets (`cost_overrun`, `alpha_wrong`, `regime_shift`, `fear_event`)
    are sound; **the inputs required to reach them are missing.** The 76% is a starved
    instrument, not a weak taxonomy.

    **(d)** **The binary win/loss label conflates the two cases at the point where the MODEL
    learns**, so the learner is **structurally incapable of learning the distinction no matter
    how many rows accrue.** This is the sharpest reading: **corpus growth cannot fix it**, which
    is exactly why *"the corpus needs to grow"* fails as an account here
    ([[concepts/dof-budget]], [[concepts/unfalsifiable-explanation]]).

    *What would close it:* add **`gross_pnl_usd`** and **`fees_usd`** as **trailing** corpus
    columns via the established extend-with-defaults ritual (header + `migrate_history` pad +
    the downstream pins), backfilled offline from `outputs/fills.csv`, which carries per-fill
    `fees_delta_usd` keyed by `position_id`. **Own change, own battery — explicitly NOT
    bundled.** The idempotence fix (`3c0debd7`) makes the resulting rotation safe: *the exact
    path that corrupted the corpus is now fixed and tested*
    ([[concepts/migration-idempotence]], item 48).

    ⚠️ **Sequencing dependency:** the backfill sources from `fills.csv`, which is **short by
    6.24 (1.6%)** against `fees_paid_total` ([[synthesis/open-contradictions-register]] item
    18). **Close or declare that gap before the backfill**, or the corpus learns a
    systematically optimistic view of its own costs.

    ⚠️ **DoF note:** these are **bookkeeping** columns, never features — the same discipline the
    price anchors and the availability quartet were filed under (item 41b). The DoF ledger stays
    **CLOSED**; this costs **0 model degrees of freedom**.

51. **THE FREE POPULATION HAS NEVER BEEN SEARCHED — adjudication input, no owner**
    ([[sources/session-20260809-unbiased-economics]] §5. **Registered 2026-08-09 as a standing
    question, not a decision.**)

    **9,570 CANDIDATE rows are counterfactual and cost ZERO fees**, against **305 live rows that
    cost ~382.59**. If gross edge exists anywhere, it can be searched for in the free population
    **without paying another cent of fees**.

    *Standing rule this establishes:* **any plan that proposes "trade more to learn more" must
    first state why the free, 31x-larger sample cannot answer the same question.** This is the
    operational form of the falsifier now attached to [[concepts/priced-bleed]].

    *What would close it:* a report-only gross-edge read over the candidate population (blocked
    on item 50 for the live side; the candidate side may be computable sooner since counterfactual
    rows have no fees to net out — **verify that before assuming it**). Note the candidate
    population is **not** a free lunch: it is counterfactual, never subject to fill hazard, queue
    position or adverse selection, so a positive read there is **necessary and not sufficient**
    evidence ([[concepts/paper-real-boundary]]).

---

## The 2026-08-09 adversarial-audit docket — items 52-83, SEVERITY-ORDERED

Source: [[sources/session-20260809-adversarial-audits]] — 47 read-only agents across two audits
(22 on the Grafana panel/metric chain, 25 hunting self-flattery). **Two of the audits' findings
already SHIPPED and are not registered here** (`1fee174e` the sizer's empty book, `a6334162` the
all-in P&L reporting). What follows is what did **not** ship.

> **Docket status as of 2026-08-09 evening** ([[sources/session-20260809-turing-test-hedge-verdict]]):
>
> | item | status |
> |---|---|
> | **52** | (a) open · **(b) counterfactual MEASURED, decision STILL OPERATOR-OWNED** |
> | **53** | **CLOSED** — `415af0f9`, five files wide; **53-residual** open |
> | **54** | code **SHIPPED** `f11b7e32`, **INERT** — not closed |
> | **55** | **PARTIAL** — export shipped, board regeneration owed |
> | **56** | **CLOSED** — `415af0f9` (same commit as 53) |
> | **57** | **CLOSED 2026-08-10** — `aeeaae36`, **EXECUTION-ERA BOUNDARY #4**; residuals **57b** (recalibration, folds into 40b) and **61** (queue gating now inert) |
> | **58** | not new (the `fills.csv` 6.24 gap) |
> | **59** | **NEW** — status-schema / fixture drift |
> | **60** | **NEW**, agent-raised — sub-minimum dust orders filled in sim |
> | **61** | **NEW 2026-08-10** — created by 57's fix: MP-7 queue gating is inert, deliberately unfixed |
> | **62** | **NEW 2026-08-10 evening — registered and SHIPPED SAME DAY** (`6fe6d98d`, OM-085): the fills.csv restart-replay duplicate guard |
> | **63** | **NEW 2026-08-10 evening** — raw ws book capture, the only instrument for intra-poll fill bias; REGISTERED, not started |
> | **64** | **NEW 2026-08-10 evening** — escalation-loss crash window; documented, deliberately unfixed (benign) |
> | **65** | **NEW at the Grand Synthesis filing — CLOSED SAME SESSION** (`2602371b`): trade-path ledger decontaminated (row quarantined, five harnesses redirected); caught twice — vault verification + **battery 14 RED via the conftest tripwire (its first confirmed catch)** |
> | **66** | **NEW at the Grand Synthesis filing — SATISFIED 2026-08-10**: both sweeps filed, battery 15 ALL GREEN (`BATCH_EXIT=0` verified directly) → **synthesis delivered** ([[synthesis/grand-synthesis-algorithm-package]]); geometry-epoch adjudication remains with the operator |
> | **67** | **NEW at the cut-#7 session** — the ALGO-5 amendment (replay-parameterized widths + decay ladder at ~30 uncensored paths); PRE-NAMED next boundary-minting adjudication |
> | **68** | **NEW at the 2026-08-11 since-6am audit — CLOSED by `66744ed1`** (the apply-batch): long-book discarded `_feature_extras`; meta now threads from the same extras dict |
> | **69** | **NEW at the 2026-08-11 since-6am audit** — h432 anti-momentum pattern; INSTRUMENTED (`defensive_cadence_report.py` §2b), still a LEAD |
> | **70** | **NEW at the 2026-08-12 lockout filing** — the 60 "capped" (`can_enter=False`) dispositions: source unpinned; residual diagnosis owed |
> | **71** | **NEW at the 2026-08-12 lockout filing** — SZ-050 anomaly: dd 7.9% while flat at $800, MTM base ~737 unexplained; WATCH item |
> | **72** | **NEW at the 2026-08-12 lockout filing** — the reset-completeness test: enumerate every calendar/dollar-anchored persisted section ([[concepts/reset-completeness]]) |
>
> **Docket update 2026-08-10** ([[sources/session-20260810-fill-double-count]]): item **57**
> closes as the docket's **largest single distortion** — **1.88x at the touch**, and the closure
> confirmed the ⚠️ banner above **from the inside**. The distortion did not merely *run* in the
> flattering direction; **its 2026-08-08 DISPOSITION did too.** The double-count had been
> correctly named on 08-07 and was disposed of as *"conservative floor, by design"* on 08-08 —
> a framing that was **backwards**, and that kept the bias alive for two more days. **Add
> adjudications to the list of surfaces the self-flattery gradient acts on**
> ([[concepts/self-flattery-gradient]]).
>
> **`a6334162` — the commit this docket credits as already-shipped — is itself the cause of item
> 59.** A fix that ships new status keys without pinning the fixture is how the next latent defect
> enters. Recorded because the docket's own framing invited the assumption that shipped items need
> no further watching.

> **The operator's own severity order is preserved as the numbering.** Item 58 is not new — it is
> the pre-existing `fills.csv` 6.24 gap, listed here so the docket is complete as an execution
> queue.

> ⚠️ **Every item on this docket is an instance of [[concepts/self-flattery-gradient]].** All six
> distortions run the **same direction** — the bot looks better than it is. When they are fixed,
> **every affected number moves DOWN.** Budget for that before starting, not after.

52. **THE PERFORMANCE LEDGER AND THE CIRCUIT BREAKER ARE BOTH BLIND TO THE HEDGE BOOK —
    HIGHEST SEVERITY; HALF OF IT NEEDS OPERATOR ADJUDICATION** (repo-side defect, sim-side
    numbers; `main.py:1671`. **Registered 2026-08-09.**)

    One predicate — `if not pos.is_hedge:` — gates **BOTH** `perf.record_close` **AND**
    `breaker.record_close`. The entire **−325.70 hedge book** is invisible to:

    **(a)** expectancy / win rate / profit factor / Sharpe, and
    **(b)** the **consecutive-loss circuit breaker**.

    **This is why 159 consecutive losing hedge round trips over 10.4h never tripped the breaker:
    they were never recorded as losses.** `status.json` implies **200 trades × −0.2838 = −56.76**
    against a true closed book of **−387.96**.

    **The two halves are NOT the same question and are deliberately filed unsplit:**

    - **(a) is clear.** The performance ledger **should** see hedges — they are real money and
      they are in the P&L. No design question exists here; only the work.
    - **(b) is a GENUINE DESIGN QUESTION AND BELONGS TO THE OPERATOR.** A hedge is
      **risk-reducing insurance that often loses BY DESIGN**; counting hedge losses could trip
      the breaker **during correct operation**. And the 159-loss run was a **churn bug** (FW-070,
      since fixed — [[sources/session-20260807-hedge-churn-guards]]), **not** normal behaviour.

    > **Changing what a circuit breaker counts changes WHEN IT FIRES.** That is a gate-semantics
    > change, and the filing agent **deliberately did not take it**
    > ([[concepts/never-widen-a-gate]]). Note the asymmetry that makes this urgent rather than
    > academic: the current state is the **permissive** one — the breaker under-counts losses
    > today, so *doing nothing* is itself a choice in the flattering direction.

    *What would close it:* **(a)** pass hedge closes to `perf.record_close`, with the
    probe/conviction/hedge split of item 54 landing in the same shape. **(b)** an operator
    decision, recorded with its reasoning, on whether the consecutive-loss breaker counts hedge
    legs — plus, if the answer is yes, a re-derivation of the threshold against a book where
    insurance legs lose by design. **Do not bundle (a) and (b) in one commit.**

    ---

    #### 52(b) — THE COUNTERFACTUAL IS NOW MEASURED. THE DECISION IS STILL THE OPERATOR'S.
    *(Added 2026-08-09, [[sources/session-20260809-turing-test-hedge-verdict]] §4. **STATUS
    UNCHANGED: AWAITING OPERATOR ADJUDICATION.**)*

    **Method:** replay the **shipped** `CircuitBreaker` over the **real close sequence**, once as
    it runs today (hedges invisible) and once with hedge closes counted.

    | | breaker trips, 19.5 days |
    |---|---|
    | as shipped (hedges invisible) | **42** |
    | counting hedges | **43** |
    | **cost of counting hedges** | **+1 trip in 19.5 days** |

    **Benefit on the one event that mattered:** counting hedges would have **stopped the churn
    after 4 round trips instead of 147**. Historical context: the breaker has fired **48 times
    across 12 assets**.

    > **The asymmetry, stated without a recommendation.** The stated fear was that counting
    > insurance legs — which **lose by design** — would trip the breaker during **correct**
    > operation. The measured price of that fear is **one extra trip in nineteen and a half
    > days**. The measured benefit is **143 laps of churn not taken**, which at the rates in
    > [[sources/session-20260809-turing-test-hedge-verdict]] §2 is the large majority of **77.3%
    > of the book's lifetime fees**.

    **This does NOT close 52(b).** A measurement was owed and is now supplied; **gate semantics
    are not decided by measurements** ([[concepts/never-widen-a-gate]]). What remains owed is
    unchanged: **an operator decision, recorded with its reasoning** — and, if the answer is yes,
    a re-derived threshold.

    ⚠️ **The FIRST version of this replay was wrong and reported the opposite.** It never called
    `is_tripped()`, so every asset tripped exactly once and both arms produced an identical trace
    **by construction** — a false **"no difference."** Self-caught; filed as
    [[concepts/tautological-instrument]] wearing the costume of
    [[concepts/honest-null-result]]. **Any earlier citation of "counting hedges makes no
    difference" is retracted.**

53. ~~**THE GO/NO-GO TOOL PRINTS THE OPPOSITE OF ITS OWN METHOD'S ANSWER**~~
    **CLOSED 2026-08-09 — SHIPPED as `415af0f9`, and the defect was FIVE files wide, not one.**
    (`scripts/breakeven_test.py:126`; sim-side numbers, repo-side defect.
    **Registered 2026-08-09; independently VERIFIED by the filing agent.**)

    > **CLOSED.** `415af0f9` landed *hedge-is-an-opening-leg* across **five** scripts —
    > `breakeven_test`, `cost_attribution`, `cost_truth_report`, `geometry_search`,
    > `random_entry_control` — which also **closes item 56**. The docket estimated *"~10 lines"*
    > on one file; the estimate was wrong about the **blast radius**, not the fix.
    >
    > **Measured after shipping:** **235 → 394** closed round trips, **165 → 6** skipped,
    > **median gross +0.0505% → −0.0305%**, and **the tool's prescription INVERTED** to
    > *"no execution change, holding period, gate, filter or model creates expectancy that is not
    > in the entries."*
    >
    > **Numeric note (domain rule 2):** the audit predicted **−0.0303%**; the shipped fix measures
    > **−0.0305%**. A **0.0002pp** difference, recorded rather than smoothed. **−0.0305% is the
    > citable figure.**
    >
    > ⚠️ **PARTIAL — the skip counter BY REASON did not ship.** **6 skips remain and their reasons
    > are not itemised**, so *"partial"* and *"deliberately excluded"* can still share a bucket
    > ([[concepts/uncounted-exclusion]]). **Carried forward as item 53-residual.**
    > ([[sources/session-20260809-turing-test-hedge-verdict]] §5)

    The tool counts **only `purpose == "entry"`** as the opening leg, so **all 159 COMPLETE hedge
    round trips are discarded** under **"165 skipped: partial or malformed."** **None are
    malformed** — they close to within **0.0%** of opening size.

    | | shipped | corrected (`entry`\|`hedge`) |
    |---|---|---|
    | closed / skipped | 235 / 165 | **394 / 6** |
    | gross | −3.03 | **−13.01** |
    | fees | 59.23 | **374.96** |
    | net | −62.27 | **−387.96** |
    | **median gross** | **+0.0505%** | **−0.0303%** |

    **The sign flips, and the sign selects the branch the tool PRINTS** — from `:214-230`
    *"This is NOT 'no edge' … that is exit geometry … fixable without touching the signal"* to
    `:231-241` *"GROSS EXPECTANCY IS NEGATIVE … no execution change, holding period, gate, filter
    or model creates expectancy that is not in the entries."*

    > **Two opposite instructions about where to spend the next month of work, and the tool has
    > been printing the wrong one.** Everything the corpus has cited from this tool's verdict
    > line should be re-read.

    *What would close it:* **~10 lines** (`purpose in {"entry", "hedge"}`) **plus a skip counter
    broken out BY REASON**, so *"partial"* and *"leg type deliberately excluded"* can never share
    a bucket again ([[concepts/uncounted-exclusion]]). Then **re-run and re-file the verdict.**

54. **`performance.overall` POOLS PROBES WITH CONVICTION TRADES, COUNT-WEIGHTED**
    (`main.py:1650`/`:1672`; sim-side numbers. **Registered 2026-08-09.**)

    91% of the sample is **EV-gate-BYPASSED probes**. Inside the exact 200-close window
    (197/200 joined): **probe n=182 expectancy −0.1636**, **conviction n=17 expectancy
    −1.5840**, **reported pooled −0.2838** — a **5.6x understatement of the population the
    strategy is actually about**. `sharpe −1.067`, `sortino −0.751`, `max_loss_streak 57` are all
    computed on the mixed sample and **describe neither population**.

    `pos.is_probe` **is in scope 22 lines earlier** and simply not passed.

    > **The codebase already holds the opposite doctrine:** `overfit_check.py:1031-1034` refuses
    > to grade DSR on the mixed sample **for exactly this reason**. The correction lives in the
    > ML-validation lane and never travelled to the P&L-reporting lane
    > ([[concepts/pooled-populations]]).

    ⚠️ **Do not "fix" this by re-weighting.** The audit corrected itself: **notional weighting
    does NOT support the argument** (return-on-notional **−0.692% probe vs −0.479% conviction**,
    the opposite ordering). **The SPLIT is the repair.**

    *What would close it:* pass `is_probe` at `main.py:1672`; emit **overall / conviction /
    probe** blocks; compute **streaks within-population**; board and status keys follow.

    > **CODE SHIPPED 2026-08-09 (`f11b7e32`) — AND IT IS CURRENTLY MEASURING NOTHING.**
    > The split landed with a **third `unknown` bucket** for pre-upgrade rows. Live reading:
    > **`unknown 200 · probe 0 · conviction 0`.** Every live row predates the flag, so item 54's
    > actual finding (**probe n=182 −0.1636 vs conviction n=17 −1.5840**, the 5.6x understatement)
    > **cannot yet be reproduced from the live split.**
    >
    > **STATUS: shipped, INERT, NOT CLOSED** ([[comparisons/dormant-vs-inert-features]]; domain
    > rule 5 — *shipped is not working*). **What still closes it:** enough post-upgrade closes for
    > the probe and conviction buckets to be non-empty, then a re-measurement filed against them.
    >
    > ***STATUS CHANGE 2026-08-14 — POPULATING, still NOT CLOSED***
    > ([[sources/session-20260814-cohort-instruments]] §supporting measurement). The buckets are
    > no longer empty: over the exact 24h window `[1786664298, 1786750698]`, live rows in
    > `signal_history.csv` carry the flag — **`probe=1` × 3, `probe=0` × 1** (the 119 blanks are
    > `source=candidate`). The first half of the closing condition is met. The second is not:
    > **at n=4 the 5.6x specimen still cannot be reproduced**, and a re-measurement filed on four
    > rows would be exactly the mixed-sample error this item exists to correct.
    > **The finding that arrives with it is the more useful one:** three of the four live rows
    > are probes, so the live corpus is now **75% probe** — the pooled population is dominated by
    > the lane that bypasses the EV gate, which is the condition item 54 was registered against,
    > now realized at corpus level rather than in one report
    > ([[concepts/probe-livelock]] §terminal state, [[concepts/pooled-populations]]).
    >
    > The `unknown` bucket is the **right** design — it refuses to guess a label for rows that
    > never carried one ([[concepts/zero-is-not-a-reading]] applied to a category rather than a
    > number) — and it is *why* the item stays open rather than closing on a fabricated backfill.
    > ([[sources/session-20260809-turing-test-hedge-verdict]] §6a)

55. **THE DRAWDOWN GAUGE PLOTS A DIFFERENT QUANTITY THAN THE HARD STOP THAT FIRES ON IT —
    DECISION-GRADE** (audit A defect **D2**; `runner.py:984`, `gc_pusher`, command board panel
    id **23**, problem/solution board panel id **23**. **Registered 2026-08-09.**)

    Both gauges plot **`drawdown_pct` = (start − cash − savings)/start** — **start-to-now,
    cash-only** — while the **15% hard-stop flatten AND the throttle both read
    `drawdown_mtm_pct`** (**peak-to-now, mark-to-market**).

    **Reproduced on live code:** a book **−20% on marks** fires `hard_stop_triggered`
    (*"20.00% >= 15%"*) **while the gauge reads 0.0, FULL GREEN.** The **inverse is already
    pinned** in `tests/test_audit_config_risk.py:281-288`, where a **WINNING account pegs the
    same gauge at 15.0, red.** The suite already knew; nothing connected it to the panel.

    **`runner.py:984` computes `drawdown_mtm_pct` and DISCARDS it as a local.** `gc_pusher`
    carries only `drawdown_pct`. **No board references the MTM series at all.**

    The audit's headline is **THREE DERIVATIONS OF ONE WORD** ([[concepts/two-paths-one-quantity]],
    **decide** rung). Two are cited above; the third is implied by the retitle below (the gauge
    omits the `reserve` term). **Recorded as the audit's count, two derivations verified.**

    *What would close it:* export `drawdown_mtm_pct` from the runner; add it to `gc_pusher`;
    **repoint both gauges**; **retitle the survivor** *"Realized drawdown from start
    (reserve-inclusive)"* so the two quantities keep two names. **Board work goes into the ONE
    regeneration below — the JSON is never hand-edited** ([[entities/observability-sidecars]]).

    > **PARTIALLY SHIPPED 2026-08-09 (`f11b7e32`) — the export half is done, the board half is
    > not.** `drawdown_mtm_pct` and `hard_stop_dd_pct` are now exported. Live:
    > **`drawdown_mtm_pct 7.6706`** vs **realized-only `7.89`**, throttle at **`0.3416`**. The
    > **hero tile is repointed to `net_pnl_all_time`** (the **D1** item below).
    >
    > **Note the direction — it is the OPPOSITE of this item's worked example.** The audit's
    > reproduction had the gauge **green** while the stop fired; live, the **MTM figure is LOWER
    > than the realized-only figure**. The two series diverge **in both directions**, which is the
    > argument for **two names and two panels** rather than picking a winner
    > ([[concepts/two-paths-one-quantity]]).
    >
    > **STILL OWED:** the **board regeneration** — gauge repoints plus the retitle of the survivor.
    > ([[sources/session-20260809-turing-test-hedge-verdict]] §6b)

56. ~~**`cost_attribution.py` IS STRUCTURALLY BLIND TO ITS OWN LARGEST COST EVENT — MEDIUM**~~
    **CLOSED 2026-08-09 — SHIPPED in `415af0f9`** (same commit as item 53; `cost_attribution` was
    one of the five scripts). **The by-reason skip counter is the shared residual — see 53.**
    (`scripts/cost_attribution.py:126`; sim-side numbers. **Registered 2026-08-09.**)

    A **bare `continue` with NO skip counter**, the same hedge blindness as item 53. The reader
    sees **n=1019** in one paragraph and a cost from **n=235** in the next, with no signal that
    the populations differ.

    ⚠️ **Corrected DOWNWARD from the initial hunt:** the printed **0.668%/trade is CORRECT** for
    the **235 directional trades**; the honest blended figure is **0.7766%** — **1.16x, NOT the
    6.4x first claimed.** Severity is **MEDIUM** and the reason is not the gap: it is that **a
    cost-attribution tool cannot see its own largest cost event.**

    *What would close it:* skip counter **by reason**, plus the blended figure reported beside
    the directional one with both populations named.

57. ~~**THE FILL SIM GIVES A RESTING ORDER TWO CHANCES PER EVENT**
    (sim-side, and it is a **sim-integrity** item. **Registered 2026-08-09.**)

    **22.30% per-order fill against an 11.66% calibration target at the touch**, because resting
    maker orders get **TWO independent chances to fill per modelled event**. **⇒ roughly half the
    near-touch paper entry population describes fills the recorded market never granted.**

    **Bounded: 1.19x at 20bps → 1.91x at the touch**, weighted toward the high end because **57%
    of post-only fills rest within 5bps.**

    ⚠️ **Propagation into the 305 live corpus rows and into the 432-bar cohort verdict is
    DIRECTIONALLY SUPPORTED but UNVERIFIED** — stated as such, and **it may not be cited against
    the 432-bar hold** until it is measured (domain standing question 3).

    *What would close it:* identify and remove the second draw; re-run `calibrate_fills.py`; then
    decide whether the change **mints a FOURTH execution-era boundary** (three exist — domain
    standing question 4). Until then every paper fill-rate statistic carries this as a known
    upward bias ([[concepts/paper-real-boundary]]).~~

    **CLOSED — commit `aeeaae36`, stamp `2026-08-10 06:03:35 −05:00` = `2026-08-10T11:03:35Z`,
    pushed (`origin/main == aeeaae36`), runner bounced onto it at 06:06:01 local. EXECUTION-ERA
    BOUNDARY #4 MINTED.** ([[sources/session-20260810-fill-double-count]].)

    **MECHANISM, confirmed three independent ways** — own derivation, the calibration source, and
    the vault's own **2026-08-07** log entry which had already named it:
    `scripts/calibrate_fills.py` measures **f = "how often the MARKET actually crossed a
    hypothetical resting limit within its life"** from recorded book frames;
    `core.fill_calibration.invert_base_prob` solves `passive_base_prob` so **the HAZARD ALONE
    reproduces f** over `n_bar` polls (`p_poll = 1−(1−f)^(1/n_bar)`; `sf_base = p_poll·exp(d_bar)`);
    `_poll_dry` then **ALSO** called `_sim_maker_cross`, which fills full remaining
    deterministically whenever the book crosses — **the very event f counts**. Decisively: the
    hazard **only ever ran INSIDE `if book:`**, so it modelled nothing a snapshot could already
    show — **purely additive**, never a floor.

    **Combined per-order rate `1−(1−f)² = 2f−f² = 21.96%`** against the **11.66%** target,
    versus a **ledger-measured 22.30%** — **agreement to 0.34 pp**. **1.88x at the touch**
    (not the 1.91x first bounded), **approaching 2x as f FALLS** — worst exactly where the book
    rests.

    **Blast radius, measured BEFORE any change** (`fills.csv`): **402 `post_only` fills**,
    **57.2% resting within 5bps** (independently reproduces the 57% already on record, and
    reproduced a third time at filing: 230/402), **154 of 401 positions = 38.4%** opened by a
    near-touch `post_only` leg, **20.4% within 1bps**.

    **Fix:** the **observed book is ground truth** — the hazard does not fire when a book is
    present (`order_manager.py:275, :1308`). **`passive_hazard_with_book=true` restores the
    pre-boundary simulator EXACTLY** so pre-#4 cohorts stay reproducible; `config.json:375` ships
    `false`. **`config_guard` WARNs — deliberately NOT FATAL, because a FATAL would make the old
    cohort unreproducible hence unauditable** — and the warning **carries the magnitude**
    (`core/config_guard.py:471-480`). **Expected consequence, stated in the config so it is not
    read as a regression: the paper fill rate roughly HALVES near the touch.**
    `tests/test_fill_double_count.py` — **7 tests, count verified by reading the file** (contrast
    item 40, where the message claimed 8 and collection said 7). Battery **pytest 3518+19, smoke
    219, assurance 49, overfit 3/0, quant G1-G5**.

    > **The 08-09 embargo still stands and is NOT lifted by the fix.** Propagation into the 305
    > live corpus rows and the 432-bar cohort verdict remains **DIRECTIONALLY SUPPORTED but
    > UNMEASURED**, and **may not be cited against the 432-bar hold**. Closing the *defect* does
    > not close the *propagation question* — that needs a measurement, not a commit.

    > **The corpus is ENTIRELY pre-boundary.** Last ledger row is **2026-08-10T06:50:23.746Z**,
    > before the commit stamp: **zero fills at or after `aeeaae36`.** Clean cut, no mixed
    > population — the next fill is the first honest one.

    **Residual, deliberately unfixed → NEW ITEM 61 (MP-7 queue gating is now inert).**

57b. **RECALIBRATE `passive_base_prob` UNDER THE SINGLE-PATH SIMULATOR** (sim-side;
    **opened 2026-08-10** as the surviving half of 57's *"what would close it"*).

    > **No new reason code is minted for this.** `core/codes.py:364-366` registers **XV-020,
    > XV-021, XV-022 and nothing else**; **XV-023 is declared only in a docstring**
    > (`core/fill_calibration.py:17`) and is **absent from the registry** — filed as a drift row
    > ([[synthesis/documentation-drift-register]], [[entities/reason-code-registry]]). Inventing
    > an XV-024 here would put a *third* unregistered code into circulation. This item belongs to
    > **XV-023's campaign**, and closes with it.

    Item 57's closure removed the second draw but **did not re-run `calibrate_fills.py`**.
    `sf_base` is still the value `invert_base_prob` solved so **the hazard alone** reproduces `f`
    — which was the *correct* inversion all along and is why the double-count was pure addition.
    Under the corrected simulator the hazard **only fires when no book is present**, so the
    quantity it should now reproduce is **`f` conditional on no observed cross**, not `f`.

    **Direction is known and is NOT the flattering one:** `sf_base` is currently calibrated
    against a superset event, so the residual hazard is if anything **too generous** on the
    bookless path — but that path is now rare, which is why this is a **precision** item and not a
    severity item.

    *What would close it:* re-run `calibrate_fills.py` with the residual calibrated **conditional
    on no deterministic cross** — **this is literally the 40(b) refinement folded into 40b/XV-023**
    ([[synthesis/owed-measurements]] item 40b). **One calibration campaign closes 13c, 23b, 40b and
    57b together**; do not run four.

    > ⚠️ **Sequencing:** that campaign would mint a **FIFTH** era boundary. Do not start it until
    > the 432-bar cohort reads out, or the cohort acquires a fourth internal regime cut
    > ([[comparisons/horizon-96-vs-24-bars]]).

58. **The `fills.csv` fee ledger is short by 6.24 (1.6%)** — **NOT NEW**, listed only to complete
    the docket. Already filed as [[synthesis/open-contradictions-register]] item **18** and as the
    **sequencing dependency** of item **50**. Its position here is the operator's severity
    ordering, not a second registration.

59. **THE STATUS SCHEMA AND ITS TEST FIXTURE CAN DRIFT SILENTLY — `_SYNTH_STATUS` IS NOT PINNED
    TO THE RUNNER'S STATUS WRITER** (repo-side defect. **Registered 2026-08-09**,
    [[sources/session-20260809-turing-test-hedge-verdict]] §7.)

    **`a6334162`** (the all-in P&L reporting fix, filed the same day) shipped **4 new status keys
    plus gauges** and **did not update `_SYNTH_STATUS`**, the synthetic status fixture.

    **The failure was latent by construction.** Nothing broke until a **panel referenced one of
    the new keys** — at which point `test_every_query_hits_an_emitted_metric` **failed, and failed
    CORRECTLY.**

    > **File this as a POSITIVE specimen as well as a defect.** The gate *could* fire and *did* —
    > the contrast case to [[concepts/false-green]], where the whole family is gates that could
    > not. What is missing is not the check; it is the **coupling** that would make the drift
    > impossible to introduce in the first place.

    **The class:** [[concepts/test-double-fidelity]], in its **mirror** form. The type specimen was
    a double supplying an attribute production **lacks**; this is a double **lacking** what
    production **has**. Same rule, opposite sign: *a double must track the production object in
    both directions.*

    *What would close it:* a **schema pin between the runner's status writer and
    `_SYNTH_STATUS`**, so adding a status key without updating the fixture **fails at the source**
    rather than waiting for a panel to reference it.

60. **THE FILL SIM ACCEPTED 31 DUST LEGS DOWN TO 1.17e-09 ETH — ORDERS NO VENUE WOULD TAKE**
    (sim-integrity; **sim-side**. **Registered 2026-08-09 BY THE WIKI FILING AGENT, not on the
    operator's severity docket** — [[sources/session-20260809-turing-test-hedge-verdict]] §1.4.)

    The Turing-test mechanical sweep found **8-decimal order sizes including 31 dust legs down to
    **1.17e-09 ETH**, all of which **filled** in the ledger and **carried fees**.

    **No real venue accepts an order of roughly one nanogram of ETH.** Exchange minimum order
    sizes are many orders of magnitude above it. These fills exist **only because the simulator
    accepted what no venue would** — squarely [[concepts/paper-real-boundary]].

    ⚠️ **Stated as a FLAGGED CONCERN REQUIRING VERIFICATION, not a measured fact.** The exact
    venue minimum is **not** quoted here, and the population's contribution to fees and to the
    fill-rate statistics is **unmeasured**. It may be economically trivial and still be a
    **sim-integrity** problem, which is how item 57 is framed and why this sits beside it.

    *What would close it:* quote the venue minimum order size for each affected asset; count the
    orders below it and their fees; then decide whether the fill sim should **reject** sub-minimum
    orders — and whether doing so perturbs any published fill-rate statistic.

61. **MP-7 QUEUE GATING IS NOW INERT — `queue_aware: true` PROTECTS NOTHING**
    (sim-side; **created by the item-57 fix, registered 2026-08-10**,
    [[sources/session-20260810-fill-double-count]] §4.)

    `queue_ok` is computed at `execution/order_manager.py:1302-1304` and **consumed at exactly one
    site — `:1308`, the passive-hazard branch.** Since the hazard no longer fires while a book is
    present, **MP-7 queue gating has no effect on the shipped configuration**:
    `_sim_maker_cross` fills the **FULL remaining with no depth constraint**, exactly as it always
    did. `config.json`'s `queue_aware: true` is now a **statement about a code path that does not
    execute.**

    **Pinned by `tests/test_sim_fill_queue.py:182 test_queue_gate_is_inert_on_the_default_path`**
    so the inertness stays **VISIBLE rather than implied** — and the gate's own fixture now sets
    `passive_hazard_with_book=True` (`:33`), because *a gate needs the path it gates to exist*.

    > **DELIBERATELY NOT FIXED IN THE SAME COMMIT, and the reason is the filable part.** Wiring
    > the gate onto the cross is **physically right** — a trade-through fills the queue in order —
    > but it is a **second uncalibrated change to a learning system's fill model**, and
    > compounding both in one commit would make **any later corpus change impossible to
    > attribute**. One era boundary per commit ([[concepts/lever-coupling]] applied
    > *prospectively*; [[concepts/inertness-protocol]]'s single-axis discipline).

    **A [[comparisons/dormant-vs-inert-features|dormant-vs-inert]] specimen with a twist:** the
    feature was **live and load-bearing until a correctness fix elsewhere removed its only
    consumer**. **Inertness can be CREATED BY A FIX, not only by a bug** — and the only thing
    between "inert" and "silently believed" is the test that names it
    ([[concepts/adoption-is-not-enforcement]]).

    *What would close it:* apply the depth constraint to `_sim_maker_cross` (a cross fills the
    queue in price-time order, so a resting order should receive only the residual after the depth
    ahead of it is consumed), **as a separate commit that mints its own era boundary** — or, if
    that is judged not worth a boundary, **turn `queue_aware` off in config** so the config stops
    asserting a protection that does not exist. **Do not leave it as-is**: a config key that reads
    as a live risk control and is not one is exactly the drift this register exists to prevent.

    *(2026-08-10 evening: the fix is now explicitly FENCED by the era-4 accrual moratorium —
    [[synthesis/governance-doctrine]] rule 17 — because it is a cohort-resetting change that
    mints the next [[synthesis/comparability-boundaries|comparability boundary]]. Status
    unchanged: OPEN, deliberately.)*

62. ~~**THE FILLS LEDGER HAS NO DEFENSE AT THE WRITE PATH AGAINST RESTART-REPLAY DUPLICATES.**~~
    **REGISTERED AND SHIPPED THE SAME DAY — CLOSED 2026-08-10 (`6fe6d98d`, OM-085,
    [[sources/session-20260810-stressor-epoch]] §2).** The ledger is fsync-durable PER FILL
    while order state is durable per SNAPSHOT; a kill between them restores a pre-fill order
    the sim re-executes — "duplicates correlate 1:1 with restarts," the class behind the
    16x/27x headline error, which every READER carried a dedupe against while nothing defended
    the WRITE. `append_fill` now refuses a row whose `(order_id, fill_size, fill_price,
    remaining)` already exists (`remaining` is monotone within an order, so legitimate fills
    can never collide while a replay collides exactly); refusal logs **OM-085**
    (`core/codes.py:116`, verified), never touches the trade. **Known residual, filed with the
    close:** a replay whose re-drawn partial DIFFERS is not caught — the readers' fill-pattern
    dedupe stays as the second layer. Pinned by `tests/test_fill_ledger_provenance.py` (9),
    including refusal across a simulated restart.

63. **THE RAW WEBSOCKET BOOK CAPTURE — the ONLY instrument that can measure intra-poll fill
    bias.** (**Registered 2026-08-10 evening**, [[sources/session-20260810-stressor-epoch]]
    §3; sim-side question, venue-data-side instrument.)

    Challenge hardening #1 against the era-4 gate closed as an **HONEST NEGATIVE**: the
    question "does the 5s-poll fill sim under- or over-fill relative to what happened BETWEEN
    polls" is **structurally unmeasurable from the existing recordings** —
    `get_order_book`/`get_tickers` are recorded at **5.00s median cadence**, i.e. the recorder
    sits downstream of the SAME fast poll the simulator consumes and cannot see between polls
    **by construction** ([[concepts/honest-coverage-gap]]). *What would close it:* a raw
    websocket book capture (read-only, non-cohort-resetting, moratorium-SAFE) running long
    enough to compare intra-poll crossings against poll-boundary crossings. Until it exists,
    **no claim about intra-poll fill bias in either direction is citable.**

64. **THE ESCALATION-LOSS CRASH WINDOW — a crash between month-close grading and the ladder
    ratchet loses the escalation.** (**Registered 2026-08-10 evening, DOCUMENTED AND
    DELIBERATELY UNFIXED**, [[sources/session-20260810-stressor-epoch]] §7.3; repo-side.)

    In `_close_periods`, `RP_MONTH_CLOSED` (RP-071) commits before `RP_GOAL_ESCALATED`
    (RP-072) fires — the AST-pinned ordering that makes a closed month be judged by the bar it
    ran under. A crash inside that window grades the month and **loses the ×1.5 ratchet**.
    **Known-benign, three ways:** *detectable* (audit shows RP-071 met without a following
    RP-072), *conservative* (the bar under-escalates — the stress never overstates itself),
    and *self-limiting* (next met month ratchets normally). *What would close it:* an
    idempotent escalation check on boot (if last closed month graded ≥100% at its effective
    bar and no RP-072 follows, apply the ratchet late) — or a conscious decision that the
    documented window is acceptable, recorded here. **Do not fix it silently in a money-path
    commit**; it touches goal grading, and the grading surface is how the $800 stressor is
    scored.

65. ~~**THE TRADE-PATH LEDGER SHIPPED WITH THE `paths_path` FALLBACK OPEN — a QA fixture row is
    ALREADY IN the production ledger.**~~ **CLOSED 2026-08-10 (`2602371b` — the same commit
    that lands the ledger, exactly as this item's close condition demanded).** (Registered
    2026-08-10 at the filing of [[sources/directive-20260811-grand-synthesis]], found by the
    filing's own verification; repo-side defect, sim-side ledger.)

    The new complete trade-path ledger (`ml/postmortem.py` `PATHS_COLS`,
    `outputs/trade_paths.csv` — winners included, closing the winners-censoring gap) defaults
    `paths_path` to the **hardcoded production path** (`ml/postmortem.py:195`), and **five
    existing harnesses** construct `PostmortemEngine` with redirected `summary_path`/`report_dir`
    but **no `paths_path` key**: `scripts/smoke_test.py:1013`, `tests/test_cleanup_batch1.py:33`,
    `tests/test_review_round2.py:82,93`, `tests/test_stop_gap_and_lapse_fixes.py:51`,
    `tests/test_telemetry_fixes.py:31`. **Proof on disk:** the production ledger's single row at
    filing is `2000,p1,ETH,long,0.620,0.180,nan,…` — byte-for-byte the
    `tests/test_telemetry_fixes.py` `_thesis(pid="p1")` fixture (the F1 nan-realized case).
    [[concepts/default-path-fallback-writes]] recurring **the day the writer shipped**; the new
    key is absent from every harness older than the key. **Severity is Phase-B-poisoning:** the
    Grand Synthesis parameterizes stop geometry from this exact file.

    *What would close it:* purge QA rows from `outputs/trade_paths.csv` (discriminator: fixture
    timestamps/pids — `ts=2000`, `p1`; real rows carry live epoch stamps); add `paths_path` to
    all five harnesses **in the same commit as the ledger lands**; and prefer the structural fix
    over the whack-a-mole — a QA/redirect mode that refuses to write any production default path
    when ANY path key is overridden. Battery 14 must not land green over a contaminated ledger.

    ***How it closed (`2602371b`):*** all five harnesses redirected to `tmp_path`; the
    contaminated row **QUARANTINED, not deleted** (`trade_paths.csv.quarantine_qa_1786` —
    nothing-is-ever-deleted holds even for fixture rows, so the contamination stays auditable).
    **Battery 14 did NOT land green over it** — it went **RED via the conftest
    production-outputs tripwire, the tripwire's first confirmed catch**
    ([[concepts/false-green]] contrast-case: a gate that could fire and did), making the
    contamination **caught TWICE independently** (vault-filing verification + battery).
    Battery 15 on the decontaminated tree: **ALL GREEN, `BATCH_EXIT=0` verified directly**;
    runner verified back. Full record:
    [[synthesis/grand-synthesis-algorithm-package]] §delivery.

66. ~~**THE GRAND SYNTHESIS TRIGGER — three inputs, none landed at filing.**~~
    **SATISFIED 2026-08-10 → SYNTHESIS DELIVERED.** (Registered 2026-08-10,
    [[sources/directive-20260811-grand-synthesis]]; the directive FIRES only when all three
    exist.) (1) The **academic literature sweep** — LANDED, filed with
    established/contested/folklore grades per [[concepts/evidence-grading-ladder]]:
    [[sources/sweep-20260811-academic-stops]]. (2) The **engineering-precedents sweep** —
    LANDED, adjudicated on the [[concepts/adoption-ledger]] grammar:
    [[sources/sweep-20260811-engineering-precedents]]. (3) **The battery over the uncensored
    trade-path ledger** — landed the honest way: battery 14 went **RED on the item-65
    contamination** (the conftest tripwire's first confirmed catch — exactly what "must not
    land green over a contaminated ledger" required), item 65 closed (`2602371b`), and
    **battery 15 ran ALL GREEN with `BATCH_EXIT=0` verified directly**. The deliverable is
    filed: [[synthesis/grand-synthesis-algorithm-package]] — Tier 1 (ALGO-1..4,
    moratorium-SAFE; ALGO-4 shipped `2602371b`), Tier 2 (ALGO-5..7, the geometry-epoch
    package, **PENDING operator timing adjudication** — future cut #7), five NOT-ADOPTED
    items with reasons. **What remains open is not this item**: the geometry-epoch timing
    adjudication is the operator's, and owed 52 stays parked.

    *Update, cut-#7 session ([[sources/session-20260811-cut7-geometry-epoch]]): the
    adjudication LANDED — as a **split**, not a monolithic yes. Cut #7 minted
    2026-08-11T01:33:50Z (`e7d5ca1a`); what the split deferred is now **item 67**.*

67. **THE ALGO-5 AMENDMENT — replay-parameterized stop widths + the time-decay ladder, at
    ~30 uncensored trade paths.** (**Registered at the cut-#7 session**,
    [[sources/session-20260811-cut7-geometry-epoch]] §0; sim-side data, repo-side change,
    operator-owned adjudication.)

    The CDO-review split landed only the **evidence-sufficient** Tier-2 elements at cut #7
    (ALGO-7's widen-beyond direction; ALGO-6's four pins over already-deployed machinery) and
    deferred everything whose parameters must come from data that does not yet exist: the
    **stop widths** (the band the widen-beyond nudge operates in — currently the retired
    implementation's half-step lattice with buffer/offset 5.0/5.0 bps carried over, i.e.
    direction-only) and the **time-decay ladder** (freqtrade's documented trap: aggressive
    decay tables reproduce the exact near-TP/far-SL geometry — parameters from replay, never
    taste). *What would close it:* the ALGO-4 ledger accruing to **~30 uncensored trade
    paths**; ALGO-5's counterfactual replay run over them (replay itself is moratorium-SAFE);
    and the operator's adjudication of the resulting widths/table — which is **PRE-NAMED in
    the moratorium law** (`ee7a94a2`, [[synthesis/governance-doctrine]] rule 17) as **the
    next adjudication that mints a comparability boundary**. Until then the deferred halves
    do not exist and none are authorized — and no mid-accrual read of the path ledger is a
    verdict on the landed direction ([[synthesis/comparability-boundaries]] cut #7 row).
    *(Scope note, apply-batch `66744ed1`: the audit's majors'-cost-floor-flattening finding
    — identical 1.50/2.00 sl/pt across the majors — was deliberately NOT un-flattened
    there; it is stop geometry and belongs to THIS item's adjudication,
    [[sources/session-20260811-apply-batch]] §5.)*

    ***STILL OPEN, trigger NOT fired — counter read 2026-08-15
    ([[sources/session-20260814-cohort-instruments]] Finding 3).*** The ALGO-4 ledger
    `outputs/trade_paths.csv` holds **10 rows against the ~30 the trigger names**. Recorded
    because that session first mis-read the trigger as fired at 182 and retracted it: the
    182 are `signal_history` **h432 barrier resolutions** (41 `tb_pt` + 141 `tb_sl`),
    overwhelmingly **counterfactual candidates**, not uncensored trade paths. Two measures
    whose names both reduce to "paths" are not interchangeable, and the item's trigger is
    the ledger.

    **New CONTEXT for the eventual adjudication (not a condition of it).** A triple barrier
    pays gross only if the target is hit at least `sl/(pt+sl)` of the time. On all h432 rows
    (n=259, 2026-08-14T23:38Z; n=262 thirty minutes later — live file, values as-of): median
    `pt_frac` **2.064%**, median `sl_frac` **1.548%**, payoff **1.333**, so breakeven demands
    a **42.9%** target-hit rate and the realized rate is **22.4%** — **−0.734% per
    barrier-resolved path, gross, before any cost.** Arithmetic, not a fit, and
    model-INDEPENDENT: no selector rescues a geometry that cannot pay. Caveats printed on the
    instrument's face: 77 `tb_time` paths resolve at neither barrier and are excluded, and
    119 of 123 recent rows are `candidate`, so this is the geometry's **counterfactual**
    expectancy and **not** the era-4 verdict. Now emitted every run by
    `scripts/cohort_eval.py`'s LABEL-GEOMETRY BREAKEVEN section (`61c3b5c1`, report-only).

    **Coupled to the ML-083 floor.** The same geometry cut shrank the honest corpus to 259
    rows (2.5% of 10,559), era exclusion correctly refused to pool it, that produced a **48x**
    champion-orphan ratio, and ML-083's unbounded unlock then promoted a negative-skill model
    **inside the accruing window** ([[concepts/deploy-deadlock]] §third polarity). Adjudicating
    ALGO-5 without the floor re-runs the chain at the next geometry cut; they belong on one
    docket, not two.

68. ~~**LONG-BOOK LIVE ROWS ARE MISSING POST-MIGRATION SCHEMA COLUMNS.**~~ **CLOSED
    2026-08-10 by `66744ed1` (the apply-batch — battery 19 GREEN, 3602 tests, deployed,
    runner verified).** (**Registered at the 2026-08-11 since-6am audit**,
    [[sources/session-20260811-operator-audit]] §6.4; repo-side writer defect, sim-side
    rows.)

    Live corpus rows written by the long-book path lack columns added by later schema
    migrations — the ledger-coherence audit's one OPEN anomaly. Consequence: any per-column
    analysis over the live corpus silently blanks or drops the long-book population
    ([[entities/long-book]] — this book is already the never-pool population on the fill
    axis; this puts it on the label/record axis too, the
    [[concepts/uncounted-exclusion]] shape at the schema level). The audit's other ledger
    anomalies all adjudicated: the 138s equity reset lag is BENIGN (write cadence), the
    PAXG `tb_time`/h432 live row is BY DESIGN (`label_era_of` is a pure function of the
    barrier string), and the orphan-close postmortem undercount was FIXED same-audit
    (degraded `orphan_close` rows in `ml/postmortem.py`). *What would close it:* identify
    the long-book row writer's schema source, emit the full current schema (or pad blanks
    per the `migrate_history` convention — `""` = UNKNOWN stays distinguishable from
    measured absence), and verify a fresh long-book row carries every current column;
    backfill of history is NOT owed (nothing is rewritten), only the writer.

    ***How it closed (`66744ed1`,*** [[sources/session-20260811-apply-batch]] ***§1):*** the
    diagnosis SHARPENED at the fix — not a schema-source problem but a **discarded value**:
    the long-book entry path computed `_feature_extras` and **threw it away**, so `meta`
    never carried `avail` and every long-book live row shipped **blank
    `avail_*`/`quotes_frozen`**. Fixed by threading `meta["avail"]` from the **SAME extras
    dict the features were built from** (main.py long-book entry — feature-build-instant
    semantics), pinned in `tests/test_long_book_integration.py`. Per rule 16 the closing
    disposition got its own adversarial pass: the audit's two blank ETH/BTC exhibit rows
    were **ALSO** explained by entry-time tuple shape (registered before `avail` existed) —
    both explanations true, and **the writer defect was real and current** independent of
    the legacy rows. History is NOT rewritten; pre-`66744ed1` long-book rows stay blank and
    never-pooled on the record axis ([[entities/long-book]]).

69. **THE h432 ANTI-MOMENTUM PATTERN — re-measure on clean cohorts before anyone consumes
    it.** (**Registered at the 2026-08-11 since-6am audit**,
    [[sources/session-20260811-operator-audit]] §2; sim-side label-space measurement.)

    > [!success] **CLOSED NULL 2026-10-03** — close terms met (clean cohort n=25,840, 53 days, by asset/vol/fingerprint). Gap against−with: long +1.2% [−3.1, +6.2], short +3.7% [−1.1, +9.0], both +1.6% [−3.0, +6.2] (day-block, 4,000 reps, seed 7); detector validated by scramble+plant. The August gradient does not survive; the original text below is kept per the both-sides rule. [[sources/session-20261003-owed69-remeasure]].

    The audit's data-lens refuter, failing to refute the backwards-derivative claim, found
    a symmetric ANTI-momentum pattern at h432: momentum-agreeing trades win LESS in BOTH
    direction cohorts (longs `ret_12_dir>0.5` wr 21.8% n=2620 vs 22.6% below −0.5; shorts
    17.5% n=1849 vs 21.4%). The symmetry rules out a sign bug; what it does NOT rule out is
    the two caveats it was filed with: the data is **pre-cut-boundary** (every row predates
    boundary #4 and the capital epoch — [[synthesis/comparability-boundaries]]) and
    **pooled** across regimes/assets ([[concepts/pooled-populations]], the class that has
    already manufactured one phenomenon from nothing). *What would close it:* recompute the
    same four-cell split on the post-`max(B4_TS, CAPITAL_EPOCH_TS)` cohort once n permits,
    and disaggregated by asset/regime; until then it is a lead, not an input — any consumer
    proposal must clear the era-4 accrual moratorium and
    [[synthesis/evidence-closed-register]] first, and no mid-accrual read is a verdict
    ([[synthesis/governance-doctrine]] rule 17).

    ***INSTRUMENTED 2026-08-10 (`66744ed1`,*** [[sources/session-20260811-apply-batch]]
    ***§2) — STILL OPEN.*** `defensive_cadence_report.py` **§2b** now reports the
    momentum-alignment split with the caveats built into its output: the **side-relative
    caveat prints on the report's face** ([[concepts/side-relative-features]]) and
    **lifetime-POOLED vs since-capital-epoch tables print separately** — the pooled number
    can no longer be quoted without its clean-cohort neighbor. First run (h432-only, pooled
    across cuts, **context only**): the gradient is **MONOTONE both directions** — longs
    with/flat/against **30.9%/35.3%/41.8%** (n=194/184/158), shorts
    **25.9%/37.1%/47.4%** (n=197/159/78) — **STEEPER** than the audit verifier's all-era
    pooled numbers; but the **post-epoch clean cohort (n=36 total) currently leans
    OPPOSITE** (longs-with **81.8%**, n=11). That disagreement at uninterpretable n is
    the item: the pattern **stays a LEAD** and this item stays open until the clean-cohort
    accrual is real. The close terms above are unchanged.

70. **THE 60 "CAPPED" DISPOSITIONS — pin the source.** (**Registered at the 2026-08-12
    lockout filing**, [[sources/session-20260812-weekly-anchor-lockout]] §6; sim-side
    decision-path telemetry.)

    During the 25-hour RP-041 window, 60 of the 118 entry-candidate dispositions read
    **"capped" (`can_enter=False`)** — the single largest bucket in the layered veto stack —
    and **the emitting check is not yet pinned**: unlike the SZ-coded buckets beside it
    (22 SZ-022, 21 SZ-023, 9 SZ-060, 1 SZ-050), "capped" names no registered code and no
    source line. A disposition that cannot be attributed cannot be adjudicated correct or
    wrong ([[entities/reason-code-registry]] — the registry rule exists precisely so no
    behavior hides behind a bare string). *What would close it:* identify the check that
    emits `can_enter=False` for these candidates, name its code (or register one), and
    re-read the 60 against it; note the incident record's buckets sum to 113 of 118 — the
    residual 5 belong to this diagnosis too.

71. **THE SZ-050 ANOMALY — dd 7.9% WHILE FLAT AT $800.** (**Registered at the 2026-08-12
    lockout filing**, [[sources/session-20260812-weekly-anchor-lockout]] §6; sim-side,
    single occurrence.)

    One disposition in the incident window fired SZ-050 on a drawdown reading of **7.9%
    while the book was flat at $800** — implying an MTM base of **~737 that nothing
    explains** (`equity_high_water` was reset to 800.00 at the epoch, verified at the
    reset; a flat book marks to cash). Single occurrence, not reproduced at filing.
    Suspicious in BOTH directions: a phantom drawdown throttles sizing for no reason
    (echoing this incident's own class — protective state reading a world that is not
    there), and an MTM base 63 below cash on a flat book would mean some valuation path
    still sees a position or a stale price. *What would close it:* recover the equity/HWM
    inputs SZ-050 read at that disposition, reproduce or bound the ~737, and either
    adjudicate BENIGN with the mechanism named or fix the valuation path. A WATCH item
    until it recurs or is explained — one occurrence is a lead, not a phenomenon.

72. **THE RESET-COMPLETENESS TEST — enumerate every calendar/dollar-anchored persisted
    section.** (**Registered at the 2026-08-12 lockout filing**,
    [[sources/session-20260812-weekly-anchor-lockout]] §5; repo-side, class-closing.)

    The reset-script sweep has now yielded **three members in three days** — the money
    counters (`monthly_realized_pnl`, `entry_fees_total`), the dollar-denominated perf
    window ([[sources/session-20260810-stressor-epoch]] §6), and the `risk_protocols`
    loss-budget anchors (found by **25 hours of production silence**,
    [[concepts/zero-is-not-a-reading]]). Each was fixed at discovery; nothing yet prevents
    the FOURTH member from being found the same way ([[concepts/reset-completeness]] —
    "the zero-list is a SCHEMA"; [[concepts/adoption-is-not-enforcement]]). *What would
    close it:* a completeness test that enumerates every persisted section matching the
    membership signature (*denominated in dollars of our capital* OR *anchored at a
    calendar key roll*) and asserts `reset_portfolio()` sweeps it, re-anchors it, or names
    it **deliberately preserved** (the corpus/fills/learning artifacts are preserved by
    governance rule 8, not by omission — the enumeration must distinguish *decided* from
    *forgotten*). The enumeration source should be the persistence schema itself, not a
    hand-list — a hand-list is the same class one level up.

73. **THE ML-083 UNLOCK FLOOR — bound the escape hatch.** (**Registered 2026-08-14**,
    [[sources/session-20260814-cohort-instruments]] Finding 2; repo-side change,
    **operator-owned, COHORT-RESETTING**.)

    ML-083 resolves an unfalsifiable champion badge by setting it aside and applying the bare
    cold-start bar `Brier < 0.25`. The doctrine is sound and this item does **not** propose
    removing it — the deadlock it prevents is real and documented. What is missing is a
    **floor**: the branch was built for a **3.2x** orphan ratio (4,823 vs 1,516, per its own
    comment) and fired at **48x** (10,217 vs 211), promoting a logistic whose own
    `family_brier` was **0.33105 — worse than a constant p=0.5 predictor**. The only upstream
    guard is `len(X) < 60` (`main.py:6237`). The regression then became **sticky**: post-deploy
    `trained_rows` fell to 211, the unlock stopped firing, and the next challenger — with a
    *better* OOF Brier of **0.17959** — was rejected by the like-for-like branch for having no
    shared row set, i.e. correct fail-closed logic defending a worse incumbent.
    *What would close it:* an operator-adjudicated bound — an orphan-ratio ceiling, an absolute
    minimum matrix size, or a required shadow period before the cold-start bar may apply —
    **plus** a rollback path, since `ModelRegistry.note()` supports `retired` and nothing calls
    it. **Not startable:** changing which model deploys is entry decisioning, fenced by
    [[synthesis/governance-doctrine]] rule 17. **Not independent of item 67** — the h432 cut
    shrank the honest corpus, era exclusion correctly refused to pool it, *that* produced the
    48x ratio; adjudicating ALGO-5 without this floor re-runs the chain at the next geometry
    cut. ([[concepts/deploy-deadlock]] §third polarity; repo
    `docs/quant/2026-08-14_model_promotion_migration_design.md` GAP-1/GAP-2.)

74. **THE COHORT-CONTAMINATION ADJUDICATION — does the accruing n=50 population still
    stand?** (**Registered 2026-08-14**, [[sources/session-20260814-cohort-instruments]]
    Finding 1; measurement DONE, **decision OPERATOR-OWNED**.)

    The instrument exists and prints every run (`scripts/cohort_eval.py`,
    `COHORT HOMOGENEITY`); what does not exist is the ruling. Measured on the accruing
    cohort: **4 of 13 trips carry a stale-binary leg** (`exec_era` field ABSENT — written at
    `21769fb8`, of which boundaries #3/#4 and cut #7 are all non-ancestors, so the TTL-hazard
    bug and the ~1.88x near-touch double-count were live), and **6 of 13 straddle a mid-flight
    champion deploy**, with **two distinct champions** having opened trips. A fifth trip was
    open at measurement and joins on close.
    *What would close it:* an operator ruling, on the record, choosing among — (a) the cohort
    stands as registered and contamination is noted as a known bias; (b) contaminated trips are
    excluded, shrinking an already-thin population; (c) the cohort resets and accrual restarts.
    **The tool deliberately does not choose**, and the pre-registered selection rule is
    byte-identical (pinned by `test_selection_rule_unchanged`) precisely so this decision stays
    the operator's. *Timing:* this compounds — at ~3–4 closes/day ([[concepts/probe-livelock]]
    §terminal state) every day of delay adds trips under whichever regime is current.

    ***THE THIRD AND WORST AXIS, found 2026-08-15 — the cohort is measuring the exploration
    constant, not the strategy.*** Reconstructing the cohort exactly as `era4_trips` does and
    joining to `signal_history.csv` by `position_id`: **13 of 13 joined; column `probe` = 12 ×
    `'1'`, 1 × `'0'`.** `main.py:4402` sets `p_win = max(p_win, self.explore_p_win)` for a probe
    admission, and `config.json ml.exploration.p_win` = **0.7** (bound at `main.py:948`) against a
    derived entry bar near **0.567** (`p_bar_mode: derived`, `p_bar_edge_margin` 0.0). **0.7 clears
    the bar by construction**, so for 92.3% of the accruing cohort the model's own probability was
    never the admitting quantity — it survives only as an eligibility test for the aggressive
    *size* branch. A fourth axis rides along: the cohort straddles **two label eras**
    (`exit_sim` 8, `triple_barrier_h432` 5).

    ***AND THE READOUT IS ON TRACK TO NAME THE WRONG CONSTRAINT.*** At n=13 (read
    2026-08-15T02:45Z): `gross_mean_pct` **−0.0387** (0.11 SE from zero), `gross_median_pct`
    **+0.7367**, `net_mean_pct` **−0.7209**. `NO_GROSS_EDGE` requires mean ≤ 0 **AND** median ≤ 0
    (`scripts/cohort_eval.py:309-316`); the positive median breaks the conjunction, so the gate
    resolves **`COST_BOUND`** — *"an edge exists and fees eat it."* But `scripts/breakeven_test.py`
    over **414** fully-closed positions with **every fee zeroed** gives gross mean **−0.0186%**,
    median **−0.0295%**: the book loses with no fees at all. `COST_BOUND` would be the wrong
    verdict, and per the registration it **cannot be repaired after n=50 without re-registering**.
    *What would close it:* an operator ruling on whether a 12/13-probe, two-label-era population
    can serve the pre-registered verdict — taken BEFORE the readout, since the registration is the
    law and a post-hoc reinterpretation is exactly what pre-registration exists to prevent.
    ([[sources/session-20260814-cohort-instruments]]; war-room run `wf_59ca8ba8-61a`)

75. **THE 25 CONFIRMED DEFECTS FROM THE 2026-08-15 SCANS — 9 SAFE unshipped, 10
    SHIP-BLOCKED, 6 shipped.** (**Registered 2026-08-15**,
    [[sources/session-20260815-scans-and-corrections]] §3; mixed classes.)

    Two adversarially-verified scans produced **25 confirmed** findings from **739**
    candidates (232→15, then 507→10). Six SAFE ones shipped in `523fde68`; the rest are
    queued here so they are not rediscovered at 180k tokens apiece.

    **SAFE, unshipped** — no adjudication needed, none alters which orders are placed:
    `gate_efficacy_report.py:115` deflate `(k,n)` before `wilson()`; `:105` add an era
    filter and refuse to pool disjoint era mixes; `thales_report.py:84` filter the money
    join to `source == "live"` (it currently pools 10,325 never-traded candidates with 327
    live and calls the total "10652 labeled trades"); `build_trading_dashboard.py:1234`
    repoint the exposure panels at `liquiditybot_rp_heat_frac` (the plotted series excludes
    hedges while the cap is enforced hedge-inclusive, so the gauge can read "room left"
    while headroom is 0.0 and every entry is `RP_HEAT_FULL`); `runner.py:996` publish
    `heat_headroom_frac` and `heat_corr`; `cost_truth_report.py:205` split the opening
    bucket so hedge legs verdict against taker; and the three unfireable tests on
    [[concepts/false-green]].

    **SHIP-BLOCKED** — each names its fence: `ml/calibration.py:87` (`my[-1] = yv` keeps the
    MAXIMUM pooled value at tied raw p instead of the weight-pooled mean; the deployed
    artifact's top knot is that artefact at `x=0.9999999999999065 → y=0.98`, and `np.interp`
    clamps every high-confidence p to it — moves `p_win` → Kelly sizing AND is model-side
    under the freeze); `risk/leverage.py:75` (the read-FAILURE sentinel 0.0 from
    `kraken_feed.py:363-370` is treated as healthy, bypassing the 150% block, the 200%
    ladder and the 1x cap — and 0.0 is ALSO the legitimate no-margin-positions value, so
    inverting the test is not the fix); `execution/hedging.py:221`; `core/watchdog.py:140`;
    `ml/history.py:1310,1351`; `main.py:1993`, `:4870-4875`; `execution/algos.py:263`.

    *What would close it:* each SAFE row landing with a test; each SHIP-BLOCKED row either
    adjudicated or explicitly deferred with a reason. **Do not re-scan for these** — they are
    confirmed, located, and reproduced.

76. **`gate_efficacy_report` INTERVALS ARE ~8x TOO NARROW — deflate before you flag.**
    (**Registered 2026-08-15**, [[sources/session-20260815-scans-and-corrections]] §2;
    report-side, SAFE.)

    Whole corpus: **n = 10,567 spans, effective n = 162.2, mean uniqueness = 0.0154, SE
    inflation ×8.07**. Every Wilson interval in the ~29-row per-rule table is computed at
    nominal n, so the report is not currently measuring gate selectivity at all — the
    resolution is absent, not merely wrong. Registered separately from item 75 because it
    invalidates *outputs already in circulation* rather than being a latent defect: see the
    contradiction register entry for the two retired figures.
    *What would close it:* effective-n deflation at `:115` and `:188-195`, per-era rows, and
    both nominal and effective n printed in the table — after which the separation question
    can be asked honestly for the first time.

77. **IS THE ISOLATED BACKUP ACTUALLY FROZEN?** (**Registered 2026-08-16**,
    [[sources/session-20260811-16-vscode-3b307393]] §4; host-side, SAFE.)

    `C:\Users\haird\Documents\liquiditybot_isolated_2026-08-11` was taken copy-not-move on
    2026-08-11 (**robocopy 2593/2593, 0 failed**; bundle verifies *"records a complete
    history"*). At the 2026-08-16 filing its `liquiditybot_ab` subdirectory carries an
    **mtime of 2026-08-16 11:36** — five days after the copy. Directory mtime alone does
    **not** establish a content change, so this is an open question, not a finding.
    *What would close it:* a hash manifest of the isolated tree compared against the
    2026-08-11 `robocopy_repo.log` inventory (or `git -C <copy> status` plus a
    `git bundle verify` re-run), and — whichever way it reads — a written statement of
    whether the copy is a restore point or merely an archive. **An isolation copy that is
    not provably frozen is not a restore point.**

78. **`CUT7_TS` IS 400 SECONDS EARLY, AND ITS COMMENT CERTIFIES THE ERROR.** (**Registered
    2026-08-16**, [[sources/session-20260816-catchup-08-12-to-08-16]]; measurement-tool only,
    **moratorium-SAFE** — it changes no order and no fill.)

    `scripts/defensive_cadence_report.py:39` reads
    `CUT7_TS = 1786411630.0  # 2026-08-11T01:33:50Z (deploy less 800ms is fine at row granularity)`.

    | quantity | value | route |
    |---|---|---|
    | `1786411630.0` actually is | **2026-08-11T01:27:10Z** | `datetime.fromtimestamp(ts, utc)` |
    | correct value for `01:33:50Z` | **`1786412030.0`** | `datetime(2026,8,11,1,33,50,utc).timestamp()` |
    | error | **400.0 s = 6m40s early** | difference of the two |
    | `e7d5ca1a` commit instant | `01:33:28Z` = `1786412008.0` | `git log -1 --format=%cI` |

    So the constant is **not** the deploy instant **and not** the commit instant, and the
    comment's "800 ms" understates the gap by **500x**. **Every geometry-side statistic that
    report cuts at `CUT7_TS` is cut 6m40s early.** Introduced **pre-gap by `d3779c8e`** and
    **untouched by all 33 commits in `8cb56a82..c4272391`**. Line 38's
    `CAPITAL_EPOCH_TS = 1786403127.0` = **2026-08-10T23:05:27Z** is **CORRECT** — one line, not a
    pattern. *What would close it:* change the constant to `1786412030.0`, delete the false
    explanation, and **re-run §2b** — the 08-11 anti-momentum split (item 69) was measured through
    this cut. **Do not assume the numbers are unchanged; measure them.**
    ([[synthesis/documentation-drift-register]] §the 2026-08-16 catch-up additions.)

79. **A PRE-REGISTRATION STATES A FACT THAT DOES NOT RE-DERIVE.** (**Registered 2026-08-16**;
    **no effect on the cohort**, which is why it is registered rather than fixed under pressure.)

    `scripts/cohort_eval.py`'s capital-epoch amendment (≈`:114-122`) states that **"the 3 closes
    accrued between them were $5000-regime trades"**. Double-derivation of the closes between the
    two epochs finds **SIX**, not three. A **benign reading exists and is probably right**: the
    author counted only the **3 pre-flatten** closes and treated the three closes landing at the
    **identical instant** (34 s before the declared epoch) as the reset flat-out, which is a
    defensible modelling choice — but it is **not what the sentence says**.

    **Why it is registered at all:** this is a **pre-registration**. Its whole authority is that it
    was written before the outcome and can be checked afterwards; a stated fact inside it that does
    not re-derive is a crack in exactly the artifact whose value is being unimpeachable
    ([[synthesis/governance-doctrine]] rule 17). *What would close it:* restate the sentence to say
    what was actually counted and why, in the file, without touching the cut.

80. **THE RED-TEAM PANEL IS NOT MANDATED — the anti-agreement mechanism binds nothing.**
    (**Registered 2026-08-16**; this one is a **LAW change, not a tooling change**, and therefore
    OPERATOR-owned.)

    `.claude/workflows/red-team-panel.js` exists, works, and has a measured track record: its
    first run put **26 agents / 5 mandated-position lenses** against a commit **its own author had
    already declared clean** and produced **35 objections, 4 withdrawn, 16 surviving**; five gap
    commits trace to it. It is the built response to
    [[concepts/location-not-magnitude]]'s finding that **agreement is the cheap default**.

    **And nothing requires anyone to run it.** Its own README says so: *"The workflow cannot make
    you answer it — that part is discipline."* A mechanism whose activation depends on the
    good intentions of the party it is meant to check is
    [[concepts/adoption-is-not-enforcement]] in its purest form — *"we use it" and "it cannot be
    skipped" are different claims, and the gap between them is where the defect class survives.*

    *What would close it:* a decision, by the operator, on whether the panel becomes **binding
    text in `CLAUDE.md`** (with a named trigger — e.g. any commit touching the decision path, any
    docket disposition, any retraction) or stays an available tool. **Filing it as a tool is the
    flattering disposition and should not be adopted by default**
    ([[concepts/self-flattery-gradient]]).

81. **THE ERA-4 READOUT NEEDS A RECORDED BINARY SHA, AND `max_concurrent_positions` IS
    EPOCH-MINTING.** (**Registered 2026-08-16**; both OPERATOR-owned.)

    (a) **The readout's provenance.** The live tree sat at `21769fb8` (2026-08-07) until the
    2026-08-12 fast-forward, and **boundaries #3/#4 and cut #7 are not ancestors of it**; the
    deploy branch is `claude/remote-control-e3h815`, not `main`. **Any readout without a recorded
    running-binary sha is unverifiable after the fact.** Full rule:
    [[synthesis/comparability-boundaries]] §the readout needs a BINARY sha.

    (b) **`max_concurrent_positions` (5, `config.json`) sets the accrual rate AND the uniqueness**
    of overlapping trips — hence `n_eff`, hence the gate's own resolution floor. Changing it does
    not merely change how fast rows arrive; it changes **what the pre-registered n=50 is worth**.
    Declared **epoch-minting until adjudicated**.

82. **THE GATE'S OWN RESOLUTION FLOOR SITS ABOVE THE EFFECT IT IS REGISTERED TO DETECT, AND THE
    SIGNATURE LINE DOES NOT NAME ITS CONVENTION.** (**Registered 2026-08-16**; **decision-grade**,
    OPERATOR-owned. Nothing here proposes changing the registration —
    [[concepts/never-widen-a-gate]].)

    At the pre-registered **n=50**, on **today's measured** per-trade sd (**2.559128%** against the
    **~0.5%** the n=50 registration assumed — a **5.1x** miss) and mean uniqueness **0.328103**:

    | quantity | value |
    |---|---:|
    | `n_eff` at n=50 | **16.4052** |
    | SE | **0.631832%** |
    | resolvable floor at **2·SE** | **1.263665%** |
    | resolvable floor at **80% power, two-sided 5%** (multiplier `z₀.₉₇₅+z₀.₈₀` = **2.801585218112968**) | **1.7701322903683439%** |
    | observed gross mean / trade | **+0.657656%** |
    | ⇒ 2·SE floor ÷ observed | **1.92x** |
    | ⇒ 80%-power floor ÷ observed | **2.6915765067072113x** |

    *(Every row re-derived by RUNNING `scripts/cohort_eval.py` at 2026-08-16T21:01:13Z, not quoted
    from the source document; all six reproduce. The sd itself is double-derived — the tool
    reports a NOMINAL-n `gross_se_pct` 0.6397819799488953, so `sd = gross_se_pct × √16`. That the
    shipped instrument's default SE is the **nominal** one, optimistic by exactly the reported
    1.7458 inflation factor, is part of the finding.)*

    **The gate will fire on a quantity 1.92x BELOW ITS OWN NOISE — and the finding is
    UNDERSTATED, not overstated.** The 2·SE form is a **2-sigma detection threshold**, not a
    **power-calibrated MDE**; at 80% power the honest floor is **2.69x** the observed mean. The two
    conventions **differ by 40.1%** and the source document **never names which one it is using**,
    while its signature section commits the operator to the resulting numbers. *What would close
    it:* name the convention **in the document, above the signature line**, and state plainly that
    at n=50 the registered CONTINUE branch is a **trigger, not a measurement** — which the document
    already says at §3 and which the signature line does not carry.

    **82(b) — A SECOND, INDEPENDENT OPTIMISM IN THE SAME NUMBER, found 2026-08-16 by the
    correction pass while double-deriving the sd.** Distinct from the nominal-vs-effective-n
    issue above: `cohort_eval.py`'s `gross_se_pct` is computed with a **POPULATION
    (n-denominator) standard deviation**, not the unbiased sample one. Pinned without reading
    further code — `0.6397819799488953 × √16 = 2.5591279197955812` is **exactly**
    `statistics.pstdev`, while `statistics.stdev` gives **2.6430559504487245**.

    | estimator | sd (gross) | SE at n=16 | SE at n=50 (`n_eff` 16.405) | 2·SE floor at n=50 |
    |---|---:|---:|---:|---:|
    | **population — as shipped** | 2.559127919795581% | **0.6397819799488953%** | **0.6318323922199418%** | **1.2636647844398836%** |
    | sample / unbiased | 2.6430559504487245% | 0.6607639876121811% | 0.6525536887099274% | **1.3051073774198547%** |
    | bias | **+3.2795558988644613%** | | | **floor understated by 3.28%** |

    **The direction is FLATTERING** — a smaller SE makes the floor look nearer and the effect
    look more resolvable than it is ([[concepts/self-flattery-gradient]]). It **strengthens**
    item 82 rather than softening it: the 2·SE ratio moves **1.9215x → 1.9845x**, and the
    80%-power ratio **2.6920x → 2.7783x**. Magnitude is small (3.28% at n=16, ~1% by n=50) and
    that is why it is a sub-item.

    > **DO NOT "FIX" THIS BY PATCHING THE ESTIMATOR MID-ACCRUAL.** The era-4 registration is a
    > **measurement standard, not a tunable** (`CLAUDE.md`, and `gate_truth_report`'s own
    > docstring). Changing an estimator between registration and readout is the shape
    > [[concepts/never-widen-a-gate]] forbids — in the tightening direction, which the doctrine
    > also does not authorize. *What would close it:* **name it in the readout** — state which
    > sd convention the reported SE uses, alongside item 82's unnamed detection convention.
    > Both are the same defect class: **a signature line committing an operator to numbers whose
    > statistical definition the document never states.**

83. **TWO [MEASURED] TAGS DISAGREE ON THE SAME READ AND NOBODY RE-RAN IT.** (**Registered
    2026-08-16**; small, and registered *because* it is small. **NARROWED the same day** — see
    the amendment.)

    For the **same `cohort_eval` read at 2026-08-15T22:06:48Z**, the boardroom brief records
    **−0.4981%** and the readout decision table records **−0.4975%** — **both tagged
    `[MEASURED]`**. One of them is a transcription, and the tag does not distinguish. *What would
    close it:* re-run and correct the loser; **or**, better, make `[MEASURED]` mean *"emitted by
    the tool in this run"* and introduce a separate tag for *"quoted from another document"*.
    A provenance tag that survives a copy is not a provenance tag
    ([[concepts/no-orphan-claims]]).

    > **⚠️ AMENDED 2026-08-16 (correction pass) — the item was registered under a WRONG METRIC
    > IDENTITY, and the corrected version is narrower and more interesting.**
    >
    > **(i) These are NOT era-4 net mean.** Both figures are
    > **`geometry_breakeven.expectancy_pct`** — gross, model-independent triple-barrier
    > arithmetic over `triple_barrier_h432` — read at
    > `docs/quant/2026-08-16_boardroom_brief_money_path.md:50-52` and
    > `docs/quant/2026-08-16_era4_readout_decision_table.md:191-195`. The original registration
    > implied era-4 `net_mean_pct`, which is a different statistic from a different file.
    >
    > **(ii) "Cannot be settled by re-running" was right for the WRONG REASON.** Not because
    > *the cohort* moved — because **the metric's own corpus moves continuously**.
    > `geometry_breakeven()` reads **`outputs/signal_history.csv`**
    > (`scripts/cohort_eval.py:390`, called at `:648`), **not** `fills.csv`. That file was
    > observed at **8,395,113 bytes, mtime 2026-08-16T21:16:29Z**, growing **between two reads
    > 34 seconds apart**. Three reads of the same metric:
    >
    > | read | rows | `expectancy_pct` |
    > |---|---:|---:|
    > | decision table `:192` (stamped 2026-08-15T22:06:48Z) | 371 | −0.4975% |
    > | verification agent, 2026-08-16T20:43-20:48Z | 435 | −0.504757740585774% |
    > | correction pass, 2026-08-16T21:15:55Z | 446 | −0.5385178137651823% |
    >
    > **(iii) A MECHANISM for the disagreement, `[I]` inferred — not a closure.** Two
    > invocations minutes apart, under one **copied** stamp, can legitimately differ with
    > neither being a transcription error. This does not prove that is what happened; it makes
    > the tag lesson **stronger**, because a copied stamp does not merely lose provenance — it
    > **asserts a shared read that never occurred**.
    >
    > **(iv) Era-4's actual `net_mean_pct` is −0.030137595811143666%** `[K]`, double-derived
    > 2026-08-16T21:15:55Z and 21:17:03Z. It has **no prior published comparison point** in
    > either document — **`[UNKNOWN]`**. Sanity check: today's 16 trips restricted to their
    > first 14 by close time give **−0.04333925281724908%**, matching neither −0.4981 nor
    > −0.4975 under any slice — corroborating the metric mismatch.
    >
    > **STILL OPEN, narrower:** *why the two documents differ from each other* is
    > **unexplained**. *What would now close it:* an **archived 2026-08-15 `--json` output**
    > (the verification agent could not locate one). **New standing rule:** never quote
    > `expectancy_pct` without its **read stamp and row count** — it is a snapshot of a
    > growing corpus, not a constant.

84. **ZOMBIE SLOT SQUATTING — a dead feed holds candidate slots forever.** (**Registered
    2026-08-16**, fee-wedge/capacity session; Tier 2 — blocks the full value of the d10c1a91
    capacity lift.) [K] `state.json $.candidates` read 2026-08-16T22:37:04Z: **32 of 187**
    pending slots held by candidates older than 38h whose entry bar has left a stale bars
    cache (DOT 17 slots, cache stale **156.0h**; SOL 6, 35.1h; ETH 7, BTC 2). The drop
    condition requires the bar window to slide, which requires NEW bars — so a dead feed
    squats its slots indefinitely. *What would close it:* an age-based eviction independent
    of bar arrival, or a staleness-triggered drop; measure recurrence after the capacity
    lift lands (source: `raw/quant/2026-08-16_fee_wedge_feasibility.md` companion, fix-agent
    report, worktree commit d10c1a91).

85. **restore() NEVER TRUNCATES TO A SHRUNK CAP.** (**Registered 2026-08-16**; Tier 4 —
    trigger: any future `max_open_candidates` DECREASE.) [I] from code read: restore keeps
    every persisted candidate and eviction only holds pool size constant, so a cap lowered
    in config is not enforced against an already-larger restored pool. Not triggered by
    d10c1a91 (cap grew). Verify by planting a shrink before relying on one.

86. **DOT/SOL BARS-CACHE STALENESS — a data-layer incident independent of labeling.**
    (**Registered 2026-08-16**; Tier 2.) [K] as-of 22:37:04Z: DOT bars **156.0h** stale,
    SOL **35.1h**. Whatever killed those feeds predates the capacity work and is unowned.
    *What would close it:* feed-staleness root-cause on the runner (THALES TH-014 exists
    for shading, not for repair), plus an alert when any asset's bars age exceeds N×cycle.

87. **THE RP-070 WEEKLY REALIZED LEDGER RECONCILES WITH NEITHER BOOK AT WEEKLY GRAIN.**
    (**Registered 2026-08-16**; Tier 3 — instruments exist, reconciliation does not.) [K]
    W30 −17.35 / W31 −14.88 / W32 −173.33, realized_total −208.31 @ 2026-08-10T00:00Z vs
    fills-derived W32 entry −8.97 + hedge −325.70. Named confounds, none quantified:
    `main.py:1671` excludes hedges from the perf ledger (`if not pos.is_hedge`), RP-041
    sweep false-loss, tier-partial timing. Trip-level claims are unaffected (per-pid PT-061
    agreement, zero disagreements over 216 covered trips) — the WEEKLY grain is what has
    never been reconciled. *What would close it:* one script that rebuilds RP-070's weekly
    numbers from fills.csv + the named exclusions and reports the residual.

    **RESOLVED same session (2026-08-16/17, `scripts/reconcile_weekly.py`, worktree
    commits 7dc5cfbe+63a830ba) — and the registration's confound #1 was WRONG.** Read
    from code, not assumed: RP-070 accrues per EXIT leg, **HEDGE-INCLUSIVE**,
    exit-fee-net — `main.py`'s `if not pos.is_hedge` guards only the rolling *perf*
    ledger, so the hedge-exclusion confound never applied to RP-070 at all. The
    "mismatch" was a **unit difference**: the fills-derived book is full-net cash-flow
    trade-grain and carries the OPENING-leg fee stack (W32: 3.64 entry + 157.84 hedge
    = $161.48, the churn week) that no weekly row ever sees. Waterfall (live run
    2026-08-17T00:15:31Z): W31 residual 0.00, W32 **0.00 at s0**, W33 0.00 once the
    documented capital epoch is passed as `--sweep` (chain check independently flagged
    the +208.31 rebase). **Sole residue: W30 +$0.41** (ledger less negative than
    fills; candidates: kill-lost in-memory accrual, or an OM-085-refused replay row) —
    that narrow question stays open; the reconciliation itself is CLOSED. Tier-partial
    timing contributed 0.00 in every closed week. 5 mutations each turned the tool's
    suite red.

88. **THE FEE-CONSTANT CORRECTION IS A PRE-NAMED COHORT-RESETTING ADJUDICATION, NOW
    FULLY EVIDENCED AND WAITING ON THE OPERATOR.** (**Registered 2026-08-16**;
    **decision-grade**, OPERATOR-owned — nothing here proposes shipping it.) The shipped
    25/40 bps constants (`config.json:356-357` via `execution/order_manager.py:511-512`)
    are **half the venue's true Tier-1 40/80** ([[concepts/cost-truth]]; re-confirmed by
    fresh fetch 2026-08-16 AND by 708-leg enumeration showing the booked schedule is the
    config restated). Correcting them is FEE BOOKING — cohort-resetting under the era-4
    moratorium. The feasibility consequence is already decided without it (the wedge binds
    at every tier, `raw/quant/2026-08-16_fee_wedge_feasibility.md`); what the adjudication
    changes is whether the SIM's future cohorts pay honest fees.

    **ADJUDICATED 2026-08-16 (operator, same session): BATCH AT READOUT.** The 40/80
    correction lands together with the pre-named ALGO-5 amendment as ONE adjudicated
    execution-era boundary (#5) when the era-4 gate reads out — not before. Cohort
    accrual (17/50 at adjudication) continues undisturbed. Scheduled, not open; kept
    in the docket so the readout session finds the commitment.

89. **PER-ASSET BARS-AGE TELEMETRY — the one owed metric the sidecar batch could
    not ship.** (**Registered 2026-08-17**; Tier 2 — blocks the FW-081 board
    gauge.) Needs an engine watchdog/status block carrying per-asset bar-cache
    ages (`watchdog.stale_assets` is names-only); engine change = schema tests +
    one restart. Every other owed metric from the board build SHIPPED in
    360b9cc9 (loaded_rows, dry_run, orphan_ratio, cohort_closes/min_n,
    lineage_events) and was PANELED in bbdf8c06.

90. **THE DEAD-MAN'S DELIVERY PATH — routing fix + injection test.**
    (**Registered 2026-08-17**; **decision-grade**, OPERATOR-owned one-click.)
    [K] lb-telemetry-stale detected every stack death (6 firings through the
    08-16 teardown) and every firing was swallowed: notification root routes
    to receiver "empty" (zero integrations). Fix = route both live rules to
    grafana-default-email (30 seconds in the UI, or scratchpad
    gf_fix_routing.py — classifier-blocked for sessions in both contexts).
    THEN the injection test: pusher dead ≥12 min → email lands → restart.
    Repo mirror committed c2beb068. Until routed, every wake-the-operator
    condition that depends on total-local-death detection is decorative.

91. **RENDERER CLAIMS PINNED BY PRECEDENT, NOT THIS INSTANCE.** (**Registered
    2026-08-17**; Tier 4 — trigger: first live view of the new panels.) The
    bargauge shared-auto-max scaling (era-4 two-bar) and stat noValue text
    rendering on the new tiles rest on Grafana display-processor behavior;
    one screenshot of each settles both. The ZERO_BAD base-color claim from
    the hostile review carries the same status.

92. **DELISTED-PAIR BATCH DEGRADATION** (**Registered 2026-08-18**, window-arc
    review F2; Tier 4 — trigger: any Kraken pair delisting while a rotated-out
    position holds it). [K, experiment vs live Kraken]: one unknown pair in the
    widened batched Ticker request kills the WHOLE batch (`EQuery:Unknown asset
    pair`, empty result) → per-pair backstop → ~16 sequential throttled calls
    per fast cycle, ~5s added to stop-evaluation cadence for ALL positions,
    permanently, marks still correct. Hardening: drop the offending pair from
    the union with a latched warn, or pre-validate offuni pairs against
    AssetPairs at boot. main.py:2668 region.

93. **poll() LINEAR SCANS AT THE NEW CEILING** (**Registered 2026-08-18**,
    review F5; Tier 5 — perf note, no owner). `bar_time in b["t"]` + `.index()`
    are O(bars) per candidate: at 1200 × ~2160 bars ≈ 5M comparisons per slow
    cycle (est. tens-of-ms). Acceptable at 30s cadence; a per-asset {ts: idx}
    map beside the array cache erases it if the pool ever runs at cap. Also
    unmeasured (review's own blind spot): state.json snapshot size at a full
    1200 pool.

94. **THE VETO STAMP AND THE VETO FEATURE DISAGREE ON THE SAME ROW.** (**Registered
    2026-08-21**, manip-gate efficacy audit; Tier 2 — blocks every efficacy claim
    about the gate.) [K, snapshot `signal_history.csv` md5
    `a6b83a65e0a037bdc4ad740ae49f1a77`, 14,170 rows, ts .. 2026-08-21T22:42:22Z]:
    `disp == SZ-045` and `manip_suspect >= 0.9` are supposed to name the same
    event and do not — **both 277 · disp-only 104 · feature-only 218 · Jaccard
    0.462**, and **116/454 = 25.6% of stamped rows record a manip_suspect BELOW
    the threshold they were refused by** (disp-only median 0.858, max 0.900). The
    entire measured "effect" of the gate rides on the stamp (+17.71 pp, z=+1.60)
    and is absent from the score (+4.75 pp, z=+0.46), so **which quantity the
    gate actually read is unknown**. Candidate mechanism [I]: the stamp is written
    from `self._manip_scores[asset]` at entry time (`main.py:4688`) while the row's
    feature column is built elsewhere in the cycle — a timing skew, not a
    disagreement about the book. **Closes when** the two are reconciled at write
    time (log the gate's own input on the row) or the skew is measured and the
    corpus re-read through it. Until then no efficacy statement about SZ-045 may
    be made from `signal_history`, in either direction.

95. **A DISCRIMINATING FEATURE FOR THE SPOOF DETECTOR.** (**Registered
    2026-08-21**; **BOUNDARY class — readout docket, operator-owned**.) [K,
    injection into the shipped `LiquidityRegimeEngine` at HEAD `dae58cf6`]:
    honest maker repricing in a +15 bps/30 s melt-up and true layering both score
    **spoof 0.949, 79 events, label `spoofy`** at matched 30 s cadence; the
    detector is directional (fires on whichever side chases the trend), evadable
    (repost ≥120 s → 0.000 against a 0.90 bar), and blind outside `track_levels
    = 15`. The observable does not separate the hypotheses, so **no threshold
    repairs it** ([[concepts/observational-equivalence]]). Candidates: trade-tape
    confirmation (a consumed level is already scored 0.000 correctly) or level
    lifetime conditioned on mid direction. **Adding one changes which orders are
    placed → cohort-resetting**; it belongs in the same batch as ALGO-5, SWEEP-0/1
    and the fee-constant correction, never mid-era.

96. **PRODUCTION FREQUENCY OF THE TREND-SHAPED FALSE POSITIVE.** (**Registered
    2026-08-21**; Tier 2 — SAFE, measurement only.) The injection establishes a
    **capability**, not a rate: synthetic book, one large level, regular polls,
    one asset. Owed: count `SZ-045` refusals and `spoofy` cycles inside the
    **2026-08-20 melt-up window** against a matched calm window, per asset. This
    is the measurement that decides whether item 95 is urgent or academic, and it
    is the same window ATTR-1 already needs. Consistent-with evidence today:
    **95.8% of the era's veto band (229/239) sits on MINA+FLOW**, the two
    widest-spread assets on the book.

### Items 97-100 — the cost-stack investigation and the rule-21 backlog (registered 2026-08-21)

97. **CLOSE THE COST-STACK INVESTIGATION.** (**Registered 2026-08-21**; Tier 1 —
    it reframes [[synthesis/the-money-path-thesis]] and is the settle-condition
    of a PROVISIONAL page.) The reported `scripts/cost_attribution.py` run over
    **434 closed positions** — mean **gross +0.0733% POSITIVE**, configured-stack
    fee cost **0.717%**, net **−0.6440%** — is single-route, uncut against
    [[synthesis/comparability-boundaries]] (434 ≫ era-4's 33, so certainly
    pooled), carries **no effective n**, has **no snapshot stamp**, and has had
    **no refuter run**. Closing it needs all four: population cut STATED,
    `n_eff` reported instead of 434, the gross **double-derived** by the
    full-book fills reconstruction, and refuters **R1-R5** run (R1 pooling
    artifact first; **R3 hedge legs has a named historical mechanism** —
    `breakeven_test.py` flipped its own median gross −0.0303% → **+0.0505%** by
    discarding 159 hedge round trips, *the same sign as this reframe*). Until
    then it is a **LEAD, not evidence**:
    [[sources/session-20260821-cost-stack-in-flight]] (PROVISIONAL), and
    [[synthesis/live-readiness-verdict]] is PROVISIONAL because of it.
    **CLOSED 2026-08-26 BY ROUTE SUBSTITUTION**
    ([[sources/session-20260826-why-losing-deep-dive]]): the question this
    item exists to answer — is gross really positive and really eaten by
    costs? — read out on the **decision-grade population instead**: the
    pre-registered era-4 cohort at n=54 (population cut stated by
    registration, uniformly post-cut-#7; effective n **21.5** reported;
    probe-tuition surviving ×1.58 concurrency deflation p≈0.027 at true
    fees; hedge legs excluded **by the registration**, not by accident, which
    retires R3's mechanism for this population). Verdict: **COST_BOUND**.
    The 434-pool figures themselves are **moot as evidence** and were never
    verified — the 08-21 page stays PROVISIONAL for those figures only.
    What survives of this item lives in **98** (struck constants) and **99**
    (execution-mix residuals), both untouched by the deep dive.

98. **THE STRUCK 16/26 SCHEDULE IS STILL HARD-CODED IN A LIVE COST INSTRUMENT.**
    (**Registered 2026-08-21**; Tier 2 — **SAFE**, alters no order and no fill.)
    `scripts/cost_attribution.py:76-77` sets `KRAKEN_MAKER_BPS = 16.0` /
    `KRAKEN_TAKER_BPS = 26.0` — the schedule this corpus **struck on 2026-08-07**
    (true Tier-1 is **40/80**, [[concepts/cost-truth]]) — and builds its two
    counterfactual comparison rows from them at `:201-204` (0.52% and 0.32%
    round trip, both **below** the true 1.20%), so every "what would this have
    cost at Kraken's own rates" figure is computed against a **schedule that
    does not exist**, in the **flattering** direction. Worse, `:74-75` asserts
    *"lower tiers only reduce these, so using base is the conservative check"* —
    a safety property that is **INVERTED** if Tier-1 is 40/80. **Third recorded
    recurrence** of this propagation ([[synthesis/documentation-drift-register]]);
    the first two were `config.json`'s rationale and a 7-agent audit quoting it.
    Owed: correct or quarantine the constants, fix the inverted comment, re-emit
    or delete the counterfactual table. Note the direction: at 40/80 the wedge is
    **~16x** the gross edge, not ~10x — **the correction makes item 97 worse.**

99. **TWO UNEXPLAINED EXECUTION-MIX RESIDUALS.** (**Registered 2026-08-21**;
    Tier 3.) (a) The implied fee cost **0.7173%** exceeds even a 60%-taker
    two-leg model of the configured stack (`2 × (0.6×40 + 0.4×25)/100 = 0.68%`)
    by **≈3.7 bps** — mechanism **not established** (exit-leg spread, multi-leg
    escalation exits, partials, or hedge legs inside the trips). (b) A **60%
    taker share is above the structural ceiling**: repo `CLAUDE.md` invariant 5
    makes entries limit-only, so a 1-entry/1-exit trip **cannot exceed 50%**
    taker. So either entries are booking taker rates, or trips carry more than
    two legs, or the population is not one-entry-one-exit (`_OPEN_PURPOSES =
    ("entry", "hedge")`, `:72`). The same tool's 2026-08-02 docstring records
    **41.87%** (`n=397` post_only=1 @ 25.0 bps, `n=286` post_only=0 @ 40.0 bps) —
    *below* the ceiling — so a real 60% is a **+18pp drift in execution mix** and
    a finding in its own right, with fill-axis consequences.

100. **DECLARE A STATUS ON THE 203 UNDECLARED PAGES — PAGE BY PAGE.**
     (**Registered 2026-08-21**; Tier — structural/hygiene, no deadline.)
     Governance rule 21 landed with **9 declared / 203 undeclared** of 212 claim
     pages (7 SETTLED, 2 PROVISIONAL, 0 SUPERSEDED, 0 lint errors) — double-derived,
     the linter's JSON counts agreeing with a `grep -rl '^status: '` of `wiki/`. **This is not a backlog to be cleared in one pass.** Bulk-stamping
     204 pages SETTLED without re-establishing that their refuters ran would be a
     203-page orphan claim filed in the name of the rule against orphan claims
     ([[concepts/claim-status-discipline]] §Scope). **UNDECLARED is an honest
     third reading** — *no session has asserted a status here*. The task is:
     **every page declares its status at the moment it is next touched for any
     reason**, and a session that establishes a page is stale marks it
     SUPERSEDED with its supersedor rather than editing it quietly. Progress is
     read from `lint_claim_status.py --vault .`; a full-enforcement run is
     `--require-all`.

---

**EXTENDED TO 52-103 at the 2026-08-26 why-losing readout filing**
([[sources/session-20260826-why-losing-deep-dive]] — the era-4 gate crossed
n=50 and read **COST_BOUND** at 54 closes). **Item 88 status:** the fee-truth
correction is now **STAGED as boundary #5** (`scripts/boundary5_stage.py
--apply`, commit `ca55e2ba` 2026-08-25, INERT — `p_win 0.85`, derived entry
bar 0.8335), and the readout it was batched to has **arrived**; the apply is
the operator's. New items:

101. **PRE-REGISTER THE MAJORS-vs-ALTS SPLIT BEFORE THE NEXT ERA.**
     (**Registered 2026-08-26**; Tier 2 — must land BEFORE the next cohort
     starts accruing or it can never be tested honestly.) The deep dive's
     claim 3 (BTC/ETH/LINK +$4.56 on 18 trips carry the entire edge;
     DOGE/ARB/LTC/ADA/SUI −$3.67 on 27, negative before fee truth) measured
     majors−alts **+1.69% CI[+0.20,+3.36], d=0.70** — but the grouping was
     chosen **after seeing the data** and the concurrency-deflated p≈0.08.
     **POST-HOC — do not act on this p.** What closes it: write the exact
     asset partition into the next era's pre-registration (same discipline as
     the era-4 gate arms), then read it out once, blind. Asset selection is
     entry decisioning → cohort-resetting → batched with the boundary-#5
     adjudication.

102. **THE CONVICTION EDGE IS DIRECTIONAL ONLY — POWER IT.** (**Registered
     2026-08-26**; Tier 3, closes by accrual, no action.) Conviction (n=5)
     beat probe by **+2.52%/trip, d=1.03 (large), CI[−0.59,+5.80], p=0.062**
     — underpowered: **~16 conviction trades needed for 80% power, have 5.**
     A Wilson interval at n=5 spans nearly everything, so "the real trades
     are profitable" is evidence the losses come from the probe lane, NOT
     evidence the conviction edge is real. What closes it: the count reaching
     ~16 under whatever admission mix the operator's adjudication sets —
     re-run the deep dive's split then. Do not cite the +1.463%/trip true-fee
     conviction net as an established edge before that.

103. **THE 2026-08-22..08-25 REPO DOCKET IS UNFILED IN THIS VAULT.**
     (**Registered 2026-08-26**; Tier — vault hygiene / rule 10.) Four
     sessions of decision-relevant instruments exist only repo-side:
     `docs/quant/2026-08-22_*` (gate power analysis MinTRL/PSR — **POWER-1/2**,
     walkforward resampling tranche 2, turbulence instrument verification +
     episode history, crisis counterfactual REG-6, loop alignment audit,
     boundary-around-the-invariant note) and
     `docs/quant/2026-08-25_boundary5_adjudication.md` (the boundary-#5
     staging memo), plus HANDOFF rows **FEE-1/2/3, CONC-1, TRIALS-1, WHY-1**.
     The 08-26 source page cites them **by repo path, not by vault page** —
     until they are ingested, every vault statement leaning on the ×1.979
     anchor, the 0.8335 entry bar, or the MinTRL numbers is one dangling
     reference from an orphan claim. What closes it: a catch-up ingest
     (raw/ snapshots + source pages + index/log), same shape as
     `session-20260816-catchup-08-12-to-08-16`. Note **FEE-3** specifically:
     the venue tier row has NEVER been verified (OM-080 has never fired,
     n_records=0); one read-only `TradeVolume` call settles it, needs the
     first real credential on the box, scope query-only — every "true fee"
     number in the corpus is conditional on it.

**Item 97 CLOSED same filing, by route substitution** (see its entry — the
clean-cohort readout answered the question; 98/99 carry its residue). Still
open after this filing: 52, 54, 55, 59, 60, 61, 63, 64, 67, 69, 70, 71, 72,
78, 79, 80, 81, 83, 94, 95, 96, 98, 99, 100, 101, 102, 103.

---

**EXTENDED TO 52-105 at the 2026-08-27 SDD-verification filing**
([[sources/session-20260827-sdd-verification-and-era-confound]] — the
era-confound instrument defect, fixed `a94b5751` and hardened `62ab10c0`,
after which **every veto-quality row and the admitted-vs-baseline headline
read CONFOUNDED_BASELINE or PARTIAL_OVERLAP**). New items:

104. **A LIVE / CONTEMPORANEOUS GATE-EFFICACY BASELINE.** (**Registered
     2026-08-27**; Tier 2 — blocks a known fix: the instrument now refuses
     honestly but can render NO verdict.) The frozen 2026-07-20 baseline
     (84.1% `legacy` / 15.9% `exit_sim` / 0% `triple_barrier*`, 0 rows
     since) caps every active code's maximum weighted `label_era` overlap
     near **0.159**, so under the hardened guard nothing clears to
     COMPARABLE — SZ-021's anti-selectivity direction, SZ-023's
     "AT baseline", and SZ-030's "earns its keep" are ALL unresolved, not
     refuted. What closes it: a contemporaneous baseline population —
     the sandbox's **control-arm stratification tag** (metadata-only,
     era-matched forever, worktree `sandbox_control_arm`, branch
     `sandbox/control-arm-shadow-weights`) is the prototype of the root
     cure, **NOT merged**; its admission class (it touches row metadata at
     write time) is an OPERATOR adjudication, not assumed SAFE. Until it
     closes, no veto-quality verdict may be cited as evidence.
     **[UPD 2026-08-28: sandbox BUILT** — `11eafb97`+`f0f3c370`:
     deterministic 5% stratification tag (metadata-only, schema 94→95) +
     never-applied shadow gate-weight learner; projected accrual once live
     is usable n=30 in 0.85–1.6 days (measured 385–709 candidates/day).
     **Adjudication clause: its base is `a94b5751` — REBASE + FULL RETEST
     required before merge; its 107/107 greens do not transfer** (T5 §2).
     Status unchanged otherwise: NOT merged, OPEN, operator's call. The
     landed `0084c16d` (admitted-headline vocabulary) changes what the
     instrument SAYS, not this item's closing condition.]
     **[UPD 2026-08-28 (cut #8): MERGED-LIVE, pending first-row poll.**
     The operator's "both: full bundle" adjudication merged the control
     arm at the boundary — landed as `7b19181d` (stratification tag,
     schema **94→95**, `CONTROL_ARM_FRACTION` 5%, deterministic
     `sha256(asset|hour-bucket)` at the `_append_row` choke point) +
     `d64ad030` (shadow learner, never applied), inside the cut-#8
     bundle (`4e502478`, `origin/main`). The rebase+retest clause is
     DISCHARGED (7 pins re-baselined / 2 structural, full DoD green at
     the boundary); the tag is **written and never read** (repo-wide
     grep guard, `tests/test_control_arm_tag.py`). **The first LIVE
     tagged row has NOT been observed** — the label queue was quiet at
     deploy (the history rotation was rehearsed on a real copy, 18,657
     rows preserved) — that poll is what this item now owes first. Then
     the closing condition proper: the CTRL-2 consumer (an era-current
     baseline arm in `gate_efficacy_report.py` that clears
     `ERA_OVERLAP_MAJORITY` by construction and routes through the
     two-vocabulary verdict function, or it reintroduces the F1
     inversion) plus accrued minority-arm rows — usable n=30 projected
     in 0.85–1.6 days of live flow. Until both land, no veto-quality
     verdict may be cited as evidence. See
     [[sources/session-20260827-sdd-verification-and-era-confound]] §6.]

105. **A FRESH-WORKTREE SUITE LEG, PLUS DEFECTS #9/#10.** (**Registered
     2026-08-27**; Tier 3 / structural — the instrument is the suite
     itself.) Measured: the same suite reads 4060/0/9 on the live repo and
     2f/4085p/9s/1e on a fresh worktree, same day — live-repo greens
     OVERSTATE because host state masks fixture defects
     ([[concepts/host-state-dependent-green]]). What closes it: (a) fix #9
     (`_aux_emitted()` never rebinds `gc_pusher.VETO_SCRIPT`) and #10
     (`pc_supervisor._VAULT_GUARD_STAMP` missing from conftest
     `_REDIRECTED_PATH_ATTRS` — 10th leak-class instance, a REAL
     production-outputs write; both queued for the post-fix-wave fixer);
     (b) a standing fresh-worktree suite leg so the honest corpus runs on
     every gate, not once (adoption ranked in
     `docs/research/llm_test_suites/07_adoption_ranking.md`); (c) the
     order-dependent flake `test_fee_reconciliation::
     test_credential_less_environment_skips_silently` (minor #8,
     audit-chain state bleed) fixed or order-shuffled into visibility.
     **[UPD 2026-08-28: leg (a) CLOSED — `0257fd59`, pushed:
     `_VAULT_GUARD_STAMP` registered in `_REDIRECTED_PATH_ATTRS`, the
     veto-quality fixture rebound, `boundary5_stage` pinned;
     fresh-worktree acceptance green. Leg (c): the flake was
     triple-checked UNREPRODUCIBLE under serial scope and deliberately
     left — order-shuffle remains the instrument that would surface it.
     Leg (b) the standing CI leg is what keeps this item OPEN — and its
     scope GREW: the C++ diode's 8 skips are PERMANENT on this box under
     Smart App Control (locally-built unsigned binaries blocked;
     signed-compiler route exhausted 2026-08-28), so diode verification
     also has no home but the fresh-worktree CI leg or an operator SAC
     decision (T5 §5).]

**EXTENDED TO 52-106 at the 2026-08-28 cut-#8 prestige filing**
([[sources/session-20260827-sdd-verification-and-era-confound]] §6 — the
fee-truth epoch executed, `exec_era` `8-ca55e2ba`,
[[synthesis/comparability-boundaries]] row 8). New item:

106. **QT-1 — THE QUANT-TRIALS FEE MIRROR (a conscious re-baseline
     adjudication, owed).** (**Registered 2026-08-28**; Tier 2 — blocks
     citing a standing gate as evidence.) Cut #8 deployed
     `est_fee_bps=80` in config; `scripts/quant_trials.py`'s
     harness-owned `TIER_CFG["est_fee_bps"]` is still **40**, so the
     harness's declared "mirrors config.json's shipped block" property
     is DRIFTED by the cut. **Measured before deciding** (200×1200,
     seed 7; runtime-proven config-independent — 0 `config.json` reads
     at import or during `run_trials`): as-is **G1–G5 all pass,
     byte-identical to pre-cut**; mirroring the cut makes **G5 capture
     FAIL, 0.574 vs baseline 0.606**, and collapses G1's margin to
     4.84% vs cap 4.91% — the #103 T6 enablement shape. Left UNCHANGED
     and NOT widened, per the never-widen law: the standing gates are
     honest about the harness world they were baselined in, and now
     demonstrably NOT about the deployed cost world. **Until the
     operator's conscious re-baseline at 200×1200 lands, G1–G5 greens
     may not be cited as deployed-geometry evidence.** Authority:
     `scripts/quant_trials.py:73-82`, the QT-1 docket row in
     `docs/HANDOFF.md`, this session's boundary-#5 report.

Still open after this filing: 52, 54, 55, 59, 60, 61, 63, 64, 67, 69, 70,
71, 72, 78, 79, 80, 81, 83, 94, 95, 96, 98, 99, 100, 101, 102, 103, 104
(MERGED-LIVE, pending first-row poll + CTRL-2), 105, 106.

> [!info] **[UPD 2026-08-30 — item 106 (QT-1) RIDER: the drift NARROWED
> from 40bps to 2bps, and the item stays OPEN anyway.]** [[comparability-boundaries]]
> row 9 / cut #9 moved the DEPLOYED `est_fee_bps` **80 → 38**
> (`59bdcf87`). `scripts/quant_trials.py`'s harness-owned
> `TIER_CFG["est_fee_bps"]` is still **40** and was not touched by the cut.
> So the harness-vs-deployed gap is now **40 vs 38 = 2bps**, not 40 vs 80
> = 40bps — the harness is **near-coherent again, by accident of the
> correction rather than by adjudication**. Two things that do NOT follow
> and must not be asserted: (i) that the G1–G5 greens are therefore
> deployed-geometry evidence — **the 2026-08-28 measurement that produced
> the G5 0.574-vs-0.606 failure was run against the 80bps mirror and has
> NOT been re-run at 38**, so the current gap's effect on the gates is
> **[UNKNOWN]**, not "small"; (ii) that a 2bps drift is negligible —
> nobody has measured the gate sensitivity. **What closes it, unchanged:**
> the operator's conscious re-baseline at 200×1200, now cheaper to
> justify. Authority: `scripts/quant_trials.py:73-82`, commit `59bdcf87`,
> [[comparability-boundaries]] row 9.

**EXTENDED TO 52-111 at the 2026-08-30 cut-#9 / audit-wave filing**
([[sources/session-20260830-audit-wave-and-external-data-atlas]];
[[comparability-boundaries]] row 9; repo `docs/HANDOFF.md` WATCH LIST +
OPERATOR DECISIONS OWED + OWED-VERIFY register). Five new items:

107. **ERA6-COUNT-1 — NO TOOL COUNTS ERA-6 ACCRUAL, and the only gate
     headline on screen POOLS THREE CUTS.** (**Registered 2026-08-30**;
     SAFE / measurement-plane; Tier 2 — blocks reading a headline as a
     current-regime verdict.) `CLAUDE.md`'s era-6 moratorium says accrual
     begins "from zero" at the cut-#9 restart, but **no script computes
     that number**: a repo-wide scan for `16ec821e` finds it only in
     `core/fill_ledger.py:87`, `scripts/glass_console.py:55`, a test pin,
     and prose. Meanwhile `scripts/cohort_eval.py` prints
     `accrual: 72/50 … COST-BOUND` at **printed line 39 of 144**, which
     READS like a current verdict but is the pre-registered **era-4**
     population — a pure timestamp cut at
     `max(B4_TS, CAPITAL_EPOCH_TS)` = 2026-08-10T23:05:27Z (`cohort_eval.py:320-322`)
     — **pooling cuts `7-e7d5ca1a`, `8-ca55e2ba` and `9-16ec821e`**
     (enumerated at printed line **73**). **THIS IS NOT A COMPUTATION
     DEFECT AND MUST NOT BE "FIXED" BY FILTERING THE GATE** — the
     population is pre-registered (`:75-77`) and re-selecting it after
     accrual is exactly what pre-registration forbids (the file says so
     itself at `:270-272`). **Correction recorded against this item's own
     interest:** `COHORT HOMOGENEITY: MIXED(both)` prints at line **40**,
     ONE line below the headline — so the "a reader stops at the headline
     and never sees the disclosure" argument is **materially weaker than
     first written**; the pooling warning is adjacent. What survives is
     narrower and still real: the headline carries no era label,
     `MIXED(both)` names neither WHICH cuts nor in what proportion, and
     **no tool computes era-6 accrual at all** (the coverage half,
     untouched by the correction). **What closes it, both SAFE:** (a)
     label the era-4 headline as era-4/pooled at the point of print; (b)
     add a separate era-6 counter reusing `era4_trips()` **unchanged**,
     segmented on its existing report-only `eras` field — no change to any
     selection predicate.

108. **MLSEC-1 — THE ML-011 MODEL-TAMPER GATE POSITIVELY ATTESTS A FORGED
     ARTIFACT.** (**Registered 2026-08-30**; **[HIGH]** under a stated
     threat model; **COHORT-RESETTING** — the fix changes which models
     load, so it waits on operator adjudication. NOT fixed this session,
     deliberately.) Root cause, after an adversarial re-verify that
     **re-rooted an earlier, shallower diagnosis**: `ml/registry.py`
     `_record_hash` (`:64`, used at `:143` and `:209`) is an **UNKEYED
     public sha256**, so anyone who can write the ledger can also write a
     VALID chain over forged content. **Measured forged-chained-row case:**
     append ONE well-formed `registered` row whose `sha256` is the SWAPPED
     artifact and whose `prev` is the last row's `h` → `verify_chain()`
     returns `{'ok': True, 'rows': 3, 'chained': 3, 'reason': 'chain intact'}`
     **and** `verify()` returns `ok=True`. The swapped artifact is not
     merely un-rejected; it is **POSITIVELY ATTESTED**. Two separate,
     weaker symptoms sit on top and must not be mistaken for the disease:
     `ml/meta_model.py:83` rejects only on `v.get("ok") is False`, while
     `registry.py:284-287` / `:221-222` return `ok=None` for absent
     pedigree or an unreadable ledger — injection-confirmed 2026-08-30
     (control: ledger intact → `ok=False`, ML-011 fires, `p_win` falls to
     the prior **0.5600**; ledger deleted → `ok=None`, the swapped
     artifact **LOADS**, `p_win`=**0.9500**, the hard-clip ceiling, on
     every entry) — and an **EMPTY ledger passes `verify_chain()`
     vacuously** (0 rows = "chain intact"), so the verifier cannot tell
     *untampered* from *no evidence*. **CONSEQUENCE FOR THE FIX, stated so
     it is not under-fixed: "reject on `ok is not True`" DOES NOT CLOSE
     THIS.** That covers only the `ok=None` path; a forged row returns
     `ok=True` and sails through. A **keyed MAC, or an out-of-tree
     signer**, is the class of fix; nothing weaker is a fix. **THREAT
     MODEL, stated so it is not over-fixed:** the [HIGH] rests on a
     **PARTIAL-WRITE** attacker — one who can write `outputs/models/` (a
     hostile artifact drop, a stray process, a botched sync) but does not
     own the repo. **Against an attacker who already owns the repo, no
     gate here helps** — the ledger lives in the same directory as the
     artifact it attests and the verifier itself is editable. This is the
     **fifth** instance of the durable rule *a gate's release condition
     must never depend on the thing it blocks*. Live state healthy as of
     **2026-08-30T22:52:02Z** (chain ok, 177 rows, deployed artifact
     `1ee3ae68c0df` verifies `ok=True`) — a snapshot, not a standing
     property.

109. **PAGER-ROOT-1 — THE GRAFANA ROOT ROUTE STILL POINTS AT RECEIVER
     `empty` (0 INTEGRATIONS): THE RULE-#5 TRAP IS ARMED.** (**Registered
     2026-08-30**; **OPERATOR DECISION OWED** — not Claude's to make.) The
     47-day silent outage (rules created 2026-07-14 with
     `notification_settings: null`; **any firing 2026-07-14 → 2026-08-30
     paged nobody**) was fixed per-rule (`8f27a326`), and delivery is now
     PROVEN to the mailer by an **organic** firing. But the fix was a
     per-rule override by design (smaller blast radius), so **any rule
     created WITHOUT `notification_settings` routes to the void exactly as
     the outage did.** The 4 current rules are safe only because each
     carries its own override. **What closes it — operator picks one:** (i)
     repoint the root route at `grafana-default-email`, or (ii) mandate
     `notification_settings` on every new rule as a checklist item. Note
     the contact point is `provenance: "api"` → **UI-locked**, editable
     only through the API. **Second, smaller residual on the same lane:**
     the organic firing's `error=None` proves only that the mailer
     **ACCEPTED the handoff** — not inbox-vs-spam, and not that the
     mailbox is monitored. **Zero-cost close, operator-side:** eyeball that
     inbox *and its spam folder* for an `lb-drift-stuck` mail stamped
     ~2026-08-30T23:05Z.

110. **ERA6-MEMBERSHIP-1 — WHICH RULE DEFINES AN ERA-6 TRIP (4 or 7).**
     (**Registered 2026-08-30**; **OPERATOR DECISION OWED**.) On the
     22:47Z snapshot: **4** trips under stamp-purity AND under entry-time —
     and these two are **SET-EQUAL, not merely count-equal** — versus **7**
     under any-leg AND under close-time (the extra 3 ENTERED under cut #8
     at the superseded 40/80 booking and only EXITED under cut #9). The
     moratorium's "accrual begins at the cut #9 restart, from zero" most
     directly implies **4**, and 4 is what this vault files, but the
     membership rule was never written down and the operator owns it.
     **What closes it:** a one-line membership rule recorded beside the
     era-6 counter of item 107, so the count and its definition ship
     together.

111. **ATLAS-REDERIVE-1 — THE PUBLIC-RECORD ATLAS HAS NO DURABLE
     INSTRUMENT.** (**Registered 2026-08-30**; SAFE; Tier 3.) Every number
     on [[synthesis/public-record-data-atlas]] §3 (bucket-midpoint
     imputation bias, the assumption-free bounds, the power and
     multiplicity arithmetic) was computed by a **session-scoped**
     scratchpad script — `…/scratchpad/disclosure_stats.py` under this
     session's temp directory — which **is not in the repo, is not
     version-controlled, and will be garbage-collected**. The *inputs* are
     durable and public (the bucket ladder is statutory; the Belmont et
     al. citation is fixed); the *computation* is not. Per the
     no-orphan-claims rule this is a TASK, not a defect to shrug at.
     **What closes it:** either (a) re-derive from the closed forms
     recorded inline on that page — they are stated so the numbers can be
     regenerated without the script — or (b) if any of it ever becomes
     load-bearing for a decision, promote it into `scripts/` where the DoD
     matrix can see it. Until then treat the atlas §3 numbers as **[K] but
     un-re-runnable**, and re-derive before citing.

112. **FH-SIGMA-1 — THE FILL-HAZARD σ ESTIMATOR HAS AN OPEN DISAGREEMENT
     ON ITS OWN MECHANISM.** (**Registered 2026-09-14**; SAFE; Tier 2.)
     Two independent replays reproduced the shipped σ for
     `session_1789255778/PAXGUSD` (2.1583 → 7.1152 bps overnight — 100.00%
     of the 09-13 → 09-14 `d_bar` shift, mutation-verified) and DISAGREE on
     cause. (A) an instrument regime change: the tape's frame-gap
     distribution is bimodal, the overnight segment is a near-dead recording
     (median ≈ 30 s) that pushed the tape median 5.017 → 9.897 s and flipped
     the estimator's subsample stride 12 → 6; cadence-independent controls
     give 1.38× (60 s grid) and 2.17× (300 s) against the estimator's 3.30×.
     (B) a real volatility jump: the per-bar scale factor barely moved
     (2.2323 → 2.2477) while the 60 s-grid rms rose 3.27×, product = the
     exact σ ratio. Both agree the original author's fixed-INDEX-stride
     control is invalid (it fixes the index while the time base doubles).
     `scripts/calibrate_fills.py:131-188` has never been audited in its own
     right, and the LEVEL calibration shares this estimator with NO
     admission guard — its immunity to the fixture tapes now known to be in
     the ring is unestablished. **What closes it:** an adjudicated
     decomposition on that one tape — hold the wall-clock grid fixed and
     vary only the stride, then hold the stride and vary the grid — plus a
     statement, measured, of whether the LEVEL calibration reads any
     fixture tape. Source:
     [[sources/session-20260914-fill-hazard-audit-and-recording-leak]] §3.

113. **FH-NEFF-1 — EFFECTIVE n WITHIN A FILL-HAZARD RUN IS UNMEASURED.**
     (**Registered 2026-09-14**; SAFE; Tier 2.) `hazard_verdict`'s power
     gate (`MIN_EPISODES=80`, `E_MIN=10`, ≥2 resolved bins) counts NOMINAL
     episodes; the 09-14 run's ~10,744 come from FIVE fitted tapes,
     synthesized at stride 6 from overlapping frames, and 97.88% of them
     are bit-identical to the previous day's. The repo's effective-n
     standard (`gate_truth_report` since 2026-07-29, `cohort_eval` since
     2026-08-15) has never been applied to this instrument. A verifier named
     this as the ONE channel that could legitimately move NO → DEFERRED and
     explicitly did not measure it. **What closes it:** a per-tape /
     per-session cluster-robust n_eff printed beside the nominal count, and
     the power gate re-stated against n_eff — as a DISCLOSURE, never a
     re-tuned floor (the floors are measurement standards, CLAUDE.md).

114. **FH-RERUN-1 — THE RENDERED FILL-HAZARD REPORT WAS NEVER REPRODUCED
     END TO END, AND ITS EXCLUSION GUARD WAS NEVER MUTATION-TESTED.**
     (**Registered 2026-09-14**; SAFE; Tier 3.) Every audit lane called
     `fill_hazard_report.py`'s component functions (`discover_recordings`,
     `extract_frames`, `median_frame_gap`, `estimate_sigma_bps`,
     `episodes_from_frames`, `_overall`, `hazard_verdict`); nobody ran the
     generator, because a re-run reads a store that has already moved and
     would overwrite the untracked artifact under audit. If `render_report`
     misprints a flag or a verdict relative to what `_overall` received,
     nothing has checked it. The gap guard (`:429-433`) was
     injection-tested (all 199 fixture tapes shown excluded) and ablated
     (removing them changes nothing) but no mutant ever DISABLED it to show
     a fixture entering the fit. **What closes it:** one end-to-end run to
     a scratch output with the store snapshotted first, diffed field by
     field against a component-level reconstruction of the same snapshot;
     and one guard-deleting mutant run to show the verdict move (or not).

115. **REC-RING-1 — THE RECORDING RING'S PAST IS UNRECOVERABLE AND THE
     294 → 282 TAPE DELTA IS UNATTRIBUTED.** (**Registered 2026-09-14**;
     SAFE; Tier 3.) `outputs/` is gitignored, `_prune_recordings_now` logs
     a COUNT only, and `runner.log` has rotated — so the tape drop between
     the 09-13 and 09-14 reports (window start unchanged, frames +910)
     cannot be attributed from the present store; the one attribution
     offered was WITHDRAWN by its own verifier (4 × 7 = 28 ≠ 12; five such
     sessions, not four). 46 of 60 ring slots were fixtures at the 23:06Z
     read; whether the ring was already fixture-dominated before 09-06 is
     unknowable. The write side is FIXED (session source §4); the 46
     existing files are NOT deleted — cleaning live data is an operator
     decision. **What closes it:** the prune log naming the session ids it
     deletes (SAFE, runner-side, one line), and the operator's call on the
     46 files — delete by the sidecar classifier (`start.equity == 10000.0`,
     no `end`), or let the FIFO age them (each new real boot evicts the
     oldest by mtime). Same standing blind spot as
     [[synthesis/comparability-boundaries]] (`fills.csv` has no history).

116. **FH-COMPARATOR-1 — THE FILL-HAZARD L1 INSTRUMENT GRADES A SWITCHED-OFF
     SIM, AND L2'S PREMISE IS MOOT ON aeeaae36.** (**Registered 2026-09-15**;
     SAFE instrument change; **Tier 1** — every prior citation of an L1 "NO"
     is affected.) Found by a red-team panel, verified by grep before
     registration: `config.json:399 order_manager.sim_fill.passive_hazard_with_book:
     false` (set at boundary #4, `aeeaae36`, 2026-08-10, owed 57) gates the
     only `_passive_poll_prob` call (`execution/order_manager.py:1360-1363`);
     live dry-run fills use `_sim_maker_cross` (`:1340`), byte-equivalent to
     the report's own "opposite best quote at-or-through the level" event
     rule. So `scripts/fill_hazard_report.py`'s "constant comparator" is
     retired code and its nine post-boundary NO verdicts, `core/codes.py:492`
     XV-050's "(close L2)" gloss, and the 07-31 L2 plan all rest on a model
     that decides nothing. Riding with it, from the same panel: effective
     EVENTS per bucket are 4-6 against `E_MIN=10` (5 tapes / 3 sessions,
     buy+sell doubled per placement, MINA+FLOW 83% of 5-bps hits, both
     ex-universe since cut #11) — every row DEFERRED under any clustered n;
     the fitted frames are REST `get_order_book` snapshots written only when
     the WS book is >3.5 s stale (`max_age` 3.5 < poll 5) — a quiet-book
     sample of a book the sim never fills on, with BTC/ETH/LINK admitting
     zero tapes; and "T=5 polls" is minutes of wall clock (hit-conditional
     median 130-217 s), not 25 s. **What closes it:** (a) the generator reads
     the flag and, when false, prints that the comparator is retired and
     WITHHOLDS "Recommend closing L2" — nothing routed into `powered`,
     `REL_MISSTATE_MAX` untouched; (b) `core/codes.py:492` gloss corrected;
     (c) a pin that goes red when the report describes a disabled block, at
     ring magnitude on `run()` output, not a source grep; (d) L2 returned to
     the HANDOFF docket — mooted on `aeeaae36`, or re-posed against
     `_sim_maker_cross` with a clustered-n power gate and a wall-clock
     horizon; (e) **items 112, 113, 114 are RE-SCOPED**: owed only if L1 is
     re-posed against the live rule — as written they refine an instrument
     with no subject. Source:
     [[sources/session-20260914-fill-hazard-audit-and-recording-leak]]
     CORRECTION block; [[concepts/the-method]] #21.

117. **DUP-RUNNER-1 — A DUPLICATE LIVE RUNNER CLOSED ONE POSITION TWICE, AND
     THE FIX TOUCHES INVARIANT 5.** (**Registered 2026-09-15**; order lifecycle
     = COHORT_RESETTING by letter, invariant-5-adjacent → **operator
     adjudication**; Tier 1 — a naked sell in live mode.) `0526a410` PAXG,
     2026-09-10 06:58Z: two exit orders 3.3 s apart from two live processes
     (audit seqs 85264-85267 each written twice on two `prev`/`h` chains; both
     `starting_capital_usd 800`). The losing process latched `FT-020` and ran
     `cycle_once` — exits included — on the same iteration
     (`runner.py:1636-1641`, `:1696-1700`), forfeiting only at
     `LOST_LIMIT = 3` (`core/runtime.py:300`). Invariant 5 assumes the process
     owns the book. 1 of 533 closed trips; **RT-010 × 10** windows in 63.7 d
     (six on 09-10); **FT-020 × 469** (98 % false alarms). Full record:
     `docs/quant/2026-09-15_duplicate_runner_double_exit.md`. **What closes
     it:** the operator picks option 1 (skip the exit loop while
     lock-lost-latched — narrows invariant 5 to "by a process that owns the
     book"), 2 (cross-process exit-intent marker), or 3 (accept and monitor
     `RT-010`); plus two SAFE instrument fixes — `disposition_integrity_report`
     flags two `PT-061` on one pid, and `cohort_eval` counts what it drops at
     `:330`. The 09-10 relaunch storm (six live boots 04:44-06:55Z) is
     uninvestigated.

118. **ERA9-READOUT-1 — THE REGISTERED STATISTIC HAS NO INSTRUMENT, AND THE
     DATE IS ~2026-09-19..22.** (**Registered 2026-09-15**; SAFE sibling script;
     Tier 1 — the only product of era-9.) Registered at cut-#11 :86-99 and
     adopted by CLAUDE.md:158-161: net $/trip, 95 % day-block bootstrap CI (UTC
     closing day, 4,000 reps, seed 7), n=50 lean iff CI excludes zero, n=100
     verdict iff net>0 and CI excludes −fee. `scripts/cohort_eval.py` computes
     none of it (grep `bootstrap|day_block|seed|reps|4000` = 0): one threshold
     (:144), no n=100 tier, iid SE on nominal n (:378-379), %/trip, sign
     branches (:387-394), pooled six-era population, `COST_BOUND` on a positive
     median alone (:389-392). The registration's own power paragraph tests z
     against zero while its rule tests against −fee. **What closes it:** a
     report-only sibling (cohort_eval is "untouched" by law) computing (a)-(d)
     of `docs/quant/2026-09-15_era9_readout_registration_questions.md` Q7,
     pinned by a planted-edge / planted-null two-arm test, BEFORE n=50 lands;
     and the operator's answers to Q1-Q6 on the record, before the numbers are
     visible.

119. **CFG-FINGERPRINT-1 — THREE CONFIG FINGERPRINTS HAVE RUN UNDER ONE ERA
     STAMP AND THE COHORT TOOL CANNOT SEE IT.** (**Registered 2026-09-15**;
     SAFE report-only axis; Tier 2.) `CG-000` `config_sha256` inside era-9:
     `d3a2bfd0` at the cut boot (matches NO committed revision — unrecoverable),
     `ebbd0a85` ~24 h before its commit, `7aab700b` (watch_lane) applied by an
     unrelated restart; the last two verified benign. `EXEC_ERA` is a code
     constant (`core/fill_ledger.py:133`); config is read once at boot
     (`runner.py:1924`); the supervisor relaunches from the working tree with
     no dirty-tree guard (`pc_supervisor.py:803-807`). **What closes it:**
     attribute every era-9 trip to the fingerprint it ran under (join `CG-000`
     to fills by boot window) and print config purity beside era purity; and
     the one-line HANDOFF rule that a working-tree edit executes at the next
     stale-heartbeat relaunch.

120. **WATCH-PERSIST-1 — THE WATCH LANE DISCARDS ITS PENDING POOL ON EVERY
     RESTART.** (**Registered 2026-09-15**; SAFE, lane-private persistence;
     Tier 3.) `core/watch_lane.py` has no to_dict/restore; `core/persistence.py`
     has zero watch-lane hooks; 12 rows written, all barrier hits, zero
     time-outs — a corpus selected on outcome magnitude, P(direction | a big
     move already happened). `max_open_candidates 400` < the 432 in-flight
     slots a 36 h horizon needs. Deploy-fragile rather than structurally
     incapable (quiet-day uptimes 43-64 h still resolve only 16-44 %). **What
     closes it:** a lane-private file written from the runner's telemetry block
     via the existing `CandidateLabeler.to_dict/restore` (`ml/history.py:2912/
     2921`) — never through `core/persistence.py` — then a week of accrual and
     a barrier-mix read before any composition study.

Still open after the 2026-09-15 filing: everything in the 2026-09-15
correction line below, plus **117, 118, 119, 120**. 118 has a date.

Still open after the 2026-09-15 correction: everything in the 2026-09-14 line
below, plus **116**; 112-114 conditional on 116.

Still open after the 2026-09-14 filing: everything in the 2026-08-30 line
below, plus **112, 113, 114, 115**.

Still open after the 2026-08-30 filing: 52, 54, 55, 59, 60, 61, 63, 64,
67, 69, 70, 71, 72, 78, 79, 80, 81, 83, 94, 95, 96, 98, 99, 100, 101,
102, 103, 104 (MERGED-LIVE, pending first-row poll + CTRL-2), 105, 106
(drift narrowed to 2bps, re-baseline still owed), 107, 108, 109, 110, 111.

### Also still owed, restated for queue completeness (nothing new)
Item **49** (the CLI/runner ML-083 asymmetry) · **42e** · **37g/37b** · **45a-45f** · **41d/41e**
· the `status.json` empty-key PowerShell break · **53-residual** (the by-reason skip counter,
shared with the closed item 56) · **40b/XV-023** (now carrying **57b**, the single-path
recalibration).

### One board regeneration covers the panel half
**D1 repoint** (the hero tile still points at `liquiditybot_realized_total`; **now unblocked**,
since `gc_pusher` skips absent keys and `a6334162`'s keys exist in the running process
post-bounce) **+ item 55 + every other panel finding — in a SINGLE regeneration.**
**Boards are GENERATED. The JSON is never hand-edited.**

121. **MINT-PRICE-1 — THE "PRICE OF A MINT" FIGURES IN CLAUDE.md HAVE NO COMMITTED DERIVATION.**
    `CLAUDE.md` (accrual moratorium, "THE PRICE OF A MINT" bullet, added 2026-09-16) cites:
    12 boundaries in 37.9 days, median 2.43-day interval, and a censoring ladder
    (11.1% lost at a 16.1-day era, 57.1% at 2.6 days, 83.3% at 2.2, 100.0% at 1.1).
    The 2026-09-17 law audit tried to reproduce the count via `git log -S 'EXEC_ERA = '` and
    could not; the figures stand as recall pending an owed measurement. Until committed,
    these numbers are not evidence and may not be cited as measured. *What would close it:*
    reproduce the boundary count, date span, median interval, and censoring ladder from
    `outputs/fills.csv` / `audit.jsonl` / git history; commit the derivation notebook or
    report to `docs/quant/`; cite the committed path in `CLAUDE.md`'s "price of a mint"
    bullet. Authority: `docs/quant/2026-09-17_law_audit.md` §7 D5; `CLAUDE.md` accrual
    moratorium.
