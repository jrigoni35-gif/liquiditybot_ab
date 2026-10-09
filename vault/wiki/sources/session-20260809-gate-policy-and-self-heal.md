---
title: "The Wedged Champion Unwedged Itself (2026-08-09 early hours) — Two Operator Adjudications Closed, and the Restraint That Was Load-Bearing"
category: source
summary: "Both open adjudications resolved. Decision 1 needed NO intervention: the codebase's own already-adjudicated ML-083 doctrine set the bug-attributable badge aside and deployed logistic on 701 clean rows — the corpus repair was the necessary AND sufficient fix, and forcing the gate would have masked that the model layer heals itself once the data is true. Decision 2 shipped as option (a) in 8e9d7e6f: OF-1/OF-7 informational while exploration is on, fail-closed, hard on synthetic, self-terminating, no threshold moved. Plus one new owed item (the CLI/runner ML-083 asymmetry) and the night's third instance of one-predicate-two-derivations."
tags: [session, adjudication, ml, deploy-gate, overfit-battery, governance, self-heal]
source_path: repo-side session record (operator dictation, re-verified against the box at filing)
source_date: 2026-08
authors: [operator, claude]
ingested: 2026-08-09
sources: 1
updated: 2026-08-09
---

# The Wedged Champion Unwedged Itself (2026-08-09 early hours)

**Head = `8e9d7e6f`, pushed. Runner live on `3c0debd7`.** The gate-policy commit is
**battery/QA-only** — `scripts/overfit_check.py` + two test files, **zero engine paths** —
so **no runner bounce is required, and nobody should bounce expecting a behaviour change.**

Two adjudications were open at the start of this session
([[synthesis/owed-measurements]] items **46** and **47**). Both are now closed. One was
closed by shipping code; the other closed **itself**, and that is the headline.

Every number below was re-verified against the box at filing (`outputs/audit.jsonl`,
`outputs/meta_model.json`, `outputs/status.json`, `git log`). Paper/real boundary
([[concepts/paper-real-boundary]]): every P&L consequence of the deployed model is
**sim-side**; the audit records, row counts, Brier scores and commit facts are
**repo-side/box-side**.

---

## 1. Decision 1 — THE WEDGED CHAMPION, RESOLVED WITHOUT INTERVENTION

### What was recommended, and what was deliberately not done

The prior filing recommended **retiring the bug-attributable champion baseline** as a
conscious re-baseline ([[concepts/conscious-re-baseline]]), and **deliberately did NOT
override the deploy gate** — CLAUDE.md forbids bypassing gates, and re-baselining is a
conscious operator act, not a patch.

**That restraint turned out to be load-bearing.** The codebase's own already-adjudicated
doctrine handled it, and an override would have hidden that capability.

### The audit-confirmed mechanism

`outputs/audit.jsonl`, three records **4 milliseconds apart**:

| Time (local) | Code | Payload |
|---|---|---|
| 02:56:04.391 | **ML-016** | `admitted: ["logistic"]`, `gated: [gbt, blend, mlp, adaptive_gbt]`, **live 6, total 701** |
| 02:56:04.480 | **ML-083** | `trained_rows 9708`, `corpus_rows 701`, `challenger_brier 0.24727982125184214`, `n_oof 464` — *"champion watermark era-orphaned … like-for-like impossible by construction; deploy gate applies the cold-start bar with the badge set aside"* |
| 02:56:04.483 | **ML-040** | `decision: "DEPLOY"`, **`ignore_champion: true`** — *"challenger brier 0.2473 vs COLD-START bar 0.25 (badge set aside: era-orphaned, see ML-083)"* |

The **era-orphan branch at `main.py:6330`** fired: the champion's `trained_rows`
watermark (**9,708** — the corrupted pooled population) **EXCEEDED** the current training
matrix (**701** rows, after the corpus repair re-armed era exclusion), so the
like-for-like fresh-row set is **empty by construction** and the badge is
**unfalsifiable**. Per the **ML-076 / ML-083 doctrine — *an unfalsifiable badge may not
gate*** — the orphaned badge was set aside entirely (`should_deploy(..., ignore_champion=True)`)
and the challenger faced the **true cold-start standard**: `Brier < 0.25` plus the
`deploy_min_oof` evidence floor.

