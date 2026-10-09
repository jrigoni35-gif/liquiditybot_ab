# Raw record — fill-hazard L1 instrument audit, 2026-09-14

Workflow `wf_c7fce1a0-10d` (session f2f5d5cd), 34 agents (2 haiku, 32 session-model), 651 tool
uses, 49.4 min, 3.24M subagent tokens. Structure: 1 prior-art pass → 5 audit lanes
(d_bar normalizer · tape-count regression · five-fitted-tapes · near-touch flip · repo hygiene)
→ each lane's top 2 findings attacked by 3 adversarial verifiers (mechanism / consequence /
arithmetic; majority-refute kills) → 1 synthesis. **9 findings judged, 9 survived, 0 refuted.**
Verification cap: 2 findings per lane; 18 further findings across four lanes were NEVER
adversarially checked (near-touch 3, d_bar 3, five-fitted 7, tape-count 5).

Subject: `docs/quant/2026-09-14_fill_hazard_l1.md` (untracked at audit time; generated
2026-09-14 10:33:33Z by `scripts/fill_hazard_report.py`, 753 lines) vs the tracked 09-13 run.
Trigger: the 09-13 → 09-14 diff showed `d_bar` shifting by a UNIFORM ÷1.59 across all seven
distance buckets, tapes 294 → 282 with the window start unchanged and frames +910, near-touch
flipping n → y at 15 bps, and EXACTLY 5 tapes fitted both days. None disclosed in the report.

