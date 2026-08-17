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

    # cold bot: no monitor window, no model, flag key absent.
    # Re-pinned 2026-07-20: an unloaded champion now exports kind="prior"
    # instead of silence — running the prior is a STATE the model panel
    # must show, not an outage ("No data" after the v7 schema bump read
    # as broken telemetry while the width guard was doing its job).
    # Re-pinned AGAIN 2026-08-17 (guard batch 2): this block used to
    # assert use_model=0.0/retrain_flag=0.0 for keys the write never
    # carried — the exact fabricated-healthy-zero class the presence
    # guards remove. Absent key -> NO series now; the truthful-value
    # direction lives in the first half of this test and the absence
    # direction in test_dashboard_no_value's parametrized guard.
    p2 = tmp_path / "s2.json"
    p2.write_text(json.dumps({"written_at": time.time(),
                              "ml": {"model_kind": None}}), encoding="utf-8")
    m2 = gp.collect(str(p2))
    assert _val(m2, "liquiditybot_ml_use_model") is None
    assert _val(m2, "liquiditybot_ml_retrain_flag") is None
    assert _val(m2, "liquiditybot_ml_hit_rate") is None
    assert _val(m2, "liquiditybot_ml_model_info", kind="prior") == 1.0


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
    # a minimal/old status.json must never crash the pusher.
    #
    # CONTRACT INVERTED 2026-08-17 (deliberate pin flip, review record in
    # this commit): this test used to assert liquiditybot_halted and
    # liquiditybot_firewall_fault were emitted as "graceful defaults" from
    # a status that never carried those keys — i.e. it PINNED the
    # fabricated-healthy-zero behavior. A version-skew or schema-transition
    # write then rendered a bot that had never been checked as one that had
    # been checked and passed. The exporter now presence-guards the
    # bool/state family: absent key -> NO series -> the boards' honest
    # empty-state text ("not in this cycle's status write") fires instead.
    p = tmp_path / "status.json"
    p.write_text(json.dumps({"written_at": time.time(), "equity": 800.0}),
                 encoding="utf-8")
    names = _names(gp.collect(str(p)))       # must not raise — that part holds
    assert "liquiditybot_halted" not in names
    assert "liquiditybot_firewall_fault" not in names
    assert "liquiditybot_op_state" not in names
    assert "liquiditybot_fault_count" not in names
    assert "liquiditybot_watchdog_entries_blocked" not in names
    # the counters were already absent-safe (None -> not emitted, no crash)
    assert "liquiditybot_exit_eval_failures" not in names
    # brier is only pushed when the judge window is full; a status with no
    # monitor block must NOT emit it (so the outcome alert stays OK, not firing)
    assert "liquiditybot_ml_brier" not in names


def test_collect_manip_suspect_garbage_value_does_not_black_out_batch(tmp_path):
    # W2-14-guards: manip_suspect is the ONLY per-asset loop with no
    # isinstance-numeric guard; one non-numeric value must be skipped, not
    # raise and black out the whole metric batch (including alarm gauges).
    status = {"written_at": time.time(),
              "halted": True,
              "manip_suspect": {"BTC": "garbage", "ETH": 0.42}}
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    m = gp.collect(str(p))                    # must not raise on BTC='garbage'
    assert _by_name(m, "liquiditybot_halted")  # rest of the batch still ships
    eth = _by_name(m, "liquiditybot_manip_suspect")
    assert len(eth) == 1
    assert eth[0]["gauge"]["dataPoints"][0]["attributes"][0]["value"][
        "stringValue"] == "ETH"


def test_num_rejects_infinity_like_nan():
    assert gp._num(float("inf")) == 0.0
    assert gp._num(float("-inf")) == 0.0
    assert gp._num(float("nan")) == 0.0
    assert gp._num(float("inf"), default=5.0) == 5.0


def test_collect_tiers_fired_infinity_does_not_crash(tmp_path):
    # W2-14-guards: _num guards NaN but not inf; int(_num(tiers_fired)) at
    # the position-aggregation site raised OverflowError on a JSON Infinity.
    status = {"written_at": time.time(),
              "positions": [{"symbol": "BTC", "direction": "long",
                            "entry": 100.0, "mark": 101.0, "size": 1.0,
                            "stop": 95.0, "tiers_fired": float("inf")}]}
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    m = gp.collect(str(p))                    # must not raise OverflowError
    tier = _by_name(m, "liquiditybot_position_tiers_fired")
    assert tier and tier[0]["gauge"]["dataPoints"][0]["asDouble"] == 0.0


