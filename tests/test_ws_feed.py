"""data/ws_feed.py — the push-based websocket data layer.

Every test drives the cache/parser/backoff with injected clocks and
synthetic frames; none opens a live socket. Covers the three contracts
the engine relies on: staleness-gating (a dead socket never feeds stale
depth), fail-safe parsing (garbage frames drop, never raise), and
REST-fallback (disabled/stale both yield None so the REST path stays the
source of truth)."""
import json
import zlib

from data.ws_feed import (BinanceUSDepthStream, KrakenV2BookStream,
                           LiveMarketCache, ResilientWebSocket,
                           WebSocketFeedManager, _backoff_delay)


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


# --- KrakenV2BookStream (incremental book "understanding") ---------------
# Real Kraken v2 frame shapes: bids/asks are [{price, qty}] lists; a
# snapshot carries the full top-N, updates carry only changed levels, and
# qty==0 removes a level. Cache is keyed by the caller's REST pair.
#
# `checksum` is OMITTED by default (None) rather than a dummy value: most of
# these fixtures exercise snapshot/update/depth-trim parsing, not checksum
# validation, so they take the documented "absent -> skip validation" path
# (case (c) below). Call sites that need a checksum-carrying, VALID frame
# pass one explicitly, computed by `_ck` (a small independent reference
# implementation of Kraken's v2 checksum algorithm - see
# test_kraken_checksum_matches_official_worked_example for its
# byte-for-byte validation against Kraken's own published worked example).
def _snap(sym, bids, asks, checksum=None):
    data = {"symbol": sym,
            "bids": [{"price": p, "qty": q} for p, q in bids],
            "asks": [{"price": p, "qty": q} for p, q in asks],
            "timestamp": "t"}
    if checksum is not None:
        data["checksum"] = checksum
    return json.dumps({"channel": "book", "type": "snapshot", "data": [data]})


def _upd(sym, bids, asks, checksum=None):
    data = {"symbol": sym,
            "bids": [{"price": p, "qty": q} for p, q in bids],
            "asks": [{"price": p, "qty": q} for p, q in asks],
            "timestamp": "t"}
    if checksum is not None:
        data["checksum"] = checksum
    return json.dumps({"channel": "book", "type": "update", "data": [data]})


def _ck_token(v) -> str:
    """Kraken v2 checksum level encoding: `str(v)` mirrors exactly what
    `json.dumps` writes for these tests' plain float/int fixture values (and
    thus what production's `parse_float=str` reads back) - decimal point and
    leading zeros stripped."""
    s = str(v).replace(".", "").lstrip("0")
    return s or "0"


def _ck(bids: dict, asks: dict) -> int:
    """Independent reference implementation of Kraken's v2 book checksum
    (top-10 asks ascending, top-10 bids descending, price+qty per level with
    the decimal point/leading zeros stripped, concatenated and CRC32'd) -
    used to compute VALID checksums for fixtures whose point is exercising
    other behavior. Its correctness is pinned separately in
    test_kraken_checksum_matches_official_worked_example against Kraken's
    own published numbers, not by this function itself."""
    a = sorted(asks.items())[:10]
    b = sorted(bids.items(), reverse=True)[:10]
    parts = []
    for p, q in a:
        parts.append(_ck_token(p))
        parts.append(_ck_token(q))
    for p, q in b:
        parts.append(_ck_token(p))
        parts.append(_ck_token(q))
    return zlib.crc32("".join(parts).encode("ascii"))


def _kstream(cache, depth=10):
    # v2 symbol 'BTC/USD' caches under the REST pair 'BTCUSD'
    return KrakenV2BookStream({"BTC/USD": "BTCUSD"}, cache, depth=depth)


def test_kraken_snapshot_caches_under_rest_pair():
    clk = _Clock()
    cache = LiveMarketCache(now=clk)
    s = _kstream(cache)
    ck = _ck({64901.9: 1.6}, {64902.0: 0.5})            # valid checksum
    s.handle(_snap("BTC/USD", [(64901.9, 1.6)], [(64902.0, 0.5)], checksum=ck))
    book = cache.get_book("kraken", "BTCUSD", 5.0)      # keyed by REST pair
    assert book == {"bids": [[64901.9, 1.6]], "asks": [[64902.0, 0.5]]}
    assert cache.get_mark("kraken", "BTCUSD", 5.0) == (64901.9 + 64902.0) / 2


