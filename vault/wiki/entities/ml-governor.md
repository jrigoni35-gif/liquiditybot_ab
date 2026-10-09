---
title: The ML Governor
category: entity
summary: "A staged monitor that can only make the bot more conservative than config — and, on 2026-08-09, the subsystem that resolved its own wedged-champion adjudication with no operator override: ML-016 → ML-083 → ML-040 in 4ms set an unfalsifiable badge aside (watermark 9,708 > matrix 701) and deployed logistic at 0.24728 against the cold-start bar, retiring the bug-promoted gbt"
tags: [subsystem, ml, risk, self-heal]
sources: 6
updated: 2026-08-09
---

# The ML Governor

The staged supervisor over model influence.

## The ladder
**healthy -> degraded** (harder shrinkage, reduced Kelly) **-> failing** (model bypassed, Kelly floored,
retrain flag raised, CRITICAL log).

## The governing invariant
> **"The governor can only make the bot more conservative than config, never less."**

And: the fix for a degraded model **"is a better model through the deployment gate, not a bigger
knob."** No manual override of a kill switch, ever; the only recovery path is a shadow-recovery
sequence requiring consecutive healthy windows.

## Current state through the corpus
Held at the **kill-switch level** (model not used for sizing, Kelly capped, shrinkage applied) — a state
described as **structural and EXPECTED** on a no-edge-yet model. Because the model drives no live
sizing in this state, a PBO breach is "a learning-health signal, not a trading-risk event."

## Champion/challenger
Selection is on **raw out-of-fold Brier** via the [[concepts/simplicity-ladder]]; a worse challenger
never deploys; calibration is a final deploy check, not a selection criterion.

## How it deadlocked
When the corpus shrank below the champion's training watermark, the like-for-like gate could not
construct a comparison and rejected fail-closed on every retrain — see [[concepts/deploy-deadlock]] and
[[concepts/ghost-badge]].

## Two deploy-seam defects fixed, two governance gaps left open (2026-08-05 evening)
Debug round 2 ([[sources/session-20260805-evening]], commit `f3253f0d`) hit this subsystem four
times. Two were fixed:

- **R2-4 — the CLI deploy gate was biased toward deploying.** `scripts/train_meta.py` fit the
  isotonic calibrator on **the very OOF vector it then scored** (in-sample), while the champion is
  rescored **strictly out-of-sample** by `rescore_frozen`. `main.py`'s auto lane had fixed exactly
  this in **H13** — **measured optimism +0.0032..+0.0066, i.e. 25–150% of the 0.005 deploy margin,
  always pro-challenger, never averaging out** — and **this lane never got it**. A manual retrain
  could therefore deploy a **strictly worse model** *and* stamp the optimistic number into the
  artifact as the **next champion's badge**, poisoning the comparison for every later gate. Fixed:
  the CLI scores through the same `cross_fitted_calibrated_oof` helper — **one gate, one
  standard**. (Compare [[concepts/ghost-badge]]: a badge computed under a rule the gate no longer
  uses is worse than no badge.)
