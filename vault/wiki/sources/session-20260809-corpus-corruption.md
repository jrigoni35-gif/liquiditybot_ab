---
title: "The Corpus Corruption Incident (2026-08-08/09) — One Non-Idempotent Line Pooled Three Label Definitions, Disarmed the Era Filter, and Deployed a Champion on a Data Bug"
category: source
summary: "Commit 3c0debd7 fixes two independent defects found by an ADVERSARIAL AUDIT OF THE PREVIOUS COMMIT (36fcfd6e), not by the battery. (1) THE CORPUS INCIDENT, CRITICAL and self-inflicted: scripts/migrate_history.py:125 recomputed label_era unconditionally as label_era_of(barrier) — the ONLY non-idempotent trailing column in migrate_rows, violating an idempotence rule documented in the pt_frac comment IMMEDIATELY BELOW it. label_era_of() has no horizon knowledge (returns unqualified 'triple_barrier' for any tb_*) while the writer ml/history.py _row_era -> triple_barrier_era(label_max_bars) persists 'triple_barrier_h432', so every migration pass merged label definitions that must never share a name. Triggered by the session's OWN 41b commit (64724480): +4 columns -> _ensure_schema rotated the corpus 20:01:30 -> corpus_sync recover_local_baks merged the .bak back THROUGH migrate_rows 20:01:46. Blast radius verified twice independently: 2,729 rows across two rotations (h24->triple_barrier 2,077; h432->triple_barrier 652), zero rows lost, the live 'triple_barrier' bucket pooling THREE incompatible 96/24/432-bar label definitions. Consequence chain, not cosmetic: current-era count 690->42 < min_new_era_rows=150 -> era filter DISARMED -> pooled corpus into training 690->9,746 -> live_clean 5->299 -> cleared min_live_rows for gbt(60)/blend(60)/mlp(150)/adaptive_gbt(250) IN ONE STEP -> gbt champion DEPLOYED 20:10:44 on a DATA BUG; the same disarm flipped overfit_check from synthetic to live grading and turned the battery red. FIX: pass the persisted label_era through, derive only when absent (also scripts/session_import.py:244, unattended hourly); 3 red-first tests in tests/test_migrate_history.py. CORPUS REPAIRED: 2,729 cells restored from two preserved backups by position_id join, most-qualified-wins, 0 conflicts, 0 rows added/removed/reordered, concurrent-append-safe, pre-repair backup retained; verified after — era armed=True/active=True, load 9,746->690, live_clean 299->6. (2) CORRECTS AN EARLIER FILING IN PLACE: the claim that the overfit red came from 'live rows crossing a 60-row synthetic->live threshold' is FALSE IN BOTH HALVES — there is no 60 (the predicate is len(X) >= len(FEATURE_NAMES)*10 = 640, and len(X) is LOADED rows, not live rows; the flat 60 was deleted 2026-07-11 by 7486ab29), and the flip was the era-filter DISARM, i.e. this corruption. (3) THE HONEST GATE VERDICT on the REPAIRED corpus: 3 pass / 4 fail — OF-1 gaps +0.422/+0.414/+0.503 WORSE than the pooled corpus's +0.19..+0.27 exactly as a smaller cleaner corpus should be, OF-7 dead_frac 0.95, rows/feature 10.8 barely passing; the audit's own learning curve reads CLIMBING (delta_auc=+0.112, 'data-starved: corpus growth is the highest-leverage learning input'), restating the DoF adjudication in the gate's own voice. NO THRESHOLD MOVED. (4) NEW OWED ITEM — THE WEDGED CHAMPION: train_meta correctly re-gated to ['logistic'] but the champion gate REJECTED the swap (challenger OOF brier 0.2714 vs champion 0.1537 measured on the CORRUPTED 9,708-row corpus) — incommensurable evaluation sets wedge a bug-promoted champion in place; the gate was deliberately NOT overridden. (5) 42a AUDIT: a CRITICAL-latent VETO BAND fixed — kraken_max_book_age_sec 5.0 > pretrade.max_data_staleness_ms 4000ms served 4-5s books that PT-020 then vetoed while PREEMPTING a fresh REST read (~0.6-3% of entry evaluations, worst on thin pairs: MINA 3.2%, FLOW 2.9%, PAXG/LINK 1.9%, BTC 0.6%); fixed 5.0->3.5 plus a config_guard FATAL on the relation itself. Three KNOWN LIMITS of 42a filed honestly: REST-path sign inversion (staleness_ms <= 0 for any book fetched this cycle — no new detection power on REST), the pre-42a code was NOT tautological on the FAILURE path, and DL-10 cannot benefit (a quantity capped at 3.5s cannot cross stale_critical_sec=120). (6) OWED-44 GAP CLOSED: test_import_integrity was never tagged @pytest.mark.timing, went red on TimeoutExpired, is the most SELF-saturating test in the suite — now serial, timing family 17->18. Battery all green except an honestly RED overfit stage. PROCESS LESSON: 36fcfd6e's commit message asserted 'the identical red reproduces on the parent commit' — ASSERTED, NEVER RUN; running it would have made the +9,272-row jump unmissable the same evening."
tags: [session, incident, corpus, label-era, migration, idempotence, era-exclusion, overfit, champion, staleness, config-guard, governance, correction]
sources: 1
source_path: none — session work product (one shipped commit, one corpus repair, one in-place correction of a prior filing)
source_date: 2026-08
authors: [operator, claude-session]
ingested: 2026-08-09
updated: 2026-08-09
---

