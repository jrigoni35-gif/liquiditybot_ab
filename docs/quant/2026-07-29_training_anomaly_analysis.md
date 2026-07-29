# Quant-training anomaly analysis (2026-07-29, operator ask)

**Disposition (same-day batch):** SHIPPED — #3 deploy deadlock unlocked
(ML-083 era-orphan clause: an unfalsifiable champion watermark falls back
to the absolute cold-start bar, nothing widened); #4 calibration-gap
no_value text corrected on all four panel sites (window filling, not
ML-075 shadow) + JSONs regenerated. ALREADY IN FLIGHT — #1b live tb_*
emission (bracket legs + the PT-060-senior correction shipped earlier
today mean model-lane closes now land tb_pt/tb_sl/tb_time or an honest
overlay reason). EXPECTED/NO ACTION — #1 clean-live-0 (era exclusion
working as decided), #2 uniqueness 0.159 (overlap, corrected by weights;
revisit trigger not met). DEFERRED — #5 per-asset probe decay (design
gap; needs its own spec + quant adjudication; SZ-046 breaker remains the
rate limiter), #3b load_stats restart persistence (panel asymmetry,
cosmetic).

Original agent report follows (verified against code + local data before
acting).

---

# Quant-training anomaly analysis — liquiditybot_ab, 2026-07-29

Read-only audit. All numbers recomputed from the repo's own data files
(`outputs/signal_history.csv`, 6462 rows; `outputs/imported_sessions/pc-live/postmortem_summary.csv`,
212 rows; pc-live model artifact `outputs/imported_sessions/pc-live/meta_model.json`) and by
executing `HistoryStore.load_training_data` locally with the shipped `config.json`.

## Verdict table