# ---- conviction formula telemetry (#120, risk/conviction.py status()) ------
def test_collect_emits_conviction_metrics(tmp_path):
    status = {
        "written_at": time.time(),
        "conviction": {
            "enabled": True, "mode": "report", "evaluated": 42, "admitted": 30,
            "denials": {"CV-010": 8, "CV-020": 4},
            "share": 0.71, "n": 40,
            "by_regime": {"range": {"share": 0.65, "n": 20},
                          "trend": {"share": 0.8, "n": 20}},
            "alarm": "ok",
        },
    }
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    m = gp.collect(str(p))
    names = _names(m)
    for expect in ("liquiditybot_conviction_evaluated",
                   "liquiditybot_conviction_admitted",
                   "liquiditybot_conviction_share",
                   "liquiditybot_conviction_n",
                   "liquiditybot_conviction_denials",
                   "liquiditybot_conviction_regime_share",
                   "liquiditybot_conviction_regime_n",
                   "liquiditybot_conviction_alarm"):
        assert expect in names, f"missing metric {expect}"
    assert _val(m, "liquiditybot_conviction_evaluated") == 42.0
    assert _val(m, "liquiditybot_conviction_admitted") == 30.0
    assert _val(m, "liquiditybot_conviction_share") == pytest.approx(0.71)
    assert _val(m, "liquiditybot_conviction_n") == 40.0
    assert _val(m, "liquiditybot_conviction_denials", code="CV-010") == 8.0
    assert _val(m, "liquiditybot_conviction_denials", code="CV-020") == 4.0
    assert _val(m, "liquiditybot_conviction_regime_share",
                regime="range") == pytest.approx(0.65)
    assert _val(m, "liquiditybot_conviction_regime_n", regime="trend") == 20.0
    # ok=0 / low=1 / high=2
    assert _val(m, "liquiditybot_conviction_alarm") == 0.0


def test_collect_conviction_alarm_numeric_mapping(tmp_path):
    for alarm, expected in (("ok", 0.0), ("low", 1.0), ("high", 2.0)):
        p = tmp_path / f"status_{alarm}.json"
        p.write_text(json.dumps({
            "written_at": time.time(),
            "conviction": {"enabled": True, "mode": "report", "evaluated": 1,
                          "admitted": 1, "denials": {}, "share": 1.0, "n": 1,
                          "by_regime": {}, "alarm": alarm}}), encoding="utf-8")
        m = gp.collect(str(p))
        assert _val(m, "liquiditybot_conviction_alarm") == expected, alarm


def test_collect_conviction_absent_emits_nothing(tmp_path):
    # older status.json (pre-#120) has no "conviction" key at all — degrade
    # silently, no crash, no conviction-scoped metrics
    p = tmp_path / "status.json"
    p.write_text(json.dumps({"written_at": time.time(), "equity": 800.0}),
                 encoding="utf-8")
    names = _names(gp.collect(str(p)))
    assert not [n for n in names if n.startswith("liquiditybot_conviction")]


def test_collect_conviction_empty_section_emits_nothing(tmp_path):
    # formula present but the section is an empty dict (e.g. a status writer
    # that emits {} rather than omitting the key) — same silent degrade
    p = tmp_path / "status.json"
    p.write_text(json.dumps({"written_at": time.time(), "conviction": {}}),
                 encoding="utf-8")
    names = _names(gp.collect(str(p)))
    assert not [n for n in names if n.startswith("liquiditybot_conviction")]


def test_collect_conviction_survives_malformed_regime_entry(tmp_path):
    # a non-dict by_regime value or non-numeric denial count must be skipped,
    # never crash and black out the whole metric batch
    status = {"written_at": time.time(), "halted": True,
              "conviction": {"enabled": True, "mode": "report",
                            "evaluated": 5, "admitted": 3,
                            "denials": {"CV-010": "garbage"},
                            "share": 0.6, "n": 5,
                            "by_regime": {"range": "garbage",
                                          "trend": {"share": 0.5, "n": 2}},
                            "alarm": "ok"}}
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    m = gp.collect(str(p))                    # must not raise
    assert _by_name(m, "liquiditybot_halted")  # rest of the batch still ships
    assert _val(m, "liquiditybot_conviction_denials", code="CV-010") is None
    assert _val(m, "liquiditybot_conviction_regime_share", regime="range") \
        is None
    assert _val(m, "liquiditybot_conviction_regime_share",
                regime="trend") == pytest.approx(0.5)


