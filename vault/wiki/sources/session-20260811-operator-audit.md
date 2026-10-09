---
title: "The since-6am operator audit (wf_54d5cbd8-caf, 7 agents, 2026-08-11) — the backwards-derivative claim REFUTED, the anti-momentum surprise, and the MIXED asset-selection verdict"
category: source
summary: "Seven-agent audit of everything since 6am: (1) the operator's backwards-derivative claim VERIFIED FALSE — NO-INVERSION-FOUND at high confidence, 0/3 adversarial refuters succeeded (recompute / consumption / data lenses); what the operator saw is the SIDE-RELATIVE *_dir convention (ml/features.py:109-115, dir_sign :342 — short rows print sign-flipped derivatives), ±6 values that are vol-normalized returns not [-1,1] flags, and the absence of any candidate leaderboard to sort backwards (round-robin _entry_assets, main.py:3911-3921). (2) The failed data-lens refuter surfaced a NEW finding: a symmetric ANTI-momentum pattern at h432 — longs with ret_12_dir>0.5 win 21.8% (n=2620) vs 22.6% below −0.5; shorts 17.5% (n=1849) vs 21.4% — momentum-agreeing trades win LESS in BOTH direction cohorts (pre-cut-boundary pooled data; owed 69). (3) Asset-selection verdict MIXED: per-asset regimes/features/vol-scaled stops/breakers/caps under GLOBAL meta-model + gate thresholds; the bracket cost floor flattens majors to identical 1.50/2.00 sl/pt while FLOW/ARB/MINA differentiate; ETH/BTC fill concentration is gate-confirmation frequency, not preference (gate_confidence flat 0.81-0.90). (4) venue_disloc_dir is ANTI-oriented vs basis_dir — documented intended, model-input-only. (5) All 14 commits since 2026-08-10T11:00Z claim-vs-diff CLEAN. (6) Ledger COHERENT with the $800 stressor; anomalies adjudicated (138s equity lag benign, orphan-close postmortem undercount FIXED with degraded rows, PAXG tb_time/h432 BY DESIGN, long-book live-row schema gap OPEN = owed 68, and a fee note that inherits the STALE 16/26 schedule). Three doc-drift fixes and the stop_round config_guard checks shipped in response."
tags: [session, audit, adversarial-verification, features, asset-selection, ledger, postmortem, doc-drift, refutation]
sources: 1
source_path: "workflow wf_54d5cbd8-caf (7 agents, 2026-08-11), ml/features.py, main.py:3911-3921, ml/postmortem.py, core/config_guard.py, risk/stop_placement.py, outputs ledgers under the $800 stressor — verified on the box at filing"
source_date: 2026-08
authors: [operator, audit-agents]
ingested: 2026-08-10
updated: 2026-08-10
---

# The since-6am operator audit (wf_54d5cbd8-caf, 7 agents, 2026-08-11)

**What this is.** An operator-ordered audit of everything since 6am (workflow
`wf_54d5cbd8-caf`, 7 agents, 2026-08-11), centered on one adversarial question — *are the
derivatives backwards?* — plus a commit-by-commit claim check and a full ledger coherence audit
under the new $800 stressor regime.

**Boundary statement** ([[concepts/paper-real-boundary]]): the feature/selection findings are
**repo-side** (code semantics, verified at file:line); the win-rate and ledger numbers are
**sim-side** (label-space and paper fills — and all of them predate at least one comparability
cut, see [[synthesis/comparability-boundaries]]); no venue truth is claimed anywhere on this
page.

## §1 — The backwards-derivative claim: VERIFIED FALSE (NO-INVERSION-FOUND)

The operator's hypothesis — that the bot's derivative features are inverted, i.e. it is
systematically sorting its candidates backwards — was put to **three adversarial refuters
instructed to find the inversion** (a recompute lens, a consumption lens, and a data lens).
**0 of 3 succeeded.** Verdict: **NO-INVERSION-FOUND, high confidence** — the strongest form
this vault accepts for a negative ([[concepts/adversarial-verification]]: the refuters were
hunting FOR the inversion, and a refuter who fails after genuinely trying is the evidence).

What the operator actually saw decomposes into three non-bugs:

1. **The `*_dir` features are SIDE-RELATIVE** (`ml/features.py:109-115`, `dir_sign` applied at
   `:342`): a short row stores the **sign-flipped** derivative by construction, so raw corpus
   rows read without conditioning on side print "backwards" derivatives for every short. This
   is a reading hazard, not an inversion — filed as its own concept,
   [[concepts/side-relative-features]].