> **CORRECTION 2026-09-15T01:47Z — the audit graded the arithmetic of an instrument
> whose SUBJECT is retired code, and this record amplified it.** A red-team panel on
> the follow-up fix (`wf_53a6ada2-6ea`, 32 objections / 18 surviving / 2 CRITICAL)
> found, and the orchestrator verified by grep before writing this: the "sim under
> test" (constant per-poll hazard `passive_base_prob × exp(−d/σ)`, report line 6) has
> been OFF since execution-era boundary #4 (`aeeaae36`, 2026-08-10T11:03:35Z) —
> `config.json:399 passive_hazard_with_book: false`; the sole `_passive_poll_prob` call
> (`execution/order_manager.py:1363`) is gated on that flag at `:1360`; the live dry-run
> fill rule is `_sim_maker_cross` (`:1340`), byte-equivalent to the report's own event
> definition. **The fit is the sim measuring itself**, and `config.json:400`'s `_doc`
> said so the whole time. Consequences for THIS record: F3's "YES arm could not fire"
> stands as arithmetic but is moot as evidence about any deployed model; F4/F5/F6
> stand as instrument findings; the "Refuted but worth naming" ablation (no fixture
> data in the statistics) stands. Further CRITICALs from the panel, all verified
> against the report text: **OBJ-17** — Wilson/Greenwood/LR/`powered` treat 10,744
> episodes as iid; they are 5 tapes from 3 sessions, buy+sell doubled per placement,
> MINA alone 67% and MINA+FLOW 83% of 5-bps hits (both ex-universe since cut #11); two
> design-effect routes put effective EVENTS at 4-6 per bucket vs `E_MIN=10`, so every
> row is DEFERRED under any clustered n. **OBJ-18** — the instrument fits REST
> `get_order_book` frames, written only when the WS book is >3.5 s stale (`max_age`
> 3.5 < poll 5): a quiet-book-conditioned sample of a book the sim does not fill on;
> BTC/ETH/LINK admit zero tapes. **OBJ-13** — "T=5 poll horizon" is not 25 s: frame
> index ≠ poll age inside the admitted tapes (hit-conditional wall age median
> 130-217 s). The panel's docket is at the session's `tasks/wep9qecgf.output`;
> dispositions: `docs/quant/2026-09-15_recording_leak_red_team_docket.md`. Owed 116.

## Headline (synthesizer, verbatim)

> Every number in the 2026-09-14 fill-hazard report reproduces and its NO is arithmetically
> correct, but the corpus headline counts QA smoke-test fixtures — because
> `scripts/smoke_test.py` writes into the live recording store and is evicting real
> recordings — so commit it with a disclosure addendum and read "close L2" as a bound the fill
> rate fixed in advance, not as a market finding.

## Confirmed findings (all 0-of-3 refuted unless stated)

**F1 — QA smoke battery writes fixtures into the LIVE recording store and evicts real
recordings.** `scripts/smoke_test.py qa_redirect_paths` (lines 91-155) redirected ten
production destinations but NOT `system.recording_dir`; section [20] constructs a real
`BotRunner` on the production config at `smoke_test.py:1416`, where `record_feeds: true` and
`recording_dir: "outputs/recordings"` (`config.json:976-977`); the store is a FIFO ring at
`retain_files: 60` (`config.json:982`), sat AT 60, most slots 21-line MockKraken fixtures; real
sessions logged in `runner.log` absent from the store. `tests/test_qa_isolation.py:81-85`
EXEMPTED `system.recording_dir` on the written justification *"a QA bot that constructs the
engine directly cannot reach feed recording"* — falsified by `smoke_test.py:1416`. Severity
high, SAFE class. Two verifiers upgraded it from inference to demonstration: one replicated
1402-1416 with only recording_dir redirected and watched a `session_*.jsonl` + sidecar appear,
then re-ran with `record_feeds=False` and watched nothing appear; another ran
`test_runtime_and_runner()` in a scratch cwd and produced 210,960 B / 21 frames, matching the
live fixtures (210,750-211,208 B, 21 frames). Verifiers corrected the actor: QA boots supply
the slot pressure, the live runner's hourly prune usually executes the delete. Until fixed, the
report's own re-open condition ("re-open only if richer recordings contradict this") is
structurally unreachable.
→ **FIXED same session** (working tree; see "Orchestrator addendum").

**F2 — The corpus headline and evidence-limits block count fixtures as corpus; one published
number is wrong.** Line 5 "59 session(s), 282 symbol-tape(s)" is majority fixture by session
and by tape (~1% by book FRAME); line 45 "~143.4 book polls per tape" divides real frames by a
fixture-inflated tape count, UNDERSTATING real per-tape depth ~3.5×; line 44 attributes every
excluded tape to "burst re-read tapes" when most were never market data. `grep -Eic
'mock|fixture|smoke|retention|prune|evict|FIFO'` over the report = 0. Fixture share
triple-derived by three classifiers agreeing exactly: (a) first kraken `get_order_book` with 15
levels and best bid ∈ {59985.0, 1999.5}; (b) raw byte fingerprint of `synth_book`'s size float;
(c) sidecar `start.equity == 10000.0` with no `end` key. Verifiers amended in the report's
favour: fixtures do not widen wall-clock span; exclusion MAGNITUDE is already disclosed one line
below; what is missing is the CAUSE. The polls-per-tape error cuts conservatively.

**F3 — The YES arm could not fire on this corpus and the report does not say so.** Holding the
5 bps bucket's episode and event counts at T=5, the max relative misstatement of F(T) over ALL
hazard shapes ≈ 1.46% against the 10% YES threshold; YES reachable only at cumulative fill
≈ 24% vs observed ≈ 3.6%. `hazard_verdict`'s `powered` gate (`fill_hazard_report.py:339-340`)
tests counts only (episodes ≥ 80, events ≥ 10, resolved bins ≥ 2), never attainability. So a
powered NO + "Recommend closing L2" sits beside LR p < 0.05 in 5 of 7 buckets. All three
verifiers reproduced by injection on the unmodified path: 1.4584% / 1.4378% at the extremes,
YES floor bisected 24.2228-24.2265%, closed-form 24.2264%, and the YES arm proven LIVE
(F(T)=0.25 → YES/XV-051). Three amendments survived: (1) the ceiling is a property of the
ENDPOINT metric — `constant_hazard_mle` is fitted on the same exposure so both models agree at
t=T by construction; on the REAL fitted 5 bps shape the misstatement at poll 1 is **11.18%**,
above threshold, and the report samples only t=T. (2) Conditional on near-zero censoring; with
censoring free at the same fill rate the live `hazard_verdict` returns YES (15.9% / 51.1% /
73.0% at 5000 / 9000 / 10000 censored). (3) Two verifiers read this as making close-L2 MORE
supported (distribution-free bound), one as discarding shape evidence. Both on record.
**Do not "fix" by adding an attainability test to `powered`** — that routes a decisive analytic
negative into DEFERRED forever.

**F4 — `d_bar` is an unweighted mean of 1/σ over the fitted tapes** (`fill_hazard_report.py:444,
:445, :705` — distance ÷ harmonic mean of per-tape σ); with five fitted tapes ONE
(`session_1789255778/PAXGUSD`, σ 2.1583 → 7.1152 bps) carried ~53% of the divisor both days, and
the overnight 1.59× shift is **100.00% attributable to that single tape**. Nothing in either
report says so: `grep -i sigma` = 1 line (the sim-formula header); the per-tape `[^sigma]`
footnote (:560-569) is suppressed because `sigma_fallback_tapes == 0`. Two verifiers ran
full-store as-of-cutoff replays importing the shipped functions and reproduced all five sigmas
and the entire `d_bar` column to displayed precision; the attribution was double-derived
(closed form dK = (1/2.1583 − 1/7.1152)/5, and by MUTATION — restoring that σ into the 09-14
set reproduces the 09-13 column exactly). affects_verdict demoted true → structural:
`hazard_verdict` takes no d_bar; a 0.01×-100× sweep of the divisor yields only NO or
INSUFFICIENT_EVIDENCE.

**F5 — Consecutive runs are near-duplicates and the disclosure names the wrong pair.** 09-13 and
09-14 are fitted on the IDENTICAL five tapes, four byte-identical; **10516 of 10744 episodes
(97.88%) are bit-for-bit the same tuples** (`episodes_from_frames(f14)[:1074] ==
episodes_from_frames(f13)` True in all seven buckets). Line 8's "the 2026-09-08 and 2026-09-10
runs shared 7 of their 9 days" is a **hardcoded string literal at
`fill_hazard_report.py:507-511`**, never recomputed. Episode totals reproduced to the unit via
stride `len(range(0, N-1, 6))`: 5258×2 = 10516, 5372×2 = 10744. 2-of-3 sustained (the refute
vote granted the facts, attacked consequence). Extension: the 681 NEW frames that constitute all
of the run's new information have their own median intra-frame gap ≈ 30 s and would FAIL the gap
guard standalone; they pass only because pooling with the older 5 s frames drags the tape
median inside the admission band — **the per-tape MEDIAN guard is blind to a contiguous
out-of-cadence tail.**

**F6 — `near-touch` gates the verdict and the report never says so.** `_overall`
(`fill_hazard_report.py:451-463`) filters to near-touch rows FIRST and returns
INSUFFICIENT_EVIDENCE if none survive; `near_touch = d_bar <= D_MAX_DEFAULT` (= 2.0,
`core/fill_calibration.py:52, :713-714`); the primary-bucket selector (:571) reads the same set.
Neither report defines the column or prints 2.0. All three verifiers ran injections against the
shipped `_overall`: a planted YES at 15 bps yields YES/XV-051 under the 09-14 d_bar and
NO/XV-050 under 09-13's; positive control d_bar×4 → INSUFFICIENT_EVIDENCE. But the flip was
INERT: exhaustive enumeration of all 127 non-empty near-touch subsets against the all-NO vector
returns the single element ('NO','XV-050'); primary is 5 bps in every bucketed report ever
written; the flip ENLARGED the near set, away from the only reachable transition, which fails
safe by withdrawing the recommendation. `_overall` and `near_touch` are pinned by no test.

**F7 — `docs/HANDOFF.md:181` says the 09-08 report is "(untracked)"; it has been tracked since
`644baee2` (2026-09-10 17:57:14 -0500), which SETTLED the convention (committed roughly weekly)
and explicitly overturned an earlier audit that proposed gitignoring them — and no RECENTLY
SETTLED row was ever filed (contract rule 2, line 1112). All three verifiers REFUTED the
original remedy ("remove the word"): line 181 is inside a stamped ERA-8 day-log entry and the
REGISTER-DECAY REPAIR clause (lines 18-22) requires corrections attached, never deleted.

## Refuted but worth naming (verbatim from the synthesis, condensed)

1. **affects_verdict was asserted TRUE on five findings and is FALSE on all five — refuted by
   MEASUREMENT.** A verifier removed all 46 all-mock sessions in-process and re-ran the fit:
   every bucket row byte-identical, overall NO/XV-050. Positive control — dropping ONE real
   fitted session moved everything (episodes 10764 → 9442, h_const 0.00744805 → 0.00769859).
   Mechanism: `fill_hazard_report.py:432-433` `continue`s a gap-excluded tape BEFORE episode
   synthesis, and every fixture tape's median gap (0.018-0.186 s) is 9× below the floor
   poll/3 = 1.667 s. **The shipped statistics contain zero fixture data.**
2. "The 12 vanished tapes were fixtures; zero real data lost" — WITHDRAWN by its own lane's
   verifier: all four cited 09-06 seven-tape sessions still on disk; 4×7 = 28 ≠ 12; five such
   sessions, not four. `outputs/` is gitignored with no history — the 294 → 282 delta **cannot
   be attributed from the present store at all.**
3. "The corpus is mostly synthetic" is a cherry-picked denominator: true by session (~78%) and
   tape (~72%), false by frame (~1%). Frames bound power. CLAUDE.md reading-discipline (a),
   committed by a finding auditing an instrument for the same error.
4. **Unresolved disagreement on WHY the dominant tape's σ tripled.** Verifier A: cadence-
   independent controls give 1.38× (60 s grid) and 2.17× (300 s) vs the estimator's 3.30× —
   an instrument regime change (bimodal gap distribution; overnight segment near-dead at
   median ≈ 30 s pushed the median 5.017 → 9.897 s, flipping subsample stride 12 → 6).
   Verifier B: per-bar scale barely moved (2.2323 → 2.2477) while 60 s-grid rms rose 3.27×,
   product = exact σ ratio — the vol jump is real. Both agree the original author's
   fixed-index-stride control is invalid. Live question on `scripts/calibrate_fills.py:131-188`.
5. "Max misstatement over all shapes is 1.46%" is over-quantified — [I] not [K]; holds
   episodes, events AND censoring fixed.
6. **The d_bar cliff nobody named:** the only d_bar-driven transition is d_bar@5 > 2.0, which
   empties the near-touch set and silently reclassifies the run to INSUFFICIENT_EVIDENCE with
   no callout. Needs ~3 of 5 tapes near the σ floor. Also: the dominant tape's median gap
   (9.897 s) is ~66% of the way to the 15.0 s exclusion bound; had it crossed, d_bar@5 =
   0.5073 vs observed 0.5464 — two different corpus events, one nearly indistinguishable number.
7. The primary-bucket half of F6 is structurally inert: d_bar ∝ distance so near-touch is a
   strict PREFIX set; events decrease monotonically; primary = nearest qualifying bucket
   always (all 8 reachable prefix sets → 5 bps or None).
8. The proposed HANDOFF fix was forbidden by HANDOFF itself (register-decay clause).
9. **Provenance defects in the findings' own evidence:** (a) a needle reported as `near_touch`
   actually returned the hyphenated prose form — five of nine cited line numbers could not have
   come from the stated filter; (b) a raw `diff` returns all 49 lines changed, not 17, because
   09-14 is CRLF and 09-13 is LF (orchestrator: **git**, not the generator —
   `.gitattributes` `* text=auto eol=lf`; 09-14 CRLF=49 raw, 09-13 LF=49 in blob and tree);
   (c) "a full-range scan of every tape at each cut" is a RECONSTRUCTION — no replay
   reproduces either header count (245 vs 294 at the 09-13 cutoff; 261 vs 282 at 09-14).

## Commit recommendation: `commit_with_caveat`

Caveat text (hand-added addendum for the report's Evidence-limits section; no volatile number
written, each names its re-derivation) and the two HANDOFF edits (a RECENTLY SETTLED row
inserted after line 1046; line 181 repaired by ATTACHING the correction) are held verbatim in
the workflow output at
`…/f2f5d5cd…/tasks/wihtfgbiv.output` lines 107-110 and in the session transcript.
**Nothing licenses acting on "Recommend closing L2"** — label geometry is COHORT-RESETTING.

## What the audit could not see (synthesizer, condensed)

Read-only scope — **nobody re-ran the generator end to end**; every lane called component
functions. The reports' own corpus is UNRECOVERABLE (store prunes, no history); header counts
never re-derived; the 294 → 282 drop UNEXPLAINED. Exclusion filter injection-tested, never
mutation-tested (no fixture tape was ever pushed INTO the fit). σ estimator: open disagreement,
`calibrate_fills.py` never audited in its own right (LEVEL calibration shares it and has no
admission guard). Eighteen lane findings never adversarially checked. No lane covered the
LEVEL question, `_clean`'s reject conditions, or effective-n WITHIN a run (MIN_EPISODES=80 /
E_MIN=10 are NOMINAL over ~10,744 clustered episodes from five tapes — the channel that could
move NO → DEFERRED, explicitly unmeasured). **The store mutated during the audit** (reads
22:18Z-22:40Z; tapes 282 → 277 → 276; d_bar@15 1.64 → 1.56). No repo file modified by any lane.