# ---- context engine telemetry (Task B6, data/context_engine.py
# ContextFeed.status()) -------------------------------------------------------
def test_collect_emits_context_metrics(tmp_path):
    status = {
        "written_at": time.time(),
        "context": {
            "enabled": True, "halving_phase": "expansion", "days_since": 300,
            "days_to_next": 500, "stress": 0.42, "stress_known": True,
            "cot_z": -0.3, "stable_wk_pct": 1.2, "flow_known": True,
            "in_event_window": False, "next_event": "cme_expiry:2026-07-31",
            "calendar_known": True,
            "sources": {"dff": True, "t10y2y": True, "vix": False,
                        "cot": True, "stablecoins": True, "calendar": True,
                        "halving": True},
            "last_poll_age_sec": 120.5,
        },
    }
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    m = gp.collect(str(p))
    names = _names(m)
    for expect in ("liquiditybot_context_stress", "liquiditybot_context_cot_z",
                   "liquiditybot_context_stable_wk_pct",
                   "liquiditybot_context_days_since_halving",
                   "liquiditybot_context_days_to_next_halving",
                   "liquiditybot_context_event_window",
                   "liquiditybot_context_source_ok",
                   "liquiditybot_context_phase"):
        assert expect in names, f"missing metric {expect}"
    assert _val(m, "liquiditybot_context_stress") == pytest.approx(0.42)
    assert _val(m, "liquiditybot_context_cot_z") == pytest.approx(-0.3)
    assert _val(m, "liquiditybot_context_stable_wk_pct") == pytest.approx(1.2)
    assert _val(m, "liquiditybot_context_days_since_halving") == 300.0
    assert _val(m, "liquiditybot_context_days_to_next_halving") == 500.0
    assert _val(m, "liquiditybot_context_event_window") == 0.0
    assert _val(m, "liquiditybot_context_source_ok", source="dff") == 1.0
    assert _val(m, "liquiditybot_context_source_ok", source="vix") == 0.0
    assert _val(m, "liquiditybot_context_source_ok", source="halving") == 1.0
    # one-hot: only the active bucket carries value 1
    assert _val(m, "liquiditybot_context_phase", phase="expansion") == 1.0
    assert _val(m, "liquiditybot_context_phase", phase="accumulation") is None


def test_collect_context_event_window_true(tmp_path):
    status = {"written_at": time.time(),
              "context": {"enabled": True, "halving_phase": "euphoria",
                          "days_since": 800, "days_to_next": 100,
                          "stress": None, "stress_known": False,
                          "cot_z": None, "stable_wk_pct": None,
                          "flow_known": False, "in_event_window": True,
                          "next_event": "fomc:2026-08-01",
                          "calendar_known": True,
                          "sources": {"dff": False, "halving": True},
                          "last_poll_age_sec": 10.0}}
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    m = gp.collect(str(p))
    assert _val(m, "liquiditybot_context_event_window") == 1.0
    # unknown dials (None) are never emitted — a 0 and an unknown must stay
    # distinguishable
    assert _val(m, "liquiditybot_context_stress") is None
    assert _val(m, "liquiditybot_context_cot_z") is None
    assert _val(m, "liquiditybot_context_stable_wk_pct") is None
    assert not _by_name(m, "liquiditybot_context_stress")


def test_collect_context_absent_emits_nothing(tmp_path):
    # pre-Phase-B status.json has no "context" key at all — degrade
    # silently, no crash, no context-scoped metrics
    p = tmp_path / "status.json"
    p.write_text(json.dumps({"written_at": time.time(), "equity": 800.0}),
                 encoding="utf-8")
    names = _names(gp.collect(str(p)))
    assert not [n for n in names if n.startswith("liquiditybot_context_")]


def test_collect_context_empty_section_emits_nothing(tmp_path):
    # engine present but the section is an empty dict — same silent degrade
    p = tmp_path / "status.json"
    p.write_text(json.dumps({"written_at": time.time(), "context": {}}),
                 encoding="utf-8")
    names = _names(gp.collect(str(p)))
    assert not [n for n in names if n.startswith("liquiditybot_context_")]


def test_collect_context_no_poll_yet_emits_no_phase(tmp_path):
    # before the first poll, ContextState() defaults halving_phase to "" —
    # an empty bucket name must never be emitted as a fake active phase
    status = {"written_at": time.time(),
              "context": {"enabled": True, "halving_phase": "", "days_since": 0,
                          "days_to_next": 0, "stress": None,
                          "stress_known": False, "cot_z": None,
                          "stable_wk_pct": None, "flow_known": False,
                          "in_event_window": False, "next_event": "",
                          "calendar_known": False,
                          "sources": {"dff": False}, "last_poll_age_sec": None}}
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    m = gp.collect(str(p))
    assert not _by_name(m, "liquiditybot_context_phase")
    # days_since/days_to_next are always-known local date math (0 is a
    # genuine value here, not an unknown) — still emitted
    assert _val(m, "liquiditybot_context_days_since_halving") == 0.0
    assert _val(m, "liquiditybot_context_days_to_next_halving") == 0.0


def test_collect_context_survives_malformed_sources(tmp_path):
    # a non-dict "sources" value must be skipped, never crash and black out
    # the whole metric batch
    status = {"written_at": time.time(), "halted": True,
              "context": {"enabled": True, "halving_phase": "accumulation",
                          "days_since": 10, "days_to_next": 1450,
                          "stress": 0.1, "stress_known": True, "cot_z": 0.0,
                          "stable_wk_pct": 0.0, "flow_known": True,
                          "in_event_window": False, "next_event": "",
                          "calendar_known": True, "sources": "garbage",
                          "last_poll_age_sec": 1.0}}
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    m = gp.collect(str(p))                    # must not raise
    assert _by_name(m, "liquiditybot_halted")  # rest of the batch still ships
    assert not _by_name(m, "liquiditybot_context_source_ok")
    assert _val(m, "liquiditybot_context_phase", phase="accumulation") == 1.0


