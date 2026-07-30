# SPB-R: Scarcity-Priced Probe Budget, Refunded — probe admission redesign

**Status:** DESIGNED, verified, awaiting implementation go-ahead (Stage 0
lands dark / behavior-preserving; the mode flip is an operator decision).
**Provenance:** 2026-07-30 design panel — three independent designers
(tuition-budget / minimal-epsilon-repair / budgeted-bandit stances),
three adversarial judges (overfit-discipline, statistics, failure-mode
red team), synthesis architect; all code claims line-verified (appendix).
Operator mandate: "yes design the probe decay" after the measured
starvation diagnosis (share cap's admission-count denominator frozen by
zero conviction flow -> ~1 probe/8h; 1,517 SZ-047 denials/12h).

All load-bearing claims verified. Two corrections to the brief found during verification: config actually has `max_probe_share: 0.35` / `probe_share_window: 40` (config.json:578-579), not 30%/10 — the defect analysis is unchanged (14 probes freeze the 40-slot window when conviction flow is ~zero); and SZ-050 is already taken by `SZ_DD_THROTTLE` (core/codes.py:138), so every candidate's code numbering needed repair. Here is the final design.

---

# FINAL DESIGN — SPB-R: Scarcity-Priced Probe Budget, Refunded (probe admission redesign)

