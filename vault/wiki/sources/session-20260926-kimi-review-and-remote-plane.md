---
title: "Session 2026-09-26 — the remote plane proven end-to-end, Kimi's ~50 commits reviewed three ways, and a model that saturates on its first live move"
category: source
status: PROVISIONAL
summary: "Remote-control git plane verified end-to-end (snapshot command, RC-010 forward -> runner ack) and its ack given the sender's id. Kimi Code authored ~50 commits since 09-17 (no Claude trailer); 8 touch engine code. Three parallel reviewers (darkpool / decisioning R1-R3 / main.py telemetry + interference) found: the darkpool block is a static date flag ranked #3 of 68 features; a training-constant column saturates the model on its first live move (_Standardizer sd=1e-9); R2 frozen tiers has four defects A-D; DE-010 claimed propensity 1.0 on randomized probes; one hourly regime-refresh raise starved retrain/drift/fee-recon. The 348 s max cycle was the 09-23 Windows-Update reboot's network settle. Era-9 n=50 lean reads ACT-negative (n=69, net -$0.42/trip)."
tags: [remote-control, kimi, multi-llm, darkpool, standardizer-saturation, de-010, propensity, interference, hourly-isolation, r2-frozen-tiers, era-9, lean-act-negative, cohort-redefinition, auto-mode-denial]
sources: 1
updated: 2026-09-26
---

# Session 2026-09-26 — remote plane, the Kimi review, and the saturating standardizer

Raw (verbatim reviewer artifacts: diffs, pin tests, probe scripts): `raw/audits/2026-09-26_kimi_review/`.
Repo commits: `6e73bf1b4` (ack names sender id, merged+pushed), `b7090af58` (overfit synthetic-prompt fix +
fill-hazard reports), plus this session's SAFE batch (see HANDOFF RECENTLY SETTLED).

## Remote-control plane [K]
Remote id `1790390354-6be212024f`: queued 21:39:18 local -> RC-010 21:39:55 -> runner ack `snapshot saved`
21:40:00. The ack carried no id (correlation by time only); now `[id=<local> origin=<remote>]`. Poller half
verified live (queue file caught carrying `origin_id`); runner half needs the next runner boot.

## Kimi's footprint [K]
~50 commits on main since 09-17 lack a Claude trailer; engine-touching: `12a164f06` (darkpool, 29 files),
`f3b5f9e1a` (R1+R3), `9b02b465f`/`5e83ebc37`/`e30f89b83` (DE-010), `2cbaabada` (book stamp), registry adds.
Unmerged: `fix/decisioning-coupling-r123` (R2). Kimi task dirs live OUTSIDE the repo
(`Documents\kimi\tasks\...`) and `config.json` darkpool.duckdb_path points into one — an unversioned file
another agent can write feeds the live scorer.

## Findings that shipped as SAFE fixes (each red-first, mutation-verified with control)
- **F2 standardizer saturation (P0 when triggered):** training-constant columns get sd = std+1e-9; the first live
  departure divides by ~1e-9. Injection `dp_vol_z=0.5` -> logistic 9.4e-14. Fix: constant columns read 0.
  Output-identical on all 33,480 corpus rows (max|d| = 0.0). Also covers `sent_fear`.
- **F3/F4/F8 darkpool lifecycle:** lifetime read-only handle blocked the mirror writer and never reconnected;
  data age never grew (stamped at ingest); degraded snapshot kept stale numerics.
- **F9:** `darkpool.enabled:false` latched DF-020 forever.
- **C1/C2 DE-010:** `propensity: 1.0` on epsilon-roll probes (reject-inference reads 1/p); failed writes
  were silently cleared (AuditTrail.log returns 0, never raises) — now counted.
- **C4:** one raise in the hourly regime refresh skipped fee-recon, model adopt, retrain, drift, health.
- **C6:** book-stamp pin counted a literal (a comment satisfied it) -> AST pin + vacuity guard.
- **C8:** quant_db external attach leaked raw duckdb exceptions past its refusal contract.
- R1 docstring over-claimed guard coverage (raw sigma reads remain; safe today, stated).
- overfit_check told users to add synthetic-only families to EXPECTED_ARMED (would brick live runs, exit 3).

## Held for operator (not applied)
- **F1** darkpool is a date flag (all v10 z = 0; `avail_dp` #3 of 68 importance; neutralising moves served
  p_win +2.2pp mean, 0 threshold crossings). Gate `max_data_age_days` drafted, default off.
- **R3 fee-proposal completeness** (4 of 6 keys -> applying it FATALs boot): fix drafted; auto-mode denied applying.
- **R2 redesign** (freeze sigma not trigger; keep-first snapshot; tolerant restore): drafted on scratch worktree.
- **C3** slow-head fault skips the entry sweep — LEFT AS-IS deliberately: fail-safe direction (invariant 5).
- **C5** in-process auto-retrain blocks the stop loop 21-28 s/hour (n=20) — needs threading design.
- **Cohort redefinition** (decision-fingerprint cohorts replacing hand-minted EXEC_ERA): operator ruled to lift the
  moratorium and redefine; writing `core/cohort.py` was DENIED by the auto-mode classifier ("Security Weaken").

## Cut #13 — SHIPPED and LIVE 2026-09-28T03:33:40Z [K]
Operator ruling lifted the moratorium and redefined cohorts: COHORT-FORKING via
decision fingerprints (`core/cohort.py`). Shipped with F1 (stale-darkpool gate 35 d),
R3 (fee proposal complete), R2 (Kimi's frozen tiers, redesigned A–D). main =
`8535c1189` (includes cloud session PR #6). Controlled restart: stop acked
03:31:05Z → STOPPED 03:31:13Z → `migrate_fills_schema` (1,458 rows → 19 cols,
backup `fills.csv.preschema_1790566274`) → supervisor relaunch 03:33:40Z. Boot
`CG-000` decision_fp **`0f773bf5fc67`** (cfg `0f773b4d84b0`, code `f5fc67e71017`),
dry_run true; first 5 post-boot fills all stamped. Record:
`docs/quant/2026-09-26_cut13_fingerprint_cohorts_decision_record.md`.
- **Exit replay (item 6):** live rule reproduced 74/74; no exit variant clears p*;
  the only significant paired diff (later trail arm) is WORSE. Lever = entry edge.
  Evidence `raw/audits/2026-09-26_kimi_review/exit_replay/`.
- Found in passing: the pusher-bounce test killed LIVE Grafana pushers on every
  full-suite run (stubbed); handoff_packet law excerpts were first-N not best-N.

## Other measured facts
- 348 s cycle max = 09-23 Windows-Update reboot: OS network settling (DNS event 1023 18:06, WSL vSwitch
  18:10-18:12); stall ~18:08 -> 18:13:52 local. Not DE-010 (7.5 ms/write), not retrain.
- Era-9 readout (`scripts/era_readout.py`, 18:55Z): selected 5m row n=69, net -$0.4177/trip, CI [-0.60, -0.25],
  LOO robust, n=50 LEAN: ACT (negative). v9-only cohort also ACT-negative at n=51 (09-23 record).
- Tier fills in era-9: 0 of 84 exits (tier 1 never fires on bracket positions) — R2 exposure currently ~nil.
- npx `ECOMPROMISED` = one half-installed `_npx/110e52990071af13` pyright dir; moved aside to %TEMP%.