# The Corpus Corruption Incident (2026-08-08/09)

## Provenance and boundary statement

Session work product, filed same session per governance rule 12, from the executing
session's own record. Commit `3c0debd7` verified on the box at filing (`git log`, the
migrator's new idempotence comment read in full, `config.json:887-888`,
`scripts/overfit_check.py:9-14` and `:180-182,:207,:228`, the `@pytest.mark.timing`
inventory across 8 files).

**Paper/real boundary** ([[concepts/paper-real-boundary]]): everything here is
**repo-side** (a data-integrity defect in the migrator) and **box-side** (the repair
executed against the live corpus file). **No sim dollar is quoted.** The corrupted and
repaired rows are training-corpus rows whose live-era entries are
**sim-execution-conditioned by construction**; the champion that got deployed on the bug
sizes simulated positions. The 42a veto-band exposure percentages are
**venue-data-side** facts about real Kraken feeds.

> ⚠️ **This page corrects [[sources/session-20260808-night-staleness-overfit]] §2 in
> place.** That filing named a root cause that is **false in both halves**. The false
> claim has been struck on that page, not deleted; §9 below is the retraction record.

---

## 1. Root cause — one line, and the rule it broke was in the comment below it

`scripts/migrate_history.py:125` recomputed `label_era` **unconditionally**:

```python
label_era_of(r.get("barrier") or "")
```

