---
title: The Ghost Badge
category: concept
summary: "A champion watermark computed on a base rate that no longer exists, which a like-for-like gate must refuse to compare against — SECOND INSTANCE 2026-08-09, and the worse kind: the champion's 0.1537 was measured on a CORRUPTED pooled corpus, wedging a bug-promoted gbt in place. RESOLVED the same night WITHOUT intervention: ML-083's era-orphan branch fired on the repaired corpus (watermark 9,708 > matrix 701), set the unfalsifiable badge aside, and deployed logistic at 0.24728 against the cold-start bar — a doctrine stated STRUCTURALLY generalized to a polarity its author never considered"
tags: [ml, calibration, governance, incident, self-heal]
sources: 3
updated: 2026-08-09
---

# The Ghost Badge

## Definition
A champion's stored quality score (an out-of-fold Brier) computed on a **population whose base rate no
longer exists**. Comparing a new challenger's score against it is comparing across base rates — which a
like-for-like gate exists specifically to refuse.

## The instance
The orphaned champion's badge was **0.1237**, measured on a **0.169**-base-rate population. The
post-exclusion corpus has a **0.30** base rate, where a naive base-rate-only predictor scores ~0.21.
Every challenger therefore "lost to a ghost" — a model that could not be re-run and whose number
described a vanished world.

## Why a Brier comparison is the wrong instrument here
Brier score is base-rate sensitive: a lower Brier on a rarer-event population is not evidence of a
better model. **"A cross-base-rate Brier is exactly what a like-for-like gate refuses to compare."**

## The doctrine
When the champion's badge is unfalsifiable, **set it aside entirely** and apply the absolute cold-start
standard rather than trying to adjust or discount it. Pinned by test.

## Where it was caught
Not by the original fix, but by the [[concepts/adversarial-verification]] pass that was instructed to
refute it — a fix that was correct in shape (fail-closed) but **inert in effect**.

## Second instance, 2026-08-09 — the badge from a population that never legitimately existed

The corpus-corruption incident produced a badge worse than a stale one
([[sources/session-20260809-corpus-corruption]] §10).

| | Corpus it was measured on | OOF Brier |
|---|---|---|
| **Champion** `gbt` | the **CORRUPTED pooled** 9,708-row corpus (three label definitions merged) | **0.1537** |
| **Challenger** `logistic` | the **repaired clean** 692-row corpus | **0.2714** |

`train_meta` on the repaired corpus **correctly** re-gated selection to `['logistic']`
(live=6, total=692 — [[concepts/evidence-floors]] and the
[[concepts/simplicity-ladder]] working exactly as designed). Then the champion gate
**REJECTED the swap**, because 0.1537 reads as better than 0.2714.

**The two numbers are incommensurable.** The champion's was computed on a corpus that
pooled three incompatible label definitions — so it is not a harder-or-easier population,
it is a population that **should never have been scored at all**. Result: **the bug-promoted
`gbt` is WEDGED in place, and no clean-corpus challenger can dislodge it.**

### Why this instance is a category worse than the first

| | Instance 1 (2026-08-01) | Instance 2 (2026-08-09) |
|---|---|---|
| Badge measured on | a real, historical population (0.169 base rate) | a **corrupted** population that never legitimately existed |
| Failure direction | challengers **locked out** of a deadlocked deploy | a **bug-promoted champion locked IN** |
| What is deployed | the old champion, honestly earned | a champion **selected by the data bug itself** |
| Detectability | base rates differ — visible in the numbers | **both numbers look plausible**; only the provenance distinguishes them |

Instance 1's deadlock cost the project *nothing running*. Instance 2 leaves a model
**running and un-challengeable**. The doctrine below (set the badge aside and apply the
cold-start standard) is the right shape for both — but here it must be invoked as a
**conscious re-baseline** ([[concepts/conscious-re-baseline]]), not as an automatic
disjunct, because the trigger is *provenance*, not arithmetic.

