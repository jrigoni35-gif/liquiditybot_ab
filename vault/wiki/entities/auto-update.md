---
title: auto_update (the deploy gate)
category: entity
summary: "The unattended deploy chain — polls origin on a ~15-minute cycle and, for externally-pushed commits only, runs the full gate battery in a scratch worktree nested inside outputs/ before deploying. CORRECTED 2026-08-07: local commits don't just bypass the battery — they bypass the RUNNER BOUNCE entirely (committed ≠ running); only the telemetry pushers reload on a local commit, so the box runs new sidecars over an old engine until an external push or a manual bounce. UNBLOCKED 2026-08-09 by 8e9d7e6f — battery_passes can go green again now that a MODEL-readiness verdict no longer gates CODE deploys; that commit is battery/QA-only and needs NO runner bounce (head 8e9d7e6f, runner correctly live on 3c0debd7)"
tags: [module, deploy, infrastructure]
sources: 9
updated: 2026-08-09
---

# auto_update (the deploy gate)

The unattended deploy chain on the production box. Polls origin on a **~15-minute cycle**;
when the remote is ahead (an **externally-pushed** commit), it runs the **full gate battery**
in a scratch worktree before deploying.

> ⚠️ **Correction (2026-08-07,** [[sources/session-20260807-evening-ops]]**):** this page
> previously said that for local commits *"the battery never runs and the code is already
> live."* The first half stands; **the second half is false.** `decide()`
> (`scripts/auto_update.py:114-146`) routes local==remote to `'current'` and local-ahead to
> `'ahead'`, and **both return with the runner untouched** — only the remote-ahead `'test'`
> path reaches `_signal_restart()`. **A locally-authored commit is committed, not deployed:**
> the runner keeps running pre-commit code until an external push, a manual bounce, or (for
> `pc_supervisor.py` only) the supervisor's source-change self-restart.

## The local-commit blind spot (2026-08-07)

Both halves of the behavior are individually deliberate (never battery-test your own
just-written commit into a self-brick; never rollback-bounce on `'ahead'`) — the blind spot is
that **nothing closes the loop afterwards**. Worse, the loop *appears* closed:
`_ensure_pushers_current()` bounces the **telemetry sidecars** on ANY head change (marker file
`pushers_code_rev.txt`), so `auto_update.log` prints *"pushers bounced for rev <new>"* right
next to *"already up to date"* — new sidecars over an old engine. One afternoon's log showed
both sides: external `cf454d5e` at 13:53 got battery → ff → runner bounce; local `101f7436`
and `48a63610` at 19:24/19:39 got pusher bounces only. `48a63610` reached the live supervisor
anyway **only because its one file was `pc_supervisor.py`** — the single self-restarting file;
an engine-file commit authored on this box has **no automatic deploy path at all**. Its commit
message's *"Deploys via the normal auto_update bounce"* is a drift-register row
([[synthesis/documentation-drift-register]]).

*Third measured confirmation, watched land in real time (2026-08-08,
[[sources/session-20260808-battery-split-freeze-gate]] §3):* locally-authored `01d59908`
(the moomoo freeze gate), pushed 13:56 — the 14:10:03 cycle printed `already up to date` /
`pushers bounced for rev 01d59908` with the runner pid untouched, exactly this page's
mechanics. The session's working deploy path for engine commits is now the ControlChannel
`stop` → supervisor `runner stale/absent -> relaunching` pair (observed 13:09:24 →
13:11:57 for `f07d60f8`), used three times that day.

## The worktree location — part of the test contract

The battery worktree is built at **`outputs/_update_wt_<pid>`** — deliberately *inside*
`outputs/`, for audit **C-F11** reclaimability. Consequence, learned 2026-08-04: every test in
the battery must be **location-invariant** — a substring path filter (`"outputs" not in
str(f)`) saw every file in the worktree as excluded and turned a green test red exactly where
deploys are decided ([[concepts/location-invariant-tests]],
[[sources/session-20260804-deploy-gate]], fixed `242568fb`).

## The asymmetry that hides defects

Because the battery runs **only for remote-ahead commits**, any gate-environment-specific
defect stays invisible for as long as every commit is local. The 2026-08-04 incident surfaced
on the **first outside-pushed commits since the HIG tests landed** — the defect had been
shipped for the whole interval with zero opportunities to fire.

## Timeline landmarks
- `outputs/auto_update.log` was among the files fabricated by the test-suite contamination
  ([[sources/test-suite-outputs-contamination]]).
- 2026-08-02: deploys stalled on seven local-only commits
  ([[sources/session-20260802-digest]]); resolved 08-03, head = remote = `d67fd6a5`
  ([[sources/session-20260803-bug-sweep]]).
- 2026-08-04: first gate rejections (two, deterministic) — root-caused and fixed same day;
  main at `242568fb`, deploy confirmed (runner pid 9212 live on it). The **dirty stamp** seen
  during the incident was **transient** — the uncommitted-fix window, not a second defect.

