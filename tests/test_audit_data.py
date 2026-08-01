"""tests/test_audit_data.py — regressions for the data-layer audit findings.

Covered here, one section each:

  * H8  data/ws_feed.py — (a) a venue-side NORMAL websocket close fell out
        of `async for` with no exception, bypassing backoff entirely (a
        zero-delay reconnect storm against the execution venue) while
        `connected`/`reconnects` still read healthy; (b) `attempt` reset on
        CONNECT, so a connect-then-immediately-drop venue was pinned at the
        base delay forever and the attempt>=3 WARNING escalation was
        unreachable.
  * M4  data/context_engine.py — five sequential blocking HTTP GETs on the
        ENGINE thread, with no aggregate deadline, stalled `fast_cycle`'s
        per-position stop loop for the whole poll.
  * LOW data/ccxt_feed.py — `funding_rate` was fabricated as 0.0 when
        funding is UNAVAILABLE (DL-11), which the liquidity-model merge
        then AVERAGED into a real print.

No sockets and no network: the websocket transport is driven through a
fake `websockets` module injected into `sys.modules`, and every
ContextFeed/CCXTFeed here takes an injected fetcher/client.
"""
import asyncio
import json
import logging
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from data import ws_feed
from data.ccxt_feed import CCXTFeed
from data.context_engine import ContextFeed
from data.ws_feed import ResilientWebSocket, WebSocketFeedManager
from strategies.liquidity_model import LiquidityModel

_WS_LOGGER = "liquiditybot.data.ws"
_CTX_LOGGER = "liquiditybot.data.context_engine"


# =========================================================================
# H8 — websocket reconnect harness
# =========================================================================
#
# `_reader` does a lazy `import websockets`, so a module-shaped stub in
# sys.modules is the whole seam. The stub reproduces the two real shapes
# that matter:
#   * a NORMAL close: `Connection.__aiter__` (websockets >= 14) swallows
#     ConnectionClosedOK and simply returns -> StopAsyncIteration, NO
#     exception reaches `_reader`. That is mechanism (a).
#   * a post-handshake failure: the iterator raises. That is the path
#     mechanism (b) mis-scheduled.


class _FakeConn:
    """One websocket connection: yields `frames`, then either ends cleanly
    (venue-side normal close) or raises `error`. Advances the control
    clock by `up_for` at the moment it drops, so the connection's measured
    lifetime is exactly `up_for` seconds."""

    def __init__(self, ctl, frames, error, up_for):
        self._ctl = ctl
        self._frames = list(frames)
        self._error = error
        self._up_for = up_for
        self.sent: list = []

    async def send(self, msg):
        self.sent.append(msg)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._frames:
            return self._frames.pop(0)
        self._ctl.clock += self._up_for      # the connection lived this long
        if self._error is not None:
            raise self._error
        raise StopAsyncIteration              # normal close: NO exception


class _FakeConnect:
    def __init__(self, ctl):
        self._ctl = ctl

    async def __aenter__(self):
        return self._ctl.on_connect()

    async def __aexit__(self, *exc):
        return False


class _FakeWsLib:
    """Stands in for the lazily-imported `websockets` module."""

    def __init__(self, ctl):
        self._ctl = ctl

    def connect(self, url, **kwargs):
        self._ctl.urls.append(url)
        return _FakeConnect(self._ctl)


class _WsCtl:
    """Drives the fake transport and owns the injected monotonic clock.

    `up_for_seq` is the per-connection lifetime in seconds (the last entry
    repeats). `_stop` is set on the `max_connects`-th connect so `_reader`
    always terminates — including when the fix is inverted to verify the
    test catches the defect."""

    def __init__(self, ws, max_connects, up_for_seq, error=None, frames=()):
        self.ws = ws
        self.max_connects = max_connects
        self._up_for = list(up_for_seq)
        self.error = error
        self.frames = list(frames)
        self.connects = 0
        self.urls: list = []
        self.conns: list = []
        self.clock = 1000.0

    def now(self):
        return self.clock

    def on_connect(self):
        self.connects += 1
        if self.connects >= self.max_connects:
            self.ws._stop.set()
        up_for = self._up_for[min(self.connects - 1, len(self._up_for) - 1)]
        conn = _FakeConn(self, self.frames, self.error, up_for)
        self.conns.append(conn)
        return conn


