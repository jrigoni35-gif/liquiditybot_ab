---
title: "The $800 Stressor Regime and the Capital Epoch (2026-08-10 evening) — Model Freeze, the Era-4 Verdict Gate, RP-072, and the Ledger That Defends Itself"
category: source
summary: "Seven pushed commits (2fee7f64 + d6112bca..a7dab725, all batteries green): the CAIO adjudication freezes model-side investment behind a pre-registered era-4 verdict gate (NO_GROSS_EDGE / COST_BOUND / CONTINUE at n>=50, written at n=1); the operator-adjudicated $800 stressor resets all money state at 2026-08-10T23:05:27Z with goals at $100/mo and the RP-072 x1.5 ratchet; the capital epoch is amended into the gate at n=3 before any new-regime data; the fills ledger gains exec_era provenance and the OM-085 restart-replay guard; and the challenge ordering audit finds the flatten-vs-resting-orders hazard and the escalation crash window (owed 64). POSTSCRIPT 2026-08-12: the reset sweep's completeness bugs grew a THIRD member found by casualty — the risk_protocols loss-budget anchors were not swept, and the un-re-anchored W33 week_anchor (4614.22) turned this reset into a 25-hour RP-041 total entry lockout (session-20260812-weekly-anchor-lockout; class page concepts/reset-completeness)"
tags: [session, stressor, capital-epoch, model-freeze, era-4-gate, goal-ladder, reset, provenance, moratorium]
sources: 2
source_path: repo commits 2fee7f64, d6112bca, 6fe6d98d, c60f9772, 43015031, 3a5fdab2, 38751d5b, a7dab725
source_date: 2026-08
authors: [operator, claude-session]
ingested: 2026-08-10
updated: 2026-08-11
---

# The $800 Stressor Regime and the Capital Epoch (2026-08-10 evening)

Seven pushed commits, every battery ALL GREEN, all re-verified against the box at filing
(`git log`, `core/codes.py`, `config.json`). Boundary statement per
[[concepts/paper-real-boundary|governance rule 13]]: everything here is **repo-side mechanism**
except the dollar figures, which are **sim-side** — the $800 is simulated capital, the $100/month
is a simulated goal, and the reset-verification numbers came from the live (dry-run) status. The
commit stamps are UTC-convertible local (`-05:00`); the capital epoch instant is stamped in UTC.

## 0. Earlier the same day, unfiled until now: `2fee7f64` (11:36:47Z)

Stamps execution-era boundary #4 with its **real UTC instant** in the shipped strings — the
`_doc` and `config_guard` comment that said "2026-08-09" now carry `2026-08-10T11:03:35Z`. This
**half-resolves the [[synthesis/documentation-drift-register]] 2026-08-10 row** (the
boundary-declaration disagreement); the row's other half — **XV-023 cited in circulation but
absent from `core/codes.py` — still stands at tonight's head** (verified: the registry stops at
`XV-022`; 193 codes registered).

## 1. The CAIO adjudication: MODEL FREEZE + the era-4 verdict gate (`d6112bca`, 22:24:02Z)

Operator adjudication of the CAIO review, verbatim: **"apply them."** The two applied rulings:

**MODEL-SIDE INVESTMENT IS FROZEN.** No new model families, features, tuning, or selection work.
The strategy go/no-go moves to a **pre-registered readout on the first honest-fill cohort** —
and that readout is the freeze's **ONLY unfreeze trigger**.

**THE ERA-4 VERDICT GATE**, registered in `scripts/cohort_eval.py` at **era-4 n=1 — the only
moment a stopping rule can be written without the data having a vote** (the same discipline as
the 2026-08-02 registration beside it, which is untouched):

- **Population cut:** `B4_TS` = `aeeaae36`'s UTC instant `2026-08-10T11:03:35Z` (execution-era
  boundary #4). Every earlier era carries the ~1.88x near-touch fill inflation and is **not
  citable for the verdict**. *(Amended same night by §8 — the cut is now
  `max(B4_TS, CAPITAL_EPOCH_TS)`.)*