## The force-kill grace was shorter than the runner's own measured stalls
Fixed 2026-08-05 late evening (commit `4799bfc7`, [[synthesis/owed-measurements]] item 30f):
`_FORCE_KILL_AFTER_SEC` was **45s**, while `runner.py:386` documents **MEASURED** worst-case cycle
stalls of **88.1s / 55.5s / 50.2s** — **every documented stall exceeded the grace**. A deploy could
therefore `taskkill` a **HEALTHY** runner mid-cycle, on a **~15-minute cadence**, and an unclean kill
mid-append is the likely origin of the `audit_tail_truncations` counter that `bc198aa5` had boarded
hours earlier ([[entities/observability-sidecars]] · [[entities/overfit-check]] ·
[[sources/session-20260809-corpus-corruption]], [[concepts/torn-append-fusion]]). Grace raised
**45s → 150s** (overridable via `LB_FORCE_KILL_AFTER_SEC`).

> **The deploy cadence is part of the failure surface, not just the delivery mechanism.** The same
> commit fixed `core/skimmer.py`'s replace-hysteresis, which was **void after every restart** — so a
> **0.55 candidate evicted a 0.90 incumbent every 15 minutes** (item 30g). A bounce every quarter
> hour makes any restart-fragile invariant fail continuously rather than rarely.

## The gate is UNBLOCKED — 2026-08-09, `8e9d7e6f` (supersedes the section below)

**`auto_update.battery_passes` can go green again**, and it did: **pytest 3473 + 1 skipped
parallel / 19 serial timing / smoke 219 / assurance 49 / overfit 3 pass 0 fail / ruff /
pyright / bandit / compileall / quant G1–G5**
([[sources/session-20260809-gate-policy-and-self-heal]] §3).

**What changed is which verdict the overfit stage is allowed to stop, not the stage's
readings.** OF-1 and OF-7's dead-feature check are **model-readiness** gates that were
consumed as a **code-deploy** gate through this very field — so a data-starved corpus was
holding **code-safety fixes** hostage. The numbers still print every run;
**0.12 and 0.55 are pinned by test**; the policy is fail-closed, hard on synthetic, and
self-terminating ([[concepts/never-widen-a-gate]] §scoping-is-not-widening,
[[entities/overfit-check]]).

> **This section's own diagnosis was correct and is worth keeping:** *"a blocked deploy gate
> is a poor alarm — it reports **that** something is red, never **why**, so a misdiagnosis
> survives inside it indefinitely."* The fix did not improve the alarm; it removed one class
> of thing that could set it off spuriously. **The alarm-quality gap is unchanged.**

### The gate-policy commit needs NO runner bounce — stated explicitly

`8e9d7e6f` touches **`scripts/overfit_check.py` + two test files only** (`git show --stat`):
**zero engine paths, zero decision paths**. It is **battery/QA-only**.

**Head is `8e9d7e6f`; the runner is live on `3c0debd7`, and that is correct.** Nobody should
bounce the runner expecting a behaviour change from this commit — there is none to get. This
is a case where the [[entities/auto-update]] local-commit blind spot documented above
(*committed ≠ running*) is **benign**, and saying so is the point: the blind spot's hazard is
that it is silent, so the times it does **not** matter must be recorded as deliberately as
the times it does.

## ~~The gate is currently BLOCKED — by an honest red, not a defect (2026-08-09)~~ *(superseded the same day — preserved as the record)*

`auto_update.battery_passes` requires the **full** battery green in the scratch worktree.
Since 2026-08-08 the **overfit stage is honestly RED** and will stay red until the training
corpus grows or the feature count drops — so **no externally-pushed commit can deploy,
regardless of its content**, and DoD "ALL GREEN" is unattainable in the interim
([[synthesis/owed-measurements]] item 46, [[entities/overfit-check]]).

This is worth stating precisely because the red's **stated cause changed**: it was first
filed as cold-start growth and is in fact the [[concepts/era-exclusion]] disarm caused by a
corpus corruption, now repaired ([[sources/session-20260809-corpus-corruption]]). **The gate's
behaviour is identical either way** — it fails closed on a red battery — which is exactly
what it should do, and also why a blocked deploy gate is a poor alarm: it reports *that*
something is red, never *why*, so a misdiagnosis survives inside it indefinitely.

~~Three policy options are registered and **not decided**~~ **— decided 2026-08-09 as option
(a); see the section above.** **No threshold has been moved**
([[concepts/never-widen-a-gate]]). Meanwhile the only deploy path in use is the manual
ControlChannel stop → supervisor relaunch, which is the same path the local-commit blind spot
already forces for locally-authored commits.

## Related
[[concepts/location-invariant-tests]] · [[entities/liquiditybot]] ·
[[sources/session-20260804-deploy-gate]] · [[sources/session-20260805-evening]] ·
[[sources/session-20260807-evening-ops]] · [[synthesis/documentation-drift-register]] ·
[[entities/observability-sidecars]] · [[concepts/torn-append-fusion]] ·
[[sources/session-20260809-gate-policy-and-self-heal]] · [[entities/overfit-check]] ·
[[concepts/never-widen-a-gate]]
