---
title: "The Second Hedge Churn and the Churn Guards (2026-08-07) — Cold Correlation Must Never Buy New Risk"
category: source
summary: "Commits 42f6cc61+9b1eb6a5 (HANDOFF + deadlock discipline), cf454d5e (fix, authored by the CLOUD session), af544d4c (the vacuous test repaired), 21769fb8 (stand-down). PANEL-CORRECTED 2026-08-07: the 01:09:45-01:34:19Z '147-lap incident #2' IS the hedge-thrash page's event under UTC (one event, double-filed; it ran on PRE-5c111962 code — D3 committed 01:53Z, after it ended), and TWO mechanisms are confirmed: wrong-pair + cold-0.0 EWMA flap (|rho|~1 at 2 samples: open passes; 0.0 at variance<=EPS: unwind fires) set the 10s lap rate, and the open-on-delta vs unwind-on-corr disagreement outlived the pair fix as 12 residual warm-correlation laps (01:56Z-11:35Z, corr 0.34-0.55) until cf454d5e's guards; cf454d5e's circulated record is false on four verified counts (see 6bis). Fix per the operator's DEADLOCK DISCIPLINE: guards on the OPEN side only (corr_min_samples 12, rehedge_cooldown_sec 600, FW-070 latch 3-in-900s with auto-release on window+warm), unwinds NEVER gated; guard clocks ride the snapshot; estimator sample counts do NOT (HANDOFF rule 3 half-shipped — owed). Deploy-gate battery on the merged tree 3423/1; zero hedge fills since."
tags: [session, incident, hedging, defect-class, cold-start, deadlock, churn-breaker, reason-codes, cross-session]
sources: 3
source_path: none — session work product (see Provenance); handoff doc at repo docs/quant/2026-08-07_ada_hedge_churn_HANDOFF.md
source_date: 2026-08
authors: [claude, claude-cloud-session]
ingested: 2026-08-07
updated: 2026-08-08
---

# The Second Hedge Churn and the Churn Guards (2026-08-07)

> ⚠️ **SUPERSEDED IN PART — 2026-08-07 institutional review
> ([[sources/session-20260807-institutional-review]] §B/§D).** Four corrections travel with
> this page:
> **(1) "INCIDENT #2, hours after #1's fix" is false on the ledger.** The 01:09:45–01:34:19Z
> window IS the event [[sources/session-20260806-hedge-thrash]] filed in local time as
> "08-06 20:09–20:34" — **one 147-lap event, double-filed under two clocks** (all 159 lifetime
> hedge fills are 08-07 UTC; equity 4,933.68 at 08-06 23:59:50Z). And the churn ran on
> **pre-`5c111962` code**: D3 was committed 01:53:17Z — *after* the fast laps ended — and
> deployed 02:08:09Z. So §1's "5c111962 held" is wrong for the main event: the wrong-pair
> unwind was still live, alongside the cold EWMA.
> **(2) Two mechanisms, panel-confirmed:** the wrong-pair + cold-0.0 defect set the ~10s lap
> rate of the main event; the **open-on-delta vs unwind-on-correlation two-variable
> disagreement (no shared deadband) outlived the pair fix** — this page's own "slow-lap tail"
> (12 laps, 01:56Z–11:35Z, corr 0.34–0.55 **warm and genuine**) is that second mechanism, not
> an estimator warming curiosity.
> **(3) The circulated record of `cf454d5e` is false on four verified counts** — §6bis below.
> **(4) All dollars here are simulated** — [[concepts/paper-real-boundary]]; the churn's
> paired gross was **−13.37** (~95.7% fees), not 0.00.

## Provenance

Five commits, three sessions, one file's disease. Head = remote = **`21769fb8`**. Chronology
(all times UTC):

