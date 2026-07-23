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
    assert drop_forming_candles(
        "nope", 300) == []  # pyright: ignore[reportArgumentType]
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


def test_kraken_committed_cut_uses_venue_last_not_local_clock(monkeypatch):
    """W2-22: committed-vs-forming must cut on Kraken's authoritative `last`
    field when present, not the local clock. A locally-fast clock can claim
    a bar committed (cutoff = skewed_now - interval_sec >= bar time) in the
    last skew-seconds of that bar's window, even though the venue's own
    `last` says the bar has not closed yet (still equal to the PRIOR bar's
    open ts). Trusting the clock leaks the still-forming bar into the
    append-only candle cache, understating its high/low forever."""
    feed = KrakenFeed({"trading_pairs": []})
    # last committed bar opened at 700; the newest returned row (1000) is
    # still forming per the venue (last stays at 700, not 1000).
    rows = [[700, "10", "11", "9", "10.5", "10", "1", 5],
            [1000, "10", "11", "9", "10.5", "10", "1", 5]]
    monkeypatch.setattr(feed, "_public_get",
                        lambda *a, **k: {"XBTUSD": rows, "last": 700})
    # local clock is fast: claims now=1301 (1s past the naive 1000+300=1300
    # window close) - the OLD local-clock-only cutoff (now - interval_sec =
    # 1001 >= 1000) would wrongly admit the still-forming bar.
    monkeypatch.setattr("core.sanitize.time.time", lambda: 1301.0)
    out = feed.get_candles("XBTUSD", interval=5)
    assert [c["time"] for c in out] == [700]


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
    # newest-first like OKX; confirm (row[8]) is "0" only on the newest
    # (still-forming) row - the real API contract this pins.
    data = [[str((start - k * 300) * 1000), "10", "11", "9", "10.5", "1",
             "0", "0", "0" if k == 0 else "1"] for k in range(0, 3)]
    monkeypatch.setattr(feed, "_get", lambda *a, **k: data)
    out = feed.get_candles("BTC-USDT", bar="5m")
    assert len(out) == 2
    assert max(b["time"] for b in out) == start - 300


def test_okx_committed_cut_uses_confirm_flag_not_local_clock(monkeypatch):
    """W2-22: OKX's `confirm` flag (already present in every candle row,
    row[8]) is exact ground truth for committed-vs-forming - no clock skew
    possible. A locally-fast clock must not override it."""
    feed = OKXFeed({})
    data = [
        [str(1000 * 1000), "10", "11", "9", "10.5", "1", "0", "0", "0"],
        [str(700 * 1000), "10", "11", "9", "10.5", "1", "0", "0", "1"],
        [str(400 * 1000), "10", "11", "9", "10.5", "1", "0", "0", "1"],
    ]
    monkeypatch.setattr(feed, "_get", lambda *a, **k: data)
    # skewed-fast local clock: old clock-only cutoff (1301-300=1001) would
    # wrongly admit the ts=1000 row, which confirm="0" says is still forming.
    monkeypatch.setattr("core.sanitize.time.time", lambda: 1301.0)
    out = feed.get_candles("BTC-USDT", bar="5m")
    assert [c["time"] for c in out] == [400, 700]


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
