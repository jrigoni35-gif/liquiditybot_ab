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

    dry_run = bool(_f(config, "system.dry_run", True))

    # --- fees ----------------------------------------------------------
    pt_maker = float(_f(config, "pretrade.maker_fee_bps", 16.0))
    pt_taker = float(_f(config, "pretrade.taker_fee_bps", 26.0))
    om_maker = float(_f(config, "order_manager.maker_fee_bps", 16.0))
    om_taker = float(_f(config, "order_manager.taker_fee_bps", 26.0))
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

    # --- capital / risk ladder ------------------------------------------
    start_cap = float(_f(config, "capital_management.starting_capital_usd", 0))
    if start_cap <= 0 and not dry_run:
        fatal("capital_management.starting_capital_usd must be > 0 in live "
              "mode (the dry-run '0 -> $10k paper' default never applies to "
              "real money)")
    daily = float(_f(config, "capital_management.daily_loss_limit_pct", 5))
    hard = float(_f(config, "capital_management.hard_stop_drawdown_pct", 15))
    if daily <= 0 or hard <= 0:
        fatal("loss limits must be positive")
    elif daily >= hard:
        fatal(f"daily_loss_limit_pct ({daily}) must be below "
              f"hard_stop_drawdown_pct ({hard}) - the daily brake must "
              f"engage before the parachute")

    soft = float(_f(config, "inventory.soft_cap_pct_of_equity", 15))
    hardc = float(_f(config, "inventory.hard_cap_pct_of_equity", 25))
    if soft >= hardc:
        fatal(f"inventory soft cap ({soft}) must be below hard cap ({hardc})")

    max_pos = float(_f(config,
                       "capital_management.max_position_size_pct_of_capital", 10))
    if not (0 < max_pos <= 100):
        fatal("max_position_size_pct_of_capital out of (0, 100]")

    # untradeable-by-construction check: if the largest permitted position
    # is below every minimum ticket, the bot will veto 100% of entries and
    # burn API quota doing nothing. Not dangerous - just pointless.
    min_ticket = max(float(_f(config, "position_sizer.min_ticket_usd", 25)),
                     float(_f(config, "pretrade.min_order_usd", 25)))
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

    lev = float(_f(config, "leverage.region_max_leverage", 10))
    if lev < 1:
        fatal("leverage.region_max_leverage below 1")
    if bool(_f(config, "leverage.use_margin", False)) and dry_run is False:
        warn("margin ENABLED in live config - confirm this is intentional")

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
    esc = _f(config, "risk.exit_escalation", {}) or {}
    mult = float(esc.get("widen_mult", 2.0))
    if mult < 1.0:
        fatal("risk.exit_escalation.widen_mult must be >= 1")

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
    hard = float(_f(config, "risk.hard_stop_drawdown_pct", 15))
    if d_b > 0 and hard > 0 and d_b >= hard:
        fatal("risk_protocols.budget.daily_loss_budget_pct must sit below "
              "risk.hard_stop_drawdown_pct - the taper must engage before "
              "the kill switch")
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
        be_buf_bps = float(_f(config, "profit_taking.be_buffer_bps", 6.0)) \
            + 2.0 * float(_f(config, "profit_taking.est_fee_bps", 0.0))
        if arm * 100.0 <= be_buf_bps:
            warn(f"give_back.arm_gain_pct={arm}% arms inside the "
                 f"break-even buffer ({be_buf_bps:.0f}bps) - the locked "
                 f"share of such small moves is fee noise")

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

    # --- hedging ---------------------------------------------------------
    h_beta_floor = float(_f(config, "hedging.beta_floor", 0.1))
    h_eq_frac = float(_f(config, "hedging.max_equity_frac", 0.5))
    if not (0.0 <= h_beta_floor < 1.0):
        fatal(f"hedging.beta_floor={h_beta_floor} must be in [0, 1) - "
              f"betas at/above 1 are never 'unreliable'")
    if not (0.0 < h_eq_frac <= 1.0):
        fatal(f"hedging.max_equity_frac={h_eq_frac} must be in (0, 1] - "
              f"a single hedge larger than equity is leverage in disguise")

    return findings


def enforce(config: dict, alerts=None) -> list:
    """Run validation; log everything; raise ConfigError on FATAL findings
    when the config is live. Dry-run downgrades FATAL to a loud warning -
    paper trading exists to catch exactly these mistakes."""
    findings = validate(config)
    dry_run = bool(_f(config, "system.dry_run", True))
    fatals = [m for s, m in findings if s == "FATAL"]
    for sev, msg in findings:
        (log.critical if sev == "FATAL" else log.warning)(f"config: {msg}")
    if fatals and alerts is not None:
        alerts.fire("config_fatal", f"{len(fatals)} fatal config finding(s); "
                    f"first: {fatals[0]}")
    if fatals and not dry_run:
        raise ConfigError(
            f"{len(fatals)} fatal config finding(s) - refusing to start "
            f"live. First: {fatals[0]}")
    return findings
