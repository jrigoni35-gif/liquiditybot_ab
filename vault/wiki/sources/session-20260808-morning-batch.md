---
title: "The Morning Batch (2026-08-08) — Execution-Era Boundary #3 (Fill-Sim TTL Normalization) and the Battery Gate That Never Fired"
category: source
summary: "Two pushed commits, both re-verified against the box at filing. (1) 3cfe0710 closes owed 40: _passive_poll_prob TTL-normalizes the passive fill hazard — p = 1-(1-sf_base*exp(-d/sigma))**min(cal_life/ttl, 1.0) — so per-ORDER fill probability is TTL-invariant at the calibrated F(25s); ttl==cal_life is bit-identical (5m book + G1-G5 unchanged, no re-baseline); exponent clamped at 1.0; sf_base=1.0 deterministic test mode bypasses. Mints EXECUTION-ERA BOUNDARY #3: corpus rows before 2026-08-08 were filled under the compounding simulator that gifted 6h long-book orders certainty fills at -50bps. XV-023 opened (per-TTL recalibration). (2) 050421a7, false-green specimen #5 CRITICAL: the battery's pytest stage gate NEVER fired — `start /b /wait \"\" cmd || (...)` satisfies || with start's own LAUNCH success — found live when a red pytest sailed to ALL GREEN, the first false arm the matrix ever produced; fixed with `if errorlevel 1`, proven two-sided; test_battery_gate.py (4) pins the semantics and bans the construct. (3) pbo subprocess flake reconfirmed load-marginal (fails -n 8, passes solo). (4) Runner bounced onto 050421a7 ~11:09 local, 2 positions restored, marks_age/cycle_duration real. Battery 3449/0/1 in 349.51s, smoke 219. Two batch claims corrected at filing: the new test file collects 7, not 8; the resume snapshot was 2.1 min old, not 6s."
tags: [session, fill-sim, calibration, paper-mode, era-boundary, false-green, gates, windows-cmd, flakes, ops]
sources: 1
source_path: none — session work product (operator-dictated batch, every item re-verified against the box at filing)
source_date: 2026-08
authors: [operator, claude-session]
ingested: 2026-08-08
updated: 2026-08-08
---

# The Morning Batch (2026-08-08)

## Provenance and boundary statement

Operator-dictated closing batch of the morning session; **every item below re-verified against
the box at filing time** — `git show` on both commits, `_passive_poll_prob` read in full,
`config.json`, both test files collected by pytest, `test_windows.bat`, `runner.log`,
`pc_supervisor.log`, `outputs/status.json`, `outputs/runner.lock`, `outputs/pushers_code_rev.txt`.
Two of the batch's claims **failed exact verification and are corrected here** (§1 test count,
§4 snapshot age) per domain rule 2 — preserve the exact numbers, the box's numbers.

**Paper/real boundary** ([[concepts/paper-real-boundary]]): §1 is a change to the **simulator
instrument itself** — sim-side by construction; every dollar it will ever influence is
simulated. §2 and §3 are repo-side (gate plumbing, test harness). §4 is box-side ops on the
real process; its equity/P&L numbers are sim-side.

---

## 1. OWED 40 CLOSED — fill-sim TTL normalization SHIPPED (`3cfe0710`)

**Head = remote = `050421a7`; `3cfe0710` is its parent. Both pushed.**

**The fix, verified in code** (`execution/order_manager.py:61-100`): new `_passive_poll_prob`
computes

```
p = 1 - (1 - sf_base * exp(-d/sigma)) ** min(cal_life/ttl, 1.0)
```

Poll cadence cancels (`n_cal/n_ord == cal_life/ttl` — no poll_sec plumbing), so the **per-ORDER
fill probability is TTL-invariant at the calibrated F(25s)**. Properties, each pinned by a
red-first test:

- **`ttl == cal_life` is bit-identical to the old model** — the calibrated 5m book (25s
  timeout) and the quant gates G1–G5 are unchanged; **no re-baseline**
  ([[concepts/conscious-re-baseline]] not triggered, by construction).
- **Exponent clamped at 1.0** — shorter-than-calibrated orders keep the measured per-poll
  hazard and fill **less** over their shorter life, never more.
- **`sf_base = 1.0` is the deterministic TEST MODE bypass** (bug-78 fixture convention);
  Wilson calibration can never emit boundary values, so the bypass is unreachable from
  calibration ([[entities/quant-trials-harness]] fixtures keep their guarantee byte-identical).
- The compounding gift is dead: per-poll hazard on a 6h order is **~864x smaller** than the
  calibrated per-poll hazard; compounded F(6h) ≈ F(25s), asserted < 0.2 where it was ≈ 1.0.