~~**The gate was deliberately NOT overridden** — CLAUDE.md forbids bypassing gates, and the
gate is behaving correctly given its inputs. **The owed decision is to retire the champion
baseline as BUG-ATTRIBUTABLE** and re-baseline on the clean corpus — the same verb the
weekly-budget lockout earned when bug-attributable consumption needed its own mechanism
([[sources/session-20260808-budget-reanchor]]). Registered as
[[synthesis/owed-measurements]] **item 47**.~~

### RESOLVED 2026-08-09 02:56:04 — WITHOUT the re-baseline, and the restraint is why

**The recommended conscious re-baseline was never needed, and never happened.** The gate
was left alone, and **the codebase's own already-adjudicated ML-083 doctrine unwedged the
champion by itself** ([[sources/session-20260809-gate-policy-and-self-heal]] §1).

Three audit records, **4 milliseconds apart**:

| Time | Code | Payload |
|---|---|---|
| 02:56:04.391 | **ML-016** | `admitted ["logistic"]`, live **6**, total **701** |
| 02:56:04.480 | **ML-083** | `trained_rows 9708 > corpus_rows 701`, `challenger_brier 0.24728`, `n_oof 464` |
| 02:56:04.483 | **ML-040** | `decision DEPLOY`, **`ignore_champion: true`** |

The era-orphan branch (`main.py:6330`) fired because the champion's watermark — **9,708,
the corrupted pooled population** — **exceeded** the repaired training matrix of **701**
rows. The like-for-like fresh-row set is **empty by construction**, so the badge is
**unfalsifiable**, so **ML-076/ML-083 doctrine sets it aside entirely** and the challenger
faces the true cold-start bar. `logistic` scored **0.24728 < 0.25** and **deployed**.

**The arithmetic that proves the mechanism** (`ml/monitor.py:667-668`, evaluated on the
recorded inputs — not inferred from the outcome): under the **normal** branch
`0.24728 < 0.1537 − 0.005` is **FALSE** and `champion_brier >= 0.25` is **FALSE**, so the
normal branch would have **REJECTED**. **Only the ML-083 path deploys.**

Verified live: `meta_model.json` `kind=logistic rows=701 oof_brier=0.24728`;
`status.json` `model_kind=logistic`, era `armed=True`/`active=True`, load **701**,
`live_clean` **6**. **The bug-promoted `gbt` is no longer trading.**

> **What this instance teaches that instance 1 did not.** Instance 1's doctrine —
> *"when the badge is unfalsifiable, set it aside and apply the cold-start standard"* —
> was written for a champion that **locked challengers out**. It fired **unmodified** on
> the opposite polarity (a champion **locked in**) because it keys on the **structural**
> condition `trained_rows > len(X)`, not on the narrative. **A doctrine stated
> structurally generalizes to polarities its author never considered.**

**But note precisely what caught it.** ML-083 detects orphaning by a **row-count proxy**.
It fired here only because the corrupted corpus was **larger** than the clean one. Had the
corruption gone the other way — a badge measured on a corrupt population that happened to
be **smaller** — the badge would have compared "successfully" against incommensurable rows
and nothing would have flagged it. **The structural residue below is therefore still
owed**, and this resolution should not be read as closing it.

> **The generalization this instance forces:** a like-for-like gate compares *scores*, and a
> score carries no record of the corpus that produced it. **Every stored watermark needs a
> provenance stamp — which corpus revision, which era set, which row count — or a gate
> cannot tell a hard population from a corrupt one.** Both instances of this class are the
> same missing field.

**Safety net meanwhile:** the [[entities/ml-governor]] grades the live model on **realized
outcomes**, so a wedged champion that is genuinely bad gets attenuated by measurement even
while the selection gate cannot move.

## Related
[[sources/session-20260809-gate-policy-and-self-heal]] ·
[[concepts/deploy-deadlock]] · [[concepts/conscious-re-baseline]] ·
[[concepts/evidence-floors]] · [[concepts/simplicity-ladder]] · [[concepts/gort-rule]] ·
[[entities/ml-governor]] · [[concepts/adversarial-verification]] ·
[[sources/session-20260809-corpus-corruption]] · [[synthesis/owed-measurements]]