def test_kraken_update_sets_and_removes_levels():
    cache = LiveMarketCache(now=_Clock())
    s = _kstream(cache)
    ck0 = _ck({100.0: 1.0, 99.0: 2.0}, {101.0: 1.0, 102.0: 2.0})
    s.handle(_snap("BTC/USD",
                   [(100.0, 1.0), (99.0, 2.0)], [(101.0, 1.0), (102.0, 2.0)],
                   checksum=ck0))
    # update: replace the 99 bid qty, add a better 100.5 ask
    ck1 = _ck({100.0: 1.0, 99.0: 5.0}, {101.0: 1.0, 102.0: 2.0, 100.5: 3.0})
    s.handle(_upd("BTC/USD", [(99.0, 5.0)], [(100.5, 3.0)], checksum=ck1))
    book = cache.get_book("kraken", "BTCUSD", 5.0)
    assert [100.0, 1.0] in book["bids"] and [99.0, 5.0] in book["bids"]
    assert book["asks"][0] == [100.5, 3.0]              # best ask now 100.5
    # qty 0 removes the 99 bid
    ck2 = _ck({100.0: 1.0}, {101.0: 1.0, 102.0: 2.0, 100.5: 3.0})
    s.handle(_upd("BTC/USD", [(99.0, 0.0)], [], checksum=ck2))
    book = cache.get_book("kraken", "BTCUSD", 5.0)
    assert all(lvl[0] != 99.0 for lvl in book["bids"])
    assert s.checksum_failures == 0                     # every frame was valid


def test_kraken_book_is_sorted_and_depth_capped():
    cache = LiveMarketCache(now=_Clock())
    s = _kstream(cache, depth=2)
    s.handle(_snap("BTC/USD",
                   [(98.0, 1), (100.0, 1), (99.0, 1)],       # unsorted
                   [(103.0, 1), (101.0, 1), (102.0, 1)]))
    book = cache.get_book("kraken", "BTCUSD", 5.0)
    assert [lvl[0] for lvl in book["bids"]] == [100.0, 99.0]   # desc, top-2
    assert [lvl[0] for lvl in book["asks"]] == [101.0, 102.0]  # asc, top-2


def test_kraken_state_trimmed_to_depth_no_phantom_levels():
    # a depth-N channel need not send a qty=0 remove for a level merely
    # pushed OUT of the window by a better price; without trimming, _state
    # grows and the stale level could later resurface as a phantom touch.
    cache = LiveMarketCache(now=_Clock())
    s = _kstream(cache, depth=2)
    s.handle(_snap("BTC/USD", [(100.0, 1), (99.0, 1)], [(101.0, 1), (102.0, 1)]))
    # better bid + better ask arrive; the old worst levels are NOT removed
    s.handle(_upd("BTC/USD", [(100.5, 1)], [(100.8, 1)]))
    st = s._state["BTC/USD"]
    assert len(st["bids"]) == 2 and len(st["asks"]) == 2   # bounded to depth
    assert set(st["bids"]) == {100.5, 100.0}               # top-2 kept
    assert set(st["asks"]) == {100.8, 101.0}               # 99/102 dropped
    # published book reflects the trimmed top-of-book, no phantom 99/102
    book = cache.get_book("kraken", "BTCUSD", 5.0)
    assert book["bids"][0] == [100.5, 1.0]
    assert book["asks"][0] == [100.8, 1.0]


def test_kraken_resnapshot_resets_state():
    # a reconnect re-subscribes -> Kraken resends a snapshot; stale levels
    # from the prior connection must not survive (no drift across reconnects)
    cache = LiveMarketCache(now=_Clock())
    s = _kstream(cache)
    s.handle(_snap("BTC/USD", [(100.0, 1.0)], [(101.0, 1.0)],
                   checksum=_ck({100.0: 1.0}, {101.0: 1.0})))
    s.handle(_snap("BTC/USD", [(200.0, 1.0)], [(201.0, 1.0)],   # fresh snap
                   checksum=_ck({200.0: 1.0}, {201.0: 1.0})))
    book = cache.get_book("kraken", "BTCUSD", 5.0)
    assert book == {"bids": [[200.0, 1.0]], "asks": [[201.0, 1.0]]}
    assert s.checksum_failures == 0


def test_kraken_drops_malformed_and_unknown_frames():
    cache = LiveMarketCache()
    s = _kstream(cache)
    s.handle("not json")                                   # no raise
    s.handle(json.dumps({"channel": "heartbeat"}))         # not a book frame
    s.handle(_snap("ETH/USD", [(1, 1)], [(2, 1)]))         # unsubscribed sym
    s.handle(_snap("BTC/USD", [], []))                     # empty sides
    s.handle(json.dumps({"channel": "book", "type": "snapshot",
                         "data": [{"symbol": "BTC/USD",
                                   "bids": [{"price": "nan"}]}]}))  # bad level
    assert cache.stats()["books"] == 0


