"""tests/test_trading_dashboard.py — the command dashboard's structural
contract, CI-enforced:

  1. the generator (scripts/build_trading_dashboard.py — the SOURCE OF TRUTH)
     and the shipped docs/grafana/liquiditybot_command.json are identical, so
     hand-edits or a stale regeneration can't drift them apart;
  2. valid UI-importable shape: unwrapped, schemaVersion at top level, stable
     uid, unique panel ids, no overlapping gridPos;
  3. EVERY liquiditybot_* metric referenced by a panel query is actually
     emitted by scripts/gc_pusher.py — a renamed/removed metric breaks the
     build instead of silently blanking a panel ("code reacts to the panels");
  4. it is a LOGISTICAL board: no time-series graphs (stat/state/table/gauge
     only), the whole point of the condense.
"""
import json
import re
from pathlib import Path

import scripts.build_trading_dashboard as gen
import scripts.gc_pusher as gp

ROOT = Path(__file__).resolve().parents[1]

# a synthetic status.json exercising every section the pusher exports, so the
# emitted-metric universe is complete for check 3
_SYNTH_STATUS = {
    "written_at": 1.7e9, "equity": 5000.0, "daily_pnl": 3.0,
    "realized_total": 1.0, "drawdown_pct": 0.4, "fees_total": 2.0,
    "cycle": 10, "cycle_lifetime": 100, "feed_latency_ms": 50.0,
    "marks_age_sec": 1.0, "equity_drift_pct": 0.0, "exit_eval_failures": 0,
    "cycle_consecutive_failures": 0, "runner_state": "RUNNING",
    "halted": False, "entries_enabled": True, "audit_dropped_writes": 0,
    "audit_tail_truncations": 0,
    "positions": [{"symbol": "BTC/USD", "direction": "long", "entry": 60000.0,
                   "mark": 60600.0, "size": 0.001, "stop": 58800.0,
                   "upnl_usd": 0.6, "upnl_pct": 1.0, "tiers_fired": 1,
                   "age_h": 2.0, "p_win": 0.7}],
    "performance": {
        "overall": {"trades": 20, "win_rate": 0.55, "win_rate_lcb": 0.34,
                    "profit_factor": 1.8, "expectancy_usd": 2.3,
                    "expectancy_r": 0.4, "payoff_ratio": 1.6, "sharpe": 0.9,
                    "sortino": 1.1, "cur_loss_streak": 1, "max_loss_streak": 4,
                    "net_usd": 46.0, "gross_profit_usd": 90.0,
                    "gross_loss_usd": 44.0, "avg_win_usd": 8.0,
                    "avg_loss_usd": -4.9},
        "by_asset": {"BTC": {"trades": 8, "win_rate": 0.5,
                             "profit_factor": 1.2, "expectancy_usd": 1.0,
                             "net_usd": 5.0, "cur_loss_streak": 2,
                             "max_loss_streak": 3}}},
    "order_manager": {"venue_rejects": 0, "deadman_failures": 0,
                      "latency_ms": 40.0, "maker_fills": 7, "taker_fills": 3,
                      "maker_share": 0.7, "maker_notional_usd": 500.0,
                      "taker_notional_usd": 200.0, "avg_slip_bps": -1.0,
                      "worst_slip_bps": 6.0},
    "markout": {"horizons_sec": [5.0], "pending": 0, "overall": {},
                "by_asset": {"BTC": {"5": {"markout_bps": -2.0, "n": 4}}}},
    "monitor": {"level": 0, "drift_share": 0.0, "brier": 0.2,
                "baseline_brier": 0.24, "calibration_gap": 0.05,
                "window_trades": 20, "shrinkage": 0.35, "kelly_mult": 1.0,
                "stop_widen": 1.0, "edge_ratio_bump": 0.0, "use_model": True,
                "champion_brier": 0.19, "hit_rate": 0.6, "hit_rate_lcb": 0.4,
                "avg_p": 0.65},
    "ml": {"history_rows": 100, "open_candidates": 5, "pending_labels": 2,
           "model_fallbacks": 0, "infer_faults": 0, "contract_failed": 0,
           "smc_faults": 0, "retrain_failures": 0, "retrain_flag": False,
           "model_kind": "blend",
           "labels_by_source": {"live": 20, "candidate": 80},
           "gate_stats": {"enabled": True, "labeled": 100, "base_rate": 0.2,
                          "weights": {"if_1_flow_persistence": 0.9}}},
    "signals": {"BTC": {"confirmed": True, "confidence": 0.8, "urgency": 0.4,
                        "concentration": 0.6,
                        "gates": {"if_1_flow_persistence": True}}},
    "manip_suspect": {"BTC": 0.1},
    "regimes": {"BTC": {"macro": "range", "momentum": 0.1, "vol": "low",
                        "vol_pct": 20.0, "liq": "liquid", "spread_bps": 0.5,
                        "spoof": 0.0, "basis_bps": -1.0}},
    "code_stats": {"by_prefix": {"PT": 9},
                   "entry_codes": {"PT-041": 6, "PT-050": 2}},
    "ws_kraken": {"connected": True, "books": 6, "reconnects": 0},
    "fault": {"state": "ARMED", "faults": {}},
    "watchdog": {"entries_blocked": False, "critical_stale": False,
                 "velocity_tripped": False, "divergent": [],
                 "stale_assets": []},
    "firewall": {"fault": None, "counters": {"FW-040": 2}},
    "circuit_breaker": {"enabled": True, "loss_streak": 4,
                        "streaks": {"BTC": 1}, "tripped": {"ETH": 3.0}},
    "risk_protocols": {"daily_budget_used_frac": 0.1,
                       "weekly_budget_used_frac": 0.05, "taper_mult": 1.0,
                       "heat_frac": 0.04, "heat_cap_frac": 0.35,
                       "dd_throttle_mult": 1.0},
    "skimmer": {"enabled": True, "candidates": 8, "max_extra": 6,
                "promoted": ["SOL/USD"],
                "scores": {"SOL/USD": {"score": 0.7, "spread_bps": 2.0,
                                       "depth_usd": 60000, "ts": 1.7e9}}},
}