# ---- long-book telemetry (Task C6, runner.py BotRunner._long_book_status())
def test_collect_emits_long_book_metrics(tmp_path):
    status = {
        "written_at": time.time(),
        "long_book": {
            "enabled": True, "rung": 2, "ceiling_frac": 0.2,
            "book_exposure_usd": 850.0, "positions": 1, "adds_placed": 6,
            "last_add_age_h": 3.5, "paused_reason": "",
            "closed_paper": 14, "closed_live": 16, "pf_live": 1.42,
            "context_aligned_last": True,
        },
    }
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    m = gp.collect(str(p))
    names = _names(m)
    for expect in ("liquiditybot_longbook_rung",
                   "liquiditybot_longbook_ceiling_frac",
                   "liquiditybot_longbook_exposure_usd",
                   "liquiditybot_longbook_adds_placed",
                   "liquiditybot_longbook_closed",
                   "liquiditybot_longbook_pf_live",
                   "liquiditybot_longbook_paused",
                   "liquiditybot_longbook_context_aligned"):
        assert expect in names, f"missing metric {expect}"
    assert _val(m, "liquiditybot_longbook_rung") == 2.0
    assert _val(m, "liquiditybot_longbook_ceiling_frac") == pytest.approx(0.2)
    assert _val(m, "liquiditybot_longbook_exposure_usd") == pytest.approx(850.0)
    assert _val(m, "liquiditybot_longbook_adds_placed") == 6.0
    assert _val(m, "liquiditybot_longbook_closed", track="paper") == 14.0
    assert _val(m, "liquiditybot_longbook_closed", track="live") == 16.0
    assert _val(m, "liquiditybot_longbook_pf_live") == pytest.approx(1.42)
    # paused_reason == "" -> not paused
    assert _val(m, "liquiditybot_longbook_paused") == 0.0
    assert _val(m, "liquiditybot_longbook_context_aligned") == 1.0


def test_collect_long_book_paused_when_deny_detail_present(tmp_path):
    status = {"written_at": time.time(),
              "long_book": {
                  "enabled": True, "rung": 0, "ceiling_frac": 0.1,
                  "book_exposure_usd": 0.0, "positions": 0, "adds_placed": 0,
                  "last_add_age_h": None,
                  "paused_reason": "BTC: no headroom (ceiling)",
                  "closed_paper": 0, "closed_live": 0, "pf_live": None,
                  "context_aligned_last": False}}
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    m = gp.collect(str(p))
    assert _val(m, "liquiditybot_longbook_paused") == 1.0
    assert _val(m, "liquiditybot_longbook_context_aligned") == 0.0
    # pf_live None (no live evidence yet, JSON-safe per runner.py) is never
    # emitted — honest absence, not a fabricated 0
    assert not _by_name(m, "liquiditybot_longbook_pf_live")


def test_collect_long_book_context_aligned_unknown_emits_nothing(tmp_path):
    # context_aligned_last is None before the FIRST long-book cycle runs
    # (or when the context stress dial is dark/unknown) — honest-unknown:
    # never a fabricated 0/1
    status = {"written_at": time.time(),
              "long_book": {
                  "enabled": True, "rung": 0, "ceiling_frac": 0.1,
                  "book_exposure_usd": 0.0, "positions": 0, "adds_placed": 0,
                  "last_add_age_h": None, "paused_reason": "",
                  "closed_paper": 0, "closed_live": 0, "pf_live": None,
                  "context_aligned_last": None}}
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    m = gp.collect(str(p))
    assert not _by_name(m, "liquiditybot_longbook_context_aligned")


def test_collect_long_book_absent_emits_nothing(tmp_path):
    # pre-Compounder-Phase-C status.json (or a bot built before long_ladder
    # existed — runner._long_book_status's own hasattr guard) has no
    # "long_book" key at all — degrade silently, no crash, no
    # longbook-scoped metrics
    p = tmp_path / "status.json"
    p.write_text(json.dumps({"written_at": time.time(), "equity": 800.0}),
                 encoding="utf-8")
    names = _names(gp.collect(str(p)))
    assert not [n for n in names if n.startswith("liquiditybot_longbook_")]


def test_collect_long_book_empty_section_emits_nothing(tmp_path):
    # engine present but the section is an empty dict (the same {} degrade
    # the status writer's own except-Exception branch returns) — same
    # silent degrade
    p = tmp_path / "status.json"
    p.write_text(json.dumps({"written_at": time.time(), "long_book": {}}),
                 encoding="utf-8")
    names = _names(gp.collect(str(p)))
    assert not [n for n in names if n.startswith("liquiditybot_longbook_")]


