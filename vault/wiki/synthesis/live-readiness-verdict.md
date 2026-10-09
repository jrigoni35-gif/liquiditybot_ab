---
title: "Live-Readiness Verdict — what must be true before dry_run:false"
category: synthesis
status: PROVISIONAL
summary: "[UPD 2026-08-30 RIDER: boundary #5 EXECUTED as cut #8 (2026-08-28T03:14:13Z, exec_era 8-ca55e2ba) at Tier-1 40/80, then CORRECTED by cut #9 (2026-08-30T15:32:36Z, exec_era 9-16ec821e, commit 59bdcf87, ARM scoped fee correction only) - the account is real Tier 3 22/38, so cut #8 over-stated fees ~2x and the ~16x fee/edge multiple quoted below is SUPERSEDED (nearer ~9x at 22/38 on the same gross; readout class COST_BOUND unchanged at both 120 and 60bps). VERDICT UNCHANGED: NOT READY, dry_run TRUE through both cuts. Blocker (3) MOVED SIDEWAYS not green - the bar fell 0.8335->0.6772 so conviction resumes and the probe-dominated book unwinds, but era-6 accrual is 4 closed trips (count only, no rates on an accruing era) so nothing is demonstrated yet. Blocker (4) GAINED a member: MLSEC-1, the ML-011 tamper gate that positively attests a forged artifact (owed 108). See synthesis/comparability-boundaries row 9.] UPDATED 2026-08-26: the era-4 gate crossed n=50 and read COST_BOUND (54 closes; gross positive, net ≤ 0 at the honest constant; old gate STAND DOWN) — blocker (1) factually resolved, verdict UNCHANGED: NOT READY (blockers 3/4/5 stand; readout cohort 91% probes, MIXED(both)); see sources/session-20260826-why-losing-deep-dive; adjudication of boundary #5 / ALGO-5 / CONC-1 is the operator's. PROVISIONAL as of 2026-08-21 (governance rule 21) — the NOT-READY DIRECTION is settled and none of the five blockers is in question, but an OPEN cost-stack investigation (sources/session-20260821-cost-stack-in-flight) reframes what the verdict is ABOUT: mean gross measured POSITIVE +0.0733% over 434 closed positions against a 0.717% configured fee stack, i.e. fees ~10x the gross edge (~16x at the true Tier-1 40/80), which turns 'no demonstrated edge' into 'an edge eaten by costs'. That investigation is unverified, single-route, un-cut against the comparability boundaries, and has had NO refuter run. Read the callout under the H1 before citing anything on this page. The one page that answers 'can this go live yet'. Verdict as of 2026-08-21T23:53:07Z: NOT READY, remain in DRY_RUN — five independent blockers, each sufficient alone: (1) the era-4 gate has not read out (33/50, double-derived); (2) at n=50 it cannot resolve what it will be asked (effective n 9.9 of 33, resolvable floor ~1.7033% vs observed gross +1.1820% — it fires below its own noise, owed-82's shape at a new n); (3) the cohort is 85% probe admissions whose p_win is forced to 0.7 against a ~0.567 bar, so it measures the exploration constant, not the selector; (4) two CRITICAL sweep findings (margin veto FAILS OPEN, uncoordinated hedge force-close) are inert ONLY because dry_run is true, so flipping the flag arms both the same day; (5) the entry path's manipulation gate cannot separate honest repricing from layering. Standing and additive: the fee constants are falsified. The page is a ROUTER — every number is stamped and paired with its re-derivation command, because a readiness number written into law decays into a false claim."
tags: [live-readiness, era-4, governance, gate, risk]
sources: 4
updated: 2026-08-30
---

# Live-Readiness Verdict

> [!success] **2026-08-26 — BLOCKER (1) IS FACTUALLY RESOLVED; THE VERDICT IS
> UNCHANGED: NOT READY.** The era-4 gate crossed its pre-registered n=50 (54
> entry-opened closes) and the readout is **COST_BOUND** — gross positive, net
> ≤ 0 at the honest fee constant; the old postmortem gate independently printed
> **STAND DOWN** (−1.007% vs −1.0%). Full decomposition with same-day
> statistical validation: [[sources/session-20260826-why-losing-deep-dive]]
> (tuition, not alpha decay: probe lane n=49/54 nets −1.05%/trip at true fees;
> conviction n=5 clears the full stack, directional only). The reframe this
> page's PROVISIONAL callout was waiting on is now **measured on the
> decision-grade cohort**. What did NOT move: blockers **(3)** — the readout
> cohort is 91% probes and MIXED(both) (2 champions, 23 straddling trips, 2
> label eras; re-derived 2026-08-26T23:55:14Z), so it describes the exploration
> constant exactly as predicted — **(4)** the two dry_run-inert CRITICALs, and
> **(5)** the manipulation gate. Blocker (2)'s shape improved but stands
> (effective n 21.5/54, uniqueness 0.399, SE ×1.58). **The readout names which
> decision is decidable; it never decides** — boundary #5 (staged, inert),
> ALGO-5, CONC-1 and asset discipline are all cohort-resetting and await the
> operator's adjudication.

