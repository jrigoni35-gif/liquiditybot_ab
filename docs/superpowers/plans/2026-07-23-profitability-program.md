# Profitability Program — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the expectancy shape the P&L diagnosis exposed (2026-07-23: 209 live closes, win $0.05 vs loss $0.19, payoff 0.27, MFE 0.16% vs MAE −1.44%, probes 69% of closes) via three structural, config-lifted levers — cost-multiple monetization floors, a time-stop on trades that never work, and a corpus-aware probe throttle.

**Architecture:** All three levers are STRUCTURAL rules derived from measured quantities (the cost stack, the corpus size), never fitted literals: thresholds land in config.json with config_guard coherence checks, flow through the existing engines (pretrade EV gate, ProfitTierEngine, exploration governor), and emit registered reason codes. No new engines.

**Tech Stack:** Python 3.11, existing pretrade/profit-tier/exploration machinery, pytest, quant_trials G1–G5, overfit battery.

## Global Constraints

- CLAUDE.md binds in full: thresholds live in config.json with guards (FATAL for incoherent combos); no fitted-looking literals in decision paths; registered reason codes only; public interfaces extended with defaults, never broken.
- OVERFIT DISCIPLINE IS THE LAW OF THIS PLAN: every lever value must be DERIVED from a measured structural quantity (round-trip cost stack ≈ 20.5 bps measured; corpus size), with the derivation written in the config guard's comment. NEVER tune a value to make the backtest/battery prettier. `scripts/quant_trials.py` gates G1–G5 must stay green UNCHANGED — if a legitimate change moves numbers, STOP and report (conscious re-baseline is the coordinator's call, never the implementer's); never widen a gate.
- Exits remain always allowed; the time-stop is an EXIT (allowed under disarm/faults like every exit).
- Every task: failing test first (TDD), full `pytest tests/` green, ruff + pyright (0 errors, shipped scope), and `.venv/bin/python scripts/quant_trials.py` outcome reported verbatim in the task report.
- Commit trailer (exact): Co-Authored-By: Claude Fable 5 <noreply@anthropic.com> + Claude-Session: https://claude.ai/code/session_01TgfcWLtZtVMQhbiPZCCV8h — with `git config user.email noreply@anthropic.com && git config user.name Claude` before committing.

---

### Task 1: Cost-multiple monetization floor (tier-1 target must clear the cost stack)

**Files:** risk/profit_tiers.py (trigger computation), execution/pretrade.py (EV gate context — read only unless needed), config.json (`profit_taking.min_trigger_cost_mult`), core/config_guard.py, core/codes.py (if a new disposition is emitted), tests.

**Requirement:** The FIRST profit tier's effective trigger (after vol scaling and clamps) must be at least `min_trigger_cost_mult ×` the estimated round-trip cost for that entry (maker entry leg + exit leg + spread — the pretrade cost model already computes est_cost_bps; thread the entry's est_cost_bps onto the position/thesis if not already there, extending with defaults). Shipped value: `min_trigger_cost_mult: 3.0` — derivation: measured avg cost overrun 20.5 bps and avg win 5 bps net show tier-1 takes at <1× cost; 3× makes the first take bank ≥2 net cost-units after paying one. Guard: FATAL outside [1.0, 10.0]; comment carries the derivation. Behavior: when the vol-scaled trigger would sit below the floor, the trigger is RAISED to the floor (never lowered); emit the existing tier codes unchanged (the floor is a clamp, not a new disposition — unless you find a disposition is needed; then register it). Tests: floor binds when costs are high; floor is inert when the trigger already clears it; short-side symmetry; config guard refusal tests; the position/thesis cost field round-trips persistence.

**Interfaces produced:** position/thesis carries entry `est_cost_bps` (default 0.0 → floor inert for legacy positions).

- [ ] Failing tests first; implement; full suite + quant_trials verbatim; commit `feat(risk): tier-1 trigger floored at min_trigger_cost_mult x entry cost stack (P1)`.

### Task 2: Time-stop — exit trades that never achieve favorable excursion