**`logistic` scored `oof_brier` 0.24728 < 0.25 and DEPLOYED on 701 clean rows.**
`n_oof` 464 clears `deploy_min_oof` 30 comfortably.

### The arithmetic that PROVES the mechanism (not inferred)

Read directly off `ml/monitor.py:667-668`, the **normal** branch is:

```python
ok = challenger_brier < self.champion_brier - self.deploy_margin \
    or (self.champion_brier >= 0.25 and challenger_brier < 0.25)
```

Substituting the live numbers (`deploy_margin` = **0.005**, the `challenger_brier_margin`
default, unset in `config.json`):

- `0.24728 < 0.1537 − 0.005 = 0.1487` → **FALSE**
- `0.1537 >= 0.25` → **FALSE**

**The normal branch would have REJECTED.** Only the ML-083 path deploys — where
`ignore_champion` short-circuits to `ok = challenger_brier < 0.25`
(`ml/monitor.py:654-655`). This is not an inference from the outcome; it is the two
predicates evaluated on the recorded inputs.

**The corpus repair is what made the watermark exceed the matrix** — and therefore what
triggered the self-heal. Before the repair, the pooled corpus was 9,746 loaded rows and
the watermark did not orphan.

### Verified live at filing

| Artefact | Reading |
|---|---|
| `outputs/meta_model.json` | `kind: logistic`, `rows: 701`, `oof_brier: 0.24727982125184214`, `feature_schema_version: 9` |
| `outputs/status.json` `ml.model_kind` | **`logistic`** |
| `ml.load_stats.era_exclusion` | **`armed: True`, `active: True`** |
| `ml.load_stats.rows` / `live_clean` | **701** / **6** |
| `ml.load_stats.label_era.triple_barrier_h432.rows` | **701** (`tb_time` 251 · `tb_sl` 269 · `tb_pt` 181) |

**THE BUG-PROMOTED GBT IS NO LONGER TRADING.**

### The lesson — file this as a POSITIVE instance

The corpus repair (`3c0debd7`) was the **necessary and sufficient** intervention. **The
model layer healed itself once the data was true.** Forcing the gate would have produced
the same visible outcome (a logistic deployed) while **masking that the system could reach
it alone** — and would have spent a conscious-re-baseline decision that was never needed.

> **The system's own doctrine outperformed the proposed override.** ML-083 was adjudicated
> on 2026-07-29 for the *opposite* polarity of this deadlock (challengers locked **out**);
> it fired correctly, unmodified, on the polarity it was never written for (a champion
> locked **in**) — because it keys on the **structural** condition (`trained_rows > len(X)`)
> and not on the story.

This is the counterweight to [[concepts/false-green]]: that page catalogues gates whose
green did not entail the work. Here a gate's **refusal to be compared** was the correct,
load-bearing behaviour, and the right operator action was **to do nothing and watch**.

---

## 2. NEW OWED ITEM — the CLI/runner asymmetry on ML-083

`scripts/train_meta.py:122` calls:

```python
if not monitor.should_deploy(challenger_brier, n_oof=n_oof):
```

**without the era-orphan detection that `main.py:6330` has.** The CLI applies the stale,
incomparable badge where the runner correctly sets it aside — so **the CLI REJECTS
challengers the runner ACCEPTS.**

**This bit live.** At **00:52** the CLI **REJECTED** `logistic` at **0.2714** on the badge
comparison — roughly **two hours before** the runner deployed `logistic` at **0.2473** via
ML-083 on the same wedged badge.

**The trap is sharp because the bot's own ML-032 message instructs the operator to run
`python scripts/train_meta.py`.** An operator following the bot's own instruction gets a
verdict the bot itself would not reach, with a REJECT message that reads authoritatively
("*This mirrors the bot's own auto-retrain deploy gate*" — `train_meta.py:126`, a claim
that is now false in exactly this case).

**Fix:** mirror `main.py`'s `int(champ.trained_rows) > len(X)` condition + the ML-083 audit
log + `ignore_champion=True`. **Registered as [[synthesis/owed-measurements]] item 49 and
deliberately NOT bundled into tonight's commit** — a gate-policy commit and a deploy-gate
behaviour change are two reviewable things, not one.

