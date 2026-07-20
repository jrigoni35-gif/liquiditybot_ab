"""
tests/test_incident_metrics.py — gc_pusher exports the fault/health signals the
incidents dashboard needs. Regression for the dark-counter audit: firewall
tallies + latched fault, order-manager rejects (OM-021/OM-050), ML fault
counters, retrain failures, watchdog trips, kill-switch level, moomoo
availability and the reason-code frequency ledger were all tracked internally
but never pushed to Grafana.
"""
import json
import time

import pytest

import scripts.gc_pusher as gp


def _names(metrics):
    return {m["name"] for m in metrics}


def _by_name(metrics, name):
    return [m for m in metrics if m["name"] == name]


def test_collect_thales_excludes_bool_values_and_survives_malformed(tmp_path):
    # the THALES metric guard must exclude bool VALUES (bool is an int
    # subclass) and never crash on a malformed (non-dict) asset entry
    status = {"written_at": time.time(),
              "thales": {"assets": {"BTC": {"grid": True, "metronome": 0.5},
                                    "ETH": "garbage"}}}
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    m = gp.collect(str(p))                       # must not raise on ETH='garbage'
    met = _by_name(m, "liquiditybot_thales_metronome")
    assert met and met[0]["gauge"]["dataPoints"][0]["asDouble"] == pytest.approx(0.5)
    assert not _by_name(m, "liquiditybot_thales_grid")   # bool value excluded


def test_collect_emits_fault_and_health_metrics(tmp_path):
    status = {
        "written_at": time.time(),
        "halted": False, "entries_enabled": True, "audit_dropped_writes": 0,
        "monitor": {"level": 1, "drift_share": 0.42, "brier": 0.31,
                    "baseline_brier": 0.24, "calibration_gap": 0.09,
                    "window_trades": 22},
        "ml": {"model_fallbacks": 7, "infer_faults": 2, "contract_failed": 0,
               "smc_faults": 1, "retrain_failures": 3, "history_rows": 268},
        "moomoo": {"options_available": True, "available": True},
        "watchdog": {"entries_blocked": True, "critical_stale": False,
                     "velocity_tripped": False, "divergent": ["BTC"],
                     "stale_assets": []},
        "firewall": {"fault": None,
                     "counters": {"FW-040": 5, "FW-020": 2, "rejected": 7}},
        "order_manager": {"venue_rejects": 4, "deadman_failures": 0},
        "code_stats": {"by_prefix": {"SZ": 120, "PT": 30, "FW": 7}},
    }
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    metrics = gp.collect(str(p))
    names = _names(metrics)
    for expect in ("liquiditybot_halted", "liquiditybot_entries_enabled",
                   "liquiditybot_monitor_level",
                   "liquiditybot_ml_drift_share",
                   "liquiditybot_ml_brier",
                   "liquiditybot_ml_baseline_brier",
                   "liquiditybot_ml_model_fallbacks",
                   "liquiditybot_ml_retrain_failures",
                   "liquiditybot_audit_dropped_writes",
                   "liquiditybot_moomoo_options_available",
                   "liquiditybot_watchdog_entries_blocked",
                   "liquiditybot_firewall_fault", "liquiditybot_firewall_count",
                   "liquiditybot_order_venue_rejects",
                   "liquiditybot_order_deadman_failures",
                   "liquiditybot_code_count"):
        assert expect in names, f"missing metric {expect}"

    lvl = _by_name(metrics, "liquiditybot_monitor_level")[0]
    assert lvl["gauge"]["dataPoints"][0]["asDouble"] == 1.0

    drift = _by_name(metrics, "liquiditybot_ml_drift_share")[0]
    assert drift["gauge"]["dataPoints"][0]["asDouble"] == 0.42

    # outcome side: brier + baseline both present when the window is full, so
    # the alert can compute brier - baseline (predictions worse than base rate)
    brier = _by_name(metrics, "liquiditybot_ml_brier")[0]
    assert brier["gauge"]["dataPoints"][0]["asDouble"] == 0.31
    base = _by_name(metrics, "liquiditybot_ml_baseline_brier")[0]
    assert base["gauge"]["dataPoints"][0]["asDouble"] == 0.24

    codes = {dp["attributes"][0]["value"]["stringValue"]
             for m in _by_name(metrics, "liquiditybot_firewall_count")
             for dp in m["gauge"]["dataPoints"]}
    assert "FW-040" in codes

    prefixes = {dp["attributes"][0]["value"]["stringValue"]
                for m in _by_name(metrics, "liquiditybot_code_count")
                for dp in m["gauge"]["dataPoints"]}
    assert {"SZ", "PT", "FW"} <= prefixes