2. **Values like ±6 are vol-normalized returns, not [−1, 1] direction flags.** The `_dir`
   suffix suggests a bounded flag; the columns are unbounded normalized magnitudes.
3. **There is no candidate leaderboard to sort backwards.** Asset selection is a
   **round-robin** over `_entry_assets` (`main.py:3911-3921`) — no ranking exists whose order
   an inverted feature could reverse.

> **Binding for future sessions:** the backwards-derivative hypothesis is adjudicated and
> closed on this evidence. Do not re-litigate it from raw-row reads — any apparent inversion
> in pooled corpus rows must first be conditioned on `side` and checked against the
> side-relative convention before it is a finding.

## §2 — The refuter that failed and still paid: the symmetric ANTI-momentum pattern (h432)

The data-lens refuter, failing to find an inversion, found something real instead
([[concepts/adversarial-verification]] — a failed refutation that pays anyway):

| cohort | ret_12_dir > 0.5 (momentum agrees) | ret_12_dir < −0.5 (momentum opposes) |
|---|---|---|
| **longs** | wr **21.8%** (n=2620) | wr **22.6%** |
| **shorts** | wr **17.5%** (n=1849) | wr **21.4%** |

**Momentum-agreeing trades win LESS in BOTH direction cohorts.** The symmetry is the point:
a sign bug would help one side and hurt the other; this pattern is the same shape on both
sides, so it is a **genuine market pattern** (anti-momentum at the h432 horizon), not an
artifact of the side-relative convention it was found while checking.

*Caveats filed with it, both load-bearing:* the data is **pre-cut-boundary** (every row
predates at least execution-era boundary #4 and the capital epoch —
[[synthesis/comparability-boundaries]]) and **pooled** across regimes/assets
([[concepts/pooled-populations]] — a pooled split can manufacture or destroy a pattern).
Re-measurement on clean post-epoch cohorts is **owed 69**
([[synthesis/owed-measurements]]). Until then this is a lead, not a input candidate — and any
proposal to consume it must pass the moratorium and the evidence-closed register first.

*Follow-up (`66744ed1`, [[sources/session-20260811-apply-batch]] §2):* owed 69 is now
**INSTRUMENTED, still open** — `defensive_cadence_report.py` §2b prints the split with the
side-relative caveat on its face and lifetime-POOLED vs since-capital-epoch tables. Its
first h432-only pooled run shows a **steeper, monotone** anti-momentum gradient than this
audit's all-era numbers — while the **post-epoch clean cohort (n=36) currently leans
OPPOSITE** — so the LEAD status here is doing exactly its job.

## §3 — Asset-selection verdict: MIXED (per-asset plumbing, global brain)

The audit's architecture question — *does the bot actually treat assets differently?* — comes
back **MIXED**, and the split is precise:

- **Per-asset:** regimes, features, vol-scaled stops, breakers, caps.
- **Global:** the meta-model and the gate thresholds — one brain scores every asset.
- **The bracket cost floor flattens the majors:** BTC/ETH-class assets all land at the
  identical **1.50/2.00 sl/pt** geometry (the cost floor binds — same mechanism as
  [[concepts/cost-truth]]'s label-floor coupling), while **FLOW/ARB/MINA** actually
  differentiate.
- **ETH/BTC fill concentration is not preference:** it reflects **gate-confirmation
  frequency** (how often the gate confirms on those books), with `gate_confidence` **flat
  across assets (0.81–0.90)** — the round-robin entry loop (§1.3) plus differential gate
  pass-through produces the concentration without any ranking existing.

Filed to [[entities/liquiditybot]] as the standing description of the selection architecture.

## §4 — venue_disloc_dir is ANTI-oriented vs basis_dir — intended, and worth writing down

The **closest real thing to a backwards derivative** in the codebase:
`venue_disloc_dir` is oriented **kraken-rich positive** where `basis_dir` is
**kraken-cheap positive** — the two dislocation features point opposite ways by construction.
**Documented intended, model-input-only** (no decision path consumes the raw sign). Recorded
here so the next raw-row reader who notices the anti-orientation finds the adjudication
instead of re-opening §1 ([[concepts/side-relative-features]] carries the reading rule).

## §5 — Commit claim check: all 14 clean

All **14 commits since 2026-08-10T11:00Z** were verified **claim-vs-diff clean** — every
commit message's claims match its diff. (Context for why this check exists: circulated commit
records have been false on multiple verified counts before —
[[sources/session-20260807-hedge-churn-guards]] — and the register of stale shipped strings is
[[synthesis/documentation-drift-register]].)