> Note this is itself an instance of the night's pattern (§4): **one decision, two
> derivations** — the runner's and the CLI's — silently disagreeing.

---

## 3. Decision 2 — THE OVERFIT GATE POLICY, IMPLEMENTED AS OPTION (a) (`8e9d7e6f`)

### The adjudication

**OF-1 and OF-7's dead-feature check are MODEL-READINESS gates that were being used as
CODE-DEPLOY gates.** The battery stage feeds `auto_update.battery_passes`
([[entities/auto-update]]), so **a data-starved corpus was holding code-safety fixes
hostage** — conflating model readiness with code correctness. Last night that meant a
critical staleness fix could not ship because the model needs more rows.

**The verdict scoped WHAT THE READING BLOCKS, never WHAT IT MEASURES.** That is the
distinction that keeps this on the right side of [[concepts/never-widen-a-gate]]: nothing
was relaxed about the measurement, only about which battery arm its verdict is allowed to
stop.

### What was NOT done — each pinned by a test

| Not done | Pin |
|---|---|
| **No threshold moved** — 0.12 (memorization band) and 0.55 (dead-fraction) unchanged | `test_thresholds_are_untouched` **fails if either literal is edited** |
| **The numbers still print EVERY run** — labelled `"INFORMATIONAL (OVER the 0.12 memorization band)"` with the gap value **and** the re-arm condition | `test_informational_lines_still_report_the_number` |
| **Model TRUST untouched** — `ml.model_selection` evidence floors still gate to `logistic` at live=6; the live governor still kills a confidently-wrong model on realized outcomes | (observed live: ML-016 at 02:56:04) |

> *"A softened gate that stops printing its measurement is how a red goes invisible"* —
> the commit's own words, and the reason the informational path asserts the **value** and
> the **re-arm condition**, not merely that it printed something.

### What WAS done — four properties, all deliberate

1. **Informational ONLY while `ml.exploration.enabled`** — the **OF-5/DSR precedent**. The
   corpus is dominated by **EV-mixed PT-050 probe/candidate rows bought to acquire
   labels**, so OF-1 is grading the **acquisition phase**, not a strategy.
2. **FAIL-CLOSED** — a caller that could not read the config passes `explore_on=False` and
   gets the **full gate**. Unreadable config never buys leniency.
3. **HARD on the SYNTHETIC benchmark, always** — there OF-1/OF-7 validate the
   **INSTRUMENT** against a **planted signal with a known answer**. *An instrument may not
   grade itself leniently.*
4. **SELF-TERMINATING** — flip exploration off and **both re-arm**. No stamp to clear, no
   operator memory required, no expiry date to miss.

### The implementation

A **pure predicate**, `scripts/overfit_check.py:101`:

```python
def gate_is_informational(explore_on: bool, on_synthetic: bool) -> bool:
    return bool(explore_on) and not bool(on_synthetic)
```

*"One function so the two gates can never drift apart, and a pure one so the policy is
unit-testable instead of only observable through a 40s CLI run."* Both OF-1 (`:745`) and
OF-7's dead-feature check (`:943`) call it. **8 tests** in
`tests/test_overfit_gate_policy.py`:

`test_only_soft_during_exploration_on_live_data` · `test_hard_gate_once_exploration_is_off` ·
`test_synthetic_benchmark_always_gates` · `test_fails_closed_on_unknown_phase` ·
`test_both_gates_use_the_one_predicate` · `test_thresholds_are_untouched` ·
`test_informational_lines_still_report_the_number` ·
`test_synthetic_run_keeps_hard_pass_fail_verdicts`

### BONUS DEFECT FIXED — `_explore_on` was derived TWICE

`_explore_on` was being derived **twice** inside `overfit_check.py`: once at the config
block (`:693`, through `main.load_config`), and once **inside the DSR block from a SECOND
direct read of the repo's `config.json` that BYPASSED `main.load_config`** — so **an
injected config could not influence OF-5's phase.** Now derived **once**, through the
injectable path (`:999` carries the explicit comment that it is *not* re-derived here).

This is the night's **second** instance of the §4 pattern, and it was found only because
building the gate policy forced a look at how phase is resolved.