def _val(metrics, name, **labels):
    """Return the single gauge value for name with the given label set."""
    for mtr in metrics:
        if mtr["name"] != name:
            continue
        dp = mtr["gauge"]["dataPoints"][0]
        got = {a["key"]: a["value"]["stringValue"] for a in dp.get("attributes", [])}
        if all(got.get(k) == v for k, v in labels.items()):
            return dp["asDouble"]
    return None


def test_collect_emits_per_instrument_positions(tmp_path):
    # 2 ETH long lots + 1 BTC short + a hedge that must NOT be counted
    status = {
        "written_at": time.time(), "equity": 5000.0,
        "positions": [
            {"symbol": "ETH/USD", "direction": "long", "entry": 2000.0,
             "mark": 2020.0, "size": 0.01, "stop": 1960.0, "upnl_usd": 0.20,
             "tiers_fired": 1, "age_h": 2.0, "p_win": 0.70},
            {"symbol": "ETH/USD", "direction": "long", "entry": 2010.0,
             "mark": 2020.0, "size": 0.01, "stop": 1970.0, "upnl_usd": 0.10,
             "tiers_fired": 0, "age_h": 5.0, "p_win": 0.60},
            {"symbol": "BTC/USD", "direction": "short", "entry": 60000.0,
             "mark": 59000.0, "size": 0.001, "stop": 61000.0, "upnl_usd": 1.0,
             "tiers_fired": 2, "age_h": 1.0, "p_win": 0.80},
            {"symbol": "SUI/USD", "direction": "long", "entry": 1.0,
             "mark": 1.0, "size": 100.0, "stop": 0.95, "upnl_usd": 0.0,
             "hedge": True},           # hedge: excluded
        ],
    }
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    m = gp.collect(str(p))

    # ETH long is the NET of its two lots
    assert _val(m, "liquiditybot_position_notional_usd",
                symbol="ETH/USD", side="long") == pytest.approx(40.4)
    assert _val(m, "liquiditybot_position_upnl_usd",
                symbol="ETH/USD", side="long") == pytest.approx(0.30)
    assert _val(m, "liquiditybot_position_lots",
                symbol="ETH/USD", side="long") == 2.0
    assert _val(m, "liquiditybot_position_tiers_fired",
                symbol="ETH/USD", side="long") == 1.0     # max of the lots
    assert _val(m, "liquiditybot_position_age_hours",
                symbol="ETH/USD", side="long") == 5.0      # oldest lot
    # BTC short R-multiple = upnl 1.0 / risk (|60000-61000|*0.001 = 1.0)
    assert _val(m, "liquiditybot_position_r_multiple",
                symbol="BTC/USD", side="short") == pytest.approx(1.0)

    # risk-on banner nets everything (hedge excluded)
    assert _val(m, "liquiditybot_open_upnl_usd") == pytest.approx(1.30)
    assert _val(m, "liquiditybot_gross_exposure_usd") == pytest.approx(99.4)
    assert _val(m, "liquiditybot_open_risk_usd") == pytest.approx(1.8)
    assert _val(m, "liquiditybot_gross_exposure_pct") == pytest.approx(99.4 / 5000 * 100)
    # the hedge contributed nothing
    assert _val(m, "liquiditybot_position_notional_usd",
                symbol="SUI/USD", side="long") is None


