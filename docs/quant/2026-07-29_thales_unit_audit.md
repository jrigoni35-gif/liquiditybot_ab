# THALES unit-coherence + earning-its-keep audit (2026-07-29)

**Disposition (same-day batch, commit follows this doc):** SHIPPED — A-1
Wilson base-rate null + dead-mute probation + __base__ ledger; B-2 shadow
grading unlock (main.py stores fired in both modes, empty lists grade the
base); A-3 spoof EWMA wall-time normalization (decay_cal_sec); A-2
stop-zone geometric-null subtraction (finest-step spacing); B-1b probe
floor withheld under manip downsize (both sizer call sites). DEFERRED —
promotion to advise (needs the shadow evidence B-2 now accrues, plus its
own quant bar); TH-021 re-parameterization (provable no-op as shipped);
per-detector counterfactual-PnL grading (bigger design).

Original agent report follows (verified before fixing; the A-1/A-2/A-3
worked examples were reproduced in tests/test_thales_unit_audit.py and
tests/test_thales_v2.py).

---

# THALES Manipulation-Defense Layer — Unit-Coherence & Earning-Its-Keep Audit
Date: 2026-07-29 · Repo: /home/user/liquiditybot_ab (read-only audit, nothing changed)

Modules: `strategies/thales.py` (ThalesEngine, TH-010..TH-021), `main.py` (manip_suspect_score /
manip_entry_scale / whiplash_suspicion, shade + gate call sites), `regime/liquidity_regime.py`
(spoof_score, imbalance_whiplash — the inputs to manip_suspect), `strategies/signal_gates.py`
(concentration_conf_mult, TH-021), `ml/history.py` (training down-weight), `risk/long_book.py`
(TH-013 bid hygiene via `round_number_grid`). Local data: `outputs/` (live-synced session,
signal_history.csv 6,462 rows / 253 live), `outputs/imported_sessions/pc-live/` (audit.jsonl 6.8M,
postmortem_summary.csv 212 rows), `outputs/status.json`, `outputs/thales_report.txt`.

Two distinct stacks share the "manipulation" label — keep them separate when reading verdicts:
- **ThalesEngine** (strategies/thales.py): grid/metronome/clockwork/stop-zone/barclose/spoof-flicker/
  feed-dirty/lapse. Shades *confidence*, influence-gated. **Currently `influence:"shadow"`** (config.json).
- **manip_suspect** (main.py:327-348): MAX(liq-model spoof_score, whiplash_suspicion, cross-venue
  divergence). Feeds the risk.manip_gate size scale/veto, the `manip_suspect` model feature, and the
  training-weight discount. **Live and enabled.**

---

## MANDATE A — Unit-coherence findings

### Verdict table A (findings)

| # | Severity | Where | Class | Finding (one line) |
|---|----------|-------|-------|--------------------|
| A-1 | HIGH (latent — only bites in `advise`) | strategies/thales.py:187-211 (`_wilson_lcb`, `_rel_weight`), 213-229 (`note_outcome`) | probability compared against wrong null | Reliability weight `w = max(0, 2·WilsonLCB − 1)` grades vindication against a **0.5 coin-flip null**, but vindication of "up" advice = P(win) with a realized base win rate of **15.8%** (40/253 live rows). Every honest up-detector gets muted at exactly `min_fired=20`; uninformative down-detectors keep ~0.44 weight. |
| A-2 | HIGH (telemetry) / LOW (decision impact) | strategies/thales.py:529-578 (`_stop_zones`), 55-73 (`round_number_grid`), config `stops.zone_tol_pct=0.15` | threshold calibrated in one unit applied in another | Proximity tolerance (0.15% of mark) is not normalized by magnet spacing (grid admits steps down to 0.30% of mark), so the tol band covers 30–100% of the gap between adjacent magnets → prox has a huge geometric base rate: corpus `th_stopzone` mean 0.42, **43.4% of all rows > 0.5**, 7% > 0.95. "Stop-hunt proximity 1.00" on the dashboard is mostly the detector's null, not a stop hunt. |
| A-3 | MEDIUM | strategies/thales.py:307-351 (`_update_spoof`), config `spoof.decay=0.85`, `score_thr=0.35` | per-poll EWMA vs wall-clock phenomenon | TH-017 flicker score is an EWMA **per fast snapshot** while the spoofing it measures is a wall-time process; the same physical spoofer flips between "fires" and "invisible" purely on poll cadence. |