**Base:** Candidate 3 (highest composite: 8.5 / 8.5 / 8). **Grafts:** placement-time accounting + refunds (repairing C3's decision-time burn, C1's economics without its reservation-leak class), probabilistic affordability (repairing C3's greedy-queue starvation), C2's event hygiene + cross-guards + RNG discipline, C1's Wilson-UPPER surcharge (dark). **Dropped:** everything any judge showed fatal (see §10), with one explicit refutation (§10, item R1).

---

## 1. Admission mechanism — exact math

All quantities dimensionless unless marked. All timestamps are engine-injected `now` (seconds) — the SZ-048 precedent (main.py:2694 "Engine `now` only — wall clock here would break replay determinism"). All label counts are LIVE labels only.

### 1.1 Scarcity price (deterministic, no RNG)

```
A          = len(engine symbol universe)                      [13 today; the iterable _entry_assets rotates over]
T_a        = corpus_target_live / max(A, 1)                   [labels/asset; 300/13 ≈ 23.1 — reuses existing knob, config.json:587]
F          = scarcity_floor if set else corpus_decay.floor_frac  [0.25 — reuses existing knob, config.json:588]
n_a        = live labels on asset a        (new HistoryStore.asset_live_counts(), §7)
n_r        = live labels in regime r       (existing HistoryStore.regime_live_count(), ml/history.py:1100)

w_asset(a) = clip( sqrt( T_a / (1 + n_a) ), F, 1 )
w_regime(r)= clip( sqrt( regime_floor_live / (1 + n_r) ), F, 1 )   [regime_floor_live = 60, config.json:589]
S(a,r)     = max( w_asset, w_regime )                          ∈ [F, 1]     [max: EITHER scarcity dimension redeems — a bear-regime ETH signal prices at 1.0]
cost(a,r)  = min( 1/S × surcharge(a), C )                      ∈ [1, C]     [surcharge = 1.0 while dark, §1.4; final clamp at capacity C so no probe is ever priced above one full bucket — a price > C would be a livelock wall under strict affordability and is forbidden by construction]
```

Unmapped regime label → treated as n_r = 0 → w_regime = 1.0, cost 1.0 (fail-safe scarce, same direction as the existing hold, main.py:2641-2642). Worked at today's data (range regime, n_range = 227 → w_regime = √(60/228) = 0.513): ETH(73) cost 1.79 · BTC(61) 1.64 · LINK(18) 1.0 · AVAX(3) 1.0 · any non-range signal 1.0.

Shape note (stats judge, C3-fixable-5): √ is the Bernoulli SE / Wilson-width scale (n^-1/2); the shape question is bracketed from below by `scarcity_pricing:false` (flat cost 1.0), which stays a real config point so the simplicity ladder can race the 1-knob rule honestly.

### 1.2 Token bucket (replaces `_probe_share_would_deny`, main.py:2709)

State (snapshot-persisted, §5): `tokens` (float, init 0.0), `last_refill_ts` (engine s, init first cycle `now`).

```
R      = tokens_per_day / 86400            [tokens/engine-second; default 15/day]
C      = tokens_per_day × burst_hours/24   [capacity; 15 × 8/24 = 5.0 tokens = exactly one book-fill]
R_eff  = f_governor × R                    [§1.5]

Refill (at each budget-mode admission decision):
  tokens ← min(C, tokens + R_eff × (now − last_refill_ts));  last_refill_ts ← now
```

### 1.3 Probabilistic-affordability admission (the starvation repair)

At the `_probe_admission_decision` site (main.py:2758), replacing the share-cap branch in `mode="budget"` — evaluated only AFTER `_exploration_active` (epsilon × decay × regime-hold × taper) has already rolled True:

```
p = clamp( tokens / cost(a,r), 0, 1 )
u = self._budget_rng.random()              [DEDICATED stream: random.Random(f"{system.seed}:probe-budget") —
                                            _explore_rng's draw count is untouched in BOTH modes (C2's discipline);
                                            str-seeding is deterministic, PYTHONHASHSEED-independent]
ADMIT  iff  u < p        (requires tokens > 0)
on non-admit: fall through to _drought_floor_admit(now) exactly as today (SZ-048 verbatim)
```

Why probabilistic, not strict `tokens ≥ cost` (failure judge, C3-fixable-1): under strict affordability the bucket is stripped at cost ~1.0 the instant it crosses 1, so a 1.79-cost ETH probe never finds tokens — a de-facto starvation wall (the taper lesson). Under `p = tokens/cost`, relative admission rates between arms are `λ_a / cost_a` — exactly "price = inverse admission weight", with every arm's probability > 0 whenever tokens > 0. No wall, floored steering.

### 1.4 Deduction at PLACEMENT, refund on unfilled terminal (the accounting repair)

**Deduct at placement, not decision** (C2 graft): the decision stashes `self._pending_probe_cost[asset] = cost`; the existing placement hook `_record_probe_admission(is_probe)` (called only after `orders.submit` succeeds — main.py:3734, 4537, 1225) is extended with-defaults to `_record_probe_admission(is_probe, cost: Optional[float] = None)`; in budget mode it pops the stash and does `tokens ← tokens − cost` (may go negative: bounded debt, floor −C by construction since deduction only occurs from tokens > 0 and cost ≤ C; worst debt C = 5 tokens = 8h refill, typical ≤ 1.95 today ≈ 3.1h). It also writes `order.meta["probe_cost"] = cost`. A probe vetoed between decision and placement (manip $15-withhold, min-ticket, SZ-046, firewall) never reaches the hook → **costs zero** — the stash is overwritten/discarded at the asset's next decision. Decision→placement is sequential within one signal's processing in `cycle_once` (verified 3364 → 3705 → 3734), so no interleaving.

**Refund on unfilled terminal** (`refund_unfilled_entry: true`): at the engine's order-terminal seam (the code that already reads `order.meta["probe"]`, main.py:1201-1225 class), if a probe entry terminates with `fill_ratio == 0`, `tokens ← min(C, tokens + meta["probe_cost"])`, emit SZ-052. Partial or full fill → position exists → ML-073 realizes a label ≤ 8h → no refund. **This is leak-proof where C1's reservation was not**: the refund is keyed to the ORDER lifecycle, which OrderManager terminates by construction within `order_timeout_sec = 25s` (+ ≤ 1 reprice; deadman 60s) — verified execution/order_manager.py:130-136, 943, 1149. No state waits on an event that may never come; the cost rides in `order.meta`, so there is no orphanable side-table at all.

Net effect: the budget depletes only on probes that actually FILL — i.e., on labels — which imports C1's "cheap probes buy more labels" self-regulation without any close-path settlement machinery, and erases the failure judge's mix-bias finding on C3 (manip-withheld thin-alt probes no longer charge the budget).

### 1.5 Tuition governor (runaway brake — bound, not estimator)

State: deque of `(close_ts, clipped_loss_usd)` for probe-tagged position closes, hooked at the `_finalize_position` seam where `pos.is_probe`/net PnL are both in scope (main.py:1400-1518 class — note: C1's cited "close path main.py:1518" is the labeler call site, not a settlement hook; the finalize seam is the real one). Pruned to trailing 86400 engine-seconds at read, never latched.

```
cap_usd      = tuition_daily_frac_max × ledger_equity(now)          [0.001 × $4,965 ≈ $4.97/day; same deterministic paper-ledger equity the entry path already passes to orders.submit, main.py:3717]
clip_usd     = cap_usd / outlier_clip_div                            [÷3 ≈ $1.66: no SINGLE probe may contribute more than a third of the day's cap — 3 = 24h/drought_hours, the system's guaranteed floor pace; one probe is never evidence (small-n law), three of the worst class is a regression]
X            = Σ min(max(0, −pnl_i), clip_usd) over trailing 24h
f_governor   = 1                      if X ≤ cap_usd
             = clip(cap_usd / X, F, 1) otherwise                     [scale-with-floor, self-redeeming as the window rolls; F reuses floor_frac — probation, never a life sentence]
```

Transitions (f crossing 1.0 either way) emit SZ-053. The window is 86400 s by definition of the daily budget's own unit — deliberately NOT a knob.

### 1.6 Wilson-UPPER surcharge — ships DARK (`surcharge.enabled: false`)

The sole permitted win-rate term (all three judges), C1's formulation: with era-filtered post-PT-060 probe outcomes `(wins_a, m_a)` and contemporaneous Laplace base `b = (W+1)/(N+2)` over the trailing `base_window` live labels:

```
wr_ub(a)     = Wilson 95% UPPER bound(wins_a, m_a, z = wilson_z)     [m_a = 0 → ub = 1: small-n honesty by construction]
surcharge(a) = 1 + (max_surcharge − 1) × max(0, b − wr_ub(a)) / b    ∈ [1, max_surcharge]
```

Fires only on proven-worse-than-base at 95% (0/18 LINK: ub 0.176 > 0.157 → surcharge 1.0; first bite ~0/21) — never mutes noise-compatible small-n, never C2's LCB. Flip preconditions: (a) the era-filtered accessor `asset_live_outcomes(min_ts)` exists with `era_min_ts` set to the PT-060 deploy epoch (FATAL if enabled while null); (b) scarcity-only has been raced and beaten out-of-sample on the simplicity ladder (OF-4 discipline, C3's pattern). C3's model-uncertainty term is dropped entirely (unverified citation; the surcharge occupies the one dark slot).

---

## 2. Config schema (`config.json → ml.exploration.admission`) + guard bounds

```jsonc
"admission": {
  "mode": "share_cap",              // ESCAPE HATCH + merge default. "share_cap" = shipped SZ-047 deque path
                                    // byte-identical (test-pinned); "budget" = SPB-R. Flip is a conscious
                                    // operator config change via the git remote-control plane.
  "budget": {
    "tokens_per_day": 15,           // THE primary knob. Derived from existing config structure, not measured
                                    // performance: book label throughput ceiling = capital_management.
                                    // max_concurrent_positions (5, config.json:178) × 24h / 8h label horizon
                                    // (ml.label_max_bars 96 × 5m bars, config.json:528). Budget above this
                                    // buys tokens the book cannot convert. Honest name: tokens, not labels —
                                    // realized labels/day ≈ tokens_per_day / avg_cost (§6).
    "burst_hours": 8.0,             // capacity window = the labeler's own horizon (label_max_bars × 5m = 8h);
                                    // C = 5 tokens = exactly one book-fill max burst.
    "scarcity_pricing": true,       // false = flat cost 1.0 — the 1-knob rule, kept as a REAL config point
                                    // so the simplicity ladder can be run against pricing honestly.
    "scarcity_floor": null,         // null = reuse ml.exploration.corpus_decay.floor_frac (0.25):
                                    // ONE trickle-floor concept in the whole file, not two.
    "refund_unfilled_entry": true,  // §1.4; refund keyed to order.meta, bounded by OM's 25s timeout.
    "governor": {
      "tuition_daily_frac_max": 0.001,  // 10 bps equity/day. Circuit-breaker BOUND, not an estimator
                                        // (same class as SZ-046's "4 consecutive"): ≥2× headroom above the
                                        // worst-case default spend (§6) and ~5× below the pre-fix 2026-07-23
                                        // bleed rate the old cap was built for.
      "outlier_clip_div": 3             // = 24 / drought_floor.drought_hours: the floor pace — the governor
                                        // may never engage on fewer probes than the system's guaranteed
                                        // daily floor admits (one probe is never evidence).
    },
    "surcharge": {
      "enabled": false,             // DARK. Flip gated on the simplicity-ladder race (§1.6).
      "wilson_z": 1.96,             // standard 95% bound — mandated by the small-n stats law, not tuned
                                    // (C2's z=1.0 was tuned-to-bite and is rejected, §10).
      "max_surcharge": 2.0,         // surcharge may at most double a price; combined price is clamped at C
                                    // in code regardless, so no setting can create an unaffordable arm.
      "base_window_labels": null,   // null = reuse corpus_target_live (300): the base is measured over the
                                    // corpus target's own scale (kills C1's free "200" literal).
      "era_min_ts": null            // epoch s of the PT-060 deploy; REQUIRED when enabled.
    }
  }
}
```

`core/config_guard.py` (extend the existing exploration block):

- FATAL: `mode` not in `{share_cap, budget}`.
- FATAL: `tokens_per_day` outside (0, 100]. WARN: > `max_concurrent_positions × 24/burst_hours` (exceeds book conversion ceiling — cross-read from capital_management). WARN: < `24/drought_floor.drought_hours` (= 3/day: the SZ-048 backstop would out-rate the budget — the floor must be the exception, never the governor; C2's cross-guard, adopted verbatim).
- FATAL: `burst_hours` outside [1, 24]. WARN: ≠ `label_max_bars × bar_minutes / 60` (capacity should mirror the labeler's horizon).
- FATAL: `scarcity_floor` set and outside (0, 1].
- FATAL: `tuition_daily_frac_max` outside (0, 0.005]; WARN > 0.002. FATAL: `outlier_clip_div` outside [1, 10]; WARN ≠ round(24/drought_hours).
- FATAL: `wilson_z` outside [1, 3]; `max_surcharge` outside [1, 1/floor_frac]; `surcharge.enabled` true while `era_min_ts` null.
- WARN: `mode="budget"` while `ml.exploration.enabled` false (dead config).
- (C2's "FATAL zero-quota" is structurally moot — refill is continuous, there is no integer quota to round to 0 — noted in the guard comment.)

---

## 3. Composition with the layers that stay

Pipeline order, everything except the boxed step verbatim:

1. `dry_run` hard gate, `explore_enabled`, graduation at `until_live_rows=1200` — untouched (exploration never influences a live order).
2. `_exploration_active` (main.py:2593): epsilon 0.5 × corpus decay (currently 1.0) × regime-coverage HOLD × per-asset label-share TAPER — **untouched, byte-identical, same `_explore_rng` draw count in both modes**. This remains the demand side ("is a probe wanted").
3. **`_probe_admission_decision` (main.py:2735): in `mode="budget"` the `_probe_share_would_deny()` branch is replaced by refill → price → probabilistic-affordability roll (§1.2-1.3).** Conviction entries remain untouched — the method still takes no p_win/size argument (pinned invariant, tests/test_probe_throttle.py).
4. SZ-048 drought floor — **verbatim**, still keyed on `_last_entry_admit_ts`; in budget mode it should never fire and becomes the livelock CANARY (alert, §8).
5. Downstream unchanged: aggressive sub-lane roll (15%, main.py:3374-3381, after admission), manip veto/downsize-with-$15-withhold, `floor_to_min`, SZ-046 breaker, full risk stack, pretrade, ML-071/ML-073. **None of these consume budget** — vetoes never reach the placement hook, unfilled entries refund (§1.4).

Interaction notes: (a) regime HOLD boosts *demand* in uncovered regimes while `w_regime` makes the same probes *cheap* — same direction, no fight; (b) the asset taper (all-labeled-rows share, hard variety pressure) and `w_asset` (live-label scarcity) overlap on ETH/BTC by design — both floored, combined drag can never reach zero; per the stats judge's note, the combined per-asset drag is exported as ONE number: `eff_weight(a) = taper_pass_prob(a) × S(a,r) ` normalized, in status (§8) — never two invisible multiplications; (c) `_record_probe_admission` continues feeding the legacy deque in BOTH modes (cheap), so a rollback to `share_cap` resumes with a warm window — stateful rollback (C3, judges endorsed); (d) the corpus decay reduces demand as live 255→300+; the bucket caps supply; hard-off at 1200 unchanged.

---

## 4. Reason codes (`core/codes.py`, SZ family)

Candidates' SZ-050 assignments collide with shipped `SZ_DD_THROTTLE` (codes.py:138 — verified). Free slots used: 049, 051, 052, 053.

| Code | Name | Semantics | Volume |
|---|---|---|---|
| SZ-049 | `SZ_PROBE_BUDGET_EXHAUSTED` | TRANSITION pair: bucket crosses into (`engaged`) / out of (`released`) the `tokens ≤ 0` state. `released` payload carries `{arrivals_denied, span_s, tokens}` so the audit trail brackets and COUNTS every denied arrival without per-event spam. | ~2×/admission, ~25/day |
| SZ-051 | `SZ_PROBE_PRICED` | Informational, attached beside the existing `ML_EXPLORATION`/`ML_EXPLORE_AGGRESSIVE` admission record on every budget-mode ADMIT: `{asset, regime, cost, w_asset, w_regime, surcharge, p, u, tokens_before, tokens_after}`. | ~12/day |
| SZ-052 | `SZ_PROBE_REFUND` | Informational: unfilled probe entry terminal, tokens refunded: `{asset, cost_refunded, tokens_after}`. | ≤ admits/day |
| SZ-053 | `SZ_PROBE_TUITION_GOVERNOR` | TRANSITION only: governor factor engaged/updated/released: `{tuition_24h_usd, cap_usd, factor}`. | rare |
| SZ-047 | `SZ_PROBE_THROTTLED` | Retained-registered; fires ONLY in `mode="share_cap"` (codes are never deleted). | legacy |
| SZ-048 | `SZ_PROBE_FLOOR` | Unchanged in both modes. | canary |

**Conscious semantic change (stated per CLAUDE.md):** in budget mode a failed admission roll is a NON-disposition — identical to a failed epsilon or taper roll today, which emits nothing (verified main.py:2647, 2662). The SZ-047 practice of per-event denial audit produced the measured 1,517-events/12h storm; SPB-R replaces it with aggregate counters (status, every cycle) + SZ-049 transition brackets carrying exact denied counts — audit information content is preserved, hash-chained volume drops ~100×. The escape hatch preserves SZ-047 per-event semantics verbatim for anyone who wants them back.

---

## 5. Persistence & determinism (MANDATORY, not "recommended")

New snapshot section `probe_budget` = `{tokens, tuition: [[close_ts, clipped_loss], ...]}`, written beside `probe_admissions` (persistence.py:460) and restored by a new isolated `_restore_probe_budget_section` mirroring `_restore_probe_admissions_section` (persistence.py:182-223 — verified pattern). The auto-updater restarts the bot on EVERY deploy (persistence.py:454-458 — verified), so unpersisted state would reset per-deploy; this is why persistence is mandatory here. `last_refill_ts` is NOT persisted: it re-seeds to the first engine `now` after restart, so **downtime never accrues tokens** — degraded toward FEWER probes, the safe direction (the old deque's restart asymmetry was permissive; ours is conservative — documented). Missing/pre-SPB section → empty bucket, refills normally. Order-terminal refunds need no persistence: the cost rides in `order.meta`, and OM state has its own lifecycle. Determinism: engine `now` only; the dedicated `_budget_rng` is seeded from `system.seed` exactly like `_explore_rng` (main.py:899); ledger equity is engine state; replay from clean state under injected feeds is bit-for-bit, and legacy mode is byte-identical including RNG stream draw counts.

---

## 6. Expected label rate at defaults (book-ceiling-honest)

- Demand: 1,517 SZ-047 denials/12h ⇒ ~3,000 post-epsilon probe-wanted arrivals/day ≫ supply. Budget binds.
- Admitted mix under cost-proportional thinning (`∝ λ_a/cost_a`), arrivals ≈ historical mix (52% ETH+BTC): ETH share (0.26/1.79)=0.145, BTC (0.26/1.64)=0.159, others (0.48/1.0)=0.480 → normalized 18.5% / 20.2% / 61.2%. **Avg cost = 0.185×1.79 + 0.202×1.64 + 0.612×1.0 ≈ 1.27.**
- Every deducted token corresponds to a FILLED probe (vetoes cost nothing; unfilled refund): **filled probes/day ≈ 15 / 1.27 ≈ 11.8**, regardless of fill attrition.
- ML-073 realizes every filled probe ≤ 8h ⇒ **≈ 11-12 live labels/day** (worst case, all arms at max price 4: 15/4 ≈ 3.75/day — still above today's ~3/day floor pace, as the FLOOR not the ceiling; if the regime leaves 'range', all costs → 1.0 and rate → 15/day = the book ceiling exactly).
- Book coherence: 11.8 labels/day × 8h/24h ≈ **3.9 avg concurrent probes ≤ 5 slots** ✓ (slot contention with returning conviction flow surfaces via telemetry WARN, §8).
- Milestones: **60 tb-era labels in 60/11.8 ≈ 5-6 days** (vs ~20 days at the current 1-per-8h); corpus 255→300 in ≈ 4 days; graduation (1200−255)/11.8 ≈ 80 days of bounded-tuition accrual.
- Tuition: 11.8 × $0.03-0.25 = **$0.35-2.95/day = 0.7-5.9 bps of $4,965** — inside the 10 bps governor cap with ≥ 1.7× headroom even at the worst measured class.

---

## 7. Failure-mode analysis

- **Livelock (the twice-learned lesson):** structurally impossible — refill is monotone in engine time; no admission-count denominator exists anywhere; `p > 0` whenever `tokens > 0`; every factor floored (S ≥ F, governor ≥ F, price ≤ C); refunds only ADD tokens; SZ-048 retained as an independent backstop and alert-wired canary. The original defect (deque frozen by zero conviction flow) cannot recur: nothing depends on conviction flow.
- **Runaway spend:** hard ceiling `tokens_per_day`/day; burst ≤ C = one book-fill; governor scales refill on realized clipped tuition (floored, unlatched, self-redeeming); SZ-046 and manip unchanged; worst notional churn 15 × $15 = $225/day, paper, dry-run invariant untouched. Failure direction is always fewer probes, never more money.
- **Debt windows:** deduction from `tokens > 0` with `cost ≤ C` bounds debt at −C (5 tokens = 8h refill worst; ≤ 1.95 ≈ 3.1h typical today). While in debt, p = 0 (that IS the pacing) — bracketed by SZ-049, counted, invisible to the human log.
- **Corpus poisoning:** probes only ride CONFIRMED signals (the unbiased-sample property, main.py:3395-3400, preserved — pricing admits/declines arrivals, never fabricates entries); floors keep majors flowing; refund + veto-costs-nothing removes the failure judge's mix-bias channel (budget can no longer be charged for thin-alt labels never bought); regimes are exogenous — pricing can only stop over-paying for range redundancy; label-mix and base-drift panels are the tripwires.
- **Governor over-brake:** per-close clip at cap/3 means one −$5 outlier contributes ≤ $1.66 and cannot engage the governor alone (repairs C3-fixable-3); worst over-brake = floor 0.25 for ≤ 24h, self-redeeming.
- **Replay/restart:** §5. Stale cached counts: (mtime,size)-gated accessors (existing pattern) — a few probes priced on slightly stale n, bounded and self-correcting.
- **Refund abuse/leak:** cost rides in `order.meta`; OM terminates every order (25s timeout, ≤1 reprice, 60s deadman — verified); refund capped at C by the bucket clamp; partial fills never refund.
- **Surcharge misuse:** dark by default; FATAL-guarded era requirement; price clamp at C makes even a misconfigured surcharge unable to create an unaffordable arm.

---

## 8. Telemetry

`status.json` — extend the load-bearing `ml` block (extend, never break): `ml.probe_budget = { mode, tokens, capacity, refill_per_day, governor_factor, tuition_24h_usd, tuition_cap_usd, admits_24h, refunds_24h, denied_exhausted_24h, rolls_failed_24h, avg_cost_24h, labels_24h, live_labels_per_day_7d, tb_era_labels, unlock_eta_days (= max(0, 60−tb_era)/max(labels_24h,1)), avg_concurrent_probes, per_asset: {a: {n_live, w_asset, cost, eff_weight}}, per_regime_live: {r: n} }` — written by the runner's StatusWriter from engine state, exported by gc_pusher.

Grafana (Models·Inv·Exec board, existing design system + decode layer; replace the SZ-047 panels): (1) token-bucket level timeseries with capacity band and debt shading — health at a glance; (2) **live labels/day sparkline with the 15/day book-ceiling line and 300/1200 milestone annotations — the program's headline number** + `unlock_eta_days` stat tile; (3) admits/day + refunds/day vs target; (4) avg admission cost timeseries (drift → 1.0 = buying scarce labels; → 4 = only redundant arms arriving); (5) per-asset `eff_weight` heatmap (the single combined-drag number — taper × scarcity, per stats-judge note); (6) per-regime live-label bars vs the 60 line; (7) tuition gauge: trailing-24h USD vs cap, `governor_factor` beside it; (8) label mix stacked by asset and regime + contemporaneous base-rate drift line (poisoning tripwires); (9) SZ-049/052/053 rates + legacy SZ-047 during rollout. Alerts: `admits_24h == 0` in budget mode (livelock canary — should be impossible); ANY SZ-048 in budget mode; `governor_factor < 1` sustained > 24h; `avg_concurrent_probes > 4` (slot-contention pressure).

---

## 9. Migration / rollout

**Stage 0 — land dark (behavior-preserving):** ship with `mode:"share_cap"`; legacy path byte-identical, `tests/test_probe_throttle.py` untouched-green. Same commit: `tests/test_probe_budget.py` — pricing table (§1.1 worked numbers as fixtures), refill/clamp/debt-floor math, probabilistic-admit determinism under fixed `_budget_rng`, stash/veto-costs-nothing, refund round-trip via simulated unfilled terminal, governor clip/engage/release/redeem, snapshot round-trip incl. missing-section, legacy-mode byte-identity **including `_explore_rng` draw-count preservation**, SZ-048 reachability under budget non-admit. File map: `core/codes.py` (4 codes), `config.json`, `core/config_guard.py`, `ml/history.py` (`asset_live_counts()`, (mtime,size)-cached like `regime_live_count`), `main.py` (decision branch, `_record_probe_admission(is_probe, cost=None)`, refund seam, finalize-seam governor feed), `core/persistence.py` (section + isolated restore), runner StatusWriter, `scripts/build_trading_dashboard.py` + board JSONs. Full CLAUDE.md battery before the zip: pytest · smoke · assurance · overfit · ruff · pyright (zero-error ratchet) · bandit · compileall · import-integrity · `.\test_windows.bat`.

**Stage 1 — conscious flip:** operator sets `mode:"budget"` via the git remote-control plane + restart. 48h watch: admits/day ≈ 10-12, refund rate, tuition ≪ cap, SZ-048 silent, no SZ-046 clustering, avg_concurrent_probes ≤ 4.

**Stage 2:** legacy share-cap code, keys, and deque-feeding stay in place until graduation (1200); retirement is a separate later cleanup. Rollback = one config key + restart, resuming a WARM deque (fed in both modes).

**Re-baselines (adjudicated, per CLAUDE.md):** quant-trials G1-G5 should NOT move (exploration is dry-run-only, outside the trial sims) — re-run at 200×1200 to confirm; if anything moves, STOP and adjudicate, never widen a gate. `overfit_check`'s standing learning-curve instrument (task #135) WILL see faster label flow — re-baseline its expectations consciously and record why (C3's honesty, endorsed by the discipline judge; C1/C2's "untouched" claims were wrong here). smoke/assurance expectations referencing SZ-047 rates → update to SZ-049/051. Status schema extended, never broken.

---

## 10. WHAT WE REJECTED

| # | Dropped idea | Killed by | Why |
|---|---|---|---|
| 1 | C1's USD reservation held to position close (settle-at-close) | failure judge (FATAL) | Unfilled limit entries create no position and no close path — each leaks its reservation forever; ~29 leaks pin Gate A = the frozen denominator rebuilt in USD. Also C1's cited close hook (main.py:1518) is the labeler call site, not a settlement seam — verified. Replaced by placement-deduct + order-terminal refund (§1.4). |
| 2 | C1's three-gate design (USD bucket + count bucket + allocation roll, ~14 knobs) | discipline judge | No simplicity-ladder comparison; cheapness term inert at all current data; `labels_per_day_target` decorative (appears in no predicate). |
| 3 | C1's `bps_per_day` refill keyed to equity with today's $4,965 baked into the derivation | discipline judge | Disguised fit to current equity; silently rots as equity moves. Refill is token-denominated, derived from config structure only. |
| 4 | C1's 25-48 labels/day and C2's 17/day headlines | all three judges | Physically exceed the book's 15/day conversion ceiling (5 slots × 24h/8h — both constants verified config.json:178,528). All rate claims here are ceiling-capped (§6). |
| 5 | C2's `cost_a` = Wilson-LCB(z=1)/base mute | stats judge (FATAL) | LCB ≡ 0 for any 0-win asset at any n (no rank order); floor-mutes noise-compatible 0/12-class assets (P=0.13 under base); net weights steer TOWARD ETH/BTC — inverts the information objective. THALES A-1 in ratio form. |
| 6 | C2's `wilson_z: 1.0` | stats judge | A statistical constant tuned so the term "does something" at today's n — fit-adjacent. The only permitted win-rate term is the UPPER-bound surcharge at z=1.96 (§1.6). |
| 7 | C2's `burst_window_hours: 1.0` (from "126/h in the 12h audit") | discipline judge | The most fitted-looking literal in any schema — one 12h observation window. Burst capacity here reuses the 8h label horizon. |
| 8 | C2's `cost_min_n: 5` ("one more than the breaker's 4") | stats judge | Rationalization, not derivation — streak tests and proportion tests are different objects. No such knob survives. |
| 9 | C3's strict `tokens ≥ cost` admission | failure judge | Greedy-queue starvation: cheap arrivals strip the bucket at 1.0 and high-cost arms never afford — a de-facto wall (the taper lesson). Replaced by probabilistic affordability (§1.3). |
| 10 | C3's no-refund decision-time burn | all three judges | Charges budget for manip-withheld/unfilled probes; biases realized mix toward majors. Replaced by §1.4. |
| 11 | C3's model-uncertainty multiplier | (C3's own flag + judges' endorsement) | Unverified citation; dropped entirely rather than kept dark — the surcharge (§1.6) is the one dark slot and has verified statistics. |
| 12 | Per-event denial audit (SZ-047 practice; C1's per-roll SZ-052; C3's per-event SZ-051) | discipline judge + measured 1,517/12h storm | Failed rolls are non-dispositions in shipped practice (verified: epsilon/taper rolls emit nothing). Transition brackets carry the counts (§4) — conscious, documented semantic change; escape hatch preserves the old semantics. |
| 13 | Candidates' SZ-050 code assignments | this synthesis (verification) | SZ-050 is shipped `SZ_DD_THROTTLE` (codes.py:138). Renumbered 049/051/052/053. |
| 14 | C1's `base_window_labels: 200` | stats judge | Unjustified free literal → `null` reuses `corpus_target_live`. |

**R1 — Explicit refutation (refunds, vs the failure judge):** the failure judge preferred "record-at-placement *without* refund complexity," ranking any refund machinery near C1's leak class. That concern is refuted by code: C1's leak was POSITION-close-keyed (unbounded wait); this refund is ORDER-terminal-keyed, and OrderManager terminates every entry within `order_timeout_sec = 25s` (+ ≤ 1 reprice, 60s deadman — execution/order_manager.py:130-136, 943, 1149). The cost travels in `order.meta`, so there is no side-table to orphan and nothing that can wait forever. Without the refund, unfilled-entry attrition (unknown, possibly 20-30% per the same judge) silently taxes the label rate the whole program is bound by; with it, the budget provably converts to filled probes = labels. Bounded by construction, one field + one seam — kept, default true.

**Verified-line appendix (claims this design depends on):** main.py:2593/2635-2669 (epsilon/decay/hold/taper), 2672-2707 (SZ-048, engine-now), 2709-2733 (share cap + deque), 2735-2816 (decision site, SZ-047 per-event + 10-min log hygiene), 3364/3705/3734 (decision→submit→record sequence), 899 (`_explore_rng` seeding), 3395-3400 (unbiased sample), 1201-1225 (order-meta probe seam); config.json:178 (5 slots), 404 ($15), 528 (96 bars), 548-592 (exploration block: ε 0.5, until 1200, share 0.5, cap 0.35/40, drought 8h, corpus 300/0.25/60); core/persistence.py:182-223 (isolated restore), 454-471 (deploy-restart persistence rationale); ml/history.py:1018-1051/1053-1059/1100-1106 (source/asset/regime accessors + caching); execution/order_manager.py:130-136/943/1149 (25s timeout, 1 reprice, deadman, sim timeout); core/codes.py:112-141 (SZ registry; 049/051-053 free, 050 taken).