- **Population definition:** entry-opened closed round trips **reconstructed from `fills.csv`**
  — the COMPLETE population, not the postmortem set (measured 2026-08-10: postmortem records
  only EV-underperformers, coverage 85.1%/93.1%, win rates biased LOW −1.5pp/−5.4pp — the caveat
  is now *printed* on the 432 sections rather than rewriting a registration mid-flight).
  Hedge-opened trips are reconstructed (**a hedge IS an opening leg**, per `415af0f9`) but
  **excluded from the verdict population** — insurance, not the thesis; the same
  `main.py:1671` split as the perf ledger.
- **Readout at n≥50, never before.** Three outcomes, none decided by the tool:
  **NO_GROSS_EDGE** (gross mean AND median ≤ 0) → the stop-strategy question goes to the
  operator; **COST_BOUND** (gross > 0, net ≤ 0) → the h432 fee levers become the live
  discussion; **CONTINUE** (net > 0). **The tool never decides — it names which decision has
  become decidable.**
- Accrual at registration: **1/50**, and that trade's gross (**+0.9619%**) matched the
  independent fills reconstruction exactly.
- Pinned by `tests/test_era4_gate.py` (9): registration constants including the UTC-instant
  boundary (**the exact error class that mis-stamped it the first time**), the 2026-08-02
  registration untouched, population rules (hedge excluded, pre-boundary excluded, still-open
  excluded, duplicate fill patterns dropped), refusal below n=50, all three readouts, empty
  cohort accrues rather than crashes. `cohort_eval.py` joins the
  `tests/test_opening_leg_pin.py` roster.

> **Why this matters more than any commit tonight:** the project's decision structure changed.
> Model work is no longer a permitted response to bad numbers; the only exits from the freeze
> are the three pre-registered readouts. See [[synthesis/comparability-boundaries]] for the cut
> the gate reads across, and [[synthesis/the-money-path-thesis]] for what the gate will
> adjudicate.

## 2. The ledger defends itself (`6fe6d98d`, 22:24:15Z) — owed 62 SHIPPED

CDO review, applied. The era-4 verdict rests on the next ~50 rows of `fills.csv`, a single
source whose documented history includes the exact corruptions that would matter most
(restart-correlated duplicates behind the 16x/27x headline error, a torn-tail fuse, the $6.24
fee gap). Two defenses, both at the write path:

1. **EXECUTION-ERA PROVENANCE** (`core/fill_ledger.py`): new `exec_era` column (`"4-aeeaae36"`),
   appended at the END per the file's own schema discipline. Four boundaries deep, era
   membership had lived only in a join between row timestamps and constants scattered across
   config prose — a training run pooling era-1 inflated-fill labels with era-4 honest ones
   would have done so invisibly. **The stamp travels WITH the row**; the constant bumps in the
   same commit as any future boundary. Header-aware append: a pre-schema file keeps ITS OWN
   width (never a ragged row); new columns reach an old file only via
   `scripts/migrate_fills_schema.py` — one-shot, idempotent, timestamped `.preschema` backup,
   REFUSES unknown columns, and **leaves old rows BLANK** — back-filling a guess would
   manufacture provenance the rows never had (blank = decide by ts against the boundary table).
   `outputs/fills.csv` migrated during the deploy restart window, backup retained.
2. **RESTART-REPLAY GUARD** (OM-085, **owed 62 — registered and SHIPPED the same day**): the
   ledger is fsync-durable PER FILL; order state is durable per SNAPSHOT. A kill between them
   restores a pre-fill order the sim re-executes, appending the same fill twice — the
   "duplicates correlate 1:1 with restarts" class every READER carried a dedupe against while
   nothing defended the WRITE. `append_fill` now refuses a row whose
   `(order_id, fill_size, fill_price, remaining)` already exists: `remaining` decreases
   monotonically within an order, so two LEGITIMATE fills can never collide while a replay
   collides exactly. Refusal logs **OM-085** (verified registered in `core/codes.py:116`),
   never touches the trade. A replay whose re-drawn partial differs is not caught — the
   readers' fill-pattern dedupe stays as the second layer.