#### A-1 worked example (the load-bearing one)
`note_outcome` (thales.py:213-229) counts an "up"-advising detector vindicated iff the trade WON,
"down" iff it LOST. `_rel_weight` then maps `max(0, 2·LCB90 − 1)` onto the gain. Verified with the
shipped `_wilson_lcb` (z=1.28) and the measured live base win rate 40/253 = **15.8%**:

| Detector at n=20 graded trades | k vindicated | Wilson LCB | weight w |
|---|---|---|---|
| No-skill **up** detector (wins at base rate 15.8%) | 3 | 0.075 | **0.000** (muted — fine) |
| **Up** detector with a 2× win-rate lift (32% win when firing — a huge real edge) | 6 | 0.188 | **0.000** (muted — WRONG) |
| Up detector needs k≥14/20 (70% win in a 16%-win regime) to keep ANY voice | 14 | 0.558 | 0.116 |
| No-skill **down** detector (vindicated at loss rate 84.2%) | 17 | 0.722 | **0.443** (keeps voice — WRONG) |
| True coin flip | 10 | 0.362 | 0.000 |

Divergence: a genuinely 2×-better-than-base up-detector is muted forever (once w=0 the detector is no
longer appended to `fired` — thales.py:647,658,668 gate `if w > 0` — so it can never accrue new grades
and never redeems itself), while a zero-information down-detector keeps 44% of its gain. The [0,1]
"vindication proportion" is in *outcome-base-rate units*, the 0.5 threshold is in *fair-coin units*.
Correct null would be the contemporaneous base win rate (or grade against counterfactual PnL). Latent
today because shadow mode never populates `fired` (main.py:3247-3248) — see B-2.

#### A-2 worked example
ARB at mark $0.52: `round_number_grid` → k=0.1, candidate steps {0.001, 0.0025, 0.005, 0.01, 0.025,
0.05}; accepted in [0.3%, 3%]·mark = [$0.00156, $0.0156] → {0.0025, 0.005, 0.01}. Finest magnet grid
$0.0025 (0.48% of mark). tol = 0.0015·0.52 = $0.00078. Distance from a random mark to the nearest
0.0025-multiple is ~uniform on [0, $0.00125] → P(prox > 0) = 2·0.00078/0.0025 = **62%**,
P(prox > 0.5) = **31%**, before adding the nested 0.005/0.01 grids and the swing-hi/lo magnets.
Corpus confirms the base rate: `th_stopzone > 0.5` on 43.4% of 6,462 rows; per-asset means ARB 0.50,
SUI 0.49, BTC 0.48, DOGE 0.48 — i.e. the score hovers at half-scale everywhere the tick is fine
enough to pass the degeneracy guard. Realized-outcome check (253 live rows): mean net PnL at
th_stopzone ≥ 0.5 = −$0.164/trade vs < 0.5 = −$0.166/trade; win% 17.5 vs 14.7 — **zero
discrimination**. Decision impact is bounded (pre_gain 0.1 → worst shade ×0.90, and only in advise
mode), but the gauge the operator watches ("ARB stop-hunt proximity 1.00") is ~noise at these price
magnitudes. Fix shape: normalize tol by the *magnet spacing actually selected* (e.g. prox measured in
units of half-spacing), or raise the step floor to ≥ 4× tol.

#### A-3 worked example
A spoofer pulls a ≥3×-median wall every 10s (event magnitude 1.0). EWMA recursion x' = 0.85x + 0.15e:
- Fast cycle at nominal **5s** (config `system.polling_interval_sec=5`): event every 2nd poll →
  steady state oscillates 0.46↔0.54, mean ≈ 0.50 > thr 0.35 → **fires**.
- Effective cadence **10s** (Kraken 3/s rate limit + 12 serial book fetches; main.py:1896-1903
  documents ~2s just for books, plus backoff): event every poll → score → **1.0, saturates**.
- Hypothetical **2.5s** cadence: event every 4th poll → mean ≈ 0.25, peak < 0.31 → **never fires**.
Same physical manipulation, three different verdicts, purely from sampling cadence. The threshold
0.35 is in per-poll event-rate units; the phenomenon is per-wall-second. (The analogous liq-model
spoof EWMA is NOT flagged: `spoof_ewma_alpha=0.06` was explicitly calibrated at the 30s slow-cycle
cadence it runs at — regime/liquidity_regime.py:135-153.) Severity MEDIUM: cadence is nominally
fixed, but degrades under rate limiting with no fence below TH-016's 600s gap threshold.

