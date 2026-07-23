# Post-Program Queue (#103) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the profitability program's consciously deferred items: (1) the label sim must apply the SAME cost-floored tier-1 geometry the live book trades (final-review Important #2 — "must not slip"); (2) the fee-tier reconciliation remainder of W2-9; (3) a regime-stratified OOF diagnostic (report-only); (4) a regime-coverage term in the probe-throttle corpus decay; (5) the four riding minors from the whole-program review + W2-28; (6) conscious adjudication of quant-trials harness enablement of the floor + time-stop.

**Architecture:** No new engines. Everything extends the shipped machinery: label-sim parity via the labeler's OWN cost stack (already computed per candidate), fee reconciliation as a read-only hourly check, the OOF diagnostic appended to `scripts/overfit_check.py` with NO gate change, the coverage term as a guard-checked extension of P3's decay formula.

**Tech Stack:** Python 3.11, existing labeler/pretrade/exploration/overfit machinery, pytest, quant_trials G1–G5.

## Global Constraints

- CLAUDE.md binds in full: thresholds live in config.json with guards (FATAL for incoherent combinations); no fitted-looking literals in decision paths; registered reason codes only (`core/codes.py`); public interfaces extended with defaults, never broken; exits always allowed.
- OVERFIT DISCIPLINE IS THE LAW OF THIS PLAN: every new value must be DERIVED from a measured/structural quantity with the derivation written into the config guard's comment. NEVER tune a value to make a battery prettier. `scripts/quant_trials.py` gates G1–G5 must stay green UNCHANGED through Tasks 1–5 — if a gate moves, STOP and report (the coordinator adjudicates; re-baseline is never the implementer's call). Task 6 is the ONLY place gate numbers may legitimately move, and only under the coordinator's explicit adjudication — never widen a gate to silence CI.
- The overfit battery baseline is 3-passed/5-failed (known data-thinness state, consciously re-baselined 2026-07-23). Tasks 1–5 must leave `scripts/overfit_check.py` verdicts byte-identical except where Task 3 APPENDS report-only lines (exit code and existing check verdicts unchanged).
- `outputs/signal_history.csv` existing rows are never rewritten. Task 1 changes how FUTURE labels are computed (intended); it must not touch historical rows.
- Every task: failing test first (TDD), full `pytest tests/` green, ruff + pyright (0 errors, shipped scope), and `.venv/bin/python scripts/quant_trials.py` outcome reported verbatim in the task report.
- Commit trailer (exact): Co-Authored-By: Claude Fable 5 <noreply@anthropic.com> + Claude-Session: https://claude.ai/code/session_01TgfcWLtZtVMQhbiPZCCV8h — with `git config user.email noreply@anthropic.com && git config user.name Claude` before committing.

---

### Task 1: Register-time cost estimate — label sim gets the live floor geometry

**Files:** ml/history.py (`_label` dispatch ~:776 and the bootstrap `simulate_exit_policy` call ~:939), ml/labeling.py (docstrings only — the mechanism already exists), tests (extend tests/test_p35_label_sim_parity.py or a new file).

**Requirement:** The P3.5 mirror wired the tier-1 cost floor into `ExitPolicy._tier_trigger` but every caller passes `est_cost_bps=0.0` (documented residual), so production labels scratch/trigger on UNFLOORED geometry while the live book trades floored geometry (whole-program review, Important #2). The register-time estimate ALREADY EXISTS: `CandidateLabeler._cost_pct(cand)` computes the candidate's round-trip cost (fee floor `rt_cost_pct` + the candidate's own capped `spread_bps` captured at register time) and is ALREADY passed to `simulate_exit_policy` as `cost_pct` for the net-of-cost label. Thread that SAME quantity into the floor: at the `_label` exit-policy dispatch, pass `est_cost_bps = cost * 100.0` (pct → bps, the exact inverse of the conversion `tier1_cost_floor_pct` applies). At the bootstrap call site, pass `est_cost_bps = cost_pct * 100.0` likewise. One cost basis now drives BOTH the net-P&L subtraction and the trigger floor — no new config, no new literal, no new data captured.

Documentation duty: ml/labeling.py's two "DOCUMENTED RESIDUAL" blocks (in `_tier_trigger` and `simulate_exit_policy`) must be rewritten — the residual is closed; what remains is a documented APPROXIMATION (the label-side cost stack is fees + capped spread; the live `PreTradeDecision.est_cost_bps` additionally carries impact/queue terms computed post-sizing, structurally unavailable at register time — the label estimate is therefore a conservative lower bound and the same basis the label's own net already uses).

