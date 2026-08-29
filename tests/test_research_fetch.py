"""Pins for scripts/research_fetch.py — the compiled-in fences.

No network here: the venue fence and scheme guard must fire BEFORE any
circuit is built, so they are testable offline. That is the whole point —
the block is structural, not a runtime hope.
"""
import pytest

from scripts.research_fetch import (VenueBlocked, _assert_not_venue, fetch)


@pytest.mark.parametrize("url", [
    "https://api.kraken.com/0/public/Ticker",
    "https://www.kraken.com/prices",
    "https://okx.com/api",
    "https://api.binance.com/api/v3/ticker",
    "https://coinbase.com/price/bitcoin",
    "https://openapi.moomoo.com/quote",
])
def test_venue_hosts_blocked(url):
    """Fence 1: every execution/venue host raises before any connection."""
    with pytest.raises(VenueBlocked):
        _assert_not_venue(url)
    # fetch() must raise the SAME block, not fall through to a circuit
    with pytest.raises(VenueBlocked):
        fetch(url)


@pytest.mark.parametrize("url", [
    "https://en.wikipedia.org/wiki/Sentiment_analysis",
    "https://www.reuters.com/markets/",
    "https://news.ycombinator.com/",
])
def test_research_hosts_pass_the_fence(url):
    """A legitimate research host clears the venue fence (returns its
    hostname) — the fence blocks venues, it does not block research."""
    host = _assert_not_venue(url)
    assert host and "kraken" not in host


def test_non_http_scheme_refused():
    with pytest.raises(ValueError):
        fetch("ftp://example.com/file")
    with pytest.raises(ValueError):
        fetch("file:///etc/passwd")


def test_empty_host_refused():
    with pytest.raises(ValueError):
        _assert_not_venue("not-a-url")


def test_denylist_is_only_extended_with_blocks():
    """The denylist exists to block, never to carve exceptions. If any entry
    stops matching its own canonical venue host, the fence has been weakened
    — this pin catches a silent removal."""
    from scripts.research_fetch import _VENUE_DENY
    canon = {
        "kraken.com": "https://api.kraken.com/x",
        "okx.com": "https://okx.com/y",
        "binance": "https://api.binance.com/z",
        "coinbase": "https://coinbase.com/w",
    }
    assert set(canon) <= set(_VENUE_DENY)
    for url in canon.values():
        with pytest.raises(VenueBlocked):
            _assert_not_venue(url)
