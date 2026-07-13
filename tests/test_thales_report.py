"""scripts/thales_report.py: parse durable THALES shadow evidence out of
events.jsonl and render a promotion-readiness verdict without tuning any
threshold or promoting anything."""
import json

from scripts.thales_report import (build_report, counterfactual_join,
                                   load_labeled_rows, parse_events)


def _write_events(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for msg in rows:
            f.write(json.dumps({"level": "INFO",
                                "logger": "liquiditybot.main",
                                "msg": msg}) + "\n")


def test_parse_extracts_asset_mult_and_codes(tmp_path):
    ev = tmp_path / "events.jsonl"
    _write_events(ev, [
        "thales BTC: TH-000: would x0.909; TH-013: stop-cluster proximity",
        "thales ETH: TH-000: would x1.120; TH-011: metro stale-quote edge",
        "unrelated log line, not thales",
    ])
    rows = list(parse_events(ev))
    assert len(rows) == 2
    assert rows[0][1:] == ("BTC", 0.909, {"TH-013"})
    assert rows[1][1] == "ETH" and rows[1][3] == {"TH-011"}


def test_report_counts_shades_and_flags_ready_detector(tmp_path):
    ev = tmp_path / "events.jsonl"
    rows = [f"thales BTC: TH-000: would x0.90{i % 10}; TH-013: stop cluster"
            for i in range(35)]
    _write_events(ev, rows)
    out = build_report(ev, tmp_path / "missing_status.json", min_fires=30)
    assert "advice events observed: 35" in out
    assert "TH-013" in out
    assert "enough to evaluate a shadow->advise A/B" in out
    assert "down" in out                       # all shades are < 1.0


def test_report_not_ready_below_bar(tmp_path):
    ev = tmp_path / "events.jsonl"
    _write_events(ev, [
        "thales BTC: TH-000: would x0.95; TH-013: stop cluster"] * 5)
    out = build_report(ev, tmp_path / "s.json", min_fires=30)
    assert "NOT READY" in out


def test_report_handles_no_events(tmp_path):
    ev = tmp_path / "events.jsonl"
    ev.write_text("", encoding="utf-8")
    out = build_report(ev, tmp_path / "s.json", min_fires=30)
    assert "no THALES advice recorded yet" in out


def test_missing_events_file_is_safe(tmp_path):
    out = build_report(tmp_path / "nope.jsonl", tmp_path / "s.json", 30)
    assert "no THALES advice recorded yet" in out


def _write_history(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        f.write("ts,asset,label,net_pnl_usd\n")
        for ts, asset, label, net in rows:
            f.write(f"{ts},{asset},{label},{net}\n")


def test_counterfactual_join_buckets_by_asset_and_window():
    fires = {"BTC": [1000.0]}
    rows = [(1050.0, "BTC", 1, 0.5),     # inside window, same asset
            (2000.0, "BTC", 0, -0.3),    # outside window
            (1050.0, "ETH", 1, 0.2)]     # same window, other asset
    j = counterfactual_join(fires, rows, window_sec=100.0)
    assert j["exposed"]["n"] == 1 and j["exposed"]["win_rate"] == 100.0
    assert j["unexposed"]["n"] == 2
    assert abs(j["exposed"]["net_usd"] - 0.5) < 1e-9


def test_report_renders_counterfactual_and_starved_verdict(tmp_path):
    ev = tmp_path / "events.jsonl"
    with open(ev, "w", encoding="utf-8") as f:
        for i in range(35):
            f.write(json.dumps({
                "ts": 1000.0 + i, "level": "INFO",
                "logger": "liquiditybot.main",
                "msg": "thales BTC: TH-000: would x0.950; TH-013: stop "
                       "cluster"}) + "\n")
    hist = tmp_path / "signal_history.csv"
    _write_history(hist, [(1100.0, "BTC", 1, 0.4), (9999999.0, "BTC", 0, -0.2)])
    out = build_report(ev, tmp_path / "s.json", min_fires=30,
                       history_path=hist, exposure_hours=8.0)
    assert "counterfactual (exposure join" in out
    assert "TH-013: exposed n=1 win=100% net=$+0.40" in out
    assert "data-starved" in out
    assert load_labeled_rows(hist)[0][1] == "BTC"


def test_report_counterfactual_notes_missing_history(tmp_path):
    ev = tmp_path / "events.jsonl"
    _write_events(ev, ["thales BTC: TH-000: would x0.95; TH-013: x"] * 35)
    out = build_report(ev, tmp_path / "s.json", min_fires=30,
                       history_path=tmp_path / "absent.csv")
    assert "the join activates as signal_history accrues" in out
