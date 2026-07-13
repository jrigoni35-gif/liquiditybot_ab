"""Pipeline-audit funnel counting (pure functions, synthetic streams)."""
import time

from scripts.pipeline_audit import (funnel_from_events, labels_in_window,
                                    verdict)


def _ev(msg, level="INFO", ts=None):
    return {"ts": ts or time.time(), "level": level, "msg": msg}


def test_funnel_counts_each_stage():
    events = [
        _ev("IF3 signal BTC long: E=+1.93 agree=4/5"),
        _ev("IF3 signal BTC long: E=+1.26 agree=3/5"),
        _ev("[BTC] exploration yielded: asset holds 22/37 labeled rows"),
        _ev("[ETH] EXPLORATION paper entry: model p=0.56 -> sizing p=0.62"),
        _ev("[ETH] sizer veto: SZ-060: x1.10; SZ-042: $4 below minimum"),
        _ev("ENTRY long ETH/USD [improve]: $15 (0.008) @ 1822.22 | p=0.62"),
        _ev("CLOSE 0.008 ETH/USD @ 1830.00"),
        _ev("boom", level="ERROR"),
    ]
    f = funnel_from_events(events)
    assert f["signals_confirmed"]["BTC"] == 2
    assert f["exploration_yielded"]["BTC"] == 1
    assert f["exploration_entries"]["ETH"] == 1
    assert f["sizer_vetoes"]["SZ-042"] == 1
    assert f["entries_filled"]["ETH"] == 1
    assert f["closes"] == 1 and f["errors"] == 1


def test_labels_window_and_economics(tmp_path):
    p = tmp_path / "h.csv"
    now = time.time()
    p.write_text(
        "position_id,asset,side,label,net_pnl_usd,source,ts\n"
        f"a,ETH,long,1,2.50,live,{now:.0f}\n"
        f"b,BTC,long,0,-1.00,candidate,{now:.0f}\n"
        f"c,BTC,long,1,3.00,live,{now - 999999:.0f}\n",   # outside window
        encoding="utf-8")
    out = labels_in_window(p, since=now - 3600)
    assert out["rows"] == 2 and out["wins"] == 1
    assert out["net_pnl"] == 1.5
    assert out["by_asset"] == {"ETH": 1, "BTC": 1}


def test_verdict_flags_sizing_wall_and_profit():
    f = funnel_from_events([
        _ev("IF3 signal BTC long: E=+1.0"),
        _ev("[BTC] sizer veto: SZ-042: $4 below minimum")])
    finds = verdict(f, {"rows": 0, "wins": 0, "net_pnl": 0.0}, {})
    assert any("SIZING WALL" in x for x in finds)
    finds2 = verdict(f, {"rows": 10, "wins": 6, "net_pnl": 4.0},
                     {"monitor": {"level": 2}})
    assert any("PROFIT-POSITIVE" in x for x in finds2)
    assert any("GOVERNOR L2" in x for x in finds2)
