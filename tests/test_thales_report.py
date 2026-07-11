"""scripts/thales_report.py: parse durable THALES shadow evidence out of
events.jsonl and render a promotion-readiness verdict without tuning any
threshold or promoting anything."""
import json

from scripts.thales_report import build_report, parse_events


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
    assert rows[0] == ("BTC", 0.909, {"TH-013"})
    assert rows[1][0] == "ETH" and rows[1][2] == {"TH-011"}


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