| Commit | When | What |
|---|---|---|
| `af544d4c` | 02:20Z (during the incident night) | **test: make the hedge-convergence test actually fail on the buggy engine** — closes owed item 34(b), the vacuous test flagged by the 08-06 filing |
| `42f6cc61` | 10:54Z | **HANDOFF doc** to the VS Code session: full evidence, root cause, three-part fix spec, acceptance criteria (`docs/quant/2026-08-07_ada_hedge_churn_HANDOFF.md`) |
| `9b1eb6a5` | 10:57Z | **DEADLOCK DISCIPLINE** appended to the same doc — operator directive, supersedes the spec's naive "hold state" wording ([[concepts/deadlock-discipline]]) |
| `cf454d5e` | 18:46Z | **the fix — authored by the CLOUD session** ("Complete this task" mid-flight reassignment), implementing the handoff exactly per the discipline |
| `21769fb8` | 20:59Z | resolution notice + **VS Code session STAND DOWN**, "appended to the same doc the VS Code session reads so two writers never meet on the hedger — which is this incident's own disease" |

**Deploy, verified from `outputs/auto_update.log`** (log clock is local = UTC−5): poll at
**18:53:34Z** found the new commit → **incoming-code battery on the merged tree: rc=0,
3423 passed / 1 skipped in 536.90s** → replay gate `XV-000` clean (3 recordings, determinism +
reconciliation) → **updated `9b1eb6a5` → `cf454d5e` at 19:04:16Z, battery-verified**, runner
clean-restarted on the new code. The cloud session's own battery at `cf454d5e` was **pytest 3424 ·
smoke 219 · assurance 49 · ruff · pyright 0 · bandit 0 · compileall**.

**Every number below re-verified at filing time** (23:02Z) from `outputs/fills.csv`,
`outputs/status.json`, `outputs/state.json`, `outputs/auto_update.log`, and the shipped source —
not copied from commit messages. Paper mode (`DRY_RUN`), same qualification as
[[sources/session-20260806-hedge-thrash]]: orders and mechanism real, dollars simulated at the
deliberately conservative taker constant.

---

## 1. Incident #2, measured — hours after incident #1's fix shipped

**Window:** 2026-08-07 **01:09:45Z → 01:34:19Z** (audit trail: 147 consecutive PT-061 closes of
the same ADA hedge, one every ~10 seconds — every one stamped `hedge unwind: correlation 0.00
below floor`, each −$1.0 to −$3.4, summing **−$318.27**).

Re-derived from `fills.csv` at filing:

| Quantity | Measured |
|---|---|
| Fills in 01:09–01:34Z | **290** = 145 hedge opens + 145 unwind exits, all ADA/USD, `post_only=0` on all |
| Fills in the wider 00:50–02:00Z window | **296** = 148 opens + 148 exits; **147** carried `correlation 0.00 below floor` |
| Fees in that window | **$296.93** — open-leg **$149.83** + exit-leg **$147.10** |
| Notional churned | **$74,232.29** on a ~$4,933 book |
| Equity cliff (HANDOFF, 00:56–02:56Z) | **$4,933.24 → $4,614.69 (−$318.55)** |
| Cadence | one lap per ~10s — every second fast cycle |

**Proof it was cold-start, not market** (HANDOFF, verified in `fills.csv`): at
02:01/02:24/02:34/02:44Z the same check fired four **isolated** unwinds with correlation
**0.34/0.46/0.55** — the estimator warming out of its post-restart reset (restarts logged ~01:00Z).
The churn then continued as a **slow-lap tail**: nine more open/unwind laps between 02:19Z and
07:00Z at 5–90-minute spacing, and a final lap at **11:31:01 → 11:35:31Z** (`correlation 0.10
below floor`). **That 11:35:31Z unwind is the last hedge fill in the ledger.**