### Checked-clean list (verified, with the check that cleared each)

| Item | Where | What was verified |
|---|---|---|
| Wilson LCB **n** = closed trades, not per-poll pseudo-samples | thales.py:213-229, main.py:1380-1384 | `note_outcome` called once per closed position (`fired` captured at entry, popped by position_id); n can never be inflated by poll-rate observations. Formula itself is textbook Wilson lower bound, correct algebra, z=1.28≈90% one-sided. |
| Metronome quantization cannot fake a clock | thales.py:395-419 | Intervals sampled at 5s polls are 5s·Geometric(p); CV=√(1−p). The `min_interval_sec=8` median guard forces p ≤ 0.5 → CV ≥ 0.707 → score ≤ 0.293 < thr 0.6. Pure Poisson flow can never cross the threshold; aliasing only causes false *negatives* (a 7s timer reads as alternating 5/10s, median 7.5 < 8 → neutral). Conservative, clean. |
| Bar-close phase buckets vs poll cadence | thales.py:775-808 | `now % 300` phase with 10×30s buckets sampled by 5s polls = 6 polls/bucket, uniform; events are per-poll binaries so no bucket can be over-sampled; Kraken 5m bars are epoch-aligned so the 300s wall clock == the bar clock. min_events 120 vs steady-state total (33× events/bar at 0.97 decay) is reachable on active books only — quiet books stay 0, never spurious. |
| Clockwork units | thales.py:493-497, 504-527 | ret = (c/o−1)·100 percent-per-5m-bar consistently on both sides of the z-test; z = (μ_b−μ_pool)/√(σ²_pool/n) — same units, correct SE-of-mean n. Bars deduped by ts (`seen_bar_set`); dedup window 4032 bars (14 days) ≫ fetch window, no double counting. |
| Stop-zone %-vs-fraction plumbing | thales.py:535 (`zone_tol_pct/100`), 55-73 (0.003/0.03 fractions), 576-578 (d as fraction of mark) | percent config → fraction at one boundary, compared fraction-to-fraction throughout. (The A-2 finding is calibration geometry, not a unit conversion bug.) |
| FLOW coarse-tick degeneracy guard | thales.py:545-560 | Inferred tick ≥ tol·mark disables prox (FLOW $0.026: one tick = 38bps > 15bps tol). Confirmed in data: FLOW `th_stopzone` mean 0.00 across 6,462 rows while peers sit at 0.4-0.5. Works as designed. |
| Sweep timestamp bookkeeping | thales.py:589-607 | Sweep stored at bar-CLOSE (ts + bar_spacing), decay read `now − ts` in seconds against `revert_decay_sec=1800` — same clock, no per-bar/per-second mixup; lapse fence compares bar-close vs wall-clock fence correctly (W2-24 comment matches code). |
| TH-016 lapse units | thales.py:263-287, 470-491 | fast_gap 600s vs 5s polls, warmup 900s, bar holes in units of the EWMA'd *observed* bar spacing (median-seeded, hole excluded from the EWMA) — all seconds, self-consistent, self-healing on ms-vs-s bar timestamps (plain assignment re-base, line 486-491). |
| TH-014 feed-dirty | thales.py:756-773 | Dirty fraction over a 40-poll (~200s) window, threshold 0.25 in the same fraction units; gain 0.5·(dirty−0.25) bounded by the global clamp. |
| Shade composition | thales.py:638-748 | Multipliers compound multiplicatively (not averaged), clamp [1/1.15, 1.15] applied after composition, confidence re-clamped to [0,1]. Max possible down-shade 13%, up 15%. |
| manip_suspect divergence normalization | main.py:346-348, 405-431 | Per-venue log-imbalances each clipped [−2,2] → |diff|/4 ∈ [0,1]; SD-003 mixed-unit merged-book bug is fixed (composite = mean of per-venue log ratios, never a cross-venue size ratio); no external book → divergence exactly 0, not "manipulated". |
| whiplash calibration cadence matches operating cadence | regime/liquidity_regime.py:135-144,294; main.py:477,573-574,3110-3114 | Whiplash = std of 20 imbalance snapshots calibrated at ~30s cadence; `liq.update` runs in `_refresh_market_state` ← slow_cycle = every `slow_cycle_every_n=6` × 5s polls = 30s. Same cadence. `whiplash_suspicion` normalizes (std−1.27)/(1.45−1.27), both ends in the same std-of-clamped-ratio units. |
| Percent→bps at the EV boundary | main.py:3439-3440 | `exp_alpha_bps = …·base_stop_pct·100` — percent × 100 = bps, correct (this is the site the 2026-07-29 unit audit already fixed for b≠1). |
| Osler stop nudge bps | main.py:302-324 | `|stop−level|/stop·1e4` vs buffer_bps, pad = level·bps/1e4 — bps consistent both directions. |
| sigma_bar_pct handoff | main.py:3344-3346 | `candidates.register(..., vol_state.sigma_bar_pct / 100.0, …)` — percent→fraction at the boundary, as the labeler expects. |
| TH-013 reuse in long book | risk/long_book.py:97,761-767 | Bid hygiene shifts off `round_number_grid(mark)` magnets — same absolute-price grid, no re-derivation drift. |

