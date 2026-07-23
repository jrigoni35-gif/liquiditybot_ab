"""config_guard batch W2-7: unguarded tunables that either crash live
(markout window, system.slow_cycle_every_n), silently disable a real gate
(pretrade EV ratio, participation clamp), pin exits at unfillable prices
(exit-escalation cap below the base slippage), or invert governor logic
(watchdog warn/critical, leverage margin band, monitor judge window).

vol_regime and sentiment threshold orderings are shading-only paths (the
bot still trades correctly on an inverted config, it just misclassifies a
regime/mood) - WARN, not FATAL, per the audit's explicit call.
"""
import json
from pathlib import Path

from core.config_guard import validate

_CFG = json.loads((Path(__file__).resolve().parents[1] / "config.json")
                  .read_text(encoding="utf-8"))


def _fatals(cfg):
    return [m for sev, m in validate(cfg) if sev == "FATAL"]


def _warns(cfg):
    return [m for sev, m in validate(cfg) if sev == "WARN"]


def test_shipped_config_has_no_new_fatals():
    # baseline: the whole W2-7 batch must ship clean against config.json
    assert not _fatals(_CFG)


# --- 1. markout --------------------------------------------------------------

def test_markout_window_zero_is_fatal():
    cfg = {"system": {"dry_run": True}, "markout": {"window": 0}}
    assert any("markout.window" in m for m in _fatals(cfg))


def test_markout_window_negative_is_fatal():
    cfg = {"system": {"dry_run": True}, "markout": {"window": -1}}
    assert any("markout.window" in m for m in _fatals(cfg))


def test_markout_empty_horizons_when_enabled_is_fatal():
    cfg = {"system": {"dry_run": True},
           "markout": {"enabled": True, "horizons_sec": []}}
    assert any("horizons_sec" in m for m in _fatals(cfg))


def test_markout_nonpositive_horizon_is_fatal():
    cfg = {"system": {"dry_run": True},
           "markout": {"enabled": True, "horizons_sec": [5.0, -1.0]}}
    assert any("horizons_sec" in m for m in _fatals(cfg))


def test_markout_negative_grace_is_fatal():
    cfg = {"system": {"dry_run": True}, "markout": {"grace_sec": -1.0}}
    assert any("grace_sec" in m for m in _fatals(cfg))


def test_markout_disabled_ignores_bad_values():
    cfg = {"system": {"dry_run": True},
           "markout": {"enabled": False, "window": 0, "horizons_sec": [],
                       "grace_sec": -5}}
    assert not any("markout" in m for m in _fatals(cfg))


def test_markout_shipped_defaults_clean():
    assert not any("markout" in m for m in _fatals(_CFG))


# --- 2. watchdog ---------------------------------------------------------------

def test_watchdog_inverted_stale_thresholds_is_fatal():
    cfg = {"system": {"dry_run": True},
           "watchdog": {"stale_warn_sec": 120, "stale_critical_sec": 30}}
    assert any("stale" in m for m in _fatals(cfg))


def test_watchdog_equal_stale_thresholds_is_fatal():
    cfg = {"system": {"dry_run": True},
           "watchdog": {"stale_warn_sec": 60, "stale_critical_sec": 60}}
    assert any("stale" in m for m in _fatals(cfg))


def test_watchdog_nonpositive_velocity_window_is_fatal():
    cfg = {"system": {"dry_run": True},
           "watchdog": {"pnl_velocity_window_sec": 0}}
    assert any("pnl_velocity_window_sec" in m for m in _fatals(cfg))


def test_watchdog_nonpositive_velocity_drop_is_fatal():
    cfg = {"system": {"dry_run": True},
           "watchdog": {"pnl_velocity_max_drop_pct": 0}}
    assert any("pnl_velocity_max_drop_pct" in m for m in _fatals(cfg))


def test_watchdog_nonpositive_velocity_cooldown_is_fatal():
    cfg = {"system": {"dry_run": True},
           "watchdog": {"pnl_velocity_cooldown_sec": -1}}
    assert any("pnl_velocity_cooldown_sec" in m for m in _fatals(cfg))


def test_watchdog_nonpositive_tick_jump_is_fatal():
    cfg = {"system": {"dry_run": True},
           "watchdog": {"tick_jump_quarantine_pct": 0}}
    assert any("tick_jump_quarantine_pct" in m for m in _fatals(cfg))


def test_watchdog_nonpositive_equity_drift_is_fatal():
    cfg = {"system": {"dry_run": True},
           "watchdog": {"max_equity_drift_pct": 0}}
    assert any("max_equity_drift_pct" in m for m in _fatals(cfg))


def test_watchdog_disabled_ignores_bad_values():
    cfg = {"system": {"dry_run": True},
           "watchdog": {"enabled": False, "stale_warn_sec": 999,
                       "stale_critical_sec": 1, "max_equity_drift_pct": 0}}
    assert not any("watchdog" in m for m in _fatals(cfg))