def _shipped(fname: str) -> dict:
    return json.loads((ROOT / "docs" / "grafana" / fname)
                      .read_text(encoding="utf-8"))


def test_generator_matches_shipped_json():
    for fname, d in gen.DASHBOARDS.items():
        assert d == _shipped(fname), \
            f"{fname} differs from the generator — regenerate with " \
            "`python scripts/build_trading_dashboard.py` (never hand-edit)"


def test_expected_boards_present():
    assert set(gen.DASHBOARDS) == {
        "liquiditybot_command.json", "liquiditybot_execution.json",
        "liquiditybot_problem_solution.json", "liquiditybot_screening.json"}


def test_importable_shape_and_layout_per_board():
    uids = set()
    for fname in gen.DASHBOARDS:
        d = _shipped(fname)
        assert "dashboard" not in d and d["schemaVersion"] == 39, fname
        assert d["uid"] and d["uid"] not in uids, f"{fname}: uid not unique"
        uids.add(d["uid"])
        assert d["panels"] and d["panels"][0]["gridPos"]["y"] == 0, fname
        ids = [p["id"] for p in d["panels"]]
        assert len(ids) == len(set(ids)), f"{fname}: duplicate panel ids"
        rects = [(p["gridPos"]["x"], p["gridPos"]["y"], p["gridPos"]["w"],
                  p["gridPos"]["h"], p["id"]) for p in d["panels"]]

        def ov(a, b):
            return not (a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0]
                        or a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1])
        bad = [(a[4], b[4]) for i, a in enumerate(rects)
               for b in rects[i + 1:] if ov(a, b)]
        assert not bad, f"{fname}: overlapping panels: {bad}"
    # the command board keeps the desk uid so it replaces the old monolith
    assert _shipped("liquiditybot_command.json")["uid"] == "liquiditybot-trading"


def test_all_boards_use_supported_panel_types():
    # professional mix: stat (sparkline) / gauge / bargauge / timeseries /
    # color-coded table. The deprecated "graph" plugin is never allowed.
    allowed = {"row", "stat", "table", "gauge", "timeseries", "bargauge"}
    for fname in gen.DASHBOARDS:
        kinds = {p["type"] for p in _shipped(fname)["panels"]}
        assert "graph" not in kinds, f"{fname}: deprecated graph panel"
        assert kinds <= allowed, f"{fname}: unexpected panel type {kinds}"


def test_has_per_asset_comparison_table():
    d = _shipped("liquiditybot_command.json")
    tables = [p for p in d["panels"] if p["type"] == "table"]
    # a table joined on the `asset` label = the decision-comparison scorecard
    asset_tbl = [t for t in tables if any(
        "asset" in str(tr.get("expr", "")) or
        tr.get("expr", "").find("perf_asset") >= 0 for tr in t["targets"])]
    assert asset_tbl, "per-asset comparison table is the decision centrepiece"


def test_every_query_hits_an_emitted_metric(tmp_path):
    p = tmp_path / "status.json"
    p.write_text(json.dumps(_SYNTH_STATUS), encoding="utf-8")
    emitted = {m["name"] for m in gp.collect(str(p))}
    referenced = set()
    for d in gen.DASHBOARDS.values():
        for panel in d["panels"]:
            for t in panel.get("targets", []):
                referenced |= set(re.findall(r"liquiditybot_[a-z_]+",
                                             t["expr"]))
    missing = referenced - emitted
    assert not missing, f"panels query metrics gc_pusher never emits: {missing}"