def test_collect_emits_exec_quality(tmp_path):
    status = {
        "written_at": time.time(),
        "order_manager": {"venue_rejects": 1, "deadman_failures": 0,
                          "latency_ms": 42.5, "maker_fills": 7,
                          "taker_fills": 3, "maker_share": 0.7,
                          "maker_notional_usd": 500.0,
                          "taker_notional_usd": 200.0,
                          "avg_slip_bps": -1.2, "worst_slip_bps": 8.0},
    }
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    m = gp.collect(str(p))
    assert _val(m, "liquiditybot_order_maker_share") == pytest.approx(0.7)
    assert _val(m, "liquiditybot_order_avg_slip_bps") == pytest.approx(-1.2)
    assert _val(m, "liquiditybot_order_worst_slip_bps") == pytest.approx(8.0)
    assert _val(m, "liquiditybot_order_latency_ms") == pytest.approx(42.5)
    assert _val(m, "liquiditybot_order_maker_fills") == 7.0

    # cold OM (no fills): None fields must NOT emit
    p2 = tmp_path / "status2.json"
    p2.write_text(json.dumps({
        "written_at": time.time(),
        "order_manager": {"venue_rejects": 0, "deadman_failures": 0,
                          "latency_ms": 0.0, "maker_fills": 0,
                          "taker_fills": 0, "maker_share": None,
                          "avg_slip_bps": None, "worst_slip_bps": None}}),
        encoding="utf-8")
    m2 = gp.collect(str(p2))
    assert _val(m2, "liquiditybot_order_maker_share") is None
    assert _val(m2, "liquiditybot_order_avg_slip_bps") is None


def test_collect_emits_performance(tmp_path):
    status = {
        "written_at": time.time(), "equity": 5000.0,
        "performance": {
            "overall": {"trades": 20, "win_rate": 0.55, "profit_factor": 1.8,
                        "expectancy_usd": 2.3, "expectancy_r": 0.4,
                        "payoff_ratio": None, "sharpe": 0.9,
                        "cur_loss_streak": 2, "max_loss_streak": 4,
                        "net_usd": 46.0},
            "by_asset": {"BTC": {"trades": 8, "win_rate": 0.5,
                                 "profit_factor": 1.2, "net_usd": 5.0,
                                 "cur_loss_streak": 3, "max_loss_streak": 3}},
        },
    }
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    m = gp.collect(str(p))
    assert _val(m, "liquiditybot_perf_win_rate") == pytest.approx(0.55)
    assert _val(m, "liquiditybot_perf_profit_factor") == pytest.approx(1.8)
    assert _val(m, "liquiditybot_perf_max_loss_streak") == 4.0
    assert _val(m, "liquiditybot_perf_net_usd") == pytest.approx(46.0)
    # None-valued payoff_ratio must NOT emit
    assert _val(m, "liquiditybot_perf_payoff_ratio") is None
    # per-asset, labeled — the circuit-breaker's future input
    assert _val(m, "liquiditybot_perf_asset_win_rate", asset="BTC") == pytest.approx(0.5)
    assert _val(m, "liquiditybot_perf_asset_cur_loss_streak", asset="BTC") == 3.0


def test_collect_emits_circuit_breaker(tmp_path):
    p = tmp_path / "status.json"
    p.write_text(json.dumps({
        "written_at": time.time(),
        "circuit_breaker": {"enabled": True, "loss_streak": 4,
                            "streaks": {"ETH": 2},
                            "tripped": {"BTC": 4.5}}}), encoding="utf-8")
    m = gp.collect(str(p))
    assert _val(m, "liquiditybot_cb_tripped_count") == 1.0
    assert _val(m, "liquiditybot_cb_paused_hours_left", asset="BTC") == pytest.approx(4.5)
    assert _val(m, "liquiditybot_cb_loss_streak", asset="ETH") == 2.0
    # absent section -> nothing, no crash
    p2 = tmp_path / "s2.json"
    p2.write_text(json.dumps({"written_at": time.time()}), encoding="utf-8")
    assert _val(gp.collect(str(p2)), "liquiditybot_cb_tripped_count") is None


