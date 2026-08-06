"""A checksum-failing book must never reach the live cache.

Round-2 finding (2026-08-05). KrakenV2BookStream.handle ran `_publish(sym)`
and only THEN `_verify_checksum(...)`, so a desynced book was written to the
cache with a fresh timestamp before being invalidated microseconds later.
The window is not theoretical: after a mismatch, local state is dropped, and
while the resubscribe backoff (up to 60s) suppresses recovery, every
subsequent `update` frame rebuilds a book from EMPTY state — so as soon as
both sides hold one level, a phantom 1-2-level book is published, stamped
fresh, on every frame. main.fast_cycle reads that cache concurrently for
stop and imbalance logic.

Verify-then-publish keeps the last GOOD book and its honest age, which the
existing staleness guards already handle correctly.
"""
import json
import zlib

from data.ws_feed import KrakenV2BookStream, LiveMarketCache


class _Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def _ck_token(v: str) -> str:
    return str(v).replace(".", "").lstrip("0")


def _ck(bids: dict, asks: dict) -> int:
    """Kraken v2 checksum: top-10 asks ascending then top-10 bids
    descending, price then qty, decimal point and leading zeros stripped."""
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


def _frame(typ, bids, asks, checksum=None):
    """handle() consumes the raw JSON text frame, and the checksum is
    reconstructed from the EXACT wire strings - so prices/qtys ride as
    numerics exactly as json.dumps would write them from Kraken."""
    d = {"symbol": "BTC/USD",
         "bids": [{"price": p, "qty": q} for p, q in bids],
         "asks": [{"price": p, "qty": q} for p, q in asks],
         "timestamp": "t"}
    if checksum is not None:
        d["checksum"] = checksum
    return json.dumps({"channel": "book", "type": typ, "data": [d]})


def _stream(depth=10):
    cache = LiveMarketCache(now=_Clock())
    return KrakenV2BookStream({"BTC/USD": "BTCUSD"}, cache, depth=depth), cache


def test_verified_book_is_published():
    s, cache = _stream()
    ck = _ck({64901.9: 1.6}, {64902.0: 0.5})
    s.handle(_frame("snapshot", [(64901.9, 1.6)], [(64902.0, 0.5)], ck))
    assert cache.get_book("kraken", "BTCUSD", 5.0) is not None
    assert s.checksum_failures == 0


def test_checksum_failure_never_publishes():
    s, cache = _stream()
    s.handle(_frame("snapshot", [(100.0, 1.0)], [(101.0, 1.0)], 12345))
    assert s.checksum_failures == 1
    assert cache.get_book("kraken", "BTCUSD", 5.0) is None, \
        "a desynced book must not reach the live cache at all"


def test_a_bad_frame_cannot_overwrite_the_last_good_book():
    """The consequential shape: a good book is live, then a desynced frame
    arrives. The reader must keep seeing the GOOD book (aged honestly), not
    a phantom stamped fresh."""
    s, cache = _stream()
    good = _ck({100.0: 1.0}, {101.0: 1.0})
    s.handle(_frame("snapshot", [(100.0, 1.0)], [(101.0, 1.0)], good))
    assert cache.get_book("kraken", "BTCUSD", 5.0)["bids"] == [[100.0, 1.0]]
    # a desync: state is dropped and the entry invalidated, so the reader
    # falls back to REST rather than trusting a rebuilt fragment
    s.handle(_frame("update", [(99.0, 7.0)], [], 999))
    assert s.checksum_failures == 1
    assert cache.get_book("kraken", "BTCUSD", 5.0) is None


def test_phantom_rebuild_during_backoff_never_publishes():
    """After a mismatch drops state, update frames rebuild from empty. Those
    thin books must stay unpublished for as long as they fail the checksum."""
    s, cache = _stream()
    s.handle(_frame("snapshot", [(100.0, 1.0)], [(101.0, 1.0)], 999))
    for _ in range(5):
        s.handle(_frame("update", [(99.0, 1.0)], [(102.0, 1.0)], 888))
    assert cache.get_book("kraken", "BTCUSD", 5.0) is None, \
        "a rebuilt fragment must never be served as a fresh book"
    assert s.checksum_failures == 6


def test_frames_without_a_checksum_still_publish():
    """Unverifiable BY CONTRACT - refusing to publish would go dark on a
    healthy feed, so behavior there is unchanged."""
    s, cache = _stream()
    s.handle(_frame("snapshot", [(100.0, 1.0)], [(101.0, 1.0)]))
    assert cache.get_book("kraken", "BTCUSD", 5.0) is not None
    assert s.checksum_failures == 0


def test_shallow_depth_still_publishes():
    """Below depth 10 there are too few retained levels to reconstruct
    Kraken's top-10 checksum window, so verification is skipped as before."""
    s, cache = _stream(depth=5)
    s.handle(_frame("snapshot", [(100.0, 1.0)], [(101.0, 1.0)], 4242))
    assert cache.get_book("kraken", "BTCUSD", 5.0) is not None
    assert s.checksum_failures == 0
