---
title: "Session 2026-09-15 — one number revised three times, a position closed twice by two live runners, and a readout whose instrument does not exist"
category: source
status: PROVISIONAL
summary: "The operator (who has never coded before this project) asked for a master-session review of a bot that is 'never profitable'. The session's own headline number was revised THREE times: '+$4.45 gross, fees 5.4x it, COST_BOUND' (a six-era pool the law forbids) → 'era-9 gross NEGATIVE −$2.96' (a four-era pool that coincidentally equals era-12 alone) → the pre-registered standard: era-9 gross/trip −$0.11, 95% CI [−$0.52, +$0.29], effective n ≈ 6 at 22 stamp-pure trips — INDISTINGUISHABLE FROM ZERO. The orchestrator's carried-in CONTEXT block was the single most-refuted artifact of a 36-agent survey (14/15 findings survived, every one demoted). What survived: the cost is certain (48.6–50 bps, $0.30/trip, the registered H0); five held-out instruments find no directional information (direction AUC 0.495–0.515, CIs spanning 0.5; the 21-point long/short gap REVERSES inside era-9); 23 of 23 era-9 5m entries were exploration probes at forced p=0.85 (model 0.39–0.51) so the readout cannot falsify model skill in either direction; the registered statistic (net $/trip, 95% day-block bootstrap, 4,000 reps, seed 7, n=50/n=100 CI rules) is computed by NO script — cohort_eval branches on point-estimate signs over a pooled six-era population. Separately: a DUPLICATE LIVE RUNNER closed one PAXG position twice on 2026-09-10 (two order ids 3.3 s apart, two PT-061, audit seqs duplicated across two prev/h chains) because the losing process keeps running exits for LOST_LIMIT=3 heartbeats after latching lock-lost — invariant 5 assumes ownership; 10 true duplicate windows in 63.7 days (FT-020 cries wolf 469×). Code health: ruff clean tree-wide, shipped pyright 0, Pylance blind to scripts/+tests/ by include-list; 108 scripts/ errors root-caused, none produce a silently wrong number. Bottom line endorsed: no measured mechanism for making money at this horizon with these features; expected n=100 verdict STOP by either branch; dollars at risk zero; WAIT and build the registered readout first."
tags: [master-session, era-9, cohort-eval, pre-registration, duplicate-runner, single-instance-lock, invariant-5, exploration-probes, direction-auc, cost-stack, informational-loop, pyright, context-block-recurrence]
sources: 1
updated: 2026-09-15
---

# Session 2026-09-15 — master survey, the double exit, and the readout that cannot be run

Raw (verbatim primary artifacts, this session): `raw/audits/2026-09-15_session_f2f5d5cd/` —
`wf1_decision_discovery.json` (6 agents), `red_team_panel_recording_leak_fix.json` (26),
`architecture_language_fit_panel.json` (36), `master_repo_survey.json` (36) + `master_repo_survey_synthesis.txt`,
`pyright_ungated_scripts_tests.json`. Repo records written this session:
`docs/quant/2026-09-15_duplicate_runner_double_exit.md`,
`docs/quant/2026-09-15_era9_readout_registration_questions.md`,
`docs/quant/2026-09-15_recording_leak_red_team_docket.md`. Repo state at filing: `main` = `41288059`
(local, 1 ahead of origin, the recording-leak fix with its message amended once); runner RUNNING / DRY_RUN,
relaunched 2026-09-15T00:47Z by the Windows-Update reboot, healthy throughout.

