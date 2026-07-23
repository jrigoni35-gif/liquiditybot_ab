"""
core/config_guard.py

Startup config validation. The most likely catastrophic failure in a
mature system is not a bug - it is an operator editing config.json at
2am. This module checks the invariants that the rest of the system
silently assumes, and refuses to start live trading on a config that
violates them. In dry-run, violations warn instead of block (paper is
for finding exactly these mistakes).

Checks (each maps to a real historical failure mode somewhere):
  * fees vs Kraken's public floor - understating your fee tier makes
    the pre-trade edge gate approve trades that are net losers.
    Kraken spot bottom tier is 25 bps maker / 40 bps taker; a config
    below that is almost certainly wrong unless explicitly overridden.
  * fee consistency - pretrade and order_manager carry independent fee
    settings; if they drift apart, the gate and the PnL ledger disagree.
  * risk ladder ordering - daily_loss_limit < hard_stop_drawdown,
    soft inventory cap < hard cap, tier triggers strictly increasing,
    tier close percentages <= 100 total.
  * live capital - starting_capital_usd must be > 0 in live mode. The
    silent "0 means 10k paper default" behavior is dry-run only.
  * bounds - polling interval, slippage, leverage caps, stop widths
    all positive and sane.

Returns a list of (severity, message); severity is "FATAL" or "WARN".
`enforce()` raises ConfigError on any FATAL when live.
"""

import logging
from typing import Any

log = logging.getLogger("liquiditybot.core.config_guard")

# Kraken spot public schedule, bottom tier (highest fees). If the
# configured fees are below this, the operator either has real volume
# tier discounts (set allow_sub_floor_fees) or has misconfigured.
KRAKEN_SPOT_FLOOR_MAKER_BPS = 25.0
KRAKEN_SPOT_FLOOR_TAKER_BPS = 40.0


class ConfigError(RuntimeError):
    pass