# ---- label-era transition (era-gated training exclusion, docs/quant/
# 2026-07-26_era_exclusion.md) — ml.load_stats' era_exclusion/label_era/
# era_mix_drift blocks (ml/history.py last_load_stats, written verbatim by
# runner.py). Shapes copied from the brief's measured example (the bot's
# own status.json the morning the era machinery went live).
def _era_load_stats(**over):
    ls = {
        "live_clean": 233, "mean_uniqueness": 0.42,
        "era_exclusion": {
            "armed": True, "active": True, "forced_off": False,
            "forced_on": False, "min_new_era_rows": 150,
            "new_era_rows": 233,
            "excluded": {
                "total": 4850,
                "by_era_source": {
                    "exit_sim_time_stop": {"candidate": 457},
                    "exit_sim": {"candidate": 2436, "live": 195},
                    "legacy": {"live": 47, "candidate": 1715},
                }}},
        "label_era": {
            "triple_barrier": {
                "rows": 233, "label_rate": 0.3991,
                "by_reason": {
                    "tb_pt": {"rows": 103, "label_rate": 0.8738},
                    "tb_sl": {"rows": 122, "label_rate": 0.0},
                    "tb_time": {"rows": 8, "label_rate": 0.375}}},
            "legacy": {"rows": 1762, "label_rate": 0.2611, "by_reason": {}},
            "exit_sim": {"rows": 2436, "label_rate": 0.1345, "by_reason": {}},
            "exit_sim_time_stop": {"rows": 457, "label_rate": 0.0066,
                                   "by_reason": {}},
        },
        "era_mix_drift": {"tvd": 0.41, "fired": True, "n_recent": 233,
                          "n_total": 4897},
    }
    ls.update(over)
    return ls


def test_collect_emits_era_exclusion_and_label_era_metrics(tmp_path):
    status = {"written_at": time.time(), "ml": {"load_stats": _era_load_stats()}}
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    m = gp.collect(str(p))
    names = _names(m)
    for expect in ("liquiditybot_era_excl_armed", "liquiditybot_era_excl_active",
                   "liquiditybot_era_excl_new_rows", "liquiditybot_era_excl_min_rows",
                   "liquiditybot_era_excl_dropped", "liquiditybot_era_rows",
                   "liquiditybot_era_label_rate", "liquiditybot_era_reason_rows",
                   "liquiditybot_era_reason_label_rate",
                   "liquiditybot_era_mix_tvd", "liquiditybot_era_mix_alarm"):
        assert expect in names, f"missing metric {expect}"

    assert _val(m, "liquiditybot_era_excl_armed") == 1.0
    assert _val(m, "liquiditybot_era_excl_active") == 1.0
    assert _val(m, "liquiditybot_era_excl_new_rows") == 233.0
    assert _val(m, "liquiditybot_era_excl_min_rows") == 150.0
    assert _val(m, "liquiditybot_era_excl_dropped") == 4850.0

    # the 0.0066 -> 0.3991 repair, one series per era
    assert _val(m, "liquiditybot_era_label_rate",
                era="triple_barrier") == pytest.approx(0.3991)
    assert _val(m, "liquiditybot_era_label_rate",
                era="exit_sim_time_stop") == pytest.approx(0.0066)
    assert _val(m, "liquiditybot_era_label_rate",
                era="exit_sim") == pytest.approx(0.1345)
    assert _val(m, "liquiditybot_era_label_rate",
                era="legacy") == pytest.approx(0.2611)
    assert _val(m, "liquiditybot_era_rows", era="triple_barrier") == 233.0

    # tb_pt high / tb_sl zero / tb_time mixed — the healthy-label signature
    assert _val(m, "liquiditybot_era_reason_label_rate",
                era="triple_barrier", reason="tb_pt") == pytest.approx(0.8738)
    assert _val(m, "liquiditybot_era_reason_label_rate",
                era="triple_barrier", reason="tb_sl") == pytest.approx(0.0)
    assert _val(m, "liquiditybot_era_reason_label_rate",
                era="triple_barrier", reason="tb_time") == pytest.approx(0.375)
    assert _val(m, "liquiditybot_era_reason_rows",
                era="triple_barrier", reason="tb_pt") == 103.0

    assert _val(m, "liquiditybot_era_mix_tvd") == pytest.approx(0.41)
    assert _val(m, "liquiditybot_era_mix_alarm") == 1.0


def test_collect_era_load_stats_empty_emits_nothing(tmp_path):
    # a just-restarted bot with no retrain yet — ml.load_stats == {} — must
    # emit NOTHING for the era section (never zeros: a zero would read as
    # "exclusion off" when the truth is "not yet measured")
    status = {"written_at": time.time(), "ml": {"load_stats": {}}}
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    names = _names(gp.collect(str(p)))
    assert not [n for n in names if n.startswith("liquiditybot_era_")]


