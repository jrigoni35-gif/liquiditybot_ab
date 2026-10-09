---
title: "The Weekly-Budget Lockout and the Audited Re-Anchor (2026-08-08) — Bug-Attributable Consumption Gets Its Own Verb"
category: source
summary: "The ADA hedge-churn class's last bill arrived days after its fix: ~$303 of simulated churn fees inside ISO week 2026-W32 drove weekly_budget_used_frac to 1.09 against the persisted Monday anchor ($4,940.59, re-verified from equity.csv), taper_mult 0.0 blocked ALL entries, and no restart could clear it — only the natural W33 rollover would, losing the whole weekend. Operator ordered a proper mechanism ('do it properly without injecting it funky'): f07d60f8 ships ControlChannel verb budget_reanchor_week — RiskProtocolStack.reanchor_week(equity) re-anchors ONLY the persisted week anchor (weekly_pnl/pools/day-budget/learning data untouched, natural ISO rollover preserved), reason REQUIRED, audited RP-042 (registry 186→187), registered in BOTH vocabulary halves (the silent-drop drift class), deliberately ABSENT from REST ALLOWED_CONTROL (arm_live posture), pinned by tests/test_budget_reanchor.py — 8 tests (the batch claimed 9; collection says 8). Executed live 13:13:10 local: re-anchored at $4,617.00, weekly_used 1.09→0.000x, taper 0.0→1.0, audit seq 37983 hash-chained with equity+reason, weekly_pnl −173.36 UNCHANGED — the no-ledger-touch proof. One filing correction: 'the week was net POSITIVE without the bug' is a hair too strong on the box's numbers — week equity drop $323.6 vs ~$303 attribution leaves ≈ −$21, flat; the LOCKOUT (1.09 vs ~0.07, taper 0.0 vs 1.0) is 100% bug-attributable either way. Plus: with 050421a7's honest gate live, the ship cycle's batteries went red-clean-red on ROTATING load-marginal timing tests, each red solo-green — the family is now the batteries' binding constraint (owed 44: split parallel/serial); and docket 41a's freeze-gate tests are written and PARKED in the session scratchpad. SECOND FIRING 2026-08-12 UTC: the weekly-budget-poisoned class recurred ANCHOR-side — the $800 capital epoch zeroed money ledgers but left W33's anchor at 4614.22, a phantom 82.7% 'loss' = 1378% of budget, RP-041 hard veto, 25h/zero entries from 118 candidates — and this verb executed the repair in one minute (second use, audit seq 44429, equity 800.0); see session-20260812-weekly-anchor-lockout."
tags: [session, incident, risk-protocols, budgets, control-channel, operator-override, audit, hedge-churn, gates, flakes, ops]
sources: 3
source_path: none — session work product (operator-dictated docket, every item re-verified against the box at filing)
source_date: 2026-08
authors: [operator, claude-session]
ingested: 2026-08-08
updated: 2026-08-11
---

# The Weekly-Budget Lockout and the Audited Re-Anchor (2026-08-08)