| # | Anomaly | Root cause | Class | Evidence (file:line) | Proposed fix (one line) |
|---|---------|-----------|-------|----------------------|--------------------------|
| 1 | CLEAN LIVE LABELS: 0 | Era-gated training exclusion is ACTIVE (1516 tb-era rows ≥ min 150) and ALL 253 live rows are old-era (`realized`→exit_sim: 206, blank→legacy: 47; zero tb_*); `live_clean` is the post-exclusion count, so 0 is the true number, not a stale-era metric | (c) expected (documented operator decision) — with a real residual gap: live closes still never emit tb_* | ml/history.py:1564, ml/history.py:296+311 (`realized`→exit_sim), config.json era_exclusion min_new_era_rows=150, docs/quant/2026-07-27_live_row_era_gap.md:74-83, reproduced load: rows=1516, live_clean=0, excluded live={exit_sim:201, legacy:47} | Make live bracket closes actually land tb_\* (audit senior-overlay/probe-realize close reasons); add "era-excluded" context to the panel description so 0 reads as designed |
| 1b | …why still no tb_* live rows | `bracket_exits` only enabled 2026-07-28 01:24 (git); the few closes since are long-book (out of scope) or probe closes via senior/realize paths — the VOI fastpath realized a 2 h-old bracket (SUI efc8f3e2) with `barrier="realized"` (fixed 07-28 so brackets realize only past deadline as `tb_time`) | (a) real defect (partially fixed, unverified on the live box) | main.py:1360-1361, main.py:2325 (tb_sl), main.py:2527/2535 (tb_pt/tb_time), main.py:230-247 + 4846 (fastpath incident + fix), git: config bracket_exits enabled 2026-07-28 | Verify the deployed PC runs the 07-28/29 fix and that model-lane closes now emit tb_\*; until live tb rows ≥ min_live_rows the evidence gate stays starved |
| 2 | LABEL UNIQUENESS 0.159 | Genuine label-window overlap, not duplicate flooding: replicated mean AFML uniqueness = 0.1558/0.1581 from the CSV; exact feature-row duplicates only 1.1% (74/6462); median label lifespan 38×5 m bars (~3.2 h) with per-cycle candidate registration ⇒ ~6 concurrent labels per (asset,bar). Corrections exist and run: per-row uniqueness weights (enabled), candidate_weight 0.4, clash-dedup (85 dropped), mass-preserving rescale. Sequential bootstrap is a documented, deliberate omission | (c) expected — panel even colors 0.159 green (threshold 0.15) | ml/history.py:1420-1444 (uniqueness weights), 1409-1416 (seq-bootstrap omission + revisit rule), scripts/build_trading_dashboard.py:689-694 (green ≥0.15), recomputation: mean=0.1581, dupes=1.1%, ETH 1901/BTC 1345 rows | None required now; revisit trigger ("<0.3 while a bagged family wins") is NOT met — champion `blend` is a logistic+gbt average, not a bag (ml/walkforward.py:41-46) |
| 3 | RETRAIN: QUEUED persists | Flag file is cleared ONLY by `note_deployed` (deploy), never on reject; and deploys are structurally impossible right now: champion `blend` was trained pre-exclusion on rows=4823, but the post-exclusion training matrix is 1516 rows, so `oof_idx >= trained_rows` is empty ⇒ `rescore_frozen`/`shared_challenger_brier` return None ⇒ like-for-like gate REJECTs fail-closed every retrain. Bonus lock: with live_clean=0 the evidence gate admits only `logistic` (gbt/blend need 60 live) | (a) real defect (deploy deadlock; the queue can never drain) | ml/monitor.py:666 (only unlink site), main.py:5218-5233 (fail-closed REJECT), ml/monitor.py:489-492 (`idx >= seen_rows`), ml/meta_model.py:116 (trained_rows=artifact rows), pc-live meta_model.json rows=4823 vs reproduced post-exclusion rows=1516, config min_live_rows gbt/blend=60 | Reset the champion watermark for the new era (one conscious CLI retrain on the era-filtered corpus, or map trained_rows into post-exclusion index space); also clear/refresh the flag on N consecutive structural rejects |
| 3b | BATCH PRIOR SKEW: "no batch yet" | Panel-mechanics asymmetry, not a skew problem: `prior_skew` is pushed only when `ml.load_stats` is non-empty (populated only by an in-process training load; `{}` after every restart until the first retrain). `state()` panels use instant queries (go dark on staleness) while `stat()` panels use range+lastNotNull (show pre-restart values) — so "Clean live 0" and "uniqueness 0.159" can display while prior-skew honestly shows "no batch yet" | (b) metric/panel mechanics (transient after restart; by-design silent degrade) | scripts/gc_pusher.py:576-578 + 586-590 (documented "observed live for hours"), scripts/build_trading_dashboard.py:203-266 (stat=range/lastNotNull, state=instant), ml/history.py:1216 (`last_load_stats={}` reset) | Either persist load_stats in status across restarts or give the three ls-panels one consistent staleness behavior |
| 4 | CALIBRATION GAP "not scoring — model shadowed" vs MODEL IN USE: YES (blend) | Two different fields, no real contradiction: "Model in use" reads `monitor.use_model` (governor stand-down flag); "Calibration gap" reads windowed ECE that exists only with ≥15 model-scored closes in the last 30 records (`_windows()`), absent otherwise — gc_pusher's own comment says "Absent = not yet judgeable". The no_value TEXT falsely asserts the ML-075 shadow state; window is simply under-filled (closes now ~2-5/day; `note_deployed` also wipes records) | (b) metric/panel bug (misleading no_value label), underlying state (c) expected | ml/monitor.py:175-180 (min_trades=15), monitor.py:661-666 (records cleared on deploy), scripts/gc_pusher.py:526-541, scripts/build_trading_dashboard.py:675-676, config min_trades_to_judge=15 | Rename the no_value to "window filling (<15 model-scored closes)" and emit a separate gauge for the true ML-075 shadow state |
| 5 | WR 9.5%, PF 0.05, −0.37R; DOGE/DOT 12-loss streaks, probes keep entering | A per-asset breaker EXISTS and fires (SZ-046: 4 consecutive losses ⇒ 6 h entry veto, probes included — checked before sizing), but its cooldown auto-resets the streak, so it is a rate-limiter (~4 losses/6 h/asset), which is exactly how a ledger streak reaches 11-12 (perf ledger never resets on breaker pause — separate by design). NO per-asset win-rate-aware probe decay exists ("regime-aware probe decay" from task #103 shipped only as the regime-coverage HOLD, which pins probe epsilon at 1.0 for under-covered regimes — i.e. MORE probes); the exploration lane is designed to pay for labels (dry-run only — system.dry_run=true, so this is paper P&L). Verified from pc-live postmortems (212 rows, loss-biased by construction: only shortfall trades are written): 204 losses, ETH −55.8%/BTC −42.3% cumulative, causes: underperformance 163 / cost_overrun 37; expected-vs-realized gap mean 0.91 pct (p90 1.87); no-progress rides (MFE<0.15%, realized≤−1%) = 39 = 19% of losses; trailing streaks ETH 42, BTC 34, LINK/SUI 15, XRP 14, SOL 12, DOT/DOGE 11, ARB 7 | (c) expected under the learning-phase design + (a) design gap (no per-asset probe suppression beyond the 4/6 h breaker; regime hold actively boosts probes) | risk/circuit_breaker.py:31-32+69-71 (trip=4, cooldown reset), main.py:3368-3376 (SZ-046 veto incl. probes), main.py:1375, config circuit_breaker {4,6 h}, config _regime_floor_live_doc (#103 hold), ml/postmortem.py:252-258 (loss-only file bias), computed stats above | Ship the queued per-asset/regime probe decay (e.g. scale probe epsilon by per-asset Wilson-LCB win rate) or make breaker cooldown escalate on repeat trips |
| 6 | ARB stop-zone 1.00 / FLOW manip 0.72 yet both still trade | Three deliberate layers: (i) THALES `influence="shadow"` — detectors (incl. stop-zone) are telemetry-only, shading is never applied; (ii) even in advise mode, probe sizing floors p_win at 0.70 (`max(p_win, explore_p_win)`) AFTER any confidence shade, and PT-050 bypasses the pretrade profit-EV gate for probes (`bypass_pretrade_ev=true`), so THALES could never reach probe size anyway; (iii) the separately-enforced manip gate DOES bite: 0.72 is in the downsize band (0.6→0.9), scaling entries ≈0.70×; veto only at ≥0.9 | (c) expected per config — but the operator should know THALES is shadow-mode and probes bypass the EV bar | strategies/thales.py:26-27+148 (shadow default), main.py:3221-3226 (shade site), main.py:3306 (p_win floor), main.py:3459 + core/codes.py:63 (PT-050 bypass), main.py:3404-3419 + config manip_gate {0.6/0.9/0.25} (SZ-045 downsize) | If stop-zone should gate probes, either promote THALES to advise (after its own shadow-evidence bar) or add manip/stop-zone terms to probe admission rather than to the (floored) p_win |

## Key reproductions

- `load_training_data(era_cfg=config)` on the synced corpus: rows 1516, live_clean 0,
  mean_uniqueness 0.1581, prior_skew False, dropped_clash 85, era_exclusion
  {armed: True, active: True, new_era_rows: 1516, min: 150}, excluded 4856 rows
  (all 248 in-scope live rows among them); per-era label rates legacy 0.261 /
  exit_sim 0.134 / time_stop 0.0066 / triple_barrier 0.302.
- Live rows: 253 total; barriers `realized` 206 / blank 47; 0 tb_*. The 11 live
  closes since the tb era began (07-26) are all `realized` (probe or long-book).
- pc-live champion: kind `blend`, rows 4823, oof_brier 0.1237, class_balance 0.169 —
  a pre-exclusion-population artifact (post-exclusion base rate is 0.30; Brier not
  comparable, which is precisely why the like-for-like gate then fails closed).
- Uniqueness replication matches the panel (0.156 vs 0.159); exact duplicate share 1.1%;
  rows/asset: ETH 1901, BTC 1345, DOT 577, ADA 385, ARB 282 … LTC 46.

## The one systemic thread

Era exclusion (a sound hygiene decision) activated on 2026-07-26/27 and now interacts
with three consumers that were never re-baselined for it: (1) `live_clean` legitimately
reads 0 because live closes don't yet emit tb_* barriers; (2) with 0 live labels the
evidence gate admits only `logistic`; (3) the deploy gate compares challengers against a
champion whose `trained_rows` watermark (4823) exceeds the entire post-exclusion corpus
(1516), so nothing can ever deploy and the retrain flag can never clear. Until a live
tb_* close stream exists and the champion watermark is re-based, the panels will keep
showing exactly this constellation.