## §6 — Ledger audit: COHERENT with the $800 stressor, five anomalies adjudicated

The money-state ledgers reconcile under the capital epoch
([[sources/session-20260810-stressor-epoch]]). Anomalies, each with a verdict:

1. **138s equity reset lag — BENIGN.** The equity series lags the epoch instant by 138s
   (write cadence, not a second reset).
2. **Postmortem undercount from orphan closes — FIXED.** The long-book flatten closes **ETH
   `d5513dd5`** and **BTC `e35c0a59`** had **no thesis at close**, so they produced no
   postmortem/path rows at all — an [[concepts/uncounted-exclusion]] on the trade-path ledger
   the Grand Synthesis parameterizes from. Fixed in `ml/postmortem.py`: **degraded
   `orphan_close` path rows** — the row exists, marked degraded; named, not omitted.
3. **PAXG live row carrying `tb_time`/h432 — BY DESIGN.** `label_era_of` is a **pure function
   of the barrier string** ([[sources/live-row-era-gap]], [[concepts/label-era]]); a PAXG row
   under the current barriers correctly stamps the current era.
4. **Long-book live rows missing post-migration schema columns — OPEN.** Registered as
   **owed 68** ([[synthesis/owed-measurements]]); see [[entities/long-book]].
   *Follow-up: CLOSED at the writer by `66744ed1`
   ([[sources/session-20260811-apply-batch]] §1) — the diagnosis sharpened to a discarded
   `_feature_extras` dict; `meta["avail"]` now threads from the same extras the features
   were built from, pinned in `tests/test_long_book_integration.py`. This audit's two blank
   ETH/BTC rows were ALSO legacy tuple-shape — both explanations true, the writer defect
   real and current.*
5. **The fee note — COHERENT AS CONFIG INTENT, but it inherits a falsified premise.** The
   audit described fees as *"padded 25/40 bps vs Kraken 16/26 (intentional stress)."*
   > ⚠️ **Contradiction with the standing panel finding** ([[concepts/cost-truth]],
   > triple-confirmed 2026-08-07): **16/26 is the STALE schedule — 25/40 matches NO row of
   > Kraken's current schedule, and Tier 1 is 40/80**, under which the constants
   > **understate** a fresh account's drag rather than pad it. What survives: the constants
   > are a deliberate, documented config choice and the ledger is internally coherent with
   > them; what must not be cited: "padded/conservative" as a statement about the venue. The
   > correction remains sequenced behind the h432 verdict (owed 37). In paper, every fee
   > "measurement" is the constant restated either way.

## §7 — Fixes shipped in response

- **`ml/postmortem.py`** — degraded `orphan_close` path rows (closes §6.2 at the writer;
  the two orphan closes stay undercounted in history — history is not rewritten).
- **`core/config_guard.py`** — **checks for the `stop_round` knobs**: the cut-#7 phantom-knob
  class ([[synthesis/documentation-drift-register]], [[entities/osler]]) now has a guard —
  the knobs must exist where the reader reads them (`config["risk"]`), so a re-divergence of
  declaration and consumer FATALs at boot instead of silently defaulting
  ([[entities/config-guard]]).
- **Three doc-drift fixes** ([[synthesis/documentation-drift-register]] 2026-08-11 rows):
  the `risk/stop_placement.py` docstring's phantom-block reference, the Osler test docstring,
  and the `_goals_doc` rewritten for the $800 regime.

## Related
[[concepts/side-relative-features]] · [[concepts/adversarial-verification]] ·
[[concepts/uncounted-exclusion]] · [[concepts/pooled-populations]] ·
[[synthesis/comparability-boundaries]] · [[synthesis/owed-measurements]] ·
[[synthesis/documentation-drift-register]] · [[entities/liquiditybot]] ·
[[entities/long-book]] · [[entities/config-guard]] · [[entities/osler]] ·
[[concepts/cost-truth]] · [[sources/session-20260811-cut7-geometry-epoch]] ·
[[sources/session-20260810-stressor-epoch]] · [[sources/session-20260811-apply-batch]]
