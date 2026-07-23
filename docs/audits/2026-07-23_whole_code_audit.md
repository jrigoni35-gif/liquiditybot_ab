# Whole-code parallel audit — 2026-07-23 (task #90)

Seven read-only domain auditors (money path, state/persistence, ML loop,
engine/runner, config/guards, ops sidecars, data/signals) swept the full
tree at commit 69d065d. 31 findings; seeds S1-S5 from the task-#89 gap
analysis all adjudicated (S1 CONFIRMED-narrow, S2 CONFIRMED-sharpened,
S3 REFUTED-at-call-site/latent, S4 CONFIRMED, S5 CONFIRMED). Fix program
runs in two waves; every fix lands TDD (failing repro first) under
systematic-debugging discipline.

## WAVE 1 — safety-critical (this session)

W1-1 HIGH main.py:3091-3102 + 1405-1560 — a deterministic raise in
  hourly_cycle (ordered BEFORE fast_cycle) or in the pre-stop segment of
  fast_cycle starves ALL exits indefinitely; wedge alert text claims the
  opposite. Fix: isolate hourly/slow (advance _last_macro regardless),
  run fast_cycle first, isolate the pre-stop telemetry block, correct
  the alert text.
W1-2 HIGH main.py:1413-1414 — no per-event isolation in fill
  application; one raising _handle_fill discards the rest of the batch
  (book/venue desync, dry-run loss permanent). Fix: per-event
  try/except + telemetry counter; snapshot still taken.
W1-3 HIGH core/persistence.py:478-479 — two unguarded restore lines
  (sizer_last_entry / pos_realized .update()) crash every boot on a
  non-mapping snapshot section. Fix: per-section try/except.
W1-4 HIGH core/persistence.py:521-535 — one shared try/except spans 7
  subsystems; a malformed monitor section silently skips circuit-breaker
  + loss-budget restore ("trip laundered by reboot"). Fix: per-subsystem
  isolation.
W1-5 HIGH main.py:1610-1650 — hedge OPEN branch has no mark-freshness
  gate and no new-risk authority (entries_enabled / watchdog /
  fault.allow_new_risk / _halted); can submit new hedge risk
  mid-catastrophe off frozen marks. Fix: gate opens like entries;
  unwind/trim stay ungated (risk reduction).
W1-6 HIGH execution/pretrade.py:193-214 + regime/liquidity_regime.py:224
  — one-sided Kraken book with healthy combined book: spread veto reads
  the combined book, p_fill defaults to the OPTIMISTIC maker_fill_p0,
  and the participation clamp silently no-ops at zero depth (skips
  instead of clamping). Maker-path only. Fix: two-sided-Kraken-touch
  requirement on the maker path; participation clamp fail-closed; floor
  negative spread (latent S3) while in the file.
W1-7 HIGH scripts/auto_update.py:104-116 — decide() has no "diverged"
  outcome: diverged histories re-run the full battery every 15 min
  forever with deploys silently bricked (ff always fails). Fix:
  ancestor probe BEFORE the battery; "diverged" outcome, loud, not OK.
W1-8 HIGH scripts/auto_update.py:207-214 — force-kill escalation
  targets runner.lock's PID with no heartbeat/identity check; Windows
  PID recycling can taskkill the supervisor/pushers/user process
  (tests/test_auto_update_restart.py:28-31 currently pins the bug).
  Fix: fresh-heartbeat requirement + cmdline identity check before
  kill; re-pin the test to the fixed contract.

## WAVE 2 — correctness/robustness (next session(s), tracked)

W2-1 HIGH-learning ml/labeling.py — label sim omits live
  conviction_runner trail-tightening (optimism-biased labels for
  p_win in [0.55,0.70)). Mirror _conviction_trail_mult or document.
W2-2 MED ml/models.py save_model + dual retrain paths — non-atomic
  model write + no lock: CLI vs runner race ships last-writer.
  temp+os.replace + CAS/lock shared by both.
W2-3 MED main.py:2834-2849 — reconcile_champion_badge not called on
  reload_if_changed rejection path (ghost-badge deadlock reachable).
W2-4 MED ml/history.py dedup — twin match misses on cross-cycle
  funding_dist drift; thread candidate lineage instead of exact vector.
W2-5 MED runner.py force_dry — strands resting LIVE orders in sim/real
  limbo (cancel-first or poll-to-terminal). Live-mode only.
W2-6 MED runner.py flatten_all while PAUSED — exits rest unmanaged
  (no poll/dead-man while paused); ack overstates. Live-leaning.