def test_watchdog_shipped_defaults_clean():
    assert not any("watchdog" in m for m in _fatals(_CFG))


def test_watchdog_tick_confirm_ratio_shipped():
    # default alignment: watchdog.tick_confirm_ratio (0.5) must be present
    # in config.json so deleting it can't silently change behavior
    assert _CFG["watchdog"]["tick_confirm_ratio"] == 0.5


# --- 3. pretrade EV / participation / staleness -------------------------------

def test_pretrade_edge_cost_ratio_below_one_is_fatal():
    cfg = {"system": {"dry_run": True},
           "pretrade": {"min_edge_cost_ratio": 0.5}}
    assert any("min_edge_cost_ratio" in m for m in _fatals(cfg))


def test_pretrade_participation_zero_is_fatal():
    cfg = {"system": {"dry_run": True},
           "pretrade": {"max_participation_of_depth": 0.0}}
    assert any("max_participation_of_depth" in m for m in _fatals(cfg))


def test_pretrade_participation_above_one_is_fatal():
    cfg = {"system": {"dry_run": True},
           "pretrade": {"max_participation_of_depth": 1.5}}
    assert any("max_participation_of_depth" in m for m in _fatals(cfg))


def test_pretrade_nonpositive_staleness_is_fatal():
    cfg = {"system": {"dry_run": True},
           "pretrade": {"max_data_staleness_ms": 0}}
    assert any("max_data_staleness_ms" in m for m in _fatals(cfg))


def test_pretrade_negative_impact_eta_is_fatal():
    cfg = {"system": {"dry_run": True}, "pretrade": {"impact_eta": -0.1}}
    assert any("impact_eta" in m for m in _fatals(cfg))


def test_pretrade_shipped_defaults_clean():
    assert not any(("min_edge_cost_ratio" in m or "max_participation" in m
                    or "max_data_staleness_ms" in m or "impact_eta" in m)
                   for m in _fatals(_CFG))


# --- 4. exit escalation / mark staleness --------------------------------------

def test_escalation_cap_below_base_slippage_is_fatal():
    cfg = {"system": {"dry_run": True},
           "risk": {"max_slippage_pct": 2.0,
                    "exit_escalation": {"max_slippage_cap_pct": 1.0}}}
    assert any("max_slippage_cap_pct" in m for m in _fatals(cfg))


def test_escalation_market_after_attempts_negative_is_fatal():
    cfg = {"system": {"dry_run": True},
           "risk": {"exit_escalation": {"market_after_attempts": -1}}}
    assert any("market_after_attempts" in m for m in _fatals(cfg))


def test_escalation_market_after_attempts_absurd_is_fatal():
    cfg = {"system": {"dry_run": True},
           "risk": {"exit_escalation": {"market_after_attempts": 21}}}
    assert any("market_after_attempts" in m for m in _fatals(cfg))


def test_mark_stale_sec_nonpositive_is_fatal():
    cfg = {"system": {"dry_run": True}, "risk": {"mark_stale_sec": 0}}
    assert any("mark_stale_sec" in m for m in _fatals(cfg))


def test_exits_shipped_defaults_clean():
    assert not any(("max_slippage_cap_pct" in m or "market_after_attempts" in m
                    or "mark_stale_sec" in m) for m in _fatals(_CFG))


# --- 5. cycle / order timing ---------------------------------------------------

def test_slow_cycle_every_n_zero_is_fatal():
    cfg = {"system": {"dry_run": True, "slow_cycle_every_n": 0}}
    assert any("slow_cycle_every_n" in m for m in _fatals(cfg))


def test_order_timeout_at_or_below_poll_cadence_is_fatal():
    cfg = {"system": {"dry_run": True, "polling_interval_sec": 5},
           "order_manager": {"order_timeout_sec": 5}}
    assert any("order_timeout_sec" in m for m in _fatals(cfg))


def test_order_timeout_zero_is_fatal():
    cfg = {"system": {"dry_run": True, "polling_interval_sec": 5},
           "order_manager": {"order_timeout_sec": 0}}
    assert any("order_timeout_sec" in m for m in _fatals(cfg))


def test_max_reprices_negative_is_fatal():
    cfg = {"system": {"dry_run": True}, "order_manager": {"max_reprices": -1}}
    assert any("max_reprices" in m for m in _fatals(cfg))


def test_min_fill_ratio_out_of_range_is_fatal():
    for bad in (-0.1, 1.5):
        cfg = {"system": {"dry_run": True},
               "order_manager": {"min_fill_ratio": bad}}
        assert any("min_fill_ratio" in m for m in _fatals(cfg)), bad


def test_cycle_order_timing_shipped_defaults_clean():
    assert not any(("slow_cycle_every_n" in m or "order_timeout_sec" in m
                    or "max_reprices" in m or "min_fill_ratio" in m)
                   for m in _fatals(_CFG))


