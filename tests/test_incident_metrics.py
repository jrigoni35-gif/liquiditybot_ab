"""
tests/test_incident_metrics.py — gc_pusher exports the fault/health signals the
incidents dashboard needs. Regression for the dark-counter audit: firewall
tallies + latched fault, order-manager rejects (OM-021/OM-050), ML fault
counters, retrain failures, watchdog trips, kill-switch level, moomoo
availability and the reason-code frequency ledger were all tracked internally
but never pushed to Grafana.
"""
import json

import scripts.gc_pusher as gp


def _names(metrics):
    return {m["name"] for m in metrics}


def _by_name(metrics, name):
    return [m for m in metrics if m["name"] == name]


def test_collect_emits_fault_and_health_metrics(tmp_path):
    status = {
        "written_at": 1_700_000_000.0,
        "halted": False, "entries_enabled": True, "audit_dropped_writes": 0,
        "monitor": {"level": 1, "drift_share": 0.42},
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

    codes = {dp["attributes"][0]["value"]["stringValue"]
             for m in _by_name(metrics, "liquiditybot_firewall_count")
             for dp in m["gauge"]["dataPoints"]}
    assert "FW-040" in codes

    prefixes = {dp["attributes"][0]["value"]["stringValue"]
                for m in _by_name(metrics, "liquiditybot_code_count")
                for dp in m["gauge"]["dataPoints"]}
    assert {"SZ", "PT", "FW"} <= prefixes


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