> ⚠️ **This was NOT a recurrence of the 08-06 two-paths bug.** `5c111962` held: both paths read
> `corr(dominant, hedge_asset)` — the same pair. What oscillated was the **reading itself**: a
> COLD post-restart EWMA flaps between **|rho|≈1** (a 2-sample estimate — the open's floor
> passes) and **0.0** (variance ≤ EPS or missing pair — the unwind's floor fires). One quantity,
> one path, two artifact values on opposite sides of the same 0.55 floor
> ([[concepts/zero-is-not-a-reading]]). The unwinder and re-hedger shared no state to notice
> they were disagreeing every cycle — **owed item 34(c), "no churn breaker anywhere," filed
> ~12 hours earlier, fired before it could be closed.**

## 2. The operator directives, verbatim

- *"That is a explicitly terrible problem I never wanna have again."* (42f6cc61)
- *"I don't want to deadlock anything so take that into account."* (9b1eb6a5) — this one matters:
  the HANDOFF's own first fix spec ("below a minimum sample count, the floor check must HOLD
  STATE") was itself **the week's 4th instance of a gate whose release depends on the thing it
  blocks** — with median PC uptime 0.5h, an estimator that resets on restart can be perpetually
  cold, and a held unwind becomes a hedge frozen forever. The superseding **five-rule deadlock
  discipline** is filed as [[concepts/deadlock-discipline]].

## 3. What shipped (`cf454d5e`) — guards on the OPEN side only

- **`regime/correlation.py`** — `CorrState.samples` + `pair_samples(a,b)` = min of the two
  assets' EWMA observation counts, the **evidence-quality signal the open gate reads**. Its
  docstring states the class fix exactly: *"A 2-sample EWMA reads |rho|~1 and a missing pair
  reads 0.0 — BOTH are artifacts… so consumers gate on this count, never on the rho value's
  plausibility."* **EMPTY samples dict = legacy "warmth untracked"** → `pair_samples` returns
  `_WARM_ASSUMED` (10^9), keeping every pre-existing caller/stub/restored-snapshot
  **byte-identical** (pinned by test).
- **`execution/hedging.py`** — three guards consulted **only** on the open path
  (`_open_blocked` is never on the unwind path; unwinds only *record*):
  1. **warmup**: open requires `pair_samples(exposed, hedge_asset) >= corr_min_samples` (**12**
     update ticks — reachable well inside the 0.5h median uptime, per discipline rule 4);
  2. **cooldown**: `rehedge_cooldown_sec` (**600**, config) per asset after ANY unwind;
  3. **churn latch**: ≥ `churn_max_unwinds` (**3**) inside `churn_window_sec` (**900s**) latches
     the asset — **FW-070**, registered — and **auto-releases on window-elapsed + estimator-warm**:
     time and evidence, both accruing regardless of hedging activity, **never the gated action**.
  Guard clocks (`last_unwind` / `unwind_ts` / `latched`) ride the snapshot via
  `to_dict`/`from_dict`.
- **`core/persistence.py`** — `hedger` section beside `monitor`, hasattr-guarded (QA stubs
  snapshot bots without a hedger), its own try so a hedger failure cannot masquerade as "monitor
  malformed". **Verified live: `state.json` carries the section** (empty dicts — no unwinds since
  the 19:04Z boot).
- **`core/codes.py`** — `FW-070 FW_HEDGE_CHURN_LATCH`, **registry 184 → 185**
  ([[entities/reason-code-registry]]).
- **`core/config_guard.py`** — bounds for all four knobs, each FATAL message carrying its
  deadlock rationale (e.g. `corr_min_samples > 1000`: *"warmup exceeds any plausible uptime (p90
  is 4h) and re-hedging deadlocks on a healthy book"*), plus the coherence FATAL
  **cooldown < window** — *"with the cooldown at/past the latch window the rate-latch can never
  observe enough unwinds to fire and the backstop is structurally dead."* **This FATAL caught the
  cloud session's OWN first config (900 ≥ 900) on its first battery run** — the guard worked
  before it shipped ([[entities/config-guard]]).
- **`main.py`** — threads the cycle's `now` into `evaluate()` (deterministic replay; `now=0.0`
  default makes every guard a no-op for legacy callers). Also rode along: 3 pre-existing pyright
  errors in shipped scope fixed (take_deferred seam ×2, `core/skimmer.py` float(None)) — the
  CLAUDE.md ratchet back to **zero**.
- **`tests/test_hedge_churn.py`** — 8 tests, written RED first, including **both HANDOFF
  acceptance cases**: the cold 01:09Z flap produces zero opens, and **the warm 02:01Z-shape
  low-correlation unwind still fires** (the guard must not become a rubber stamp for unwinds).

## 4. The test repair (`af544d4c`) — owed item 34(b) closed, with a technique worth keeping

