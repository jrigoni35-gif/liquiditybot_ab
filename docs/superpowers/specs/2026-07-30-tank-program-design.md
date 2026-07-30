# TANK Program — 10-Checkpoint Reliability + Quant Revamp

**Date:** 2026-07-30 · **Mandate:** operator free-range ("build a tank of a
bot ... refine it so i can stop contending with the small bugs like the data
being dirty, slow learning, constant quirks ... make 10 checkpoints where all
changes are argued then debated then voted on").

**Goal:** one canonical, self-consistent bot installation; labeling/learning
pipeline benchmarked against peer-reviewed practice and revamped only where
the evidence wins a debate; the standing quirk classes (dirty data, slow
learning, wedges) enumerated and killed.

**Decisions already taken (operator-delegated "whatever makes the bot most
successful"):**
- Canonical home stays `C:\Users\haird\Documents\liquiditybot\liquiditybot_ab`
  (live process tree, data, and all 3 scheduled tasks already point there).
  The Desktop copy / zip backups are stale July-20 ancestors with zero
  learning data (verified against the uploaded zip: tip `395ab95`, ancestor
  of main, `outputs/` = one stray stop command from the 2026-07-30 recovery).
- Deletions on the PC are recycle-bin, report-first, and data-checked: any
  candidate folder/zip is scanned for learning artifacts
  (signal_history.csv, audit/events jsonl, snapshots) before removal; a hit
  aborts that removal and reports instead. Never delete learning data.

## Checkpoint protocol (applies to every checkpoint)

1. Proposal drafted (change map + rationale).
2. Debate panel: independent advocate + skeptic + quant judge agents argue
   the proposal against the codebase and the evidence; majority vote decides
   ship / amend / reject. Vote record goes in the checkpoint report.
3. Shipped changes run the full CLAUDE.md battery before commit; every
   commit pushes branch `claude/remote-control-e3h815` then fast-forwards
   main (PC updater deploys, battery-gated).
4. Hard invariants are out of vote scope: dry-run default, Kraken-only,
   deny-listed withdrawals, limit-only entries, exits-always, audit chain,
   config-lifted tunables, overfit battery green.

## The 10 checkpoints

- **C1 — Environment consolidation.** `scripts/pc_tidy.ps1`: scan Desktop /
  Downloads / Documents / user root for bot artifacts outside the canonical
  checkout (folders, zips, .lnk shortcuts), verify data-free, recycle on
  `-Apply`; verify scheduled tasks + live process tree afterwards. Operator
  runs it; paste-back verifies.
- **C2 — SPB-R Stage 0 integration.** Land the scarcity-priced probe budget
  dark (implementer in flight); the single biggest slow-learning lever
  (~3 → ~11-12 labels/day when flipped).
- **C3 — Data-hygiene tank.** Audit the dirty-data classes end-to-end: feed
  validation/quarantine coverage, signal_history schema drift, corpus
  dedup/import seams, restart continuity. Fix + regression-test each class.
- **C4 — Labeling vs literature (verdict).** Benchmark candidate/live/
  conviction + tb_* labeling against peer-reviewed practice (triple-barrier,
  meta-labeling, sample-uniqueness weighting, purged CV, label concurrency —
  López de Prado line + 2023-2026 crypto-microstructure work). Output:
  keep-or-revamp verdict per component, debated and voted.
- **C5 — Labeling revamp implementation.** Implement exactly what C4's vote
  approved (champion-style components are kept as-is by design).
- **C6 — Learning-speed program.** Retrain cadence, era exclusion, deploy
  gate friction, cold-start path, SPB-R flip readiness — remove structural
  friction the C4/C2 evidence exposes.
- **C7 — Strategy adoption scan.** Peer-reviewed, currently-successful
  strategies applicable to Kraken spot with our infra (order-flow imbalance,
  inventory-aware market making, vol-managed sizing, lead-lag). Adopt-list
  debated; anything adopted enters through the existing sizer/protocol
  stack.
- **C8 — Quirk kill list.** Enumerate recurring quirks from events/audit
  (wedge classes, seam warnings, restart losses, PT/OM edge cases); fix the
  voted top set.
- **C9 — Data/framework corrections.** Trading-database corrections
  (exchange outages, bad prints, survivorship) + framework integrations
  worth adopting into the battery; verify our overfit suite against current
  best practice.
- **C10 — Final synthesis.** Whole-branch review, full battery, deploy,
  and the "precise bot" report: everything shipped, every vote, every
  deferred item.

## Sequencing

C1 starts immediately (script + operator run). Research agents for C4/C7/C9
launch in parallel at program start. C2 lands when the implementer reports.
C3/C8 proceed between debates. C5 strictly after C4's vote. C10 closes.

## Out of scope

Live-mode arming, venue changes, withdrawal capability, UI processes —
all barred by CLAUDE.md invariants regardless of any vote.
