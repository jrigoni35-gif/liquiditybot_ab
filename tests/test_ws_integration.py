"""The websocket feed must actually be WIRED: before this, WebSocketFeedManager
was built and unit-tested but never constructed by the engine, so flipping
websockets.enabled did nothing. These lock in the integration contract:

1. BinanceUSFeed serves a FRESH cached book instead of hitting REST;
2. a stale/absent/disabled cache falls straight back to REST;
3. a raising ws source never propagates - REST still answers;
4. when disabled the feed is byte-for-byte the old REST-only behavior.
"""
from data.binanceus_feed import BinanceUSFeed
from data.ws_feed import LiveMarketCache, WebSocketFeedManager


class _FakeREST(BinanceUSFeed):
    """BinanceUSFeed with the network stubbed: _get returns a canned book so
    we can prove which SOURCE (ws cache vs REST) answered."""

    def __init__(self, ws=None):
        super().__init__({"symbols": ["BTCUSD"]}, ws=ws)
        self.rest_calls = 0

    def _get(self, path, params=None):
        self.rest_calls += 1
        return {"bids": [["100", "1"]], "asks": [["101", "1"]]}   # REST marker


def _mgr(enabled, cache):
    return WebSocketFeedManager(
        {"enabled": enabled, "binanceus_symbols": ["BTCUSD"],
         "max_book_age_sec": 2.0}, cache=cache)


def test_fresh_ws_book_served_without_rest():
    t = [1000.0]
    cache = LiveMarketCache(now=lambda: t[0])
    cache.update_book("binanceus", "BTCUSD", [[200.0, 5.0]], [[201.0, 5.0]])
    feed = _FakeREST(ws=_mgr(True, cache))

    book = feed.get_order_book("BTCUSD")

    assert book is not None
    assert book["bids"][0][0] == 200.0        # ws value, not the REST 100
    assert feed.rest_calls == 0               # REST never touched


def test_stale_ws_book_falls_back_to_rest():
    t = [1000.0]
    cache = LiveMarketCache(now=lambda: t[0])
    cache.update_book("binanceus", "BTCUSD", [[200.0, 5.0]], [[201.0, 5.0]])
    feed = _FakeREST(ws=_mgr(True, cache))
    t[0] += 10.0                              # age past max_book_age_sec

    book = feed.get_order_book("BTCUSD")

    assert book is not None and book["bids"][0][0] == 100.0   # REST
    assert feed.rest_calls == 1


def test_disabled_manager_is_rest_only():
    cache = LiveMarketCache()
    cache.update_book("binanceus", "BTCUSD", [[200.0, 5.0]], [[201.0, 5.0]])
    feed = _FakeREST(ws=_mgr(False, cache))    # disabled -> get_order_book None

    book = feed.get_order_book("BTCUSD")

    assert book is not None
    assert book["bids"][0][0] == 100.0        # REST despite a fresh cache
    assert feed.rest_calls == 1


def test_raising_ws_source_never_breaks_rest():
    class _Boom:
        def get_order_book(self, symbol):
            raise RuntimeError("socket exploded")

    feed = _FakeREST(ws=_Boom())
    book = feed.get_order_book("BTCUSD")
    assert book is not None
    assert book["bids"][0][0] == 100.0        # REST answered anyway
    assert feed.rest_calls == 1


def test_manager_symbols_default_and_health_shape():
    mgr = WebSocketFeedManager({"enabled": False,
                                "binanceus_symbols": ["BTCUSD", "ETHUSD"]})
    h = mgr.health()
    assert h["enabled"] is False and "connected" in h and "reconnects" in h