W2-7 MED config_guard batch — markout (S5), watchdog inversion set,
  pretrade EV/participation/staleness, exit-escalation caps +
  mark_stale_sec, slow_cycle_every_n>=1, order_timeout_sec>0, leverage
  governor knobs, monitor judge-window coherence, vol/sentiment
  ordering pairs; + align ~8 .get() defaults with config.json
  (retrain_cooldown_hours 12v6, min_hedge_usd 50v15, min_order_usd
  25v15, min_half_spread_bps 4v26, vol_scaled F v true, fee fallbacks,
  tick_confirm_ratio missing key).
W2-8 MED execution/order_manager.py — post-format >0 guard before
  AddOrder + dust-exit floor independent of omin>0 (S1).
W2-9 MED execution/order_manager.py — read venue-reported per-fill fee
  when present; reconcile configured bps vs account tier.
W2-10 MED main.py _place_ladder — deep rungs never re-check
  p_fill-weighted EV floor (PT-040); per-rung cheap EV check or bound
  rung distance vs sigma.
W2-11 MED regime/liquidity_regime.py:224 — Kraken-book expiry lets
  combined-book samples poison imb/depth/mid/large_levels histories
  (false spoofy, tier distortion ~30 min). No-observation cycles.
W2-12 MED data/ws_feed.py — Kraken v2 book checksum never validated;
  partial-frame parse skip can drift a book that never goes stale.
W2-13 MED scripts/pc_supervisor.py — negative ages read as fresh (clock
  step back silences all cadences + blocks dead-runner relaunch).
W2-14 MED scripts/gc_pusher.py — manip_suspect loop lacks the DL-1
  numeric guard (whole-batch blackout); _num passes inf (OverflowError
  at tiers_fired). Also: missing status.json should emit the alarm
  batch, not silence — CONSCIOUS RE-DECISION needed (currently pinned
  as intended in tests/test_remote_control.py:271-274).
W2-15 MED core/fault.py — FaultManager latched state not persisted;
  future CRITICAL latches silently re-armed by routine restart. Policy:
  persist all except cycle_wedged (documented recoverable), or pin
  "every CRITICAL latch sets _halted".
W2-16 MED execution/markout.py — to_dict/restore + persistence wiring
  (S4); config guards land in W2-7.
W2-17 LOW-MED ml/monitor.py — L0<->L1 no deadband (kelly/shrinkage flap).
W2-18 LOW-MED main.py:767 + ml/monitor.py:142 — wall-clock seeds break
  replay parity (drought fastpath, cause decay); seed from injected now.
W2-19 LOW core/codes.py — register CG-000, EX-ALGO-*, candidate
  disposition strings; route through tag().
W2-20 LOW core/runtime.py atomic_write_json — tmp not unlinked when
  retries exhaust (orphan litter under lock storms).
W2-21 LOW scripts/auto_update.py:288-291 — outcome stamp hardcodes
  origin/main as "remote" on branch-checked-out boxes.
W2-22 LOW data candle boundary — local-clock committed-bar inference;
  use Kraken OHLC "last" / OKX confirm.
W2-23 LOW execution/fair_value.py — frozen Kraken touch fabricates
  basis/edge during outages; age-stamp and zero out.
W2-24 LOW strategies/thales.py — sweep fence/decay mixes bar-open ts
  with local now (advice-bounded).
W2-25 LOW scripts/gc_log_pusher.py — lacks trace_pusher's
  advance-on-junk fix; remote_control _git logs stderr (could echo a
  credentialed remote URL into local logs).

## Clean-area consensus (all seven auditors)

Firewall self-validation, sizer/protocols degenerate-case handling,
audit-chain healing + seam classification, position/order round-trip
fidelity, remote-command surface, supervisor lock liveness (modulo
W2-13), sanitize boundary, THALES clamps, exploration/give-back blocks,
walk-forward purging, calibration OOF discipline, evidence floors.

W2-26 MED execution/pretrade.py book_walk_bps — returns 0.0 (not the
  1e6 sentinel) when the walked side is WHOLLY empty, so a taker entry
  against a fully one-sided book gets a zero walk cost instead of the
  PT-023 veto (found by the W1-6 fixer, 2026-07-23). Repro + fail-closed
  sentinel needed.

W2-27 MED main.py:1522-1528 — with W1-1's isolation, a persistently
  raising watchdog.evaluate no longer trips the wedge guard, and
  entries proceed on the FROZEN prior entries_blocked value (fails
  open on the entries side during the one incident that breaks the
  watchdog). Follow-up: treat a raised watchdog.evaluate as
  entries_blocked=True for that cycle (whole-wave review, 2026-07-23).
