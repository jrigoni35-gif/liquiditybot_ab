"""MoomooFeed must NEVER block the engine when OpenD is down.

The moomoo SDK's sync constructor retries a dead gateway forever inside
OpenQuoteContext.__init__ (auto-reconnect loop, no retry cap, no
timeout). Observed live 2026-07-09: OpenD down froze the runner's cycle
loop mid-slow-cycle — no status writes, stale lock heartbeat, silent
hang. The feed's contract is the opposite: gateway down -> warn once,
available=False, engine keeps trading without the feed.

Enforced two ways, both covered here:
  1. a bounded TCP probe runs BEFORE any SDK code (dead port never
     reaches the SDK at all);
  2. the context is opened with is_async_connect=True plus a sync-query
     connect timeout, so OpenD dying between probe and construction (or
     accepting TCP without speaking the protocol) fails with ret != 0
     instead of blocking.
"""
import socket
import time
from unittest.mock import MagicMock, patch

from data.moomoo_feed import MoomooFeed

TICKERS = [{"code": "US.COIN", "weight": 1.0}]


def _dead_port() -> int:
    """A localhost port with no listener: bind ephemeral, then release."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _cfg(port: int) -> dict:
    return {"enabled": True, "poll_minutes": 0, "opend_host": "127.0.0.1",
            "opend_port": port, "connect_timeout_sec": 1.0,
            "tickers": TICKERS}


class FakeQuoteCtx:
    """Records how the feed constructs and configures the SDK context."""
    def __init__(self, host=None, port=None, is_async_connect=False):
        self.host, self.port = host, port
        self.is_async_connect = is_async_connect
        self.sync_timeout = None
        self.closed = False
        self.global_state_ret = 0

    def set_sync_query_connect_timeout(self, timeout):
        self.sync_timeout = timeout

    def get_global_state(self):
        return self.global_state_ret, {}

    def close(self):
        self.closed = True


def test_dead_port_fails_fast_without_touching_sdk():
    feed = MoomooFeed(_cfg(_dead_port()))
    sdk = MagicMock(side_effect=ImportError("unreachable in this test"))
    with patch.object(MoomooFeed, "_import_sdk", sdk):
        t0 = time.monotonic()
        snap = feed.maybe_poll(1000.0)
        elapsed = time.monotonic() - t0
    # the SDK must never be reached with a dead gateway: its sync
    # constructor cannot be interrupted once entered (a swallowed
    # exception from the seam would mask this - count calls instead)
    assert sdk.call_count == 0
    assert not snap.available
    assert feed._ctx is None
    assert feed._warned                      # operator told exactly once
    # refused localhost connect is near-instant; generous CI bound, but
    # far below the SDK's infinite constructor retry
    assert elapsed < 4.0


def test_live_port_constructs_async_with_bounded_sync_queries():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        feed = MoomooFeed(_cfg(port))
        with patch.object(MoomooFeed, "_import_sdk",
                          return_value=FakeQuoteCtx):
            assert feed._ensure_ctx() is True
    ctx = feed._ctx
    assert isinstance(ctx, FakeQuoteCtx)
    # the two SDK knobs that make a dead/zombie OpenD fail instead of
    # block: never the sync constructor, never an unbounded sync query
    assert ctx.is_async_connect is True
    assert ctx.sync_timeout == 1.0


def test_failed_probe_call_releases_ctx_and_degrades():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]

        class RefusingCtx(FakeQuoteCtx):
            def __init__(self, **kw):
                super().__init__(**kw)
                self.global_state_ret = -1   # SDK-level failure

        feed = MoomooFeed(_cfg(port))
        with patch.object(MoomooFeed, "_import_sdk",
                          return_value=RefusingCtx):
            snap = feed.maybe_poll(1000.0)
    assert not snap.available
    assert feed._ctx is None                 # released for a clean retry
    assert feed._warned


def test_warned_rearms_on_successful_reconnect():
    """A one-shot _warned that never resets makes a SECOND OpenD outage
    (after a recovery) go silent. Reconnecting must re-arm the warning."""
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        feed = MoomooFeed(_cfg(port))
        feed._warned = True                  # simulate a prior outage warning
        with patch.object(MoomooFeed, "_import_sdk",
                          return_value=FakeQuoteCtx):
            ok = feed._ensure_ctx()
    assert ok
    assert feed._warned is False             # re-armed for the next outage


def test_config_guard_validates_moomoo_block():
    from core.config_guard import validate

    def _fatals(m):
        return [msg for sev, msg in validate({"moomoo": m}) if sev == "FATAL"]

    assert any("opend_port" in m for m in _fatals(
        {"enabled": True, "opend_port": 99999}))
    assert any("poll_minutes" in m for m in _fatals(
        {"enabled": True, "poll_minutes": 0}))
    assert any("negative weight" in m for m in _fatals(
        {"enabled": True, "tickers": [{"code": "US.COIN", "weight": -1}]}))
    assert any("missing a 'code'" in m for m in _fatals(
        {"enabled": True, "tickers": [{"weight": 1.0}]}))
    # disabled moomoo is never validated (validate() runs the whole guard,
    # so filter to moomoo-specific findings, not the empty-config noise)
    disabled = _fatals({"enabled": False, "opend_port": 99999})
    assert not any(("moomoo" in m or "opend_port" in m) for m in disabled)
