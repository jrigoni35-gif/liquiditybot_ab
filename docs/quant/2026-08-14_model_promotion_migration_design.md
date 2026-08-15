# Model promotion as a migration problem — design, not implementation

**Status:** DESIGN ONLY. Nothing here is implemented. Every item is
classified against the era-4 accrual moratorium below; the SHIP-BLOCKED ones
require operator adjudication before any code moves.

**Date:** 2026-08-14 · **Author:** session `4b5e9197` · **Trigger:** the
2026-08-14T15:14:13Z champion swap (10,217-row `adaptive_gbt` → 211-row
`logistic`) reached production through a documented unlock with no floor on
it. That is not a model bug. It is a **migration** bug: a cutover executed
without a compatibility gate or a rollback plan.

---

## 1. Why the migration frame is the right one

The bot already treats models as a *neural network of specialists*: five
families (`logistic`, `gbt`, `blend`, `mlp`, `adaptive_gbt` —
`ml/retrain_log._FAMILIES`) learn from one shared corpus, are scored
separately by `ml/walkforward.evaluate_and_select`, and are arbitrated by a
board of governors before any of their output reaches an order.

What it does **not** treat as a system is the *transition between champions*.
Each promotion is a production cutover: a new artifact takes over a live
decision path, on a corpus that may have changed shape underneath it, with no
staged rollout and no defined way back. Framed that way, the standard
migration toolkit applies directly — and names the missing parts.

## 2. Inventory — what already exists (prior art, do not rebuild)

| Migration pattern | Already implemented as | Where |
|---|---|---|
| Versioned artifact registry | `ModelRegistry`, hash-chained, `model_id` = artifact sha256[:12], model cards, `verify_chain()` | `ml/registry.py` |
| Integrity check before cutover | `verify()` fails closed on a broken chain (ML-011) | `ml/registry.py:240` |
| Shadow / parallel run | ML-075 `shadow_p` — the champion is scored even while the governor has KILLED it, telemetry-only, so a killed model can re-arm on evidence | `main.py:6637-6646` |
| Circuit breaker + legacy fallback | `ModelMonitor` governor levels; cold-start prior when no champion loads | `ml/monitor.py` |
| Validation checkpoint | `should_deploy()` + the like-for-like shared-row comparison, **fail-closed** | `main.py:6428-6456` |
| Continuous rollout telemetry | `retrain_history.jsonl`, one row per retrain, deployed or rejected | `ml/retrain_log.py` |

This is a strong base. Three of the six are better than most production ML
systems have. The gaps below are narrow and specific — not a rewrite.

## 3. The three gaps

### GAP-1 — No compatibility gate. The unlock has no floor.

`main.py:6387` — when the champion's `trained_rows` watermark exceeds the
current matrix, ML-083 sets the champion badge aside entirely and applies the
cold-start bar (`Brier < 0.25`):

```python
elif int(self.meta.trained_rows) > len(X):      # 10,217 > 211  -> TRUE
    _deploy_ok = self.monitor.should_deploy(
        challenger_brier, n_oof=len(oof_cal), ignore_champion=True)
```

The unlock is *correct in intent*. Its own comment records the case it was
built for on 2026-07-29: **4,823 vs 1,516, a 3.2× orphan ratio** — where an
unfalsifiable badge would otherwise deadlock retraining forever, and "an
unfalsifiable badge may not gate forever" is sound doctrine.

It fired on 2026-08-14 at **10,217 vs 211 — a 48× ratio**, and handed the
cold-start bar to a model trained on 2.0% of the data the incumbent saw. The
only floor upstream is `len(X) < 60` (`main.py:6237`), which 211 clears
comfortably. The deployed model's own `family_brier` was **0.33105** — worse
than the 0.25 a constant p=0.5 predictor scores.

In migration terms: **the compatibility checker was skipped because the
schemas were too different to compare, and "cannot compare" was read as
"proceed" instead of "escalate."** That inversion is the whole defect.