def test_collect_emits_risk_protocols(tmp_path):
    p = tmp_path / "status.json"
    p.write_text(json.dumps({
        "written_at": time.time(),
        "risk_protocols": {"daily_budget_used_frac": 0.3,
                           "weekly_budget_used_frac": 0.12,
                           "taper_mult": 1.0, "heat_frac": 0.05,
                           "heat_cap_frac": 0.35,
                           "dd_throttle_mult": 0.92}}), encoding="utf-8")
    m = gp.collect(str(p))
    assert _val(m, "liquiditybot_rp_daily_budget_used_frac") == pytest.approx(0.3)
    assert _val(m, "liquiditybot_rp_heat_frac") == pytest.approx(0.05)
    assert _val(m, "liquiditybot_rp_heat_cap_frac") == pytest.approx(0.35)
    assert _val(m, "liquiditybot_rp_dd_throttle_mult") == pytest.approx(0.92)
    # absent block -> nothing emitted, no crash
    p2 = tmp_path / "s2.json"
    p2.write_text(json.dumps({"written_at": time.time()}), encoding="utf-8")
    assert _val(gp.collect(str(p2)), "liquiditybot_rp_heat_frac") is None


def test_collect_emits_model_health(tmp_path):
    status = {
        "written_at": time.time(),
        "monitor": {"level": 0, "drift_share": 0.1, "shrinkage": 0.35,
                    "kelly_mult": 0.8, "stop_widen": 1.1,
                    "edge_ratio_bump": 0.05, "champion_brier": 0.1887,
                    "use_model": True, "hit_rate": 0.6, "hit_rate_lcb": 0.41,
                    "avg_p": 0.66, "brier": 0.19, "baseline_brier": 0.24,
                    "calibration_gap": 0.07, "window_trades": 18},
        "ml": {"retrain_flag": True, "model_kind": "blend",
               "labels_by_source": {"live": 21, "candidate": 400}},
    }
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    m = gp.collect(str(p))
    assert _val(m, "liquiditybot_ml_champion_brier") == pytest.approx(0.1887)
    assert _val(m, "liquiditybot_ml_hit_rate") == pytest.approx(0.6)
    assert _val(m, "liquiditybot_ml_hit_rate_lcb") == pytest.approx(0.41)
    assert _val(m, "liquiditybot_ml_avg_p") == pytest.approx(0.66)
    assert _val(m, "liquiditybot_ml_kelly_mult") == pytest.approx(0.8)
    assert _val(m, "liquiditybot_ml_shrinkage") == pytest.approx(0.35)
    assert _val(m, "liquiditybot_ml_use_model") == 1.0
    assert _val(m, "liquiditybot_ml_retrain_flag") == 1.0
    assert _val(m, "liquiditybot_ml_labels", source="live") == 21.0
    assert _val(m, "liquiditybot_ml_labels", source="candidate") == 400.0
    assert _val(m, "liquiditybot_ml_model_info", kind="blend") == 1.0

    # cold bot: no monitor window, no model, flag off -> booleans still emit
    p2 = tmp_path / "s2.json"
    p2.write_text(json.dumps({"written_at": time.time(),
                              "ml": {"model_kind": None}}), encoding="utf-8")
    m2 = gp.collect(str(p2))
    assert _val(m2, "liquiditybot_ml_use_model") == 0.0
    assert _val(m2, "liquiditybot_ml_retrain_flag") == 0.0
    assert _val(m2, "liquiditybot_ml_hit_rate") is None
    assert not [x for x in m2 if x["name"] == "liquiditybot_ml_model_info"]


def test_collect_never_emits_non_finite(tmp_path):
    # json round-trips NaN: a poisoned status field must be dropped at the
    # choke point — ONE non-finite gauge invalidates the whole OTLP batch
    import math
    p = tmp_path / "status.json"
    p.write_text(json.dumps({"written_at": time.time(),
                             "equity": float("nan"),
                             "daily_pnl": float("inf"),
                             "drawdown_pct": 0.5}), encoding="utf-8")
    m = gp.collect(str(p))
    assert all(math.isfinite(x["gauge"]["dataPoints"][0]["asDouble"])
               for x in m)
    assert _val(m, "liquiditybot_equity") is None          # dropped, not sent
    assert _val(m, "liquiditybot_drawdown_pct") == 0.5     # clean ones remain