def test_collect_era_pre_era_task_status_has_no_excl_block(tmp_path):
    # older ml.load_stats (live_clean/mean_uniqueness only, predating the
    # era-exclusion task) has no era_exclusion/label_era/era_mix_drift keys
    # at all — the armed/active gauges must not fabricate a 0
    status = {"written_at": time.time(),
              "ml": {"load_stats": {"live_clean": 40, "mean_uniqueness": 0.3}}}
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    names = _names(gp.collect(str(p)))
    assert not [n for n in names if n.startswith("liquiditybot_era_")]
    assert "liquiditybot_ml_live_clean" in names   # rest of the block unaffected


def test_collect_era_cardinality_clamp_garbage_strings(tmp_path):
    # a malformed era/reason string must clamp to "other", never mint a new
    # Prometheus series from garbage
    ls = _era_load_stats()
    ls["label_era"] = {
        "totally-not-a-real-era": {
            "rows": 5, "label_rate": 0.2,
            "by_reason": {"nonsense-barrier-xyz": {"rows": 5,
                                                     "label_rate": 0.2}}}}
    status = {"written_at": time.time(), "ml": {"load_stats": ls}}
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    m = gp.collect(str(p))
    assert _val(m, "liquiditybot_era_rows", era="other") == 5.0
    assert _val(m, "liquiditybot_era_rows", era="totally-not-a-real-era") is None
    assert _val(m, "liquiditybot_era_reason_rows", era="other",
                reason="other") == 5.0
    assert _val(m, "liquiditybot_era_reason_rows", era="other",
                reason="nonsense-barrier-xyz") is None


def test_collect_era_reason_blank_clamps_to_none(tmp_path):
    ls = _era_load_stats()
    ls["label_era"] = {"exit_sim": {
        "rows": 10, "label_rate": 0.5,
        "by_reason": {"": {"rows": 10, "label_rate": 0.5}}}}
    status = {"written_at": time.time(), "ml": {"load_stats": ls}}
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    m = gp.collect(str(p))
    assert _val(m, "liquiditybot_era_reason_rows", era="exit_sim",
                reason="none") == 10.0


def test_collect_era_mix_drift_silent_below_min_rows_emits_nothing(tmp_path):
    # _era_mix_drift_check returns tvd=None (SILENT) when the recent window
    # has too few rows to trust its own mix — honest-unknown, never a
    # fabricated 0/"not exceeded"
    ls = _era_load_stats(era_mix_drift={"tvd": None, "fired": False,
                                        "n_recent": 3, "n_total": 50})
    status = {"written_at": time.time(), "ml": {"load_stats": ls}}
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    names = _names(gp.collect(str(p)))
    assert "liquiditybot_era_mix_tvd" not in names
    assert "liquiditybot_era_mix_alarm" not in names


def test_collect_era_exclusion_inert_shape(tmp_path):
    # era_cfg=None caller (structurally inert): armed=active=False, no
    # rows excluded — must still emit real 0-valued gauges (this IS a
    # measured state, not an absence)
    ls = _era_load_stats(era_exclusion={
        "armed": False, "active": False, "forced_off": False,
        "forced_on": False, "min_new_era_rows": 150, "new_era_rows": 12,
        "excluded": {"total": 0, "by_era_source": {}}})
    status = {"written_at": time.time(), "ml": {"load_stats": ls}}
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    m = gp.collect(str(p))
    assert _val(m, "liquiditybot_era_excl_armed") == 0.0
    assert _val(m, "liquiditybot_era_excl_active") == 0.0
    assert _val(m, "liquiditybot_era_excl_new_rows") == 12.0
    assert _val(m, "liquiditybot_era_excl_dropped") == 0.0


def test_collect_era_survives_malformed_entries(tmp_path):
    # a non-dict era-block or reason-block value must be skipped, never
    # crash and black out the whole metric batch
    ls = _era_load_stats()
    ls["label_era"] = {
        "legacy": "garbage",
        "exit_sim": {"rows": 4, "label_rate": 0.1, "by_reason": {
            "sl": "garbage", "time": {"rows": 4, "label_rate": 0.1}}}}
    status = {"written_at": time.time(), "halted": True,
              "ml": {"load_stats": ls}}
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    m = gp.collect(str(p))                    # must not raise
    assert _by_name(m, "liquiditybot_halted")  # rest of the batch still ships
    assert _val(m, "liquiditybot_era_rows", era="legacy") is None
    assert _val(m, "liquiditybot_era_reason_rows", era="exit_sim",
                reason="sl") is None
    assert _val(m, "liquiditybot_era_reason_rows", era="exit_sim",
                reason="time") == 4.0