It was the **ONLY non-idempotent trailing column** in `migrate_rows`. Every other
trailing column — `pt_frac`, `sl_frac`, the 7 `sg_*`, `entry_price`, `exit_price`, the
4 new `avail_*` — uses the `r.get(X) or <pad>` pass-through. **The idempotence rule it
violated is documented in the `pt_frac` comment IMMEDIATELY BELOW it** ("a second
migration pass must never clobber real geometry").

The mechanism is [[concepts/two-paths-one-quantity]] in its purest form — two functions
computing "the row's label era", disagreeing on the one thing that matters:

| Path | Function | Produces |
|---|---|---|
| **Writer** (production) | `ml/history.py` `_row_era` → `triple_barrier_era(label_max_bars)` | `triple_barrier_h432` — **horizon-qualified** |
| **Migrator** (this bug) | `scripts/migrate_history.py` `label_era_of(barrier)` | `triple_barrier` — **unqualified for ANY `tb_*`** |

`label_era_of()` **has no horizon knowledge**. So every migration pass silently
re-tagged era-qualified rows into the pooled bucket, **merging label definitions that
must never share a name**. See [[concepts/label-era]], whose "derived purely from the
row's own barrier string" framing is exactly the premise this incident falsifies.

## 2. Trigger — the session's own commit, one file rotation later

Self-inflicted, and the chain is short:

1. **`64724480` (owed 41b)** added 4 corpus columns.
2. `_ensure_schema` **rotated the corpus** at **20:01:30**.
3. `corpus_sync`'s `recover_local_baks` **merged the `.bak` back THROUGH `migrate_rows`**
   at **20:01:46**.

Sixteen seconds. A schema change the same session shipped, running through a recovery
path the same session did not think about, is what fired the latent line.

## 3. Blast radius — verified twice, independently

Verified by **position_id join** *and* by **re-running `migrate_rows` on the real
`.bak`** — two methods, same answer:

| Rotation | From | To | Rows |
|---|---|---|---|
| 1 | `triple_barrier_h24` | `triple_barrier` | **2,077** |
| 2 | `triple_barrier_h432` | `triple_barrier` | **652** |
| | | **Total** | **2,729** |

**Zero rows lost.** The damage was purely to the era *tag* — which is worse than losing
rows, because the live `triple_barrier` bucket was then **pooling THREE incompatible
label definitions** (the 96-bar legacy era, the 24-bar era, and the current 432-bar era).
A corpus that has forgotten which label definition produced each row cannot be filtered
back into coherence by any downstream consumer.

## 4. Consequence chain — the damage was not cosmetic

Every link measured:

| Link | Before | After | Mechanism |
|---|---|---|---|
| Current-era row count | **690** | **42** | era-exclusion arms on the current-era count; retagged rows left the bucket |
| Era filter | armed | **DISARMED** | 42 < `ml.era_exclusion.min_new_era_rows` = **150** |
| Training load | 690 | **9,746** | the whole pooled corpus entered training |
| `live_clean` | 5 | **299** | pooled live rows counted as current-era |
| Evidence floors | blocked | **cleared IN ONE STEP** | `ml.model_selection.min_live_rows` for `gbt`(60) / `blend`(60) / `mlp`(150) / `adaptive_gbt`(250) |
| Champion | logistic | **gbt DEPLOYED 20:10:44** | on a **DATA BUG**, not evidence |
| Overfit stage | synthetic grading | **LIVE grading, RED** | `len(X)` crossed `640` because of the same disarm |

Nine minutes and fourteen seconds from the corrupting merge to a deployed champion. This
is [[concepts/evidence-floors]]'s worst case: floors designed to stop an under-evidenced
family from manufacturing a lucky winner were cleared **all four at once** by a counter
that was lying — and clearing four floors in a single step is itself the signature that
should have been alarming.

## 5. The fix (`3c0debd7`)

**Pass the persisted `label_era` through; derive only when absent.** The migrator now
matches every other trailing column. Legacy rows that genuinely have no persisted value
still derive one — so the migrator remains able to do its original job.

The same defect was present in **`scripts/session_import.py:244`**, which runs **hourly
and unattended** under `corpus_sync --apply` — the same unattended third-writer path that
[[sources/session-20260806-append-gate]] found for the torn-append class. Fixed there too.

**3 red-first tests in `tests/test_migrate_history.py`:**

1. a persisted era is **preserved**;
2. **migration is a fixed point** (migrate twice ≡ migrate once);
3. a **legacy row still derives** its era.

Red-first proven **by construction** — the tests fail on the parent tree by the same
arithmetic that produced the 2,729 rows.

## 6. The corpus REPAIRED — the part that is not a code change

The fix stops the bleeding; it does not restore the tags. The repair did:

- **2,729 `label_era` cells restored** from the two preserved backups
  (`.bak_1785879005.recovered`, `.bak_1786237290.recovered`);
- **position_id join**, **most-qualified-wins** resolution, **0 conflicts**;
- **0 rows added / removed / reordered**, **no other cell touched**;
- **concurrent-append-safe** — the live runner was appending during the repair;
- pre-repair backup `signal_history.csv.prerepair_1786253662` **retained**.

**Verified after the repair:** era filter `armed=True` / `active=True`; load
**9,746 → 690**; `live_clean` **299 → 6**. Every link of §4 walked back.

This is the [[concepts/era-exclusion]] design paying off in the direction nobody planned
for: because exclusion is a **load-time view** and **nothing is ever deleted**, the raw
rows survived the corruption intact and only a derived column needed restoring.

## 7. Re-corruption risk CLOSED

`pc_supervisor` **spawns `corpus_sync` as a fresh process** (`_spawn` at `:657`), so it
picks the fixed migrator up off disk. There is **no stale in-memory code hazard** — the
next hourly unattended run cannot re-corrupt from a cached import.

## 8. The honest gate verdict on the REPAIRED corpus (operator decision OWED)

The repair does not turn the battery green, and **no threshold was moved**
([[concepts/never-widen-a-gate]]).

**3 pass / 4 fail** on the clean corpus:

- **OF-1 memorization gaps: +0.422 / +0.414 / +0.503** (logistic / gbt / mlp) — **WORSE**
  than the pooled corpus's +0.19..+0.27, **exactly as a smaller, cleaner corpus should
  be.** The pooled reading was flattered by 9,000 rows of other-era labels.
- **OF-7 `dead_frac` = 0.95** — 61 of 64 features at near-zero importance.
- **OF-7 rows/feature = 10.8** — **PASSES, but barely** (690 rows / 64 features).
- **shuffle and purge PASS.**

The audit's own learning-curve diagnostic states the conclusion in the gate's voice:

> **"CLIMBING (delta_auc=+0.112) — data-starved: more rows are still buying skill; corpus
> growth is the highest-leverage learning input right now."**

That is the 2026-08-08 [[concepts/dof-budget]] adjudication — hundreds of labels fund
~2-5 effective context features, 64 features against ~61 fresh-era labels, **ledger
CLOSED** — restated by an independent instrument that was not told the answer.

**The battery cannot go green at the overfit stage until the corpus grows or the feature
count drops** (item 45f, the schema-AB prune experiment). Policy options for the operator,
**registered NOT decided**:

- **(a)** exploration-phase **informational** grading for OF-1/OF-7 (the DSR precedent);
- **(b)** **hard block** until the corpus grows;
- **(c)** **`--force-synthetic`** in the battery until era-3 matures.

The [[entities/auto-update]] deploy gate (`auto_update.battery_passes`) is **blocked
meanwhile**.

## 9. What this filing RETRACTS — the false root cause, corrected in place

*(The retraction pattern this vault requires: what was claimed → what refuted it → what
stands.)*

**WHAT WAS CLAIMED** ([[sources/session-20260808-night-staleness-overfit]] §2, filed
2026-08-08 night): the overfit red was caused by *"live rows crossing `overfit_check`'s
60-row synthetic→live threshold"*, described as **honest cold-start growth**.

**WHAT REFUTED IT — both halves are false:**

1. **There is no 60.** The predicate is
   **`len(X) >= len(FEATURE_NAMES) * 10 = 640`** (`scripts/overfit_check.py:180-182,
   :207`). **The flat `60` was DELETED 2026-07-11 by `7486ab29`** ("fix a live min_rows
   data-starvation bug") — it had not existed for a month.
2. **`len(X)` is LOADED rows — candidate + live, after every filter — not live rows.**
   The corpus holds **305 live rows total** and is **append-only**, so the battery's own
   printed **"live rows=467"** was **arithmetically impossible** and should have been the
   tell.
3. **The arithmetic names the real cause.** Between the 17:06 and 23:30 batteries only
   **33 rows** were appended (**all candidate**), while the **loaded** count jumped
   **467 → 9,739**. A 9,272-row jump is not growth; it is the **era-filter DISARM** —
   i.e. **this corruption**.

**WHAT STANDS:** the overfit stage *is* honestly red, and the red *is* the DoF ledger
stated back by the gate — but for the corrected reason, on the corrected (repaired)
corpus, with the corrected numbers of §8. The **conclusion survived its own false
premise**, which is precisely why the premise had to be checked.

**Two stale strings caused the misreading, and both are fixed at source in `3c0debd7`:**
the module docstring (`:9`) and the report string (`:216`) both **mislabelled total
loaded rows as "live rows"**. Filed to
[[synthesis/documentation-drift-register]] — an instrument that prints the wrong noun for
its own quantity will eventually be believed.

## 10. NEW OWED ITEM — the WEDGED CHAMPION

`train_meta` on the repaired corpus **correctly re-gated selection to `['logistic']`**
(live=6, total=692; `gbt`/`blend`/`mlp`/`adaptive_gbt` skipped) — the
[[concepts/simplicity-ladder]] working as designed.

**But the champion gate REJECTED the swap:**

| | OOF Brier |
|---|---|
| Challenger (logistic, **clean** 692-row corpus) | **0.2714** |
| Champion (gbt, **corrupted pooled** 9,708-row corpus) | **0.1537** |

The champion's 0.1537 was **measured on the corrupted corpus**. The gate is comparing
scores computed on **incommensurable evaluation sets**, so the **bug-promoted gbt is
WEDGED in place** and **no clean-corpus challenger can ever dislodge it**. This is a new
instance of [[concepts/ghost-badge]] — a watermark computed on a population that no
longer exists — and a new spelling of [[concepts/deploy-deadlock]].

**The gate was deliberately NOT overridden.** CLAUDE.md forbids bypassing gates, and
re-baselining is a **conscious operator act** ([[concepts/conscious-re-baseline]]).

**Recommendation to adjudicate:** retire the champion baseline as **bug-attributable**
and re-baseline on the clean corpus — the same verb the weekly-budget lockout earned for
bug-attributable consumption ([[sources/session-20260808-budget-reanchor]]).

**Safety net meanwhile:** the [[entities/ml-governor]] still grades the live model on
**realized outcomes**, so a wedged champion that is actually bad gets attenuated by
measurement rather than by the selection gate.

> ### ✅ RESOLVED the same night, 2026-08-09 02:56:04 — WITHOUT the recommended re-baseline
>
> **The recommendation above was never executed and was never needed.** The gate was left
> alone, and the codebase's **own already-adjudicated ML-083 doctrine** unwedged the champion
> ([[sources/session-20260809-gate-policy-and-self-heal]] §1).
>
> As the corpus grew past this filing (692 → **701** rows), the **era-orphan branch**
> (`main.py:6330`) triggered: the champion's `trained_rows` watermark (**9,708** — the
> corrupted pooled population) **EXCEEDED** the training matrix, so the like-for-like
> fresh-row set is **empty by construction**, the badge is **unfalsifiable**, and per
> **ML-076/ML-083 doctrine** it was **set aside entirely** (`ignore_champion=True`). The
> challenger then faced the true **cold-start** bar and passed: `logistic` **0.24728 <
> 0.25**, `n_oof` **464**, **DEPLOYED**. Audit: **ML-016** 02:56:04.391 → **ML-083**
> 02:56:04.480 → **ML-040** 02:56:04.483.
>
> **The arithmetic proves it was that branch:** under the normal branch
> (`ml/monitor.py:667-668`) `0.24728 < 0.1537 − 0.005` is **FALSE** and
> `champion_brier >= 0.25` is **FALSE** — it would have **REJECTED**.
>
> **This section's own restraint is what made the resolution visible.** *"The gate was
> deliberately NOT overridden"* was the load-bearing decision: an override would have
> produced the same deployed model while hiding that the system could reach it alone.
> **The corpus repair (§1–§7) was the necessary AND sufficient intervention.**
>
> **Still owed:** the structural residue — a stored watermark records a *score* and not the
> *corpus* that produced it, and ML-083's row-count proxy would **not** have fired had the
> corrupt population been *smaller* than the clean matrix
> ([[synthesis/owed-measurements]] item 47). Plus a **new** item **49**: the CLI
> (`scripts/train_meta.py:122`) lacks this branch, so it **REJECTS what the runner ACCEPTS**
> — measured live, 00:52 vs 02:56, same corpus.

## 11. The 42a audit — one CRITICAL-latent defect, three honest limits

An adversarial audit of the session's **own** previous commit (`36fcfd6e`,
[[sources/session-20260808-night-staleness-overfit]] §1).

