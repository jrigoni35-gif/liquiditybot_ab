"""Per-asset label cost + multi-horizon shadow evidence.

1. A wide-spread (small-cap) candidate's label must reflect its OWN cost,
   not the flat fee floor - the mechanism that stops the model learning to
   scalp illiquid pairs into losses.
2. With no spread passed, cost == the fee floor (backward compatible with
   every existing label).
3. Multi-horizon scoring writes shadow rows (one per horizon) to a
   SEPARATE fixed-schema file, never to signal_history, and never changes
   the primary label.
4. config_guard rejects a horizon longer than the primary label horizon.
5. scripts/horizon_report ranks each asset's best horizon by net return.
"""
import csv

import numpy as np

from ml.history import CandidateLabeler, HistoryStore, HorizonShadowStore


def _labeler(tmp_path, ml_cfg, shadow=None):
    return CandidateLabeler(HistoryStore(str(tmp_path / "sig.csv")),
                            ml_cfg, shadow_store=shadow)


def test_spread_raises_label_cost_for_small_cap():
    lab = CandidateLabeler(HistoryStore("x"), {"label_round_trip_cost_pct": 0.5})
    cheap = lab._cost_pct({"spread_bps": 0.0})
    wide = lab._cost_pct({"spread_bps": 40.0})
    assert cheap == 0.5                       # fee floor only
    assert abs(wide - (0.5 + 0.40)) < 1e-9    # + 40bps spread


def test_spread_cost_is_capped():
    lab = CandidateLabeler(HistoryStore("x"),
                           {"label_round_trip_cost_pct": 0.5,
                            "label_spread_cap_bps": 60})
    assert abs(lab._cost_pct({"spread_bps": 500.0}) - (0.5 + 0.60)) < 1e-9


def test_include_spread_off_is_backward_compatible():
    lab = CandidateLabeler(HistoryStore("x"),
                           {"label_round_trip_cost_pct": 0.5,
                            "label_include_spread": False})
    assert lab._cost_pct({"spread_bps": 40.0}) == 0.5


def _feed_ramp(lab, asset, n=130):
    # a slow upward drift: +~0.3% over the window, small per-bar moves
    for k in range(n):
        px = 1.0 + 0.00003 * k
        lab.update_candles(asset, [{"time": k, "open": px, "high": px * 1.0002,
                                    "low": px * 0.9998, "close": px,
                                    "volume": 1.0}])


def test_multi_horizon_writes_one_shadow_row_per_horizon(tmp_path):
    shadow = HorizonShadowStore(str(tmp_path / "hz.csv"))
    lab = _labeler(tmp_path, {"label_max_bars": 96,
                              "multi_horizon": {"enabled": True,
                                                "horizons_bars": [24, 48, 96]}},
                   shadow=shadow)
    feats = np.zeros(43)
    lab.update_candles("MINA", [{"time": 0, "open": 1.0, "high": 1.0,
                                 "low": 1.0, "close": 1.0, "volume": 1.0}])
    lab.register("MINA", "long", feats, 0.01, 0, spread_bps=30.0)
    _feed_ramp(lab, "MINA", 130)
    assert lab.poll() == 1                       # primary label fired

    with open(tmp_path / "hz.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert [int(r["horizon_bars"]) for r in rows] == [24, 48, 96]
    assert all(r["asset"] == "MINA" for r in rows)
    assert rows[0].__contains__("net_ret_pct")


def test_shadow_disabled_writes_nothing(tmp_path):
    lab = _labeler(tmp_path, {"label_max_bars": 96})   # no multi_horizon
    feats = np.zeros(43)
    lab.update_candles("ETH", [{"time": 0, "open": 1.0, "high": 1.0,
                                "low": 1.0, "close": 1.0, "volume": 1.0}])
    lab.register("ETH", "long", feats, 0.01, 0)
    _feed_ramp(lab, "ETH", 130)
    lab.poll()
    assert lab.horizons == [] and lab.shadow_store is None


def test_horizon_shadow_store_fixed_header(tmp_path):
    s = HorizonShadowStore(str(tmp_path / "h.csv"))
    s.append("cand-1", "SUI", "long", 24, 1, 0.42, "pt")
    with open(tmp_path / "h.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0] == HorizonShadowStore.HEADER
    assert rows[1][:5] == ["cand-1", "SUI", "long", "24", "1"]


def test_guard_fatal_on_horizon_over_max_bars():
    from core.config_guard import validate
    cfg = {"system": {"dry_run": True},
           "ml": {"label_max_bars": 96,
                  "multi_horizon": {"enabled": True,
                                    "horizons_bars": [24, 200]}}}
    fatals = [m for sev, m in validate(cfg) if sev == "FATAL"]
    assert any("label_max_bars" in m for m in fatals)


def test_horizon_report_ranks_best_per_asset(tmp_path):
    from scripts.horizon_report import build_report
    p = tmp_path / "hz.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HorizonShadowStore.HEADER)
        # MINA pays over the long horizon, loses short
        for i in range(25):
            w.writerow([f"c{i}", "MINA", "long", 24, 0, -0.30, "time", 1])
            w.writerow([f"c{i}", "MINA", "long", 96, 1, 0.80, "pt", 1])
    out = build_report(p, min_samples=20)
    assert "MINA: 96 bars" in out