def test_collect_emits_signal_edge(tmp_path):
    status = {
        "written_at": time.time(),
        "signals": {"ETH": {"confirmed": True, "confidence": 0.9,
                            "urgency": 0.55,
                            "gates": {"if_1_flow_persistence": True,
                                      "if_2_accumulation": False}},
                    "BTC": {"confirmed": False, "confidence": 0.5,
                            "urgency": 0.0, "gates": {}}},
        "ml": {"gate_stats": {"enabled": True, "labeled": 281,
                              "base_rate": 0.21,
                              "weights": {"if_1_flow_persistence": 0.913}}},
        "regimes": {"ETH": {"macro": "range", "momentum": -0.33, "vol": "low",
                            "vol_pct": 22.0, "liq": "thin", "spread_bps": 0.1,
                            "spoof": 0.0, "basis_bps": -1.1}},
        "code_stats": {"by_prefix": {"PT": 9},
                       "entry_codes": {"PT-041": 6, "PT-050": 2, "SZ-045": 1}},
    }
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    m = gp.collect(str(p))
    assert _val(m, "liquiditybot_signal_confirmed", asset="ETH") == 1.0
    assert _val(m, "liquiditybot_signal_confirmed", asset="BTC") == 0.0
    assert _val(m, "liquiditybot_signal_gate_passed", asset="ETH",
                gate="if_1_flow_persistence") == 1.0
    assert _val(m, "liquiditybot_signal_gate_passed", asset="ETH",
                gate="if_2_accumulation") == 0.0
    assert _val(m, "liquiditybot_gate_weight",
                gate="if_1_flow_persistence") == pytest.approx(0.913)
    assert _val(m, "liquiditybot_gate_labeled") == 281.0
    assert _val(m, "liquiditybot_regime_momentum", asset="ETH") == pytest.approx(-0.33)
    assert _val(m, "liquiditybot_regime_vol_pct", asset="ETH") == 22.0
    assert _val(m, "liquiditybot_regime_info", asset="ETH", macro="range",
                vol="low", liq="thin") == 1.0
    assert _val(m, "liquiditybot_code_count_detail", code="PT-041") == 6.0
    assert _val(m, "liquiditybot_code_count_detail", code="PT-050") == 2.0


def test_collect_positions_absent_safe(tmp_path):
    # no positions -> risk-on banner is all zeros, no per-instrument series
    p = tmp_path / "status.json"
    p.write_text(json.dumps({"written_at": time.time(), "equity": 5000.0}),
                 encoding="utf-8")
    m = gp.collect(str(p))
    assert _val(m, "liquiditybot_open_upnl_usd") == 0.0
    assert _val(m, "liquiditybot_gross_exposure_usd") == 0.0
    assert _val(m, "liquiditybot_open_risk_usd") == 0.0
    assert _val(m, "liquiditybot_position_notional_usd", symbol="ETH/USD",
                side="long") is None


def test_collect_emits_hardening_guard_counters(tmp_path):
    # the exit-isolation + wedge-guard counters feed the incidents dashboard
    p = tmp_path / "status.json"
    p.write_text(json.dumps({
        "written_at": time.time(),
        "exit_eval_failures": 3, "cycle_consecutive_failures": 2}),
        encoding="utf-8")
    metrics = gp.collect(str(p))
    assert _by_name(metrics, "liquiditybot_exit_eval_failures")[0][
        "gauge"]["dataPoints"][0]["asDouble"] == 3.0
    assert _by_name(metrics, "liquiditybot_cycle_consecutive_failures")[0][
        "gauge"]["dataPoints"][0]["asDouble"] == 2.0


def test_collect_handles_missing_fault_blocks(tmp_path):
    # a minimal/old status.json must never crash the pusher
    p = tmp_path / "status.json"
    p.write_text(json.dumps({"written_at": time.time(), "equity": 800.0}),
                 encoding="utf-8")
    names = _names(gp.collect(str(p)))
    assert "liquiditybot_halted" in names
    assert "liquiditybot_firewall_fault" in names       # graceful default
    # the new counters are absent-safe (None -> not emitted, no crash)
    assert "liquiditybot_exit_eval_failures" not in names
    # brier is only pushed when the judge window is full; a status with no
    # monitor block must NOT emit it (so the outcome alert stays OK, not firing)
    assert "liquiditybot_ml_brier" not in names