# --- 6. leverage ----------------------------------------------------------------

def test_leverage_target_vol_zero_is_fatal():
    cfg = {"system": {"dry_run": True}, "leverage": {"target_vol_annual_pct": 0}}
    assert any("target_vol_annual_pct" in m for m in _fatals(cfg))


def test_leverage_min_leverage_negative_is_fatal():
    cfg = {"system": {"dry_run": True}, "leverage": {"min_leverage": -0.1}}
    assert any("min_leverage" in m for m in _fatals(cfg))


def test_leverage_inverted_margin_band_is_fatal_when_use_margin():
    cfg = {"system": {"dry_run": True},
           "leverage": {"use_margin": True, "margin_scale_below_pct": 150,
                       "margin_block_below_pct": 200}}
    assert any("margin_block_below_pct" in m for m in _fatals(cfg))


def test_leverage_inverted_margin_band_ignored_without_use_margin():
    # use_margin=false never reads margin_scale/block_below_pct at all
    # (risk/leverage.py's elif branch is gated on self.use_margin) - flagging
    # it here would be a false positive on a purely-spot config.
    cfg = {"system": {"dry_run": True},
           "leverage": {"use_margin": False, "margin_scale_below_pct": 150,
                       "margin_block_below_pct": 200}}
    assert not any("margin_block_below_pct" in m for m in _fatals(cfg))


def test_leverage_shipped_defaults_clean():
    assert not any(("target_vol_annual_pct" in m or "min_leverage" in m
                    or "margin_block_below_pct" in m) for m in _fatals(_CFG))


# --- 7. monitor coherence --------------------------------------------------------

def test_monitor_min_trades_above_window_is_fatal():
    cfg = {"system": {"dry_run": True},
           "ml": {"monitor": {"window_trades": 10, "min_trades_to_judge": 15}}}
    assert any("min_trades_to_judge" in m for m in _fatals(cfg))


def test_monitor_window_trades_zero_is_fatal():
    cfg = {"system": {"dry_run": True}, "ml": {"monitor": {"window_trades": 0}}}
    assert any("window_trades" in m for m in _fatals(cfg))


def test_monitor_shrinkage_inverted_is_fatal():
    cfg = {"system": {"dry_run": True},
           "ml": {"monitor": {"shrinkage_base": 0.8, "shrinkage_max": 0.3}}}
    assert any("shrinkage" in m for m in _fatals(cfg))


def test_monitor_kelly_mult_min_out_of_range_is_fatal():
    for bad in (0.0, 1.5):
        cfg = {"system": {"dry_run": True},
               "ml": {"monitor": {"kelly_mult_min": bad}}}
        assert any("kelly_mult_min" in m for m in _fatals(cfg)), bad


def test_monitor_stop_widen_max_below_one_is_fatal():
    cfg = {"system": {"dry_run": True},
           "ml": {"monitor": {"stop_widen_max": 0.5}}}
    assert any("stop_widen_max" in m for m in _fatals(cfg))


def test_monitor_shipped_defaults_clean():
    assert not any(("min_trades_to_judge" in m or "window_trades" in m
                    or "shrinkage" in m or "kelly_mult_min" in m
                    or "stop_widen_max" in m) for m in _fatals(_CFG))


# --- 8. vol_regime / sentiment ordering (WARN, shading-only) -------------------

def test_vol_regime_inverted_percentiles_warns_not_fatal():
    cfg = {"system": {"dry_run": True},
           "vol_regime": {"low_pct": 90, "elevated_pct": 70, "extreme_pct": 30}}
    assert any("vol_regime" in m for m in _warns(cfg))
    assert not any("vol_regime" in m for m in _fatals(cfg))


def test_sentiment_stress_calm_above_confirm_warns_not_fatal():
    cfg = {"system": {"dry_run": True},
           "sentiment": {"filter": {"stress_calm_threshold": 0.8,
                                    "stress_confirm_threshold": 0.3}}}
    assert any("stress_calm" in m or "stress_confirm" in m
               for m in _warns(cfg))
    assert not any(("stress_calm" in m or "stress_confirm" in m)
                   for m in _fatals(cfg))


def test_sentiment_fear_euphoria_wrong_sign_warns_not_fatal():
    cfg = {"system": {"dry_run": True},
           "sentiment": {"fear_threshold": 0.1, "euphoria_threshold": -0.1}}
    assert any("fear_threshold" in m or "euphoria_threshold" in m
               for m in _warns(cfg))
    assert not any(("fear_threshold" in m or "euphoria_threshold" in m)
                   for m in _fatals(cfg))


def test_vol_regime_sentiment_shipped_defaults_clean_of_warns():
    assert not any("vol_regime" in m for m in _warns(_CFG))
    assert not any(("stress_calm" in m or "stress_confirm" in m
                    or "fear_threshold" in m or "euphoria_threshold" in m)
                   for m in _warns(_CFG))