def _f(cfg: dict, path: str, default: Any = None) -> Any:
    """Walk a dotted path through arbitrary JSON. Returns `default` on
    any missing segment. Return type is Any because config values can
    legitimately be any JSON scalar or nested structure; callers cast
    (float/bool/int) at the site where they know what they expect."""
    cur: Any = cfg
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def validate(config: dict) -> list:
    """Pure check: returns [(severity, message), ...]. No side effects."""
    findings = []
    fatal = lambda m: findings.append(("FATAL", m))       # noqa: E731

    # ---- rev-4: execution-routing invariant ---------------------------
    eligible = [str(v).lower() for v in (config.get("execution", {})
                .get("routing", {}).get("eligible_venues", ["kraken"]))]
    rogue = [v for v in eligible if v != "kraken"]
    if rogue:
        fatal(f"execution.routing.eligible_venues contains {rogue} — "
              f"Kraken is the sole execution venue by invariant; other "
              f"venues are read-only data sources. Remove them (routing "
              f"scores them for the audit trail regardless).")
    # any non-kraken venue adapter flipped enabled is a live-config FATAL:
    # the adapter layer refuses to execute on it, but an enabled disabled-
    # adapter signals intent that must not reach live silently.
    venues_cfg = config.get("execution", {}).get("venues", {}) or {}
    enabled_rogue = [name for name, v in venues_cfg.items()
                     if isinstance(v, dict) and name != "kraken"
                     and v.get("enabled")]
    if enabled_rogue:
        fatal(f"execution.venues has non-kraken adapters enabled "
              f"{enabled_rogue} — Kraken is the sole execution venue. These "
              f"adapters cannot execute (VenueNotEnabled) and must not be "
              f"enabled in a live config until onboarded and re-reviewed.")
    algos_cfg = config.get("execution", {}).get("algos", {})
    if algos_cfg.get("enabled") and \
            float(algos_cfg.get("min_interval_sec", 30)) < 15:
        fatal("execution.algos.min_interval_sec < 15s would collide with "
              "the risk-firewall per-minute order budget (FW-020); child "
              "slices must pace slower than the budget refills.")

    warn = lambda m: findings.append(("WARN", m))         # noqa: E731
    # ADVISORY: a config-coherence/hygiene note where the bot still trades
    # correctly (e.g. a phantom knob whose effective value differs). Logged at
    # INFO by enforce(), so it stays OFF the WARNING+ incidents stream - a
    # WARN there should mean a real operational concern, not a cosmetic note.
    advisory = lambda m: findings.append(("ADVISORY", m))  # noqa: E731

    dry_run = bool(_f(config, "system.dry_run", True))

    # --- fees ----------------------------------------------------------
    # defaults mirror the read-sites' shipped values (execution/pretrade.py,
    # execution/order_manager.py both default 25/40 bps) - a stale 16/26
    # fallback here would silently pass a config that DELETED the fee keys
    # even though the modules it validates against actually run at 25/40.
    pt_maker = float(_f(config, "pretrade.maker_fee_bps", 25.0))
    pt_taker = float(_f(config, "pretrade.taker_fee_bps", 40.0))
    om_maker = float(_f(config, "order_manager.maker_fee_bps", 25.0))
    om_taker = float(_f(config, "order_manager.taker_fee_bps", 40.0))
    allow_low = bool(_f(config, "pretrade.allow_sub_floor_fees", False))

    if min(pt_maker, pt_taker, om_maker, om_taker) < 0:
        fatal("negative fee configured")
    if abs(pt_maker - om_maker) > 1e-9 or abs(pt_taker - om_taker) > 1e-9:
        fatal(f"fee mismatch: pretrade ({pt_maker}/{pt_taker}) != "
              f"order_manager ({om_maker}/{om_taker}) - the edge gate and "
              f"the PnL ledger would disagree about costs")
    if not allow_low and (pt_maker < KRAKEN_SPOT_FLOOR_MAKER_BPS
                          or pt_taker < KRAKEN_SPOT_FLOOR_TAKER_BPS):
        msg = (f"configured fees {pt_maker:.0f}/{pt_taker:.0f} bps are below "
               f"Kraken's public spot floor "
               f"{KRAKEN_SPOT_FLOOR_MAKER_BPS:.0f}/"
               f"{KRAKEN_SPOT_FLOOR_TAKER_BPS:.0f} bps. Understated fees make "
               f"the pre-trade gate approve net-losing trades. Set your real "
               f"tier, or set pretrade.allow_sub_floor_fees=true if you "
               f"genuinely have volume discounts.")
        (fatal if not dry_run else warn)(msg)
    if pt_taker < pt_maker:
        warn("taker fee below maker fee - unusual; double-check the tier")

    # --- pretrade EV gate / participation clamp / staleness ----------------
    # min_edge_cost_ratio gates PT-041 as `edge < ratio * cost`; edge is a
    # sum of two max(., 0) terms so it is never negative, meaning ratio=0
    # makes `edge < 0` impossible and the entire edge-vs-cost gate silently
    # never fires. max_participation_of_depth=0 doesn't veto - it makes
    # max_units = depth_units * 0 = 0, which SKIPS the clamp on a size that
    # sizes to zero rather than blocking the order, the opposite of caution.
    pt_ratio = float(_f(config, "pretrade.min_edge_cost_ratio", 1.3))
    if pt_ratio < 1.0:
        fatal(f"pretrade.min_edge_cost_ratio={pt_ratio} must be >= 1 - below "
              f"1x the edge/cost gate (PT-041) can approve trades whose "
              f"edge doesn't even cover cost, and at 0 the gate never fires "
              f"at all (edge is a sum of max(.,0) terms, never negative)")
    pt_part = float(_f(config, "pretrade.max_participation_of_depth", 0.15))
    if not (0.0 < pt_part <= 1.0):
        fatal(f"pretrade.max_participation_of_depth={pt_part} must be in "
              f"(0, 1] - 0 zeroes the depth-participation clamp itself "
              f"(silently sizing to zero instead of blocking), and >1 is "
              f"not a fraction of depth")
    pt_stale = float(_f(config, "pretrade.max_data_staleness_ms", 4000.0))
    if pt_stale <= 0:
        fatal(f"pretrade.max_data_staleness_ms={pt_stale} must be positive "
              f"- a non-positive staleness gate rejects every quote as "
              f"stale (or trusts a permanently dead one, at exactly 0)")
    pt_impact_eta = float(_f(config, "pretrade.impact_eta", 0.8))
    if pt_impact_eta < 0:
        fatal(f"pretrade.impact_eta={pt_impact_eta} must be >= 0 - it "
              f"scales the market-impact cost term; negative would PAY the "
              f"entry for taking liquidity")

    # label cost coherence: the triple-barrier win/loss label subtracts a
    # round-trip cost. If it sits below the maker round-trip, labels call
    # net-losing trades "wins" and teach the meta-model to take them - the
    # label proxy diverges from realized profitability.
    label_cost = float(_f(config, "ml.label_round_trip_cost_pct", 0.5))
    maker_rt_pct = 2.0 * pt_maker / 100.0
    if label_cost + 1e-9 < maker_rt_pct:
        warn(f"ml.label_round_trip_cost_pct={label_cost:.2f}% is below the "
             f"maker round-trip {maker_rt_pct:.2f}% ({pt_maker:.0f}bps x2) - "
             f"triple-barrier labels understate cost and will mislabel "
             f"net-losing trades as wins, biasing the model to overtrade")
    if float(_f(config, "ml.label_spread_cap_bps", 60.0)) < 0:
        fatal("ml.label_spread_cap_bps must be >= 0")
    sgf = float(_f(config, "ml.postmortem.stop_gap_factor", 2.0))
    if sgf <= 1.0:
        fatal(f"ml.postmortem.stop_gap_factor={sgf} must be > 1.0 - at or "
              f"below 1x every ordinary slippage-past-stop fill becomes an "
              f"'ops failure' and the cost/whipsaw governors go blind to "
              f"real execution problems")
    elif sgf > 5.0:
        warn(f"ml.postmortem.stop_gap_factor={sgf} above 5x will almost "
             f"never fire - unenforced-stop losses will keep polluting the "
             f"cost governor (the 2026-07-14 failure this knob exists for)")

    # multi-horizon shadow: every horizon must be a positive integer no
    # larger than the primary label horizon, or its outcome would never be
    # ready when the primary label fires (the shadow row would be silently
    # dropped, defeating the whole point of collecting the evidence)
    mh = config.get("ml", {}).get("multi_horizon", {}) or {}
    if mh.get("enabled", False):
        max_bars = int(_f(config, "ml.label_max_bars", 96))
        horizons = mh.get("horizons_bars", [])
        if not horizons:
            fatal("ml.multi_horizon.enabled but horizons_bars is empty")
        for h in horizons:
            if not isinstance(h, (int, float)) or int(h) <= 0:
                fatal(f"ml.multi_horizon.horizons_bars has non-positive {h!r}")
            elif int(h) > max_bars:
                fatal(f"ml.multi_horizon horizon {int(h)} > label_max_bars "
                      f"{max_bars} - would never be labeled")

    # State-Change Sampler: cusum_k is the sigma-multiple event threshold.
    # Below 1 sigma nearly every bar triggers - clock sampling by another
    # name, defeating the filter; above 6 events all but vanish and the
    # candidate corpus starves. Calibrated plateau is k in [1,4]; the
    # bound leaves headroom without allowing a self-defeating config.
    smp = config.get("ml", {}).get("sampling", {}) or {}
    if smp.get("cusum_enabled", False):
        cusum_k = float(smp.get("cusum_k", 3.0))
        if not (1.0 <= cusum_k <= 6.0):
            fatal(f"ml.sampling.cusum_k={cusum_k} outside [1.0, 6.0] - "
                  f"below 1 sigma the event filter degenerates to clock "
                  f"sampling (defeats the uniqueness win); above 6 it "
                  f"starves the training corpus")

    # adaptive_gbt (opt-in top ladder rung): bounds so an enabled config
    # can't degrade the learner. max_total_trees must sit comfortably above
    # a base GBT fit (~n_estimators, default 300) or warm_update would find
    # no room and continuous learning would silently never fire.
    ag = config.get("ml", {}).get("adaptive_gbt", {}) or {}
    if ag.get("enabled", False):
        bags = int(_f(config, "ml.adaptive_gbt.bags", 4))
        if not (1 <= bags <= 16):
            fatal(f"ml.adaptive_gbt.bags ({bags}) must be in [1, 16] - one "
                  f"bag is a plain gbt with overhead; >16 just burns train "
                  f"time for vanishing variance reduction")
        warm = int(_f(config, "ml.adaptive_gbt.warm_rounds", 25))
        if not (1 <= warm <= 200):
            fatal(f"ml.adaptive_gbt.warm_rounds ({warm}) must be in [1, 200] "
                  f"- <1 disables continuous learning, >200 lets one warm "
                  f"batch dominate the trained ensemble")
        cap = int(_f(config, "ml.adaptive_gbt.max_total_trees", 800))
        if cap < 400:
            fatal(f"ml.adaptive_gbt.max_total_trees ({cap}) must be >= 400 - "
                  f"below a base fit's ~300 trees, warm_update never has room "
                  f"and continuous learning silently never fires")

    # model-selection evidence gate: floors must be coherent or the ladder
    # admits complexity out of order (train adaptive_gbt but not gbt) or a
    # family enters selection on fewer TOTAL rows than the LIVE floor it just
    # cleared. Complexity order fixed: gbt <= blend <= mlp <= adaptive_gbt.
    ms = config.get("ml", {}).get("model_selection", {}) or {}
    if ms.get("enabled", False):
        _order = ("gbt", "blend", "mlp", "adaptive_gbt")
        for _key in ("min_live_rows", "min_total_rows"):
            floors = ms.get(_key, {}) or {}
            prev, prev_fam = -1, None
            for fam in _order:
                if fam not in floors:
                    continue
                val = int(floors[fam])
                if val < 0:
                    fatal(f"ml.model_selection.{_key}.{fam} ({val}) must be "
                          f">= 0")
                if val < prev:
                    fatal(f"ml.model_selection.{_key} non-monotonic: {fam}="
                          f"{val} < {prev_fam}={prev} - a more complex family "
                          f"would be admitted on LESS evidence than a simpler "
                          f"one, so the ladder could train {fam} but not "
                          f"{prev_fam}")
                prev, prev_fam = val, fam
        live_f = ms.get("min_live_rows", {}) or {}
        total_f = ms.get("min_total_rows", {}) or {}
        for fam in _order:
            if fam in live_f and fam in total_f and \
                    int(total_f[fam]) < int(live_f[fam]):
                fatal(f"ml.model_selection floors incoherent for {fam}: "
                      f"min_total_rows ({total_f[fam]}) < min_live_rows "
                      f"({live_f[fam]}) - total includes live, so the total "
                      f"floor can never bind and is a config typo")

    # --- ml.sample_weights: de Prado corrections (AFML ch.4) --------------
    sw = config.get("ml", {}).get("sample_weights", {}) or {}
    if sw:
        gsec = float(sw.get("uniqueness_grid_sec", 300))
        if not (30.0 <= gsec <= 3600.0):
            fatal(f"ml.sample_weights.uniqueness_grid_sec ({gsec}) outside "
                  f"[30, 3600]s - the grid must be near the signal cadence "
                  f"(finer burns CPU for nothing, coarser blurs concurrency)")
        ufl = float(sw.get("uniqueness_floor", 0.05))
        if not (0.0 <= ufl <= 1.0):
            fatal(f"ml.sample_weights.uniqueness_floor ({ufl}) outside "
                  f"[0, 1] - it bounds the uniqueness discount")
        tbw = float(sw.get("time_barrier_zero_weight", 1.0))
        if not (0.0 < tbw <= 1.0):
            fatal(f"ml.sample_weights.time_barrier_zero_weight ({tbw}) "
                  f"outside (0, 1] - 0 would erase every no-touch zero "
                  f"(discarding evidence); >1 would overweight the weakest "
                  f"label class")
        pw = float(sw.get("prior_skew_window_h", 24))
        if not (1.0 <= pw <= 168.0):
            fatal(f"ml.sample_weights.prior_skew_window_h ({pw}) outside "
                  f"[1, 168]h")
        pt = float(sw.get("prior_skew_threshold", 0.25))
        if not (0.05 <= pt <= 0.9):
            fatal(f"ml.sample_weights.prior_skew_threshold ({pt}) outside "
                  f"[0.05, 0.9] - below is noise, above never fires")
        pm = int(sw.get("prior_skew_min_rows", 30))
        if pm < 10:
            fatal(f"ml.sample_weights.prior_skew_min_rows ({pm}) < 10 - the "
                  f"window prior is meaningless on fewer rows")

    # --- markout: post-fill mark-out measurement (execution/markout.py) ---
    # window <= 0 makes MarkoutTracker's _obs a deque(maxlen<=0): 0 is a
    # silent blackhole (every observation discarded on append, the tracker
    # runs but never accumulates); a negative maxlen isn't validated by
    # collections.deque until the FIRST lazy defaultdict access mid-cycle,
    # where it raises ValueError - a crash-loop discovered only in
    # production, not at boot. horizons_sec must be non-empty with every
    # entry positive when the tracker is enabled, or record_fill/poll are
    # no-ops that silently measure nothing.
    mk = config.get("markout", {}) or {}
    if bool(mk.get("enabled", True)):
        mk_window = int(mk.get("window", 200))
        if mk_window < 1:
            fatal(f"markout.window={mk_window} must be >= 1 - 0 silently "
                  f"discards every observation (a blackhole deque), "
                  f"negative raises ValueError lazily on first mid-cycle "
                  f"access")
        mk_hz = mk.get("horizons_sec", [5.0, 30.0, 60.0]) or []
        if not mk_hz:
            fatal("markout.enabled but horizons_sec is empty - nothing to "
                  "measure")
        elif any(not isinstance(h, (int, float)) or float(h) <= 0
                 for h in mk_hz):
            fatal(f"markout.horizons_sec={mk_hz!r} has a non-positive entry "
                  f"- every horizon must be > 0 seconds")
        mk_grace = float(mk.get("grace_sec", 15.0))
        if mk_grace < 0:
            fatal(f"markout.grace_sec={mk_grace} must be >= 0")

    # --- watchdog: tail-event sentry (core/watchdog.py) --------------------
    # inverted/equal warn-vs-critical un-blocks entries on a dead feed: the
    # critical trip (operator alert, "stops are blind") can only ever fire
    # AFTER the warn trip in evaluate(), so warn >= critical means critical
    # never has room to fire above warn (or fires simultaneously, which is
    # not "graduated" tail handling - it's a single silent step). The pnl-
    # velocity/tick-quarantine/equity-drift knobs are all rate/magnitude
    # gates that must be positive or the corresponding trip either fires on
    # every cycle (0 threshold) or never resets (0 cooldown).
    wd = config.get("watchdog", {}) or {}
    if bool(wd.get("enabled", True)):
        wd_warn = float(wd.get("stale_warn_sec", 30))
        wd_crit = float(wd.get("stale_critical_sec", 120))
        if not (0.0 < wd_warn < wd_crit):
            fatal(f"watchdog stale thresholds incoherent: stale_warn_sec="
                  f"{wd_warn} must be > 0 and strictly below "
                  f"stale_critical_sec={wd_crit} - inverted/equal leaves the "
                  f"critical trip (operator alert, stops blind) unable to "
                  f"fire after the warn trip")
        wd_vel_window = float(wd.get("pnl_velocity_window_sec", 900))
        if wd_vel_window <= 0:
            fatal(f"watchdog.pnl_velocity_window_sec={wd_vel_window} must be "
                  f"positive - it is the rolling window the velocity trip "
                  f"measures equity drop over")
        wd_vel_drop = float(wd.get("pnl_velocity_max_drop_pct", 6.0))
        if wd_vel_drop <= 0:
            fatal(f"watchdog.pnl_velocity_max_drop_pct={wd_vel_drop} must be "
                  f"positive - <= 0 trips the velocity halt on ordinary "
                  f"equity noise")
        wd_vel_cd = float(wd.get("pnl_velocity_cooldown_sec", 1800))
        if wd_vel_cd <= 0:
            fatal(f"watchdog.pnl_velocity_cooldown_sec={wd_vel_cd} must be "
                  f"positive - <= 0 means the velocity trip never latches "
                  f"(re-arms on the very next healthy tick)")
        wd_tick = float(wd.get("tick_jump_quarantine_pct", 8.0))
        if wd_tick <= 0:
            fatal(f"watchdog.tick_jump_quarantine_pct={wd_tick} must be "
                  f"positive - <= 0 quarantines every tick, holding stops "
                  f"one cycle forever")
        wd_drift = float(wd.get("max_equity_drift_pct", 2.0))
        if wd_drift <= 0:
            fatal(f"watchdog.max_equity_drift_pct={wd_drift} must be "
                  f"positive - <= 0 flags the live equity-truth check on "
                  f"ordinary rounding noise")

    # --- fair_value: Kraken-touch staleness bound (W2-23) ------------------
    # at 0, `(now - kraken_touch_ts) > 0` is true on every cycle except the
    # exact instant the touch was stamped, so the touch never holds even
    # across a single missed poll - zeroing basis_bps/edge_bps constantly.
    fv_stale = float(_f(config, "fair_value.kraken_stale_sec", 120.0))
    if fv_stale <= 0:
        fatal(f"fair_value.kraken_stale_sec={fv_stale} must be positive - "
              f"at 0 the Kraken touch never holds across even a single "
              f"missed poll, so basis_bps/edge_bps read zero every cycle")

    # --- capital / risk ladder ------------------------------------------
    start_cap = float(_f(config, "capital_management.starting_capital_usd", 0))
    if start_cap <= 0 and not dry_run:
        fatal("capital_management.starting_capital_usd must be > 0 in live "
              "mode (the dry-run '0 -> $10k paper' default never applies to "
              "real money)")
    daily = float(_f(config, "capital_management.daily_loss_limit_pct", 5))
    hard = float(_f(config, "capital_management.hard_stop_drawdown_pct", 15))
    # profit-split parity: the reinvested share is IMPLICITLY
    # (100 - savings_pct) in CapitalManager.record_realized_profit; the
    # reinvestment knob is informational. If an operator sets the two to
    # numbers that don't sum to 100, the config is lying about where profit
    # goes — refuse rather than silently honoring only savings_pct.
    sav = float(_f(config, "capital_management.savings_pct_of_profit", 20))
    resv = float(_f(config, "capital_management.reserve_pct_of_profit", 0))
    reinv = float(_f(config, "capital_management.reinvestment_pct_of_profit",
                     100 - sav - resv))
    if not (0.0 <= sav <= 100.0):
        fatal(f"capital_management.savings_pct_of_profit ({sav}) outside "
              f"[0, 100]")
    if not (0.0 <= resv <= 50.0):
        fatal(f"capital_management.reserve_pct_of_profit ({resv}) outside "
              f"[0, 50] - above half of every win into the shock "
              f"absorber starves both compounding and savings")
    if abs(sav + resv + reinv - 100.0) > 1e-9:
        fatal(f"capital_management profit split incoherent: savings "
              f"({sav}) + reserve ({resv}) + reinvestment ({reinv}) "
              f"must sum to 100 - the split silently lies about "
              f"where profit goes otherwise")
    if daily <= 0 or hard <= 0:
        fatal("loss limits must be positive")
    elif daily >= hard:
        fatal(f"daily_loss_limit_pct ({daily}) must be below "
              f"hard_stop_drawdown_pct ({hard}) - the daily brake must "
              f"engage before the parachute")

    max_conc = int(_f(config, "capital_management.max_concurrent_positions", 3))
    if max_conc < 1:
        fatal(f"capital_management.max_concurrent_positions ({max_conc}) "
              f"must be >= 1 - at 0 can_open_new_position vetoes every "
              f"entry and the bot idles silently")

    # profit goals (measurement only): a target must be a non-negative
    # number; 0 disables grading for that period. Negative is nonsense
    # (a "goal" of losing money), and a goal above the hard-stop loss
    # bound is unreachable by construction - flag it rather than grade
    # every period a guaranteed miss.
    wkg = float(_f(config, "capital_management.weekly_profit_goal_usd", 0))
    mog = float(_f(config, "capital_management.monthly_profit_goal_usd", 0))
    cap_ceiling = start_cap * hard / 100.0    # a period can't out-earn the
    for _name, _v in (("weekly_profit_goal_usd", wkg),
                      ("monthly_profit_goal_usd", mog)):
        if _v < 0.0:
            fatal(f"capital_management.{_name} ({_v}) is negative - a "
                  f"profit goal is a target to beat, not a loss budget")
        if cap_ceiling > 0 and _v > cap_ceiling * 4.0:
            fatal(f"capital_management.{_name} ({_v}) is unreachable: "
                  f"above 4x the hard-stop loss bound ({cap_ceiling:.0f}) "
                  f"every period grades a guaranteed miss - set a real "
                  f"target or 0 to disable grading")

    soft = float(_f(config, "inventory.soft_cap_pct_of_equity", 15))
    hardc = float(_f(config, "inventory.hard_cap_pct_of_equity", 25))
    if soft >= hardc:
        fatal(f"inventory soft cap ({soft}) must be below hard cap ({hardc})")

    mss = int(_f(config, "inventory.max_same_side_positions_per_asset", 2))
    if mss < 1:
        fatal(f"inventory.max_same_side_positions_per_asset ({mss}) must be "
              f">= 1 - at 0 every entry is vetoed as crowded")
    n_pairs = len(_f(config, "exchanges.kraken.trading_pairs", []) or [])
    if n_pairs and mss * 2 * n_pairs < max_conc:
        warn(f"max_concurrent_positions ({max_conc}) can never be reached: "
             f"{n_pairs} pairs x {mss} same-side cap x 2 directions = "
             f"{mss * 2 * n_pairs} slots. Not dangerous, just unreachable.")

    ex_share = float(_f(config, "ml.exploration.max_asset_share", 0.5))
    if not (0.0 < ex_share <= 1.0):
        fatal(f"ml.exploration.max_asset_share ({ex_share}) must be in "
              f"(0, 1] - at 0 exploration never fires once any asset has a "
              f"labeled row; 1 disables the share check")
    if int(_f(config, "ml.exploration.share_min_rows", 10)) < 1:
        fatal("ml.exploration.share_min_rows must be >= 1")
    # ML-073 label realization: the maturity horizon must be at least one full
    # label window (the barrier has to have fired) and not absurdly long, or a
    # position never matures and the starvation loop never clears.
    rls = float(_f(config, "ml.exploration.realize_after_label_spans", 1.0))
    if bool(_f(config, "ml.exploration.realize_mature_labels", True)) and \
            not (1.0 <= rls <= 6.0):
        fatal(f"ml.exploration.realize_after_label_spans ({rls}) must be in "
              f"[1, 6] label spans - below 1 closes positions before the "
              f"triple-barrier label window even resolves; above 6 they sit so "
              f"long the SD-002 starvation loop never clears")
    # fastpath: only binds when the book is FULL (buying a teach slot). A
    # shortened-hold realized label is honest ground truth of that hold —
    # but below a quarter-span the holds get so short the labels are churn,
    # not outcomes. 0 disables; otherwise [0.25, realize_after_label_spans].
    rfp = float(_f(config, "ml.exploration.realize_fastpath_spans", 0.0))
    if bool(_f(config, "ml.exploration.realize_mature_labels", True)) and \
            rfp != 0.0 and not (0.25 <= rfp <= rls):
        fatal(f"ml.exploration.realize_fastpath_spans ({rfp}) must be 0 "
              f"(disabled) or in [0.25, realize_after_label_spans={rls}] - "
              f"shorter holds than a quarter-span teach churn, and a "
              f"fastpath above the full horizon never fires")
    # drought extension: arms the fastpath with FREE slots after this many
    # hours without an admitted entry. Meaningless without a fastpath; sane
    # only between "one label span" scale and "a day" (longer = never fires
    # inside a weekend, the exact drought it was built for).
    rdh = float(_f(config, "ml.exploration.realize_drought_h", 0.0))
    if bool(_f(config, "ml.exploration.realize_mature_labels", True)) and \
            rdh != 0.0:
        if rfp == 0.0:
            fatal(f"ml.exploration.realize_drought_h ({rdh}) needs "
                  f"realize_fastpath_spans enabled - the drought extension "
                  f"only chooses WHEN the fastpath horizon applies")
        if not (0.25 <= rdh <= 24.0):
            fatal(f"ml.exploration.realize_drought_h ({rdh}) must be 0 "
                  f"(disabled) or in [0.25, 24] hours")

    # give-back vol-scaled arm: 0 = static arm_gain_pct; else the arm is
    # mult * sigma_bar. Below 0.5 sigma the ratchet arms inside ordinary
    # bar noise (churn); above 6 sigma it can never arm on a real move.
    gbm = float(_f(config, "profit_taking.give_back.arm_vol_mult", 0.0))
    if bool(_f(config, "profit_taking.give_back.enabled", False)) and \
            gbm != 0.0 and not (0.5 <= gbm <= 6.0):
        fatal(f"profit_taking.give_back.arm_vol_mult ({gbm}) must be 0 "
              f"(static arm) or in [0.5, 6] sigma_bar multiples")

    max_pos = float(_f(config,
                       "capital_management.max_position_size_pct_of_capital", 10))
    if not (0 < max_pos <= 100):
        fatal("max_position_size_pct_of_capital out of (0, 100]")

    # capital_management.max_position_size_pct_of_capital is NOT what
    # actually caps a live entry - risk/position_sizer.py's PositionSizer
    # reads its own position_sizer.max_position_size_pct_of_capital copy
    # (risk/capital_manager.py's calculate_position_size, which reads the
    # capital_management copy, is dead code - never called from main.py).
    # Same failure mode as the pretrade/order_manager fee split above: two
    # independent copies of one number silently drift apart. Enforce parity
    # rather than pick a canonical source, so either being edited catches it.
    sizer_max_pos = float(_f(config,
                             "position_sizer.max_position_size_pct_of_capital",
                             max_pos))
    if abs(max_pos - sizer_max_pos) > 1e-9:
        fatal(f"max_position_size_pct_of_capital mismatch: "
              f"capital_management ({max_pos}) != position_sizer "
              f"({sizer_max_pos}) - only the position_sizer copy actually "
              f"caps live entries; the capital_management copy is checked "
              f"here but not enforced at runtime")

    # untradeable-by-construction check: if the largest permitted position
    # is below every minimum ticket, the bot will veto 100% of entries and
    # burn API quota doing nothing. Not dangerous - just pointless.
    min_ticket = max(float(_f(config, "position_sizer.min_ticket_usd", 15)),
                     float(_f(config, "pretrade.min_order_usd", 15)))
    if start_cap > 0:
        max_ticket = start_cap * max_pos / 100.0
        if max_ticket < min_ticket:
            warn(f"max position {max_pos}% of ${start_cap:,.0f} = "
                 f"${max_ticket:,.0f} is below the ${min_ticket:,.0f} "
                 f"minimum ticket - NO entry can ever be approved. Raise "
                 f"max_position_size_pct_of_capital or add capital.")

    # --- profit tiers -----------------------------------------------------
    # ProfitTierEngine closes close_pct of the CURRENT (remaining) size at each
    # tier, not the original, so closes compound geometrically:
    #     cumulative retired = 1 - prod(1 - close_i/100)
    # That asymptotes to 100% and can never exceed it. The old check summed the
    # four closes and warned above 100% "of the ORIGINAL" - both the label and
    # the impossible >100% state were wrong. The condition actually worth
    # flagging is the opposite: if the tiers together retire only a little, most
    # of the position becomes a permanent RUNNER left on the trailing/give-back
    # floor after the last tier.
    prev = 0.0
    remaining = 1.0
    for i in range(1, 5):
        t = _f(config, f"profit_taking.tier_{i}", {}) or {}
        trig = float(t.get("trigger_pct_gain", 0))
        close = float(t.get("close_pct_of_position", 0))
        if trig <= prev:
            fatal(f"tier_{i} trigger {trig}% not strictly above tier_{i-1} "
                  f"({prev}%)")
        if not (0 < close <= 100):
            fatal(f"tier_{i} close_pct_of_position out of (0, 100]")
        prev = trig
        remaining *= (1.0 - close / 100.0)
    if remaining > 0.5:
        warn(f"profit tiers retire only {(1.0 - remaining) * 100:.0f}% of the "
             f"position across all four (closes are % of CURRENT size); "
             f"{remaining * 100:.0f}% rides the trailing/give-back floor after "
             f"the last tier - confirm that floor is tight enough to protect a "
             f"runner that large.")

    # tier-1 cost-multiple floor (P1, 2026-07-23 P&L diagnosis): floors
    # tier-1's effective trigger at mult x the entry's own estimated
    # round-trip cost (Position.est_cost_bps). Derivation: the 2026-07-23
    # live-close audit (209 closes) measured avg win $0.05 vs avg loss $0.19
    # and a ~20.5bps cost overrun - tier-1 was banking LESS than one
    # round-trip cost unit. Shipped 3.0x makes the first take bank >= 2 net
    # cost-units after paying one. Below 1.0x the floor could not even
    # guarantee covering a single cost unit (defeats its own purpose);
    # above 10.0x tier-1 would almost never fire in an ordinary vol regime.
    mtcm = float(_f(config, "profit_taking.min_trigger_cost_mult", 3.0))
    if not (1.0 <= mtcm <= 10.0):
        fatal(f"profit_taking.min_trigger_cost_mult ({mtcm}) must be in "
              f"[1.0, 10.0] - it floors tier-1's effective trigger at mult x "
              f"the entry's estimated round-trip cost (est_cost_bps); below "
              f"1x the floor can't even guarantee covering one cost unit, "
              f"above 10x tier-1 would almost never fire")

    # --- stops / slippage / cadence --------------------------------------
    if float(_f(config, "risk.stop_loss_pct", 2.0)) <= 0:
        fatal("risk.stop_loss_pct must be positive")
    if float(_f(config, "risk.max_slippage_pct", 0.5)) <= 0:
        fatal("risk.max_slippage_pct must be positive")
    poll = float(_f(config, "system.polling_interval_sec", 5))
    if poll <= 0:
        fatal("system.polling_interval_sec must be positive")
    elif poll > 60:
        warn(f"polling_interval_sec={poll:.0f}s: stops are only enforced "
             f"once per cycle - this is a long time to be blind")

    cfh = int(_f(config, "system.cycle_fail_halt", 10))
    if cfh < 1:
        fatal("system.cycle_fail_halt must be >= 1 - the runner halts new "
              "risk after this many consecutive cycle failures")
    elif cfh < 3:
        warn(f"system.cycle_fail_halt={cfh}: halting new risk after so few "
             f"consecutive failures will trip on a transient feed blip")

    # main.py does `self._cycle % self.slow_every` every fast cycle - 0
    # raises ZeroDivisionError on the very first cycle, every cycle after.
    slow_every = int(_f(config, "system.slow_cycle_every_n", 6))
    if slow_every < 1:
        fatal(f"system.slow_cycle_every_n={slow_every} must be >= 1 - 0 "
              f"raises ZeroDivisionError on `cycle % slow_cycle_every_n` "
              f"every cycle")

    # order_manager.order_timeout_sec must exceed the poll cadence: an order
    # is only checked for timeout when the runner polls, so a timeout at or
    # below the cadence expires the order before it can ever be evaluated
    # once (born already dead).
    om_timeout = float(_f(config, "order_manager.order_timeout_sec", 25.0))
    if om_timeout <= poll:
        fatal(f"order_manager.order_timeout_sec ({om_timeout}) must exceed "
              f"system.polling_interval_sec ({poll}) - at/below the poll "
              f"cadence every order expires before the runner can check it "
              f"even once")
    om_reprices = int(_f(config, "order_manager.max_reprices", 1))
    if om_reprices < 0:
        fatal(f"order_manager.max_reprices={om_reprices} must be >= 0")
    om_fill_ratio = float(_f(config, "order_manager.min_fill_ratio", 0.10))
    if not (0.0 <= om_fill_ratio <= 1.0):
        fatal(f"order_manager.min_fill_ratio={om_fill_ratio} must be in "
              f"[0, 1] - it is graded against a filled/requested ratio")

    lev = float(_f(config, "leverage.region_max_leverage", 10))
    if lev < 1:
        fatal("leverage.region_max_leverage below 1")
    lev_use_margin = bool(_f(config, "leverage.use_margin", False))
    if lev_use_margin and dry_run is False:
        warn("margin ENABLED in live config - confirm this is intentional")
    # target_vol_annual_pct feeds `lev = target_vol/vol` BEFORE the
    # use_margin branch even runs (risk/leverage.py allowed_leverage) - at 0
    # every allowed-leverage computation floors to 0 and every entry is
    # silently blocked regardless of margin being on or off. min_leverage
    # is a floor applied to that same pre-margin ladder, so it must not be
    # negative either. Unconditional (not gated on use_margin), matching
    # the code path both actually run on.
    lev_target_vol = float(_f(config, "leverage.target_vol_annual_pct", 35.0))
    if lev_target_vol <= 0:
        fatal(f"leverage.target_vol_annual_pct={lev_target_vol} must be "
              f"positive - lev = target_vol/realized_vol runs regardless of "
              f"use_margin; 0 zeroes allowed leverage and silently blocks "
              f"every entry")
    lev_min = float(_f(config, "leverage.min_leverage", 0.25))
    if lev_min < 0:
        fatal(f"leverage.min_leverage={lev_min} must be >= 0")
    # margin_scale_below_pct/margin_block_below_pct are read ONLY inside the
    # `elif self.use_margin:` branch (risk/leverage.py) - gate this check on
    # use_margin so a purely-spot config with stale/unused margin fields
    # isn't flagged for a band that code path never reads.
    if lev_use_margin:
        m_scale = float(_f(config, "leverage.margin_scale_below_pct", 200))
        m_block = float(_f(config, "leverage.margin_block_below_pct", 150))
        if m_block >= m_scale:
            fatal(f"leverage.margin_block_below_pct ({m_block}) must be "
                  f"below margin_scale_below_pct ({m_scale}) - an inverted/"
                  f"equal band divides by zero in the scaling fraction (at "
                  f"equal) or creates a leverage cliff at the margin "
                  f"boundary (inverted)")

    # --- live credentials -------------------------------------------------
    if not dry_run:
        if not _f(config, "exchanges.kraken.api_key", "") \
                or not _f(config, "exchanges.kraken.api_secret", ""):
            fatal("live mode requires Kraken api_key and api_secret in "
                  "exchanges.kraken - every private call would silently "
                  "fail otherwise")

    # --- new hardening sections (defaults are fine; nonsense is not) ------
    dm = float(_f(config, "order_manager.deadman_timeout_sec", 60))
    if dm and (dm < 15 or dm > 3600):
        fatal("order_manager.deadman_timeout_sec must be 0 (off) or in "
              "[15, 3600] - below the poll cadence it flaps, above an hour "
              "it protects nothing")
    # DRY-RUN sim fill realism (MP-7): probabilities in [0,1], fraction
    # window ordered, queue tolerance non-negative. A base prob of 0 would
    # make passive orders NEVER fill in the sim (no candidate labels at
    # all); flag it loud rather than silently starving the learner.
    sf_base = float(_f(config, "order_manager.sim_fill.passive_base_prob",
                       0.45))
    if not (0.0 < sf_base <= 1.0):
        fatal(f"order_manager.sim_fill.passive_base_prob={sf_base} must be "
              f"in (0, 1] - zero starves candidate labels, >1 is not a "
              f"probability")
    sf_lo = float(_f(config, "order_manager.sim_fill.fill_frac_min", 0.3))
    sf_hi = float(_f(config, "order_manager.sim_fill.fill_frac_max", 1.0))
    if not (0.0 < sf_lo <= sf_hi <= 1.0):
        fatal(f"order_manager.sim_fill fill_frac window [{sf_lo}, {sf_hi}] "
              f"must satisfy 0 < min <= max <= 1")
    sf_tol = float(_f(config, "order_manager.sim_fill.queue_tol_frac", 1.0))
    if sf_tol < 0.0:
        fatal(f"order_manager.sim_fill.queue_tol_frac={sf_tol} negative - "
              f"it is a multiple of order size, the front-of-queue yardstick")
    sf_drain = float(_f(config, "order_manager.sim_fill.queue_drain_frac",
                        0.20))
    if not (0.0 <= sf_drain <= 1.0):
        fatal(f"order_manager.sim_fill.queue_drain_frac={sf_drain} must be "
              f"in [0, 1] - it is the per-poll geometric turnover fraction; "
              f"0 starves fills on static-snapshot replays")
    sf_sref = float(_f(config, "order_manager.sim_fill.sigma_ref_bps", 30.0))
    if sf_sref <= 0.0:
        fatal(f"order_manager.sim_fill.sigma_ref_bps={sf_sref} must be "
              f"positive - it normalizes the vol-scaled queue turnover")
    # STARVATION caveat (review finding): with queue_aware on, the geometric
    # turnover clears at most ~1/(1-drain*sigma/sigma_ref) of the queue per
    # poll, and only ~order_timeout_sec/poll_cadence polls exist before an
    # unfilled order expires. At the default drain/sigma_ref a wall more than
    # a few multiples of the order size never clears in-window, so a book bot
    # resting behind real depth generates ZERO passive labels. It is now ON by
    # default (execution-truth harness): calibrate drain/sigma_ref against the
    # live poll cadence via scripts/calibrate_fills.py and confirm fills are not
    # starved before trusting the labels.
    if bool(_f(config, "order_manager.sim_fill.queue_aware", False)):
        warn("order_manager.sim_fill.queue_aware=true: verify passive fills "
             "are not starved at your live sigma/poll-cadence before trusting "
             "the labels — the queue turnover must clear a typical wall inside "
             "order_timeout_sec or every behind-the-wall entry expires unfilled")
    esc = _f(config, "risk.exit_escalation", {}) or {}
    mult = float(esc.get("widen_mult", 2.0))
    if mult < 1.0:
        fatal("risk.exit_escalation.widen_mult must be >= 1")
    # the escalation ladder computes slip_pct = min(base * widen_mult**n,
    # cap); if cap sits BELOW the base max_slippage_pct, even attempt 0
    # clamps to the cap - an exit that should be marketable at the ordinary
    # slippage tolerance instead pins at a TIGHTER (unfillable) price than
    # a normal order would ever use.
    esc_cap = float(esc.get("max_slippage_cap_pct", 3.0))
    base_slip = float(_f(config, "risk.max_slippage_pct", 0.5))
    if esc_cap < base_slip:
        fatal(f"risk.exit_escalation.max_slippage_cap_pct ({esc_cap}) must "
              f"be >= risk.max_slippage_pct ({base_slip}) - a cap below the "
              f"base tolerance pins every escalated exit at a TIGHTER "
              f"(less fillable) price than an ordinary order ever uses")
    esc_market_after = int(esc.get("market_after_attempts", 3))
    if not (0 <= esc_market_after <= 20):
        fatal(f"risk.exit_escalation.market_after_attempts="
              f"{esc_market_after} must be in [0, 20] - negative is not an "
              f"attempt count, and past ~20 the ladder never reaches its "
              f"market-order failsafe rung within a position's lifetime")
    mark_stale = float(_f(config, "risk.mark_stale_sec", 20.0))
    if mark_stale <= 0:
        fatal(f"risk.mark_stale_sec={mark_stale} must be positive - at 0, "
              f"`(now - mark_ts) <= 0` is false for every mark except the "
              f"exact instant it was stamped, so every mark reads STALE "
              f"permanently (profit tiers, inventory derisk and the "
              f"equity-peak/hard-stop all lose their trusted mark)")

    # --- anti-scalp manip gate (new-entry downsize/veto band) --------------
    mg = _f(config, "risk.manip_gate", {}) or {}
    if bool(mg.get("enabled", True)):
        d_at = float(mg.get("downsize_at", 0.6))
        v_at = float(mg.get("veto_at", 0.9))
        m_sc = float(mg.get("min_scale", 0.25))
        if not (0.0 <= d_at <= 1.0) or not (0.0 <= v_at <= 1.0):
            fatal("risk.manip_gate.downsize_at/veto_at must be in [0, 1] - "
                  "manip_suspect_score is a [0, 1] suspicion level")
        if v_at <= d_at:
            fatal(f"risk.manip_gate.veto_at ({v_at}) must be strictly above "
                  f"downsize_at ({d_at}) - the downsize band collapses "
                  f"otherwise and entries jump straight from full size to a "
                  f"hard veto")
        if not (0.0 <= m_sc <= 1.0):
            fatal("risk.manip_gate.min_scale must be in [0, 1] - it is the "
                  "floor of a multiplicative size scale (1.0 = no downsize)")

    # --- input-drift window vs PSI stability ------------------------------
    # decile-PSI on too small a live window fabricates drift from pure
    # sampling noise (null-tested: a 40-row window reads ~19% mean / 28% p95
    # "drift" on an in-distribution sample, nearly tripping the retrain vote).
    # WARN (never fatal - the bot trades correctly, it just retrains on noise).
    dmr = int(_f(config, "ml.monitor.drift_min_rows", 100))
    if dmr < 80:
        warn(f"ml.monitor.drift_min_rows={dmr} is below ~80: a 10-bin PSI at "
             f"that window fabricates false drift from in-distribution noise "
             f"(null p95 ~28% at 40 rows vs the {float(_f(config, 'ml.monitor.drift_frac_features', 0.30)):.0%} "
             f"retrain trigger). Raise it so a fired ML-031 means a real shift.")

    # ML-075 shadow-recovery is a bool feature flag; a non-bool would be
    # coerced by bool() and silently mean something the operator didn't intend.
    _sr = _f(config, "ml.monitor.shadow_recovery", True)
    if not isinstance(_sr, bool):
        advisory(f"ml.monitor.shadow_recovery={_sr!r} is not a boolean; it is "
                 f"coerced by bool() - set true/false explicitly.")

    # W2-17: de-escalation deadband. Below 1 the deadband is disabled outright
    # (every healthy window de-escalates instantly - reopens the L0<->1 flap
    # the knob exists to fix); above 10 a genuinely recovered model stays
    # throttled far longer than the evidence warrants.
    dhw = int(_f(config, "ml.monitor.deescalate_healthy_windows", 3))
    if not (1 <= dhw <= 10):
        fatal(f"ml.monitor.deescalate_healthy_windows ({dhw}) must be in "
              f"[1, 10] - <1 disables the de-escalation deadband (reopens "
              f"the L0<->L1 flap on window-churn noise), >10 leaves a "
              f"recovered model throttled long past the evidence")

    # --- model governor judge window / shrinkage-kelly-stop ordering ------
    # _windows() slices `recs = [...][-window_trades:]` then requires
    # `len(recs) >= min_trades_to_judge` - recs can never exceed
    # window_trades, so min_trades_to_judge > window_trades makes the
    # governor NEVER judge (never escalates OR de-escalates on live
    # evidence). shrinkage ramps base (healthy) -> max (killed) as level
    # rises (_evaluate); an inverted pair reverses that ramp. kelly_mult
    # starts at 1.0 and floors at kelly_mult_min as level rises; stop_widen
    # starts at 1.0 and ceilings at stop_widen_max.
    mon_window = int(_f(config, "ml.monitor.window_trades", 30))
    mon_min_judge = int(_f(config, "ml.monitor.min_trades_to_judge", 15))
    if mon_window < 1:
        fatal(f"ml.monitor.window_trades={mon_window} must be >= 1")
    if mon_min_judge > mon_window:
        fatal(f"ml.monitor.min_trades_to_judge ({mon_min_judge}) must be <= "
              f"window_trades ({mon_window}) - the judged window is capped "
              f"at window_trades, so a higher min can never be reached and "
              f"the governor never judges")
    mon_shrink_base = float(_f(config, "ml.monitor.shrinkage_base", 0.35))
    mon_shrink_max = float(_f(config, "ml.monitor.shrinkage_max", 0.70))
    if not (0.0 <= mon_shrink_base <= mon_shrink_max <= 1.0):
        fatal(f"ml.monitor shrinkage bounds incoherent: need 0 <= "
              f"shrinkage_base ({mon_shrink_base}) <= shrinkage_max "
              f"({mon_shrink_max}) <= 1 - shrinkage ramps base (healthy) up "
              f"to max (killed) as the governor escalates; inverted reverses "
              f"that ramp")
    mon_kelly_min = float(_f(config, "ml.monitor.kelly_mult_min", 0.40))
    if not (0.0 < mon_kelly_min <= 1.0):
        fatal(f"ml.monitor.kelly_mult_min={mon_kelly_min} must be in "
              f"(0, 1] - kelly_mult starts at 1.0 (healthy) and floors here "
              f"as the governor escalates; 0 would zero every sized entry "
              f"at the worst level")
    mon_stop_widen_max = float(_f(config, "ml.monitor.stop_widen_max", 1.5))
    if mon_stop_widen_max < 1.0:
        fatal(f"ml.monitor.stop_widen_max={mon_stop_widen_max} must be >= 1 "
              f"- stop_widen starts at 1.0 and ceilings here; below 1 it "
              f"would TIGHTEN the stop on a degrading model instead of "
              f"widening it")

    # --- post-hoc interpretability report (ml/interpret.py) ---------------
    # analysis knobs, not decision-path tunables — but nonsense values make
    # the report LIE (a background too thin makes interventional SHAP noise;
    # a cluster threshold at the extremes silently degenerates clustered
    # permutation into the exact Hooker/de-Prado failure modes it exists
    # to fix). Fail loud rather than emit a confident wrong report.
    it_bg = int(_f(config, "ml.interpret.background_rows", 64))
    if it_bg < 16:
        fatal(f"ml.interpret.background_rows={it_bg} below 16: the "
              f"interventional value function is an average over the "
              f"background - this few rows makes exact SHAP precisely "
              f"wrong about a noisy expectation")
    it_ct = float(_f(config, "ml.interpret.corr_cluster_thr", 0.7))
    if not (0.3 <= it_ct <= 0.99):
        fatal(f"ml.interpret.corr_cluster_thr={it_ct} outside [0.3, 0.99]: "
              f"near 1.0 nothing clusters (substitution effects return), "
              f"below 0.3 everything clusters (importance of one blob)")
    it_ef = float(_f(config, "ml.interpret.eval_frac", 0.3))
    if not (0.1 <= it_ef <= 0.5):
        fatal(f"ml.interpret.eval_frac={it_ef} outside [0.1, 0.5]: the "
              f"held-out tail must exist AND leave a training majority")
    if int(_f(config, "ml.interpret.n_repeats", 5)) < 3:
        fatal("ml.interpret.n_repeats below 3: one permutation draw is an "
              "anecdote, not an importance estimate")
    it_dc = float(_f(config, "ml.interpret.drift_cos_warn", 0.8))
    if not (0.0 < it_dc <= 1.0):
        fatal(f"ml.interpret.drift_cos_warn={it_dc} must be in (0, 1] - "
              f"it is a cosine similarity floor")

    # --- risk protocol stack (rev 4 sizing overlay) ------------------------
    sf = float(_f(config, "risk_protocols.stack_floor_mult", 0.10))
    if not (0.0 < sf <= 1.0):
        fatal("risk_protocols.stack_floor_mult must be in (0, 1] - it is "
              "the last defense against a multiplicative collapse to zero")
    fmax = float(_f(config, "webdata.fear_greed_fear_max", 15))
    emin = float(_f(config, "webdata.fear_greed_euphoria_min", 85))
    if not (0 <= fmax < emin <= 100):
        fatal("webdata fear/euphoria thresholds must satisfy "
              f"0 <= fear_max({fmax}) < euphoria_min({emin}) <= 100 - "
              "inverted thresholds make sentiment context fire backwards")

    # --- vol_regime / sentiment ordering (shading-only paths) --------------
    # Mirrors the webdata fear/euphoria check above, but WARN not FATAL: a
    # miscalibrated percentile/threshold band here mis-classifies a regime
    # or a mood, it does not open the bot to a hard failure mode (the trade
    # path still executes correctly) - a FATAL would be disproportionate to
    # a shading-only misconfiguration, so it is caught loud without
    # refusing to start.
    vr_low = float(_f(config, "vol_regime.low_pct", 30.0))
    vr_elev = float(_f(config, "vol_regime.elevated_pct", 70.0))
    vr_ext = float(_f(config, "vol_regime.extreme_pct", 90.0))
    if not (0.0 <= vr_low < vr_elev < vr_ext <= 100.0):
        warn(f"vol_regime percentile thresholds incoherent: need 0 <= "
             f"low_pct({vr_low}) < elevated_pct({vr_elev}) < "
             f"extreme_pct({vr_ext}) <= 100 - inverted/equal bands "
             f"misclassify the vol regime shading")
    se_calm = float(_f(config, "sentiment.filter.stress_calm_threshold", 0.3))
    se_confirm = float(_f(config,
                          "sentiment.filter.stress_confirm_threshold", 0.6))
    if se_calm > se_confirm:
        warn(f"sentiment.filter.stress_calm_threshold ({se_calm}) must be "
             f"<= stress_confirm_threshold ({se_confirm}) - inverted "
             f"hysteresis makes the stress filter confirm before it can "
             f"even calm")
    se_fear = float(_f(config, "sentiment.fear_threshold", -0.35))
    se_euphoria = float(_f(config, "sentiment.euphoria_threshold", 0.45))
    if not (se_fear < 0.0 < se_euphoria):
        warn(f"sentiment fear_threshold ({se_fear}) / euphoria_threshold "
             f"({se_euphoria}) must satisfy fear_threshold < 0 < "
             f"euphoria_threshold - a wrong-signed threshold fires the "
             f"fear/euphoria spike flags backwards")

    a = float(_f(config, "risk_protocols.cvar.alpha", 0.975))
    if not (0.5 < a < 1.0):
        fatal("risk_protocols.cvar.alpha must be in (0.5, 1) - it is a "
              "tail-confidence level, not a percentage")
    esb = float(_f(config, "risk_protocols.cvar.es_budget_frac", 0.010))
    if not (0.0 < esb <= 0.05):
        fatal("risk_protocols.cvar.es_budget_frac must be in (0, 0.05] - "
              "budgeting >5% of equity to one entry's expected shortfall "
              "is not a cap, it is a wish")
    ts = float(_f(config, "risk_protocols.budget.taper_start", 0.5))
    fl = float(_f(config, "risk_protocols.budget.floor_mult", 0.15))
    if not (0.0 <= ts < 1.0) or not (0.0 <= fl < 1.0):
        fatal("risk_protocols.budget taper_start and floor_mult must be "
              "in [0, 1)")
    d_b = float(_f(config, "risk_protocols.budget.daily_loss_budget_pct",
                   2.5))
    w_b = float(_f(config, "risk_protocols.budget.weekly_loss_budget_pct",
                   6.0))
    if d_b > 0 and w_b > 0 and w_b < d_b:
        fatal("risk_protocols.budget weekly budget below the daily budget "
              "- the weekly gate would bind before a single bad day ends")
    hard = float(_f(config, "capital_management.hard_stop_drawdown_pct", 15))
    if d_b > 0 and hard > 0 and d_b >= hard:
        fatal("risk_protocols.budget.daily_loss_budget_pct must sit below "
              "capital_management.hard_stop_drawdown_pct - the taper must "
              "engage before the kill switch")
    ht = float(_f(config, "risk_protocols.heat.max_portfolio_heat_frac",
                  0.35))
    if not (0.0 < ht <= 1.0):
        fatal("risk_protocols.heat.max_portfolio_heat_frac must be in "
              "(0, 1]")
    corr = float(_f(config, "risk_protocols.heat.assumed_corr", 0.9))
    if not (0.0 <= corr <= 1.0):
        fatal("risk_protocols.heat.assumed_corr must be in [0, 1]")
    gshock = float(_f(config, "risk_protocols.gap.gap_shock_pct", 15.0))
    gloss = float(_f(config, "risk_protocols.gap.max_equity_loss_pct", 4.0))
    if gshock <= 0 or gloss <= 0:
        fatal("risk_protocols.gap shock and max loss must be positive")
    if bool(_f(config, "risk_protocols.vol_target.enabled", False)):
        vt_lo = float(_f(config, "risk_protocols.vol_target.min_mult", 0.25))
        vt_hi = float(_f(config, "risk_protocols.vol_target.max_mult", 1.15))
        if not (0.0 < vt_lo <= vt_hi):
            fatal("risk_protocols.vol_target min_mult/max_mult malformed")
        warn("risk_protocols.vol_target ENABLED - it overlaps the leverage "
             "governor's vol input; confirm the paper A/B before live")

    # --- give-back ratchet (rev 4 exit floor) -------------------------------
    if bool(_f(config, "profit_taking.give_back.enabled", False)):
        gbf = float(_f(config, "profit_taking.give_back.giveback_frac",
                       0.40))
        tgf = float(_f(config, "profit_taking.give_back.tight_frac", 0.25))
        arm = float(_f(config, "profit_taking.give_back.arm_gain_pct", 1.5))
        tgn = float(_f(config, "profit_taking.give_back.tighten_gain_pct",
                       0.0))
        if not (0.0 < gbf < 1.0) or not (0.0 < tgf < 1.0):
            fatal("profit_taking.give_back fractions must be in (0, 1)")
        elif tgf > gbf:
            fatal("profit_taking.give_back.tight_frac above giveback_frac "
                  "- the ratchet would LOOSEN as the trade improves")
        if arm <= 0:
            fatal("profit_taking.give_back.arm_gain_pct must be positive")
        if tgn > 0 and tgn <= arm:
            fatal("profit_taking.give_back.tighten_gain_pct must exceed "
                  "arm_gain_pct (or be 0 to disable the second rung)")
        # arm-vs-break-even coherence: flag a ratchet that arms inside the
        # fee/break-even buffer (its locked share would be fee noise). Lives
        # here — where `arm` is bound — not under the unrelated pos_cap>heat_cap
        # branch, where `arm` may be undefined (NameError) and the check would
        # only fire for the wrong reason.
        be_buf_bps = float(_f(config, "profit_taking.be_buffer_bps", 6.0)) \
            + 2.0 * float(_f(config, "profit_taking.est_fee_bps", 0.0))
        if arm * 100.0 <= be_buf_bps:
            warn(f"give_back.arm_gain_pct={arm}% arms inside the "
                 f"break-even buffer ({be_buf_bps:.0f}bps) - the locked "
                 f"share of such small moves is fee noise")

    # --- conviction runner (rev 6 entry-conviction leash) -------------------
    if bool(_f(config, "profit_taking.conviction_runner.enabled", False)):
        ncf = float(_f(config, "profit_taking.conviction_runner.neutral_conf",
                       0.70))
        mcf = float(_f(config, "profit_taking.conviction_runner.min_conf",
                       0.55))
        tml = float(_f(config, "profit_taking.conviction_runner.min_trail_mult",
                       0.60))
        if not (0.0 < mcf < ncf <= 1.0):
            fatal("profit_taking.conviction_runner needs 0 < min_conf < "
                  "neutral_conf <= 1 (the leash tightens BELOW neutral)")
        if not (0.1 <= tml <= 1.0):
            fatal("profit_taking.conviction_runner.min_trail_mult must be in "
                  "[0.1, 1.0] - it can only tighten the runner, never loosen it")

    # --- v8 anti-predation batch -----------------------------------------
    # stop-magnet band: the nudge widens a trailing stop by up to band_bps
    # past a round level. Negative is nonsense; above 100bps (1%) the
    # "nudge" rivals the trail distance itself and the labeler divergence
    # (ml/labeling.py mirrors trails in percent space, magnets are price-
    # anchored) stops being ignorable. 0 = off.
    mgb = float(_f(config, "profit_taking.stop_magnet.band_bps", 0.0))
    if not (0.0 <= mgb <= 100.0):
        fatal(f"profit_taking.stop_magnet.band_bps={mgb} outside [0, 100] - "
              f"negative bands are nonsense and past 100bps the anti-hunt "
              f"nudge rivals the trail distance itself (and the label sim, "
              f"which cannot mirror price-anchored magnets, diverges "
              f"materially)")
    # imbalance distance decay: 0 = legacy equal-weight; above 200bps the
    # e-folding covers the whole tracked book and the decay is a no-op
    # wearing a knob (every level weighted ~1), which lies about intent.
    idb = float(_f(config, "liquidity_regime.imbalance_decay_bps", 15.0))
    if not (0.0 <= idb <= 200.0):
        fatal(f"liquidity_regime.imbalance_decay_bps={idb} outside [0, 200] "
              f"- negative inverts the weighting (rewarding painted far "
              f"depth); above 200bps every tracked level weighs ~1 and the "
              f"decay is a silent no-op (set 0 to disable explicitly)")
    # venue-candle refresh: below 30s the throttled refresh burns the 3
    # req/s Kraken REST budget the trading path depends on for nothing (5m
    # bars can't change that fast); above 600s (2 full bars) the cached
    # bars lag the external feed enough to skew volume_z at bar rollover.
    crs = float(_f(config, "exchanges.kraken.candle_refresh_sec", 150.0))
    if not (30.0 <= crs <= 600.0):
        fatal(f"exchanges.kraken.candle_refresh_sec={crs} outside [30, 600] "
              f"- below 30s the candle refresh eats the Kraken REST budget "
              f"for identical 5m bars; above 600s (2 bars) venue-grounded "
              f"features lag the market they price")

    # --- urgency composition vs the execution ladder --------------------------
    ub = float(_f(config, "informed_flow.urgency.base", 0.30))
    uw = (float(_f(config, "informed_flow.urgency.w_burst", 0.40))
          + float(_f(config, "informed_flow.urgency.w_fresh", 0.20))
          + float(_f(config, "informed_flow.urgency.w_delta", 0.10)))
    u_max = ub + uw
    taker_at = float(_f(config, "execution_tactics.taker_at_urgency", 0.88))
    join_at = float(_f(config, "execution_tactics.join_at_urgency", 0.40))
    if not (0.0 <= ub <= 1.0) or uw < 0:
        fatal("informed_flow.urgency: base must be in [0,1] and weights "
              "non-negative")
    if u_max < taker_at:
        advisory(f"informed_flow.urgency: max reachable urgency "
                 f"{u_max:.2f} is below execution_tactics.taker_at_urgency "
                 f"{taker_at:.2f} - the taker rung can never fire")
    if ub >= join_at:
        advisory(f"informed_flow.urgency.base {ub:.2f} >= join_at_urgency "
                 f"{join_at:.2f} - EVERY confirmed signal at least joins the "
                 f"touch (no pure spread-capture rung)")
    # thin-book precision: the improve fraction must stay strictly inside
    # the spread (a full-spread rest is a cross, which defeats maker-only).
    tif = float(_f(config, "execution_tactics.thin_improve_spread_frac", 0.4))
    if not (0.0 <= tif < 0.5):
        fatal(f"execution_tactics.thin_improve_spread_frac={tif} must be in "
              f"[0, 0.5) - at 0.5+ the resting price reaches/crosses the "
              f"opposite touch, which is a taker fill, not maker precision")

    # --- sizer vol scaling + tier reach (lifted literals) --------------------
    vsmin = float(_f(config, "position_sizer.vol_scalar_min", 0.3))
    vsmax = float(_f(config, "position_sizer.vol_scalar_max", 1.5))
    vtgt = float(_f(config, "position_sizer.vol_target_ann_pct", 35.0))
    if not (0.0 <= vsmin <= vsmax):
        fatal("position_sizer vol_scalar bounds incoherent: need "
              "0 <= vol_scalar_min <= vol_scalar_max")
    if vtgt <= 0:
        fatal("position_sizer.vol_target_ann_pct must be positive")
    trd = float(_f(config, "position_sizer.tier_reach_decay", 0.65))
    if not (0.05 <= trd <= 1.0):
        fatal("position_sizer.tier_reach_decay must be in [0.05, 1.0] - it "
              "derives the payoff ratio b/b_net and the Kelly breakeven")
    if bool(_f(config, "risk_protocols.vol_target.enabled", False)):
        advisory("risk_protocols.vol_target is enabled ON TOP of the sizer's "
                 "own vol scaling (position_sizer.vol_target_ann_pct) - two "
                 "vol-targeting layers compound; confirm that is intended")

    # --- per-asset circuit breaker -------------------------------------------
    if bool(_f(config, "circuit_breaker.enabled", True)):
        ls = int(_f(config, "circuit_breaker.loss_streak", 4))
        ch = float(_f(config, "circuit_breaker.cooldown_hours", 6))
        if ls < 2:
            fatal("circuit_breaker.loss_streak < 2 would pause an asset on a "
                  "single loss - that's not a breaker, that's a coin flip")
        if not (0.25 <= ch <= 168):
            fatal("circuit_breaker.cooldown_hours must be in [0.25, 168]")
        if ls > 10:
            advisory(f"circuit_breaker.loss_streak={ls} is so high the "
                     f"breaker will likely never fire (portfolio budgets "
                     f"bind first)")

    # --- asset skimmer (scan wide, trade narrow) -----------------------------
    if bool(_f(config, "skimmer.enabled", False)):
        core = _f(config, "exchanges.kraken.trading_pairs", []) or []
        cands = _f(config, "skimmer.candidates", []) or []
        max_extra = int(_f(config, "skimmer.max_extra", 6))
        # the REST-fallback envelope: with the WS down, N pairs cost
        # ~N*6 book calls + tickers + candles per 30s against 3 req/s (=90).
        # Past ~12 active pairs the fallback falls behind exactly when the
        # primary feed is already degraded.
        if len(core) + max_extra > 12:
            fatal(f"skimmer: core ({len(core)}) + max_extra ({max_extra}) "
                  f"exceeds the 12-pair REST-fallback envelope - a WS outage "
                  f"would starve the book poll at 3 req/s")
        pscore = float(_f(config, "skimmer.promote_score", 0.55))
        dscore = float(_f(config, "skimmer.demote_score", 0.35))
        if not (0.0 < dscore < pscore <= 1.0):
            fatal("skimmer: needs 0 < demote_score < promote_score <= 1 "
                  "(equal or inverted bands churn the universe)")
        if float(_f(config, "skimmer.eval_every_min", 60)) < 5:
            fatal("skimmer.eval_every_min below 5 min - candidate polling "
                  "would eat the REST budget the trading path depends on")
        overlap = [c for c in cands if c in core]
        if overlap:
            advisory(f"skimmer: candidates already in trading_pairs are "
                     f"ignored: {overlap}")
        bad = [c for c in cands
               if not (isinstance(c, str) and c.endswith("/USD"))]
        if bad:
            fatal(f"skimmer: candidates must be Kraken 'X/USD' spot pairs "
                  f"(execution venue + quote-currency invariant): {bad}")
        # every tradable pair needs an offline pair-meta row: the generic
        # 2-decimal default silently grids sub-dollar prices (and AssetPairs
        # keys by ALTNAME, so DOGE-style pairs fall back even online)
        try:
            from data.kraken_feed import PAIR_META_FALLBACK
            nometa = [p for p in list(core) + [c for c in cands
                                               if isinstance(c, str)]
                      if p.replace("/", "") not in PAIR_META_FALLBACK]
            if nometa:
                advisory(f"pairs without an offline pair-meta fallback row "
                         f"(would run on the generic 2-decimal default): "
                         f"{nometa} - add them to data/kraken_feed.py "
                         f"PAIR_META_FALLBACK with AssetPairs-verified values")
        except ImportError:
            pass

    # --- entry cap vs the outer rails (coherence, not a hard stop) ----------
    # the position cap should sit at/under the per-order firewall cap and the
    # portfolio heat cap; if it pokes above, those rails still bind, but the
    # position cap is then dead config that reads as bigger than it can act.
    pos_cap = float(_f(config, "position_sizer.max_position_size_pct_of_capital",
                       10.0))
    fw_cap = float(_f(config, "risk_firewall.max_order_pct_equity", 30.0))
    heat_cap = 100.0 * float(_f(config,
                                "risk_protocols.heat.max_portfolio_heat_frac",
                                0.35))
    if pos_cap > fw_cap:
        advisory(f"position cap {pos_cap:.0f}% exceeds the firewall order cap "
                 f"{fw_cap:.0f}% - the firewall will clamp entries first")
    if pos_cap > heat_cap:
        advisory(f"position cap {pos_cap:.0f}% exceeds the portfolio heat cap "
                 f"{heat_cap:.0f}% - a single max position can't fit under heat")

    # --- regime ensemble thresholds -------------------------------------
    mom_bear = float(_f(config, "regime.momentum_bear_max", -0.34))
    mom_bull = float(_f(config, "regime.momentum_bull_min", 0.67))
    if not (-1.0 <= mom_bear < 0.0 < mom_bull <= 1.0):
        fatal(f"regime momentum thresholds incoherent: momentum_bear_max="
              f"{mom_bear} must be in [-1, 0) and momentum_bull_min="
              f"{mom_bull} in (0, 1] (TSMOM score is a mean of signs)")

    # --- liquidity regime: whiplash detector coherence --------------------
    # whiplash is the std of an imbalance ratio clamped to [0, 3], so it is
    # structurally bounded by 1.5. Outside (0, 1.5) the detector is not a
    # detector: <= 0 fires always (size_mult=0 -> vetoes EVERY entry),
    # >= 1.5 can never fire. Healthy books at the ~30s book-sampling
    # cadence measure p50~1.1 (45h live evidence), so low thresholds
    # reproduce the always-on failure in practice as well.
    wt = float(_f(config, "liquidity_regime.imbalance_whiplash_threshold",
                  1.45))
    if wt <= 0.0:
        fatal(f"liquidity_regime.imbalance_whiplash_threshold={wt} fires on "
              f"every cycle - the 'spoofy' label zeroes sizing, so this "
              f"blocks 100% of entries structurally")
    elif wt >= 1.5:
        warn(f"liquidity_regime.imbalance_whiplash_threshold={wt} exceeds "
             f"the metric's ceiling (std of a [0,3]-clamped ratio is "
             f"bounded by 1.5) - the whiplash detector can never fire")
    elif wt < 1.0:
        warn(f"liquidity_regime.imbalance_whiplash_threshold={wt} is below "
             f"the healthy-book baseline (p50~1.1 at the 30s book cadence; "
             f"45h evidence in outputs/monitor/liquidity_dist.jsonl) - "
             f"expect near-constant 'spoofy' labels vetoing all entries")
    # manip_suspect's whiplash component normalizes the raw std against
    # [healthy_p95, threshold]; a p95 at/above the threshold collapses the
    # ramp into a 0/1 step, and a p95 at/below the healthy MEDIAN re-creates
    # the saturation bug this knob exists to prevent (manip pegged 1.0 on
    # ordinary quiet books, halving healthy rows' training weight)
    wp95 = float(_f(config, "liquidity_regime.whiplash_healthy_p95", 1.27))
    if wp95 >= wt:
        fatal(f"liquidity_regime.whiplash_healthy_p95={wp95} >= "
              f"imbalance_whiplash_threshold={wt} - the manip_suspect "
              f"whiplash ramp needs healthy_p95 strictly below the spoofy "
              f"threshold")
    elif wp95 <= 1.1:
        warn(f"liquidity_regime.whiplash_healthy_p95={wp95} sits at/below "
             f"the healthy-book median (p50~1.1) - manip_suspect will read "
             f"elevated on ordinary quiet books")

    # --- v9 liquidity-tier isolation coherence ----------------------------
    # The cap-tiers scale ONLY the categorical executability floors. Two
    # invariants keep them coherent: CORE must reproduce the legacy flat floors
    # exactly (else enabling tiers silently retunes ETH/BTC and quant_trials/
    # overfit), and a THINNER tier must never be STRICTER than a richer one
    # (lower depth floor => wider spread ceiling), else the isolation gates
    # low-volume assets harder than the majors — the opposite of its purpose.
    lr = config.get("liquidity_regime", {}) or {}
    tcfg = lr.get("tiers") or {}
    if tcfg.get("enabled"):
        base_depth = float(lr.get("min_depth_usd", 150_000))
        base_spread = float(lr.get("max_spread_bps", 12.0))
        order = tcfg.get("order") or ["core", "mid", "micro"]
        rows = [(str(n),
                 float((tcfg.get(n) or {}).get("min_depth_usd", base_depth)),
                 float((tcfg.get(n) or {}).get("max_spread_bps", base_spread)))
                for n in order]
        core = next((r for r in rows if r[0] == "core"), None)
        if core is None:
            fatal("liquidity_regime.tiers.enabled but no 'core' tier defined - "
                  "core anchors the majors to the legacy floors")
        elif abs(core[1] - base_depth) > 1e-6 or \
                abs(core[2] - base_spread) > 1e-6:
            fatal(f"liquidity_regime.tiers.core "
                  f"({core[1]:.0f}/{core[2]:.0f}) must equal the legacy flat "
                  f"floors min_depth_usd/max_spread_bps "
                  f"({base_depth:.0f}/{base_spread:.0f}) - core is the majors' "
                  f"anchor; drift here silently retunes ETH/BTC")
        if any(r[1] <= 0 or r[2] <= 0 for r in rows):
            fatal("liquidity_regime.tiers floors must be positive")
        srt = sorted(rows, key=lambda r: r[1], reverse=True)
        for a, b in zip(srt, srt[1:], strict=False):
            if b[2] < a[2] - 1e-6:
                fatal(f"liquidity_regime.tiers: tier '{b[0]}' has a thinner "
                      f"depth floor than '{a[0]}' but a TIGHTER spread ceiling "
                      f"({b[2]:.0f} < {a[2]:.0f}); a thinner tier must allow a "
                      f"WIDER spread, else isolation is incoherent")

    # pretrade per-tier spread ceiling: core must match the flat cap, and the
    # ceiling must not tighten as tiers thin (mirror of the depth-tier rule).
    pt = config.get("pretrade", {}) or {}
    pt_tms = pt.get("tier_max_spread_bps") or {}
    if pt_tms:
        pt_base = float(pt.get("max_spread_bps", 15.0))
        vals = {str(k): float(v) for k, v in pt_tms.items()
                if not str(k).startswith("_")}
        if "core" in vals and abs(vals["core"] - pt_base) > 1e-6:
            fatal(f"pretrade.tier_max_spread_bps.core ({vals['core']:.0f}) must "
                  f"equal pretrade.max_spread_bps ({pt_base:.0f}) - core is the "
                  f"majors' spread ceiling")
        if any(v <= 0 for v in vals.values()):
            fatal("pretrade.tier_max_spread_bps values must be positive")
        # monotonicity is FATAL here (unlike the size-only depth-tier ordering):
        # this ceiling is the LIVE-ORDER veto (PT-021). Check it against the SAME
        # depth-tier order the classifier uses, generically over whatever tiers
        # are declared (not hardcoded core/mid/micro), and flag any declared
        # liquidity tier missing a pretrade cap (it silently falls back to flat).
        lr_tiers = lr.get("tiers") or {}
        if lr_tiers.get("enabled"):
            lr_base_depth = float(lr.get("min_depth_usd", 150_000))
            t_order = lr_tiers.get("order") or ["core", "mid", "micro"]
            depth_of = {n: float((lr_tiers.get(n) or {}).get(
                "min_depth_usd", lr_base_depth)) for n in t_order}
            richest_first = sorted(t_order, key=lambda n: depth_of[n],
                                   reverse=True)
            prev_n, prev_cap = None, None
            for n in richest_first:
                cap = vals.get(n)
                if cap is None:
                    warn(f"pretrade.tier_max_spread_bps has no entry for tier "
                         f"'{n}' (declared in liquidity_regime.tiers) — it falls "
                         f"back to the flat max_spread_bps={pt_base:.0f}, which "
                         f"may gate that tier's assets too hard")
                    continue
                if prev_cap is not None and cap < prev_cap - 1e-6:
                    fatal(f"pretrade.tier_max_spread_bps: tier '{n}' is thinner "
                          f"than '{prev_n}' but has a TIGHTER spread ceiling "
                          f"({cap:.0f} < {prev_cap:.0f}) — the live-order veto "
                          f"would gate low-volume assets HARDER than the majors")
                prev_n, prev_cap = n, cap
        else:
            c, m, mi = vals.get("core"), vals.get("mid"), vals.get("micro")
            if c is not None and m is not None and mi is not None \
                    and not (mi >= m >= c):
                warn(f"pretrade.tier_max_spread_bps not monotonic "
                     f"core<=mid<=micro ({c:.0f}/{m:.0f}/{mi:.0f})")

    # --- v10 grid ladder coherence ----------------------------------------
    gl = config.get("grid_ladder", {}) or {}
    if gl.get("enabled"):
        gl_rungs = int(gl.get("rungs", 3))
        gl_decay = float(gl.get("size_decay", 0.7))
        gl_arm = float(gl.get("p_win_arm", 0.60))
        gl_disarm = float(gl.get("p_win_disarm", 0.55))
        gl_mult = float(gl.get("spacing_vol_mult", 0.35))
        gl_floor = float(gl.get("min_spacing_bps", 8.0))
        if not (1 <= gl_rungs <= 6):
            fatal(f"grid_ladder.rungs={gl_rungs} out of [1, 6] - a deeper "
                  f"ladder than the position-slot budget (5) can never fill "
                  f"and only bloats the resting book")
        if not (0.0 < gl_decay <= 1.0):
            fatal(f"grid_ladder.size_decay={gl_decay} must be in (0, 1] - "
                  f">1 loads the LARGEST size furthest from the signal")
        if not (gl_disarm < gl_arm <= 1.0):
            fatal(f"grid_ladder p_win_disarm={gl_disarm} must be strictly "
                  f"below p_win_arm={gl_arm} (<= 1) - equal/inverted bars "
                  f"remove the hysteresis and the ladder flaps every cycle")
        if gl_mult <= 0.0 or gl_floor <= 0.0:
            fatal("grid_ladder spacing (spacing_vol_mult, min_spacing_bps) "
                  "must be positive - zero spacing stacks every rung at one "
                  "price (a single entry pretending to be a ladder)")
        gl_min_pwin = float(_f(config, "position_sizer.min_p_win", 0.55))
        if gl_arm < gl_min_pwin:
            # config-honesty note, not an operational concern (the bot trades
            # correctly): the sizer's own p(win) floor screens entries first,
            # so an arm bar below it simply arms on every approved entry.
            advisory(f"grid_ladder.p_win_arm={gl_arm} sits below the sizer's "
                     f"entry floor ({gl_min_pwin}) - the ladder arms on "
                     f"every approved entry (hysteresis still applies)")

    # --- rev-5 adaptive blocks: aggression / gate learning / exit coupling
    ia = _f(config, "position_sizer.inventory_aggression", {}) or {}
    if isinstance(ia, dict) and ia.get("enabled"):
        lb = float(ia.get("light_boost", 1.10))
        hc = float(ia.get("heavy_cut", 0.65))
        if not (1.0 <= lb <= 1.5):
            fatal(f"inventory_aggression.light_boost={lb} must be in "
                  f"[1.0, 1.5] - below 1 punishes an empty book, above "
                  f"1.5 overrides Kelly by half again")
        if not (0.2 <= hc <= 1.0):
            fatal(f"inventory_aggression.heavy_cut={hc} must be in "
                  f"[0.2, 1.0] - 0 would silently veto every entry at a "
                  f"full book (that is the inventory cap's job)")
        if float(ia.get("short_window_hours", 6)) <= 0:
            fatal("inventory_aggression.short_window_hours must be positive")
        fh = float(ia.get("full_book_heat_frac", 0.35))
        if not (0.05 <= fh <= 1.0):
            fatal(f"inventory_aggression.full_book_heat_frac={fh} out of "
                  f"[0.05, 1.0]")
    if bool(_f(config, "profit_taking.signal_decay.enabled", False)):
        sd_t = float(_f(config, "profit_taking.signal_decay.tighten_factor",
                        0.5))
        if not (0.1 <= sd_t <= 1.0):
            fatal(f"profit_taking.signal_decay.tighten_factor={sd_t} must "
                  f"be in [0.1, 1.0] - below it is an instant exit, above "
                  f"it would LOOSEN the leash on a dead thesis")
    if bool(_f(config, "profit_taking.inventory_coupling.enabled", False)):
        icb = float(_f(config, "profit_taking.inventory_coupling.max_boost",
                       0.5))
        if not (0.0 <= icb <= 1.0):
            fatal(f"profit_taking.inventory_coupling.max_boost={icb} must "
                  f"be in [0, 1] - doubling a tier close at full pressure "
                  f"is the sane ceiling")
    lw = _f(config, "signal_gates.learned_weights", {}) or {}
    if isinstance(lw, dict) and lw.get("enabled"):
        if int(lw.get("min_samples", 40)) < 5:
            warn("signal_gates.learned_weights.min_samples < 5: the Wilson "
                 "bound on so few labeled passes is noise, not evidence")
        st = float(lw.get("strength", 2.0))
        if not (0.0 <= st <= 5.0):
            fatal(f"signal_gates.learned_weights.strength={st} out of "
                  f"[0, 5]")

    # --- informed_flow (rev-3 fusion engine) coherence --------------------
    # strategies.engine defaults to "informed_flow" (config.json's shipped
    # default) - unlike signal_gates.learned_weights above, this section had
    # NO guard coverage even though it is the active decision path, not the
    # five_gate rollback. Checked unconditionally (like learned_weights) so
    # switching strategies.engine later stays covered too.
    N_COMPONENTS = 5  # flow, delta, accum, burst, trend - see evaluate_asset
    if_min_agree = int(_f(config, "informed_flow.min_agree", 3))
    if not (1 <= if_min_agree <= N_COMPONENTS):
        fatal(f"informed_flow.min_agree={if_min_agree} must be in "
              f"[1, {N_COMPONENTS}] - the engine fuses {N_COMPONENTS} "
              f"components (flow/delta/accum/burst/trend); a value outside "
              f"that range can never be satisfied or is not a real bar")
    if_evidence = float(_f(config, "informed_flow.evidence_threshold", 1.15))
    if if_evidence <= 0:
        fatal("informed_flow.evidence_threshold must be positive - it "
              "gates confirmation on |sum(w_i * s_i)|")
    if_flow_min = float(_f(config, "informed_flow.flow_min", 0.25))
    if not (0.0 <= if_flow_min <= 1.0):
        fatal(f"informed_flow.flow_min={if_flow_min} must be in [0, 1] - "
              f"s_flow is a tanh score bounded there")
    if_material = float(_f(config, "informed_flow.material_threshold", 0.10))
    if not (0.0 <= if_material <= 1.0):
        fatal(f"informed_flow.material_threshold={if_material} must be in "
              f"[0, 1] - components vote on |s_i| >= this")
    if_persist = int(_f(config, "informed_flow.persistence_evals", 3))
    if if_persist < 1:
        fatal("informed_flow.persistence_evals must be >= 1")
    if_fast = int(_f(config, "informed_flow.fast_period", 9))
    if_slow = int(_f(config, "informed_flow.slow_period", 21))
    if if_fast < 2:
        fatal("informed_flow.fast_period must be >= 2")
    if if_slow <= if_fast:
        fatal(f"informed_flow.slow_period ({if_slow}) must exceed "
              f"fast_period ({if_fast}) - EMA cross is meaningless "
              f"otherwise (the engine silently clamps this at runtime, "
              f"which is not the same as the configured intent being sane)")
    if_weights = _f(config, "informed_flow.weights", {}) or {}
    if isinstance(if_weights, dict):
        neg = [k for k, v in if_weights.items()
              if isinstance(v, (int, float)) and v < 0]
        if neg:
            warn(f"informed_flow.weights has negative entries {neg} - this "
                 f"INVERTS that component's contribution to the evidence "
                 f"sum; confirm that is intentional, not a sign typo")
    if_amove = float(_f(config, "informed_flow.absorption_move_sigmas", 1.0))
    if if_amove <= 0:
        fatal("informed_flow.absorption_move_sigmas must be positive")
    if_aad = float(_f(config, "informed_flow.absorption_ad_min", 0.15))
    if not (0.0 <= if_aad <= 1.0):
        fatal(f"informed_flow.absorption_ad_min={if_aad} must be in [0, 1]")

    # --- THALES lazy-bot insecurity model (docs/THALES.md) ----------------
    th_infl = str(_f(config, "thales.influence", "shadow")).lower()
    th_enabled = bool(_f(config, "thales.enabled", False))
    if th_infl not in ("off", "shadow", "advise"):
        fatal(f"thales.influence='{th_infl}' unknown - must be off, shadow, "
              f"or advise (the engine would silently fall back to shadow, "
              f"which is not the same as the configured intent being sane)")
    if th_infl == "advise" and not th_enabled:
        fatal("thales.influence=advise with thales.enabled=false is "
              "incoherent - advice requires a running detector bank")
    th_shade = float(_f(config, "thales.max_conf_shade", 1.15))
    if not (1.0 <= th_shade <= 1.5):
        fatal(f"thales.max_conf_shade={th_shade} must be in [1.0, 1.5] - "
              f"the advice channel is a SHADE on gate confidence, not a "
              f"signal source; beyond 1.5 it overrides the gates")
    if th_infl == "advise" and th_shade == 1.0:
        warn("thales.influence=advise with max_conf_shade=1.0 is a no-op - "
             "advice can never move confidence")
    # TH-021 evidence-concentration shade coherence (a DOWN-only trim of
    # diffuse-and-marginal confidence). Nonsense bounds silently degrade it.
    if bool(_f(config, "thales.evidence_concentration.enabled", False)):
        ec_pivot = float(_f(config, "thales.evidence_concentration.conc_pivot", 0.35))
        ec_atten = float(_f(config, "thales.evidence_concentration.max_atten", 0.15))
        ec_hi = float(_f(config, "thales.evidence_concentration.marginal_conf", 0.65))
        ec_lo = float(_f(config, "thales.evidence_concentration.floor_conf", 0.50))
        if not (0.0 < ec_pivot <= 1.0):
            fatal(f"thales.evidence_concentration.conc_pivot={ec_pivot} must be "
                  f"in (0, 1] - it is the concentration BELOW which a signal "
                  f"counts as diffuse")
        if not (0.0 <= ec_atten <= 0.5):
            fatal(f"thales.evidence_concentration.max_atten={ec_atten} must be "
                  f"in [0, 0.5] - it is a bounded confidence TRIM, not a veto")
        if not ec_hi > ec_lo:
            fatal(f"thales.evidence_concentration.marginal_conf={ec_hi} must "
                  f"exceed floor_conf={ec_lo} - the marginality ramp is "
                  f"degenerate otherwise (every signal trimmed equally)")
    th_z = float(_f(config, "thales.clockwork.z_thr", 2.33))
    if th_z < 1.5:
        fatal(f"thales.clockwork.z_thr={th_z} below 1.5 disables the "
              f"significance gate on time-of-day flow - that gate is the "
              f"anti-overfit teeth (OF-2 discipline); mining unsignificant "
              f"seasonality is exactly the lazy-bot sin this model hunts")
    for knob in ("grid.gain", "metronome.gain", "clockwork.gain",
                 "stops.pre_gain", "stops.post_gain",
                 "feed_integrity.gain", "spoof.gain"):
        gv = float(_f(config, f"thales.{knob}", 0.0))
        if gv < 0.0:
            fatal(f"thales.{knob}={gv} negative - inverted advice; flip "
                  f"the detector's exploit thesis in code, not via sign")
    # A-S inventory skew (position_sizer.inventory_skew): an unknown mode
    # silently disables a risk overlay the operator believes is on; a
    # gamma above ~2 can floor EVERY same-direction entry (the floor then
    # hides the misconfiguration); sigma_ref at/below zero divides by it.
    sk_mode = str(_f(config, "position_sizer.inventory_skew.mode",
                     "shadow")).lower()
    if sk_mode not in ("off", "shadow", "active"):
        fatal(f"position_sizer.inventory_skew.mode='{sk_mode}' unknown - "
              f"must be off, shadow, or active")
    sk_g = float(_f(config, "position_sizer.inventory_skew.gamma", 0.5))
    if sk_g < 0.0:
        fatal(f"position_sizer.inventory_skew.gamma={sk_g} negative - "
              f"inverted skew would REWARD piling onto inventory")
    elif sk_g > 2.0:
        warn(f"position_sizer.inventory_skew.gamma={sk_g} above 2: most "
             f"same-direction entries will sit at floor_mult - the skew "
             f"becomes a step function, not a gradient")
    sk_ref = float(_f(config, "position_sizer.inventory_skew.sigma_ref_pct",
                      60.0))
    if sk_ref <= 0.0:
        fatal(f"position_sizer.inventory_skew.sigma_ref_pct={sk_ref} must "
              f"be positive - it normalizes the sigma^2 amplifier")
    sk_fl = float(_f(config, "position_sizer.inventory_skew.floor_mult",
                     0.25))
    if not (0.05 <= sk_fl <= 1.0):
        fatal(f"position_sizer.inventory_skew.floor_mult={sk_fl} must be "
              f"in [0.05, 1.0] - zero would silently veto entries (that "
              f"is the inventory MANAGER's job, with its own code)")

    # TH-017 spoof-flicker coherence: a big_ratio near 1 calls ordinary
    # depth churn a spoof (every MM reprice flickers); drop/decay/thr
    # outside their unit ranges make the EWMA either never fire or latch.
    sp_br = float(_f(config, "thales.spoof.big_ratio", 3.0))
    if sp_br < 1.5:
        fatal(f"thales.spoof.big_ratio={sp_br} below 1.5 - a level barely "
              f"above median depth is ordinary MM churn, not layering; "
              f"this would shade on every reprice")
    sp_df = float(_f(config, "thales.spoof.drop_frac", 0.8))
    if not (0.0 < sp_df <= 1.0):
        fatal(f"thales.spoof.drop_frac={sp_df} must be in (0, 1] - the "
              f"fraction of a level that must vanish to count as pulled")
    sp_dc = float(_f(config, "thales.spoof.decay", 0.85))
    if not (0.0 < sp_dc < 1.0):
        fatal(f"thales.spoof.decay={sp_dc} must be in (0, 1) - at 0 the "
              f"EWMA has no memory, at 1 it never forgets a flicker")
    sp_st = float(_f(config, "thales.spoof.score_thr", 0.35))
    if not (0.0 < sp_st < 1.0):
        fatal(f"thales.spoof.score_thr={sp_st} must be in (0, 1)")
    if int(_f(config, "thales.spoof.top_levels", 5)) < 2:
        fatal("thales.spoof.top_levels below 2 cannot compute a median "
              "depth to compare against")

    # V2 reliability: min_fired is the cold-start fence. Below ~5 grades a
    # Wilson LCB is pure noise and weights would flap trade-to-trade; a
    # huge value silently disables the vindication loop (weights pinned at
    # the prior forever while claiming to be evidence-based).
    th_mf = int(_f(config, "thales.reliability.min_fired", 20))
    if th_mf < 5:
        fatal(f"thales.reliability.min_fired={th_mf} below 5 grades a "
              f"detector on a sample where the Wilson bound is noise - "
              f"weights would flap on every trade")
    elif th_mf > 500:
        warn(f"thales.reliability.min_fired={th_mf} over 500: at this "
             f"corpus's trade rate the vindication loop would never "
             f"activate - evidence-weighting in name only")
    # TH-014 feed_integrity bounds: a threshold outside [0,1] or a min_obs
    # not inside [1, window] makes the detector either never fire or fire on
    # noise. Fail loud rather than shade on a nonsense config.
    fi_thr = float(_f(config, "thales.feed_integrity.dirty_frac_thr", 0.25))
    if not (0.0 <= fi_thr <= 1.0):
        fatal(f"thales.feed_integrity.dirty_frac_thr={fi_thr} must be a "
              f"fraction in [0, 1] - it gates on a rejected-data RATE")
    fi_win = int(_f(config, "thales.feed_integrity.window", 40))
    fi_min = int(_f(config, "thales.feed_integrity.min_obs", 20))
    if fi_win < 1:
        fatal(f"thales.feed_integrity.window={fi_win} must be >= 1")
    if not (1 <= fi_min <= fi_win):
        fatal(f"thales.feed_integrity.min_obs={fi_min} must be in "
              f"[1, window={fi_win}] - beyond the window the detector can "
              f"never accumulate enough samples to ever judge")
    # TH-016 lapse hygiene: a non-positive gap threshold makes EVERY cycle
    # a lapse (permanent warmup = the engine silently disabled); negative
    # durations are nonsense; a bar fence below 2 spacings fires on ordinary
    # venue jitter and erases healthy swing context.
    lp_gap = float(_f(config, "thales.lapse.fast_gap_sec", 600.0))
    if lp_gap <= 0:
        fatal(f"thales.lapse.fast_gap_sec={lp_gap} must be > 0 - at zero "
              f"every observation counts as a lapse and THALES mutes itself "
              f"forever (a silent disable disguised as hygiene)")
    elif lp_gap < 60:
        warn(f"thales.lapse.fast_gap_sec={lp_gap} below 60s: fast cadence "
             f"is ~5s and ordinary proxy flaps last seconds - this would "
             f"spend most of its life in warmup")
    lp_wu = float(_f(config, "thales.lapse.warmup_sec", 900.0))
    if lp_wu < 0:
        fatal(f"thales.lapse.warmup_sec={lp_wu} negative - a lapse cannot "
              f"end before it is detected")
    lp_bg = float(_f(config, "thales.lapse.bar_gap_bars", 3.0))
    if lp_bg < 2:
        fatal(f"thales.lapse.bar_gap_bars={lp_bg} must be >= 2 - one "
              f"missing bar is venue jitter, not a hole; fencing on it "
              f"erases healthy swing/sweep context daily")
    lp_skew = float(_f(config, "thales.lapse.clock_skew_tol_sec", 1.0))
    if lp_skew < 0:
        fatal(f"thales.lapse.clock_skew_tol_sec={lp_skew} negative - "
              f"tolerance is a magnitude")
    elif lp_skew >= lp_gap:
        warn(f"thales.lapse.clock_skew_tol_sec={lp_skew} >= "
             f"fast_gap_sec={lp_gap}: tolerating a bigger backwards clock "
             f"jump than the forward gap called a lapse silently disables "
             f"the counter-rollback arm (the 2026-07-14 incident class)")

    # --- Smart Money Concepts features (docs/SMC.md) ----------------------
    smc_enabled = bool(_f(config, "smc.enabled", True))
    if smc_enabled:
        for fast_path, slow_path in (
                ("smc.mtf.ltf_fast_period", "smc.mtf.ltf_slow_period"),
                ("smc.mtf.htf_fast_period", "smc.mtf.htf_slow_period")):
            mtf_fast = int(_f(config, fast_path, 9))
            mtf_slow = int(_f(config, slow_path, 21))
            if mtf_fast < 2:
                fatal(f"{fast_path} must be >= 2")
            if mtf_slow <= mtf_fast:
                fatal(f"{slow_path} ({mtf_slow}) must exceed {fast_path} "
                      f"({mtf_fast}) - EMA cross is meaningless otherwise")
        for path, lo, hi in (
                ("smc.liquidity.pull_max_pct", 0.0, 100.0),
                ("smc.fvg.pull_max_pct", 0.0, 100.0),
                ("smc.fvg.min_gap_pct", 0.0, 100.0),
                ("smc.fvg.confluence_tol_pct", 0.0, 100.0),
                ("smc.volume_profile.poc_dist_cap_pct", 0.0, 100.0)):
            v = float(_f(config, path, 1.0))
            if not (lo < v <= hi):
                fatal(f"{path}={v} must be in ({lo}, {hi}] - zero or "
                      f"negative disables the feature as a silent no-op "
                      f"instead of an explicit smc.enabled=false")
        va_pct = float(_f(config, "smc.volume_profile.value_area_pct", 0.68))
        if not (0.0 < va_pct <= 1.0):
            fatal(f"smc.volume_profile.value_area_pct={va_pct} must be in "
                  f"(0, 1] - it is a fraction of total profile volume")
        n_bins = int(_f(config, "smc.volume_profile.n_bins", 24))
        if n_bins < 3:
            fatal(f"smc.volume_profile.n_bins={n_bins} must be >= 3 - a "
                  f"POC/Value-Area needs bins either side of the mode")
        for path in ("smc.pd_zone.lookback", "smc.liquidity.lookback",
                     "smc.fvg.lookback_bars",
                     "smc.volume_profile.lookback_bars"):
            lb = int(_f(config, path, 8))
            if lb < 8:
                fatal(f"{path}={lb} must be >= 8 - below that the swing/"
                      f"profile window can't distinguish structure from "
                      f"noise (matches strategies/swing_points.MIN_BARS)")

    # --- live websocket data feed (data/ws_feed.py) ----------------------
    if bool(_f(config, "websockets.enabled", False)):
        max_age = float(_f(config, "websockets.max_book_age_sec", 2.0))
        poll = float(_f(config, "system.polling_interval_sec", 5))
        if max_age <= 0:
            fatal(f"websockets.max_book_age_sec={max_age} must be > 0 - a "
                  f"non-positive staleness gate would trust a dead socket "
                  f"forever")
        if max_age > poll:
            # a cache older than one poll interval buys no freshness over
            # REST - the whole point is a book fresher than a poll cycle
            findings.append(("WARN",
                             f"websockets.max_book_age_sec={max_age} exceeds "
                             f"system.polling_interval_sec={poll} - live "
                             f"books can be older than a REST cycle, negating "
                             f"the latency edge"))
        interval = int(_f(config, "websockets.interval_ms", 100))
        if interval < 100:
            findings.append(("WARN",
                             f"websockets.interval_ms={interval} is below "
                             f"Binance.US's 100ms floor - it will be clamped "
                             f"venue-side"))
        depth = int(_f(config, "websockets.depth", 20))
        if depth not in (5, 10, 20):
            fatal(f"websockets.depth={depth} must be 5, 10, or 20 - the "
                  f"Binance.US partial-depth stream only offers those levels")
        if not (_f(config, "websockets.binanceus_symbols", []) or []):
            fatal("websockets.enabled but websockets.binanceus_symbols is "
                  "empty - nothing to subscribe to")

    # --- Kraken v2 live book stream (data/ws_feed.KrakenV2BookStream) -----
    # Wired INDEPENDENTLY of websockets.enabled (main.py gates it on
    # websockets.kraken_enabled), so its knobs need their OWN validation — they
    # were previously unguarded, so a high kraken_max_book_age_sec silently
    # served stale books into stops/imbalance/firewall AND defeated the
    # staleness watchdog (book_ts is stamped at read time, not data time).
    if bool(_f(config, "websockets.kraken_enabled", False)):
        k_age = float(_f(config, "websockets.kraken_max_book_age_sec", 5.0))
        poll = float(_f(config, "system.polling_interval_sec", 5))
        if k_age <= 0:
            fatal(f"websockets.kraken_max_book_age_sec={k_age} must be > 0 - a "
                  f"non-positive staleness gate would trust a dead socket "
                  f"forever")
        if k_age > 30.0:
            fatal(f"websockets.kraken_max_book_age_sec={k_age} must be <= 30s - "
                  f"a book that stale reads as FRESH (book_ts is stamped at read "
                  f"time) and defeats the staleness watchdog that guards stops")
        elif k_age > poll:
            findings.append(("WARN",
                             f"websockets.kraken_max_book_age_sec={k_age} "
                             f"exceeds system.polling_interval_sec={poll} - live "
                             f"books can be older than a REST cycle"))
        k_depth = int(_f(config, "websockets.kraken_depth", 10))
        if k_depth not in (10, 25, 100, 500, 1000):
            fatal(f"websockets.kraken_depth={k_depth} must be one of "
                  f"10/25/100/500/1000 - the Kraken v2 book channel only "
                  f"offers those depths")

    # --- moomoo equities context (optional, read-only) -------------------
    # Degrades to neutral on any failure, so bad config can't stop the bot -
    # but a nonsense port/interval/weight silently yields no data forever
    # instead of failing loud, so validate it like every other feed block.
    if bool(_f(config, "moomoo.enabled", False)):
        m_port = int(_f(config, "moomoo.opend_port", 11111))
        if not (1 <= m_port <= 65535):
            fatal(f"moomoo.opend_port={m_port} is not a valid TCP port "
                  f"(1-65535)")
        m_poll = float(_f(config, "moomoo.poll_minutes", 5.0))
        if m_poll <= 0:
            fatal(f"moomoo.poll_minutes={m_poll} must be > 0")
        m_to = float(_f(config, "moomoo.connect_timeout_sec", 5.0))
        if m_to <= 0:
            fatal(f"moomoo.connect_timeout_sec={m_to} must be > 0 - a "
                  f"non-positive TCP-probe timeout never completes")
        tickers = _f(config, "moomoo.tickers", []) or []
        if not tickers:
            findings.append(("WARN",
                             "moomoo.enabled but moomoo.tickers is empty - "
                             "the basket will always be unavailable/neutral"))
        for t in tickers:
            if not isinstance(t, dict) or not t.get("code"):
                fatal(f"moomoo.tickers entry {t!r} missing a 'code'")
            elif float(t.get("weight", 1.0)) < 0:
                fatal(f"moomoo ticker {t.get('code')} has negative weight "
                      f"{t.get('weight')} - flip the basket thesis in code, "
                      f"not via a negative weight")

    # --- hedging ---------------------------------------------------------
    h_beta_floor = float(_f(config, "hedging.beta_floor", 0.1))
    h_eq_frac = float(_f(config, "hedging.max_equity_frac", 0.5))
    if not (0.0 <= h_beta_floor < 1.0):
        fatal(f"hedging.beta_floor={h_beta_floor} must be in [0, 1) - "
              f"betas at/above 1 are never 'unreliable'")
    if not (0.0 < h_eq_frac <= 1.0):
        fatal(f"hedging.max_equity_frac={h_eq_frac} must be in (0, 1] - "
              f"a single hedge larger than equity is leverage in disguise")

    # --- exploration coherence: a DRY-RUN learning entry bumps p_win to
    # exploration.p_win for SIZING; if that sits at/below the net-Kelly
    # breakeven the sizer SZ-030-vetoes EVERY exploration entry and the
    # learning lane goes silent. Observed 2026-07-15: the cost-honest
    # rt_cost (maker+taker) raised the breakeven to ~0.632 while p_win stayed
    # 0.62 -> zero exploration trades, flat equity, model starved of labels.
    if bool(_f(config, "ml.exploration.enabled", False)):
        ep = float(_f(config, "ml.exploration.p_win", 0.62))
        try:
            from risk.position_sizer import payoff_ratio_from_config
            pt = config.get("pretrade", {}) or {}
            rt = (float(pt.get("maker_fee_bps", 25.0))
                  + float(pt.get("taker_fee_bps", 40.0))) / 100.0
            b_net = payoff_ratio_from_config(
                config.get("profit_taking", {}) or {},
                config.get("risk", {}) or {}, rt_cost_pct=rt)
            breakeven = 1.0 / (1.0 + b_net)
        except Exception:
            breakeven = None
        if breakeven is not None and ep <= breakeven:
            fatal(f"ml.exploration.p_win={ep:.3f} is at/below the net-Kelly "
                  f"breakeven {breakeven:.3f} (maker+taker round-trip cost) - "
                  f"every exploration entry SZ-030-vetoes and the DRY-RUN "
                  f"learning lane goes silent. Raise p_win above the breakeven.")

    # --- sizer entry-bar coherence: min_p_win is the EARLY p(win) gate, but the
    # net-Kelly step floors size at 0 below the breakeven (SZ-030) regardless.
    # If min_p_win sits BELOW that breakeven it is a PHANTOM bar — the headline
    # "minimum win prob" is not the effective one (the breakeven is), and every
    # signal in [min_p_win, breakeven) passes the gate only to die SZ-030 a step
    # later. WARN (not fatal — the bot trades correctly) so the configured
    # number is honest. exploration.p_win IS guarded above; min_p_win was not.
    mpw = float(_f(config, "position_sizer.min_p_win", 0.55))
    try:
        from risk.position_sizer import payoff_ratio_from_config
        pt = config.get("pretrade", {}) or {}
        rt = (float(pt.get("maker_fee_bps", 25.0))
              + float(pt.get("taker_fee_bps", 40.0))) / 100.0
        be = 1.0 / (1.0 + payoff_ratio_from_config(
            config.get("profit_taking", {}) or {},
            config.get("risk", {}) or {}, rt_cost_pct=rt))
    except Exception:
        be = None
    if be is not None and mpw < be - 1e-6:
        advisory(
            f"position_sizer.min_p_win={mpw:.3f} is below the net-Kelly "
            f"breakeven {be:.3f}, so the EFFECTIVE entry bar is {be:.3f} (the "
            f"sizer floors Kelly at 0 below it, SZ-030) - the configured "
            f"min_p_win is not the real minimum. Raise it to >= the breakeven "
            f"to make the bar honest, or keep it as an intentional soft floor.")

    return findings


def enforce(config: dict, alerts=None) -> list:
    """Run validation; log everything; raise ConfigError on FATAL findings
    when the config is live. Dry-run downgrades FATAL to a loud warning -
    paper trading exists to catch exactly these mistakes."""
    findings = validate(config)
    dry_run = bool(_f(config, "system.dry_run", True))
    fatals = [m for s, m in findings if s == "FATAL"]
    _levels = {"FATAL": log.critical, "WARN": log.warning,
               "ADVISORY": log.info}
    for sev, msg in findings:
        _levels.get(sev, log.warning)(f"config: {msg}")
    if fatals and alerts is not None:
        alerts.fire("config_fatal", f"{len(fatals)} fatal config finding(s); "
                    f"first: {fatals[0]}")
    if fatals and not dry_run:
        raise ConfigError(
            f"{len(fatals)} fatal config finding(s) - refusing to start "
            f"live. First: {fatals[0]}")
    return findings