### 11.1 CRITICAL-latent: the VETO BAND (fixed in `3c0debd7`)

`websockets.kraken_max_book_age_sec` = **5.0s** exceeded
`pretrade.max_data_staleness_ms` = **4000ms**. Once 42a made `book_ts` **data time**, a
ws book aged **4–5s** is **SERVED by the cache** and then **VETOED by PT-020** — and
because `main.py` only falls back to REST when the ws returns `None`, **that doomed book
PREEMPTS a REST read that would have been fresh.**

**Exposure ~0.6–3% of entry evaluations**, worst on the thinnest pairs — **MINA 3.2%,
FLOW 2.9%, PAXG/LINK 1.9%, BTC 0.6%** — which **skews which assets can accumulate fill
labels at all**. A silent, asset-selective refusal to enter is the kind of defect that
poisons a corpus rather than announcing itself.

**Masked only because the book was full 5/5** (pre-trade unreachable); it **would arm the
moment a position closed.**

**FIX:** `5.0 → 3.5`, **plus a `config_guard` FATAL on the relation itself** — verified
two-sided (it FATALs the old config, passes the new). The knob now carries its own note:
*"Lower this knob rather than raising the veto ceiling"* — [[concepts/never-widen-a-gate]]
written into the config.

**And the documentation that asserted the falsified premise is fixed:**
`config_guard:2835-2848` prose still **ASSERTED** the very premise 42a falsified
("book_ts is stamped at read time, not data time"), and **`tests/test_audit_fixes.py`
pinned that dead premise in its test NAME and assertion message.** Both rewritten. A test
that pins a premise by name outlives the premise unless someone renames it.