---

## MANDATE B — Is THALES earning its keep?

### Verdict table B

| # | Question | Verdict | Evidence |
|---|----------|---------|----------|
| B-1a | Does the manip suspicion score reach position sizing? | **YES for manip_suspect (live); NO for ThalesEngine (shadow = zero decision influence)** | manip gate: main.py:3387-3401 → `manip_scale` → `risk_scale=self.monitor.kelly_mult*explore_scale*manip_scale` (main.py:3409) → position_sizer.py:498. Enabled: config `risk.manip_gate {downsize_at:0.6, veto_at:0.9, min_scale:0.25}`. ThalesEngine: config `thales.influence:"shadow"` → thales.py:736-742 returns confidence untouched (`out.mult=1.0`, counterfactual only). The 65 shade events ever recorded are all "would-shade" (outputs/thales_report.txt: 0 up / 65 down, mean ×0.948, zero applied). |
| B-1b | Do EXPLORATION probes bypass/dilute the shade? | **YES — three ways** | (1) PT-050 EV bypass (execution/pretrade.py:340, `explore_bypass_ev:true`). (2) Probe sizing p is floored: `p_win = max(p_win, 0.7)` (main.py:3306, config p_win 0.7; aggressive 0.72 at 3317) — any THALES/gate confidence shade upstream of `meta.p_win` is erased whenever shaded p < 0.7, i.e. nearly always for probes. (3) The manip **downsize band is void for standard probes**: `floor_to_min=(explored and not aggressive)` (main.py:3410) re-inflates the post-`risk_scale` notional to the $15 explore floor (position_sizer.py:531-537) — a manip 0.72 book gives manip_scale 1−(0.72−0.6)/0.3·0.75 = **0.70×, then the floor puts the probe right back at $15**. Only the hard veto (≥0.9) and the aggressive-lane `max_manip 0.6` actually reach the probe lane. The dashboard observation (ARB stop-hunt 1.00 + FLOW manip 0.72, both trading probes) is exactly this wiring: stop-hunt gauge = shadow THALES stop_zone (zero influence, and ~noise per A-2); FLOW 0.72 < 0.9 → probe admitted at floor size. Data: pc-live audit ML-070 probe admissions n=2,262 with manip recorded — 316 admitted at manip ≥ 0.6, **129 at ≥ 0.9** (admission logging happens before the gate); the veto then held downstream: **max manip on any of the 253 live FILLS is 0.842 — zero fills ≥ 0.9**; 11 live fills at manip ≥ 0.6 (6 flagged probes). SZ-045 vetoes are logged only via `_log_sizer_veto` → logging (main.py:2908-2916), never the audit chain — they're invisible in audit.jsonl (0 hits), which is why the gate looks inert in the audit while actually binding. |
| B-2 | Has ANY detector accumulated realized outcomes (Wilson-LCB ever engaged)? | **NO — reliability layer has never engaged and CANNOT in the current mode** | Ledger empty everywhere: `outputs/status.json` thales.reliability absent/null, recent_advice []; `outputs/state.json` (v2, 2026-07-18) has no `thales_reliability`/`pos_thales` keys at all; persistence support exists (core/persistence.py:409-416, 749-755) but has only ever saved nothing. Root cause is structural: `_thales_fired[asset] = list(th.fired) if influence == "advise" else []` (main.py:3247-3248) → in shadow mode `note_outcome` receives nothing, ever. **Chicken-and-egg: promotion to advise requires shadow evidence, but the reliability ledger only learns in advise.** The separate shadow-evidence loop (scripts/thales_report.py) is itself data-starved: only TH-013 has ever fired (65/65 events; 206 TH-013 lines in events.jsonl; grid/metronome/clockwork/barclose 0), and its counterfactual exposure join has 8 exposed vs 0 unexposed labeled trades ("keep shadow, keep accruing" per its own output). So THALES is running but **functionally inert as a decision layer**, and A-1 means that if promoted tomorrow, the reliability loop would start mis-grading immediately. |
| B-3 | Learning down-weight path wired and non-zero? | **YES — wired, active, material** | main.py:5053-5056 passes `manip_discount=0.5` (config ml.sample_weights) into `history.load_training_data` → ml/history.py:1370-1372 `w *= 1 − 0.5·manip_suspect` on every retrain. Corpus manip_suspect: mean 0.233, p75 0.372, 50% of rows > 0.156 → average training weight factor ≈ 0.88, a fully-suspect row keeps 0.5. Feature side also wired: `manip_suspect` + `th_grid/th_metronome/th_clockwork/th_stopzone/th_barclose` are model features (ml/features.py:124, 393; main.py:4714-4733), non-degenerate in data (th_stopzone mean 0.42). |
| B-4 | TH-021 evidence-concentration shade: gate state, case for enabling? | **Gated OFF; enabling it today would be a provable NO-OP (dead band)** | Gate: config `thales.evidence_concentration.enabled: false`; wired at main.py:3232-3243 → signal_gates.py:28-62 (down-only, ≤15% trim, tests in tests/test_concentration_shade.py). Case check on data: the trim requires concentration < 0.35 AND confidence ∈ [0.50, 0.65). All 422 concentration-instrumented rows in signal_history have gate_confidence ≥ **0.701** (min observed; mean 0.87) — a confirmed 5-gate signal never lands in the marginal band as parameterized. Would-trim set on the whole corpus: **n = 0**. Verdict: no case to flip the flag as-is; the shade needs re-parameterization (marginal_conf ≳ 0.75) first, and that is a new behavior requiring its own shadow evidence per the docs' promotion bar (docs/THALES.md §Evidence concentration, "shadow hit-rate beats null + OF/quant battery green"). Do not enable to "do something" — it will do nothing. |
| B-5 | Keep-earning test: do high-manip entries lose more? | **No dose-response → detectors currently indistinguishable from noise on realized outcomes (small n)** | 253 live fills: manip < 0.3 → n=207, win 18.4%, mean −$0.142; 0.3–0.6 → n=35, win 2.9%, mean −$0.316; ≥ 0.6 → n=11, win 9.1%, mean −$0.129. Postmortem join (173 of 212 pc-live shortfall records matched by position_id): mean realized_pct −0.85% / −0.91% / −0.75% across the same buckets. High-manip entries do NOT lose more; the mid band is worst. Since the shade never applied (shadow) and the downsize is floored away for probes, this cannot be "the shade worked" — it is "the detectors haven't demonstrated predictive value yet" (n=11 at ≥0.6 is too thin to close the question, but there is no signal so far). th_stopzone shows the same: −$0.164 vs −$0.166 per trade above/below 0.5. |

### Bottom line
- **Unit hygiene of the detector math is largely good** — percent/fraction/bps boundaries, per-poll vs
  per-bar clocks, and the Wilson n are all correct (14-item clean list). The three real defects are
  calibration-in-the-wrong-units, not arithmetic: a reliability null in coin-flip units over a 16%-win
  outcome stream (A-1), a proximity tolerance in percent-of-mark units unnormalized by magnet spacing
  (A-2), and a spoof threshold in per-poll units over a wall-time phenomenon (A-3).
- **THALES the engine is not earning its keep today and cannot start**: shadow mode has zero decision
  influence, the reliability ledger only learns in advise mode, only 1 of 6 detectors has ever fired,
  and its shadow counterfactual is data-starved (8/0). The parts of the manipulation defense that DO
  work are outside ThalesEngine: the manip_gate veto (bounded live fills below 0.9 — verifiable in
  data), and the training-weight discount (active every retrain).
- Before any promotion to advise: fix A-1's null (or grade against counterfactual PnL), renormalize
  A-2 (else stop_prox — the only detector that fires — will dominate the fired ledger with base-rate
  noise and, per A-1's down-side bias, entrench itself), and decide whether probes should honor the
  shade (today they would not, by construction).