The 08-06 filing proved `test_open_and_unwind_agree_across_repeated_evaluations` — docstring:
*"the actual money bug"* — was **vacuous**: green against the pre-fix engine, because it
evaluated a book it never mutated. Repaired: `_run_loop` now drives the engine **the way the
runner does — evaluate, APPLY the returned actions to the book, evaluate again** — and its own
docstring records the lesson (*"Applying the actions is the whole point: the thrash only exists
across cycles"*). Verified against the **genuine pre-fix engine**, loaded from
`git show 0e30ca09:execution/hedging.py` into a scratch module so the live tree was never
reverted:

```
PRE-FIX  over 25 cycles → opens: 13  unwinds: 12   ['open','unwind','open','unwind',…]
POST-FIX over 25 cycles → opens: 1   unwinds: 0
```

The alternating sequence is the production incident in miniature. A second case pins the live
trigger directly: a **cold correlation matrix must also converge** — the property is not which
branch wins but that the two decisions cannot oscillate.

> **Technique note, filed to [[concepts/adoption-is-not-enforcement]]:** the earlier red-check
> (`git stash push -- execution/hedging.py`) was a **no-op once the fix was committed** — that
> run compared the fixed engine against itself. **Loading the parent blob as a separate module is
> the correct red-check when the code under test is already at HEAD.** Design rule 5
> ("prove the gate bites"), stated 08-06 and not applied on 08-06, is now discharged for this
> test — one day late and by a different author, which is what a written residual is for.

Battery at `af544d4c`: 3415 / 1 skipped, smoke 219, assurance 49.

## 5. Verified aftermath — quiet, so far

- **Last hedge fill: 11:31:01Z; last unwind: 11:35:31Z** — both pre-fix. Fix live **19:04:16Z**.
- **Zero fills of ANY kind since 12:35:00Z** (an ETH tier-trail exit) through the 23:02Z status —
  so the guards have **~4 hours live without a hedge order**, but note honestly: the tape had
  already gone quiet at 11:35Z on its own (estimator warm, corr readings 0.10–0.55 hovering at
  the floor), so "quiet since deploy" is **consistent with the fix, not yet a measurement of it**.
  The discriminating observation arrives at the next cold restart with a live hedge.
- Both hedger fixes coexist at HEAD: `5c111962`'s shared `_exposure_by_asset()` (agreement) +
  `cf454d5e`'s evidence/cooldown/latch guards (stability under cold estimators).

> **5bis. The churn's LAST bill arrived 08-08 — the incident outlived both of its fixes by a
> day** ([[sources/session-20260808-budget-reanchor]]). The churn's ~$303 of simulated W32
> fees had consumed **109% of the weekly loss budget** (equity-anchored on the persisted
> Monday anchor $4,940.59, so **no restart clears it**): `taper_mult` 0.0, **all entries
> blocked** on 08-08 with the natural release only at the W33 rollover — a lockout enforced by
> a healthy protective layer on the basis of damage a **dead bug** did. Resolved by operator
> order via the new audited verb `budget_reanchor_week` (`f07d60f8`, RP-042, reason
> mandatory): re-anchored at $4,617.00 at 13:13 local, `weekly_used` 1.09 → 0.000x, taper
> restored 1.0, **`weekly_pnl` −173.36 untouched** — the proof the ledger was never edited.
> Lesson attached to this incident's page because it belongs to the incident: **a churn
> event's cost has a tail in every stateful layer that consumed it** — the fills stopped
> 11:35Z 08-07; the budget was still punishing the book 26 hours later.

## 6. Corrections and residuals — verified, not asserted

1. > ⚠️ **CORRECTION to this session's own headline: the estimator's sample counts are NOT
   persisted.** HANDOFF deadlock rule 3 explicitly required it (*"Persist the correlation
   estimator's sample count too — otherwise every 15-min deploy re-colds it and rule 1's 'waits
   for warmth' starves re-hedging on a healthy book"*). Verified: `samples` appears **nowhere in
   `core/persistence.py`**; `hedger.to_dict()` carries only `last_unwind`/`unwind_ts`/`latched`.
   So the **guard clocks survive restart; the warmth does not** — every boot re-colds the
   estimator and the 12-tick warmup is re-earned per process life (median uptime 0.5h; the knob
   was sized for exactly this, rule 4). **Direction safe** — a cold estimator blocks *opens*
   only; unwinds are untouched. Boot corner, also verified: at process start `samples` is empty
   → `pair_samples` returns warm-assumed (10^9) — but `corr()` reads 0.0 < 0.55 on an empty
   estimator, so opens stay blocked anyway; after the first update tick the counts are real and
   the warmup gate takes over. Two in-domain sentinels landing on opposite sides of the gate,
   with the safe one winning ([[concepts/zero-is-not-a-reading]]). **Owed item 35(a).**
2. **The FW-070 latch is telemetry-dark.** One `log.warning` on latch and one on release —
   **no gauge, no panel, no alert**; verified by grep of `scripts/gc_pusher.py` (the firewall
   latched-fault gauge is a different mechanism). The HANDOFF's own fix part 3 said "surface on
   the incident board"; that half did not ship. **Task #148** (>2 unwinds/hour on ANY asset =
   the class-level alarm) is owned by the cloud session per the resolution notice. **Owed item
   35(b).**
3. **Stale comment shipped in the fix:** `execution/hedging.py:75` annotates the latch dict
   `# asset -> latch ts (FW-060)` — the actual registered code is **FW-070**; FW-060 is
   `FW_NO_REFERENCE`. Cosmetic, but it is the audit-trail vocabulary pointing at the wrong
   registry entry → [[synthesis/documentation-drift-register]].
4. **Defaults corner, recorded not owed:** the code defaults are
   `rehedge_cooldown_sec=900.0` = `churn_window_sec=900.0`, which the guard's own coherence rule
   forbids — a config omitting both keys **FATALs at boot** (loud, fail-closed; the live config
   sets 600 < 900). Same shape the cloud session hit on its first battery run.
5. **Still open from 08-06:** 34(a) — no gate for the two-paths class (the shared helper remains
   a convention); 34(d) — the hedge asset is still chosen alphabetically.
6. **Post-panel addendum (2026-08-07 capacity sweep): the record's battery line did not hold on
   the pulled tree.** The circulated `ruff · pyright 0` was not reproducible on the production
   box: this commit's own **hedger snapshot section** grew `core/persistence.py` `restore()`
   past the C901 limit (**42 > 40**), so **full-scope ruff on the live tree was RED** —
   unnoticed because nobody ran full-scope ruff after the pull, *and* the local battery's
   pyright stage had been printing **`SKIPPED` for weeks** (the tool was never installed).
   Both repaired in `00bd0e52`+`101f7436`: `_restore_subsystem_sections` extracted per the
   file's own convention; the bat now hard-fails on a missing tool; pyright 1.1.411 in-venv,
   0 errors on shipped scope. The record certifies the cloud environment, not this box
   ([[sources/session-20260807-capacity-sweep]] §1, [[concepts/false-green]]).

## 6bis. Panel adjudication (2026-08-07 institutional review): the record vs the code

The 5-judge panel put `cf454d5e`'s **circulated record** (HANDOFF resolution + this page's
original summary) at **false on four verified counts** — the commit message itself is honest
("byte-identical behavior for restored snapshots"); the record is not
([[sources/session-20260807-institutional-review]] §D):