### 11.2 KNOWN LIMITS of 42a, filed honestly

Registered as open sub-items. **The genuine gain is the WS path only.**

1. **REST-path sign inversion.** `now` is frozen at cycle start, but `recv_ts` is stamped
   **AFTER** the blocking fetch — so `staleness_ms <= 0` for **any** book fetched this
   cycle. A **50s REST hang reads −50000ms**. The change buys **NO new detection power on
   the REST path.**
2. **The pre-42a code was NOT tautological on the FAILURE path** — `book_ts` held the
   **last successful cycle's `now`** and grew **~5s/cycle**. That is precisely the path
   `36fcfd6e`'s commit message led with. The tautology was real on the **success** path
   only ([[concepts/tautological-instrument]] corrected accordingly).
3. **DL-10 cannot benefit.** The new measurement is **capped at
   `kraken_max_book_age_sec` (now 3.5s)** while DL-10 / the watchdog trip at
   `stale_critical_sec` = **120**. **A quantity capped at 3.5 cannot cross 120.**

## 12. OWED-44 gap CLOSED — the most self-saturating test in the suite

`tests/test_import_integrity.py` was **never tagged `@pytest.mark.timing`** and went red
in this battery on `TimeoutExpired`. It is the **most SELF-saturating test in the suite**:
**8 threads × ~100 fresh interpreter spawns**, each under a **hard 120s wall deadline**,
running **inside the `-n 8` parallel pass alongside the live BelowNormal runner** — and it
**passes solo in 4.3s**.

