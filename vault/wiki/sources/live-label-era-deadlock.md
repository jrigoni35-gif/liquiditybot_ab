---
title: Live Label Era Deadlock (2026-07-31)
category: source
summary: The full arc of the slow-learning root cause: a six-link chain, a same-day retraction of its own central claim, a three-way adjudication, and the first live tb_* rows in the bot's history
tags: [era-exclusion, deadlock, horizon, adjudication, retraction]
sources: 1
updated: 2026-08-01
---

# Live Label Era Deadlock (2026-07-31)

**Raw source:** `raw/quant/2026-07-31_live_label_era_deadlock.md`

## The chain (all links verified on the live corpus)
1. `ml.label_mode = "triple_barrier"` since 07-26; PT floor 2.00%; `max_bars = 96` (8h).
2. `_finalize_position` stamps `barrier = close_reason if close_reason in (tb_pt, tb_sl, tb_time)
   else "realized"`, and overlays close positions long before the 96-bar vertical -> **every live
   close lands `realized`**. Corpus: 256 live rows, **`tb_*` = 0**.
3. Era census: `triple_barrier` 2,132 rows — **all candidate, zero live**.
4. Era exclusion armed and ACTIVE excludes 4,859 rows **including all 251 live labels** ->
   `rows 2132, live_clean 0`.
5. The evidence gate reads exactly that: `admissible_families(0, ...) -> ['logistic']`. gbt / blend /
   mlp / adaptive_gbt are unreachable **forever** on this path.

## The retraction
Step 2's original claim — "the barriers are unreachable by this strategy" (median MFE +0.156%, 0/60
reaching either leg) — was **retracted in-document** as apples-to-oranges: it measured excursions over
the ACTUAL short holding window against a barrier defined over a 96-bar horizon.

**C1 — barriers ARE reachable**: of 2,137 candidate rows, PT 17.9%, SL 34.5%, TIME 47.5%.

## The real mechanism
**C2 — a HORIZON mismatch**: median hold **live 13.6 bars vs candidate 43.2 bars**; share reaching
the vertical **live 9.3% vs candidate 33.8%**. Live positions close ~3x sooner than the label's
horizon. PT-060 fires at bar 36; the vertical is at bar 96 — [[concepts/clock-inversion]].

## The two findings that reframe everything
- **C3 — the simulated edge at this geometry is NEGATIVE**: SL 34.5% vs PT 17.9%, the stop hit
  **1.9x more often** than the target. "The most consequential number in the document and it is not a
  plumbing defect."
- **Convergent finding 2 — every model rung loses to a constant.** Deployed logistic Brier 0.2736 vs
  0.1936 base-rate; tb-model on live rows 0.2124 vs 0.1393; live-only OOS AUC **0.4375** (worse than
  random). **"Nothing in the battery currently reports this."** -> option G,
  [[concepts/null-model-floor]].
- **Convergent finding 1 — the mechanism closing probes is UNKNOWN**: 3 of 8 bracket probes died at
  19.8 / 24.8 / 35.8 minutes, too early for every known overlay. **No fix may be chosen until the
  mechanism is named** ([[concepts/iron-law-of-debugging]]).

## The ruling table
- **I0 PT-061 close-reason audit: SHIP FIRST** (both briefs' prerequisite; report-only).
- **G null-model floor: SHIP** — "the gate cannot keep hiding that every rung loses to a constant."
- **E horizon re-alignment (96 -> ~24 bars): ADOPT pending I0** — dominates option B, suppresses no
  protective exit, converts ~100% of probes to era-valid rows at 1/4 the capital-time.
- **D probe entry selectivity: ADOPT (profit item)**.
- **A live rows era-exempt: REJECT** — fails on measurement, not principle.
- **B probes ride to the vertical: REJECT** — as written it re-runs the 07-29 LINK wedge.
- **C re-align barriers: REJECT** — its defensible half IS E.

## Resolution, verified live
Live `tb_*` rows **0 -> 3**; `live_clean` **0 -> 3**; all three carrying
`barrier=tb_time, label_era=triple_barrier_h24`. **Accepted cost**: corpus drops ~2,141 -> 379 rows,
because "the 2,146 rows labelled at a 96-bar horizon answer a question the bot no longer asks."

## The fix that hid the fix
`_apply_era_exclusion` hardcoded the **un-qualified** `LABEL_ERA_TRIPLE_BARRIER` as the era to KEEP,
so the horizon qualifier introduced by this very fix made the new rows **invisible** — it kept the
stale 96-bar rows and excluded the 24-bar ones including the first three live labels. "Left alone,
`live_clean` would have stayed 0 forever and the horizon fix would have been wrongly written off as a
failure." **Found only because the operator verified rather than assumed.**

## Carried defects surfaced
- `last_load_stats` computes `ess_kish`/`mean_uniqueness` **PRE**-exclusion while `rows`/`live_clean`
  are **POST**-exclusion.
- Root `outputs/postmortem_summary.csv` is **stale (17 rows, ends 07-16)** while the live 216-row
  series lives elsewhere — two analyses in this debate initially disagreed because of it. This
  retroactively undermines the cost-truth n=16 measurement in
  [[sources/geometry-alignment-adjudication]].
- Corrects the record that commit `381e870` "unblocked the tb_* label stream" — **it did not**.

## Related
[[comparisons/horizon-96-vs-24-bars]] · [[entities/historystore]] · [[entities/ml-governor]]