`tests/test_fill_ledger_provenance.py` (9), on the REAL `ManagedOrder`/`FillEvent`. One
pre-existing fixture (`test_performance_records`) had appended the same fill twice as a header
vehicle — **the exact signature the guard refuses** — and now appends two genuinely different
fills ([[concepts/test-double-fidelity]] in miniature: the fixture's convenience was a
production defect's signature).

## 3. The gate readout carries its own epistemics + REST matrix + the moratorium (`43015031`, 22:37:50Z)

Three pieces, all measurement-layer — **moratorium-SAFE by the law this commit itself writes**:

1. **Challenge hardening #2 (added at n=2, pre-data — reporting, not rule change; the
   registration stands):** the era-4 readout prints the **SE of the mean gross** beside the
   mean, plus a **resolution note**: at n=50 with per-trade sd ~0.5% the SE is **~0.07%**, so
   only |edges| beyond **~0.14%** are resolvable — **an order of magnitude above every gross
   edge this strategy has exhibited** (−0.0019% per trade, t=−0.332). The gate is a
   pre-committed decision TRIGGER and now says so, so nobody reads a triggered readout as a
   measured effect size.
2. **`tests/test_rest_api_matrix.py` (33):** the non-security axes of the REST surface —
   response shape of every GET, both 404s, every body-validation branch of `/control`, the
   allowed-verb round trip, the auth-token matrix (secret never echoed), both 500 fault paths,
   and three Content-Length edges. **The negative Content-Length hang hypothesis was REFUTED
   empirically before the test was written** — `read(-n)` on a buffered stream looked like a
   thread-pinning primitive; it is not — and then **pinned so a refactor of the body read
   cannot regress it into one**. A hypothesis honestly killed and then fenced:
   [[concepts/adoption-is-not-enforcement]] applied to a *non*-bug.
3. **THE ERA-4 ACCRUAL MORATORIUM as binding law (challenge hardening #3), written into the
   repo's `CLAUDE.md`:** cohort-resetting changes (entry decisioning, sizing, fill sim, fee
   booking, order lifecycle) are **forbidden without operator adjudication, because they mint
   boundary #5**; measurement/boards/tests/wiki are safe; the accruing numbers are not a trend;
   the model freeze is cross-referenced. Written because tonight's culture is heavy retooling
   and the accrual window needs an explicit fence. Filed as
   [[synthesis/governance-doctrine|governance rule 17]].

**Challenge hardening #1 closed separately as an HONEST NEGATIVE:** the intra-poll fill bias is
**structurally unmeasurable from the existing recordings** — `get_order_book`/`get_tickers` are
recorded at **5.00s median cadence**, i.e. the recorder sits downstream of the SAME fast poll
the simulator uses and **cannot see between polls by construction**. A raw websocket book
capture (read-only, non-cohort-resetting) is the only instrument that could measure it —
**registered as owed 63**. Compare [[concepts/honest-coverage-gap]] and
[[concepts/honest-null-result]]: the instrument that cannot answer says so instead of answering.

## 4. The heartbeat test asserted one legal schedule, not the invariant (`c60f9772`, 22:24:15Z)

`test_c1_first_lost_heartbeat_latches_new_risk_off` flaked red under `-n 8` load: the heartbeat
thread latched `lock_lost` BEFORE the first loop iteration, the HALTED runner **correctly**
never cycled (a peer owns the lock), and `seen` stayed empty — which the old `is False` assert
read as failure. **A cycle that never runs places no orders, so that schedule SATISFIES the
invariant under test** ("new risk sealed at lost_count == 1"); only observing
`allow_new_risk=True` refutes it. The assert now tests the invariant (`is not True`) with both
legal schedules documented; 5x green serial. **The halted-runner-never-cycles schedule is the
SAFER outcome, and the test read it as failure** — same family as the bracket-exit repairs:
an assertion encoding one lucky schedule, exposed the first time conditions stopped being
generous ([[concepts/generosity-masks-fragility]]).

