---
title: "Session 2026-08-27 — SDD 3-day verification, the era-confound instrument defect, and the confounded-everything consequence"
category: source
status: SETTLED
summary: "Four read-only verification tasks over the 3-day commit stream (T1-T4, two defects found and dispatched), the era-confound defect in the veto-quality instrument (fixed a94b5751, hardened 62ab10c0 — after which EVERY veto-quality row reads CONFOUNDED_BASELINE or PARTIAL_OVERLAP pending a live baseline), the suite host-state-dependence discovery, five research folders written, and the control-arm sandbox prototype. §6 ADDENDUM 2026-08-28: CUT #8 EXECUTED — boundary #5 the fee-truth epoch minted under operator adjudication, exec_era 8-ca55e2ba, deploy instant 2026-08-28T03:14:13Z, commits 4e502478+9f0264c6 on origin/main, constants proven in-binary, control-arm MERGED-LIVE (first tagged row = owed poll), QT-1 registered, dry_run TRUE untouched; carries the archived era-4 progression-bar block (the prestige record)"
tags: [sdd, verification, era-confound, gate-efficacy, veto-quality, test-suite, host-state, research, sandbox, control-arm]
sources: 1
source_path: raw/audits/2026-08-27_sdd_verification/
source_date: 2026-08
authors: [session cdb03d59 (Claude Code, liquiditybot_ab)]
ingested: 2026-08-27
---

# Session 2026-08-27 — SDD verification, era confound, confounded-everything

**Session identity:** `cdb03d59-62a4-41ee-8c1c-00feb1307464`, repo
`liquiditybot_ab`, branch `claude/claude-rc-f3heik`. Primary artifacts
snapshotted to `raw/audits/2026-08-27_sdd_verification/` (the session's
master checklist `progress.md`, task briefs/reports 1–4, fix-wave
brief/report, the live gate-efficacy JSON, the final full-suite log).
**All session commits (`a94b5751`, `62ab10c0`) were LOCAL AND UNPUSHED at
filing time (2026-08-27T23:09Z); the push decision is the operator's.**
Everything below is repo-side / sim-side of the paper/real boundary — no
venue truth anywhere in this page ([[concepts/paper-real-boundary]]).