- **R2-5 — a good model rejected as tampered, permanently.** `save_model` publishes the artifact
  atomically and appends its `"registered"` ledger row **a beat later**; a reload in that gap hashes
  **new bytes** against the **previous champion's row**, fails verification, logs **ML-011**, and
  drops to the **cold-start prior** — and **never retries**, because `_loaded_mtime` is stamped
  **before** the verify (deliberately, so rejects don't re-trigger every cycle). A millisecond race
  became a **persistent model outage** until the next deploy or restart. Fixed: rejection
  **un-stamps the mtime**, so a deploy-seam race **self-heals** while a genuine tamper
  **re-rejects, once per cycle, loudly**.

Two were filed rather than fixed ([[synthesis/owed-measurements]] items 30a, 30b) and both weakened
governance where it claims to be strongest:

- **`ml/registry.py` has no real hash chain** — `verify()` compares one **unauthenticated** sha256
  from the last matching row; edits, deletions and reordering are undetectable, and deleting the
  ledger downgrades every load to "unknown provenance", which `reload()` **accepts**. **The ML-011
  gate R2-5 just made recoverable degrades to a log line if the ledger is touched at all.**
- **`ml/monitor.py:206-219` — the Wilson credibility guard is algebraically dead.** Since
  `wilson_lcb ≤ observed` always, the second conjunct is **implied by the first and can never
  veto**; the intended *"even the optimistic bound can't explain it"* test needs the **UPPER**
  bound. Worse, `baseline_brier` is scored against **the window's own realized mean** — an
  **in-window oracle** ([[concepts/wrong-null-calibration]]).

> The governing invariant still holds — every one of these makes the bot **more** conservative, not
> less (a rejected model falls to the cold-start prior; a dead credibility guard over-indicts).
> That is exactly why they survived this long: **failures in the safe direction do not announce
> themselves.**

## Both governance gaps CLOSED the same evening (commit `4799bfc7`, battery 3376/1)
Item 30 was closed in one commit, every sub-item with a test written **red-first against the
unfixed code** ([[sources/session-20260805-evening]] §5). The two that land here:

### The evidence layer — `_judge` had two defects, and they compounded
**(1) The Wilson credibility guard was ALGEBRAICALLY DEAD.** `hit_deficit` required
`raw_gap > allow` **AND** `promised − wilson_lcb > allow`. Because **`wilson_lcb ≤ observed`
always**, `promised − lcb ≥ promised − observed = raw_gap` — the second clause is **implied by the
first** and could **never veto anything**. Worse, it grew **MORE permissive as n fell**, exactly
inverting the purpose of a credibility guard. **Fixed** with a new **`wilson_ucb()`**: the promise
must clear **even the most optimistic reading of the outcomes**. That condition **implies** the
raw-gap clause (so it can actually bind) and is correctly **HARDER at small n**.

**(2) `baseline_brier` was an IN-WINDOW ORACLE.** It scored a constant equal to **the window's own
realized mean** — a forecaster no honest model can beat, because it already knows the answer. An
**all-loss 15-close window handed the baseline a clairvoyant 0.05** and convicted an
honestly-calibrated model on its **first** evaluation. **Fixed** with new **`_prior_base_rate()`**,
computed from **rows PREDATING the window only** and neutral **0.5 at cold start** — deliberately a
**weaker** baseline, hence **slower to convict**, which is the correct direction when the false
positive is **killing a working model**. Pinned by `tests/test_monitor_credibility.py` (**9 tests**).

> ⚠️ **Retraction — the "15-loss streak" example filed with item 30b was WRONG.** The original
> filing (and the first draft of the test) claimed an all-loss 15-close window at "~4-9%" should
> not convict. Against a **promised 0.30**, `0.70^15 ≈ **0.5%**` — a ~1-in-200 event **under the
> model's own claim** — so **convicting is CORRECT** there. The two defects were real; the worked
> example was not. The test now pins the **actual** mechanism: an honest **~0.18** promise
> **survives** an unlucky streak, and **the same shortfall is harder to indict at small n**.
> Never requote the retracted example ([[synthesis/open-contradictions-register]]).

> **A test was leaning on the bug.** `tests/test_monitor_deescalate_deadband.py` needed a new
> `_seeded()` helper: its fixture had been green **because of** the oracle baseline. A fixture
> tuned against a defective null is a defect with a green test in front of it — the
> [[concepts/iron-law-of-debugging]] shape.

### The provenance layer — the registry is now what its adjective claimed
`ml/registry.py` is **genuinely hash-chained**: `prev` + `seq` + content hash, **the same
construction `core/audit.py` uses**, with `verify_chain()` walking the links and — the load-bearing
change — **a broken chain now FAILS the load gate instead of authorizing it**.
`tests/test_registry_chain.py` (**9 tests**) covers edited row · deleted row · reordered rows · and
**a rewritten row minting provenance for a swapped artifact**. **The ML-011 tamper gate that R2-5
made recoverable is now backed by a property that actually holds**, and the corpus's citation hazard
is RESOLVED ([[comparisons/stated-invariants-vs-audited-reality]]).

> **The eleventh bug, found by a test for something else.** Constructing the torn-row *input* for
> the chain tests revealed that the registry writer had the **same torn-append fusion defect as
> `fills.csv`** — a crash mid-append leaves a fragment, the next write welds onto it, and **a good
> provenance record dies with the bad one**. Third instance of the class; same heal applied; now
> [[concepts/torn-append-fusion]]. Five parallel area agents had read this file in round 2 and not
> seen it.

**Net effect on the governor's honesty:** before `4799bfc7`, the evidence layer could **convict a
good model on a fair streak** and the provenance layer could **authorize a swapped artifact**. Both
failures pointed the *safe* way for the bot's risk posture (over-conservative, then cold-start
prior) — which is precisely why neither announced itself, and why the fix direction on the baseline
was chosen to be **slower to convict**, not faster.