## 5. The probe tile goes BLUE (`3a5fdab2`, 22:48:05Z)

Design-token audit (ui-design-system pass). The probe expectancy tile used the **PNL steps
palette** (red below zero) while its own description says a probe's expectancy is **EXPECTED
slightly negative — probes buy information, not P&L** ([[concepts/pooled-populations]], owed
54's split made this legible). A state tile that sits red in normal operation trains **alarm
fatigue**; the money verdict lives in the conviction tile beside it. BLUE (neutral-info) steps;
one regeneration, JSON never hand-edited ([[entities/observability-sidecars]]).

**Audit verdict otherwise: the generator already IS the design system** — Apple dark-variant
semantic palette applied at generation time, **WCAG AA measured on the real hexes** (green
8.55:1, red 5.07:1, orange 8.41:1 on the panel ground), evidence-anchored thresholds. No other
change warranted.

## 6. THE $800 STRESSOR REGIME (`38751d5b`, 23:04:28Z)

**OPERATOR-ADJUDICATED**, verbatim: *"reset everything with equity back to $800. full clean
sweep of all money figures and make it trade to gain around $100 a month... putting it through
this stressor will see what we have right and what is completely wrong"* + *"as it starts to
succeed, scale the profits to the most it can stress every month."* **This message chain IS the
moratorium adjudication the repo's CLAUDE.md requires.** The sweep resets **MONEY STATE only**
— the corpus, fills ledger and every learning artifact are untouched
([[synthesis/governance-doctrine|governance rule 8]]: never delete learning data).

**The honesty line, filed with the change as it was said to the operator:** config can point
the goals ledger at $100/month and make the system measure against it honestly — **nothing here
makes a book with no measured gross edge EARN it.** The era-4 evidence
([[sources/session-20260809-unbiased-economics]]) says the likely outcome is **the truth
arriving faster and louder at $800, where every venue floor bites 6.25x harder. That is what a
stressor is for.** ([[concepts/unfalsifiable-explanation]] honored in advance: the stressor's
falsifier is the era-4 gate readout itself.)

**The rescale rule** (verified against `config.json` at filing):

| knob class | rule | instances |
|---|---|---|
| %-of-capital knobs | scale-invariant — **unchanged** | all |
| capital-USD literals | **×0.16** (they denominate OUR capital) | `starting_capital_usd` 5000→**800** · `monthly_profit_goal_usd` 350→**100** · `weekly_profit_goal_usd` 80→**25** · `risk_firewall.max_order_usd` 25000→**4000** (preserves 5x equity) · `execution.algos.engage_notional_usd` 1500→**250** (preserves ~30% equity) |
| venue floors | **UNSCALED, deliberately** — Kraken physics; at $800 the $15 min ticket is **1.9% of equity per ticket** and **the bite IS the stressor** | $15 min ticket/order/hedge |
| market-structure thresholds | untouched — they describe the venue, not the wallet | pool/depth/ADV floors |

**RP-072 GOAL LADDER** (`core/state.py`, `core/persistence.py`, `main.py`, `runner.py`,
`core/codes.py`): effective monthly goal = base × persisted `state.goal_ladder_mult`. A month
CLOSING at ≥100% of its EFFECTIVE goal ratchets the mult **×1.5** — **graded first, escalated
after, so a closed month is judged by the bar it was run under** (AST-pinned:
`RP_MONTH_CLOSED` (RP-071) precedes `RP_GOAL_ESCALATED` (RP-072) in `_close_periods`).
**Never de-escalates: the stress never relaxes.** Week grades at base (escalation is monthly by
directive). **Grading/telemetry only — no trading decision reads the mult.** Persisted (absent
on a pre-RP-072 snapshot → 1.0, clamped up); the runner exports the effective month goal +
ladder_mult so a board shows how many rungs were climbed rather than a target that silently
moved. Resets to 1.0 **only with a capital reset** — a multiplier, not a balance; zeroing it
would disable monthly grading entirely. `tests/test_goal_ladder.py` (7). RP-072 verified
registered (`core/codes.py:233`; registry now **193**).

**RESET-SCRIPT COMPLETENESS BUGS** (`scripts/reset_paper_capital.py`): `_MONEY_ZERO` was
missing TWO fields —

- **`monthly_realized_pnl`** — **predates the script; the monthly counter survived EVERY prior
  reset** (a pre-existing completeness hole, found only because this reset was audited).
- **`entry_fees_total`** — born 2026-08-09 (`a6334162`); a stale value would have carried
  **$185.94 of old-regime opening-leg fees into the fresh base** and broken
  `net_pnl_all_time = equity − start` on day one, because **persistence's backfill only fires
  when the key is ABSENT — a persisted stale value WINS.** The exact mirror of
  [[concepts/default-path-fallback-writes]]'s pin lesson: presence of a key is not presence of
  a guarantee; **a reset script's zero-list is a SCHEMA that must be maintained with the state
  it resets.**

Plus a **perf-window sweep**: the dollar-denominated rolling perf window would otherwise blend
6.25x-scaled regimes — [[concepts/pooled-populations]] on live boards.

> ⚠️ **THIRD MEMBER, found 2026-08-12 UTC by casualty
> ([[sources/session-20260812-weekly-anchor-lockout]]):** the sweep ALSO missed the
> `risk_protocols` **loss-budget anchors** — W33's `week_anchor` stayed at the pre-reset
> 4614.22, this reset read as an 82.7% in-week trading loss (1378% of the 6% weekly budget),
> and **RP-041 hard-vetoed all new risk for 25 hours** (118 candidates, zero entries) until
> the audited `budget_reanchor_week` repair. `reset_portfolio()` now re-anchors
> `day_anchor`/`week_anchor` in the same sweep (keys preserved), pinned in
> `tests/test_reset_paper_capital.py`. The "zero-list is a SCHEMA" rule stated above is now a
> named class with three members in three days — [[concepts/reset-completeness]]; the
> enumeration test that would close the class is **owed 72**.

**Deploy runbook** (as written into the commit): entries_off → flatten_all → wait flat →
`reset_paper_capital --yes` → verify → entries_on — hardened by §7 before execution.

## 7. The challenge ordering audit — three findings on the deploy sequence itself

An adversarial pass over the ORDER of operations, run before the reset executed:

1. **The ratchet consumes the grader's own "hit" verdict instead of re-deriving `>=` at a
   second site** — because two sites deriving one predicate drift silently, and this predicate
   is the grading surface the stressor is scored by. One derivation of "did the month meet its
   bar," consumed by both the grade record and the ratchet.
   [[concepts/two-paths-one-quantity]]'s **second prospective application** (the first was the
   OF-1/OF-7 shared predicate): the class applied at review time, before it could become the
   seventh instance.
