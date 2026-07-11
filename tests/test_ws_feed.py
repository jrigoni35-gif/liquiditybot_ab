"""data/ws_feed.py — the push-based websocket data layer.

Every test drives the cache/parser/backoff with injected clocks and
synthetic frames; none opens a live socket. Covers the three contracts
the engine relies on: staleness-gating (a dead socket never feeds stale
depth), fail-safe parsing (garbage frames drop, never raise), and
REST-fallback (disabled/stale both yield None so the REST path stays the
source of truth)."""
import json

from data.ws_feed import (BinanceUSDepthStream, LiveMarketCache,
                           ResilientWebSocket, WebSocketFeedManager,
                           _backoff_delay)


class _Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


# --- LiveMarketCache -----------------------------------------------------
def test_fresh_book_returns_clean_book_shape():
    clk = _Clock()
    c = LiveMarketCache(now=clk)
    c.update_book("binanceus", "BTCUSD",
                  [["64000", "1.5"]], [["64010", "2.0"]])
    book = c.get_book("binanceus", "BTCUSD", max_age_s=2.0)
    assert book == {"bids": [[64000.0, 1.5]], "asks": [[64010.0, 2.0]]}


def test_stale_book_reads_as_absent():
    clk = _Clock()
    c = LiveMarketCache(now=clk)
    c.update_book("binanceus", "BTCUSD",
                  [["64000", "1"]], [["64010", "1"]])
    clk.t += 3.0                                   # older than max_age
    assert c.get_book("binanceus", "BTCUSD", max_age_s=2.0) is None


def test_missing_symbol_reads_as_absent():
    c = LiveMarketCache(now=_Clock())
    assert c.get_book("binanceus", "DOGEUSD", max_age_s=2.0) is None
    assert c.get_mark("binanceus", "DOGEUSD", max_age_s=2.0) is None


def test_mark_tracks_book_mid_and_trade():
    clk = _Clock()
    c = LiveMarketCache(now=clk)
    c.update_book("binanceus", "BTCUSD",
                  [["64000", "1"]], [["64010", "1"]])
    assert c.get_mark("binanceus", "BTCUSD", 2.0) == 64005.0
    c.update_trade("binanceus", "BTCUSD", 64020.0)
    assert c.get_mark("binanceus", "BTCUSD", 2.0) == 64020.0


def test_garbage_levels_never_raise_and_are_dropped():
    c = LiveMarketCache(now=_Clock())
    c.update_book("binanceus", "BTCUSD",
                  [["nan", "x"]], [["64010", "1"]])   # poisoned bid
    # clean_book rejects the empty bid side -> None, no exception
    assert c.get_book("binanceus", "BTCUSD", 2.0) is None
    c.update_trade("binanceus", "BTCUSD", "not-a-number")   # type: ignore[arg-type]  # ignored
    assert c.get_mark("binanceus", "BTCUSD", 2.0) is None


# --- backoff -------------------------------------------------------------
def test_backoff_is_exponential_capped_and_jittered():
    assert _backoff_delay(0, 1.0, 30.0, 0.0) == 1.0
    assert _backoff_delay(1, 1.0, 30.0, 0.0) == 2.0
    assert _backoff_delay(2, 1.0, 30.0, 0.0) == 4.0
    assert _backoff_delay(10, 1.0, 30.0, 0.0) == 30.0     # capped
    assert _backoff_delay(0, 1.0, 30.0, 0.5) == 1.5       # jitter added


# --- BinanceUSDepthStream ------------------------------------------------
def test_stream_url_lowercases_and_joins_symbols():
    s = BinanceUSDepthStream(["BTCUSD", "ETHUSD"], LiveMarketCache(),
                             depth=20, interval_ms=100)
    url = s.stream_url()
    assert "btcusd@depth20@100ms" in url
    assert "ethusd@depth20@100ms" in url
    assert url.startswith("wss://")


def test_handle_parses_frame_into_cache_under_caller_symbol():
    clk = _Clock()
    cache = LiveMarketCache(now=clk)
    s = BinanceUSDepthStream(["BTCUSD"], cache)
    frame = json.dumps({"stream": "btcusd@depth20@100ms",
                        "data": {"bids": [["64000", "1"]],
                                 "asks": [["64010", "1"]]}})
    s.handle(frame)
    # keyed under the caller's exact 'BTCUSD', not the wire 'btcusd'
    assert cache.get_book("binanceus", "BTCUSD", 2.0) is not None


def test_handle_drops_malformed_and_unknown_frames():
    cache = LiveMarketCache()
    s = BinanceUSDepthStream(["BTCUSD"], cache)
    s.handle("not json")                                   # no raise
    s.handle(json.dumps({"stream": "btcusd@depth20@100ms"}))  # no data
    s.handle(json.dumps({"stream": "xrpusd@depth20@100ms",
                        "data": {"bids": [["1", "1"]],
                                 "asks": [["2", "1"]]}}))   # unknown sym
    s.handle(json.dumps({"stream": "btcusd@depth20@100ms",
                        "data": {"bids": [], "asks": []}}))  # empty
    assert cache.stats()["books"] == 0


# --- WebSocketFeedManager ------------------------------------------------
def _mgr(enabled):
    return WebSocketFeedManager({
        "enabled": enabled, "binanceus_symbols": ["BTCUSD"],
        "max_book_age_sec": 2.0})


def test_disabled_manager_always_yields_none():
    m = _mgr(enabled=False)
    m.cache.update_book("binanceus", "BTCUSD",
                        [["64000", "1"]], [["64010", "1"]])
    assert m.get_order_book("BTCUSD") is None      # forces REST fallback
    assert m.get_mark("BTCUSD") is None
    assert m.health()["enabled"] is False


def test_enabled_manager_serves_fresh_book_and_falls_back_when_stale():
    clk = _Clock()
    m = WebSocketFeedManager(
        {"enabled": True, "binanceus_symbols": ["BTCUSD"],
         "max_book_age_sec": 2.0}, cache=LiveMarketCache(now=clk))
    m.cache.update_book("binanceus", "BTCUSD",
                        [["64000", "1"]], [["64010", "1"]])
    assert m.get_order_book("BTCUSD") == {"bids": [[64000.0, 1.0]],
                                          "asks": [[64010.0, 1.0]]}
    clk.t += 5.0
    assert m.get_order_book("BTCUSD") is None       # stale -> REST fallback


def test_health_reports_lib_and_connection_state():
    m = _mgr(enabled=True)
    h = m.health()
    assert set(h) >= {"enabled", "connected", "reconnects",
                      "lib_available", "books", "marks"}
    assert h["connected"] is False                  # never started


def test_stop_before_start_is_safe():
    m = _mgr(enabled=True)
    m.stop()                                        # no thread yet, no raise


def test_available_reflects_importability():
    # websockets is installed in the dev venv; the method must not raise
    assert isinstance(ResilientWebSocket.available(), bool)