*Shape of a fix (NOT a proposal to implement):* the unlock keeps its
deadlock-breaking purpose but gains a floor — an orphan ratio ceiling, or an
absolute minimum matrix size, or a required shadow period before the cold-start
bar may be applied. Which of those is right is an empirical question the
current data cannot answer.

### GAP-2 — No rollback. Promotion is one-way by construction.

`ModelRegistry.note()` supports `retired`, and nothing calls it. Before this
session nothing called `deployed` either — 134 `registered` events and 2
`integrity_fail`, and no record of any artifact ever becoming champion. (The
`deployed` half is now wired at both cutover sites, commit `61c3b5c1`.)

There is still no defined way back. Worse, the fail-closed gate makes
regression *sticky*: once the 211-row logistic deployed, `trained_rows`
dropped to 211, ML-083 stopped firing, and the very next retrain — with a
**better** OOF Brier of 0.17959 — was rejected by the like-for-like branch
because no shared row set could be built. A worse model installed itself and
then the correct fail-closed logic protected it.

That is the migration anti-pattern exactly: **no rollback path, and the
validation gate defends the incumbent regardless of merit.**

### GAP-3 — Base-rate mixture across label eras is unmanaged

`label_era` spans a **40× base-rate range** in the live corpus (measured
2026-08-14T23:38Z):

| `label_era` | n | base rate |
|---|---:|---:|
| `triple_barrier_h432` | 259 | 0.2239 |
| `triple_barrier` | 5,328 | 0.2508 |
| `exit_sim` | 2,732 | 0.1398 |
| `legacy` | 1,781 | 0.2611 |
| `exit_sim_time_stop` | 459 | **0.0065** |

The deploy gate's own comment (`main.py:6371-6376`) already establishes the
principle — "Brier is not comparable across differing base rates" — and
enforces it *between champion and challenger*. It is not enforced *within the
training matrix*. Era exclusion is the current mitigation and it works, but
its cost is the corpus collapse that triggered GAP-1. Expand-contract on label
eras (dual-label through a transition, contract the retired geometry only once
the new one has n) is the migration pattern that would decouple these.

## 4. Moratorium classification

| Item | Class | Rationale |
|---|---|---|
| GAP-1 floor on ML-083 | **SHIP-BLOCKED** | Changes which model deploys → entry decisioning → cohort-resetting |
| GAP-2 rollback path | **SHIP-BLOCKED** | Same |
| GAP-2 `retired`/`deployed` lineage events | **SAFE** (`deployed` shipped `61c3b5c1`) | Ledger rows only; no decision path reads them |
| GAP-3 expand-contract on label eras | **SHIP-BLOCKED** | Alters the training matrix → model behavior |
| GAP-3 era-mix + base-rate telemetry | **SAFE** (shipped `61c3b5c1`) | Report-only |
| Compatibility report (no gate) | **SAFE** | A report that *names* an incompatible promotion without blocking it is measurement |

The honest summary: **the valuable half is ship-blocked and should stay that
way.** All three gaps live in the promotion decision path, which is precisely
what the moratorium fences. What was shippable — lineage and telemetry — is
shipped. The rest is evidence for the ~08-16 table, not work to start.

## 5. What this changes about the ~08-16 decision

GAP-1 and the ALGO-5 trigger are **not independent**, and the docket should
not treat them as separate line items:

1. The h432 geometry change shrank the honest corpus to 259 rows.
2. Era exclusion correctly refused to pool it with the retired geometries.
3. That made the orphan ratio 48×, which fired ML-083.
4. ML-083 promoted a negative-skill model into the accruing verdict window.
5. Six of thirteen accruing trips straddle a deploy; two distinct champions
   opened trips in the cohort.

One geometry decision propagated through four mechanisms into the verdict
population. Adjudicating ALGO-5 without also adjudicating the ML-083 floor
would re-run this chain the next time a geometry cut lands.

---

*Grounding note: every file:line, count, and rate above was read from the
working tree or `outputs/` on 2026-08-14, not recalled. Live-file values are
as-of their stated read time and will have drifted.*
