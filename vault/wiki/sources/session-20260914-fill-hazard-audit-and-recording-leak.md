---
title: "Session 2026-09-14 — the fill-hazard report's corpus was mostly fixtures, its statistics were not, and the test that should have caught it had exempted itself"
category: source
status: PROVISIONAL
summary: "A 34-agent instrument audit of the untracked 2026-09-14 fill-hazard L1 report (5 lanes, 3 adversarial lenses per finding, 9 judged / 9 survived / 0 refuted) found every shipped number reproduces and the NO is arithmetically correct — but the corpus headline counts QA smoke fixtures, because scripts/smoke_test.py builds a real BotRunner on the production config and runner.py records feeds into the live outputs/recordings ring, evicting a real session per boot (46 of 60 retained sidecars were fixtures at the 23:06Z read). tests/test_qa_isolation.py had EXEMPTED system.recording_dir on a written claim the BotRunner call falsifies. FIXED same session (redirect, e2e pin), proven by mutation pair + injection on the real smoke section; live store byte-identical. The audit also established by ablation that NO fixture data reaches any statistic (removing all 46 mock sessions leaves every row byte-identical; removing one real session moves everything), that the YES arm is bounded ~1.46% below its 10% threshold by the fill rate before any data is read (so the NO BOUNDS the endpoint misstatement rather than testing shape, beside LR p<0.05 in 5 of 7 buckets), that d_bar's overnight ÷1.59 is 100.00% one PAXG tape's sigma moving through an unweighted 1/sigma mean, and that consecutive reports are 97.88% bit-identical episodes with a HARDCODED non-independence disclosure naming the wrong pair. PROVISIONAL until the fix commit lands with the DoD matrix green; the fixture files themselves are an operator decision, undeleted."
tags: [fill-hazard, instrument-audit, qa-isolation, recording-store, smoke-test, fixtures, mutation-verified, injection-verified, effective-n, hazard-verdict, near-touch, d_bar, handoff-decay]
sources: 1
updated: 2026-09-14
---

# Session 2026-09-14 — the fill-hazard audit and the recording leak

> **CORRECTION 2026-09-15T01:47Z (both sides visible; nothing below deleted).** A
> red-team panel on the recording-leak fix found what the 34-agent audit, this page
> and the same-day report addendum all missed: **the fill-hazard L1 instrument
> grades a sim that has been OFF since boundary #4** (`aeeaae36`, 2026-08-10).
> Verified by grep: `config.json:399 passive_hazard_with_book: false`; the only
> `_passive_poll_prob` call (`order_manager.py:1363`) is gated on it (`:1360`); live
> dry-run fills use `_sim_maker_cross` (`:1340`), byte-equivalent to the report's
> event rule — the fit is the sim measuring itself, and `config.json:400`'s `_doc`
> says so. So §2 F3 ("the YES arm could not fire") is arithmetic about a retired
> comparator; §5's "the NO is a bound…" is a bound on nothing deployed; the L2
> plan's premise predates the boundary by 10 days and is MOOT unless re-posed
> against `_sim_maker_cross`. The panel added three CRITICAL/BLOCKING instrument
> defects, each verified against the report text: effective EVENTS 4-6 per bucket
> under any clustered n (< `E_MIN` 10 → every row DEFERRED); the fit samples REST
> books written only when the WS book is >3.5 s stale; "T=5 polls" is minutes of
> wall clock, not 25 s. **What stands:** §2 F1/F2/F4/F5/F6/F7, §3's ablation
> (no fixture data in the statistics), §4 (the fix, now local commit `baad9754`
> amended once — its "fails safe in direction" claim about the sentinel leak was
> the WRONG SIGN: a smoke run deletes an operator's `entries_off.on`/`paused.on`
> and drains queued `flatten_all`/`stop` unrun). The-method gains **#21**;
> owed **116**. Windows Update rebooted the box at 00:43-00:46Z the same night;
> the BootTrigger revival relaunched the runner in ~70 s (measured, positive).

Raw: `raw/audits/2026-09-14_fill_hazard_l1_instrument_audit.md` (the synthesis, every
number, the orchestrator's corroboration and the fix's three-way proof).
Repo: `docs/quant/2026-09-14_fill_hazard_l1.md` (untracked at audit time),
`scripts/fill_hazard_report.py`, `scripts/smoke_test.py`, `tests/test_qa_isolation.py`,
`runner.py:219-251`. Repo state at filing: `main` = `d6957321`; runner pid of the 17:06
local relaunch, RUNNING / DRY_RUN, untouched by any of this.

