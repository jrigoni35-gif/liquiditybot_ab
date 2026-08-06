"""A deep paginated history request must return what it paginated for.

Round-2 finding (2026-08-05). get_history_candles walks the OKX
history-candles endpoint 100 bars at a time and slices `rows[:total]`
correctly - then handed the result to clean_candles, whose default
`max_n=2000` keeps only the last 2000 bars. scripts/train_meta.py asks for
2880 (~10 days of 5m bars) to have enough EMA-cross events to bootstrap a
training set, and silently received ~7 days: no log line, no error, and a
docstring promising "up to `total` bars".

The 2000 cap belongs to LIVE per-cycle fetches, where it bounds work. A
deliberate paginated history request is exactly the caller it should not
silently shrink.
"""
from data.okx_feed import OKXFeed


def _page(start_ms: int, n: int = 100, step_ms: int = 300_000) -> list:
    """One newest-first OKX page: [ts, o, h, l, c, vol, ...] as strings."""
    return [[str(start_ms - i * step_ms), "100", "101", "99", "100.5", "5"]
            for i in range(n)]


class _PagedFeed(OKXFeed):
    """OKXFeed with the network replaced by a deterministic pager."""

    def __init__(self, pages: int):
        super().__init__({"symbols": [], "rate_limit_per_sec": 5})
        self._pages_left = pages
        # a fixed PAST epoch (2023-11-14 UTC): deterministic for replay, and
        # safely committed so the forming-bar filter keeps every bar
        self._cursor = 1_700_000_000_000
        self.calls = 0

    def _get(self, path, params=None):
        if "history-candles" not in path:
            return None
        if self._pages_left <= 0:
            return []
        self.calls += 1
        self._pages_left -= 1
        page = _page(self._cursor)
        self._cursor -= 100 * 300_000
        return page


def test_deep_request_keeps_more_than_two_thousand_bars():
    feed = _PagedFeed(pages=29)                    # 2900 bars available
    out = feed.get_history_candles("BTC-USDT-SWAP", bar="5m", total=2880)
    assert len(out) > 2000, \
        f"deep history truncated to {len(out)} bars by the live-fetch cap"
    assert len(out) >= 2870                        # minus any forming bar


def test_result_is_oldest_first_and_monotonic():
    feed = _PagedFeed(pages=29)
    out = feed.get_history_candles("BTC-USDT-SWAP", bar="5m", total=2880)
    times = [c["time"] for c in out]
    assert times == sorted(times), "history must be oldest-first"
    assert len(set(times)) == len(times), "pagination duplicated a bar"


def test_small_request_is_unchanged():
    """The common case must behave exactly as before."""
    feed = _PagedFeed(pages=3)
    out = feed.get_history_candles("BTC-USDT-SWAP", bar="5m", total=300)
    assert 290 <= len(out) <= 300