**Files:** risk/profit_tiers.py (or the exit-evaluation path it owns), config.json (`profit_taking.time_stop`), core/config_guard.py, core/codes.py (new registered PT-06x code), tests.

**Requirement:** A position that has NOT reached `min_mfe_frac_of_tier1` (shipped 0.5 — half the tier-1 trigger) of favorable excursion within `max_bars_no_progress` (shipped 36 bars = 3 h at 5 m bars) is exited as a scratch (full close via the existing exit path, registered new code, e.g. PT-060 "time-stop: no favorable progress"). Derivation (write into the guard comment): measured MFE 0.16% vs MAE −1.44% and recovered_after_stop 0/17 — trades showing no early favorable excursion overwhelmingly resolve to full-stop losses; scratching them converts −1.4%-class losses into ≈−0.2%-class scratches. Uses the injected `now`/bars-in-trade machinery (EX-8) — deterministic under replay; wall-clock never read. Config: `time_stop: {enabled: true, max_bars_no_progress: 36, min_mfe_frac_of_tier1: 0.5}`; guards: bars in [6, 500] FATAL, frac in (0, 1] FATAL, coherence WARN if bars < the trail-decay window it would shadow. The time-stop is an EXIT: must fire under entries_disabled/fault-latched (pin it). High-water/MFE tracking already exists — reuse it; do not add a parallel tracker. Tests: fires at the boundary exactly; does not fire when MFE clears the fraction; short symmetry; disarm/fault still exits; replay determinism (injected now); config guards.

- [ ] Failing tests first; implement; full suite + quant_trials verbatim; commit `feat(risk): time-stop scratches no-progress positions (P2, PT-060)`.

### Task 3: Corpus-aware probe throttle

**Files:** wherever the exploration/probe admission decision lives (grep `probe` / `explor` in main.py + risk/ + strategies/ — read before writing), config.json (`exploration.max_probe_share` + `exploration.corpus_decay`), core/config_guard.py, core/codes.py (registered veto code if a new disposition is emitted), tests.

**Requirement:** Probe (exploration) entries are throttled by BOTH: (a) a rolling share cap — probes may not exceed `max_probe_share` (shipped 0.35) of the last `probe_share_window` (shipped 40) entry admissions; and (b) corpus-aware decay — the effective probe admission rate scales down as the live-label corpus grows past `corpus_target_live` (shipped 300): effective_rate = base_rate × clip(corpus_target_live / max(live_labels, 1), floor_frac, 1.0) with `floor_frac` shipped 0.25. Derivation (guard comment): probes are 69% of closes and −$22.87 of −$31.68 measured 2026-07-23; the corpus is 3.3k rows/214 live — marginal probe value has fallen while its cost has not; cap share and decay toward a floor rather than to zero (the learner keeps a trickle). Guards: share in (0, 1] FATAL, window [10, 500] FATAL, corpus_target_live ≥ deploy_min_oof coherence WARN, floor_frac in (0, 1] FATAL. Probe DENIALS emit a registered code (register e.g. SZ-/PT- family per where the veto lands). Conviction entries are NEVER throttled by this lever (pin it). Tests: share cap binds and releases; decay math at corpus sizes {50, 300, 1200}; floor holds; conviction unaffected; guards; codes registered.

- [ ] Failing tests first; implement; full suite + quant_trials verbatim; commit `feat(sizing): corpus-aware probe throttle (P3)`.

### Task 4: Battery, quant-trials adjudication, deploy

**Files:** none expected (fix-forward only).

- [ ] Full CLAUDE.md battery (pytest, smoke, assurance, overfit — 3/5 data-thinness baseline is the known state, ruff, pyright, bandit, compileall).
- [ ] `.venv/bin/python scripts/quant_trials.py` full run: G1–G5 verdicts recorded verbatim in the ledger. If any gate moved from its baseline, STOP — coordinator adjudicates (re-baseline at 200×1200 is a conscious decision, never automatic).
- [ ] Push branch; fast-forward main (established deploy channel); verify PC pickup via paper-telemetry; log ledger.