> [!warning] **[UPD 2026-08-30 — RIDER: BOUNDARY #5 EXECUTED, THEN WAS
> CORRECTED BY BOUNDARY #6. THE VERDICT IS STILL NOT READY.]**
> Two cohort-resetting adjudications have landed since the callout above,
> and neither moves the direction of this page.
> **Cut #8** (2026-08-28T03:14:13Z, `exec_era` `8-ca55e2ba`) executed the
> staged boundary #5 at Kraken **Tier-1 40/80**. **Cut #9**
> (2026-08-30T15:32:36Z, `exec_era` `9-16ec821e`, commit `59bdcf87`,
> operator ARM scoped *"fee correction only"*) then **corrected cut #8's
> founding constant**: the account is real **Tier 3 = 22/38 bps** on
> $17,482 30-day volume, so cut #8 over-stated fees ~2x. Authoritative row:
> [[comparability-boundaries]] **row 9**.
>
> **Effect on this page's five blockers — read them one at a time, because
> only one moved and it moved SIDEWAYS:**
> - **(1)** stays factually resolved (era-4 read COST_BOUND at n=54). But
>   its **fee anchor was wrong by ~2x**, so the "≈16x at the true Tier-1
>   40/80" arithmetic quoted in this page's PROVISIONAL callout below is
>   **superseded** — it is nearer **≈9x** at 22/38 on the same gross. The
>   readout CLASS is unchanged: COST_BOUND at both 120 and 60bps
>   ([[sources/session-20260829-fee-tier-and-stream-audit]] §2).
> - **(2)** unmoved — the resolution floor is a property of the design.
> - **(3) is the one that MOVED, and NOT to green.** The lower derived
>   entry bar (**0.8335 → 0.6772**) means **conviction resumes** and cut
>   #8's probe-dominated book is UNWOUND — so the "85-91% probes, it
>   measures the exploration constant" complaint should decay in **era-6**.
>   It has **NOT** decayed yet, and cannot be claimed to: **era-6 accrual
>   is 4 closed entry-opened trips** as of 2026-08-30 (count only — no
>   gross/net/win-rate on an accruing era, per the moratorium), and the
>   admission mix at that n is not a measurement of anything.
> - **(4)** unmoved: both dry_run-inert CRITICALs stand, and **a new one
>   joins them** — MLSEC-1, the ML-011 model-tamper gate that positively
>   attests a forged artifact ([[owed-measurements]] item 108). It is
>   *also* inert only because nothing here is real money and the box is
>   the operator's.
> - **(5)** unmoved.
>
> **VERDICT UNCHANGED: NOT READY, remain in DRY_RUN.** `dry_run` was TRUE
> through both cuts and neither touched it. And a fresh reason to stay
> there: the correction bought an **honest** readout, not a winning one —
> the median trip clears the real rake and the **fat tail loses**, an
> **ALGO-5** problem cut #9 explicitly EXCLUDED.

> [!warning] **PROVISIONAL — an open investigation reframes this page.**
> Filed under [[concepts/claim-status-discipline]] (governance rule 21) on
> 2026-08-21, retroactively, because this page was written to read as a
> **final verdict** while a cost-stack investigation that changes its
> economics was still running.
>
> **What is NOT in question:** the direction. **NOT READY, remain in
> DRY_RUN.** All five blockers stand, none is a cost claim, and none is
> weakened by anything below.
>
> **What IS provisional:** what the verdict is *about*. A run of
> `scripts/cost_attribution.py` over **434 closed positions** reports mean
> **gross +0.0733% — POSITIVE** — against a configured 25/40 bps stack
> costing **0.717%**, for net **−0.6440%**: fees ≈ **10x** the gross edge, and
> ≈ **16x** at the true Tier-1 40/80. That would turn *"no demonstrated
> edge"* into *"a small positive edge eaten by the cost stack"* — a **reframe,
> not a reversal**. It is **unverified**: single-route, no `n_eff`, no stated
> population cut against
> [[synthesis/comparability-boundaries|the boundaries]] (434 ≫ era-4's 33, so
> it is certainly pooled), and **no refuter has been run**.
>
> **Full account, its five named pending refuters, and three items that WERE
> verified — including that the tool's own Kraken constants are a schedule
> this vault struck on 2026-08-07 —
> [[sources/session-20260821-cost-stack-in-flight]].** Treat that
> investigation as a **lead**, never as evidence.

> **The road to live is fixed by law and is not negotiable here:** config
> `dry_run:false` → restart → typed `ARM LIVE`. Nothing on this page authorizes
> any step of it. This page records what would have to be **true first**, and
> what is measurably not.

**VERDICT as of 2026-08-21T23:53:07Z — NOT READY. Remain in DRY_RUN.**

## The five blockers

Each is sufficient on its own; none is a threshold that could be moved to clear
the verdict.

### 1. The gate that decides the strategy question has not read out

`33 / 50` entry-opened closes, **double-derived**: the running binary's own
counter (`pc_status.era4.accrual_n`) and a local `scripts/cohort_eval.py` run
agree. Re-derive: `python scripts/cohort_eval.py`, or read `era4` from
`origin/paper-telemetry:control/pc_status.json`.

The readout names which decision has become decidable; it decides nothing. Until
it fires, the accruing numbers are not a trend and are not retune evidence
([[concepts/never-widen-a-gate]]).

### 2. At n=50 the gate fires below its own noise

Effective n is **9.9 of 33 nominal** (mean uniqueness 0.301 — concurrent trips
share the same market path, so the nominal SE is optimistic by ×1.82). The
tool's own resolvable-edge floor reads **~1.7033%** against an observed gross
mean of **+1.1820%** (SE 0.4669%).

This is [[synthesis/owed-measurements]] **item 82's exact shape**, recurring at a
different n and the opposite sign — which makes it a property of the design, not
of the sample. The correct response is to say the quantity is **unresolved**, not
to lower a floor: the n and the estimator are measurement standards, not
tunables.

### 3. The cohort measures the exploration constant, not the selector

`probe: {'1': 28, '0': 5}` — **85% probe admissions**. A probe sets
`p_win = max(p_win, ml.exploration.p_win = 0.7)` against a derived bar near
0.567, so it **clears by construction** and the model's own p is never the
admitting quantity. The cohort is `MIXED(both)` on three further axes: 18/33
trips straddle a mid-flight deploy (14 deploys inside the window, two champions),
5/33 carry a leg from a binary predating the `exec_era` stamp, and two label eras
are present (`exit_sim` 17, `triple_barrier_h432` 16).

Whatever reads out, it is not a statement about the entry selector.
([[concepts/pooled-populations]], [[concepts/era-exclusion]].)

### 4. Two CRITICAL defects are inert ONLY because `dry_run` is true

Both are BOUNDARY class from the 2026-08-20 25-agent sweep, deliberately unfixed
(fixing them alters which orders are placed → cohort-resetting), and both are
gated by the very flag that going live removes:

- `risk/leverage.py:75` — the margin-health veto **FAILS OPEN**: `0.0` means both
  "TradeBalance API failed" and "no margin in use", so a transient failure
  disables the 150%/200% margin block for a full hour, at up to the 10× region
  cap. No last-known-good, no distinct unknown state, no test.
- `execution/inventory.py:134-155` → `main.py:2921` — `derisk_actions` can select
  a **HEDGE** position and force-close it with **zero hedge coordination**: the
  rehedge cooldown and the FW-070 churn latch are never armed, so the hedger
  re-opens next cycle and derisk cuts again — a guard-invisible reproduction of
  the `cf454d5` ADA churn incident (−$318) through an unguarded path.

**Flipping `dry_run` arms both on the same day.** Authority:
`docs/quant/2026-08-20_codebase_sweep_docket.md`.

### 5. The entry path's manipulation gate is not evidence

Injection into the shipped `LiquidityRegimeEngine` (2026-08-21): honest maker
repricing in a +15 bps/30 s melt-up and true layering both score **spoof 0.949 /
79 events / label spoofy** at matched cadence — and 0.949 clears the live
`veto_at 0.90`, refusing entries as SZ-045. The detector is directional (it fires
on whichever side must chase the trend), evadable (repost ≥120 s → 0.000), and
blind outside its 15-level window. Its efficacy on the corpus is **unresolved in
both directions** — the apparent effect lives on the disposition stamp, dies on
the manipulation score, and a placebo stamp (SZ-021) scores higher.

Full account: [[concepts/observational-equivalence]] ·
[[sources/session-20260821-manip-gate-and-live-readiness]].

## Standing and additive (not counted above)

- **The fee constants are falsified** — 25/40 bps shipped against a Tier-1 40/80
  schedule ([[concepts/cost-truth]], owed item 88, batched at the readout
  boundary). Live fills would book against a cost stack the ledger under-prices,
  in the flattering direction. The feasibility table behind it —
  the wedge binds at **every** row of the Kraken spot ladder — is
  [[sources/session-20260816-fee-wedge-feasibility]]. **2026-08-21:** the
  struck **16/26** schedule was found still hard-coded in a live cost
  instrument (`scripts/cost_attribution.py:76-77`) with a comment asserting
  the *opposite* conservatism direction — third recorded recurrence of that
  propagation ([[sources/session-20260821-cost-stack-in-flight]] §B).
- **An open cost-stack investigation reframes this page** — see the
  PROVISIONAL callout at the top.
  [[sources/session-20260821-cost-stack-in-flight]].
- **The config itself is not a blocker**: verified 0 FATAL, no duplicate keys, no
  BOM, `system.dry_run: true`, deploy channel pinned to `main`
  ([[sources/session-20260819-config-solidity]]). Three of its four standing
  guard WARNs are readout-docket tunables, so they move at the same boundary as
  everything else on this page.
- **The money-path verdict is open**: gross edge is indistinguishable from zero
  in **both** directions — which is not "there is no edge"
  ([[synthesis/the-money-path-thesis]]).

## What would move the verdict

Nothing on this list is a threshold change; each is an accrual, a measurement, or
an operator adjudication.

1. The era-4 gate reaching n=50 **and** its readout being read as what it is (a
   trigger naming a decidable decision), with the §4.1 convention rider and the
   population's probe share stated in the same breath.
2. The BOUNDARY docket adjudicated at that boundary — SWEEP-0 and SWEEP-1 first,
   because they are the two that `dry_run` is currently masking.
3. A discriminating feature for the spoof detector, or the gate's removal from
   the live entry path — both cohort-resetting, both operator-owned.
4. The fee-constant correction landing as part of the same boundary batch (owed
   88).

## What would settle this

**The verdict's DIRECTION does not need settling** — it is established, and
blockers 1-5 above are its evidence. What is provisional is this page's
**framing**, and it settles when the open cost-stack investigation closes:

1. `scripts/cost_attribution.py` re-run with its **population cut stated**
   against [[synthesis/comparability-boundaries]] and its **effective n**
   reported instead of 434.
2. The gross figure **double-derived** by a second route (contract clause (e)).
3. The tool's struck 16/26 Kraken constants corrected or quarantined
   (`scripts/cost_attribution.py:76-77` — SAFE, alters no order and no fill).
4. All five pending refuters run.

At that point this page is re-marked **SETTLED** with whichever framing
survives, or the blocker list is amended and the verdict re-derived. **Until
then no downstream page may depend on the cost-stack reframe** — it may be
cited only as `[[sources/session-20260821-cost-stack-in-flight]], PROVISIONAL`.

### Pending refuters

Held on [[sources/session-20260821-cost-stack-in-flight]] §*Pending refuters*
— **R1** pooling artifact (run first), **R2** noise at `n_eff` ≪ 434, **R3**
hedge legs decide the sign (named historical mechanism: `breakeven_test.py`
flipped its own median gross from −0.0303% to **+0.0505%** by discarding 159
hedge round trips — *the same sign as this reframe*), **R4** the fee side is
the artifact, **R5** the instrument is blind to hedge legs as both cost tools
once were. **None has been run; default disposition REFUTED.**

## Re-derivation contract

Every number on this page is volatile. Re-derive before citing:

| fact | command |
|---|---|
| accrual, cohort composition, effective n | `python scripts/cohort_eval.py` |
| live state (deploy head, era4, equity, mode) | `git show origin/paper-telemetry:control/pc_status.json` |
| docket state | `docs/HANDOFF.md`, `docs/quant/2026-08-20_codebase_sweep_docket.md` |
| readout branch → action map | `docs/quant/2026-08-16_era4_readout_decision_table.md` (SIGNED) |

## Related

[[sources/session-20260821-manip-gate-and-live-readiness]] ·
[[sources/session-20260821-cost-stack-in-flight]] ·
[[concepts/claim-status-discipline]] · [[concepts/the-method]] ·
[[concepts/cost-truth]] ·
[[synthesis/owed-measurements]] · [[synthesis/the-money-path-thesis]] ·
[[synthesis/governance-doctrine]] · [[synthesis/risk-posture-doctrine]] ·
[[concepts/never-widen-a-gate]] · [[concepts/observational-equivalence]] ·
[[concepts/paper-real-boundary]] · [[concepts/average-uniqueness-and-ess]]