def test_collect_era_stale_batch_never_includes_era_metrics(tmp_path):
    # DL-6: a status.json older than STALE_AFTER_SEC pushes the alarm-only
    # batch; a stale era snapshot must never masquerade as current
    status = {"written_at": time.time() - 600,
              "ml": {"load_stats": _era_load_stats()}}
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    names = _names(gp.collect(str(p)))
    assert not [n for n in names if n.startswith("liquiditybot_era_")]
    assert "liquiditybot_status_stale" in names


def test_collect_long_book_survives_malformed_values(tmp_path):
    # non-numeric rung/ceiling/exposure/adds and a non-bool
    # context_aligned_last must be skipped, never crash and black out the
    # whole metric batch
    status = {"written_at": time.time(), "halted": True,
              "long_book": {
                  "enabled": True, "rung": "garbage",
                  "ceiling_frac": "garbage", "book_exposure_usd": "garbage",
                  "adds_placed": "garbage", "closed_paper": "garbage",
                  "closed_live": 5, "pf_live": "garbage",
                  "paused_reason": "", "context_aligned_last": "maybe"}}
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    m = gp.collect(str(p))                    # must not raise
    assert _by_name(m, "liquiditybot_halted")  # rest of the batch still ships
    assert not _by_name(m, "liquiditybot_longbook_rung")
    assert not _by_name(m, "liquiditybot_longbook_ceiling_frac")
    assert not _by_name(m, "liquiditybot_longbook_exposure_usd")
    assert not _by_name(m, "liquiditybot_longbook_adds_placed")
    assert not _by_name(m, "liquiditybot_longbook_pf_live")
    assert not _by_name(m, "liquiditybot_longbook_context_aligned")
    assert _val(m, "liquiditybot_longbook_closed", track="live") == 5.0
    assert _val(m, "liquiditybot_longbook_closed", track="paper") is None
    # paused is unconditional (a free-form detail string's truthiness),
    # never skipped
    assert _val(m, "liquiditybot_longbook_paused") == 0.0


# ---- audit wf_c730ca1b: DL6-A fail-stale written_at ------------------------
# `ts = float(s.get("written_at") or time.time())` re-derived ts as NOW on
# every call whenever written_at was absent/null/0 — a frozen status file
# without the key showed running=1/stale=0/equity=... forever, the ONE
# liveness check in the tree that defaulted toward FRESH instead of STALE.
def test_written_at_missing_fails_stale_not_fresh(tmp_path):
    status = {"runner_state": "RUNNING", "equity": 12345.0, "positions": []}
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    m = gp.collect(str(p))
    names = _names(m)
    assert _val(m, "liquiditybot_status_stale") == 1.0
    assert _val(m, "liquiditybot_running") == 0.0
    assert "liquiditybot_equity" not in names, \
        "missing written_at must never masquerade as a fresh healthy batch"


def test_written_at_null_fails_stale_not_fresh(tmp_path):
    status = {"runner_state": "RUNNING", "equity": 999.0, "written_at": None}
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    m = gp.collect(str(p))
    assert _val(m, "liquiditybot_status_stale") == 1.0
    assert _val(m, "liquiditybot_running") == 0.0
    assert "liquiditybot_equity" not in _names(m)


def test_written_at_zero_fails_stale_not_fresh(tmp_path):
    status = {"runner_state": "RUNNING", "equity": 999.0, "written_at": 0}
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    m = gp.collect(str(p))
    assert _val(m, "liquiditybot_status_stale") == 1.0
    assert _val(m, "liquiditybot_running") == 0.0
    assert "liquiditybot_equity" not in _names(m)


def test_written_at_present_and_fresh_still_pushes_full_batch(tmp_path):
    # guard against over-correcting: a real, current written_at must still
    # read as fresh (not everything defaults to stale now)
    status = {"runner_state": "RUNNING", "equity": 12345.0,
              "written_at": time.time()}
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    m = gp.collect(str(p))
    assert _val(m, "liquiditybot_status_stale") == 0.0
    assert _val(m, "liquiditybot_running") == 1.0
    assert _val(m, "liquiditybot_equity") == 12345.0


# ---- audit wf_c730ca1b: DL6-B malformed-but-parseable status ---------------
# A status.json that PARSES but has the wrong SHAPE (top-level null/list,
# "goals" as a list, "positions" as an int, written_at as a non-numeric
# string, ...) used to raise OUT of collect() entirely — main()'s
# push(cfg, collect(...)) is one expression, so push() never ran and ZERO
# gauges shipped, not even the alarm batch. The blanket fallback must emit
# the alarm-only batch plus liquiditybot_status_malformed=1.0.
def _malformed_status_texts():
    return {
        "top_level_null": "null",
        "top_level_list": "[1, 2, 3]",
        "goals_as_list": json.dumps({"written_at": time.time(),
                                     "goals": [1, 2, 3]}),
        "positions_as_int": json.dumps({"written_at": time.time(),
                                        "positions": 5}),
        "written_at_bad_string": json.dumps({"written_at": "not-a-number",
                                             "runner_state": "RUNNING",
                                             "equity": 999.0}),
    }