> **RE-STAMP 2026-08-28Z (the 23:09Z filing predates the session's landing —
> read this box before quoting any "at filing" caveat below).** The full
> landing queue executed and **the entire chain is PUSHED to `origin/main`**
> (ancestry verified by `git merge-base --is-ancestor`, 2026-08-28):
> `a94b5751` · `62ab10c0` · `0257fd59` (fix-wave 2: defects #9/#10 + stager
> pins) · `cd84c2aa` (config-audit SAFE batch, 758 keys) · `f17e28b5` (the
> five research folders, **citation-verified**: 19 defects + 19 overreach
> corrected in place, 0 hallucinated sources) · `52315a57` (**T5 synthesis
> DONE** — `docs/quant/2026-08-28_session_synthesis_T5.md`) · `0084c16d`
> (final-review **F1**: admitted-headline vocabulary — §2 addendum) ·
> `22d789ce` (HANDOFF landing). **Final whole-branch review passed and the
> full DoD matrix ran GREEN**, with the corpus lines read per house law:
> `overfit_check` ran on the **REAL live-history corpus, 8220 rows**
> (`outputs/overfit_report.md` stamped 2026-08-27 20:39 −05:00, "Dataset:
> live history (8220 rows)"; no synthetic substitution), **OF-4 plateau
> INERT** (flat surface, 0 entries on the recording) and **OF-5 DSR
> DEFERRED** (26 conviction trades < 30 floor) — degraded honestly, named,
> not failures. New finding post-filing: the **C++ diode's 8 skips are
> PERMANENT on this box under Smart App Control** (SAC blocks locally-built
> unsigned binaries; signed-compiler route exhausted 2026-08-28) — diode
> verification moves to the owed-105 fresh-worktree CI leg or an operator
> SAC decision (T5 §5). §4's gov-fee-1 loose end also closed: re-refereed,
> **STANDS at grade C** (`docs/research/behavioral/README.md:67`).

Method: subagent-driven verification — read-only investigator agents per
target, fixes only via separate fix agents carrying the focused-fix
protocol by path ([[concepts/iron-law-of-repair]]), each fix re-reviewed
by a fresh agent, the T4 report itself adversarially reviewed.

---

## 1. SDD 3-day verification (T1–T4) — the commit stream audited

Scope: the 2026-08-24..08-26 commits plus one unmerged branch. Verdicts,
each from its own report (`task-N-report.md` in the raw snapshot):

- **T1 — `8a9cc087` (labels schema 93→94, `label_ret_pct`):** code
  VERIFIED CLEAN (77 targeted tests green, mutation-verified, SAFE
  class). **Defect (narrow): the commit message overclaims its own
  verification** — claims "13 new pins" where the diff holds **12**
  (`git show 8a9cc087 -- tests/ | grep -c "^+def test_"` = 12, all in
  `tests/test_label_ret_persistence.py`), and lists
  `tests/test_migrate_history.py` which has **zero diff** (only
  `tests/test_history_migration.py` changed, 3 lines — two
  similarly-named files confused). History is pushed, not amended; the
  correction of record is the HANDOFF RECENTLY SETTLED row (fix-wave
  I3). Same class as [[synthesis/documentation-drift-register]]'s
  shipped-claim rows: a false tally in a commit message outlives the
  code.
- **T2 — `ca55e2ba` (boundary-#5 fee-truth stager):** VERIFIED_CLEAN
  (40+321 tests green); inertness confirmed — the stager stages, nothing
  applies. Minors: a boundary **#5/#6 numbering drift** (two 08-22
  HANDOFF prose lines said "#6" against three code-level sources saying
  "#5"; reconciled to **#5** by fix-wave I2 — the number
  [[synthesis/comparability-boundaries]] already uses), and the stager
  has no persisted regression test (queued).
- **T3 — `5e785c16` (veto counters / gate-efficacy by_code):** **DEFECT
  (Important) — the era confound**, §2 below. Arithmetic and pending
  logic clean (81 tests green); the defect is in what the numbers were
  compared against. Fixed `a94b5751`, re-review APPROVED (spec 5/5,
  mutation independently re-verified).
- **T4 — unmerged branch `claude/remote-control-hds2hd` (tip
  `6f8b6315`):** VERIFIED_CLEAN **in itself** — two independent fresh
  worktrees agree exactly (`2 failed, 4085 passed, 9 skipped, 1 error`,
  both runs); TRIALS-1/OF-5/OF-3 runtime-verified; SAFE class; merge
  decision → operator. **The 3 reds reproduce byte-identically on bare
  main `5e785c16`** — pre-existing main defects, not the branch's:
  **#9** (minor): `tests/test_trading_dashboard.py`'s `_aux_emitted()`
  fixture never rebinds `gc_pusher.VETO_SCRIPT`/`_veto_cache`, so the
  new veto subprocess (from `5e785c16` itself) shells out for real and
  finds no audit history on a fresh checkout; **#10** (IMPORTANT):
  `scripts/pc_supervisor.py:104` `_VAULT_GUARD_STAMP` is absent from
  `tests/conftest.py`'s `_REDIRECTED_PATH_ATTRS` — a **real
  production-outputs write** from a test, the **10th leak-class
  instance** (the branch's own `3ec6dbbc` fixed the 9th), caught by the
  conftest production-outputs tripwire — in a fresh worktree only (§3).
  Both queued for the post-fix-wave fixer — **[RE-STAMP: both FIXED and
  pushed in `0257fd59`** (stamp registered in `_REDIRECTED_PATH_ATTRS`,
  veto fixture rebound, stager pinned; fresh-worktree acceptance green;
  the order flake #8 triple-checked unreproducible under serial scope and
  deliberately left)]. Also flagged: the LOCAL
  branch ref is stale (`69088a5d`; the tip exists only on
  `origin/claude/remote-control-hds2hd`).
- **Adversarial review of the T4 report** (operator-invoked): verdict
  BLOCK-as-is / branch-clean core STANDS. Promoted **C1 = the
  host-state-dependence finding** (§3). Also: the report's
  ff/zero-conflict merge claim went STALE the moment `a94b5751` landed
  (re-derive at merge time), and the fresh-worktree suites were verified
  to have spawned only the report-only vault guard (no push risk).
- **T5 (goal-alignment synthesis): NOT DONE at filing time** — queued in
  the session's execution DAG behind the research-folder commit; its
  input (the suite-outcome reconciliation) is §3. **[RE-STAMP: DONE —
  `docs/quant/2026-08-28_session_synthesis_T5.md` (`52315a57`, pushed).
  Its verdict: on the only axis the moratorium permits movement —
  measurement fidelity and staged remedies — YES, materially; the
  strategy axis is unchanged and waits at the prestige gate
  ([[synthesis/progression-bar]]).]

---

## 2. The era-confound instrument defect — and the confounded-everything consequence

The session's central finding; the full contradiction-register treatment
is on [[synthesis/open-contradictions-register]] (the 2026-08-15
gate-selects-against-itself entry, 2026-08-27 additions), which this
page summarizes and extends with the hardened-guard consequence.

**The defect.** `5e785c16` (08-26) published SZ-021 as **"ANTI-SELECTIVE
at significance"** — vetoed candidates won 0.509 [0.439, 0.580] vs
baseline 0.265 [0.192, 0.354], n=2,032 (n_eff 189) — into HANDOFF REG-6
and the Grafana metric `liquiditybot_veto_cf_rate`. T3 measured the
baseline itself: **every blank-`disp` baseline row is a 2026-07-20
migration backfill, 0 rows written since**, label_era mix **84.1%
`legacy` / 15.9% `exit_sim` / 0% `triple_barrier*`** — while SZ-021's
own rows are **100% `triple_barrier_h432`. Zero label-era overlap** with
the population it was scored against. Re-derived against a
**contemporaneous same-window comparator** (everything else the pipeline
saw in SZ-021's active window, `signal_ts` 2026-08-19T22:10 →
2026-08-25T01:35, n=1,772, rate 0.440 [0.369, 0.514]): SZ-021's interval
**overlaps** — "significant" does not survive. **Direction UNRESOLVED,
not refuted**: neither the frozen-baseline verdict nor a clean
"not significant" is established, because the comparator was the wrong
population ([[concepts/pooled-populations]], [[concepts/label-era]]).

**Fix 1 — `a94b5751`** ("gate_efficacy_report refuses significance
across disjoint label_era"): `_row_era` + `ERA_OVERLAP_FLOOR` (5%,
policy floor, not fitted) + a `comparison` field reading
`CONFOUNDED_BASELINE` instead of asserting `anti_selective`/`selective`;
rates/CIs stay printed, unsuppressed. Injection-tested both directions,
mutation-verified (3 pins). A user-invoked `/code-review` on it returned
**12 findings (F1–F12)** from three finders — the strongest: the overlap
test was one-directional SET membership (a single contaminating baseline
row bought full credit), and the admitted-vs-baseline **headline** was
entirely unguarded (same confound species).

**Fix 2 — `62ab10c0`** (the fix-wave, C1-C7 + I1-I5, focused-fix
protocol, report in the raw snapshot): membership → **WEIGHTED
(histogram-intersection) overlap** + a 50% majority line
(`ERA_OVERLAP_MAJORITY`; `PARTIAL_OVERLAP` between the floors); the
headline guarded (C2); ambiguous fallback rows → UNKNOWN rather than
guessed — the live corpus carries no per-row horizon column to
disambiguate with (C3); honest-null vs n_eff-uncomputable split (C4);
`gc_pusher` exports `comparison`/`era_overlap` so the glass can tell
CONFOUNDED from not-significant (C5); the dashboard description that
still asserted SZ-021 harm as fact — baked into the checked-in Grafana
JSON — corrected (C6); doc-truth corrections C7/I2/I3.

**The hardened-guard consequence (the surprise, and the reason every
veto row is now confounded).** Live re-run under the weighted guard
(`ger_live_20260827T2248Z.json` in the raw snapshot, read
2026-08-27T22:48:57Z): **every `by_code` row AND the
admitted-vs-baseline headline read `CONFOUNDED_BASELINE` or
`PARTIAL_OVERLAP` — none clears to COMPARABLE.** Including **SZ-030**,
previously the one clean "selective, earns its keep" read: membership
overlap said 0.685, weighted overlap is **0.1586608442503639** →
`PARTIAL_OVERLAP`. Full row: SZ-021 0.0 CONFOUNDED · SZ-023 0.0082
CONFOUNDED · SZ-030 / SZ-046 / SZ-020 / SZ-050 0.1587 PARTIAL · SZ-045
0.0842 PARTIAL · SZ-022 0.0737 PARTIAL · headline 0.1587 PARTIAL.
Mechanism, and why this is the guard working rather than over-tuned: the
baseline's own composition **caps every code's maximum possible weighted
overlap near 0.159** (its `exit_sim` share) unless a code is itself
majority-`legacy` — which no currently active veto code is. **The frozen
2026-07-20 baseline cannot honestly vouch for ANY of today's corpus**;
the report now says so instead of printing partial confidence. The
structural remedy — a live/contemporaneous baseline — is **owed 104**
([[synthesis/owed-measurements]]); the fix-wave explicitly declared it
out of scope, and §5's sandbox prototypes it.

**Fix 3 — `0084c16d` (post-filing, final-review F1): the admitted
headline gets its own vocabulary.** The admitted-vs-baseline headline
had been calling `_comparison` with `is_veto=True` (a lie to the
parameter, needed to reach the confound states), leaking the VETO
significance tokens **inverted** onto a TAKEN sample — an admitted
cohort at 0.90 vs baseline 0.10, same era, exported `anti_selective`,
the harm word for brilliant selection. `_comparison` gains a
keyword-only `admitted=` flag; the admitted headline now speaks
**`selects_winners` / `adverse_selection`**; the veto tokens are
untouched. **Currency note for every enumeration of the comparison
vocabulary:** the state set is now {`selects_winners`,
`adverse_selection`} on the admitted side and {`anti_selective`,
`selective`, not-significant} on the veto side, both behind
{`CONFOUNDED_BASELINE`, `PARTIAL_OVERLAP`, `UNKNOWN`} — any enumeration
predating `0084c16d` (including this session's own raw snapshot,
dated-correct as filed) lacks the two admitted tokens.

**Verification state:** full suite on the live repo at `62ab10c0`:
**4060 passed / 0 failed / 9 skipped** (540.96s, log stamped
2026-08-27T23:01Z; +11 collected over `a94b5751`'s 4058 = exactly the
wave's new tests, double-derived). The earlier post-`a94b5751` full run
was 4048/1/9 — the 1 red is the **pre-existing order-dependent flake**
`test_fee_reconciliation::test_credential_less_environment_skips_silently`
(passes in isolation; audit-chain state bleed across a full run; minor
#8, deliberately unfixed in this wave). Both greens are live-repo greens
and carry §3's caveat.

---

## 3. The suite host-state-dependence discovery

Three full-suite outcomes, same day, same code families, all
reproducible — and all "true":

| run | corpus | result |
|---|---|---|
| live repo at `62ab10c0` | long-running bot's host state | 4060 passed / 0 failed / 9 skipped |
| fresh worktree at `6f8b6315` (×2, independent) | clean checkout | 2 failed / 4085 passed / 9 skipped / 1 error |
| fresh worktree at bare main `5e785c16` | clean checkout | same 3 reds |

**A suite green is a claim about (code × host state), not about code.**
The live repo passes tests a fresh checkout fails because host state
masks the defects: the running bot's **real audit history** feeds the
veto-quality subprocess that fixture #9 fails to stub, and
`outputs/.vault_guard_stamp` **already existed** (stamped 15:49 that day
by the running bot) so `_stamp_due` was not due and #10's real
production-outputs write never fired there. Conversely the live repo
shows an order-dependent flake (minor #8) the fresh runs don't.
**Live-repo greens overstate** — the adversarial reviewer's C1, promoted
to the session's method-level finding. Filed as its own defect class:
[[concepts/host-state-dependent-green]]. Remedy adopted into the
adoption shortlist (§4, llm_test_suites): a **fresh-worktree CI leg** —
owed 105. One honesty note the T4 report carries on its face: a third,
self-polluted worktree once read `4 failed, 4083 passed`, could not be
re-captured, and is recorded [UNKNOWN, not re-established] rather than
silently dropped.

---

## 4. Five research folders (written and reviewed; UNTRACKED at filing)

`docs/research/` in the repo gained **five folders, 35 files**, all
literature passes graded against house bars, all SAFE class
(measurement plane), model freeze intact. **Uncommitted at filing time**
(the session's DAG batches them into one commit after the fix-wave);
cite by path with that caveat until landed. **[RE-STAMP: LANDED —
committed `f17e28b5`, pushed to `origin/main`; the caveat is retired.
Before the commit, a citation-verification pass live-searched all five
folders: 19 defects + 19 overreach corrected in place, 0 hallucinated
sources, conduct review PASS (HANDOFF RECENTLY SETTLED row). Grade
movement of record (from `README.md`'s grade table, the committed
authority): **sent-ret-1 regraded "B in-sample; D at our horizon"**,
**sent-ret-2 to C**, both AMENDED both-sides — and the derived
platform-sentiment feature row is **D-grade at our horizon**
(best-replicated effects live at ≤15 min, `06_sanity_check_spec.md:340`);
**gov-liq-1 carries amendments** (`02_exchange_economics.md:63`,
grade C).]

- **`behavioral/`** (7 files) — who loses / who harvests: 45 claims, 7
  flagships AMENDED both-sides by its own refuter pass, a 20-test sanity
  spec, **9 pre-registered feature candidates marked FORBIDDEN to
  implement** until boundary adjudication — DOCKET MATERIAL for the next
  execution-era boundary, on its face. Compliance gate PASS. Open loose
  end: the gov-fee-1 claim's referee verdict came back
  `reason="placeholder"` — a real re-referee was dispatched, outcome not
  recorded at filing. Cross-linked from [[concepts/who-loses-to-us]],
  [[concepts/behavioral-isomorphism]], [[entities/thales-engine]].
- **`llm_economics/`** (5 files) — 4/4 papers FOUND (03 abstract-only,
  flagged); graded against era-4 pre-registration, OF-1..7, effective-n,
  POWER-2 cost tolerance. New SAFE adoptables: an **agent-spend ledger**
  and a **regime-stratified cohort report**.
- **`llm_linting/`** (7 files) — 5/5 FOUND; top-3 adoptables:
  vault_guard **raw-vs-rendered hidden-text diff**, **doc_cite_lint**,
  **verdict_screen** (sycophantic-positive direction).
- **`llm_test_suites/`** (8 files) — 6/6 FOUND, mapped onto this
  session's five measured suite defects (host-state greens, stamp leak,
  order flake, zero-coverage paths, mutation-kill standard); top-3
  adoptions: **fresh-worktree CI leg**, **coverage-gap report**,
  **order-shuffle leg**. House rule stated on its face: generated tests
  are accepted only with mutation-kill evidence.
- **`token_efficiency/`** (8 files) — 5 techniques + harvest survey +
  `07_implementation_plan.md` (ranked injections); measured local
  baselines: rtk 99% filter rate / 125.6M tokens saved, 33.5KB
  always-loaded instruction files, ~80+ skill-catalog listings. No paper
  percentage adopted as a local expectation — every plan item carries
  its own before/after measurement.

*(The operator's filing request said "the 4 research folders" and named
five; five exist on disk — recorded as observed.)*

---

## 5. The control-arm sandbox — rationale

Operator latitude grant, STREAM 11: an **isolated worktree** at
`c:\Users\haird\Documents\liquiditybot\sandbox_control_arm`, branch
`sandbox/control-arm-shadow-weights` (verified at filing: branch
current, based on `a94b5751`; working-tree deltas in `ml/history.py`,
`scripts/migrate_history.py`, 4 test files). Two components:

1. **Control-arm stratification tag** — metadata-only: tag a stratum of
   live candidates as a permanent, era-matched control arm, so the
   gate-efficacy baseline is **contemporaneous forever**. This is the
   structural cure for §2's frozen-baseline confound **at the root** —
   the remedy both the original CAVEAT and the fix-wave named but
   declared out of their scope.
2. **Shadow gate-weight learner** — sidecar, **never applied** to
   decisions.

**Why a sandbox:** prototyping in an isolated worktree on a
shadow-named branch keeps the era-4 accrual moratorium intact by
construction — nothing can touch the live decision path, and the branch
name declares the intent. **NOT merged without operator adjudication**
(the stratification tag touches row metadata at write time, so its
admission class must be adjudicated, not assumed SAFE). A stale locked
agent-worktree from a failed isolation attempt was cleaned
(unlock+remove+prune, branch deleted). Prototype status: RUNNING at
filing — a work-in-progress, not a claim; nothing here is evidence yet.

---

## 6. ADDENDUM 2026-08-28 — CUT #8 EXECUTED: the fee-truth epoch (boundary #5), the prestige fired

**Second addendum, same session (`cdb03d59`), after the landing re-stamp
above.** Operator adjudication 2026-08-27 ("both: full bundle") executed
2026-08-28: **boundary #5 is minted as cut #8**, `exec_era` =
**`8-ca55e2ba`** (`core/fill_ledger.py:78`; naming judgment recorded in
the constant's comment — a commit cannot contain its own hash, so the
anchor is `ca55e2ba`, the package-DEFINING commit, not the apply commit).
Authoritative row + full mechanism:
[[synthesis/comparability-boundaries]] table row 8.

- **Instant = 2026-08-28T03:14:13Z** (deploy: config applied 02:34:42Z;
  stop 03:11:58Z → STOPPED 03:12:13Z → runner PID 9108 up 03:14:13Z,
  RUNNING observed 03:14:51Z). The era begins at the deploy because a
  running process keeps its init-read fee constants.
- **Commits `4e502478`** (sandbox merge in + stager `--apply` fee-truth
  40/80 bps + era mint — exec_era bump IN THE SAME COMMIT, cut #7's
  late-bump debt not repeated; 7 suite pins re-baselined, 2 structural,
  none widened) **+ `9f0264c6`** (deploy-instant stamp), both verified on
  `origin/main`.
- **Constants proven IN-BINARY, not just in-repo** (the binary-sha lesson
  applied prospectively): startup log `fees=40/80bps`, derived bar
  `0.833`. First 162 post-cut cycles: **SZ-023 ×42** — the book quieting
  exactly as the adjudication predicted (bar 0.6902 → 0.8335; probes stop
  clearing by construction). **`dry_run` TRUE untouched.**
- **Control-arm MERGED-LIVE** (§5's sandbox, landed as `7b19181d` tag +
  `d64ad030` shadow learner within the bundle): schema **94→95**
  write-path live. **First live tagged row NOT yet observed** — the label
  queue was quiet at deploy; the history rotation was rehearsed on a real
  copy, **18,657 rows preserved**. An owed poll, not a claim
  ([[synthesis/owed-measurements]] 104).
- **QT-1, new docket item** (owed 106): `scripts/quant_trials.py`
  `TIER_CFG["est_fee_bps"]` = **40**, unmirrored vs deployed **80**.
  Measured before deciding (200×1200, seed 7, runtime-proven
  config-independent — 0 config.json reads): as-is G1–G5 pass
  byte-identical to pre-cut; **mirroring the cut FAILS G5 capture 0.574
  vs baseline 0.606** and collapses G1's margin to 4.84% vs cap 4.91% —
  the #103 T6 shape. Left UNCHANGED, nothing widened; a conscious
  re-baseline adjudication is owed, and until it lands **G1–G5 greens
  may not be cited as deployed-geometry evidence.**

### Era-4 progression-bar cycle — ARCHIVED AS-OF block (prestige record)

Per [[synthesis/progression-bar]]'s own update contract ("when a prestige
fires, archive the cycle's AS-OF block into the boundary's dated doc and
reset the page"), the era-4 cycle's final AS-OF block moves here verbatim
in substance:

> **Cycle: era-4, READ OUT at n=54** (this page carries the readout
> chain). End-game reached: the prestige bundle (boundary #5 fee-truth
> cut + control-arm tag; ALGO-5 / asset discipline / CONC-1 deferred to
> their own adjudications) staged, adjudicated 2026-08-27, **walked
> through 2026-08-28T03:14:13Z**. Final session movement (verified-
> shipped, [K]): era-confound refusal + hardened weighted guard
> (`a94b5751`, `62ab10c0`); four main-inherited suite defects
> (`0257fd59`); config audit (758 keys, 0 FATAL) + SAFE fixes; five
> graded research folders (`f17e28b5`, citation-verified, 19+19
> corrections); control-arm + shadow-learner sandbox → merged at the
> boundary; T5 synthesis (`52315a57`); F1 vocabulary fix (`0084c16d`);
> full DoD GREEN with corpus lines read
> (overfit on the REAL 8220-row corpus, OF-4 inert / OF-5 deferred);
> SAC/diode 8-skips-permanent finding. Known denominator at close:
> ~15 docket items, ~8 ledger backlog, ~24 ranked adoptables, 105 owed
> measurements. The chain `a94b5751`→`22d789ce` pushed; the boundary
> commits `4e502478`+`9f0264c6` closed the cycle.

The progression bar itself is now RESET to the era-`8-ca55e2ba` baseline
— new 0% = this code as measured at the boundary.

## Still open at filing (the landing queue, not claims)

T5 goal-alignment synthesis · post-fix-wave fixer (#9, #10, triaged
minors incl. the order flake #8) · one commit for the research folders ·
final whole-branch review over `5e785c16..HEAD` · full DoD matrix ·
HANDOFF session update · **push decision = OPERATOR** · Grafana
reconfig/makeover (stream 7, separate task). Owed items minted by this
filing: **104** (live baseline) and **105** (fresh-worktree suite leg +
#9/#10) on [[synthesis/owed-measurements]].

**[RE-STAMP 2026-08-28Z: every queue item above except the Grafana
makeover EXECUTED and PUSHED — see the top callout for the commit map,
DoD corpus lines, and the SAC/diode 8-skip finding. Owed-item state
after landing: 104 still OPEN (the sandbox control-arm is BUILT at
`11eafb97`+`f0f3c370` — deterministic 5% stratification tag, schema
94→95, shadow learner — but its base is `a94b5751`: REBASE + FULL RETEST
required before any merge, and the merge is an operator adjudication);
105's #9/#10 leg CLOSED by `0257fd59`, the standing fresh-worktree CI
leg still OPEN — and it is now also the diode's only verification home
on this box.]**

## Related
[[synthesis/open-contradictions-register]] ·
[[concepts/host-state-dependent-green]] · [[concepts/false-green]] ·
[[concepts/label-era]] · [[concepts/pooled-populations]] ·
[[concepts/iron-law-of-repair]] · [[concepts/the-method]] ·
[[sources/session-20260826-why-losing-deep-dive]] ·
[[sources/test-suite-outputs-contamination]]