def _drive(monkeypatch, ws, ctl) -> list:
    """Run `_reader` to completion against the fake transport; returns the
    backoff delays it actually slept (sleep itself is stubbed out)."""
    delays: list = []

    async def _fake_sleep(stop_event, delay):
        delays.append(delay)

    monkeypatch.setattr(ws_feed, "_stoppable_sleep", _fake_sleep)
    monkeypatch.setitem(sys.modules, "websockets", _FakeWsLib(ctl))
    asyncio.run(ws._reader())
    return delays


def _ws(**kwargs) -> ResilientWebSocket:
    kwargs.setdefault("rng", lambda: 0.0)        # deterministic: no jitter
    return ResilientWebSocket("wss://ws.example.invalid/v2",
                              on_message=lambda t: None,
                              subscribe='{"method":"subscribe"}', **kwargs)


# ---- H8(a): a normal close is a disconnect, not a free reconnect ---------

def test_normal_close_backs_off_instead_of_reconnect_storming(monkeypatch):
    """PRE-FIX: `async for` ends with no exception, so the entire `except`
    branch — sleep, `reconnects += 1`, `connected = False` — is skipped and
    the loop re-dials immediately (measured 310 connects/s against the
    execution venue). POST-FIX: every non-deliberate close routes through
    the one backoff branch."""
    ws = _ws()
    ctl = _WsCtl(ws, max_connects=4, up_for_seq=[0.0], error=None)
    ws._now = ctl.now

    delays = _drive(monkeypatch, ws, ctl)

    assert ctl.connects == 4
    # 3 closes are followed by a reconnect (the 4th sets _stop): each one
    # must have slept. PRE-FIX this list is EMPTY.
    assert delays == [1.0, 2.0, 4.0]
    assert ws.reconnects == 3                    # PRE-FIX: 0 (blind telemetry)
    assert ws.connected is False                 # PRE-FIX: True during outage


def test_normal_close_outage_is_visible_in_health(monkeypatch):
    """The operator-facing consequence: `health()` -> status.json -> Grafana
    reported `{connected: true, reconnects: 0}` for the whole outage."""
    ws = _ws()
    ctl = _WsCtl(ws, max_connects=3, up_for_seq=[0.0], error=None)
    ws._now = ctl.now
    mgr = WebSocketFeedManager({"enabled": True, "max_book_age_sec": 5.0})
    mgr._ws = ws

    _drive(monkeypatch, ws, ctl)

    h = mgr.health()
    assert h["connected"] is False                # PRE-FIX: True
    assert h["reconnects"] == 2                   # PRE-FIX: 0


def test_deliberate_stop_and_resync_are_not_treated_as_disconnects(
        monkeypatch):
    """NO-REGRESSION GUARD (passes before and after — it pins what the
    H8(a) fix must NOT break): `stop()` and `request_reconnect()` end the
    connection ON PURPOSE, so they must not sleep, must not bump
    `reconnects`, and (for resync) must re-dial immediately — the
    documented no-backoff resubscribe path."""
    ws = _ws()
    ws.request_reconnect()                       # arm a resync
    # frames so the loop body runs and can observe the resync flag; the
    # connection would otherwise never drop (error=None + frames consumed
    # would end it, so give it a long life and a stop on the 2nd connect)
    ctl = _WsCtl(ws, max_connects=2, up_for_seq=[0.0], error=None,
                 frames=['{"channel":"heartbeat"}'])
    ws._now = ctl.now

    delays = _drive(monkeypatch, ws, ctl)

    assert ctl.connects == 2                     # it DID re-dial
    assert delays == []                          # but with no backoff
    assert ws.reconnects == 0                    # and no disconnect counted
    assert ctl.conns[0].sent == ['{"method":"subscribe"}']   # resubscribed


# ---- H8(b): the ladder escalates unless the link actually stays up ------

def test_attempt_escalates_when_the_socket_never_stays_up(monkeypatch,
                                                          caplog):
    """PRE-FIX: `attempt = 0` sat inside the `async with`, before
    `ws.send(subscribe)`, so every post-handshake failure recomputed
    `_backoff_delay(0, ...)` — a flapping venue was retried at 1-2s
    forever, the 75s cap was unreachable, and `attempt >= 3` (the WARNING
    escalation) could never fire."""
    caplog.set_level(logging.INFO, logger=_WS_LOGGER)
    ws = _ws(ping_interval=20.0)
    # every connection dies 0.5s in — far short of one ping interval, so
    # none of them counts as a recovery
    ctl = _WsCtl(ws, max_connects=5, up_for_seq=[0.5],
                 error=OSError("connection reset by peer"))
    ws._now = ctl.now

    delays = _drive(monkeypatch, ws, ctl)

    assert delays == [1.0, 2.0, 4.0, 8.0]        # PRE-FIX: [1.0, 1.0, 1.0, 1.0]
    # the sustained-outage escalation is reachable again
    warns = [r for r in caplog.records
             if r.name == _WS_LOGGER and r.levelno == logging.WARNING]
    assert len(warns) == 2                        # attempts 3 and 4; PRE-FIX: 0