### The brittle assertion this exposed

The `_explore_on` fix broke `tests/test_audit_ml_offline.py` — a **bare substring check**
read **`"2|0 live labeled trades"`** as the **`"0 live labeled trades"`** it meant to
forbid, so the test **FAILED on a report that proves the fix**. Now **word-boundary
anchored**. Filed to [[synthesis/documentation-drift-register]]: a test that pins a string
rather than a property fails on the fix, not on the bug.

### The battery — ALL GREEN

**pytest 3473 passed + 1 skipped (parallel `-n 8`, `-m "not timing"`) · 19 serial timing ·
smoke 219 · assurance 49 · overfit 3 pass / 0 fail · ruff · pyright · bandit · compileall ·
quant G1–G5.**

Two firsts, both worth stating:

- **The first fully-green battery since the incident.**
- **The first ever in which the overfit stage grades the LIVE corpus rather than falling
  back to synthetic.** Every prior all-green battery in this project's history was green at
  a stage that was measuring a **planted signal**, because `len(X) >= len(FEATURE_NAMES)*10`
  (640) was never satisfied on a clean corpus. That is a *stronger* green than any that
  preceded it, and the policy is what made it reachable without moving a number.

*(Timing family note: **19 serial**, up from the 18 recorded at `3c0debd7` —
[[synthesis/owed-measurements]] item 44's census continues to accrete members.)*

---

## 4. THE PATTERN — three instances of one class in a single night

**One predicate/measurement, two derivations, silently disagreeing:**

| # | Instance | The two derivations | Cost |
|---|---|---|---|
| 1 | **`label_era`** | `migrate_history.py:125` **derived** it vs `ml/history.py` `_row_era` **persisted** it | **2,729 corrupted corpus rows**, era filter disarmed, a champion deployed on a data bug |
| 2 | **`_explore_on`** | config block via `main.load_config` vs a **second direct `config.json` read** inside the DSR block | an injected config **could not influence OF-5's phase** — a test-only blind spot, but a real one |
| 3 | **the champion badge** | 0.1537 computed on the **corrupted pooled 9,708-row** population vs 0.2714/0.2473 on the **clean 701-row** population | ML-083's own subject — the wedged champion |

**The new gate policy was deliberately built as a single pure predicate to avoid becoming
the fourth.** That is the pattern's first *prospective* application in this corpus: every
prior instance was diagnosed after it fired.

**Filed as a new section of [[concepts/two-paths-one-quantity]]**, which already carries
this class, rather than as a fourth page. [[concepts/migration-idempotence]] is the
**special case** where one of the two derivations **writes** — an idempotence failure is
two-derivations-of-one-truth with the loser overwritten on disk.

---

## 5. Ledger

| Item | Status |
|---|---|
| [[synthesis/owed-measurements]] **46** (overfit gate policy) | **CLOSED** — option (a) shipped `8e9d7e6f` with its pins |
| [[synthesis/owed-measurements]] **47** (wedged champion) | **CLOSED** — resolved **without intervention** by ML-083; audit evidence above |
| [[synthesis/owed-measurements]] **49** (CLI/runner ML-083 asymmetry) | **NEW, OPEN** |
| Head | `8e9d7e6f`, pushed |
| Runner | live on `3c0debd7` — **no bounce needed**; the gate-policy commit is battery/QA-only |

## Related
[[concepts/ghost-badge]] · [[concepts/deploy-deadlock]] · [[concepts/two-paths-one-quantity]] ·
[[concepts/migration-idempotence]] · [[concepts/false-green]] ·
[[concepts/never-widen-a-gate]] · [[concepts/conscious-re-baseline]] ·
[[concepts/overfit-battery]] · [[concepts/dof-budget]] · [[concepts/evidence-floors]] ·
[[concepts/simplicity-ladder]] · [[concepts/era-exclusion]] ·
[[entities/overfit-check]] · [[entities/ml-governor]] · [[entities/auto-update]] ·
[[entities/reason-code-registry]] · [[sources/session-20260809-corpus-corruption]] ·
[[synthesis/learning-pipeline-arc]] · [[synthesis/documentation-drift-register]] ·
[[synthesis/owed-measurements]]
