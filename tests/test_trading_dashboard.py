"""tests/test_trading_dashboard.py — the trading dashboard's structural
contract, CI-enforced:

  1. the generator (scripts/build_trading_dashboard.py — the SOURCE OF TRUTH)
     and the shipped docs/grafana/liquiditybot_trading.json are identical, so
     hand-edits or a stale regeneration can't drift them apart;
  2. valid UI-importable shape: unwrapped, schemaVersion at top level, stable
     uid, unique panel ids, no overlapping gridPos;
  3. EVERY liquiditybot_* metric referenced by a panel query is actually
     emitted by scripts/gc_pusher.py — a renamed/removed metric breaks the
     build instead of silently blanking a panel ("code reacts to the panels").
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
                        "gates": {"if_1_flow_persistence": True}}},
    "manip_suspect": {"BTC": 0.1},
    "regimes": {"BTC": {"macro": "range", "momentum": 0.1, "vol": "low",
                        "vol_pct": 20.0, "liq": "liquid", "spread_bps": 0.5,
                        "spoof": 0.0, "basis_bps": -1.0}},
    "code_stats": {"by_prefix": {"PT": 9},
                   "entry_codes": {"PT-041": 6, "PT-050": 2}},
    "risk_protocols": {"daily_budget_used_frac": 0.1,
                       "weekly_budget_used_frac": 0.05, "taper_mult": 1.0,
                       "heat_frac": 0.04, "heat_cap_frac": 0.35,
                       "dd_throttle_mult": 1.0},
    "firewall": {"fault": None, "counters": {"FW-040": 2}},
}


def _shipped() -> dict:
    return json.loads((ROOT / "docs" / "grafana" /
                       "liquiditybot_trading.json").read_text(encoding="utf-8"))


def test_generator_matches_shipped_json():
    assert gen.dash == _shipped(), \
        "generator and shipped JSON differ — regenerate with " \
        "`python scripts/build_trading_dashboard.py` (never hand-edit the JSON)"


def test_importable_shape_and_layout():
    d = _shipped()
    assert "dashboard" not in d and d["schemaVersion"] == 39
    assert d["uid"] == "liquiditybot-trading"     # stable => re-import overwrites
    ids = [p["id"] for p in d["panels"]]
    assert len(ids) == len(set(ids)), "duplicate panel ids"
    rects = [(p["gridPos"]["x"], p["gridPos"]["y"], p["gridPos"]["w"],
              p["gridPos"]["h"], p["id"]) for p in d["panels"]]

    def ov(a, b):
        return not (a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0]
                    or a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1])
    bad = [(a[4], b[4]) for i, a in enumerate(rects)
           for b in rects[i + 1:] if ov(a, b)]
    assert not bad, f"overlapping panels: {bad}"


def test_every_query_hits_an_emitted_metric(tmp_path):
    p = tmp_path / "status.json"
    p.write_text(json.dumps(_SYNTH_STATUS), encoding="utf-8")
    emitted = {m["name"] for m in gp.collect(str(p))}
    referenced = set()
    for panel in _shipped()["panels"]:
        for t in panel.get("targets", []):
            referenced |= set(re.findall(r"liquiditybot_[a-z_]+", t["expr"]))
    missing = referenced - emitted
    assert not missing, f"panels query metrics gc_pusher never emits: {missing}"