1. **"Estimator sample counts ride the snapshot" — never shipped.** This page's own §6.1
   correction, now **triple-verified** by independent judge greps (no `to_dict`/`from_dict` in
   `regime/correlation.py`; persistence carries guard clocks only; engine rebuilt at boot).
2. **The guards gate TRIMS.** §3's "consulted only on the open path" is incomplete: the warm
   check and `_open_blocked` sit **above** the trim block (`hedging.py:239-291`), suppressing
   the delta-reducing partial exit that `main.py:2634-2646` classifies *"risk REDUCTION, never
   gated."* Reproduced live by a judge; re-verified at filing. Fail-safe direction, but the
   code contradicts its own comment and arguably invariant 5.
3. **"Reachable well inside the 0.5h median uptime" is false at the floor.** 12 samples ×
   `candle_refresh_sec` 150s = **30 min = exactly the median uptime** (`main.py:4041` passes
   no `bar_ts`). With (1), roughly **half of process lives never reach warm** — post-churn
   hedging and trimming are structurally unavailable for an unquantified fraction of wall time.
4. **The deploy-gap timeline** — see the banner: pre-D3 churn, post-D3 residual laps for ~17h,
   and an owed **interim-containment rule** (`hedging.enabled` was a one-line toggle nobody
   flipped while the fix was in flight).

