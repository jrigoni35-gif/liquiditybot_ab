"""
Regression for the forming-candle leak (found in the 2026-07-13 timestamp
audit): all three venues serve the still-forming bar as the last OHLC
row, and CandidateLabeler.update_candles's append-only cache froze its
first sight forever - understated highs/lows for every triple-barrier
walk, crushed sigma/ATR inputs, and THALES detectors fed partial bars.
Proven live: an OKX 1m bar's low moved $8 within 25s of first sight.

Pins: drop_forming_candles keeps committed bars only (boundary bar is
committed), interval parsing is case-sensitive (Binance 1m minute vs 1M
month), every feed drops the forming bar by default, and the daily
regime path deliberately keeps today's partial bar (include_forming).
"""
import time

from core.sanitize import drop_forming_candles, interval_str_to_sec
from data.binanceus_feed import BinanceUSFeed
from data.kraken_feed import KrakenFeed
from data.okx_feed import OKXFeed


def _bars(now, interval, n=3):
    """n bars ending with one whose window contains `now` (forming)."""
    start = int(now - now % interval)
    return [{"time": start - k * interval, "open": 10.0, "high": 11.0,
             "low": 9.0, "close": 10.5, "volume": 1.0}
            for k in range(n - 1, -1, -1)]


def test_drop_forming_keeps_committed_only():
    now = 1_000_000.0
    bars = _bars(now, 300)
    out = drop_forming_candles(bars, 300, now=now)
    assert len(out) == len(bars) - 1
    assert all(b["time"] + 300 <= now for b in out)


def test_drop_forming_boundary_bar_is_committed():
    # window [700, 1000) closes exactly at now=1000 -> committed, kept
    out = drop_forming_candles([{"time": 700.0}], 300, now=1000.0)
    assert out == [{"time": 700.0}]


def test_drop_forming_sheds_future_bars_and_tolerates_bad_input():
    out = drop_forming_candles([{"time": 2000.0}], 300, now=1000.0)
    assert out == []
    assert drop_forming_candles([], 300) == []
    assert drop_forming_candles("nope", 300) == []
    bars = [{"time": 1.0}]
    assert drop_forming_candles(bars, 0) == bars      # unknown interval


def test_interval_parsing_is_case_sensitive():
    assert interval_str_to_sec("1m") == 60
    assert interval_str_to_sec("5m") == 300
    assert interval_str_to_sec("1h") == 3600
    assert interval_str_to_sec("1H") == 3600
    assert interval_str_to_sec("1d") == 86400
    assert interval_str_to_sec("1D") == 86400
    assert interval_str_to_sec("1M") == 2592000       # month, not minute
    assert interval_str_to_sec("bogus") == 0.0


def _now_aligned_kraken_rows(interval_min):
    now = time.time()
    step = interval_min * 60
    start = int(now - now % step)
    return [[start - k * step, "10", "11", "9", "10.5", "10", "1", 5]
            for k in range(2, -1, -1)]


def test_kraken_drops_forming_bar_by_default(monkeypatch):
    feed = KrakenFeed({"trading_pairs": []})
    rows = _now_aligned_kraken_rows(5)
    monkeypatch.setattr(feed, "_public_get",
                        lambda *a, **k: {"XBTUSD": rows, "last": rows[-2][0]})
    out = feed.get_candles("XBTUSD", interval=5)
    assert len(out) == 2
    assert out[-1]["time"] == rows[-2][0]
    raw = feed.get_candles("XBTUSD", interval=5, include_forming=True)
    assert len(raw) == 3


def test_kraken_daily_keeps_todays_partial_bar(monkeypatch):
    feed = KrakenFeed({"trading_pairs": []})
    rows = _now_aligned_kraken_rows(1440)
    monkeypatch.setattr(feed, "_public_get",
                        lambda *a, **k: {"XBTUSD": rows, "last": rows[-2][0]})
    out = feed.get_daily_candles("XBTUSD")
    assert len(out) == 3                       # regime sees "as of now"


def test_okx_drops_forming_bar_by_default(monkeypatch):
    feed = OKXFeed({})
    now = time.time()
    start = int(now - now % 300)
    data = [[str((start - k * 300) * 1000), "10", "11", "9", "10.5", "1",
             "0", "0", "1"] for k in range(0, 3)]   # newest-first like OKX
    monkeypatch.setattr(feed, "_get", lambda *a, **k: data)
    out = feed.get_candles("BTC-USDT", bar="5m")
    assert len(out) == 2
    assert max(b["time"] for b in out) == start - 300


def test_binance_drops_forming_bar_by_default(monkeypatch):
    feed = BinanceUSFeed({})
    now = time.time()
    start = int(now - now % 300)
    data = [[(start - k * 300) * 1000, "10", "11", "9", "10.5", "1", 0]
            for k in range(2, -1, -1)]
    monkeypatch.setattr(feed, "_get", lambda *a, **k: data)
    out = feed.get_candles("BTCUSD", interval="5m")
    assert len(out) == 2
    assert max(b["time"] for b in out) == start - 300