2. **`_drive_flatten` exits POSITIONS ONLY — it never cancels resting entries.** A restored
   6h-TTL long-book bid sized for the $5000 regime could fill a **156%-of-equity position into
   the $800 book, past the $4000 fat-finger cap** — the cap gates order PLACEMENT, not a
   restored resting order's fill. **Deploy gate hardened: proceed only on
   `positions == 0 AND open_orders == 0`.** `open_orders` was 0 at deploy, so the hazard was
   **theoretical this time** — filed because the next reset will not re-derive it.
   ([[entities/long-book]] — the book whose design is to REST is the book a flatten forgets;
   compare [[concepts/protective-senior-overlay]]: an exit path that misses a whole order class
   is a hole in the overlay's seniority.)
3. **The crash window between month rollover and ratchet** — a crash after `RP_MONTH_CLOSED`
   commits but before `RP_GOAL_ESCALATED` fires loses the escalation. **Known-benign:
   detectable (RP-071 present without RP-072), conservative (under-escalates — the bar stays
   lower, the stress never overstates), documented not fixed.** Registered as **owed 64**.

## 8. THE CAPITAL EPOCH AMENDMENT (`a7dab725`, 23:19:20Z)

The reset executed **2026-08-10T23:05:27Z (epoch 1786403127)**, after `38751d5b` deployed.
Verified on relaunch, every figure exact:

```
equity 800.00 = starting_capital      net_pnl_all_time 0.0
entry_fees_total 0.0   realized_net_all_in 0.0   fees_total 0.0
goals week 25 / month 100 / ladder_mult 1.0
perf window 0 trades   positions 0
```

`scripts/cohort_eval.py` gains **`CAPITAL_EPOCH_TS`** at that instant; the era-4 verdict
population cut becomes **`max(B4_TS, CAPITAL_EPOCH_TS)`**. The **3 closes accrued between
boundary #4 and the reset were $5000-regime trades: honest fills, wrong capital regime** — the
$15 venue floor was **0.3% of equity** for them and is **1.9% now**, which shifts the gross%
distribution through sizing floors. **One cohort, one regime. Accrual restarts 3/50 → 0/50.**

**AMENDED AT n=3, BEFORE ANY NEW-REGIME DATA EXISTED:** the book was flat and entries were OFF
across the reset instant (the deploy kept them off until this commit landed), so the boundary
has **zero in-flight ambiguity — no trade can straddle it or precede its own definition.** The
registration's RULES (n=50, NO_GROSS_EDGE / COST_BOUND / CONTINUE) are unchanged; **only the
population start moved, and only forward.** Tests pin the epoch's exact UTC instant beside
B4's and add the discriminating case: a post-#4 but pre-epoch trade (honest fills, wrong
regime) must be excluded.