> **SECOND FIRING — 2026-08-12 UTC ([[sources/session-20260812-weekly-anchor-lockout]]).** The
> weekly-budget-poisoned class recurred with the poison on the **other side**: here the
> *consumption* was poisoned (a dead bug's real fees) against a true anchor; there the *anchor*
> was poisoned (the $800 capital reset zeroed money ledgers but never re-anchored W33's
> 4614.22) against zero consumption — a phantom 82.7% "loss" = 1378% of budget, RP-041, **25
> hours, zero entries from 118 candidates**. The verb built in §3 executed the repair in one
> minute (**second use**: audit seq 44429, equity 800.0, bug-attribution reason — vs first use
> seq 37983 below); every design constraint (reason required, RP-042 audit, keys preserved,
> no-ledger-touch) paid unchanged. The class pages are
> [[concepts/calendar-anchored-state]] and [[concepts/reset-completeness]].

## Provenance and boundary statement

Operator-dictated docket, filed same session; **every claim below re-verified against the box at
filing** — `git show f07d60f8`, `risk/protocols.py` / `runner.py` / `core/runtime.py` /
`core/codes.py` / `api/rest_server.py` read at the cited lines, `pytest --collect-only` on the
new test file, `runner.log:24540`, `audit.jsonl:37995`, `outputs/status.json`,
`outputs/equity.csv` (Monday-open anchor), `config.json:233-234`, and the scratchpad parked
file's existence. **Two of the docket's claims failed exact verification and are corrected
here** (§2 the net-positive arithmetic, §3 the test count) — preserve the box's numbers.

**Paper/real boundary** ([[concepts/paper-real-boundary]]): every dollar in this filing is
**sim-side** (the churn fees were simulated at the falsified 40bps taker constant, the budget
frac is computed on simulated equity). The mechanism (§3) is repo-side; the execution (§4) is
box-side ops on the real process. The *lockout itself was real*: taper 0.0 blocked genuine
entry decisions of the running system regardless of which side the dollars live on.

---

## 1. The incident — the churn's last bill, days after its fix

`risk_protocols.weekly_budget_used_frac` hit **1.0906** on 2026-08-08 (the reading pinned in
the new test file's docstring; **1.0921** immediately before the re-anchor) with
**`taper_mult` 0.0** — **every new entry blocked**. The weekly loss budget anchors on the
**persisted week-open equity**, so no restart clears it; without intervention the block would
have held **through the weekend until the natural W33 rollover** (Monday 00:00 UTC).

**The arithmetic, re-verified against the box:** week anchor = Monday-open equity
**$4,940.59** (`equity.csv` ts 1785715002, the last pre-boundary rows); weekly budget =
`weekly_loss_budget_pct` **6.0** (`config.json:233`) × anchor = **$296.4**; equity at re-anchor
**$4,617.00** → in-week equity drop **$323.6** → frac **1.0916** ≈ the observed 1.0921 (equity
moves tenths between reads). `taper_start` 0.5 (`config.json:234`) → taper hit 0.0 when the
budget fully spent, and stayed there.

**Cause:** the ADA hedge-churn class — fixed `5c111962` (shared exposure pair) + `cf454d5e`
(warmup/cooldown/FW-070 latch) — whose fees landed **wholly inside ISO week 2026-W32**
(all 159 lifetime hedge fills are 08-07 UTC;
[[sources/session-20260807-hedge-churn-guards]]). The fixes ended the *mechanism* on 08-07;
the *budget consumption* it left behind was still governing entries on 08-08. A protective
layer correctly refusing new risk on the basis of damage a **dead bug** did — the mirror image
of [[concepts/protective-senior-overlay]]: the overlay worked exactly as designed, on
poisoned input.

## 2. Attribution — and a filing correction on "net positive"

Operator attribution, recorded verbatim in the audit reason: the churn class *"manufactured
~USD303 of simulated fees in ISO week 2026-W32; week was net positive without the bug."* The
**~$303** is consistent with the corpus's prior measurements (panel-canonical **$301.31** fees
for the one 147-lap ledger event + the 12 residual warm-correlation laps).

- **The lockout attribution HOLDS, 100%:** without the bug the week's frac is ≈ **0.07**
  (~$21 of budget) against `taper_start` 0.5 — taper **1.0** with 7x margin. The entire
  taper-to-zero, and every blocked entry, is bug-attributable.
- ⚠️ **The "net POSITIVE without the bug" claim is a hair too strong on the box's numbers.**
  On the **equity axis** (the axis the budget actually measures): drop $323.6 − ~$303 ≈
  **−$21** — flat, not positive (positive only if attribution ≥ $324, which including the
  churn's gross −13.37 and residual-lap fees is inside the measurement band, but is not what
  the box shows at the stated $303). On the **weekly_pnl axis**: −173.36 contains only the
  churn's **exit-leg** fees (~$150) per the three-series taxonomy
  ([[sources/session-20260807-pnl-reconciliation]] — open legs enter NO P&L counter), so
  without the bug it reads ≈ **−$23**. Either way: **essentially flat without the bug, and
  the $303-vs-−173.36 comparison in the circulated docket crosses two series.** The audit
  record carries the operator's phrasing; this page carries the reconciliation. The decision
  the arithmetic supported — reset a budget spent by a dead bug — survives untouched.

The operator's order, verbatim intent: **"do it properly without injecting it funky"** — no
state-file surgery, no restart-with-edited-JSON; a first-class audited mechanism or nothing.

## 3. The mechanism (`f07d60f8`) — an audited operator verb, shaped by three prior lessons

Commit `f07d60f8` (2026-08-08 13:09:04 −0500; 5 files, +186/−2, pushed). **ControlChannel verb
`budget_reanchor_week`** → `RiskProtocolStack.reanchor_week(equity)`
(`risk/protocols.py:238-255`):

- **Touches ONLY the week anchor** — `_week_key`/`_week_anchor` re-set at current equity;
  `weekly_pnl`, pools, the day budget, and learning data untouched; the key refresh means the
  **natural ISO rollover keeps working** (the next genuine week boundary re-anchors as
  always). Degenerate equity (non-finite or ≤ EPS) refused.
- **Reason REQUIRED** — the runner handler (`runner.py:593-`) refuses the command without an
  explicit reason; no anonymous budget resets.
- **Audited `RP-042`** (`RP_BUDGET_REANCHORED`, `core/codes.py:221` — registry **186 → 187**,
  [[entities/reason-code-registry]]): the hash-chained audit record carries **equity AND the
  full reason**.
- **Registered in BOTH vocabulary halves** — `core/runtime.VALID_COMMANDS` (`runtime.py:48`)
  *and* `runner.HANDLED_COMMANDS` (`runner.py:74`). This is the **silent-drop drift class**
  (the 08-05 acked-but-never-run finding, R2-1 family): a verb handled by the runner but
  absent from `VALID_COMMANDS` is **dropped at consume with no ack and no error**. The
  membership is pinned by its own test.
- **Deliberately ABSENT from `rest_server.ALLOWED_CONTROL`** (`api/rest_server.py:55-56`) —
  risk-loosening verbs stay off the browser-reachable surface, the same posture as
  `arm_live`/`stop`; pinned by `test_verb_is_not_exposed_over_rest`.

**Tests: `tests/test_budget_reanchor.py` — 8, red-first.** ⚠️ *The docket claimed 9;
`pytest --collect-only` says 8* (same correction class as the morning batch's 8→7,
[[sources/session-20260808-morning-batch]]): clears-bug-consumed-week-only ·
natural-rollover-still-works · refuses-degenerate-equity · survives-persistence-roundtrip ·
command-refused-without-reason · command-reanchors-and-audits (asserts RP-042 + reason in the
hash-chained trail) · not-exposed-over-REST · in-VALID_COMMANDS.

Design lineage, explicit: the reason requirement and registered code are the
[[entities/reason-code-registry]] rule ("new behavior = new registered code, never a bare
string"); the both-halves registration is [[concepts/adoption-is-not-enforcement]] applied to
a command vocabulary; the REST exclusion is the standing browser-surface posture.

## 4. Executed and verified live — 13:13 local

- **Command**: id `1786212788.674852-e82d3b` (issuing session's record; the control file is
  **consumed at pickup** so the id is not independently recoverable from the box — the audit
  ts **1786212790.778**, ~2s after the id's embedded timestamp, corroborates it).
- **Ack**: `runner.log:24540` — `13:13:10,781 WARNING … control: budget_reanchor_week
  {'reason': 'operator order 2026-08-08: ADA hedge-churn class (fixed 5c111962/cf454d5e/FW-070)
  manufactured ~USD303 of simulated fees in ISO week 2026-W32; week was net positive without
  the bug'} -> weekly loss budget re-anchored at $4,617.00 … (runner=RUNNING)` — the ack
  carries the **full reason**, as designed.
- **Audit**: `audit.jsonl:37995` — code **RP-042**, seq **37983**, `data.equity` **4617.0**,
  full reason, hash-chained (`h 9acb9c6b9dc108d6` / `prev a8270138adc56d16`).
- **Effect**: `weekly_budget_used_frac` **1.0921 → 0.0001** (session reading at execution);
  box at filing (status ~13:16:42 local): **0.0004** (equity had drifted to $4,616.90 —
  exactly the new anchor doing its job), **taper_mult 1.0**, daily frac 0.0.
- **The no-ledger-touch proof**: **`weekly_pnl` −173.36 UNCHANGED** across the re-anchor
  (−173.23 on 08-07 + Friday's −0.12 daily) — the anchor moved, the realized ledger did not.
  `daily_pnl` −0.12, `realized_total`/pools untouched. The persistence round-trip (the new
  anchor surviving restart) is pinned by `test_reanchor_survives_persistence_roundtrip`.

## 5. Honest-gate observations — the rotating load-marginal red

With `050421a7`'s honest pytest gate live ([[concepts/false-green]] specimen #5's fix), this
ship cycle's three battery runs went **red · clean · red** — each red on **ONE load-marginal
timing test, a different one each time**, each **solo-verified green on the same tree**
(session-observed; consistent with the family's two prior filed members):

1. `test_pbo_variants` schema-AB — red under the battery, **18/18 green run solo BESIDE a
   still-running battery** (the second member registered 08-08 morning, recurring);
2. clean run;
3. `test_concurrency_throttle` burst — red under the battery, **4/4 green solo in 7.7s**.

**The load-marginal timing family is now the batteries' binding constraint** — the honest gate
converts what used to sail through as false green into real reds that cost a full re-run each.
Per the `48a63610` precedent, the commit **shipped with the flake disclosed** rather than
holding the ship hostage to an unrelated timing test — and per
[[concepts/never-widen-a-gate]], no blanket retry was added. The structural response is
**registered as owed item 44** ([[synthesis/owed-measurements]]): split the battery into a
parallel pass (`-m "not timing"`) and a gated **SERIAL** pass (`-m timing`) for the
timing-sensitive family, so load-marginal tests are never judged under 8-way load.

> **RESOLVED same day — item 44 CLOSED by `be341867`**
> ([[sources/session-20260808-battery-split-freeze-gate]] §1): 17 tests / 7 files tagged
> by mechanism, `timing` marker strict-registered, both passes honest-gated, split pinned
> by `test_battery_gate.py` (5). First split battery fully green zero-flake — parallel
> 3445/1 skipped in 3:28, serial 17/17 in 3:07.

## 6. Docket 41a status — parked tests, noted so they are not lost

The input-feed docket's moomoo freeze-gate sub-item (owed **41(a)**) has its **red-first tests
already written and PARKED**, deliberately unshipped ahead of the implementation:
`test_feed_freeze_gate.py.parked` in the session scratchpad
(`C:\Users\haird\AppData\Local\Temp\claude\c--Users-haird-Documents-liquiditybot\63d8f842-8108-448c-b2d9-fa9a4c8a2da4\scratchpad\` —
**session-scoped storage; copy it out before the session is cleaned**). The moomoo gate
implementation resumes next; **the parked file must return to `tests/` when 41a resumes.**
Noted on the owed item itself.

> **RESOLVED same day — the parked file RETURNED and 41a SHIPPED as `01d59908`**
> ([[sources/session-20260808-battery-split-freeze-gate]] §2): `test_feed_freeze_gate.py`
> is back in `tests/`, committed with the fix, run 4/4 red on the pre-fix tree then 4/4
> green. Nothing remains in session-scoped storage; this note is preserved only as the
> record of the parking discipline working.

## Related

[[sources/session-20260807-hedge-churn-guards]] · [[sources/session-20260806-hedge-thrash]] ·
[[sources/session-20260807-pnl-reconciliation]] · [[sources/session-20260808-morning-batch]] ·
[[entities/reason-code-registry]] · [[concepts/false-green]] ·
[[concepts/protective-senior-overlay]] · [[concepts/deadlock-discipline]] ·
[[concepts/adoption-is-not-enforcement]] · [[concepts/paper-real-boundary]] ·
[[synthesis/owed-measurements]]