def test_a_connection_that_stays_up_resets_the_backoff_ladder(monkeypatch):
    """The reset is not deleted, only MOVED: a link that survives past
    `stable_after_s` (one ping interval by default) is a genuine recovery
    and returns the ladder to its base delay."""
    ws = _ws(ping_interval=20.0)
    #        c1    c2    c3(stable)  c4    c5
    ctl = _WsCtl(ws, max_connects=6, up_for_seq=[0.5, 0.5, 30.0, 0.5, 0.5],
                 error=OSError("reset"))
    ws._now = ctl.now

    delays = _drive(monkeypatch, ws, ctl)

    #                     c3 survived 30s >= 20s -> back to base
    assert delays == [1.0, 2.0, 1.0, 2.0, 4.0]
    # PRE-FIX: [1.0, 1.0, 1.0, 1.0, 1.0] — indistinguishable from a healthy
    # link, which is exactly why the escalation never happened.


def test_stable_after_s_defaults_to_the_ping_interval_and_is_liftable():
    # behavior-preserving default (derived from an existing knob), and the
    # config key is honored when present
    assert _ws(ping_interval=20.0).stable_after_s == 20.0
    assert _ws(ping_interval=20.0, stable_after_s=45.0).stable_after_s == 45.0
    assert WebSocketFeedManager({}).stable_connect_s is None
    assert WebSocketFeedManager(
        {"stable_connect_sec": 45.0}).stable_connect_s == 45.0


# =========================================================================
# M4 — ContextFeed poll cluster must not stall the engine thread
# =========================================================================

_URLS = {"fred_dff": "https://x.test/dff",
         "fred_t10y2y": "https://x.test/t10y2y",
         "fred_vix": "https://x.test/vix",
         "cot_finfut": "https://x.test/cot",
         "stablecoins": "https://x.test/stable"}


def _fred_csv(value: float) -> str:
    return f"DATE,X\n2026-01-01,{value}\n"


def _cot_row(long_: float, short_: float) -> str:
    fields = (['"BITCOIN - CHICAGO MERCANTILE EXCHANGE"'] +
              [str(i) for i in range(1, 14)] +
              [str(long_), str(short_)] + ["x"] * 71)
    return ",".join(fields) + "\n"


def _stable_json(total: float) -> str:
    return json.dumps({"peggedAssets": [{"circulating":
                                         {"peggedUSD": total}}]})


def _responses() -> dict:
    return {_URLS["fred_dff"]: _fred_csv(0.25),
            _URLS["fred_t10y2y"]: _fred_csv(-0.3),
            _URLS["fred_vix"]: _fred_csv(25.0),
            _URLS["cot_finfut"]: _cot_row(4015.0, 11506.0),
            _URLS["stablecoins"]: _stable_json(1.0e11)}


def _ctx_cfg(**overrides) -> dict:
    base = {"enabled": True, "poll_hours": 1.0,
            "next_halving_date": "2028-04-17", "urls": dict(_URLS)}
    base.update(overrides)
    return base


# an instant far from every 2026 FOMC date and CME expiry (mirrors
# tests/test_context_feed.py's anchor) — event mechanics are not the point
_QUIET_NOW = datetime(2026, 7, 24, 12, tzinfo=timezone.utc).timestamp()


class _HangingFetch:
    """Fetcher whose named URLs block until `release` is set (bounded by
    `max_block` so a broken test can never wedge the suite). Models a
    blackholed host: connected, never answering."""

    def __init__(self, release: threading.Event, hang: set,
                 responses: dict, max_block: float = 3.0):
        self.release = release
        self.hang = set(hang)
        self.responses = dict(responses)
        self.max_block = max_block
        self.calls: list = []

    def __call__(self, url: str):
        self.calls.append(url)
        if url in self.hang:
            self.release.wait(self.max_block)
            return None
        return self.responses.get(url)


def _feed(tmp_path: Path, fetch, **cfg) -> ContextFeed:
    cal = tmp_path / "calendar.json"
    cal.write_text(json.dumps({"fomc": ["2026-01-28"]}), encoding="utf-8")
    return ContextFeed(_ctx_cfg(**cfg), fetch=fetch,
                       history_path=str(tmp_path / "ctx.jsonl"),
                       calendar_path=cal)