> **Why the amendment is legitimate where mid-flight rewrites are not:** it excludes data that
> existed at amendment time in the STRICTER direction (3 accrued closes dropped, none added),
> it was committed before any trade of the population it defines, and entries stayed OFF until
> it landed. Compare the 2026-08-02 XV-021 boundary, which had to be read ACROSS 11
> already-earned closes — this one was cut where the knife could not touch data.

## 9. Housekeeping, filed so it is not re-investigated

- **Orphan `ui/__pycache__` `.pyc` of the RETIRED Streamlit console** explained + removed:
  source deleted (the 2026-08-07 venv prune, [[sources/session-20260807-closing-batch]] §4),
  gitignored, unimportable — a compiled ghost of a module that no longer exists.
- **XV-023 remains unregistered** in `core/codes.py` at tonight's head — the
  [[entities/reason-code-registry]] finding stands unchanged.
- Registry count: **191 → 193** (OM-085, RP-072).

## Owed-register deltas from this session

- **62** — fills.csv restart-replay duplicate guard: **registered and SHIPPED same day**
  (`6fe6d98d`, OM-085).
- **63** — raw websocket book capture (the ONLY instrument that can measure intra-poll fill
  bias): **REGISTERED**, not started; read-only, non-cohort-resetting.
- **64** — escalation-loss crash window: **documented, deliberately unfixed** (benign,
  detectable, under-escalates).
- **61** — unchanged OPEN; the moratorium (§3.3) now explicitly fences its fix behind operator
  adjudication, because wiring the depth constraint mints an era boundary.

## Related

[[synthesis/comparability-boundaries]] · [[synthesis/owed-measurements]] ·
[[synthesis/governance-doctrine]] · [[synthesis/risk-posture-doctrine]] ·
[[synthesis/the-money-path-thesis]] · [[concepts/paper-real-boundary]] ·
[[concepts/two-paths-one-quantity]] · [[concepts/pooled-populations]] ·
[[concepts/generosity-masks-fragility]] · [[entities/long-book]] ·
[[entities/reason-code-registry]] · [[sources/session-20260810-fill-double-count]]