## The self-heal — the governor unwedged its own champion (2026-08-09 02:56:04)

**The governor resolved the wedged-champion adjudication by itself, with no operator
override and no code change** ([[sources/session-20260809-gate-policy-and-self-heal]] §1,
[[concepts/ghost-badge]], [[concepts/deploy-deadlock]]).

Three of its own audit records, **4 ms apart**:

- **ML-016** — `admitted ["logistic"]`, gated `[gbt, blend, mlp, adaptive_gbt]`, **live 6,
  total 701**. [[concepts/evidence-floors]] and the [[concepts/simplicity-ladder]] behaving
  exactly as designed.
- **ML-083** — `trained_rows 9708 > corpus_rows 701`; `challenger_brier 0.24728`;
  `n_oof 464`. The era-orphan branch (`main.py:6330`): the champion's watermark indexes a
  population the matrix cannot contain, so the badge is **unfalsifiable**.
- **ML-040** — `decision DEPLOY`, **`ignore_champion: true`**, *"challenger brier 0.2473 vs
  COLD-START bar 0.25 (badge set aside: era-orphaned)"*.

**The arithmetic proving it was the ML-083 path and not the ordinary one**
(`ml/monitor.py:667-668`, evaluated on the recorded inputs): `0.24728 < 0.1537 − 0.005` is
**FALSE**, `champion_brier >= 0.25` is **FALSE** — **the normal branch would have
REJECTED**. `deploy_min_oof` is 30 and `n_oof` was 464, so the evidence floor was never the
binding term.

**Live state at filing:** `meta_model.json` `kind=logistic rows=701 oof_brier=0.24728`;
`status.json` `ml.model_kind=logistic`, era `armed=True`/`active=True`, load **701**,
`live_clean` **6**. **The bug-promoted `gbt` is no longer trading.**

> **What this says about the governor as a design.** ML-083 was adjudicated 2026-07-29 for
> the *opposite* failure — challengers locked **out** of a deadlocked deploy. It fired
> **unmodified** on a champion locked **in**, because its trigger is **structural**
> (`trained_rows > len(X)`) rather than narrative. The governing invariant held throughout:
> **the governor only ever makes the bot more conservative** — here it declined to trust a
> comparison it could not make, and fell back to an absolute bar rather than a relative one.

**The honest bound.** The detection is a **row-count proxy**. It fired because the corrupted
corpus was **larger** than the clean one; a corrupt population that happened to be
**smaller** would have compared "successfully" against incommensurable rows. The missing
field — **provenance on the stored watermark** — remains owed
([[synthesis/owed-measurements]] item 47's structural residue).

**One asymmetry this exposed, registered not fixed:** `scripts/train_meta.py:122` calls
`should_deploy` **without** the era-orphan condition, so the **CLI rejects what the runner
accepts** — measured live, two hours apart, on the same corpus (item **49**).

## ML-032 drift watch (opened 2026-08-03, open)
The day after the honest-fills regime change (`8e5455e8`), the governor raised an **ML-032
retrain request at 37% feature drift** — classified EXPECTED
([[sources/session-20260803-bug-sweep]]). By **2026-08-05 drift grew 37% → 40%**: the governor
keeps requesting retrain, and the champion/challenger bar keeps refusing the resulting worse
challengers — **both mechanisms working as designed, in tension**. Expected to resolve on its
own as post-regime-change rows accumulate in the corpus. The cost while it persists: the
deployed champion is **increasingly mismatched to the current fill regime**. Filed as a
**watch item, not a defect** — and bounded by the governing invariant (the governor only ever
makes the bot more conservative, never less).