## 7. What this session changes elsewhere in the wiki

- **NEW [[concepts/deadlock-discipline]]** — the five operator-directed rules, with this fix as
  the first mechanism built to them and the week's four self-blocking gates as the type instances.
- **[[sources/session-20260806-hedge-thrash]]** — sequel section: residual (c) fired within ~12
  hours; (b) and (c) now closed.
- **[[concepts/zero-is-not-a-reading]]** — the second live firing, and the class fix: gate on the
  evidence count, never on the value's plausibility; the |rho|≈1 under-sampled artifact joins the
  0.0 sentinel.
- **[[concepts/two-paths-one-quantity]]** — the boundary of the class demonstrated: agreement
  held and the loop recurred anyway via an oscillating reading.
- **[[concepts/adoption-is-not-enforcement]]** — rule 5 discharged late for the vacuous test +
  the parent-blob red-check technique.
- **[[concepts/protective-senior-overlay]]** — the invariant applied under incident pressure:
  unwinds never gated, all three guards on the open side.
- **[[synthesis/owed-measurements]]** — 34(b)/(c) closed; new item 35.
- **[[entities/reason-code-registry]]** — FW-070, 184 → 185.
- **[[entities/liquiditybot]]** — status block.
- **[[synthesis/documentation-drift-register]]** — the FW-060 comment row.

## Re-measured 2026-08-09 — the guards held, and the event's true share of lifetime cost

([[sources/session-20260809-turing-test-hedge-verdict]] §2.)

**The guards held: no recurrence in 56.5h.** That is the first affirmative statement this page can
make about the fixes — previously it could only report that they had shipped.

**And the event's cost now has a denominator:** **$289.73** in fees over **147** matched 2-leg
round trips on **$36,210** notional (gross **−$12.77**) = **77.3% of ALL lifetime fees**
(**$374.96**). **59** of the trips were held at exactly **5.000s**.

⚠️ **This page's own window figure is NOT superseded — it is a different population.** This page
records **$296.93** (open-leg $149.83 + exit-leg $147.10) over **290 fills** for
**01:09:45–01:34:19Z**, with **296** fills in the wider 00:50–02:00Z envelope. The **$7.20**
difference from the round-trip figure is **consistent with** unmatched or out-of-window legs being
excluded from the 147 matched pairs — **an inference, not a measurement**, and filed as such in
[[synthesis/open-contradictions-register]] entry **19**. *What would close it:* itemise the fills
in the wider window excluded from the matched pairs.

**Related and still open:** the whole hedge book — **159** round trips, **0 of them profitable NET
of fees** — remains invisible to the performance ledger and the consecutive-loss circuit breaker
(owed **52**). The breaker counterfactual is now measured: counting hedges would have **stopped
this event after 4 round trips instead of 147**, at a cost of **+1 breaker trip in 19.5 days**.
**The adjudication is still the operator's** ([[concepts/never-widen-a-gate]]).

## Related
[[sources/session-20260809-turing-test-hedge-verdict]] ·
[[synthesis/open-contradictions-register]] · [[concepts/priced-bleed]] ·
[[concepts/never-widen-a-gate]] · [[concepts/ratio-aggregation-bias]] ·
[[sources/session-20260806-hedge-thrash]] · [[concepts/deadlock-discipline]] ·
[[concepts/zero-is-not-a-reading]] · [[concepts/two-paths-one-quantity]] ·
[[concepts/adoption-is-not-enforcement]] · [[concepts/protective-senior-overlay]] ·
[[concepts/iron-law-of-debugging]] · [[concepts/probe-livelock]] · [[concepts/deploy-deadlock]] ·
[[entities/config-guard]] · [[entities/reason-code-registry]] · [[entities/auto-update]] ·
[[entities/liquiditybot]] · [[synthesis/owed-measurements]] ·
[[synthesis/documentation-drift-register]] · [[sources/session-20260807-pnl-reconciliation]] ·
[[sources/session-20260807-institutional-review]] · [[sources/session-20260807-capacity-sweep]] ·
[[concepts/paper-real-boundary]]