def test_malformed_status_shapes_emit_malformed_alarm_batch(tmp_path):
    for label, text in _malformed_status_texts().items():
        p = tmp_path / f"{label}.json"
        p.write_text(text, encoding="utf-8")
        m = gp.collect(str(p))                      # must not raise
        assert m, f"{label}: collect() must never return empty"
        assert _val(m, "liquiditybot_status_malformed") == 1.0, label
        assert _val(m, "liquiditybot_running") == 0.0, label
        assert _val(m, "liquiditybot_status_stale") == 1.0, label
        assert "liquiditybot_equity" not in _names(m), label


def test_malformed_status_push_receives_nonempty_batch_end_to_end(
        tmp_path, monkeypatch):
    # end-to-end: main()'s `push(cfg, collect(...))` must still execute
    # with a real, non-empty OTLP payload on a malformed status.json
    p = tmp_path / "status.json"
    p.write_text("null", encoding="utf-8")
    captured = {}

    class _Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def _fake_urlopen(req, timeout=30):
        captured["body"] = json.loads(req.data.decode())
        return _Resp()

    monkeypatch.setattr(gp.urllib.request, "urlopen", _fake_urlopen)
    cfg = {"url": "https://example.invalid/otlp", "auth": "x"}
    code = gp.push(cfg, gp.collect(str(p)))
    assert code == 200
    metrics = captured["body"]["resourceMetrics"][0]["scopeMetrics"][0]["metrics"]
    assert metrics, "push() must ship a non-empty batch even on malformed status"
    names = {mm["name"] for mm in metrics}
    assert "liquiditybot_status_malformed" in names


def test_malformed_flag_zero_on_fresh_and_stale_healthy_paths(tmp_path):
    # mirrors liquiditybot_status_missing's existing pattern: the malformed
    # series must always exist (0.0) whenever the file parsed and the
    # fresh-path body completed, whether stale or fresh
    fresh = tmp_path / "fresh.json"
    fresh.write_text(json.dumps({"written_at": time.time(), "equity": 1.0}),
                     encoding="utf-8")
    assert _val(gp.collect(str(fresh)), "liquiditybot_status_malformed") == 0.0

    stale = tmp_path / "stale.json"
    stale.write_text(json.dumps({"written_at": time.time() - 600,
                                 "equity": 1.0}), encoding="utf-8")
    assert _val(gp.collect(str(stale)), "liquiditybot_status_malformed") == 0.0


# ---- audit wf_c730ca1b: F1 labels{source=} cardinality clamp ---------------
def test_ml_labels_source_clamps_garbage_to_other(tmp_path):
    # HistoryStore.source_counts() keys ride verbatim off the CSV column
    # (r[idx] or "unknown"), bounded today only by the two literal write
    # sites ("live"/"candidate"). A corrupted/hand-edited row must clamp at
    # the EMISSION site here, never mint a new Prometheus series.
    status = {"written_at": time.time(),
              "ml": {"labels_by_source": {"live": 5,
                                          "garbage-source-xyz": 3}}}
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    m = gp.collect(str(p))
    assert _val(m, "liquiditybot_ml_labels", source="live") == 5.0
    assert _val(m, "liquiditybot_ml_labels", source="other") == 3.0
    assert _val(m, "liquiditybot_ml_labels", source="garbage-source-xyz") \
        is None


def test_ml_labels_source_known_values_pass_through_unclamped(tmp_path):
    status = {"written_at": time.time(),
              "ml": {"labels_by_source": {"live": 21, "candidate": 400}}}
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    m = gp.collect(str(p))
    assert _val(m, "liquiditybot_ml_labels", source="live") == 21.0
    assert _val(m, "liquiditybot_ml_labels", source="candidate") == 400.0


# ---- audit wf_c730ca1b: DL6-D dropped-nonfinite visibility (Minor, judgment
# call: implemented rather than document-and-skip — cheap, and the existing
# finiteness filter already has the hook point) -----------------------------
def test_dropped_nonfinite_counter_zero_when_clean(tmp_path):
    status = {"written_at": time.time(), "equity": 100.0}
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    m = gp.collect(str(p))
    assert _val(m, "liquiditybot_gauges_dropped_nonfinite") == 0.0


def test_dropped_nonfinite_counter_reflects_nan_storm(tmp_path):
    status_text = ('{"written_at": %f, "equity": NaN, "daily_pnl": Infinity, '
                  '"weekly_pnl": -Infinity, "drawdown_pct": 0.5}'
                  % time.time())
    p = tmp_path / "status.json"
    p.write_text(status_text, encoding="utf-8")
    m = gp.collect(str(p))
    assert _val(m, "liquiditybot_gauges_dropped_nonfinite") == 3.0
    assert _val(m, "liquiditybot_drawdown_pct") == 0.5
