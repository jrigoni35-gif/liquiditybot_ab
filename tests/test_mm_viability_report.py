"""scripts/mm_viability_report.py - instrument pins (no network)."""
import csv

import numpy as np
import pytest

from scripts import mm_viability_report as mm


def _fills(tmp_path, rows):
    p = tmp_path / "fills.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ts", "symbol", "side", "fill_price",
                                          "purpose", "post_only"])
        w.writeheader()
        w.writerows(rows)
    return p


def test_only_post_only_legs_and_units_normalised(tmp_path):
    t = 1_790_000_000
    p = _fills(tmp_path, [
        {"ts": t, "symbol": "ETH/USD", "side": "buy", "fill_price": 100, "purpose": "entry", "post_only": 1},
        {"ts": t * 1000, "symbol": "BTC/USD", "side": "sell", "fill_price": 100, "purpose": "exit", "post_only": "1"},
        {"ts": t, "symbol": "ETH/USD", "side": "sell", "fill_price": 100, "purpose": "exit", "post_only": 0},
    ])
    out = mm.load_maker_fills(p)
    assert [x["asset"] for x in out] == ["ETH", "BTC"]
    assert all(x["ts"] == pytest.approx(t) for x in out)      # ms -> s


def test_markout_is_adverse_when_price_runs_through_a_buy(tmp_path, monkeypatch):
    """A maker buy filled at bar k, then price falls: alpha < 0 (picked off)."""
    t0 = 1_790_000_000.0
    opens = t0 + np.arange(1200) * 300.0              # above the 1,000-bar floor
    close = np.r_[np.full(100, 100.0), np.linspace(100, 90, 1100)]
    monkeypatch.setattr(mm, "binance_klines",
                        lambda *a, **k: {"t": opens, "close": close})
    fills = [{"ts": opens[150] + 10, "asset": "ETH", "side": "buy", "price": 100.0}]
    rows = mm.markouts(fills, tmp_path)["ETH"]
    assert len(rows) == 1
    al = rows[0][1]
    assert al[5] < 0 and al[60] < al[5]
    sell = [{"ts": opens[150] + 10, "asset": "ETH", "side": "sell", "price": 100.0}]
    assert mm.markouts(sell, tmp_path)["ETH"][0][1][60] > 0


def test_half_spread_is_half_the_median(tmp_path):
    p = tmp_path / "sh.csv"
    p.write_text("asset,spread_bps\nETH,2\nETH,4\nETH,0\nBTC,1\n", encoding="utf-8")
    hs = mm.median_half_spread(p)
    assert hs == {"BTC": 0.5, "ETH": 1.5}                     # zero spreads dropped