def test_poll_cluster_is_bounded_by_the_wall_clock_budget(tmp_path):
    """PRE-FIX: five sequential blocking GETs on the engine thread — with
    every host dark the poll floors at 5x the per-request timeout, and for
    all of it `fast_cycle`'s per-position stop loop does not run (there are
    no venue-resident stop orders to cover the gap). POST-FIX: one
    concurrent cluster under a single wall-clock deadline."""
    release = threading.Event()
    fetch = _HangingFetch(release, hang=set(_URLS.values()),
                          responses={}, max_block=3.0)
    feed = _feed(tmp_path, fetch, poll_budget_sec=1.0)
    try:
        t0 = time.monotonic()
        state = feed.maybe_poll(_QUIET_NOW)
        elapsed = time.monotonic() - t0
    finally:
        release.set()                     # let the workers exit immediately

    # PRE-FIX: ~15s (5 x 3s, serially). POST-FIX: ~1s, the whole budget.
    assert elapsed < 2.5, f"poll cluster took {elapsed:.1f}s"
    assert len(fetch.calls) == 5          # every source was still attempted
    # a timed-out source is UNAVAILABLE, never fabricated
    assert state.stress is None and state.stress_known is False


def test_budget_timeout_degrades_exactly_like_a_failed_fetch(tmp_path):
    """A source that misses the deadline must take the ordinary
    failed-fetch disposition — no raise into the engine, the 3x-grace
    classification untouched, and every other source still delivered."""
    release = threading.Event()
    fetch = _HangingFetch(release, hang=set(), responses=_responses(),
                          max_block=3.0)
    feed = _feed(tmp_path, fetch, poll_budget_sec=1.0)
    try:
        feed.maybe_poll(_QUIET_NOW)                    # poll 1: all healthy
        assert feed.status()["sources"]["vix"] is True

        fetch.hang = {_URLS["fred_vix"]}               # vix blackholes
        t0 = time.monotonic()
        s2 = feed.maybe_poll(_QUIET_NOW + 3600.0)      # poll 2, inside grace
        elapsed = time.monotonic() - t0
    finally:
        release.set()

    assert elapsed < 2.5, f"one dark source stalled the poll {elapsed:.1f}s"
    assert s2.stress is None                    # vix missing -> no partial dial
    assert feed.status()["sources"]["vix"] is True      # still inside 3x grace
    # the neighbours are unaffected: flow dials computed from fresh reads
    assert s2.cot_z is not None and s2.stable_wk_pct is not None


def test_slow_source_does_not_delay_the_fast_ones(tmp_path, caplog):
    """One blackholed host must cost the budget, not its own timeout, and
    it is logged with the same shape as any other failed fetch — so CX-010
    still fires only when the grace window lapses (the disposition is
    unchanged; only the wall clock is bounded)."""
    caplog.set_level(logging.WARNING, logger=_CTX_LOGGER)
    release = threading.Event()
    fetch = _HangingFetch(release, hang={_URLS["cot_finfut"]},
                          responses=_responses(), max_block=4.0)
    feed = _feed(tmp_path, fetch, poll_budget_sec=1.0)
    try:
        t0 = time.monotonic()
        s = feed.maybe_poll(_QUIET_NOW)
        elapsed = time.monotonic() - t0
    finally:
        release.set()

    assert elapsed < 2.5, f"one dark source stalled the poll {elapsed:.1f}s"
    assert s.stress is not None                  # the three FRED reads landed
    assert s.cot_z is None                       # the dark one did not
    assert any("cot" in r.message and "fetch failed" in r.message
               for r in caplog.records)


def test_default_fetch_uses_a_connect_read_timeout_pair(monkeypatch,
                                                        tmp_path):
    """PRE-FIX: a single 10s scalar, which requests applies to EACH phase —
    a blackholed host burns the full budget on connect alone. The pair is a
    lifted knob; the module default keeps a bare call working."""
    seen = {}

    class _Resp:
        text = "payload"

        def raise_for_status(self):
            return None

    class _Requests:
        @staticmethod
        def get(url, headers=None, timeout=None):
            seen["timeout"] = timeout
            return _Resp()

    import data.context_engine as ce
    monkeypatch.setattr(ce, "requests", _Requests)

    assert ce._default_fetch("https://x.test/a") == "payload"
    assert seen["timeout"] == (3.0, 5.0)          # PRE-FIX: 10.0

    # and the configured values are what actually reach the wire
    feed = ContextFeed({"enabled": True, "poll_hours": 1.0,
                        "fetch_connect_timeout_sec": 1.5,
                        "fetch_read_timeout_sec": 2.5},
                       history_path=str(tmp_path / "ctx.jsonl"))
    feed.fetch("https://x.test/b")
    assert seen["timeout"] == (1.5, 2.5)


