"""scripts/asset_learning_report.py: reconcile per-asset outputs into a
read-only progress table, classifying each pair (learning / gated / quiet)
without touching live state."""
import csv
import json

from scripts.asset_learning_report import _candidate_counts, build_report


def _setup(o):
    (o / "status.json").write_text(json.dumps({"regimes": {
        "BTC": {"macro": "bull", "liq": "liquid", "spread_bps": 1.0,
                "spoof": 0.0, "vol_pct": 20},
        "MINA": {"macro": "range", "liq": "spoofy", "spread_bps": 18.5,
                 "spoof": 1.0, "vol_pct": 17},
        "SUI": {"macro": "range", "liq": "thin", "spread_bps": 1.4,
                "spoof": 0.02, "vol_pct": 7},
    }}), encoding="utf-8")
    (o / "state.json").write_text(json.dumps(
        {"candidates": {"_cands": [{"asset": "BTC"}, {"asset": "BTC"}]}}),
        encoding="utf-8")
    with open(o / "signal_history.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["asset", "source", "label"])
        w.writerow(["BTC", "live", "1"])
        w.writerow(["BTC", "candidate", "0"])
    with open(o / "horizon_shadow.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["candidate_id", "asset", "direction", "horizon_bars",
                    "label", "net_ret_pct", "exit_reason", "ts"])
        w.writerow(["c1", "BTC", "long", "24", "1", "0.010000", "pt",
                    "1700000000"])
        w.writerow(["c1", "BTC", "long", "96", "1", "0.030000", "pt",
                    "1700000000"])


def test_report_classifies_each_asset(tmp_path):
    _setup(tmp_path)
    rep = build_report(str(tmp_path))
    assert "[BTC] learning" in rep                 # candidates + labels
    assert "gated: illiquid/spoofy" in rep         # MINA spoofy/wide-spread
    assert "quiet: no confirmed signal" in rep     # SUI clean but idle
    assert "h24" in rep and "h96" in rep           # horizon evidence shown


def test_candidate_counts_handles_nested_dict():
    c = _candidate_counts(
        {"candidates": {"_cands": [{"asset": "SUI"}, {"asset": "SUI"}]}})
    assert c["SUI"] == 2


def test_missing_files_are_safe(tmp_path):
    rep = build_report(str(tmp_path))              # no output files at all
    assert "per-asset learning progress" in rep