Now serial. **Timing family 17 → 18**, across 8 files. Same disposition as
[[sources/session-20260808-battery-split-freeze-gate]] §1: **scheduling changed, the gate
did not.** The owed-44 taxonomy was right; the inventory was one test short — a small
instance of [[concepts/adoption-is-not-enforcement]], since nothing forces a *new*
self-saturating test to declare itself.

## 13. Battery and deploy state

pytest **3466 + 1 skipped** parallel / **18 serial** timing · smoke **219** · assurance ·
ruff · **pyright 0 errors** · bandit · compileall · quant **G1–G5 ALL GREEN**.
**Overfit honestly RED** (§8).

Committed **`3c0debd7`**, **pushed**. Runner bounce **sent**; relaunch onto `3c0debd7`
**pending confirmation at filing time** — so at filing this is
**committed-and-pushed, not confirmed-running** ([[entities/auto-update]]'s
local-commit blind spot).

## 14. PROCESS LESSON — "reproduces on the parent commit" was ASSERTED, NEVER RUN

`36fcfd6e`'s commit message asserted **"the identical red reproduces on the parent
commit."** It was **asserted, never run.**

**Had it been run, the +9,272-row jump would have been unmissable, and the corruption
would have been caught the same evening.** Instead the false premise reached the wiki and
had to be corrected in place one day later.

