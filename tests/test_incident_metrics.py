"""
tests/test_incident_metrics.py — gc_pusher exports the fault/health signals the
incidents dashboard needs. Regression for the dark-counter audit: firewall
tallies + latched fault, order-manager rejects (OM-021/OM-050), ML fault
counters, retrain failures, watchdog trips, kill-switch level, moomoo
availability and the reason-code frequency ledger were all tracked internally
but never pushed to Grafana.
"""
import json

import pytest

import scripts.gc_pusher as gp


def _names(metrics):
    return {m["name"] for m in metrics}


def _by_name(metrics, name):
    return [m for m in metrics if m["name"] == name]


def test_collect_emits_fault_and_health_metrics(tmp_path):
    status = {
        "written_at": 1_700_000_000.0,
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
        "written_at": 1_700_000_000.0, "equity": 5000.0,
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


def test_collect_positions_absent_safe(tmp_path):
    # no positions -> risk-on banner is all zeros, no per-instrument series
    p = tmp_path / "status.json"
    p.write_text(json.dumps({"written_at": 1_700_000_000.0, "equity": 5000.0}),
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
        "written_at": 1_700_000_000.0,
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
    p.write_text(json.dumps({"written_at": 1_700_000_000.0, "equity": 800.0}),
                 encoding="utf-8")
    names = _names(gp.collect(str(p)))
    assert "liquiditybot_halted" in names
    assert "liquiditybot_firewall_fault" in names       # graceful default
    # the new counters are absent-safe (None -> not emitted, no crash)
    assert "liquiditybot_exit_eval_failures" not in names
    # brier is only pushed when the judge window is full; a status with no
    # monitor block must NOT emit it (so the outcome alert stays OK, not firing)
    assert "liquiditybot_ml_brier" not in names