Tests: (a) with a candidate whose spread+fees put the floor above the vol-scaled trigger, the simulated tier-1 trigger equals the floored value (assert via geometry: a favorable path that clears the unfloored trigger but not the floor must NOT fire tier 1 / must time-stop at the floored half-trigger); (b) the est_cost_bps handed to the sim equals `_cost_pct(cand) * 100.0` exactly; (c) bootstrap path passes its cost the same way; (d) `label_include_spread=False` still floors on the fee-only stack; (e) triple_barrier mode unaffected. Battery note for the report: overfit_check reads pre-labeled rows — verdicts must be byte-identical.

- [ ] Failing tests first; implement; full suite + quant_trials verbatim; commit `feat(ml): label sim floors tier-1 on the candidate's own cost stack (#103 T1)`.

### Task 2: Fee-tier reconciliation (W2-9 remainder)

**Files:** data/kraken_feed.py (read-only private `TradeVolume` accessor — the deny-list at :65 stays untouched; TradeVolume is not on it and must not be), main.py `hourly_cycle` (~:3117, isolated like its peers), execution/order_manager.py (only if the comparison naturally lives with its fee config), core/codes.py (new registered OM-xxx code, next free number), config.json (`order_manager.fee_recon: {enabled: true, tolerance_bps: 1.0, interval_hours: 24}`), core/config_guard.py, tests.

**Requirement:** W2-9 shipped per-fill venue-fee reading; the remainder is the periodic check of CONFIGURED maker/taker bps vs the account's ACTUAL Kraken fee tier. On its interval (default daily, from hourly_cycle's injected now — never wall clock), query Kraken `TradeVolume` (private, read-only) for the traded pairs; compare the venue's current maker/taker fee (bps) against `pretrade.maker_fee_bps`/`taker_fee_bps` and `order_manager.*` equivalents. Disposition (registered code, audit event, WARN log) when configured < actual (the EV gate is underestimating costs — the dangerous direction) or |configured − actual| > tolerance_bps in either direction. REPORT-ONLY: never mutates config at runtime (lifted-threshold discipline — the operator re-tunes config.json consciously). Surface the last reconciliation result (ts, per-pair actual vs configured, verdict) in the order-manager stats dict → status.json → telemetry.

Fail-safe: missing/invalid API credentials, DRY_RUN without keys, network errors, malformed responses → debug-level skip, never a raised exception into hourly_cycle, never audit spam (at most one audit event per interval). Guards: tolerance_bps in (0, 50] FATAL; interval_hours in [1, 168] FATAL; derivation comment: tolerance 1.0 bps = smallest Kraken tier step matters at our 20.5 bps measured stack.

Tests: mismatch beyond tolerance emits the code once per interval; within-tolerance is silent; configured-below-actual flagged regardless of tolerance direction check; credential-less environment skips silently; response-shape garbage skips; interval honored under injected now; deny-list untouched (assert TradeVolume absent from it and Withdraw entries all still present); stats dict carries the result.

- [ ] Failing tests first; implement; full suite + quant_trials verbatim; commit `feat(execution): periodic Kraken fee-tier reconciliation vs configured bps (#103 T2)`.

### Task 3: Regime-stratified OOF diagnostic (report-only)

**Files:** scripts/overfit_check.py (append a diagnostic section), tests/test_overfit.py (extend), no config/gate changes.