def test_kraken_subscribe_msg_is_book_channel_all_symbols():
    s = KrakenV2BookStream({"BTC/USD": "BTCUSD", "ETH/USD": "ETHUSD"},
                           LiveMarketCache(), depth=10)
    msg = json.loads(s.subscribe_msg())
    assert msg["method"] == "subscribe"
    assert msg["params"]["channel"] == "book"
    assert set(msg["params"]["symbol"]) == {"BTC/USD", "ETH/USD"}
    assert msg["params"]["depth"] == 10
    assert s.url() == "wss://ws.kraken.com/v2"


def test_manager_with_kraken_adapter_serves_book_by_pair():
    clk = _Clock()
    cache = LiveMarketCache(now=clk)
    adapter = KrakenV2BookStream({"BTC/USD": "BTCUSD"}, cache, depth=10)
    m = WebSocketFeedManager({"enabled": True, "max_book_age_sec": 5.0},
                             cache=cache, adapter=adapter)
    assert m.venue == "kraken"
    adapter.handle(_snap("BTC/USD", [(100.0, 1.0)], [(101.0, 1.0)],
                         checksum=_ck({100.0: 1.0}, {101.0: 1.0})))
    assert m.get_order_book("BTCUSD") == {"bids": [[100.0, 1.0]],
                                          "asks": [[101.0, 1.0]]}
    clk.t += 9.0
    assert m.get_order_book("BTCUSD") is None              # stale -> REST


# --- Kraken v2 checksum validation (W2-12) --------------------------------
# Kraken's v2 book channel carries a CRC32 `checksum` on every frame; the
# audit finding was that it was never validated, so a self-inflicted parse
# gap (one unparseable level skipped via `continue` while the rest of the
# frame still applies) could silently desync local state from Kraken's real
# book forever - the cache timestamp keeps refreshing (staleness gate never
# fires) and clean_book only catches crossed/degenerate shapes, not a
# plausible-but-wrong book.
def test_kraken_checksum_matches_official_worked_example():
    # Kraken's own published BTC/USD worked example for the v2 checksum
    # algorithm (docs.kraken.com/api/docs/guides/spot-ws-book-v2): exact
    # top-10 asks/bids and the resulting checksum, fetched from the live
    # docs and independently cross-checked with zlib.crc32 before writing
    # this test. Built as raw JSON text (not via json.dumps on Python
    # floats) so the wire-precision trailing zeros survive - exactly what
    # production's `parse_float=str` is designed to capture. Also pins case
    # (b): a correct checksum applies normally, no resubscribe.
    asks = [("45285.2", "0.00100000"), ("45286.4", "1.54571953"),
            ("45286.6", "1.54571109"), ("45289.6", "1.54560911"),
            ("45290.2", "0.15890660"), ("45291.8", "1.54553491"),
            ("45294.7", "0.04454749"), ("45296.1", "0.35380000"),
            ("45297.5", "0.09945542"), ("45299.5", "0.18772827")]
    bids = [("45283.5", "0.10000000"), ("45283.4", "1.54582015"),
            ("45282.1", "0.10000000"), ("45281.0", "0.10000000"),
            ("45280.3", "1.54592586"), ("45279.0", "0.07990000"),
            ("45277.6", "0.03310103"), ("45277.5", "0.30000000"),
            ("45277.3", "1.54602737"), ("45276.6", "0.15445238")]

    def lvl_json(levels):
        return "[" + ",".join(
            f'{{"price": {p}, "qty": {q}}}' for p, q in levels) + "]"

    frame = ('{"channel": "book", "type": "snapshot", "data": [{'
             '"symbol": "BTC/USD", '
             f'"bids": {lvl_json(bids)}, "asks": {lvl_json(asks)}, '
             '"checksum": 3310070434, "timestamp": "t"}]}')

    cache = LiveMarketCache(now=_Clock())
    s = _kstream(cache, depth=10)
    resubscribed = []
    s.request_resubscribe = lambda: resubscribed.append(True)

    s.handle(frame)

    assert s.checksum_failures == 0
    assert not resubscribed
    book = cache.get_book("kraken", "BTCUSD", 5.0)
    assert book is not None
    assert book["asks"][0] == [45285.2, 0.001]
    assert book["bids"][0] == [45283.5, 0.1]