**The disclosure precedent ([[sources/session-20260807-evening-ops]], `f07d60f8`) is
tightened:**

1. **A battery stage turning red FOR THE FIRST TIME is a blocking investigation, not a
   disclosable footnote.** The disclosure precedent covers *known, characterized* flakes —
   it was never a license to ship past a novel red.
2. **Any "orthogonal" / "reproduces on parent" claim must ship with the command that
   produced it.** An orthogonality claim is a *measurement*; without its command it is a
   *hope*.

Filed to [[concepts/false-green]] — this is the mirror specimen: not a green that did not
entail the work, but a **red that was explained away by an unrun claim**.

## 15. Register moves

- **Item 46 CORRECTED and, for the first time, actually written** into
  [[synthesis/owed-measurements]] — the prior filing referenced "item 46" but never
  created the entry.
- **NEW item 47** — the wedged champion (operator adjudication owed, §10).
  **→ CLOSED the same night, RESOLVED WITHOUT INTERVENTION** by the ML-083 era-orphan
  branch ([[sources/session-20260809-gate-policy-and-self-heal]] §1). Structural residue
  (watermark provenance) still open.
- **Item 46 → CLOSED the same night**, commit `8e9d7e6f`, option (a) — exploration-phase
  informational grading for OF-1/OF-7, fail-closed, hard on synthetic, self-terminating,
  no threshold moved (same source, §3).
- **NEW item 49** — the CLI/runner ML-083 asymmetry: `scripts/train_meta.py:122` lacks the
  era-orphan branch, so the CLI **rejects what the runner accepts** (same source, §2).
- **Item 42(a) reopened as sub-limits** — the three known limits of §11.2.
- **Item 44 addendum** — the 18th timing test. *(19th arrived with `8e9d7e6f`'s battery.)*
- [[concepts/label-era]] — the "derived purely from the barrier string" premise
  **corrected**; persisted-era-wins is now the rule.
- **NEW** [[concepts/migration-idempotence]] — the class this incident mints.

## Related

[[concepts/label-era]] · [[concepts/migration-idempotence]] ·
[[concepts/two-paths-one-quantity]] · [[entities/historystore]] ·
[[concepts/era-exclusion]] · [[concepts/evidence-floors]] · [[concepts/ghost-badge]] ·
[[concepts/deploy-deadlock]] · [[concepts/conscious-re-baseline]] ·
[[concepts/simplicity-ladder]] · [[entities/ml-governor]] · [[entities/overfit-check]] ·
[[concepts/overfit-battery]] · [[concepts/dof-budget]] · [[concepts/false-green]] ·
[[concepts/never-widen-a-gate]] · [[concepts/adoption-is-not-enforcement]] ·
[[concepts/tautological-instrument]] · [[entities/pretrade-gate]] ·
[[entities/config-guard]] · [[entities/auto-update]] ·
[[sources/session-20260808-night-staleness-overfit]] ·
[[sources/session-20260808-evening-availability-persistence]] ·
[[sources/session-20260808-battery-split-freeze-gate]] ·
[[synthesis/owed-measurements]] · [[synthesis/documentation-drift-register]] ·
[[synthesis/open-contradictions-register]] · [[concepts/paper-real-boundary]]
