---
title: "Session 2026-09-30 — pipeline congruence: values exact, counting incomplete; losing runners wrote duplicate rows; drift share is an autocorrelation artifact"
category: source
status: SETTLED-AS-OF-RUN
summary: "scripts/pipeline_congruence_report.py re-derived the corpus four ways: labels vs the bot's own 5m bars 2,511/2,511 exact, live rows vs fills 94/94, engine vs independent training load 24,573 vs 24,588 (+15 since), clean live labels 108 = 108. Found: 12 exact duplicate rows (era-9's 8 each at a losing runner's RT-010 second), three uncounted exits (26 long-book, pool-cap eviction, entry-bar slide), funnel 7,725 = 7,278 written + 177 pending + 270 never written. Fixed (cohort fork 6709bb74df3e -> 6709bb58cd7c): one-writer hold/release/discard on a lost lock, exact-duplicate dedup, counters. Drift: in-sample consecutive-window null reads 18.4% (42% of measurable) with zero change - the 34.4% tile is not drift evidence."
tags: [pipeline, congruence, cs-1, corpus, duplicate-runner, rt-010, one-writer, dedup, uncounted-exclusion, drift-share, psi, autocorrelation, live-clean, lineage-agreement, cohort-fork]
sources: 2
updated: 2026-09-30
---

# Session 2026-09-30 — pipeline congruence

Repo: `docs/quant/2026-09-30_one_writer_corpus_decision_record.md`; code `scripts/pipeline_congruence_report.py`,
`ml/history.py` (hold/release/discard, dedup, counters), `runner.py` (lock-branch wiring).
Raw: `raw/2026-09-30_drift_share_in_sample_null.md` (script verbatim + output).
Related: [[concepts/uncounted-exclusion|Uncounted Exclusion]], [[sources/session-20260930-trip-explanations-te1|TE-1]],
[[concepts/the-method|THE METHOD]].

## Findings (2026-09-30; re-derive)

1. **Values congruent.** Labels re-derived from the bot's own 5m ring with each row's stamped fracs,
   stop-first, 432 bars: 2,511/2,511 exact (entry, barrier, exit). Live rows vs fills 94/94 (max $0.005).
2. **My own instrument erred first**: the bare `HistoryStore(path)` defaults max_bars 96 -> legacy era
   (5,287 rows vs the engine's 24,573). The dashboard was right. Sixth tool to hit this default; the report
   now uses `store_for_config` (AST-pinned).
3. **Duplicates**: 12 exact duplicate rows corpus-wide; era-9's 8 each at the same second as a losing runner's
   RT-010 (09-10 x3 losers, 09-18). Last RT-010 09-18; the 09-27 boot-ownership check closes the boot race,
   post-boot lock loss still cycled until forfeit. Fixed: HOLD on first lost heartbeat, RELEASE on regain,
   DISCARD on forfeit; loader dedup on (source, id, signal_ts, asset, side) — never id alone (07-14 reused ids).
4. **Uncounted exits** now counted: long_book_skipped (26), evicted_pool_cap, dropped_entry_slid. Training
   ledger closes exactly: 35,131 = 24,576 trained + 4 old eras + 276 clash + 12 duplicate + 26 long-book.
5. **Drift share is not drift evidence.** In-sample null, exact monitor rules: iid windows 1.4% (0/300 alarms);
   consecutive 300-row windows (~10.8 h) 18.4% mean, 25.1% p95, 42% of measurable — zero real change.
   Live 34.4% / 78.6% measurable; 36 of 64 voting features degenerate. OPERATOR: monitor change = its own fork.
6. Lineage twin agreement 83% [77%, 88%] (200 pairs) — candidate label vs realized live label, same signal.