Related: [[sources/session-20260914-fill-hazard-audit-and-recording-leak]] (earlier the same night) ·
[[concepts/the-method]] (#22 added here; #21 the dead comparator) · [[synthesis/owed-measurements]] (117-120) ·
[[synthesis/comparability-boundaries]] · [[concepts/resolution-vs-direction-decomposition]] ·
[[synthesis/live-readiness-verdict]] · [[concepts/false-green]] · [[concepts/observational-equivalence]].

**Claim status: PROVISIONAL (rule 21).** Discharge: (a) the fix commit pushed with its docket answered;
(b) the era-9 readout question set (Q1-Q7) adjudicated by the operator on the record. §2-§6 are settled by
the survey's verification and would not move.

All timestamps UTC. Every count as-of its stamp; re-derive, never recall. Nothing on the order path was
mutated or replayed by any lane; no battery ran alongside a fan-out.

---

## 1. The operator's framing, and what it changed

Verbatim: never coded before this project; "not losing a ton of money but it's never profitable"; a prior
session called the model "good at predicting $0"; wants a master session that flags its own instability.
Consequence for filing: findings are stated as what they mean for the money or the decision; file:line is
support, not the point.

## 2. One number, three times — the-method recurrence #22

| revision | claim | how it died |
|---|---|---|
| 1 | "+$4.45 gross before fees, fees $24.12 = 5.4×; COST_BOUND — a real edge fees eat" | `status.json` ledger pooled across SIX execution eras (7-12) and five fee rows; 1,030 of 1,322 fill legs carry a blank era and $377 of the $403 lifetime fees. The caveat was written; the conclusion was drawn anyway. |
| 2 | "era-9 gross NEGATIVE, −$2.96 across 66 trips since cut #9" | A four-era pool that coincidentally equals era-12 alone; era-9 proper (`9-16ec821e`) is **+$0.91**. And the orchestrator's own first re-derivation read **+$84.59** — one trip with a doubled exit (§3). |
| 3 | era-12 gross/trip **−$0.11, 95% CI [−$0.52, +$0.29]**, median +$0.10, 13/26 winners, **effective n ≈ 6** | The pre-registered standard. Both verifying lenses demoted "negative, decisive" to **undetermined**. At n=22 against a registered lean of 50 the sign cannot be resolved. |

Per-era table (fills.csv 2026-09-15T04:27Z, 1,322 legs; all CIs span zero): era-7 +$8.48 (59 trips, CI
[−$0.01, +$0.29]/trip) · era-9 +$0.91 · eras 10-11 −$0.91 · era-12 ≈ −$3 to −$4. **"Per-era gross is a table,
not a number" — HANDOFF:1055 said so on 2026-09-06; the survey prompt regressed it.**

## 3. The duplicate-runner double exit (repo record: `docs/quant/2026-09-15_duplicate_runner_double_exit.md`)

`0526a410` PAXG: entry 09-08 18:56Z; exits **`6daedca4`** 09-10 06:58:55Z and **`bc34b1bf`** 06:58:58Z, each
full size, both `tb_time`; two `PT-061` at 06:58:56.366 and 06:59:00.633, each full-size `net_usd`.
`audit.jsonl` seqs 85264-85267 each appear **twice** with different `ts` and `prev` — two writers, both the
live bot (`config_sha256 ebbd0a85`, capital 800): process A booted 06:39:48, process B 06:55:06 (`resumed=True`
from a snapshot holding the position). A latched `FT-020` at :55.881, **submitted its exit 0.3 s later**,
and forfeited (`RT-010`, pid 19160) 9.7 s after that. Mechanism (read, [K]): `runner.py:1636-1641` seals new
risk on the first lost heartbeat "— exits keep running (invariant #5)"; the loop breaks only at
`LOST_LIMIT = 3` (`core/runtime.py:300`, `runner.py:1642-1663`); `cycle_once` at `:1696-1700` runs on the
same iteration. Within one process it cannot happen (fill drain `main.py:2886-2897` precedes the stop loop
at `:3013`; `_submit_exit` dedups resting exits at `:2453-2465`). The repo's own docstring (`runner.py:424-428`)
names this seam. Scope: **1 of 533 closed trips, all eras**; **RT-010 × 10** in 63.7 days (six on 09-10),
**FT-020 × 469** (98% false alarms). Six live boots 04:44-06:55Z that morning. Classification: order
lifecycle + invariant-5-adjacent → **operator adjudication**; options in the record. SAFE gaps:
`disposition_integrity_report.py` cannot see two `PT-061` on one pid; `cohort_eval.py:330` drops the trip
silently. The survey found the same trip independently (lane money-truth) without reading the record.

## 4. What five held-out instruments agree on (survey lane signal-truth, verified)

Deployed gbt OOF Brier 0.2515 vs base-rate 0.2437 on 15,805 rows, day-block CI on the difference
[−0.0086, +0.0216] — "probably worse, not proven" (the null-floor line's "LOSES TO THE NULL" is a point
estimate with no margin, against a benchmark handed the test rows' own base rate); learning curve flat;
resolution AUC 0.616 vs **direction 0.510, 0/7 pairs significant**; day×side-stratified direction AUC
**0.515 [0.433, 0.605]** (stumps) and **0.495 [0.451, 0.540]** (logistic); the deployed model's walk-forward
importance drops "direction" from its top ten; the 52%-vs-31% long/short gap is the day's market move —
sign flips on 15 of 35 days and **reverses inside era-9 (shorts 54%, longs 37%)**. Detector validated by
planting (scrambled outcomes → 0.50; planted clue → lights). **And the model is not deciding:** 23 of 23
era-9 5m entries were `ML-070` probes at forced `p_win = 0.85` (`main.py:4728`) while the model said
0.39-0.51; zero conviction entries since the cut. Power caveat: 26-28 day-blocks cannot separate 0.50 from
~0.55 — a power-limited null, not a proof of zero.

## 5. The registered readout has no instrument

Registered (cut-#11 adjudication :86-99, adopted by CLAUDE.md:158-161): net $/trip, 95% day-block
bootstrap CI (UTC closing day, 4,000 reps, seed 7), n=50 lean iff CI excludes zero, n=100 verdict iff net>0
and CI excludes −fee. `scripts/cohort_eval.py`: one threshold (:144), no n=100 tier, naive iid SE (:378-379),
%/trip, point-estimate sign branches (:387-394), pooled n=131 population; `COST_BOUND` needs only a positive
median (:389-392). The earlier panel's correction ("that registration belongs to the feature-skill tools")
was **wrong**; the registration IS the gate's, verbatim at cut-#11 :88 — and its power paragraph tests z
against zero while its rule tests against −fee. **Three config fingerprints have run under the one era-9
stamp** (`d3a2bfd0` at the cut boot matches no committed revision; `ebbd0a85` ran 24 h before its commit;
`7aab700b` applied by an unrelated restart); the tool's homogeneity verdict segments by a code constant and
cannot see it. Seven questions for the operator, with the ~09-19..22 deadline, in
`docs/quant/2026-09-15_era9_readout_registration_questions.md`. Q6 — *what does the readout test?* — is the
one that matters: it will describe "$60 entries admitted by a constant under this geometry", not model skill.

## 6. Informational loops (review agent, read-only, double-derived)

Literal: 8 self-recursive functions, all bounded; 18 `while` loops, all with runner-owned or finite exits;
zero unbounded; one latent `__getattr__` recursion (`data/replay.py:68` reads `self._feed` before its `_`
guard) — SAFE. Circular: **T1-a** `fill_hazard_report` grades a config-disabled sim (#21) and
`learning_panel.py:77` re-emits it daily; **T1-b** `cohort_eval` judges a selector that did not select the
cohort (95.5% probes; the exploration off-switch counts rows the lane itself produces); **T1-c**
`cost_truth_report` — in dry-run the sim books fees AT the configured rate so "measured" = configured;
DANGEROUS unreachable. **T2-c** `pc_status.json['era4'].accrual_n = 131` pushed off-box while the honest
current-era count is 22. Also: the Grafana `live_labels_per_day_7d` tile (process-local deque, 13 era-9
restarts), `entries_enabled` true beside 5,366 "Blocked: max concurrent" lines, 45 fixture recordings still in
the ring (`calibrate_fills.py` has no fixture exclusion — the instrument that SET `passive_base_prob`).

## 7. Code health (the operator asked for the editor's view)

ruff: clean, entire tree, incl. 46,158 lines of `scripts/` the DoD never lints. pyright shipped scope: **0
errors** (ratchet holds, verified). compileall: 0. Security: no eval/exec/pickle/shell in shipped scope; keys
ship empty; deny-list broader than invariant 4 names. **`pyrightconfig.json` include-lists shipped scope, so
Pylance never checks 138,797 lines.** Those lines: 1,827 errors, of which 1,719 in tests are sanctioned
duck-typed doubles; 108 in `scripts/` root-caused — A `__doc__`→argparse (20, crashes only under `-OO`),
B pandas/numpy stub unions (50), C Optional past a correlated guard (23; two reachable on malformed input:
`pbo_row_sensitivity.py:155`, `candle_backfill.py:230`; `cost_truth_report.py:443` unreachable at 15/30),
D annotation mismatch (15). **None produces a silently wrong number; the reachable ones raise.** The
"subprocess stdout not narrowed" hypothesis was refuted by the reviewer against its own brief.

## 8. Refuted this session, kept so they are not re-derived

"Accrual stalled" (a never-persisted deque); "5/5 slots" (4); "the highest-value work is subtractive"
(454 LOC = 0.24%, paid in assurance); "13 decision points unpinned" (3 of the panel's own coverage claims
were false — pins live in `smoke_test.py` and assert values, not codes); "2,004 ms is Kraken's rate limit"
(our own `time.sleep`, on a loop the WS retired); "every exit pays taker, 17 bps avoidable" (config already
books exits at taker; ceiling $0.19/era, realized $0); "COST_BOUND was carried by the median alone" (at the
only readout that fired, mean and median were both positive; live risk for the coming lean); "market making
is dormant" (the A-S quoter prices every entry, one-sided, zero tests); "Kraken-only enforced by
`execution_eligible`" was NOT re-asserted — the deny-list is the enforcement, and `config.json:3` still says
otherwise (DOC_ONLY, owed).

## 9. What to do — the survey's ranking, endorsed

**[1] WAIT** — nothing on the order path until n=50 (~09-19..22) and n=100 (~10-01); do not save
`config.json`. **[2]** Build the registered readout as a SAFE sibling script before the date. **[3]** Settle
membership (22 vs 27; long book in or out). **[5]** Adjudicate the double exit. Then hygiene: config-
fingerprint axis on the cohort readout; persist the watch-lane pool; alert on config FATALs; the three
report-wording fixes; log the entry-plan name. Boundary-only: TP width, maker-rest TTL, entry taker fills,
`min_half_spread_bps`. NOT on the list: the hedged 12-asset book, two-sided quoting, model work.

## 10. What this session could not see

No mutation or replay on the order path; every cost number is a claim about the DRY-RUN fill simulator, not
Kraken — a live venue has never filled any of these 1,322 legs. Every gross sign is unresolved by
construction at n=22 / n_eff≈6. The direction-AUC instruments cannot separate 0.50 from ~0.55. `d3a2bfd0`
(the config that booted the era) is unrecoverable. The 09-10 relaunch storm's cause (six boots in two
hours; 40 supervisor "relaunching" lines since 09-08 vs 13 live boots) was not investigated. The long book
(2 of 5 slots, the era's largest winner) was surveyed by no lane. The fix commit is unpushed. The session
hit the account limit once (16 verifiers died; resumed from cache). Four of the orchestrator's own scans
were wrong before they were right (the +502 bps gross, the 48 "recursive" functions, the `$'\r'` line-ending
count, a battery that never ran and printed rc=0) — each caught by a second artifact, none by the exit code.

## 11. The two SAFE fixes the operator authorised ("Do this" — items 1 and 2)

**Item 1 — the watch lane's pending pool now survives a restart.** The lane registers
candidates and labels them when a barrier resolves; the pool between those two moments lived
only in memory, so every runner restart dropped it and nothing recorded the loss. The pool is
now snapshotted beside the corpus, restored at boot, written atomically (`mkstemp` +
`os.replace`), throttled to 600 s, and fail-soft on a corrupt file. **No magnitude for the
historical loss is written anywhere, because before this change there was no instrument for it**
— re-derive from the new `pending` / `restored_on_boot` snapshot keys once it ships. SAFE:
`separate_corpus=true`, `feeds_model=false`, no order path, era-9 untouched.

**Item 2 — OF-7 now prints its EFFECTIVE sample size beside the nominal one it gates on.**
OF-7 is the one rung built to catch an under-determined model (rows/feature vs a floor of 10)
and it computes that ratio on NOMINAL rows, over labels that overlap by construction — so the
gate designed to catch under-determination reads a row count the model does not have, and reads
it green. The new line is `info()`, never `check()`: **re-pointing a pre-registered gate at a
different quantity after seeing the data is the move CLAUDE.md forbids**, and a pin
(`test_of7_still_gates_on_the_nominal_count_it_was_registered_on`) asserts the verdict does NOT
move on a corpus that is un-starved nominally and starved effectively. The route is the same
`cohort_effective_n` the file already uses for OF-5, and it is **asset-blind** — a LOWER bound
on n_eff, which the returned dict says about itself in a string a pin checks.

**Three defects found in this session's own new code, all by running it rather than reading it:**

1. **A pin asserted a PRODUCTION path was absent.** `assert not (ROOT/"outputs"/
   "watch_history_state.json").exists()` — that file is exactly where the live pool BELONGS once
   the change ships, so the pin would have gone red on the operator's box the day it shipped and
   then kept blaming the test for the bot working. An absence check also cannot distinguish
   "this test wrote it" from "anyone ever wrote it". The write claim belongs to conftest's
   audit-hook tripwire (it watches `open`/`os.rename`/`os.replace`/`os.remove` and fails the
   OFFENDING test by name); what remains in the test is a PATH claim, which is deterministic and
   production-independent.
2. **An unread module constant holding a production path.** `WATCH_STATE_PATH` was introduced as
   "the DOCUMENTED shape, not the value the code reads". conftest redirects only the attribute
   names it has REGISTERED, so the first caller to reach for the obvious-looking constant instead
   of the method would have written into the operator's tree with nothing flagging it — the
   twelfth instance of the QA-writes-production class, pre-loaded. Deleted before it shipped.
3. **The atomicity pin was decorative.** It asserted only "no `*.tmp` is left" and "the result
   parses" — both satisfied by a plain `open(p, "w")`. A sweep replaced the whole
   `mkstemp`/`os.replace` block with a direct write and SURVIVED all 29 tests. The property
   atomicity actually buys is that a write dying MIDWAY leaves the previous file intact, and
   `"w"` truncates before the first byte; the pin now kills a save mid-serialisation at the real
   seam and reads the old pool back byte-for-byte. Related to [[concepts/false-green]]'s
   "vacuous test" variant, but distinct: this pin was not testing nothing, it was testing the
   mechanism's **litter** instead of the mechanism's **guarantee**.

Mutation after repair: **7/7** on the watch lane (FREEZE_AT_INIT, HARDCODE_PRODUCTION,
NO_RESTORE, NON_ATOMIC_SAVE, NO_TMP_CLEANUP, COUNT_FAILED_SAVE, SILENT_FAILURE) and **6/6** on
OF-7 (INVERT_SE_INFLATION, NOMINAL_ON_DEGENERATE, DROP_THE_CLAMP, SWAP_NOMINAL_AND_EFFECTIVE,
ROUTE_CLAIMS_TO_BE_THE_ANSWER, DROP_LENGTH_GUARD), sources restored byte-exact, control asserted
green in both.

## 12. The mutation harness reported 4/4 without running a single test — false green, INVERTED polarity

The first watch-lane sweep printed **`4/4 caught`**, every mutant dying in **~0.3 s**. Nothing
had run. The harness passed `--basetemp=/c/lbt/ms`, a **Git-Bash path that Python resolves as
`C:\c\lbt\ms`**, which does not exist — so `tmp_path_factory.mktemp()` raised at session-fixture
setup and every mutant "died" before a test was collected. The tell was the runtime (0.3 s for
29 tests) and the word **`error`** where a killed mutant produces `failed`.

**Why this belongs to [[concepts/false-green]] as a new variant, not an instance of an existing
one.** In every specimen on that page the broken machinery yields the *flattering* answer by
producing a **PASS**. A mutation sweep inverts the success criterion — its evidence of health is
a **FAILURE** — so a harness that cannot run produces **"100% of mutants caught"**, the most
flattering result the instrument can emit, and it does so through the *same* channel a genuine
100% uses. Design rule 2 of that page ("output must be read — exit codes are not evidence") is
necessary and **not sufficient** here: the output was read, and it said `1 error`, which is
exactly what a caught mutant looks like to a careless reader.

**The repair is mechanical, not vigilance:** a mutation sweep must run the **UNMUTATED CONTROL
first and assert it green** before reporting any mutant result, and must distinguish `error`
from `failed`. Both harnesses used for the rest of the session do this, and the corrected sweep
is the run that found `NON_ATOMIC_SAVE` surviving — i.e. the control row did not merely restore
confidence, **it paid for itself immediately**. This is `the-method`'s standing separator
("'0 findings' and 'the scan is broken' are the SAME OBSERVATION until separated") meeting
[[concepts/false-green]] from the opposite direction, and it is the session's second
self-caught instrument failure after §2's thrice-revised number.

## 13. Two live routes to one quantity disagree by 9 (unresolved, low stakes)

Stamped 2026-09-15T23:35:09Z: the live `watch_lane` snapshot reads `rows_labeled: 215`
(`evaluations: 271`, `watched: 11`, `errors: 0`) while `outputs/watch_history.csv` holds **224
data rows**. The likely reading is that the counter is per-process and the corpus is cumulative,
which would make the 9-row gap a direct measure of what earlier process lifetimes wrote — but
that is **[I], not established**, and it is exactly the quantity item 1's new snapshot keys will
answer. Recorded so the next reader does not cite either number as "the" row count. Note also
that an earlier workflow this session claimed the lane had labelled **12** rows; both routes
above refute that, and it should not be re-cited.

## 14. The restore path had no clock, and the file proving it was already on disk

`CandidateLabeler.restore()` checks the feature SCHEMA version. **Nothing checked the CLOCK.** A
watch candidate resolves within `label_max_bars` (36 h at 432 x 5 m); past that its vertical
barrier has already expired in wall-clock terms, and restoring it resumes the labeller's bar
series across a gap the size of the outage — a silent corruption of exactly the rows the
persistence in §11 exists to win.

**This was never hypothetical.** At the moment the restore path was about to ship,
`outputs/watch_history_state.json` existed on the operator's box: 27 KB, dated **2026-09-13**,
holding fabricated SOL bars on a perfectly round epoch of **1789300000.0** — which is the test
file's own `NOW` constant. Three independent routes identified it (the round epoch, the 300 s
exactly-spaced synthetic bars, and `git show HEAD:core/watch_lane.py` containing no
`_save_state` at all, so the live bot could not have written it).

**Its author was this change's own mutation sweep.** The `HARDCODE_PRODUCTION` mutant plants the
production path deliberately — that is its job — and conftest's audit-hook tripwire caught the
offending TEST and named it correctly. **The tripwire does not, and cannot, undo the write.** So:

> **A mutation sweep that plants a production-path defect PERFORMS that production write. The
> tripwire fails the test; it does not clean the tree. The sweep must delete its own artifact.**

The artifact survived two separate sweeps here before anyone looked, and the first thing it
would have done after the operator's next relaunch is get restored as a live pending pool.

**The gate that resulted** drops a pool older than the horizon, or stamped more than an hour in
the FUTURE (skew gets slack; a stamp beyond it is a fabricated or corrupt file, and a one-sided
check accepts every one of them). The drop is COUNTED in a new `stale_dropped` snapshot key,
because "there was no pool" and "there was one and it was refused" must never read alike.
`_BAR_SEC` is duplicated rather than imported — an unrelated import failure at boot would cost
the pool the restore exists to save — and a pin compares it to `ml.walkforward.BAR_SECONDS` so
the duplicate cannot drift.

Mutation after the addition: **11/11** on the watch lane, control asserted green first
(FREEZE_AT_INIT, HARDCODE_PRODUCTION, NO_RESTORE, NON_ATOMIC_SAVE, NO_TMP_CLEANUP,
COUNT_FAILED_SAVE, SILENT_SAVE_FAILURE, DROP_THE_AGE_GATE, AGE_GATE_ONE_SIDED,
SILENT_STALE_DROP, WRONG_BAR_WIDTH).

**The shape worth carrying forward:** the defect was not found by reading the new code, by a
review, or by a gate. It was found by looking at *what was on disk* and asking who wrote it —
the same move that opened §12. Both of tonight's real findings came from treating an artifact
as evidence about its author rather than as background noise.

## 15. Battery state at close (pre-existing red, adjudicated — NOT caused by tonight)

`scripts/overfit_check.py` exits **1**: `passed 4, failed 1, informational lines 50`, corpus
`live history (19203 rows)`, 110 s. The failure is **OF-5 DSR** —
`dsr=0.003 sr=-0.29 n=33 sr0=0.241 (probes excluded: 417)` — which `docs/HANDOFF.md` records as
armed-and-failing since **2026-09-11** with the operator ruling **"Keep pooling — SETTLED"**; its
28 anti-silencing pins pass. Proven not-mine two ways: the diff's only hunks are at lines
716–820 and 1708–1734 while OF-5 lives at 1794, and the only lines in the diff matching
`dsr|sharpe|sentinel|conviction` are **prose in two comments**. The task-completion notification
for that run said "exit code 0" — that was the SHELL's; the battery's own marker said
`OF_RC=1`, the same reader-versus-process trap [[concepts/false-green]] logs as its seventh way.
Read the marker, never the wrapper.

## 16. The report-only line that took down the gate it reports on

`scripts/overfit_check.py`'s `load_dataset` has **two** return paths. The live one hands back
real arrays. The SYNTHETIC one returns `(Xs, ys, None, None, None, ...)` — **its own docstring
says so in as many words** — and the first version of `dof_effective_n` (§11, item 2) took
`len(sig)` OUTSIDE its `try`. `len(None)` raised a `TypeError` that took the **whole battery**
to a non-zero exit.

**Eight suite tests caught it**: `test_overfit_check_ci.py` (×5), `test_overfit_gate_policy.py`,
`test_pbo_variants.py` (×2) — every one a test that runs the battery as a SUBPROCESS and asserts
exit 0. All 35 in those files pass once the guard is added, so the crash was the sole cause.

**Three things this is worth remembering for:**

1. **A report-only line taking down the gate it reports on is the worst failure available to
   SAFE-class code.** SAFE class buys the right to ship fast *because* it cannot affect the
   governed path. A crash revokes that guarantee retroactively — and it does it to the single
   instrument the operator reads to decide whether the model is overfit.
2. **The live corpus could never have shown it.** Every check run while building this used the
   live path, where `sig`/`res` are real arrays. The defect lived exclusively on the branch the
   development never touched. Reading the docstring was not enough either: the line *"so res is
   None"* was read during this same session, from this same file, and did not connect.
3. **The catching gate was 3m45s of subprocess and the diagnosis was one word.** Eight tests
   spent nearly four minutes to report `TypeError`. A direct unit pin
   (`test_dof_effective_n_survives_the_synthetic_paths_none_label_times`, three argument shapes)
   says the same thing in microseconds AND names the cause in its docstring. When a slow gate is
   the only thing standing between a defect and production, someone eventually skips it — so a
   slow catch is a reason to add a fast pin, not a reason to feel covered.

Mutation after repair: **8/8** on OF-7 (DROP_THE_NONE_GUARD, INVERT_SE_INFLATION,
SKIP_DEGENERATE_GUARD, DROP_THE_CLAMP, SWAP_NOMINAL_AND_EFFECTIVE,
ROUTE_CLAIMS_TO_BE_THE_ANSWER, DROP_LENGTH_GUARD, REVERT_TO_THE_O_N3_HELPER), control asserted
green first.

**Tonight's running tally of defects found in this session's OWN new code: seven.** A pin
asserting a production path was absent; an unread constant holding a production path; a
decorative atomicity pin; a mutation harness that never ran; a cubic-complexity helper that
wedged the battery; a fixture wrong about bar quantisation; and this crash. Every one was found
by RUNNING something — a sweep, a battery, a suite, or a directory listing — and not one by
reading the diff. That is [[concepts/the-method]]'s second operating consequence stated as a
score rather than as advice.

## 17. The firing audit — is the machine doing what it was designed to do? (2026-09-16)

Operator instruction, verbatim: *"do the work to fix all of it and look at how the bot has been
firing to make sure it's been doing what it is supposed to do or what our theory is to become."*

**Method.** A control lane established the design's own FALSIFIABLE PREDICTIONS from the docs
alone, having read no ledger, so the comparison could not be contaminated by the outcome. Seven
observation lanes then measured the ledgers against those predictions, each adversarially
refuted, then a reconciliation lane. 16 agents.

**Verdict: QUALIFIED YES ON SAFETY, NO ON THE EXPERIMENT.** See [[wiki/log]] 2026-09-16 for the
headline numbers. Three things are worth carrying forward as METHOD rather than as findings:

1. **A claimed breach that does not survive adjudication is not a breach.** Six were claimed; all
   six fell. One ("the ALGO-7 stop nudge breaks geometry alignment") inverted completely — the
   code's own docstring MANDATES the behaviour, so omitting it would have been the breach. A
   reviewer who stops at "found six problems" ships six false alarms.
2. **The decisive finding needed no statistics at all.** The structural truncation is arithmetic
   over four config values. Every statistical framing of the same question (live-vs-candidate PT
   rates, n=20) is UNRESOLVED and will stay unresolved for months. When a question has an
   arithmetic form, find it before reaching for a sample.
3. **The audit's most useful output was a NOT-ESTABLISHED list.** It refused to convert a
   structural certainty into a dollar cost, and named the missing instrument (per-position peak
   unrealized gain, SAFE, does not exist) rather than estimating around the gap.

**What the operator's own question turned out to mean.** He asked whether the bot does what it is
supposed to do. The answer is that it does exactly what it is CONFIGURED to do, and the
configuration encodes two bets that fight each other: a labelled bet that wants 1.80% before
1.35%, and a safety overlay that closes at a fraction of that first. Neither is a bug. The
conflict was never written down anywhere, and no instrument reported it, which is why it survived
five era cuts and 65 days.
