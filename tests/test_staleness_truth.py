"""Staleness-veto resurrection (latency audit 2026-08-07, owed 42a).

THE DEFECT: book_ts was stamped with the same cycle-frozen `now` it was
later compared against (main.py stamp vs the pretrade staleness_ms and
DL-10 gate reads), so the pre-trade staleness veto (PT-020, 4000ms
ceiling) and the absent-book gate read ~0 forever - a REST hang, a
stalled feed, a stale cached book were all invisible to the exact gates
built to catch them. The veto MECHANISM was always live
(test_exploration_entry pins PT-020 at staleness_ms=99999); the
MEASUREMENT was tautological.

THE FIX: books carry their own receive stamp. REST attaches recv_ts
after clean_book (which strips unknown keys); the WS manager attaches
the cache's raw write stamp (the cache's get_book stays the pure 2-key
shape its tests pin). The engine stamps
    book_ts[asset] = float(book.get("recv_ts") or now)
so DATA time drives the veto, with the legacy now-stamp as the exact
fallback for books without the key (older recordings, test stubs) -
byte-identical pre-42a behavior there, which is what keeps replay of
old sessions deterministic. New recordings capture recv_ts verbatim in
the frame (FeedRecorder records the returned dict), so replay
reproduces the stamp from the recording, never recomputes it.
"""
from pathlib import Path

from data.kraken_feed import KrakenFeed
from data.ws_feed import LiveMarketCache, WebSocketFeedManager

_ROOT = Path(__file__).resolve().parents[1]


class _Clock:
    def __init__(self, t=1_000.0):
        self.t = t

    def __call__(self):
        return self.t


# ------------------------------------------------------------------ REST
def test_rest_book_carries_receive_timestamp(monkeypatch):
    feed = KrakenFeed.__new__(KrakenFeed)
    monkeypatch.setattr(
        feed, "_public_get",
        lambda ep, params: {"XBTUSD": {"bids": [["100.0", "1.0", 0]],
                                       "asks": [["101.0", "1.0", 0]]}},
        raising=False)
    import data.kraken_feed as kf
    monkeypatch.setattr(kf.time, "time", lambda: 5_555.5)
    book = feed.get_order_book("XBTUSD")
    assert book is not None
    assert book["recv_ts"] == 5_555.5
    assert book["bids"] and book["asks"]      # clean_book shape intact


def test_rest_malformed_book_still_returns_none(monkeypatch):
    feed = KrakenFeed.__new__(KrakenFeed)
    monkeypatch.setattr(feed, "_public_get",
                        lambda ep, params: {"XBTUSD": "garbage"},
                        raising=False)
    assert feed.get_order_book("XBTUSD") is None


# -------------------------------------------------------------------- WS
def test_cache_book_ts_returns_raw_write_stamp():
    clk = _Clock(2_000.0)
    c = LiveMarketCache(now=clk)
    assert c.book_ts("kraken", "BTCUSD") is None
    c.update_book("kraken", "BTCUSD", [["100", "1"]], [["101", "1"]])
    assert c.book_ts("kraken", "BTCUSD") == 2_000.0
    clk.t = 2_009.0                            # age moves, the stamp doesn't
    assert c.book_ts("kraken", "BTCUSD") == 2_000.0


def test_manager_book_recv_ts_is_write_time_not_read_time():
    clk = _Clock(3_000.0)
    m = WebSocketFeedManager(
        {"enabled": True, "binanceus_symbols": ["BTCUSD"],
         "max_book_age_sec": 5.0}, cache=LiveMarketCache(now=clk))
    m.cache.update_book("binanceus", "BTCUSD", [["64000", "1"]],
                        [["64010", "1"]])
    clk.t = 3_004.0                            # read 4s after the write
    book = m.get_order_book("BTCUSD")
    assert book is not None
    assert book["recv_ts"] == 3_000.0, (
        "recv_ts must be the DATA write stamp - a read-time stamp would "
        "rebuild the exact look-time tautology this change removes")


# ---------------------------------------------------------- engine stamp
def test_engine_stamps_book_ts_from_recv_ts_source_contract():
    """Source pin, same convention as test_data_layer_batch's stale-book
    gate contract: both book_ts writers must stamp from the book's own
    recv_ts with the legacy `now` fallback. If this line changes shape,
    re-verify the pretrade staleness read (`staleness_ms=`) and the
    DL-10 gate still measure data time."""
    main_src = (_ROOT / "main.py").read_text(encoding="utf-8")
    runner_src = (_ROOT / "runner.py").read_text(encoding="utf-8")
    stamp = 'book_ts[asset] = float(book.get("recv_ts") or now)'
    assert f"self.{stamp}" in main_src, "fast_cycle stamp must be data-time"
    assert f"bot.{stamp}" in runner_src, (
        "the runner's PAUSED-flatten refresh must use the same stamp or "
        "its books would regress to look-time")
    # two engine writers as of the 2026-08-16 broken-exit-path fix: the
    # fast_cycle universe loop and _refresh_offuniverse_marks (open
    # positions whose asset rotated out of the universe). The tripwire's
    # demand — every writer stamps DATA time — is now asserted directly:
    # each writer site must be the exact recv_ts-or-now form, so a third
    # writer with a look-time stamp still fails here.
    n_writers = main_src.count("self.book_ts[asset] = ")
    assert n_writers == 2, (
        "engine book_ts writer count changed - the new writer must adopt "
        "the recv_ts stamp and this pin must name it")
    assert main_src.count(f"self.{stamp}") == n_writers, (
        "EVERY engine writer of book_ts must stamp data time "
        "(recv_ts with the legacy now fallback), not look time")