## Orchestrator addendum (same session, after the audit)

**Corroboration of F1 by a second route (23:06Z):** `scripts/smoke_test.py` has ZERO
references to `recording_dir` / `record_feeds`; `tests/test_qa_isolation.py:81-85` carries the
exemption and quoted justification verbatim; `config.json:976-982` `record_feeds: true`,
`retain_files: 60`; store = 60 sidecars = the cap, **46** with `"equity": 10000.0` (the audit's
46 to the unit), 14 real.

**Fix applied (working tree, SAFE class, uncommitted at this writing):** `qa_redirect_paths`
now sets `cfg["system"]["recording_dir"] = str(d / "recordings")` (redirect, not disable —
`main.py:725` reads `record_feeds` for serial-feed mode); `tests/test_qa_isolation.py`:
`system.recording_dir` removed from `_EXEMPT` (its false justification replaced by the record),
added to `_KNOWN_LEAK_KEYS`, docstring renumbered to TEN instances (the singletons were already
the ninth), and a new end-to-end pin
`test_a_runner_under_the_redirected_config_records_outside_outputs` constructs a real
`BotRunner` on the redirected production config with a duck-typed bot and asserts the sink's
parent IS the redirected directory (distinguishing "the redirect worked" from "chdir saved us").

**Proof, three ways:** (1) suite 25 passed; (2) MUTATION PAIR — redirect line removed → 5 pins
red (`test_no_config_path_survives_redirect_pointing_at_outputs`,
`test_known_leak_keys_are_actually_set[system.recording_dir]`, the new e2e pin,
`test_replay_config_leaves_no_path_under_outputs`,
`test_replay_sets_every_known_leak_key[system.recording_dir]`) → restored → 25 green;
(3) INJECTION on the real `test_runtime_and_runner()` from a scratch cwd — mutant arm:
`session_1789427935.jsonl` appeared in scratch `outputs/recordings`; fixed arm: nothing in
scratch, `session_1789427936.jsonl` in `%TEMP%\smoke_out_runtime\recordings`. Live store 60/60,
sidecar set byte-identical before/after; live `force_dry.on` mtime unchanged (2026-09-13
15:15:24); `outputs/control/` empty.

**Found by the injection, not fixed:** the same smoke section drives `force_dry` /
`entries_off` / `entries_on` in-process, and `runner.py:310` (`ControlChannel()` — consumes
`outputs/control/` at construction), `:345` (`StatusWriter()`), `:365-369` (`paused.on`,
`entries_off.on`, `force_dry.on`) are all cwd-RELATIVE — both scratch arms wrote
`outputs/force_dry.on` + `outputs/control/` into scratch, so a DoD run from the repo root
rewrites the live sentinels and can swallow a queued operator command. Fails safe in direction.
Carried into the decision sweep as a SAFE lead.