All timestamps UTC unless marked local. Every number is as-of its stated read time.
Re-derive, never recall — the recording store is a FIFO ring that moves every boot.

Related: [[concepts/the-method]] (recurrences 19, 20) · [[synthesis/owed-measurements]]
(112-115) · [[synthesis/comparability-boundaries]] (the no-history blind spot this
ring shares with `fills.csv`) · [[concepts/false-green]] · [[concepts/observational-equivalence]]
(a fixture-dominated ring and a thin market are indistinguishable from the report's
headline) · [[sources/session-20260913-resume-storm-and-hook]] (the previous session;
its "instrument scope" recurrence 17 is the mirror of this page's 20).

**Claim status: PROVISIONAL (rule 21).** Discharge condition: the recording-leak fix
commit lands on `origin/main` with the full definition-of-done matrix green, at which
point §4 becomes SETTLED; §1-3 and §5 are settled by the audit's own verification and
would not move.

---

## 1. Why the report earned an audit before a commit

The 09-14 run was the tenth in a tracked daily-generated series (nine prior, all
committed; convention settled `644baee2`). Its diff against 09-13 showed four things the
report's own "Evidence limits" did not: `d_bar` ÷1.59 UNIFORMLY across all seven distance
buckets (a normalizer, not a market); symbol-tapes 294 → 282 with the window start
unchanged and frames +910; the 15 bps bucket's near-touch flag n → y; EXACTLY 5 tapes
fitted both days. A report-only artifact ending in "Recommend closing L2" — a
label-geometry decision, COHORT-RESETTING under era-9 — with an undisclosed normalizer
shift is the-method's first suspect.

## 2. What survived three adversarial lenses (9 of 9)

Full statements, line citations and verifier notes are in the raw record. One line each:

- **F1 — the leak.** `qa_redirect_paths` never redirected `system.recording_dir`;
  `smoke_test.py:1416` builds a real `BotRunner`; `runner.py:219-251` records. Ring at
  `retain_files` 60 = 60, 46 fixtures. **SAFE; fixed (§4).**
- **F2 — the headline counts fixtures** (by session ~78%, by tape ~72%, by FRAME ~1%);
  "~143.4 polls per tape" understates real depth ~3.5×; line 44 mis-attributes the
  exclusions. What is missing is the CAUSE, not the magnitude.
- **F3 — the YES arm could not fire.** Max misstatement over ALL shapes ≈ 1.46% vs the 10%
  threshold at this fill rate (YES needs F(T) ≈ 24% vs 3.6% observed); the `powered` gate
  tests counts only. On the REAL fitted shape the poll-1 misstatement is **11.18%** — the
  report samples only t=T. **Information, not an action**: adding an attainability test
  would route a decisive analytic negative into DEFERRED forever.
- **F4 — `d_bar` is an unweighted mean of 1/σ**; one PAXG tape (σ 2.1583 → 7.1152)
  carried ~53% of the divisor; the shift is **100.00% that tape**, mutation-verified
  (restore its σ → the 09-13 column reproduces). Verdict-neutral on both observed runs;
  verdict-path by construction.
- **F5 — consecutive runs are near-duplicates**: identical five fitted tapes, **97.88%
  bit-identical episodes**, and the "7 of 9 days" disclosure is a **hardcoded literal**
  (`:507-511`). The 681 new frames would FAIL the gap guard standalone and pass only by
  pooling — the per-tape median is blind to a contiguous out-of-cadence tail.
- **F6 — `near-touch` gates the verdict** (`_overall` :451-463 filters to it first;
  threshold 2.0 from `core/fill_calibration.py:52`), undisclosed and unpinned; the 15 bps
  flip was INERT by exhaustive enumeration (127 subsets → one verdict) and fails safe.
- **F7 — HANDOFF:181 "(untracked)" decayed** (tracked since `644baee2`); the convention
  was never filed as SETTLED; the remedy must ATTACH, not delete (register-decay clause).

## 3. What was refuted, and why the refutations matter more than the findings

- **`affects_verdict` was asserted on five findings and is FALSE on all five — by
  ABLATION, not argument.** Remove all 46 mock sessions in-process: every bucket row
  byte-identical, NO/XV-050. Remove ONE real fitted session: episodes 10764 → 9442,
  h_const moves. The gap guard `continue`s a fixture BEFORE episode synthesis (fixture
  median gap 0.018-0.186 s vs floor 1.667 s). **The shipped statistics contain zero
  fixture data.** The instrument is right about the market and wrong about itself.
- **"Mostly synthetic" was a cherry-picked denominator** — CLAUDE.md reading-discipline
  (a), committed by a finding auditing an instrument for the same error.
- **The 294 → 282 tape delta is UNATTRIBUTABLE** from the present store (`outputs/`
  has no history; the lane's attribution was withdrawn by its own verifier: 4×7 = 28 ≠ 12).
- **Open, unadjudicated: why the dominant tape's σ tripled.** Two independent replays
  reproduced the shipped σ and disagree on cause (instrument regime change at a bimodal
  median gap that flipped the subsample stride 12 → 6, vs a real vol jump). Both agree the
  original author's fixed-index-stride control is invalid. `scripts/calibrate_fills.py:131-188`
  has never been audited in its own right — and the LEVEL calibration shares it with no
  admission guard. → owed.

## 4. The fix, and its proof (PROVISIONAL until committed)

Redirect, not disable — `main.py:725` reads `record_feeds` for serial-feed mode.
`qa_redirect_paths` now sets `system.recording_dir`; the key moved from `_EXEMPT` (its
false justification replaced by the record of why it was false) to `_KNOWN_LEAK_KEYS`; the
docstring renumbered to TEN instances (the singletons were already the ninth); a new
end-to-end pin builds a real `BotRunner` on the redirected production config with a
duck-typed bot and asserts the sink's PARENT is the redirected directory — which is what
separates "the redirect worked" from "chdir saved us" (every other `BotRunner` test
chdirs to `tmp_path`; that incidental belt is the only reason the pytest suite never
leaked while the smoke script did).

Proof: suite 25 passed · mutation pair (redirect removed → 5 pins red incl. the new one
and both replay-family pins → restored green) · injection on the real
`test_runtime_and_runner()` from a scratch cwd (mutant arm: `session_*.jsonl` in scratch
`outputs/recordings`; fixed arm: none there, one under `%TEMP%\smoke_out_runtime\recordings`)
· live store 60/60 sidecar set byte-identical · live `force_dry.on` mtime unchanged ·
`outputs/control/` empty.

**Found by the injection, carried not fixed:** `runner.py:310` `ControlChannel()`, `:345`
`StatusWriter()`, `:365-369` the three sentinels are cwd-RELATIVE. Both scratch arms wrote
`outputs/force_dry.on` + `outputs/control/` into scratch — from the repo root a DoD run
rewrites the live sentinels and can swallow a queued operator command. Fails safe in
direction. On the decision-sweep docket.

## 5. How to read the nine committed reports now

Two agreeing runs a day apart are close to **one fit seen twice** — the report says this
in principle and understates it in practice. The NO is a **bound on the endpoint
misstatement at the observed fill rate**, not a shape test; its LR column rejects
constancy in most buckets and that is not a contradiction. `d_bar` and near-touch are a
single-tape-fragile verdict-path input whose only reachable transition fails safe. None
of this licenses acting on "close L2".

## 6. Owed / not done

The generator was never re-run end to end (the RENDERED report was never reproduced);
effective-n WITHIN a run is unmeasured (MIN_EPISODES=80 / E_MIN=10 are nominal over
~10,744 clustered episodes from five tapes — the one channel that could move NO →
DEFERRED); `calibrate_fills.py` σ estimator adjudication; LEVEL calibration's fixture
immunity; 18 lane findings never adversarially checked (the cap); the exclusion filter
injection-tested but never mutation-tested; the 46 fixture files in the ring (operator:
delete, or let the FIFO age them out — each new real boot evicts the oldest by mtime).

## 7. The two recurrences this adds to the-method

(a) **An exemption comment disarmed the test that existed to catch its class** — the
generic walk SAW `system.recording_dir` under `outputs/` and was told to look away by a
sentence that was false when written. A comment cannot fail; this one had, inside the file
that says so. (b) **An instrument correct in its estimate and wrong in its
self-description** — every statistic clean, the corpus headline and one limits number
contaminated, and the report's own re-open condition unreachable while it stood.