- **AST pin**: `_poll_dry` must call `_passive_poll_prob` — the bare inline hazard is banned
  from coming back.

**Config**: `sim_fill.calibration_life_sec = 25.0` (`config.json:370`) with a
`_calibration_life_sec_doc` that carries the era-boundary declaration in the config itself.

~~**The double-count disposition** (owed 40's sub-item (b)): the deterministic `_sim_maker_cross`
path is **retained by design** — reframed as *genuine trade-through against the live book*,
which still fills long orders whenever the market actually crosses; the calibrated stochastic
hazard becomes a **conservative floor** on top. The
calibrate-conditional-on-no-cross refinement is folded into **XV-023** (below), not silently
dropped.~~

> ⚠️ **RETRACTED 2026-08-10 — THIS PARAGRAPH WAS WRONG, AND IT WAS THE MOST CONSEQUENTIAL
> SENTENCE IN THIS FILING** ([[sources/session-20260810-fill-double-count]], owed 57, era
> boundary #4).
>
> **The hazard was not a "conservative floor."** A floor models something the observation cannot
> see. This ran **only when the observation was present** — the hazard branch sits **inside
> `if book:`** — so it modelled nothing the snapshot could not already show. And
> `core.fill_calibration.invert_base_prob` had already solved `sf_base` so **the hazard ALONE
> reproduces `f`**, the very crossing frequency `_sim_maker_cross` fires on. Stacking them did
> not add conservatism; it **spent the calibrated frequency twice**:
>
> `1−(1−f)² = 2f − f² = 21.96%` against an `f = 11.66%` target · ledger-measured **22.30%** ·
> **1.88x at the touch, approaching 2x as f falls.**
>
> **Sub-item (b) was not disposed — it was the whole remaining defect**, and
> [[sources/session-20260807-fleet-findings]] §1 had already named it correctly *the night
> before* (*"the calibrated trade-through frequency is spent twice"*). **Item 40's closure stands
> for (a), the TTL normalization, alone.** (b) closes on **2026-08-10** with `aeeaae36`.
>
> **Why this filing got it wrong is worth more than the correction.** The disposition was written
> **in the same section as a genuine, well-verified fix**, by an author who had just earned the
> right to feel finished — and it was the *only* claim in this filing that received no
> independent check, while the same filing was careful enough to catch its own test-count error
> (8 claimed vs 7 collected). **The scrutiny went to the numbers and skipped the adjudication.**
> Filed as [[synthesis/open-contradictions-register]] entry 25; the surface is added to
> [[concepts/self-flattery-gradient]].

**THIS MINTS EXECUTION-ERA BOUNDARY #3** — after the QA-contamination quarantine
(`858c8d71`/`483f6727`) and XV-021 (`8e5455e8`, ts ~1785717000): **corpus rows before
`3cfe0710` (2026-08-08) were filled under the compounding simulator** that gifted 6h long-book
orders certainty fills at −50 bps. **Label cohorts must treat this date as a regime cut** —
the 432 cohort now contains a *second* execution boundary
([[synthesis/owed-measurements]] item 1b, [[comparisons/horizon-96-vs-24-bars]]).

**XV-023 OPENED**: per-TTL recalibration when `calibrate_fills.py` gains long-life recordings
— declared in `core/fill_calibration.py:17` and registered as owed item 40b. The inversion
`g(f)` is unchanged; `sf_base` keeps its calibrated meaning at the calibrated life.

**Tests**: `tests/test_fill_ttl_normalization.py`, red-first. **Filing correction: the file
collects 7 tests, not the batch's (and the commit message's) claimed 8** — verified by
`pytest --collect-only` (7 + 4 = 11 new; 3438 prior + 11 = 3449, so the claimed battery total
itself confirms 7). The commit message over-counted by one; the tests themselves are exactly
the property list above.

**Battery through the HONEST gate** (i.e., through §2's repaired pytest arm): **3449 passed /
0 failed / 1 skipped in 349.51s, smoke 219, ALL GATES PASS** (session-reported; arithmetic
cross-checked at filing).

## 2. FALSE-GREEN SPECIMEN #5, CRITICAL CLASS — the battery's pytest gate NEVER fired (`050421a7`)

**The mechanism, verified in the bat and pinned by test**: `start /b /wait "" cmd || (...)`
**satisfies `||` with `start`'s own LAUNCH success** — the awaited child's exit code lands
only in `ERRORLEVEL`, which the `||` form never reads. The pytest stage — the battery's
primary arm, 3,400+ tests — **could not fail the battery no matter what pytest returned**.

**Window**: the construct entered at `101f7436` (2026-08-07) — the capacity-sweep commit whose
own headline was *"repair two lying gates"*: the BelowNormal renice
([[sources/session-20260807-capacity-sweep]] §2, profit-protection) introduced
`start /belownormal /b /wait`, and its `||` arm was **dead from birth**. Fixed one day later.
The commit that repaired two lying gates installed a third —
[[concepts/adoption-is-not-enforcement]]'s recursion, again.

**Found live, not by audit**: a red pytest (1 failed — §3's pbo load-marginal flake) **sailed
through to ALL GREEN** — the first false arm the matrix ever produced. Every earlier failed
battery had been caught by LATER stages whose engines broke on the same bugs — **a lying gate
survives exactly as long as it is never the last line of defense** (new observation for
[[concepts/false-green]]: redundancy masks a dead gate; the death is visible only when the
lying stage is the *sole* detector of a failure).

**Fixed** in `test_windows.bat` with `if errorlevel 1` (the documented-reliable form),
**proven two-sided live**: the old form fell through on an exit-1 child; the new form fired.

**Class fence**: `tests/test_battery_gate.py` (**4 tests**, verified by collection) pins the
cmd semantics **both ways** (the `||` form misses a child failure; `if errorlevel 1` catches
failure and passes success) **and bans the construct from the bat**
(`test_matrix_never_pairs_start_wait_with_or_operator` — the
[[sources/session-20260806-append-gate]] pattern: gate the class, not the instance).

**Gotcha, worth its own entry**: inline `cmd /c "start /b /wait ..."` **DEADLOCKS under
captured pipes** (3x 60s TimeoutExpired during test development) — the construct must run from
a **real `.bat` file**. This is the same invocation plane as the capacity sweep's false-green
invocation specimen; Windows batch semantics under harness capture are their own hazard class.

## 3. The pbo subprocess flake — reconfirmed load-marginal (owed-39 successor family)

`test_pbo_variants.py::test_schema_ab_flag_adds_no_new_gating_check_and_is_info_only` failed
under `-n 8` with the inner overfit subprocess at `passed 7, failed 1` at 33s; **passes solo in
60.33s on the same tree**. Registered as the **second member of the load-marginal timing
family** (successor to owed 39's RST class, alongside `test_feed_concurrency`) — honest red,
watch, no blanket retry ([[concepts/never-widen-a-gate]]). Its single red is also the failure
that exposed §2's dead gate — the flake earned its keep.

## 4. Runner bounced onto `050421a7` (~11:09 local) — the honest simulator is live

Verified in `runner.log` / `pc_supervisor.log` / `status.json` / `runner.lock` /
`pushers_code_rev.txt` at filing:

- **Graceful stop 11:08:17** (`control: stop -> ok`, final snapshot saved); supervisor
  auto-update spawn 11:09:50; **resumed 11:10:22 from a 2.1-min-old snapshot** — **filing
  correction: the batch said "6s-old snapshot"; the box's own resume line says 2.1 min**
  (`resumed from snapshot (2.1 min old): 2 positions, 0 open orders, 2 pending labels,
  equity=$4,605.65`).
- **2 positions restored** (ETH long d5513dd5, BTC long e35c0a59), RUNNING, DRY_RUN,
  `pushers_code_rev.txt = 050421a7`, lock pid live. Equity $4,617.04 at the batch's
  observation; $4,617.12 at filing (drifts with marks — sim-side dollars).
- **The latency instruments are reading real values on the new boot**: `marks_age_sec` 0.7 at
  observation / 0.2 at filing (never the tautological 0.0 —
  [[concepts/tautological-instrument]] repair holding), `cycle_duration_sec` 1.25 / 4.08 with
  `max` 42.73 (the warmup stall visible again, as designed).
- **No import deaths** — the pandas lesson held
  ([[sources/session-20260807-closing-batch]] §4).
- **Every long-book order placed from this boot is priced by the honest simulator** —
  [[entities/long-book]] third reading.

## 5. Commits and queue

`3cfe0710` (era boundary #3) + `050421a7` (gate) **pushed, head = remote** (verified:
`origin/main` = `050421a7`). Queue after this batch, restated from the register: **input-feed
docket (41) next**, then staleness-veto **42a** + restart-warmup **42e**, `ret_pct`/bars_held
(37g), `cf454d5e` record repairs (37b); **fee constants remain HELD behind h432** (37a).

## Related

[[synthesis/owed-measurements]] · [[concepts/false-green]] · [[entities/long-book]] ·
[[concepts/paper-real-boundary]] · [[synthesis/the-money-path-thesis]] ·
[[sources/session-20260807-fleet-findings]] · [[sources/session-20260807-capacity-sweep]] ·
[[concepts/adoption-is-not-enforcement]] · [[concepts/conscious-re-baseline]] ·
[[comparisons/horizon-96-vs-24-bars]]
