"""tests/test_glass_console.py — the box-rendered glass console.

Pins for the presentation layer over the shared state files: it must render
a complete page from real-shaped state, ESCAPE everything it quotes (state
strings reach a browser — a poisoned symbol must never become markup),
degrade honestly when inputs are absent, and feed ONLY current-era fills.
"""
import json

import pytest

import scripts.glass_console as gc


@pytest.fixture()
def state(tmp_path, monkeypatch):
    status = tmp_path / "status.json"
    fills = tmp_path / "fills.csv"
    equity = tmp_path / "equity.csv"
    monkeypatch.setattr(gc, "STATUS", status)
    monkeypatch.setattr(gc, "FILLS", fills)
    monkeypatch.setattr(gc, "EQUITY", equity)
    status.write_text(json.dumps({
        "ts": 1788120000.0, "runner_state": "RUNNING", "mode": "DRY_RUN",
        "equity": 798.21, "daily_pnl": -1.62, "weekly_pnl": -4.8,
        "drawdown_pct": 0.62, "fees_total": 9.62,
        "positions": [{"symbol": "ETH/USD", "direction": "long",
                       "size": 0.0188, "entry": 2443.82, "mark": 2492.88,
                       "upnl_pct": 2.007, "upnl_usd": 0.92, "age_h": 186.7}],
        "regimes": {"BTC": {"macro": "bull_quiet", "spoof": 0.0},
                    "FLOW": {"macro": "bear", "spoof": 1.0}},
        "monitor": {"brier": 0.2485, "baseline_brier": 0.25,
                    "drift_share": 0.367, "level": 1, "kelly_mult": 0.7,
                    "shrinkage": 0.525},
        "ml": {"history_rows": 10235, "pending_labels": 41},
    }), encoding="utf-8")
    fills.write_text(
        "ts,symbol,side,purpose,fill_size,fill_price,fees_delta_usd,exec_era\n"
        "1788110677.0,XRP/USD,sell,exit,12.9,1.41228,0.069," + gc.EXEC_ERA +
        "\n1788000000.0,OLD/USD,buy,entry,1.0,1.0,0.01,8-ca55e2ba\n",
        encoding="utf-8")
    equity.write_text("ts,equity\n1788119940.0,798.30\n1788120000.0,798.21\n",
                      encoding="utf-8")
    return tmp_path


def test_renders_complete_page_from_state(state):
    page = gc.build(now=1788120060.0)
    assert page.startswith("<!doctype html>")
    assert "798.21" in page                      # equity reaches the hero
    assert "ETH/USD" in page and "bull_quiet" in page
    assert gc.EXEC_ERA in page                   # era chip
    # honesty stamps: rendered instant + status age both on the page
    assert "rendered 2026-08-30" in page
    assert "status age 60s" in page


def test_current_era_filter_excludes_prior_cuts(state):
    page = gc.build(now=1788120060.0)
    assert "XRP/USD" in page
    assert "OLD/USD" not in page                 # 8-ca55e2ba row filtered out
    assert "1 fills" in page                     # count is era-scoped


def test_state_strings_are_escaped_before_markup(state, monkeypatch):
    # SECURITY: plant markup in every string field the page quotes; none may
    # survive as live markup. (status.json is written by our own runner, but
    # the console must not be the one component that trusts it blindly.)
    status = json.loads(gc.STATUS.read_text(encoding="utf-8"))
    status["positions"][0]["symbol"] = "<script>alert(1)</script>"
    status["regimes"]["<img onerror=x src=y>"] = {"macro": "<b>bear</b>"}
    gc.STATUS.write_text(json.dumps(status), encoding="utf-8")
    page = gc.build(now=1788120060.0)
    assert "<script>alert(1)</script>" not in page
    assert "<img onerror" not in page
    assert "<b>bear</b>" not in page
    assert "&lt;script&gt;" in page              # escaped form present


def test_absent_inputs_degrade_honestly_never_raise(tmp_path, monkeypatch):
    monkeypatch.setattr(gc, "STATUS", tmp_path / "missing_status.json")
    monkeypatch.setattr(gc, "FILLS", tmp_path / "missing_fills.csv")
    monkeypatch.setattr(gc, "EQUITY", tmp_path / "missing_equity.csv")
    page = gc.build(now=1788120060.0)
    assert page.startswith("<!doctype html>")
    assert "status MISSING" in page              # labeled, not invented
    assert "book flat" in page
    assert "no fills stamped" in page


def test_render_writes_the_output_file(state, tmp_path):
    out = tmp_path / "console.html"
    p = gc.render(out)
    assert p == out and out.stat().st_size > 4000
    assert out.read_text(encoding="utf-8").startswith("<!doctype html>")