**Requirement:** Append a REPORT-ONLY diagnostic that stratifies the existing OOF predictions by regime (the corpus rows carry one-hot columns `regime_bull_quiet, regime_bull_vol, regime_range, regime_bear, regime_crisis` — stratum = argmax of the one-hots; all-zero rows go to an "unknown" stratum). Per stratum report: n (candidate + live split), base rate, and — only where n ≥ a floor (use the existing evidence-floor convention in the file; if none fits, min 30 with a comment deriving it from the file's own OOF minimums) — OOF AUC and Brier vs the pooled numbers. Flag (text only) strata whose OOF materially degrades vs pooled and strata with insufficient live coverage (this line is Task 4's operator-facing rationale). MUST NOT: change any existing check's verdict, the script's exit code, or the OF-1..OF-7 numbers. Output goes into the same report stream/file the script already writes (overfit_report.md section).

Tests: synthetic corpus with planted per-regime structure stratifies correctly; a thin stratum reports "insufficient n" and is never scored; exit code and existing verdicts unchanged with the diagnostic present (run the script's main path on a fixture corpus twice — with and without the diagnostic reachable — same verdicts); all-zero one-hots land in "unknown".

- [ ] Failing tests first; implement; full suite + quant_trials verbatim; commit `feat(overfit): regime-stratified OOF diagnostic, report-only (#103 T3)`.

### Task 4: Regime-coverage term in the probe-throttle corpus decay

**Files:** main.py (`_exploration_active` corpus-decay block ~:1937 and whatever helper it needs; per-regime live counts via ml/history.py — extend HistoryStore with a cheap cached counter if needed, refreshed on its existing cadence, never a per-cycle CSV scan), config.json (`exploration.corpus_decay.regime_floor_live`), core/config_guard.py, tests.

**Requirement:** P3's corpus decay (`clip(corpus_target_live / max(live, 1), floor_frac, 1.0)`, active past `until_live_rows`) treats the live corpus as one pool, but probe value is regime-local: 231 live rows concentrated in a few regimes teach nothing about the others (gap-analysis follow-on). Extension: while the CURRENT macro regime (the same `macro_state.label` already in scope at the admission site) has fewer than `regime_floor_live` live-labeled rows, the decay term is held at 1.0 (no decay) — the epsilon stays at its base rate for that regime's signals. Once the current regime's live count reaches the floor, the shipped global decay applies unchanged. The share cap (max_probe_share) is NOT touched — it still bounds total probe flow regardless of regime (the stall-under-drought behavior stays deliberate). Shipped value: `regime_floor_live: 60` — derivation (guard comment): corpus_target_live 300 / 5 regime classes = 60 per-regime target; below it the regime's live evidence cannot support the decay's premise ("the learner has enough"). Guards: FATAL outside [0, corpus_target_live]; 0 disables the term (decay reverts to shipped P3 behavior exactly); WARN when regime_floor_live × 5 > until_live_rows × floor_frac coherence bound is violated (the term would dominate the decay it modifies).

Per-regime live counts come from rows whose regime one-hot marks that regime AND that are live-labeled (`source == live` per the store's existing convention) — read the store's schema before writing. Counter must be O(1) at admission time (cached, refreshed at most hourly or on new-live-row append).

Tests: decay held at 1.0 when current regime under floor even at live=1200; shipped decay resumes when regime count crosses the floor; regime_floor_live=0 reproduces P3 behavior byte-identically; share cap still binds regardless; guard refusals; counter never scans the CSV per cycle (assert call pattern or cadence); persistence round-trip unaffected.

- [ ] Failing tests first; implement; full suite + quant_trials verbatim; commit `feat(sizing): regime-coverage hold on probe-decay (#103 T4)`.

### Task 5: Riding minors batch

**Files:** main.py (three small fixes), data/ws_feed.py (W2-28), tests.

Four independent minors, one implementer, one commit:

1. **PT-060 log string** (main.py ~:1890): `f"tier {action.tier_fired or 'trail'}"` logs a time-stop scratch as "tier trail". Make the human reason string reason-aware: when `action.reason_code` is PT-060, the `_submit_exit` reason reads "time-stop scratch" (the meta reason_code wiring is already correct — this is the operator-facing string only). Pin with a test.
2. **Algo-parent admission asymmetry** (main.py ~:2622 vs ~:2679): the algo path records a probe admission at parent creation (before any child submits) while the direct path records only on successful submit — a parent whose first child is rejected still fills the share window. Unify the semantic: record the algo path's admission on its FIRST successful child submission (same "an order actually went out" meaning as the direct path). A parent that never lands a child records nothing. Test: rejected-first-child parent leaves the window untouched; successful child records exactly one admission per parent.
3. **Sub-25s reclamp sliver** (whole-program review Minor #6): a resting maker tier-1 take on a still-virgin position (`tier_closed` increments on FILL) can be preempted by PT-060 when a vol spike reclamps the trigger during the submission-to-fill window — a profitable close mislabeled as a scratch. Fix at the caller (main.py exit-evaluation path): suppress the PT-060 submission when the position already has an OPEN resting profit-take exit order (the order book knows; the tier engine stays pure). The suppression is one-cycle — if the resting take dies unfilled, the time-stop fires next evaluation. Test: virgin position + open resting tier-1 exit + time-stop-eligible state → no PT-060 submit this cycle; same state with the resting order gone → PT-060 fires.
4. **W2-28 checksum-resubscribe backoff** (data/ws_feed.py): checksum-mismatch resubscribes reconnect with zero delay; a systematic mismatch churns reconnects. Add a consecutive-failure backoff (e.g. doubling from 1s, capped at 60s, reset on a clean verified frame) on the checksum-mismatch resubscribe path ONLY — normal reconnect/staleness paths untouched. Constants config-lifted only if a natural ws config block exists; otherwise module constants with a derivation comment (read-only public WS; REST fail-over keeps books flowing — backoff bounds churn, never data availability). Test: N consecutive mismatches space out resubscribe requests per the schedule; a verified frame resets the backoff.

- [ ] Failing tests first; implement all four; full suite + quant_trials verbatim; commit `fix: post-program riding minors — PT-060 reason string, algo admission timing, reclamp sliver, ws checksum backoff (#103 T5)`.

### Task 6: Quant-trials harness enablement — conscious adjudication — then battery + deploy

**Files:** scripts/quant_trials.py (TIER_CFG + harness Position), tests/test_quant_trials.py (CI bounds — ONLY under coordinator adjudication), then fix-forward only.

**Part A (implementer):** Enable the deployed geometry in the harness: give the harness `Position` an `est_cost_bps` populated from the trial's own cost model, add the `time_stop` key and `min_trigger_cost_mult` to `TIER_CFG` mirroring config.json's shipped values, so G1–G5 measure the strategy the bot actually deploys (the coverage boundary documented in P3.5). Run the full 200×1200 battery TWICE (determinism check), record before/after G1–G5 verbatim, then STOP and report — do NOT touch tests/test_quant_trials.py bounds, do NOT commit. The diff and numbers go to the coordinator.

**Part B (coordinator adjudication — not delegable):** The coordinator compares the moved gate numbers against the baseline (G1 4.76 vs 5.53 / G2 −4.57 vs −6.17 / G3 −1.37 vs −2.17 / G4 0.00 / G5 0.55 vs 0.53) and decides: re-baseline the CI bounds at 200×1200 with the derivation documented in the ledger AND in the test file's comments (both directions honest — bounds tighten where the new geometry improves a metric), or revert the enablement with the deferral documented. A gate that the new geometry legitimately FAILS is a STOP-and-report to the operator, never a silent widen.

**Part C:** Full CLAUDE.md battery (pytest, smoke, assurance, overfit — 3/5 baseline + T3's appended section, ruff, pyright, bandit, compileall); push branch; fast-forward main; verify PC pickup via `git show origin/paper-telemetry:control/pc_status.json`; ledger.

- [ ] Part A: enablement + double 200×1200 run, numbers verbatim, no commit.
- [ ] Part B: coordinator adjudication recorded in ledger; commit per verdict.
- [ ] Part C: battery, deploy, PC pickup verified, ledger closed.
