# Program history and priorities (through 2026-08-15)

## What this is

A single operator-facing synthesis of the liquiditybot program from
**2026-08-02T01:42:22Z** through **2026-08-15T18:38:35.755Z**. It is built from
**13 Claude Code compaction summaries across two sessions** —
`63d8f842-8108-448c-b2d9-fa9a4c8a2da4.jsonl` (the MAIN session, files 03–13) and
`4b5e9197-4dda-4d98-afe7-5273ee88e65d.jsonl` (the WORKTREE session
`liquidity-bot-isolation-2bd01a`, files 01–02) — read through three faithful
structured extracts, plus the two live docket files
(`2026-08-15_red_team_docket_f756676e.md`, `2026-08-15_docket_dispositions.md`)
and the repo's binding `CLAUDE.md`.

This is a **decision document**, not an archive. Section 4 is the point of it.

### The one rule this document follows

Every number carries a tag:

- **[ASSERTED]** — the record states it. It has *not* been re-verified here. The
  compaction summaries themselves were extraction-only; the extracts say so in
  as many words ("Extraction only — nothing below has been verified against
  code, data, git, or the vault").
- **[VERIFIED]** — re-derived against live code or data during the **2026-08-15
  docket verification pass**, in which an independent agent re-checked each
  objection against LIVE code under instructions to be adversarial toward the
  objection *and* toward the author.

Where two records disagree, **both readings are given and neither is resolved**
(Section 6). Where a claim was retracted, the retraction is recorded next to the
claim. Commit SHAs, `file:line` references, and operator quotes are verbatim.

---

## 1. The arc, in phases

### Phase 1 — The horizon migration (2026-08-02)
**Defining question: is the holding horizon the lever?**

*Believed at the start:* the bot's flat alpha was a signal-quality problem.

*What changed it:* a cost-to-volatility measurement. cost/σ = **0.82**
[ASSERTED] — the round-trip cost was nearly the size of the bar's own move.
A non-parametric bootstrap (`scripts/horizon_bootstrap.py`, seed 7, commit
`631fceeb`) showed break-even selection improving monotonically with horizon:
6 bars 19.5% [16.0, 23.1] → 96 bars 56.9% [55.2, 58.6], top-decile net +0.220% →
+0.913% [all ASSERTED]. Monte Carlo P(monotone) = **0.986**, endpoints disjoint
[ASSERTED].

*Operator decision:* **"1.5 day swing"** — which drove the six-knob 432-bar
migration: `ml.label_max_bars` 24 → **432**, `profit_taking.time_stop.max_bars_no_progress`
36 → **480**, `ml.multi_horizon.horizons_bars` [6,12,24] → **[108,216,432]**,
`budget.burst_hours` 2.0 → **24.0**, `budget.tokens_per_day` 15 → **5.0**, new
`system.lock_progress_max_stall_sec: 300` [all ASSERTED]. The first attempt went
RED (6 failed) and was **reverted rather than papered over**; the 6th failure was
a real coherence defect.

*Settled:* the horizon migration shipped. **432-bar migration is ON HOLD — do
not retune.** That hold is still in force and is restated in every subsequent
compaction summary.

*Debt created that is still being paid:* this migration minted the era
`triple_barrier_h432` and retired `triple_barrier`. Two years of instruments
keyed on the old literal. `gate_truth_report.py:194` still filters
`label_era == "triple_barrier"` today [VERIFIED] — see OBJ-11.

---

### Phase 2 — "Is the paper P&L trustworthy at all?" (2026-08-02)
**Defining question: are the numbers we are reasoning about real?**

*Believed at the start:* the strategy had negative gross expectancy of
**−1.3244%** mean gross [ASSERTED].

*What changed it:* the percentile dump showed **11 trades at exactly −18.392%**,
**66% of losses** [ASSERTED]. Deduplicating by **fill pattern rather than
position_id** revealed **one pattern appearing 16×**; deduplicated mean gross
**−0.1336%** — a **10× correction** [ASSERTED]. The dumped position read
`reason=stop 1948.26 hit`, fill `1490.645739`, **85 seconds** after entry —
1490.65 being the **global minimum ETH price in the entire file** [ASSERTED].

*Mechanism found:* entry `arrival_ref = 2000.000000` (exactly round = a seeded
placeholder); the stop fill's `arrival_ref = 1491.018493`, fill = ref × (1 − 2.5 bps);
`1490.645739 / 1491.018493 = 0.999750` — **exactly 2.5 bps** [ASSERTED].
**The fill simulator was exonerated**: *"The fill simulator worked correctly; the
reference price it was given was fabricated."*

*Operator directive, verbatim:* **"purge that ETH position from"** then
**"figure out why"**.

*Response:* **quarantined, not deleted** — 16 position_ids / 64 rows to
`outputs/fills.quarantine.csv`, honoring never-delete-learning-data. Clean
numbers: **n=214, mean gross −0.0483%, median +0.0487%, gross win rate 57.5%**
against fees of **0.32–0.67%** [ASSERTED].

*Settled:* the verdict flipped from "no edge, start over" to **near-flat gross
against a fee stack that eats it** — stated at the time as *"Not the 'no edge,
start over' picture I gave earlier."*

*Machinery minted here that still governs:* `scripts/cohort_eval.py` with
**`MIN_COHORT_N = 50`** — *the tool refuses to render a verdict below 50 closes*
[ASSERTED]. This is the single most consequential piece of measurement
infrastructure in the program and it is still the gate everything waits on.

---

### Phase 3 — The "better model" refutation (2026-08-05)
**Defining question: should we start over with a new model, or let this geometry earn its keep?**

The operator asked it directly: *"so should i start again with a new model or
continue to let this geometry earn its keep?"*

Three **independent** measurements answered it, and the answer was neither:

1. **No entry timing signal.** `scripts/random_entry_control.py` — random entries
   scored a mean MFE percentile of **0.516 [0.439, 0.594]** [ASSERTED]. The bot's
   entries were indistinguishable from coin flips against the same forward window.
2. **No surviving bracket geometry.** `scripts/geometry_search.py` ran a
   **48-combo pre-registered** TP/SL/HORIZON grid at Bonferroni **z = 3.26**.
   **NO GEOMETRY SURVIVES** — best **−0.400%**, lower bound **−1.124%** [ASSERTED].
3. **The payoff arithmetic is impossible.** Win rate **57%**, payoff ratio
   **0.56** against **0.75 needed**; break-even win rate `p = (cost + L)/(W + L)`
   is **> 1 — IMPOSSIBLE at every real fee schedule** [ASSERTED]. Cost wedge:
   **25.1%** of winning PT touches label 0 because fees eat the win [ASSERTED].

*Settled — do not re-litigate:* **"better model" is retired as a lever.** The
levers are the cost stack, fewer/longer maker-only trades, and pooling.
Separately, **meta-labeling was RULED OUT** after research found zero independent
peer-reviewed tests and that it has *never* been tested on a losing primary — it
was recommended and **retracted twice** before being banned. *Never re-propose.*

*Also settled here:* **XV-021** — measured passive fill probability
**0.048 [0.046, 0.050]** against a configured **0.45**: the simulator was **9×
flattering**. `order_manager.sim_fill.passive_base_prob` corrected 0.45 → 0.048
[ASSERTED]. **XV-022**: the `exp(-d_bar)` form is misspecified, band
**[0.048, 0.082]** — still owed.

*Governance minted here:* **rule 12, operator verbatim** — *"From now on the
corpus's Wiki is the truth and evrything that is determined correct or has been
determined correct needs to be injected into the corpuses wiki"*.

---

### Phase 4 — The false-green / lying-gate doctrine (2026-08-07 → 08-08)
**Defining question: which of our greens were ever evidence?**

This phase produced no strategy finding. It produced something worse and more
useful: the discovery that **the measurement apparatus had been lying, and had
been lying for weeks.**

Specimens, in the order they were caught:

- **The pyright gate had been silently SKIPPED for weeks** [ASSERTED]. The green
  was not evidence. Fixed by in-venv install (**1.1.411**, 0 errors) + a
  **hard-fail RED stage when the tool is missing**.
- **Git Bash `cmd /c "test_windows.bat"`** printed the banner, **exited 0, and
  ran nothing** [ASSERTED]. Lesson filed: **exit codes are not evidence.**
- **The lying pytest gate (CRITICAL).** The battery printed **ALL GREEN over
  "1 failed, 3444 passed"** [ASSERTED]. `start /b /wait "" cmd || (...)` never
  fires — `||` sees `start`'s *launch* success; the child's exit code lives only
  in `ERRORLEVEL`. Fix: `if errorlevel 1`. **Named false-green specimen #5.**
  Aphorism recorded: *"a lying gate survives while it is never the last line of
  defense."*
- **The commit that introduced it was `101f7436` — the commit whose own message
  claimed to "repair two lying gates"** [ASSERTED]. This **retroactively
  invalidates every green battery between `101f7436` and `050421a7`.** The era of
  ALL GREEN requiring a genuine pytest pass begins at **`050421a7`** [ASSERTED].
- **A vacuous test of the assistant's own** — a hedge-convergence test that
  passed on the *buggy* engine because the function under test was pure and never
  mutated state. Proven RED only by loading the parent blob as a scratch module
  (pre-fix: **13 opens / 12 unwinds** [ASSERTED]).
- **The deploy gate self-brick** — commit `64b6fd5` shipped an outputs guard that
  failed `test_goals_ledger_contamination.py`, so `auto_update` refused ALL
  updates *including its own repair*. Same shape as the replay gate self-brick of
  07-21. Fixed in `3f777aa`.
- **The deploy gate rejected external commits twice** — the gate worktree lives
  at `outputs/_update_wt_<pid>`, so a substring filter `if "outputs" not in str(f)`
  excluded **the entire repo** → empty scan. Fixed to path-component exclusion
  (`242568fb`).

*Settled doctrine, still binding:* two-sided proof (prove RED before trusting
GREEN); **AST pins over grep pins** (grep pins match the module's own prose —
proven); **missing tool = RED stage**; **rule 16** — check **BOTH** `BATCH_EXIT`
**and** the literal `ALL GREEN.` marker, because wrapper-exit misreads happened
twice.

---

### Phase 5 — The economics finding (2026-08-09)
**Defining question: strip the repo's vocabulary out and read the numbers cold — what is actually killing this?**

Operator framing, verbatim: *"The real cause was corruption. Let me strip the
repo's vocabulary out and read the numbers cold. Fixing the lint first, then
computing the figure nobody has computed: fix any instances of this. this blocks
the corpus from understanding real truth."* And, on method: *"make sure your
taking an unbiased opinioin and intergrating thoughts into it that conform to
those values in the mindset, geomerty, and corpus. Not making those unbiased
opinions (true data) conform to my bot"*.

**The headline measurement of the entire program** [all ASSERTED]:

| quantity | value |
|---|---|
| Gross P&L before ANY fees | **−$11.66** |
| Fees | **−$382.59** |
| Net all-in | **−$394.25 (−7.89%)** |
| **Fees ÷ \|gross edge\|** | **32.8×** |

Five independent corroborations, none of which share a data path with the above
[all ASSERTED]: OOF AUC **0.43–0.48** (at or below chance); champion Brier
**0.24728** against a **0.25** coin; postmortem MFE median **0.18%** against a
**~0.65%** round-trip cost; **61–62 of 64** features at near-zero importance;
**6** live labels in the current era.

*Enabling correction:* `scripts/breakeven_test.py:126` was counting only
`purpose == "entry"` legs. Changing it to `("entry", "hedge")` moved closed/skipped
from **235/165 → 394/6**, fees from **$59.23 → $374.96**, net from
**−$62.27 → −$387.96**, and **flipped median gross from +0.0505% to −0.0303%**
[ASSERTED]. The assistant's *first* verification of this flip was wrong — it
added fees back into `cash`, which is already a pure notional flow, producing a
false "no flip". Caught by re-deriving. **The flip is real.**

*Also settled here:* **THE CORPUS INCIDENT ROOT CAUSE** —
`scripts/migrate_history.py:125` was `label_era_of(r.get("barrier") or "")`,
which **destroyed existing `label_era` values on every migration**. Corrected to
`r.get("label_era") or label_era_of(r.get("barrier") or "")`. **2,729 `label_era`
cells restored from two `.recovered` baks, zero rows lost** [ASSERTED].

*And a live risk bug:* `risk/position_sizer.py` read
`getattr(state, "positions", {}).values()` at three sites — `PortfolioState` has
**no** `positions` attribute. Heat was **structurally 0.0**; after the fix it read
**0.1177** [ASSERTED].

---

### Phase 6 — Era-4 pre-registration and the $800 capital reset (2026-08-10 → 08-11)
**Defining question: what population is the verdict allowed to accrue on, and can we still register it before we contaminate it?**

*Operator adjudication, verbatim:* **"now since we are getting things more refined
i want you to reset everything with equity back to $800. full clean sweep of all
money figures and make it trade to gain around $100 a month off the $800 equity.
putting it through this stressor will see what we have right and better COMPLETEly
wrong."** Followed by: *"as it starts to succeed, scale the profits to the most it
can stress every month if you or it realizes it can be useful for more monotary
gain."*

The record states explicitly that **the stressor and cut-#7 messages WERE
adjudications** under the moratorium.

Boundaries fixed [all ASSERTED]:

| marker | value |
|---|---|
| Execution-era boundary **#3** | `3cfe0710`, 2026-08-08 (fill-sim TTL normalization) |
| Execution-era boundary **#4** | **`aeeaae36`, 2026-08-10T11:03:35Z** |
| Capital epoch | **2026-08-10T23:05:27Z** (unix **1786403127**) |
| Cut **#7** = geometry epoch | **`e7d5ca1a`, 2026-08-11T01:33:50Z**, `exec_era = "7-e7d5ca1a"` |
| Pre-registered n | **`ERA4_MIN_N = 50`** |
| Readouts | **NO_GROSS_EDGE / COST_BOUND / CONTINUE** |

Boundary #4 was **mis-stamped as 2026-08-09** and fixed in `2fee7f64`. The rule
that came out of it: **cut on UTC instants, never local dates.**

*Stressor config live* [ASSERTED]: capital **800**, weekly **25**, monthly
**100**, `max_order_usd` **4000**, `engage_notional_usd` **250**. **RP-072 goal
ladder**: effective monthly goal = base × `state.goal_ladder_mult`, ratchet
**×1.5** *after* grading a met month, **never de-escalates**, resets to 1.0 on
capital reset.

*The geometry flip (cut #7):* Osler stop semantics **FLIPPED** from tighten-above
(exit before the cascade) to **widen-beyond** (survive the sweep; the herd fires
first). New pure module `risk/stop_placement.py`; the old clamps
`min(max(nudged, stop), entry*0.999)` were **REMOVED** because they structurally
enforced tighten-only. Cost accepted knowingly: this breaks exits into the
cascade, and the escalation ladder owns it. **An existing Osler nudge with
opposite semantics was discovered mid-edit**, dormant on the bracket path, reading
a **phantom config block** (`risk_management` does not exist — the knob lives
under `risk`); the initial edit **would have double-nudged and was reverted.**

*Settled:* **`vault/wiki/synthesis/comparability-boundaries.md` is authoritative**
for the boundary table; `core/fill_ledger.py` comments defer to it. The
**era-4 accrual moratorium** was written into repo `CLAUDE.md` in this phase, and
**model-side investment was FROZEN** by the 2026-08-10 operator adjudication.

---

### Phase 7 — The adversarial-review era (2026-08-14 → 08-15, worktree session)
**Defining question: can any of our instruments answer the question they were built to answer?**

This is the phase the program is currently in, and its finding is the most
uncomfortable one: **the verdict machinery is running, and it cannot presently
render a verdict.**

**Six instruments that cannot resolve their own questions** [all ASSERTED]:

| instrument | why it cannot fire |
|---|---|
| era-4 gate | **n_eff 4.3 / 14** |
| overfit battery | **SYNTHETIC** — 346–352 loaded < **640** floor; **0** from the worktree |
| OF-4 plateau | replay recording opens no positions — **`entries [0,0,0]`** |
| OF-5 DSR | **22/30** — below its conviction-trade floor |
| `gate_efficacy_report` | **SE × 8.07**; **n_eff 162.2 / 10,567**; uniqueness **0.0154** |
| `cost_truth_report` | **36.23 vs 28.005 bps** |

**The root-cause chain** [ASSERTED]: era exclusion (which is *correct*) shrinks
the corpus → (a) a **48×** orphan ratio fires **ML-083**, producing a
negative-skill champion; (b) **346 < 640** routes the overfit battery to
SYNTHETIC; (c) a zero-entry replay makes OF-4 inert. **One correct behavior
degrades three instruments at once.**

**The probe-cohort finding** — arguably the sharpest thing in the record:
**13 of 14** accruing trips are `probe=1`, and **`main.py:4402`** sets
`p_win = max(p_win, 0.7)` against a derived bar of **~0.567** — the probe lane
**clears by construction** [ASSERTED]. Two label eras are mixed in the accruing
set (`exit_sim` **8**, `triple_barrier_h432` **6**) [ASSERTED].

**Cohort contamination (verified at the time):** **6 of 1,065** fill rows carry
**16 fields vs 17** (rows **1038–1043**, **2026-08-12T20:55–22:02Z**); width
histogram **{17: 1059, 16: 6}** [ASSERTED]. Cause: the live tree sat at
**`21769fb8` (2026-08-07)** until the **08-12** fast-forward — boundaries #3, #4
and cut #7 are **NOT ancestors** of what was executing. **4 of 13 era-4 cohort
trips contain stale-binary legs**: `c37926ad` (exit), `42bdcaec` (entry),
`ef2a8c80` (entry), `d6fcc6df` (**both legs — the entire round trip**);
`911f9e88` is open and will join on close [ASSERTED]. And
**`cohort_eval.py` is era-blind** — selection is exit-time only
(`if tclose < max(B4_TS, CAPITAL_EPOCH_TS): continue`) and the string `exec_era`
**never appears in the file** [ASSERTED].

**DL-1, the structural trading deadlock** [ASSERTED]: cold-start prior **0.56** <
derived bar **0.690239**; `min_p_win` **0.55** is also below it. It is **masked in
DRY_RUN by the probe lane** (p=0.70, the only lane clearing, by **+0.0098**). It
becomes **total the instant `dry_run=false`.** **Clearing it is cohort-resetting.**

**The red-team panel.** Built to operator order: *"create a dedicated algorithmic
system to check it from different perspectives to make sure you are disagreed with
and have to state your case."* → `.claude/workflows/red-team-panel.js`, five
mandated-position lenses (RE-DERIVER, CLASS-DETECTIVE, LAW-READER,
NULL-HYPOTHESIS, FUTURE-READER), cross-examined by a *different* lens, concession
rate as the health metric. Doctrine: *"**The docket is not closed until every
objection has a recorded disposition.** The workflow cannot make you answer it —
that part is discipline."* and *"**0% conceded → the panel is theatre… 100%
conceded → the author stopped thinking.**"*

Result: **26 agents, 35 objections raised, 4 withdrawn, 16 surviving (4 BLOCKING,
5 CRITICAL)** [ASSERTED]. Current disposition status: **12 of 16 dispositioned —
11 conceded, 1 split concede/contest, 0 fully refuted; OBJ-4/7/8 and OBJ-13(a)
pending** [VERIFIED against the dispositions file].

*Settled here as method:* the verification layer **disagreed with the panel as
often as it disagreed with the author** — four objections were **amended on
verification** (OBJ-15's arithmetic, OBJ-10's remedy, OBJ-3's citation and
severity, OBJ-5's blocking claim). That is what keeps the panel from being either
theatre or capitulation.

---

## 2. Binding law now in force

Everything below currently constrains work. Nothing here is advisory.

### 2.1 Hard invariants — `CLAUDE.md` § "Hard invariants"
Never weaken, never "temporarily" bypass. When chat conflicts with one of these,
**stop and say so instead of complying.**

1. `system.dry_run` defaults **true**. No code path, config default, test
   fixture, or control command may set it false at runtime. Only road to live:
   config `dry_run:false` → restart → typed `ARM LIVE`.
2. `force_dry` is **one-way** (LIVE→DRY) and must flip **both** `bot.dry_run` and
   `bot.orders.dry_run` (OrderManager caches the flag at init).
3. **Kraken is the sole execution venue.** OKX / Binance.US / ccxt / moomoo are
   read-only data. `VenueAdapter.execution_eligible` requires `name == "kraken"` —
   do not relax, do not subclass around it.
4. **Withdrawals/transfers are impossible** — endpoint deny-list (Withdraw,
   WithdrawInfo, WalletTransfer, WithdrawAddresses) blocks before any network I/O.
5. Entries are **limit orders only** (OM-011). **Exits are ALWAYS allowed** —
   disarm, faults, and kill switches block new risk, never escapes.
6. Hash-chained JSONL audit trail; registered reason codes on every disposition
   (SZ-\*, VN-\*, RP-\*, FW-\*, ML-\*, OM-\*, QT-\*, PT-\*). New behavior = a new
   code in `core/codes.py`, never a bare string.
7. Public interfaces stay stable. Extend with defaults.

**Formal standing of invariant 5** (established 2026-08-14): under
Ramadge–Wonham, entries = Σ_c (controllable), exits = Σ_u (uncontrollable).
**Invariant 5 is the controllability precondition — weakening it makes the class
of implementable supervisors EMPTY** [ASSERTED]. Related: **no non-trivial
liveness property is refutable on a finite trace** (Alpern–Schneider 1985;
Aceto et al. 2019 Thm 6.1: violation-complete = Safe; Schneider 2000).

### 2.2 The era-4 accrual moratorium — `CLAUDE.md` § "Era-4 accrual moratorium"
In force from 2026-08-10 **until the gate reads out**.

**COHORT-RESETTING — forbidden without operator adjudication.** Any of these
mints the next execution-era boundary and restarts accrual:
- entry decisioning
- position sizing
- **stop/exit geometry** — placement, nudges, time limits (the cut-#7 lesson:
  *geometry changes trip outcomes even when fills don't move*)
- the fill simulator
- fee booking
- the order lifecycle

**SAFE:** measurement/report tools, dashboards, tests, wiki, telemetry export,
and bug fixes that do not alter which orders are placed or how they fill.

**Also binding:** do not read the accruing gate numbers as a trend; do not retune
on them. The registration is the law. The readout (NO_GROSS_EDGE / COST_BOUND /
CONTINUE) **names which decision has become decidable — it never decides.**

The **ALGO-5 amendment** (stop widths + time-decay ladder at ~30 uncensored
paths) is **PRE-NAMED as the next such adjudication**.

### 2.3 The model freeze (2026-08-10 operator adjudication)
No new model families, no new features, no meta-labeling. The retrain loop itself
continues by design. **The era-4 gate readout is the ONLY unfreeze trigger.**

### 2.4 Measurement standards, not tunables — `CLAUDE.md` § "Definition of done"
**DO NOT "fix" a degraded gate by lowering a floor.**
- overfit row floor **640** = `len(FEATURE_NAMES) * 10` [ASSERTED]
- `SG_MIN_ROWS` = **100** [ASSERTED]
- era-4 **n = 50** (`cohort_eval.py:79 MIN_COHORT_N = 50`; `:125 ERA4_MIN_N = 50`)
  [ASSERTED]

`gate_truth_report.py:12` says "measurement standard, not a tunable" — but
**only about `SG_MIN_ROWS`**; there are **zero** such hits in `cohort_eval.py`,
`cost_truth_report.py`, or `overfit_check.py` [VERIFIED]. **The overfit row floor
has neither a doctrine sentence nor a test pin** — `min_rows` is a
caller-overridable kwarg with zero test references, and `CLAUDE.md` is currently
the only thing holding it. It is the weakest of the three [VERIFIED].

**A GREEN IS ONLY AS BIG AS ITS CORPUS.** Read what each gate measured, not its
exit code. Any statistic over concurrent trips or overlapping label windows must
report **effective n**, not row count — `n_eff = Σ(time-weighted mean of 1/c(t))`,
SE scales `1/sqrt(n_eff)`; an SE on nominal n is optimistic by `sqrt(n/n_eff)`.

### 2.5 Governance rule 12 — the wiki is truth
**Operator verbatim:** *"From now on the corpus's Wiki is the truth and evrything
that is determined correct or has been determined correct needs to be injected
into the corpuses wiki"*. Every confirmed finding is filed **same-session**.

**Canonical vault:** `C:\Users\haird\Documents\liquiditybot\vault` — holds
`wiki/synthesis/comparability-boundaries.md`, the authoritative execution-boundary
table that `core/fill_ledger.py` comments defer to. Lints at 0 broken links.

**Duplicate vault:** `C:\Users\haird\vaults\liquiditybot` — created in error,
**RETIRED as a write target 2026-08-14**, nothing deleted. Carries
`_RETIRED_READ_THIS_FIRST.md`. **Never file new liquiditybot knowledge there;
never bulk-copy it into canonical** — a shared basename is not a shared page, and
a blind merge would overwrite canonical pages with stale variants and break the
wikilink graph. **Merge-or-retire is an OPERATOR decision, still open.**

**Governance rule 18 — NO ORPHAN CLAIMS** (`concepts/no-orphan-claims`,
2026-08-14). Three obligations in order: (a) consult the wiki *before* deriving;
(b) wiki silent → **reference back** to the primary artifact the page cites, not
to recall; (c) no reference at all → **find one** — "no citation available" is a
TASK, not a disposition. **Currency counts as correctness:** a page a measurement
contradicts gets its callout the same session, both sides.

### 2.6 Never delete learning data
Operator standing rule from the earliest window. **Machine-enforced** via
`.mythos/policy.json`: `"block": ["outputs/**", ".mythos/**", ".git/**", "config.json"]`.
Operationalized as **quarantine, not delete** — `fills.quarantine.csv`,
`trade_paths.csv.quarantine_qa_1786`, `signal_history.csv.prerepair_1786253662`,
`fills.csv.bak_1785680678`.

### 2.7 The delegated-measurement contract — `USAGE.md`, clauses a–g
**ENFORCED.** Measured cause: under-determined specs produced **5 of 9 wrong
numbers in one session**; agents fill gaps silently rather than halting. Every
subagent asked to produce numbers gets ALL of these in its prompt:

- **(a)** boundaries are EXACT — no "~", no "roughly"; state inclusive bounds
  verbatim in every prompt sharing the window
- **(b)** NAME THE NEEDLE — exact grep string per source; an unnamed needle
  returns "cannot be established"
- **(c)** SNAPSHOT-STAMP LIVE FILES — `status.json`, `*.lock`, logs mutate;
  require the read time; values are as-of, never "current"
- **(d)** ONSET CLAIMS NEED FULL-RANGE SCANS — "first/earliest/began" may never
  come from a sampled tail
- **(e)** DOUBLE-DERIVE LOAD-BEARING COUNTS — two routes, both reported if they
  disagree
- **(f)** PROVENANCE PER CLAIM — file + filter + value, tagged [K]/[I]/[UNKNOWN]
- **(g)** RE-DERIVE, DON'T RECALL — including the assistant's own earlier
  summaries. Recall-before-derive saves re-*reading*; it must never become reuse
  of a **cached conclusion as evidence.**

### 2.8 Agent-spend tiering — `USAGE.md`, clauses h–m
**ENFORCED**, measured 2026-08-14: model monoculture was the #1 overspend
pattern — **61 agents, ~5.6M tokens, all on one model at effort high** [ASSERTED].

- **(h)** RECALL BEFORE FAN-OUT — query the wiki *before* launching a workflow.
  One **1.12M-token** architecture workflow re-derived a taxonomy the vault held.
- **(i)** PRIOR-ART PASS FIRST — one cheap agent answering "does this already
  exist?" **3 of 25** proposals in one workflow duplicated shipped tooling.
- **(j)** TIER THE MODEL — mechanical extraction/grep/inventory → haiku;
  synthesis/judging/adversarial-verify → session model.
- **(k)** TIER THE EFFORT — `low` for mechanical stages; `high`+ only for the
  hardest verify/judge/synthesis. **high is the API default, so unset ==
  expensive.**
- **(l)** CACHE THE FAN-OUT PREFIX — run ONE agent first, then fan out, because
  concurrent requests cannot read a cache still being written.
- **(m)** offline / non-latency-sensitive re-runs go through the Batch API.

Grounded rates (verify with the `claude-api` skill, never memory): Opus 5
**$5/$25** per 1M in/out; Fable 5 **$10/$50**; Haiku 4.5 **$1/$5**; cache read
**~0.1×** input, cache write **1.25×** (5m) / **2×** (1h); minimum **512** tokens
on Opus 5 / Fable 5, **4096** on Haiku 4.5; Batch API **−50%** [all ASSERTED].

### 2.9 Standing operator directives (verbatim, all recorded as still in force)
- *"dont ask me to merge any of these task. i pre-approve all changes. if you
  have any questions reach into financial data bases and reflect to get the best
  answer."*
- *"make sure profitable crypto trading is its ground truth."*
- The bot must *"think its trading seriously with real money at all times being
  vigilent to never miss rent payment because a bad trade"* and know *"rent gets
  paid through profitable trades so it cant be afraid to take calculated risk"*.
- *"Run python scripts/gate_efficacy_report.py after any gate change."*
- *"make sure anything similar to pytest-xdist that will improve/distribute my
  PC's load or computational abilities need to be sought after and implemented"*
- **Paste-back = approval.** The record explicitly names this as the operator's
  approval pattern.

### 2.10 Operational laws that are easy to forget and expensive to relearn
- **Grafana boards are GENERATED** by `scripts/build_trading_dashboard.py`;
  `test_generator_matches_shipped_json` enforces it. **Never hand-edit the JSON.**
  Serialization contract: `indent=2, ensure_ascii=False, NO trailing newline`.
- **Grafana SA token** via `GRAFANA_SA_TOKEN` env or
  `~/.liquiditybot/grafana-sa-token` — **never argv, never committed.**
- **Model ID never in commits, PR bodies, or repo artifacts.** Trailer is exactly
  `Co-Authored-By: Claude <noreply@anthropic.com>`.
- **Deploy topology:** the live box follows **`claude/remote-control-e3h815`, not
  `main`** — pushing to main alone deploys nothing. And separately:
  **"Commits made on the deploy machine never deploy themselves"** — `auto_update`
  logs "already up to date" because `git pull` is a no-op on the box that
  authored the commit. This silently ran the runner on 4:31 PM 8/5 code across
  six commits.
- **Never dirty the PC checkout.** A fresh worktree is the honest test
  environment — two leaks were invisible to both in-repo instruments.
- **Coordination:** one session owns `main` fast-forwards at a time; pull
  `--rebase` before any push. **A gate's release condition must never depend on
  the thing it blocks** — four incidents in one week shared that shape.
- **Deploy runbook gate is `positions == 0 AND open_orders == 0`** — flatten never
  cancels resting entries; 6h long-book bids could fill **156%-of-equity** into an
  **$800** book [ASSERTED].
- **`ALGO-2` must be a SIDE-LEDGER keyed `candidate_id` — never corpus schema.
  `ALGO-3` must be a REPORT script — zero engine writes.**
- **rtk quirks:** mangles multi-line here-strings and `stash@{0}` braces. Use
  `git commit -F <file>` and quoted refs. Never fight it; route around.
- **Local toolchain traps** (from memory, all three "return green having checked
  nothing"): the SuperClaude pytest plugin silences the whole battery; the
  worktree `outputs/` is **empty**; pyright needs `--venvpath`.

---

## 3. Settled conclusions — do not re-litigate

Each entry below has been closed by measurement. Re-opening one costs a session
and has, historically, produced the same answer.

| # | Finding | Evidence | Why it is closed |
|---|---|---|---|
| S1 | **"A better model" is not the lever.** | Three *independent* directions: random-entry control mean MFE percentile **0.516 [0.439, 0.594]** (no entry timing signal); 48-combo pre-registered geometry grid at Bonferroni z=3.26 with **NO GEOMETRY SURVIVING** (best −0.400%, LB −1.124%); break-even win rate **> 1, impossible at every real fee schedule** [all ASSERTED]. | Three refutations that share no data path. A fourth model would have to beat an arithmetic impossibility, not a fitted baseline. Levers are the cost stack, fewer/longer maker-only trades, and pooling. |
| S2 | **No bracket geometry survives out-of-sample.** | `scripts/geometry_search.py`, **pre-registered** 48-combo grid, Bonferroni **z = 3.26**, first-touch walk with both-touched → SL (conservative) [ASSERTED]. | Pre-registered, multiplicity-corrected, and conservative on ties. A post-hoc winner from this grid would be exactly the OF-4 backtest-peak the overfit discipline forbids. |
| S3 | **Fees, not signal, are the binding constraint.** | Gross **−$11.66** vs fees **−$382.59** → **32.8× \|gross edge\|**; net all-in **−$394.25 (−7.89%)** [ASSERTED]. Five corroborations at chance level. | The ratio is not close. Any signal improvement of realistic size is dominated by the cost stack. |
| S4 | **Meta-labeling is RULED OUT.** | Research found **zero independent peer-reviewed tests** and that it has **never been tested on a losing primary** [ASSERTED]. Recommended and **retracted twice** before the ban. | Standing directive: *never re-propose.* |
| S5 | **The fill simulator was exonerated in the ETH contamination.** | It applied 2.5 bps to `arrival_ref` correctly; `1490.645739 / 1491.018493 = 0.999750` = exactly 2.5 bps. The **reference price** was a seeded placeholder (`arrival_ref = 2000.000000`) [ASSERTED]. | *"The fill simulator worked correctly; the reference price it was given was fabricated."* |
| S6 | **The simulator WAS 9× flattering on passive fills (XV-021).** | Measured passive fill prob **0.048 [0.046, 0.050]** vs configured **0.45**; config corrected [ASSERTED]. | Distinct from S5 and both are true. The form is still misspecified (**XV-022**, band [0.048, 0.082]) — that piece is *owed*, not settled. |
| S7 | **Exit codes are not evidence.** | Five named false-green specimens, including a battery printing **ALL GREEN over "1 failed, 3444 passed"**, and a pyright gate **skipped for weeks** [ASSERTED]. | Doctrine, not a bug. Encoded as rule 16 (check BOTH markers), missing-tool = RED, and AST-pins-over-grep-pins. |
| S8 | **`101f7436` introduced the lying gate its own message claimed to repair.** | Wiki traced the `||`-after-`start` construct to that commit; era of honest greens begins at **`050421a7`** [ASSERTED]. | **Every green between `101f7436` and `050421a7` is retroactively invalid.** Do not cite them. |
| S9 | **The corpus incident root cause.** | `scripts/migrate_history.py:125` overwrote `label_era` on every migration; **2,729 cells restored, zero rows lost** [ASSERTED]. | Fixed at the source and the data was recovered. |
| S10 | **`equity.csv`'s −$20,061 era-1 "loss" was NOT P&L.** | Capital reconfigurations: **25k → 100k → $800 → 5k**, last **07-16 21:37Z** [ASSERTED]. | Recomputed post-reset. A retracted claim; do not re-derive from `equity.csv` without the reconfiguration mask. |
| S11 | **The haven ladder is a tendency, not a law.** | Realized 5m vol ranks down the ladder (PAXG 0.075% < BTC 0.093% < ETH 0.120% ≈ SUI 0.116% < ARB 0.160%), but **BTC-ETH came out negative** [ASSERTED]. | Qualified at the moment of its own live validation. `regime/haven.py` states **UNKNOWN is a state, not a guessed number.** |
| S12 | **exec_era #6 never existed.** | The boundary table held rows `0,1,2,3,4,L,5`; the label row's letter **`L` consumed slot 6**, and **#7 was assigned as the next free *ordinal* rather than the next free *numeric ID*** [ASSERTED]. #5 was minted (capital axis) but the stamp never bumped, and its window is fill-free anyway (**25h22m** RP-041 lockout). | Retracted and explained. Only **two** `exec_era` values have ever existed. |
| S13 | **Explicit pyright CLI paths override config `include`.** | Four runs, no working-tree mutation: DoD command **0/0**; `pyright tests scripts` (both absent from include) **1545 errors, 1 warning**; bare `pyright` with include **0/0**; explicit pre-change reconstruction **1545/1** [VERIFIED]. | Settles the precedence question empirically. The DoD command and `test_windows.bat:72` are **provably inert** to the `pyrightconfig.json` change. 0 + 1545 = 1545 locates **100%** of errors inside `tests/`+`scripts/`, which `CLAUDE.md` states are outside the gate. |
| S14 | **No string breaks `"SYNTHETIC" in str(source).upper()` but not `startswith("SYNTHETIC")`.** | **Exhaustive scan of all 1,114,112 codepoints plus 200k random suffixes, zero counterexamples** [VERIFIED]. | The stated fragility rationale for the CI ban is provably impossible. **But the ban stays** — the banned form fails **OPEN** on false positives (`'live history (348 rows, synthetic-fill era)'` → banned True, retained False), which would print "not evidence about the deployed strategy" over a **real** corpus. Code correct, prose wrong. |
| S15 | **Invariant 5 is a controllability precondition, not a preference.** | Ramadge–Wonham: entries Σ_c, exits Σ_u. Weakening it makes the class of implementable supervisors **empty** [ASSERTED]. | Elevates "exits are always allowed" from policy to a theorem about whether *any* supervisor can exist. |

---

## 4. Open items, PRIORITIZED

Ranked by **blast radius × irreversibility × what it blocks**. Read P1–P5 first;
they are the ones where doing nothing is itself a decision.

### 4.A — OPERATOR-ONLY adjudications

---

#### P1 — Sign the era-4 readout decision table. **DEADLINE ~2026-08-16 (TOMORROW).** — OPERATOR
**What:** the pre-registered decision table mapping each readout
(NO_GROSS_EDGE / COST_BOUND / CONTINUE) to an action, signed **before** any gate
reaches n=50.

**Why the clock is real:** the legacy **2026-08-02** gate hits **n=50 around
2026-08-16**; the era-4 readout follows around **08-23/24** [ASSERTED]. Signing
*after* seeing a number is not pre-registration — it is the selection effect the
entire n=50 apparatus exists to prevent.

**Blocks:** the credibility of every downstream decision, including the model
unfreeze.

**Reversibility:** effectively **zero**. Once the number is visible the
registration cannot be recovered.

**Status in the record:** listed as **N1, ~08-16 deadline**, "[LIKELY STILL
OPEN]" in the most recent extract.

---

#### P2 — Adjudicate cohort contamination: 4 of 13 era-4 trips carry stale-binary legs — OPERATOR
**What:** the live tree sat at **`21769fb8` (2026-08-07)** until the **08-12**
fast-forward. Boundaries **#3, #4 and cut #7 are NOT ancestors** of the binary
that executed those trips [ASSERTED]. Affected: **`c37926ad`** (exit),
**`42bdcaec`** (entry), **`ef2a8c80`** (entry), **`d6fcc6df`** (**both legs**);
**`911f9e88`** is open and **will join the cohort on close**.

Compounding: **`cohort_eval.py` is era-blind** — selection is exit-time only
(`if tclose < max(B4_TS, CAPITAL_EPOCH_TS): continue`), and the string `exec_era`
**never appears in the file** [ASSERTED]. Also confirmed: **6 of 1,065** fill rows
are 16-field vs 17 (rows **1038–1043**, **2026-08-12T20:55–22:02Z**; histogram
`{17: 1059, 16: 6}`) [ASSERTED]. And the fill simulator active during the
contaminated window had **both the TTL hazard compounding bug and the ~1.88×
near-touch double-count** [ASSERTED].

**Who decides:** OPERATOR only. The prior session's own closing line governs and
should be honored: *"Adjudicating whether this mints/voids anything is an operator
decision — I changed nothing and read no gate P&L."*

**Blocks:** the *meaning* of the era-4 readout. A cohort that mixes two binaries
is not the pre-registered population.

**Deadline:** before the readout (~08-23/24), and ideally before `911f9e88`
closes and enlarges the contaminated fraction.

---

#### P3 — Owed 74: the probe cohort clears BY CONSTRUCTION — OPERATOR
**What:** **13 of 14** accruing trips are `probe=1`, and **`main.py:4402`** sets
`p_win = max(p_win, 0.7)` against a derived bar of **~0.567** [ASSERTED]. The
lane that is filling the cohort is the lane that **cannot fail the gate it feeds.**
The accruing set also mixes two label eras (`exit_sim` **8**,
`triple_barrier_h432` **6**) [ASSERTED].

**Why this is P3 and not lower:** this is the **gate-that-cannot-fail** defect
class applied to the *verdict itself*. If left unadjudicated, the era-4 readout
may render CONTINUE on a population selected by a floor rather than by the model.

**Who decides:** OPERATOR — any change to which lane accrues is entry decisioning,
i.e. **cohort-resetting**.

**Blocks:** the interpretation of P1 and P2.

---

#### P4 — DL-1: the structural trading deadlock that is total the instant `dry_run=false` — OPERATOR, and blocked by the moratorium
**What:** cold-start prior **0.56** < derived bar **0.690239**; `min_p_win`
**0.55** is also below it. The **only** lane clearing is the probe lane at p=0.70,
by **+0.0098** [ASSERTED]. In DRY_RUN this reads as "the bot trades". At
`dry_run=false` **the probe lane is gone and nothing clears — the deadlock is
total.**

**Who decides:** OPERATOR. The record is explicit: **"Clearing it is
cohort-resetting."** It touches entry decisioning.

**Blocks:** live arming, entirely. This is the single item that makes the
difference between "we have a paper bot with an unproven edge" and "we have a
paper bot that structurally cannot trade live at all."

**Note the coupling to P3:** DL-1 and the probe-cohort finding are two views of
the same mechanism — the p=0.70 floor is simultaneously *what masks the deadlock*
and *what makes the cohort self-clearing*. Adjudicate them together.

---

#### P5 — Owed 73: the ML-083 floor — OPERATOR
**What:** `main.py:6387` — when `trained_rows > len(X)` (an era-orphan condition),
ML-083 sets the champion badge aside and applies the **bare cold-start bar
Brier < 0.25** [ASSERTED]. In the current corpus state a **48× orphan ratio**
fires this, producing a **negative-skill champion** that is nonetheless deployed
[ASSERTED]. The champion cleared at Brier **0.24728** against a **0.25** coin
[ASSERTED] — a margin of 0.00272 against random.

**Who decides:** OPERATOR. Raising the floor is a model-side change under the
2026-08-10 freeze; lowering it is the widening `CLAUDE.md` forbids.

**Blocks:** whether the deployed champion should be trusted at all during accrual.

**Note the retraction attached to this item:** the earlier claim that
`champion_bar` "ratchets the wrong way, cleared by 0.00049" was **WRONG** — that
value is `monitor.champion_brier` recorded for observability only
(`main.py:6467`) and is **never a threshold**. The real mechanism is ML-083's
unlock. Do not re-derive from the retracted framing.

---

#### P6 — The 9 SHIP-BLOCKED defects — OPERATOR
Deferred to the operator in the most recent session. **The record does not
enumerate them in the extracts** — locate the list before acting. Provenance:
`vault/wiki/.../owed-measurements` and the 2026-08-15 scans page
(`sources/session-20260815-scans-and-corrections.md`).

#### P7 — The 88-page vault merge-or-retire — OPERATOR
**What:** the duplicate vault at `C:\Users\haird\vaults\liquiditybot`. Retired as
a write target 2026-08-14; nothing deleted; carries `_RETIRED_READ_THIS_FIRST.md`.

**Why it must not be done by the assistant:** *a shared basename is not a shared
page.* A blind merge would overwrite canonical pages with stale variants and break
the canonical vault's wikilink graph, which currently lints at **0 broken links**.

**Contradiction to resolve first:** page count is recorded as **90** (2026-08-14)
and **88** (2026-08-15); `USAGE.md` records **115 files / 88 basenames canonical
does not have**. See §6.

---

### 4.B — Assistant-actionable SAFE items

All of the following are **measurement/report/test/docs** surfaces and do **not**
touch which orders are placed or how they fill. They are SAFE under the
moratorium — the docket itself records this for the OBJ-2 fix in as many words:
*"It is report-only tooling: no order, fill, fee, or geometry surface, so it does
not trip the era-4 moratorium."*

---

#### P8 — `gate_truth_report.py:194` reads the RETIRED era — the only conceded defect with LIVE consequences today
```python
era = [r for r in rows if (r.get("label_era") or "") == "triple_barrier"]
```
[VERIFIED]. That is the retired 96-bar era. It reads **5,328 dead rows** and
**zero** of the **358** deployed `triple_barrier_h432` rows [ASSERTED]. Recomputed
with the report's own `effective_n()` over the deployed era: **n_eff 55.1 <
SG_MIN_ROWS 100 → XV-042 THIN**, not the **XV-040 ALIGNED** it currently prints
[ASSERTED].

**Two compounding facts:** `ml/history.py:645-654` already documents this exact
bug class as fixed *elsewhere*; and `CLAUDE.md` currently **cites this tool as the
exemplar** of the effective-n standard. Fixing the tool also requires fixing the
citation.

**Do this first among the SAFE items.** It is the only one where a verdict
instrument is presently reporting a wrong grade on live data.

---

#### P9 — Finish the red-team docket: 4 pending dispositions + 6 code fixes
**Status [VERIFIED against `2026-08-15_docket_dispositions.md`]:** 12 of 16
dispositioned — **11 conceded, 1 split (OBJ-10), 0 fully refuted**.

**Pending dispositions (archaeology; an agent was running at write time):**
- **OBJ-4** — number decay against a *frozen* file. Re-running the loader at
  18:28:29Z gave **352** while `signal_history.csv` was byte-identical
  (**8,324,656 B / 10,659 lines**, mtime 17:00:34Z) — so the drift is wall-clock
  label resolution, not file growth [ASSERTED].
- **OBJ-7** — the three-run provenance sequence "346, then 352, then 347 within
  the hour". Reconstruction says the count changed **exactly once** in
  15:22Z–16:22Z (**348→349**); 346 was last true **12:51Z**, 347 at **13:02Z**,
  and **352 was not reached until 16:40Z — after the commit** [ASSERTED].
  **"(moving)" is NOT contested** — the count moved **+39** on 08-15 alone
  (**314@09:52Z → 353@17:00Z**) with three measured decrements (08-13T17:00:25Z,
  08-14T13:48:42Z, 08-14T15:39:34Z, each −1 via `ml/history.py:1573-1582`
  clash-dedup). Only the three-run *sequence* must be struck.
- **OBJ-8** — era **reset** vs era **exclusion** as the correct causal lever. The
  panel's case: exclusion was armed and still produced **2141 rows** on
  2026-07-31 against the same 640 floor; the real trigger is `label_max_bars`
  24→432 (**`7566ea88`, 2026-08-01**) minting `triple_barrier_h432`; first row
  **2026-08-12T20:56:18Z**; 150th re-armed exclusion **2026-08-14T00:15:07Z**
  [ASSERTED]. **It will recur at every horizon migration.** The consequence the
  author must answer: `ml.era_exclusion.forced_off` (`config.json:781`, "restores
  the pre-exclusion training set exactly") is the **un-fenced door** to exactly
  the widening the new CLAUDE.md paragraph forbids by floors.
- **OBJ-13(a)** — accounting **CONCEDED**, severity **REFUTED** (see S13).
  **Disposition already recorded: commit `pyrightconfig.json` SEPARATELY**, with a
  message naming the surface (editor / bare-pyright only; DoD path-explicit and
  unaffected; 1545 ungated diagnostics intentionally suppressed).

**The six code fixes the dispositions name as "what actually needs fixing in
code (not prose)":**
1. the volatile number at `overfit_check.py:1118` (**OBJ-1**)
2. the **five-fold** predicate derivation — `:704, 833, 1075, 1084, 1089`
   [VERIFIED] (**OBJ-2/9/14**). One fix closes four objections: thread the single
   `on_synthetic` through the four inline sites, assert
   `code.count('source.startswith("SYNTHETIC")') == 1`, and pin the `:266` prefix.
   **Do it first among the six** — `on_synthetic` feeds `gate_is_informational` at
   `:745`, and `config.json ml.exploration.enabled` is `true`, so a `:266` prefix
   rename would silently soften OF-1 and OF-7 while the battery printed
   "passed 7, failed 0".
3. the loaded-vs-live conflation minted at `:254` (**OBJ-12/5**). Re-derived
   census: **candidate 10,331 : live 327 = 31.6:1**; today's live path would print
   **352 against `n_live=6` = 58.7:1** [VERIFIED]. `n_live` is unconditionally in
   scope at `:701`.
4. the missing **could-not-fire denominator** (**OBJ-15**). The shipped run is
   **7 of 14** — *not* 7 of 13; the panel missed the `:955`/`:941` dof site
   [VERIFIED]. Two `monotone` slots vanish **silently** via the `continue` at
   `:309`. Print `passed N, failed M, could-not-fire K`. **Do not** count all 46
   `info()` sites — that prints K=25 of mostly by-design diagnostics.
5. the one-story reason string at `:260-261` (**OBJ-3**). `:247` has **three**
   conjuncts; a class-balance trip prints the literally false
   `loaded rows=700 < 640` as the headline. `grep -rn "loaded rows" tests/` =
   **0 hits** [VERIFIED] — nothing pins the reason text's truth.
6. `gate_truth_report.py:194` (**OBJ-11**) — see P8.

Plus, from OBJ-10's split disposition: **the same false fragility claim is
duplicated in a live docstring at `tests/test_preventive_maintenance.py:169-170`**
and must be fixed there too [VERIFIED].

**Rule that governs completion:** *the docket is not closed until every objection
has a recorded disposition.*

---

#### P10 — NEW, raised by verification and not by the panel: the shipped-scope list exists in THREE uncoordinated copies
`CLAUDE.md` prose (~line 116), `tests/test_dependency_hygiene.py:30-32`
(`ENGINE_DIRS`/`ENGINE_FILES`), and now `pyrightconfig.json`'s `include`
[VERIFIED]. **All three agree exactly today; nothing keeps them agreeing.** A new
engine directory would be added to one and silently missed by the others — and
the pyright copy means bare `pyright` would stop checking it **with no signal.**

This is the **duplicated-predicate class of OBJ-2, one level up**, and it is
partly self-inflicted: `test_dependency_hygiene.py` was authored in a prior
session of this same effort.

---

#### P11 — Uncommitted work sitting in the tree
- `pyrightconfig.json` (+13, the `include` list; **1546 → 0** diagnostics,
  `filesAnalyzed` **489 → 96** [ASSERTED]) — **commit separately**, per OBJ-13(a).
- `.claude/workflows/red-team-panel.js` + its `README.md` — NEW, uncommitted.
- `logentry4.md` — written to scratchpad, **not yet appended** to
  `vault/wiki/log.md`; final lint owed.
- `docs/quant/2026-08-14_edge_training_design.md` — created, **uncommitted**;
  carries the CDO addendum's three binding conditions (N1 candidate-repair branch
  first; forensic columns need freeze-tripwire tests pinning them **OUT** of
  `FEATURE_NAMES`; boundary-#4 mask as a hard S1 filter).

**Scratchpad is session-scoped.** Anything still there is at risk.

---

#### P12 — The six instruments that cannot resolve their own questions
Listed in §1 Phase 7 with their measured degradation. This is **not** a bug list —
it is a standing structural problem with **no closure recorded**. The correct
response per `CLAUDE.md` is to **say so out loud and treat what each was meant to
prove as UNPROVEN.** Do **not** fix any of them by lowering a floor.

What is actionable without operator input:
- report **effective n** everywhere it is currently nominal (`cohort_eval.py` has
  done so since 2026-08-15; `gate_truth_report.py` since 2026-07-29)
- add the could-not-fire denominator (P9 item 4)
- fix the era filter so `gate_truth_report` reads the deployed era (P8)
- surface the corpus qualifier where the mandated battery form can see it —
  **but NOT** by wiring `--require-live-corpus` into `test_windows.bat:57`, which
  the panel itself **REFUSED**: it reddens the DoD matrix until 640 new-era rows
  exist, and new-era rows accrue only by running the bot while shipping requires a
  green matrix. That is the exact *"gate's release condition depends on the thing
  it blocks"* shape `CLAUDE.md`'s coordination notice names as this week's
  four-incident pattern. **`tests/test_battery_gate.py` (`_BAT` at `:23`) is the
  existing seam.**

---

#### P13 — The SAFE-NOW backlog (recorded, none marked closed)
N2 realized-hold report from PT-061 rows · shadow re-tag report · effective-n
telemetry · label-forensics persistence · calibrator pool-mass monitor · docs
correction (**h432 real start ~08-03**) · restore the parked
`test_feed_freeze_gate.py.parked` if docket 41a resumes (flagged **do-not-lose**;
scratchpad is session-scoped) · `status.json` empty-key PowerShell break ·
`fills.csv` **$6.24** gap · `train_meta` ML-083 asymmetry.

Tier-1 ALGO builds, in the operator's adjudicated dependency order:
**ALGO-3** defensive-cadence REPORT script (joins `trade_paths` + `signal_history`
barrier reasons + funding/basis — **zero engine writes**) → **ALGO-2**
regime-stamp SIDE-LEDGER keyed `candidate_id` (**never corpus schema**) →
**ALGO-1** four-state slow/fast tape (**432/96**: Bull/Correction/Bear/Rebound),
alongside Tier 2.

---

#### P14 — Unanswered operator requests (most recent session)
- *"add basically all python configurations and add them to the path and refine
  the whole codebase with more suitable code stability"*
- *"look for improvements /brainstorming"*

Both **[LIKELY STILL OPEN]** per the most recent extract.

---

### 4.C — Items BLOCKED by the moratorium (do not touch until the gate reads out)

| item | why blocked |
|---|---|
| **ALGO-5 amendment** — stop widths + time-decay ladder | **PRE-NAMED** as the next cohort-resetting adjudication. Gated at **~30 uncensored paths**; `outputs/trade_paths.csv` currently reads **10 rows** [ASSERTED]. *(The earlier claim "ALGO-5 trigger fired 6× over at 182" was **RETRACTED** — item 67's measure is the 10-row file.)* |
| **37a — fee constants** | **HELD behind the h432 verdict per the 5-0 judge panel**, because of coupling at `labeling.py:48-52`. Fee booking is cohort-resetting. |
| **Fill-sim double-chance** (**22.30%** measured vs **11.66%** target; combined hazard **2f − f²**) | Fill simulator = cohort-resetting. |
| **DL-1 clearing** (P4) | Entry decisioning = cohort-resetting. |
| **Owed 52** — should the consecutive-loss breaker count HEDGE closes? | OPERATOR-only design call, standing since 2026-08-09. `main.py:1671` `if not pos.is_hedge:` gates **BOTH** `perf.record_close` **AND** `breaker.record_close`, excluding **−$325.70** of real money from the perf ledger. Effect if changed: **+1 trip / 19.5d**; churn stops at **4 laps vs 147** [ASSERTED]. The recorded position: the **perf ledger** should clearly see hedges; the **breaker** is a genuine design question — *a hedge loses by design*. Verbatim: *"I'm not going to silently redefine when your circuit breaker fires."* |
| **Model-side work of any kind** | 2026-08-10 freeze. Only unfreeze trigger: **the era-4 gate readout.** |

Also still open and never adjudicated: **the h432 `6/11`-vs-`recent-30`
discrepancy**, left **UNADJUDICATED** by the 5-0 judge panel on 2026-08-08 and
never revisited in any later summary.

---

## 5. The recurring defect classes

Across 13 summaries the extracts record roughly **141** corrections and
retractions (file-level counts: 13 + 19 + 12 + 13 in batch 1, 10 + 9 + 10 (dup) +
9 in batch 2, 8 + 10 + 12 + 12 + 14 in batch 3). The list is not the lesson. The
**shapes** are, and there are eight of them.

---

### Class 1 — The gate that cannot fail (false green)
The dominant class, and the one that costs the most because it consumes *other*
sessions' trust.

- **pyright silently SKIPPED for weeks** — the gate was absent, not passing.
- **`start /b /wait "" cmd || (...)`** — printed **ALL GREEN over "1 failed, 3444
  passed"**, and the construct **entered at `101f7436`, the commit whose message
  claimed to repair two lying gates.**
- **OBJ-14, mutation survival [VERIFIED]** — swapping `if on_synthetic:` for the
  inline predicate (the precise duplication the test forbids) leaves **all three
  asserts green**. The test never imports, never runs `main()`, never captures
  stdout.
- **A vacuous hedge-convergence test** that passed on the buggy engine because the
  function was pure and never mutated state.
- **A trajectory-row test that read only `row["panels"]`**, which is empty for
  EXPANDED rows — it asserted nothing.

**Structural fix (partly shipped):** prove RED before trusting GREEN (two-sided
proof); **AST pins over grep pins**; **rule 16** — check **BOTH** `BATCH_EXIT`
and the literal `ALL GREEN.` marker; **missing tool = RED stage**. **Still
missing:** a mutation-survival check on the pins themselves. OBJ-14 shows the
current pins do not have one.

---

### Class 2 — The gate whose release condition depends on the thing it blocks
`CLAUDE.md`'s coordination notice names this explicitly: *"a gate's release
condition must never depend on the thing it blocks (4 incidents this week share
that shape)."*

- **The deploy-gate self-brick (`64b6fd5`)** — the new outputs guard failed a
  test, so `auto_update` refused ALL updates **including its own repair**. Same
  shape as the replay-gate self-brick of 07-21.
- **OBJ-16's refused remedy** — wiring `--require-live-corpus` into
  `test_windows.bat:57` reddens the DoD matrix until 640 new-era rows exist, and
  new-era rows accrue **only by running the bot**, while shipping requires a green
  matrix. The panel **REFUSED its own headline demand** on exactly this ground.
- **The probe lane (P3)** — `p_win = max(p_win, 0.7)` against a bar of ~0.567.
  The population feeding the verdict is selected by a floor that guarantees it
  clears.
- **The era deadlock** — `live_clean` stuck at **0** for **13 days**, invisible,
  because the filter's arming condition depended on rows the filter was
  suppressing.

**Structural fix:** before shipping any gate, state its release condition and
check whether that condition is downstream of the gate. This is a **one-sentence
design review** and it would have caught all four.

---

### Class 3 — Volatile numbers written into permanent files
A number written into law decays into a false claim. `CLAUDE.md` says so and then
the same commit did it anyway.

- **OBJ-1 [VERIFIED]** — `overfit_check.py:1118` says *"era exclusion left 346
  loaded"*; the artifact reads **347**, a re-measure gave **352**. Author's own
  words: *"the exact volatile-number defect I evicted from CLAUDE.md, re-shipped
  in a code comment."*
- **`cost_attribution.py`'s verdict text** — *"the binding constraint is tail
  risk"*, written **before** the quarantine, left standing after it.
- **`36fcfd6e`'s commit message** — two false claims: a *"60-row threshold"* (the
  real value is **640**) and *"the identical red reproduces on the parent commit"*
  (**never run**).

**Structural fix (shipped as doctrine):** dated measurements live in the vault,
not in files loaded every session; permanent files carry **class rules**, not
readings; a retained number must be **freeze-pinned and written beside its
expression** (`640` beside `len(FEATURE_NAMES)*10` survives on exactly this
ground) or carry a minute-resolution stamp reading **"re-derive, do not cite."**

---

### Class 4 — Hardcoded literals that go stale at a migration
The horizon migration (24 → 432) is a machine for producing this defect, and
OBJ-8 warns **it will recur at every horizon migration.**

- **`gate_truth_report.py:194` [VERIFIED]** — `label_era == "triple_barrier"`, the
  retired era. Reads **5,328 dead rows and zero deployed rows.**
- **`core/fill_ledger.py:46`** — `EXEC_ERA = "7-e7d5ca1a"`, **a hand-typed
  constant with no computation** [ASSERTED].
- **The battery-16 pin** — a `<=4` threshold built from a **`head -4`-truncated
  grep**; the real count was **6**. Named the **evidence-truncation** class.
- **A stale literal `22`** in the session-import pin, later replaced by derivation
  from `_N_LEAD`/`_N_TRAIL`.

**Structural fix:** derive from config or schema rather than transcribing
(`_N_TRAIL = 13 + len(SG_COMPONENT_KEYS) + 2` is the pattern that works); pin the
**expression**, not the **value**; and treat every era/horizon migration as
requiring a repo-wide sweep for the retired literal.

---

### Class 5 — One quantity, two derivations
Two spellings of the same predicate always diverge eventually, and the divergence
is silent.

- **OBJ-2 [VERIFIED]** — `source.startswith("SYNTHETIC")` derived at **five**
  sites (`:704, 833, 1075, 1084, 1089`) while the pin asserts *"exactly ONE place
  may derive on_synthetic"* and passes, because it counts the **assignment
  spelling.** Author's concession: *"my claim to have removed the duplication
  defect is false — four more copies exist."*
- **The shipped-scope list in THREE copies [VERIFIED]** — `CLAUDE.md` prose,
  `test_dependency_hygiene.py:30-32`, `pyrightconfig.json` include. Same class,
  one level up.
- **`net_pnl_all_time` (−382.4) vs `realized_net_all_in` (−394.25)** in the *same
  snapshot*, differing by **11.85**, with definitions given and the reconciliation
  never stated.
- **Loaded vs live** at `overfit_check.py:254` → `:1121`. The file's own comment
  at `:256-259` says this conflation *"cost a session's diagnosis on 2026-08-08."*

**Structural fix:** single-source the predicate and thread it; assert on the
**property**, not the spelling; and where two populations genuinely differ,
**print both** rather than picking one (the fee-free falsifier was rebuilt on
exactly this principle after failing to arm).

---

### Class 6 — Substring matching where identity was required
Named in the record as the **iron-law corollary**, with three original instances
and more since.

- **Grouping fills by `position_id`** — one contaminated pattern counted **16×**,
  making mean gross wrong by **27×** (−1.32% vs a deduplicated −0.1336%). Fixed by
  deduplicating **by fill pattern.**
- **`if ".venv" not in str(f) and "outputs" not in str(f)`** — the deploy gate's
  worktree lives at `outputs/_update_wt_<pid>`, so the filter excluded **the entire
  repo** → an empty scan → **external commits rejected twice.** Fixed to
  path-component exclusion.
- **Round-number `arrival_ref` as a placeholder tell** — load-bearing in one
  summary, **explicitly retracted as wrong** three days later.
- **A naive comma-split CSV verification** reporting **170** mismatches where a
  real `csv` parser gave **6**. Author's note: *"My method was wrong, not the
  agent's."*
- **`config_guard` reading a nonexistent key** (`system.lock_stale_after_sec`) and
  being right only by coincidence.

**Structural fix:** use real parsers, path-component sets, and exact-match on
typed columns. The operator asked the right question in-window — *"Are
engine-written enumerated codes the best way to write quant labels…"* — and the
answer recorded was **"for quant data, exact-match on typed columns."**

---

### Class 7 — Measuring on the wrong population (uncounted exclusion / pooled populations)
This class does not produce errors — it produces **confident wrong answers.**

- **The `is_hedge` exclusion** — `main.py:1671` gates **both** `perf.record_close`
  and `breaker.record_close`, silently excluding **−$325.70** of real money from
  the performance ledger.
- **The opening-leg omission** — `breakeven_test.py:126` counted only `"entry"`,
  not `("entry","hedge")`. Correcting it moved fees **$59.23 → $374.96** and
  **flipped the median gross sign.** This changed the answer to *"should I keep
  running this."*
- **The "5.9× censoring differential" — WRONG**: **159 hedge trips** sat in the
  post-432 denominator; corrected to **85.1% / 93.1%**, and the companion claim
  *"should read 188"* was also wrong (**29** entry-opened).
- **`equity.csv`'s −$20,061** read as a loss when it was **capital
  reconfigurations** (25k → 100k → $800 → 5k).
- **The heat overclaim −40.9%** — the reconstruction **stamped every position as
  opened *now***, maxing `u_short`. Real ages give **−13.7%**.
- **Nominal n where effective n was required** — `gate_efficacy_report` SE is
  optimistic by **×8.07** (n_eff **162.2** of **10,567**, uniqueness **0.0154**).

**Structural fix (partly shipped):** state the denominator with every ratio
(the **77.3% → 75.7%** fee correction is exactly this); enumerate exclusions
explicitly; report **effective n** on anything with overlapping windows —
`gate_truth_report.py` since 2026-07-29, `cohort_eval.py` since 2026-08-15.

---

### Class 8 — Self-flattery gradient and cached-conclusion reuse
Recorded as a named principle: **"all measurement bias runs one direction."**

- **The most instructive instance in the whole record:** the assistant
  **miscounted 8 vs 9 verifier corrections *inside an analysis of miscounting***.
  This became the core insight of the failure taxonomy.
- **`batch_audit.py` self-regression** — found the correct field path
  (`dimensions.structure`), then **"corrected" its own working code from memory**
  to a top-level `structure`. Re-fixed only after inspecting the real JSON.
- **The near-dismissal of the breakeven flip** — the verification added fees back
  into `cash` (already a pure notional flow), producing a false "no flip".
- **Three successive wrong diagnoses**, each overturned by better measurement:
  exit asymmetry (refuted by MFE capture −3.34) → cost domination (refuted by
  gross P&L) → "negative gross expectancy −1.32%" (**wrong by 27×**).
- **"Said 'four domains', dispatched two"** — acknowledged rather than papered over.
- **A harness agent run in the WORKTREE with an empty `outputs/`** — results were
  **void**; the reported "signal drought" was an artifact of the wrong root.

**Structural fix (shipped as law):** `USAGE.md` clause **(g)** — *re-derive, don't
recall, in-turn load-bearing numbers, **including my own earlier summaries***;
clause **(e)** — double-derive load-bearing counts by different routes and report
both if they disagree; and the **red-team panel** itself, whose whole purpose is
to make disagreement structural rather than optional.

---

### Two process classes worth naming separately

**Running or editing the tree during a battery.** Recorded in **three separate
summaries** — phantom failures, ~9 minutes burned each time, and explicitly noted
as *"the same class of mistake repeated twice."* Fix: frozen-tree discipline;
`TaskStop` a doomed battery pre-waste; park red-by-design tests out of the tree.

**Guessing an API instead of reading the module.** `PositionSizer({})` (real
signature needs `(config, profit_cfg, risk_cfg, ...)`); `om.snapshot()` where
`om.status()` exists; `record_close` vs `note_close`; `KrakenV2BookStream` vs
`KrakenBookAdapter`; `models.py` register-before-write (it hashes **from the
file**, so it cannot run pre-write); the **phantom-knob** `risk_management` block
that does not exist. `CLAUDE.md` already forbids it — *"no guessed APIs (read the
module first)"* — which is why it belongs here as a **discipline lapse**, not a
knowledge gap.

---

## 6. Contradictions and unresolved numbers

Recorded, **not resolved.** Both readings are given, plus what would settle each.

---

**C1 — Duplicate compaction summary; non-monotonic timestamps.**
`07_main_line9538.txt` and `09_main_line13171.txt` have **byte-identical bodies**
(verified by `diff`; both `CHARS=18873`, both `TIMESTAMP=2026-08-08T00:37:54.964Z`),
differing only in the `LINE=` header. File 09's timestamp **precedes file 08's by
~18 hours** despite sitting ~2,268 lines later in the transcript. Content
chronology is 07 → 08 → 10, with 09 == 07.
*Settled by:* treating file 09 as a re-emission of the 07 checkpoint. No action —
but any future transcript archaeology must not read `LINE=` as time.

---

**C2 — The round-number `arrival_ref` tell.**
- **2026-08-02T16:20Z:** treated as *the* diagnostic placeholder tell; "quarantined
  16 of 64 / kept 19 of 683" reported under that heading, with the status of the
  19 kept rows left open.
- **2026-08-05T21:12Z:** *"My own earlier round-number tell and 're-logged on
  restore' theory were both wrong — corrected in memory/wiki."* Recorded as one of
  three instances of substring-matching-where-identity-was-required.
*Settled by:* the later record presents itself as the correction. **But the 19
kept rows' disposition was never separately closed.** Re-run the audit-crossref on
those 19 rows against `audit.jsonl` to close it properly.

---

**C3 — `realized_total`: −208.22 vs −208.31.**
File 07/09 (2026-08-08T00:37Z) reads **−208.22**; file 10 (2026-08-09 11:46:10
bounce) reads **−208.31** [both ASSERTED]. Both are stated as live readings ~2
days apart. The summaries do not reconcile them.
*Settled by:* a snapshot-stamped re-read (`USAGE.md` clause c) plus the closes
between the two instants. Probably not a contradiction at all — but it is
recorded as one because neither source says so.

---

**C4 — `net_pnl_all_time` −382.4 vs `realized_net_all_in` −394.25, in ONE snapshot.**
Same readout block, differing by **11.85**. Definitions are given
(`net_pnl_all_time = total_equity − starting_capital`;
`realized_net_all_in = realized_pnl_total − entry_fees_total`) but the
reconciliation is **not stated**, and the prose asserts net all-in = **−$394.25
(−7.89%)** on the strength of one of them.
*Settled by:* deriving the 11.85 from unrealized + savings + reserve at that
instant. **This one matters** — the −7.89% headline in Phase 5 rests on which of
the two is the right measure.

---

**C5 — Fee totals across scopes.**
ADA incident **~$297**; open-leg fees **invisible to ALL P&L counters**
(`record_entry_fee` was cash-only) vs `fees_total` **382.59** / `entry_fees_total`
**185.94** / fees = **32.8×** |gross edge|. Different scopes (one incident vs
all-time), recorded but **not merged.**
*Settled by:* one reconciliation table from `fills.csv` splitting fee totals by
incident, by leg type, and by counter.

---

**C6 — Duplicate-vault page count: 90 / 88 / 115.**
- 2026-08-14: *"Wiki vault `C:\Users\haird\vaults\liquiditybot` — **90 pages**"*
- 2026-08-15: pending OPERATOR decision listed as *"**88-page** vault merge"*
- `USAGE.md` (current): *"**115 files, 88 basenames** canonical does not have"*
The three do not reconcile on their face; **88** appears in two different senses.
*Settled by:* one `Get-ChildItem -Recurse -Filter *.md | Measure-Object` against
the duplicate vault plus a basename-diff against canonical, both stamped.
**Do this before P7, not during it.**

---

**C7 — The status of `101f7436`.**
- Recorded as *"lying gates + matrix hardening"* — a **repair**.
- Recorded three days later: the wiki *"found the construct entered at
  `101f7436`"* — the same commit **introduced** a lying gate.
*Settled by:* `git show 101f7436 -- test_windows.bat`. Both readings can be true
simultaneously (it repaired two and introduced a third), and the later record
treats it as a retraction. **Consequence either way:** greens between `101f7436`
and `050421a7` are not evidence.

---

**C8 — The h432 `6/11` vs `recent-30` discrepancy.**
Left **UNADJUDICATED** by the 5-0 judge panel on 2026-08-08 and **never revisited
in any later summary.** Fee constants (37a) are held behind the h432 verdict, so
this open question is load-bearing for a blocked docket item.
*Settled by:* an operator adjudication, or by the era-4 readout superseding it.
**Flag: this may simply have been forgotten.**

---

**C9 — The loaded-row count: 314 / 346 / 347 / 348 / 349 / 352 / 353 / 358.**
- Code comment (`overfit_check.py:1118`): **346** [ASSERTED, CONCEDED as wrong]
- Live artifact on disk: **347** [VERIFIED]
- Re-measure at 18:28:29Z: **352** [VERIFIED], against a **byte-identical**
  `signal_history.csv` (8,324,656 B / 10,659 lines, mtime 17:00:34Z)
- Panel reconstruction from the CSV in append order: **353** at 17:00Z, with the
  count changing **exactly once** (348→349) in the commit hour
- Census of the deployed era: **358** rows — a **~6-row gap** the census cannot see
- Trajectory on 08-15 alone: **+39** (314@09:52Z → 353@17:00Z), with **three
  measured decrements** (08-13T17:00:25Z, 08-14T13:48:42Z, 08-14T15:39:34Z, each
  −1 via `ml/history.py:1573-1582` clash-dedup)
*Settled by:* OBJ-4/OBJ-7's pending disposition. The panel **deliberately did not
invoke the loader** because `store_for_config` → `HistoryStore._ensure_schema` can
**rotate the production CSV** (`ml/history.py:846,877`) — a write to the DATA root.
Falsifying the ~6-row offset requires running `overfit_check.py` against a
**scratchpad copy** at a matched as-of row index. **Do it that way or not at all.**

---

**C10 — The could-not-fire denominator: 7 of 13 vs 7 of 14.**
The panel said **7 of 13**; verification found **7 of 14** — the panel **missed the
`:955`/`:941` dof site** [VERIFIED]. Recorded as an amendment to the objection,
not to the author.
*Settled:* the verification number stands, but **both are recorded** because the
docket text still says 13.

---

**C11 — The gate's self-selection: −12.2% vs −2.3%.**
- 2026-08-02: *"gate selects against itself at **−12.2%**"* [ASSERTED]
- 2026-08-14 `outputs/gate_efficacy.md`: baseline **26.5%** [24.7, 28.5] n=2061;
  admitted **24.2%** [22.2, 26.4] n=1662; separation **−2.3%** — *"the gate selects
  AGAINST itself"* — but **"not significant at this sample size; intervals
  overlap"** [ASSERTED]
The direction agrees; the magnitude differs by ~5× and the later reading is
**explicitly non-significant.**
*Settled by:* re-running `gate_efficacy_report.py` with **effective n** (its SE is
optimistic by **×8.07** at uniqueness 0.0154), and by stating which population each
reading covered.

---

**C12 — Defender exclusion: "+6.9%" vs "within run spread".**
Measured cost **+6.9%** battery time, then **caveated as within run spread**. The
record is explicit that **the posture was adopted, not the number.**
*Settled by:* a repeated A/B at n ≥ 5 per arm against the **~391–413s** baseline
with the **>5% measured gain** threshold. Low priority — the security posture
decision does not depend on it.

---

**C13 — Cohort-contamination row count: 170 vs 6.**
A naive comma-split verification reported **170** mismatches; a real `csv` parser
gave **6**, matching the agent. Recorded verbatim: *"My method was wrong, not the
agent's."*
*Settled:* **6** is the standing figure (histogram `{17: 1059, 16: 6}`, rows
1038–1043). Recorded here because the 170 appears in the record and must not be
re-cited.

---

**C14 — `MIN_COHORT_N` and `ERA4_MIN_N` are two constants both equal to 50.**
`cohort_eval.py:79` and `:125` [ASSERTED]. Not a contradiction today — a
**Class-5 duplicated-quantity hazard** for the day one is changed and the other is
not.
*Settled by:* deriving one from the other, or a pin asserting equality.

---

**C15 — Unverifiable battery claims in the docket window.**
The panel could not assess `pytest 3687 / smoke 219-0 / assurance 48-0` — **no
artifact exists under the DATA root**; `outputs/` matching `smoke|assur|overfit`
yields `overfit_report.md` only, and its mtime **precedes the commit**. The
**3686 → 3687** delta is merely *consistent* with the one added test function.
**Nothing verifies that the other two suites ran.**
*Settled by:* running the DoD matrix and retaining the artifacts. Note the
battery-count trajectory across the record for context [all ASSERTED]:
3264 → 3292/1 → 3376/1 → 3423/1 @623s serial → ~400s parallel → 3427/1/1 @400.57s
→ "1 failed, 3444 passed" mis-reported as ALL GREEN (honest ~3457) → 3687.

---

**C16 — "Every overfit green since era exclusion" is untested, not refuted.**
No real-corpus GREEN in the 2026-07-26 → 2026-08-14 window exists on disk;
`outputs/overfit_report.md` is untracked and `git ls-files` returns nothing for it.
*Settled by:* nothing currently on disk. It requires either recovering an
artifact or restating the claim as unverifiable.

---

## Reading this document six months from now

Three things in here will age badly and one will not.

**Will age:** every number in Section 1 (re-derive, do not cite — clause g); the
open-item ordering in Section 4 (it is a snapshot of 2026-08-15); and the docket
status (12 of 16).

**Will not age:** Section 5. The defect classes have each recurred three or more
times across two weeks and two sessions, and the structural fixes that stuck —
AST pins, two-sided proof, rule 16, effective n, the delegated-measurement
contract, and the red-team panel — are all responses to a *class*, never to an
instance. That is the part of this program that is compounding.

The single sentence the record earns most: **a green is only as big as its
corpus**, and the corollary the docket added — **an instrument that cannot fail
is not evidence that anything passed.**