def test_kraken_checksum_mismatch_drops_state_cache_and_resubscribes():
    # Repro (a): simulates the audit finding's exact desync mechanism - a
    # frame carries one level the parser cannot apply (missing "qty", caught
    # by the existing `except (KeyError, ...): continue`) while the rest of
    # the frame still applies. Kraken's real book (and its checksum) include
    # the skipped level; ours does not, so the two diverge. FAILS before the
    # fix: the drifted book stays published, its cache ts stays fresh, and
    # nothing resubscribes.
    clk = _Clock()
    cache = LiveMarketCache(now=clk)
    s = _kstream(cache, depth=10)
    resubscribed = []
    s.request_resubscribe = lambda: resubscribed.append(True)

    good_ck = _ck({100.0: 1.0}, {101.0: 1.0})
    s.handle(_snap("BTC/USD", [(100.0, 1.0)], [(101.0, 1.0)],
                   checksum=good_ck))
    assert cache.get_book("kraken", "BTCUSD", 5.0) is not None   # seeded ok

    # Kraken's real book after this update also carries a new 102.0 ask;
    # its checksum reflects that 3-level book. Our frame's 102.0 level is
    # missing "qty" - unparseable, skipped - so we only apply 100/101.
    true_ck = _ck({100.0: 1.0}, {101.0: 1.0, 102.0: 1.0})
    frame = json.dumps({"channel": "book", "type": "update", "data": [{
        "symbol": "BTC/USD",
        "bids": [],
        "asks": [{"price": 102.0}],      # missing "qty" -> unparseable
        "checksum": true_ck, "timestamp": "t"}]})
    clk.t += 0.01                          # cache ts would otherwise stay fresh

    s.handle(frame)

    # post-fix contract:
    assert "BTC/USD" not in s._state                        # state dropped
    assert cache.get_book("kraken", "BTCUSD", 5.0) is None   # cache invalidated
    assert resubscribed == [True]                            # resubscribe fired
    assert s.checksum_failures == 1


def test_kraken_checksum_absent_preserves_current_behavior():
    # Repro (c): no `checksum` field on the frame at all -> never treated as
    # a mismatch, exactly the pre-fix behavior, even though nothing here
    # coincidentally happens to be a valid checksum.
    cache = LiveMarketCache(now=_Clock())
    s = _kstream(cache, depth=10)
    resubscribed = []
    s.request_resubscribe = lambda: resubscribed.append(True)

    s.handle(_snap("BTC/USD", [(100.0, 1.0)], [(101.0, 1.0)]))   # no checksum

    assert cache.get_book("kraken", "BTCUSD", 5.0) == {
        "bids": [[100.0, 1.0]], "asks": [[101.0, 1.0]]}
    assert not resubscribed
    assert s.checksum_failures == 0
    assert "BTC/USD" in s._state


def test_kraken_checksum_skipped_below_depth_ten():
    # Kraken's checksum always covers the top-10 window; at depth<10 we
    # cannot retain enough levels to reconstruct it, so even a WRONG
    # checksum must never trigger a resubscribe there.
    cache = LiveMarketCache(now=_Clock())
    s = _kstream(cache, depth=2)
    resubscribed = []
    s.request_resubscribe = lambda: resubscribed.append(True)

    s.handle(_snap("BTC/USD", [(100.0, 1.0)], [(101.0, 1.0)], checksum=999999))

    assert cache.get_book("kraken", "BTCUSD", 5.0) is not None
    assert not resubscribed
    assert s.checksum_failures == 0


def test_cache_invalidate_drops_book_and_mark():
    c = LiveMarketCache(now=_Clock())
    c.update_book("kraken", "BTCUSD", [["100", "1"]], [["101", "1"]])
    assert c.get_book("kraken", "BTCUSD", 5.0) is not None
    assert c.get_mark("kraken", "BTCUSD", 5.0) is not None

    c.invalidate("kraken", "BTCUSD")

    assert c.get_book("kraken", "BTCUSD", 5.0) is None
    assert c.get_mark("kraken", "BTCUSD", 5.0) is None


def test_resilient_ws_request_reconnect_sets_resync_flag():
    ws = ResilientWebSocket("wss://example.invalid", on_message=lambda t: None)
    assert not ws._resync.is_set()
    ws.request_reconnect()
    assert ws._resync.is_set()


def test_health_reports_checksum_failures():
    cache = LiveMarketCache()
    adapter = KrakenV2BookStream({"BTC/USD": "BTCUSD"}, cache, depth=10)
    m = WebSocketFeedManager({"enabled": True, "max_book_age_sec": 5.0},
                             cache=cache, adapter=adapter)
    assert m.health()["checksum_failures"] == 0
    adapter.checksum_failures = 3
    assert m.health()["checksum_failures"] == 3
