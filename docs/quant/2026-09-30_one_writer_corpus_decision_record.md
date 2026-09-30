# 2026-09-30 — One-writer training corpus + CS-1 counters (COHORT FORK)

Operator, verbatim: "Look at our pipeline in general and if the corpus is
congruent with the rows it's attained." then "Even though you are on auto
mode configure it to run smoothly and not duplicate".

**Fork:** `ml/history.py` and `runner.py` are decision modules
(`core/cohort.DECISION_MODULES`). Running fingerprint `6709bb74df3e` ->
this tree `6709bb58cd7c` (code half only; config unchanged). Banked trips keep
their own read. Hard invariants 1–7 untouched: nothing here places, sizes or
exits an order; exits keep running on a lost lock exactly as before (#5).

## What was measured (scripts/pipeline_congruence_report.py, 2026-09-30)

- Labels vs the bot's own 5m bars (bot_cache lane): **2,511/2,511 exact**
  (entry price, barrier, exit price). Live rows vs fills.csv: **94/94**.
  Engine vs independent re-derivation: trained 24,573 vs 24,588 (+15 labeled
  since), clean live labels 108 = 108.
- **Duplicates**: era-9 holds 8 duplicate rows from 6 candidate ids (one ETH
  id 4x on 09-10, five PAXG ids 2x on 09-18); the whole corpus holds 12
  exact duplicates. Every era-9 episode lines up to the second
  with a losing runner's RT-010 self-termination. The 2026-09-27 boot
  ownership check closes the boot race; a runner that loses its lock AFTER
  boot still cycled - and wrote labels - until forfeit (09-10: losers ran 60
  and 40 lost heartbeats). The loader had no exact-duplicate dedup, so the
  copies trained.
- **Uncounted exits (CS-1)**: 26 long-book rows skipped by the loader with no
  counter; two candidate exits (pool-cap eviction, entry-bar slide) with no
  row, log or code. Era-9 funnel: 7,725 ids minted = 7,278 written + 177
  pending + 270 never written.

## What changed (the lever: corpus integrity, not the model)

1. `HistoryStore` HOLD / RELEASE / DISCARD. From the first lost heartbeat the
   runner holds rendered corpus rows in memory; a regained lock flushes them in
   order (nothing lost); a forfeit drops them (the live peer writes its own).
   `_commit_row` is the one place a row reaches disk.
2. Loader drops an EXACT duplicate (source, id, signal_ts, asset, side),
   counted `dropped_duplicate`. Never on id alone: bare ids were reused for
   distinct signals after the 2026-07-14 rollback, and both must survive.
   Effect on this corpus: 12 rows (0.05% of 24,588).
3. Counters: `long_book_skipped` (loader stats), `evicted_pool_cap` and
   `dropped_entry_slid` (labeler), published in status.json
   `ml.candidate_drops` / `ml.held_writes`.

Pins: tests/test_one_writer_corpus.py (11, mutation 11/11 vs green control);
tests/test_pipeline_congruence_report.py (47, mutation 5/5).

## Found, NOT changed (operator decisions)

- **Drift share cannot be read as drift.** In-sample null on the training
  corpus: 300 random rows read 1.4% (0/300 alarms); 300 CONSECUTIVE rows
  (~10.8 h, how the live buffer fills) read 18.4% mean / 25.1% p95, 42% of
  measurable features - with zero real change. The live buffer is denser than
  10.8 h, so its artifact is likely larger. Live reads 34.4% (78.6% of the 28
  measurable features); ML-031's 30% retrain vote sits inside the artifact.
  Changing the monitor changes when retrains run - a fork of its own.
- Lineage twin agreement 83% [77%, 88%] over 200 pairs (candidate label vs
  realized live label, same signal) - disclosed by the bot, not on a board.
- Candle collector never scheduled; 09-07..09-23 5m hole (TE-1 record).
