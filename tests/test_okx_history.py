"""OKXFeed.get_history_candles: paginated deep history must walk the `after`
cursor backward through newest-first pages, stop on a short page or the total
cap, and return oldest-first sanitized candles. (The plain candles endpoint
caps at 300 bars - too few EMA-cross events to bootstrap training.)
"""
from data.okx_feed import OKXFeed


def _page(start_ts, n, step=300_000):
    """One newest-first OKX page: [ts, o, h, l, c, vol, ...] rows."""
    return [[str(start_ts - i * step), "100", "101", "99", "100.5", "10"]
            for i in range(n)]


def _feed_with_pages(pages):
    feed = OKXFeed({"symbols": ["ETH-USDT"]})
    calls = []

    def fake_get(path, params=None):
        calls.append(dict(params or {}))
        idx = len(calls) - 1
        return pages[idx] if idx < len(pages) else []

    setattr(feed, "_get", fake_get)     # test seam: fake transport, no network
    return feed, calls


def test_paginates_with_after_cursor_and_returns_oldest_first():
    t0 = 1_700_000_000_000
    p1 = _page(t0, 100)
    p2 = _page(t0 - 100 * 300_000, 100)
    feed, calls = _feed_with_pages([p1, p2])
    out = feed.get_history_candles("ETH-USDT", total=200)
    assert len(out) == 200
    # second request must carry the first page's OLDEST ts as `after`
    assert "after" not in calls[0]
    assert calls[1]["after"] == p1[-1][0]
    # oldest-first, strictly increasing timestamps, no duplicates
    ts = [c["time"] for c in out]
    assert ts == sorted(ts) and len(set(ts)) == len(ts)


def test_short_page_terminates_pagination():
    feed, calls = _feed_with_pages([_page(1_700_000_000_000, 40)])
    out = feed.get_history_candles("ETH-USDT", total=1000)
    assert len(out) == 40 and len(calls) == 1     # short page: no second call


def test_total_cap_respected():
    t0 = 1_700_000_000_000
    pages = [_page(t0 - k * 100 * 300_000, 100) for k in range(5)]
    feed, calls = _feed_with_pages(pages)
    out = feed.get_history_candles("ETH-USDT", total=250)
    assert len(out) == 250 and len(calls) == 3    # ceil(250/100) pages


def test_empty_response_returns_empty():
    feed, _ = _feed_with_pages([])
    assert feed.get_history_candles("ETH-USDT", total=500) == []
