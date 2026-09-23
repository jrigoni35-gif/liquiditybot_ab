# tests/test_operator_page.py
"""Correctness-contract tests for scripts/operator_page.py."""
import json

from scripts.operator_page import (  # noqa: E402
    build_state,
    position_rows,
    tile,
)


def _write(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")


def _status(tmp, **over):
    s = {"ts": 1000.0, "runner_state": "RUNNING", "mode": "DRY_RUN",
         "entries_enabled": True, "halted": False,
         "fault": {"state": "ARMED", "faults": {}}, "equity": 766.42,
         "cash": 761.13, "savings": 5.57, "reserve": 0.19,
         "weekly_pnl": -1.93, "monthly_pnl": -18.84}
    s.update(over)
    _write(tmp / "status.json", s)
    return s


def test_tile_fresh_stale_nosource():
    ok = tile("x", 1, source="s", as_of=100.0, cadence=60, now=110.0)
    stale = tile("x", 1, source="s", as_of=0.0, cadence=60, now=1000.0)
    none = tile("x", None, source="s", as_of=None, cadence=60, now=1000.0)
    assert ok["status"] == "ok" and ok["age_s"] == 10.0
    assert stale["status"] == "stale"
    assert none["status"] == "nosource"


def test_money_equity_agreement_and_mismatch(tmp_path):
    _status(tmp_path)
    (tmp_path / "equity.csv").write_text("1,766.42,0.00\n", encoding="utf-8")
    st = build_state(tmp_path, tmp_path / "boards", now=1010.0)
    eq = [t for t in st["sections"]["money"] if t["label"] == "equity"][0]
    assert eq["status"] == "ok" and eq["value"] == 766.42
    (tmp_path / "equity.csv").write_text("1,800.00,0.00\n", encoding="utf-8")
    st = build_state(tmp_path, tmp_path / "boards", now=1010.0)
    eq = [t for t in st["sections"]["money"] if t["label"] == "equity"][0]
    assert eq["status"] == "mismatch"


def test_position_rows_net(tmp_path):
    (tmp_path / "fills.csv").write_text(
        "ts,order_id,position_id,purpose,symbol,side,ordertype,post_only,"
        "attempt,fill_size,fill_price,arrival_ref,slip_bps,fees_delta_usd,"
        "remaining,reason,exec_era,book\n"
        "1,o1,p1,entry,PAXG/USD,buy,limit,t,1,1.0,100.0,,0,0,0,,e,5m\n"
        "2,o2,p1,exit,PAXG/USD,sell,limit,f,1,0.4,101.0,,0,0,0,,e,5m\n"
        "3,o3,p2,entry,BTC/USD,buy,limit,t,1,0.001,50000.0,,0,0,0,,e,long\n",
        encoding="utf-8")
    rows, as_of = position_rows(tmp_path / "fills.csv")
    by = {r["symbol"]: r for r in rows}
    assert abs(by["PAXG/USD"]["net_qty"] - 0.6) < 1e-9
    assert by["BTC/USD"]["net_qty"] == 0.001
    assert by["PAXG/USD"]["legs"] == 2 and as_of == 3.0


def test_build_state_never_raises_on_empty(tmp_path):
    st = build_state(tmp_path, tmp_path / "boards", now=1000.0)
    assert st["generated_at"] == 1000.0
    for name in ("posture", "money", "judge", "era", "boards"):
        assert all(t["status"] == "nosource"
                   for t in st["sections"][name]
                   if isinstance(t, dict) and "status" in t)
    assert st["sections"]["positions"]["rows"] == []


def test_render_html_badges(tmp_path):
    from scripts.operator_page import render_html  # noqa: PLC0415
    _status(tmp_path, ts=0.0)  # ancient => stale
    st = build_state(tmp_path, tmp_path / "boards", now=1000.0)
    html = render_html(st)
    assert "STALE" in html and "window.__STATE__" in html
    assert "RUNNING" in html  # values render even when stale


def test_once_writes_html(tmp_path):
    from scripts.operator_page import main  # noqa: PLC0415
    out = tmp_path / "page.html"
    rc = main(["--once", "--out", str(out), "--no-render",
               "--outputs", str(tmp_path)])
    assert rc == 0
    body = out.read_text(encoding="utf-8")
    assert "<html" in body and "nosource" in body  # empty dir, truthful


def test_fetch_boards_writes_and_reports(tmp_path):
    from scripts.operator_page import fetch_boards  # noqa: PLC0415
    tok = tmp_path / "tok"
    tok.write_text("secret", encoding="utf-8")

    def fake(url, headers):
        assert headers["Authorization"] == "Bearer secret"
        return b"\x89PNG"

    res = fetch_boards(tmp_path / "b", token_file=tok, fetcher=fake)
    assert all(v == "ok" for v in res.values())
    png = tmp_path / "b" / "liquiditybot-trading.png"
    assert png.read_bytes() == b"\x89PNG"


def test_fetch_boards_no_token_is_skip(tmp_path):
    from scripts.operator_page import fetch_boards  # noqa: PLC0415
    res = fetch_boards(tmp_path / "b", token_file=tmp_path / "absent",
                       fetcher=lambda u, h: b"x")
    assert all(v.startswith("skip") for v in res.values())
    assert not list((tmp_path / "b").glob("*.png"))