# =========================================================================
# LOW — CCXTFeed funding: DL-11 unavailable-is-not-zero
# =========================================================================

class _SpotExchange:
    """ccxt client for a spot venue: no funding endpoint at all."""
    has = {"fetchFundingRate": False}

    def fetch_order_book(self, symbol, limit=20):
        return {"bids": [[100.0, 1.0]], "asks": [[100.5, 1.0]]}

    def fetch_ohlcv(self, symbol, timeframe="5m", limit=200):
        return [[1_000_000 + i * 300_000, 100.0, 101.0, 99.0, 100.5, 50.0]
                for i in range(40)]

    def fetch_ticker(self, symbol):
        return {"quoteVolume": 1_000.0}


class _PerpExchange(_SpotExchange):
    has = {"fetchFundingRate": True}

    def __init__(self, payload=None, boom=False):
        self._payload = payload
        self._boom = boom

    def fetch_funding_rate(self, symbol):
        if self._boom:
            raise RuntimeError("funding endpoint 503")
        return self._payload


def _one_payload(client, symbol="ETH/USDT"):
    return CCXTFeed({"symbols": [symbol]},
                    client=client).get_market_data()[symbol]


def test_spot_venue_funding_is_unavailable_not_zero():
    # PRE-FIX: 0.0 — indistinguishable from a real 0% print
    assert _one_payload(_SpotExchange())["funding_rate"] is None


def test_funding_fetch_failure_is_unavailable_not_zero():
    p = _one_payload(_PerpExchange(boom=True), symbol="ETH/USDT:USDT")
    assert p["funding_rate"] is None              # PRE-FIX: 0.0
    assert p["order_book"]["bids"]                # rest of the payload survives


@pytest.mark.parametrize("payload", [None, {}, {"fundingRate": None},
                                     {"fundingRate": "not-a-number"},
                                     {"fundingRate": float("nan")}])
def test_unparsable_funding_is_unavailable_not_zero(payload):
    # DL-11 applies to a garbage/missing FIELD too, not just a dead call —
    # safe_float's 0.0 default was the second fabrication site
    p = _one_payload(_PerpExchange(payload=payload), symbol="ETH/USDT:USDT")
    assert p["funding_rate"] is None              # PRE-FIX: 0.0


def test_a_genuine_zero_funding_print_is_preserved():
    # the point of the fix is DISTINGUISHING these two, so 0.0 must still
    # come through as 0.0 when the venue really said 0.0
    p = _one_payload(_PerpExchange(payload={"fundingRate": 0.0}),
                     symbol="ETH/USDT:USDT")
    assert p["funding_rate"] == 0.0
    assert p["funding_rate"] is not None


def test_a_real_funding_rate_still_passes_through():
    p = _one_payload(_PerpExchange(payload={"fundingRate": 0.0001}),
                     symbol="ETH/USDT:USDT")
    assert p["funding_rate"] == 0.0001


def test_unavailable_ccxt_funding_no_longer_dilutes_the_merged_average():
    """The verified mechanism (the claimed signal-gate flip was refuted):
    `liquidity_model.build_view` AVERAGES every source whose funding_rate
    is not None, so one fabricated 0.0 halves a real print — pulling a
    genuine 0.012 under the 0.01 funding veto. Driven through the REAL
    CCXTFeed and the REAL build_view, not a hand-built payload."""
    ccxt_payload = CCXTFeed({"symbols": ["ETH/USDT"]},
                            client=_SpotExchange()).get_market_data()
    okx_payload = {"ETH-USDT-SWAP": {
        "order_book": {"bids": [[100.0, 1.0]], "asks": [[100.5, 1.0]]},
        "candles": [], "funding_rate": 0.012, "volume_24h": 1.0}}

    view = LiquidityModel({}).build_view(okx_payload, ccxt_payload,
                                         now=_QUIET_NOW)

    assert view["ETH"]["funding_available"] is True
    # PRE-FIX: (0.012 + 0.0) / 2 == 0.006 — under the 0.01 veto threshold
    assert view["ETH"]["funding_rate"] == pytest.approx(0.012)
