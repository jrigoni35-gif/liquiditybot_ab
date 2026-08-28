"""
data/ws_feed.py — push-based market data over websockets.

The REST feeds (data/_http.ThrottledRestClient subclasses) pull a fresh
order book every slow cycle (~5s), during which stops run on data that
is up to a cycle old. This module streams venue order-book snapshots
into a thread-safe in-memory cache; the existing synchronous
`get_order_book(symbol)` accessors read from that cache when it is
FRESH and fall back to REST when the socket is stale, absent, or the
`websockets` package is not installed. Net effect: sub-second book
freshness with the REST path as an always-available safety net.

Design contract (matches the rest of the data layer):
  * FAIL-SAFE. A dropped connection, a garbage frame, or a missing
    optional dependency degrades to "no cached book" -> REST fallback.
    Nothing here ever raises into the engine.
  * STALENESS-GATED. A cached book older than `max_age_s` is treated as
    absent, so a silently-dead socket can never feed stale depth to the
    firewall or stop logic (same discipline as the venue watchdog).
  * OPTIONAL. `websockets` is not in requirements.txt floors; if it is
    absent the manager still constructs, `.start()` is a no-op, and the
    bot runs exactly as it does today on REST.
  * READ-ONLY. Public market-data streams only. No auth, no order
    entry, no venue on which this could place risk. Kraken execution
    stays exclusively on the hardened REST order path.

The websocket transport runs its own asyncio loop on a daemon thread;
the engine never awaits. Cache reads are plain locked dict lookups.
"""

import json
import logging
import threading
import time
import zlib
from typing import Callable, Optional

from core.sanitize import clean_book

log = logging.getLogger("liquiditybot.data.ws")

# Binance.US partial-depth snapshot stream: each frame is a COMPLETE
# top-N book, so no local diff-merge / sequence-resync bookkeeping (the
# classic source of order-book desync bugs). 100ms cadence.
_BINANCEUS_WS_BASE = "wss://stream.binance.us:9443/stream"

# Kraken v2 public book channel: one snapshot per (re)subscribe then
# incremental updates. Unlike Binance's full-frame stream this needs local
# book maintenance (see KrakenV2BookStream), but a reconnect re-subscribes
# and Kraken resends a snapshot that RESETS state, so drift self-heals.
_KRAKEN_WS_V2 = "wss://ws.kraken.com/v2"


class LiveMarketCache:
    """Thread-safe latest-snapshot store, keyed by (venue, symbol).

    Writers are websocket handler threads; readers are the engine's slow
    cycle. Every read is staleness-gated and re-sanitized through
    clean_book, so a consumer of this cache gets exactly the same shape
    and guarantees as a fresh REST `get_order_book`."""

    def __init__(self, now: Callable[[], float] = time.time):
        self._now = now
        self._lock = threading.Lock()
        self._books: dict = {}      # (venue, symbol) -> (bids, asks, ts)
        self._marks: dict = {}      # (venue, symbol) -> (price, ts)

    def update_book(self, venue: str, symbol: str, bids: list, asks: list):
        """Store the latest book snapshot + a lockstep mid mark (writer:
        the websocket handler thread)."""
        ts = self._now()
        with self._lock:
            self._books[(venue, symbol)] = (bids, asks, ts)
            # keep a mark in lockstep with the book: mid of best levels
            try:
                mid = (float(bids[0][0]) + float(asks[0][0])) / 2.0
                if mid > 0:
                    self._marks[(venue, symbol)] = (mid, ts)
            except (IndexError, TypeError, ValueError):
                pass

    def update_trade(self, venue: str, symbol: str, price: float):
        """Store a last-trade mark; non-positive/garbage prices are dropped
        (writer: the websocket handler thread)."""
        ts = self._now()
        try:
            px = float(price)
        except (TypeError, ValueError):
            return
        if px <= 0:
            return
        with self._lock:
            self._marks[(venue, symbol)] = (px, ts)

    def get_book(self, venue: str, symbol: str,
                 max_age_s: float) -> Optional[dict]:
        """Sanitized (clean_book) snapshot no older than max_age_s, else
        None - missing and stale are indistinguishable BY DESIGN so the
        caller always falls back to REST (reader: engine thread)."""
        with self._lock:
            entry = self._books.get((venue, symbol))
        if entry is None:
            return None
        bids, asks, ts = entry
        if self._now() - ts > max_age_s:
            return None                      # stale -> caller falls back
        return clean_book({"bids": bids, "asks": asks})

    def get_mark(self, venue: str, symbol: str,
                 max_age_s: float) -> Optional[float]:
        """Latest mark no older than max_age_s, else None (reader: engine
        thread)."""
        with self._lock:
            entry = self._marks.get((venue, symbol))
        if entry is None:
            return None
        px, ts = entry
        if self._now() - ts > max_age_s:
            return None
        return px

    def invalidate(self, venue: str, symbol: str) -> None:
        """Drop the cached book + mark for (venue, symbol) so the next read
        is a cache miss -> caller falls back to REST (writer: websocket
        handler thread, e.g. on a Kraken checksum mismatch that means local
        state can no longer be trusted until it resyncs)."""
        with self._lock:
            self._books.pop((venue, symbol), None)
            self._marks.pop((venue, symbol), None)

    def age(self, venue: str, symbol: str) -> Optional[float]:
        """Seconds since the last book write, or None if never written."""
        with self._lock:
            entry = self._books.get((venue, symbol))
        return None if entry is None else self._now() - entry[2]

    def book_ts(self, venue: str, symbol: str) -> Optional[float]:
        """RAW wall timestamp of the last book write (owed 42a), or None
        if never written. The stored stamp itself, not an age - the
        manager attaches it to served books as recv_ts so the engine's
        book_ts records DATA time, never look time."""
        with self._lock:
            entry = self._books.get((venue, symbol))
        return None if entry is None else float(entry[2])

    def stats(self) -> dict:
        """Entry counts ({books, marks}) for health/telemetry payloads."""
        with self._lock:
            return {"books": len(self._books), "marks": len(self._marks)}


def _backoff_delay(attempt: int, base: float, cap: float,
                   jitter: float) -> float:
    """Exponential backoff with a hard cap and additive jitter. Pure and
    deterministic under an injected jitter value, so the reconnect
    schedule is unit-testable without sleeping or opening a socket."""
    raw = base * (2 ** max(attempt, 0))
    return min(raw, cap) + max(jitter, 0.0)


class ResilientWebSocket:
    """Generic reconnecting websocket reader on a daemon asyncio thread.

    Owns nothing venue-specific: it connects to `url`, optionally sends
    `subscribe`, and hands every text frame to `on_message`. Reconnects
    with capped exponential backoff forever until `stop()` — including
    after a venue-side NORMAL close, which the `websockets` iterator
    reports as a clean end-of-stream rather than an exception (W2-H8a).
    The `websockets` dependency is imported lazily so the whole module is
    importable (and testable) without it installed."""

    def __init__(self, url: str, on_message: Callable[[str], None],
                 subscribe: Optional[str] = None,
                 backoff_base: float = 1.0, backoff_cap: float = 30.0,
                 ping_interval: float = 20.0,
                 rng: Optional[Callable[[], float]] = None,
                 stable_after_s: Optional[float] = None,
                 now: Callable[[], float] = time.monotonic):
        self.url = url
        self.on_message = on_message
        self.subscribe = subscribe
        self.backoff_base = backoff_base
        self.backoff_cap = backoff_cap
        self.ping_interval = ping_interval
        # W2-H8(b): how long a connection must SURVIVE before it counts as a
        # recovery that resets the backoff ladder. Defaults to one
        # `ping_interval` - the shortest interval over which the transport
        # itself proves liveness by exchanging a keepalive - so it is derived
        # from an existing knob rather than a fresh fitted literal. Injectable
        # clock (monotonic) follows KrakenV2BookStream's convention below:
        # sidecar/data code, no engine replay/injected-`now` discipline.
        self.stable_after_s = (float(ping_interval) if stable_after_s is None
                               else max(float(stable_after_s), 0.0))
        self._now = now
        import random
        # jitter only decorrelates reconnect storms across clients; it
        # guards no secret, so the non-crypto PRNG is the right tool
        self._rng = rng or (lambda: random.uniform(0.0, 1.0))  # nosec B311
        self._stop = threading.Event()
        self._resync = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.connected = False
        self.reconnects = 0

    @staticmethod
    def available() -> bool:
        """True when the optional `websockets` package is importable."""
        try:
            import websockets  # type: ignore[import-not-found]  # noqa: F401  # optional dep; absence = feature off
            return True
        except Exception:
            return False

    def start(self):
        """Launch the reader daemon thread (idempotent; no-op without the
        websockets package - REST fallback stays in effect)."""
        if not self.available():
            log.warning("websockets package absent - live stream disabled, "
                        "REST fallback remains in effect")
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run_loop, name="ws-feed", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0):
        """Signal the reader to exit and join it (bounded wait); safe to
        call from any thread, any number of times."""
        self._stop.set()
        t = self._thread
        if t and t.is_alive():
            t.join(timeout=timeout)
        self.connected = False

    def request_reconnect(self):
        """Ask the reader to drop the current connection and reconnect
        immediately (no backoff) - the existing connect/subscribe flow then
        re-sends `subscribe` fresh, which is exactly how a caller (e.g. a
        Kraken checksum-mismatch resync) asks for a clean resubscribe
        without a parallel protocol path. Safe from any thread; a no-op if
        not currently connected (the next connect subscribes anyway)."""
        self._resync.set()

    def _run_loop(self):
        import asyncio
        try:
            asyncio.run(self._reader())
        except Exception:
            log.debug("ws reader loop exited", exc_info=True)
        finally:
            self.connected = False

    async def _reader(self):
        import asyncio

        import websockets  # type: ignore[import-not-found]  # optional dep; start() is gated on available()
        attempt = 0
        while not self._stop.is_set():
            # W2-H8(a): did WE end this connection (stop / resync), or did the
            # peer? Only the latter is a disconnect that owes backoff.
            intentional = False
            up_since: Optional[float] = None
            try:
                async with websockets.connect(
                        self.url, ping_interval=self.ping_interval,
                        ping_timeout=self.ping_interval,
                        open_timeout=10, close_timeout=5) as ws:
                    self.connected = True
                    # W2-H8(b): stamp WHEN we connected instead of resetting
                    # `attempt` here. Resetting on CONNECT meant a venue that
                    # accepts the handshake and drops it a moment later pinned
                    # every retry at attempt 0 (1-2s): the exponential ladder
                    # and its cap were unreachable and the attempt>=3 WARNING
                    # escalation could never fire, so a sustained flap read as
                    # a string of unrelated blips. The reset now lives in the
                    # except branch, gated on the connection having STAYED up.
                    up_since = self._now()
                    if self.subscribe:
                        await ws.send(self.subscribe)
                    async for raw in ws:
                        if self._stop.is_set():
                            intentional = True
                            break
                        try:
                            self.on_message(
                                raw if isinstance(raw, str)
                                else raw.decode("utf-8", "replace"))
                        except Exception:
                            log.debug("ws frame handler error - skipped",
                                      exc_info=True)
                        if self._resync.is_set():
                            self._resync.clear()
                            intentional = True
                            log.info("ws resubscribe requested - "
                                     "reconnecting now")
                            break
                self.connected = False
                # W2-H8(a): `Connection.__aiter__` (websockets >= 14) swallows
                # ConnectionClosedOK and simply returns, so a venue-side NORMAL
                # close (1000/1001/1005 - maintenance, graceful drain, a proxy
                # that closes without a status) leaves this `async with` with NO
                # exception. That bypassed the whole except branch: no sleep at
                # all (measured 310 reconnects/s against the execution venue's
                # ws), `reconnects` frozen at 0 and `connected` stuck True, so
                # health() -> status.json -> Grafana reported the outage as
                # healthy. Re-raise it as the disconnect it is, so ONE branch
                # owns backoff + telemetry for every non-deliberate close.
                if not intentional and not self._stop.is_set():
                    raise ConnectionError("closed normally by peer")
            except Exception as e:
                self.connected = False
                if self._stop.is_set():
                    break
                # W2-H8(b): only a connection that actually SURVIVED counts as
                # the "clean connect" that clears the ladder; anything shorter
                # is part of the same ongoing outage and must keep escalating.
                if up_since is not None and \
                        self._now() - up_since >= self.stable_after_s:
                    attempt = 0
                self.reconnects += 1
                delay = _backoff_delay(attempt, self.backoff_base,
                                       self.backoff_cap, self._rng())
                attempt += 1
                # a single reconnect is transient and self-healing (attempt
                # resets to 0 once a connection STAYS up past stable_after_s);
                # only a SUSTAINED outage that is not recovering (>=3
                # consecutive failures) is an incident worth WARNING - below
                # that it stays INFO, off the incidents stream, so a momentary
                # blip does not read as a fault.
                lvl = logging.WARNING if attempt >= 3 else logging.INFO
                log.log(lvl, "ws disconnect (%s); reconnecting in %.1fs "
                        "(attempt %d)", e, delay, attempt)
                try:
                    await asyncio.wait_for(
                        _stoppable_sleep(self._stop, delay), timeout=delay + 1)
                except Exception:
                    log.debug("ws backoff sleep interrupted", exc_info=True)


async def _stoppable_sleep(stop_event: threading.Event, delay: float):
    """Sleep that wakes early if stop is signalled, so shutdown is prompt
    even mid-backoff."""
    import asyncio
    step = 0.1
    waited = 0.0
    while waited < delay and not stop_event.is_set():
        await asyncio.sleep(step)
        waited += step


class BinanceUSDepthStream:
    """Venue adapter: builds the Binance.US combined partial-depth stream
    URL for a symbol set and parses its frames into a LiveMarketCache.

    Symbols arrive in the feed's format (e.g. 'BTCUSD'); Binance stream
    paths are lowercase concatenated ('btcusd'). The reverse map restores
    the caller's exact symbol string on the cache key so a cache read
    lines up with the matching REST `get_order_book(symbol)`."""

    VENUE = "binanceus"

    def __init__(self, symbols: list, cache: LiveMarketCache,
                 depth: int = 20, interval_ms: int = 100):
        self.cache = cache
        self._symbols = list(symbols)
        self._to_venue = {s: s.lower() for s in self._symbols}
        self._from_venue = {v: s for s, v in self._to_venue.items()}
        self.depth = depth
        self.interval_ms = interval_ms

    def stream_url(self) -> str:
        """Combined partial-depth stream URL for every configured symbol."""
        parts = [f"{v}@depth{self.depth}@{self.interval_ms}ms"
                 for v in self._to_venue.values()]
        return f"{_BINANCEUS_WS_BASE}?streams={'/'.join(parts)}"

    # uniform adapter interface (see WebSocketFeedManager): Binance encodes
    # its subscription in the URL, so there is no post-connect subscribe frame
    def url(self) -> str:
        """Adapter interface: the connect URL (carries the subscription)."""
        return self.stream_url()

    def subscribe_msg(self) -> Optional[str]:
        """Adapter interface: None - Binance subscribes via the URL."""
        return None

    def handle(self, text: str):
        """Parse one combined-stream frame into a book update. Never
        raises: a malformed frame is dropped, the cache keeps its last
        good snapshot until staleness expires it."""
        try:
            msg = json.loads(text)
        except (ValueError, TypeError):
            return
        stream = msg.get("stream", "") if isinstance(msg, dict) else ""
        data = msg.get("data") if isinstance(msg, dict) else None
        if not isinstance(data, dict):
            return
        venue_sym = stream.split("@", 1)[0]
        symbol = self._from_venue.get(venue_sym)
        if symbol is None:
            return
        bids = data.get("bids") or data.get("b") or []
        asks = data.get("asks") or data.get("a") or []
        if not bids or not asks:
            return
        self.cache.update_book(self.VENUE, symbol, bids, asks)


def _kraken_ck_token(raw) -> str:
    """One price/qty value formatted for Kraken's v2 checksum: the exact
    wire digit string with the decimal point removed and leading zeros
    stripped (e.g. "0.00100000" -> "000100000" -> "100000")."""
    s = raw if isinstance(raw, str) else str(raw)
    s = s.replace(".", "").lstrip("0")
    return s or "0"


class KrakenV2BookStream:
    """Venue adapter: Kraken v2 public `book` channel -> LiveMarketCache.

    Kraken streams an INCREMENTAL book: one `snapshot` frame per
    (re)subscribe carrying the full top-N, then `update` frames carrying
    only changed levels (qty>0 sets/replaces a level, qty==0 removes it).
    We keep the book per symbol and republish the top-N levels keyed by the
    caller's Kraken REST *pair* (e.g. 'BTCUSD'), so a cache read lines up
    with get_order_book(pair) exactly like the Binance adapter's symbol key.

    Checksum-verified: every frame that carries Kraken's CRC32 `checksum`
    (top-10-per-side, price+qty with the decimal point and leading zeros
    stripped, asks-then-bids, per Kraken's v2 spec) is checked against the
    freshly-applied local book after every snapshot/update. Ordered,
    lossless websocket delivery keeps the two in sync in the common case,
    but a self-inflicted gap (e.g. one unparseable level in a frame being
    skipped while the rest of the frame still applies) can silently drift
    local state without ever tripping the staleness gate - the cache
    timestamp keeps refreshing even though the book itself is wrong. A
    checksum mismatch is treated as exactly that: local state for the
    symbol is dropped, the published cache entry is invalidated (forcing
    REST fallback), and a resubscribe is requested (reusing
    ResilientWebSocket's own reconnect -> subscribe flow - Kraken answers a
    fresh subscribe with a new `snapshot`, which resets local state, same
    as the natural reconnect path). Frames without a `checksum` field, and
    frames while `depth` < 10 (too few retained levels to reconstruct
    Kraken's top-10 checksum window), skip verification - never treated as
    a mismatch. Reads are still staleness-gated and clean_book-sanitised on
    top of this, so a crossed/degenerate book degrades to None -> REST,
    same as every other cache read.

    READ-ONLY public market data. Kraken execution stays exclusively on the
    hardened REST order path (invariant 3)."""

    VENUE = "kraken"

    def __init__(self, sym_to_pair: dict, cache: LiveMarketCache,
                 depth: int = 10,
                 ck_backoff_base_s: float = 1.0,
                 ck_backoff_cap_s: float = 60.0,
                 now: Callable[[], float] = time.monotonic):
        self.cache = cache
        # v2 symbol ('BTC/USD') -> cache key = Kraken REST pair ('BTCUSD')
        self.sym_to_pair = dict(sym_to_pair or {})
        self._symbols = list(self.sym_to_pair.keys())
        self.depth = max(int(depth), 1)
        # v2 symbol -> {'bids': {price: (price_raw, qty_raw)}, 'asks': {...}}
        # price is the float dict key (math/sort/dedup); price_raw/qty_raw
        # are the EXACT wire strings (see handle()'s parse_float=str) so the
        # checksum can be reconstructed byte-for-byte against Kraken's own
        # pair-precision formatting without needing pair-precision metadata.
        self._state: dict = {}
        # telemetry: count of checksum mismatches observed (desync events)
        self.checksum_failures = 0
        # wired by WebSocketFeedManager.start() to ResilientWebSocket's
        # request_reconnect - left None (no-op) when used standalone/tested
        self.request_resubscribe: Optional[Callable[[], None]] = None
        # W2-28: consecutive checksum-mismatch backoff on the RESUBSCRIBE
        # REQUEST itself only - never on data correctness. A mismatch still
        # drops local state + invalidates the cache on EVERY occurrence
        # (forcing an instant REST fallback read); only how often we
        # actually ASK for a resubscribe is paced. Derivation: this is
        # read-only public market data (invariant 3) and REST fail-over
        # already keeps books flowing through any gap, so a systematic
        # mismatch (e.g. a persistently malformed venue frame) would
        # otherwise churn reconnects at zero delay forever for no
        # corresponding gain in data availability - doubling 1s -> 60s
        # bounds that churn while a one-off transient mismatch still
        # resyncs promptly (first mismatch always fires immediately).
        # Monotonic clock (injectable for tests): this is sidecar/data
        # code, not the engine - no replay/injected-`now` discipline
        # applies here, only the file's own reconnect-timing convention
        # (see _backoff_delay above).
        self._ck_backoff_base_s = max(float(ck_backoff_base_s), 0.01)
        self._ck_backoff_cap_s = max(float(ck_backoff_cap_s),
                                     self._ck_backoff_base_s)
        self._ck_fail_streak = 0        # consecutive fired requests
        self._ck_next_resub_ok_ts = 0.0  # gate open until real time clears this
        self._ck_now = now

    def url(self) -> str:
        """Adapter interface: the Kraken v2 public websocket URL."""
        return _KRAKEN_WS_V2

    def subscribe_msg(self) -> Optional[str]:
        """Adapter interface: the post-connect `book` subscribe frame
        (None with no symbols configured)."""
        if not self._symbols:
            return None
        return json.dumps({"method": "subscribe", "params": {
            "channel": "book", "symbol": self._symbols, "depth": self.depth}})

    def _trim(self, st: dict) -> None:
        """Bound each side to the top-`depth` levels (bids highest, asks
        lowest). A depth-N channel need not send a qty=0 remove for a level
        merely PUSHED OUT of the window by a better price, so without this
        the state would grow unbounded AND a stale out-of-window level could
        later resurface as a phantom best bid/ask. Trimming to depth after
        every frame makes local state == Kraken's canonical top-N book."""
        for side, best_first in (("bids", True), ("asks", False)):
            book = st[side]
            if len(book) > self.depth:
                keep = sorted(book, reverse=best_first)[:self.depth]
                st[side] = {p: book[p] for p in keep}

    def _publish(self, sym: str):
        st = self._state.get(sym)
        pair = self.sym_to_pair.get(sym)
        if not st or pair is None:
            return
        # top-N: bids highest-first, asks lowest-first (matches REST shape)
        bids = sorted(st["bids"].items(), reverse=True)[:self.depth]
        asks = sorted(st["asks"].items())[:self.depth]
        if not bids or not asks:
            return
        self.cache.update_book(
            self.VENUE, pair,
            [[p, float(raw[1])] for p, raw in bids],
            [[p, float(raw[1])] for p, raw in asks])

    def handle(self, text: str):
        """Apply one book frame. Never raises: a malformed frame is dropped
        and the cache keeps its last good snapshot until staleness expires.

        Parses with `parse_float=str`: Kraken sends price/qty as bare JSON
        numbers (not strings), formatted wire-side to each pair's exact
        decimal precision (e.g. qty "0.00100000") - a plain `json.loads`
        collapses that through a Python float and loses the trailing
        zeros/precision the checksum needs, so the raw digit string is
        captured here, before any float conversion."""
        try:
            msg = json.loads(text, parse_float=str)
        except (ValueError, TypeError):
            return
        if not isinstance(msg, dict) or msg.get("channel") != "book":
            return
        typ = msg.get("type")
        data = msg.get("data")
        if not isinstance(data, list):
            return
        for d in data:
            if not isinstance(d, dict):
                continue
            sym = d.get("symbol")
            # `is None` first: sym_to_pair keys are str, so a missing symbol
            # field could never match anyway - the explicit check narrows
            # the type for the _publish(sym) call below
            if sym is None or sym not in self.sym_to_pair:
                continue
            st = self._state.setdefault(sym, {"bids": {}, "asks": {}})
            if typ == "snapshot":                 # (re)subscribe: hard reset
                st["bids"].clear()
                st["asks"].clear()
            for side in ("bids", "asks"):
                book_side = st[side]
                for lvl in d.get(side) or []:
                    try:
                        # price is the dict key: Kraken echoes each level's
                        # price string identically between set and its later
                        # qty=0 delete, so the float round-trip matches for
                        # pop(); staleness + reconnect-snapshot + checksum
                        # verification bound any drift
                        price_raw = lvl["price"]
                        qty_raw = lvl["qty"]
                        px = float(price_raw)
                        qty = float(qty_raw)
                    except (KeyError, TypeError, ValueError):
                        continue
                    if qty <= 0.0:
                        book_side.pop(px, None)   # qty 0 removes the level
                    else:
                        book_side[px] = (price_raw, qty_raw)
            self._trim(st)                        # bound to top-N (no phantoms)
            # VERIFY BEFORE PUBLISH (round-2 finding 2026-08-05). This ran
            # publish-then-verify, so a book that FAILS its checksum was
            # already in the live cache with a fresh timestamp before being
            # invalidated microseconds later. During the resubscribe backoff
            # after a mismatch, every update frame rebuilt a book from empty
            # state and republished it: as soon as both sides had one level,
            # a phantom 1-5-level book was served to the stop/imbalance
            # logic (main.fast_cycle reads this cache concurrently) stamped
            # as fresh. Verifying first means a bad book never becomes
            # readable at all - the cache keeps the last GOOD book and its
            # honest age, which the staleness guards already handle.
            if self._verify_checksum(sym, st, d.get("checksum")):
                self._publish(sym)

    def _checksum(self, st: dict) -> int:
        """Kraken v2 book checksum: top-10 asks ascending then top-10 bids
        descending, each level as price-then-qty with the decimal point and
        any leading zeros stripped, all concatenated and CRC32'd (unsigned).
        Verified byte-for-byte against Kraken's own published worked example
        (see tests)."""
        asks = sorted(st["asks"].items())[:10]
        bids = sorted(st["bids"].items(), reverse=True)[:10]
        parts = []
        for _, (price_raw, qty_raw) in asks:
            parts.append(_kraken_ck_token(price_raw))
            parts.append(_kraken_ck_token(qty_raw))
        for _, (price_raw, qty_raw) in bids:
            parts.append(_kraken_ck_token(price_raw))
            parts.append(_kraken_ck_token(qty_raw))
        return zlib.crc32("".join(parts).encode("ascii"))

    def _verify_checksum(self, sym: str, st: dict, expected) -> bool:
        """Validate the frame's `checksum` (if present) against the local
        book just applied. Returns True when the book is SAFE TO PUBLISH -
        verified, or unverifiable by contract (no checksum on the frame, or
        depth < 10) - and False on a real mismatch. The caller publishes
        only on True, so a desynced book never becomes readable (round-2
        finding: publish-then-verify briefly served a phantom book stamped
        fresh, and during the resubscribe backoff it did so on every frame).

        A mismatch means local state has desynced from
        Kraken's real book (e.g. a skipped unparseable level) - the failure
        is silent otherwise, since the cache timestamp keeps refreshing and
        the staleness gate never fires on a drifted-but-plausible book.

        On mismatch: drop local state for the symbol, invalidate the
        published cache entry (forces REST fallback until resynced), and
        request a resubscribe (reuses ResilientWebSocket's own
        reconnect -> subscribe flow; Kraken answers a fresh subscribe with a
        `snapshot`, which resets state exactly like a natural reconnect).

        Skipped (never a mismatch) when: no checksum on the frame, or
        `depth` < 10 - too few retained levels to reconstruct Kraken's
        top-10 checksum window, so any comparison would be meaningless.

        W2-28: the resubscribe REQUEST (not the state-drop/cache-
        invalidate above it) is paced by a consecutive-failure backoff -
        see __init__'s derivation. A clean verified frame (this method's
        early return below) resets that backoff entirely."""
        if expected is None or self.depth < 10:
            return True          # unverifiable by contract: publish as before
        try:
            expected_int = int(expected)
        except (TypeError, ValueError):
            return True
        if self._checksum(st) == expected_int:
            # clean verified frame: only a SUSTAINED (consecutive) desync
            # escalates the resubscribe backoff, so recovery resets it
            self._ck_fail_streak = 0
            self._ck_next_resub_ok_ts = 0.0
            return True
        self.checksum_failures += 1
        pair = self.sym_to_pair.get(sym)
        log.warning(
            "kraken book checksum mismatch for %s (pair %s) - local book "
            "desynced, dropping state + cache, requesting resubscribe",
            sym, pair)
        self._state.pop(sym, None)
        if pair is not None:
            self.cache.invalidate(self.VENUE, pair)
        if self.request_resubscribe is not None:
            now_ts = self._ck_now()
            if now_ts >= self._ck_next_resub_ok_ts:
                self.request_resubscribe()
                self._ck_next_resub_ok_ts = now_ts + _backoff_delay(
                    self._ck_fail_streak, self._ck_backoff_base_s,
                    self._ck_backoff_cap_s, 0.0)
                self._ck_fail_streak += 1
            else:
                log.info(
                    "kraken checksum mismatch resubscribe suppressed for "
                    "%s - backoff active (%.1fs remaining)",
                    sym, self._ck_next_resub_ok_ts - now_ts)
        return False             # desynced: the caller must NOT publish


class WebSocketFeedManager:
    """Owns one venue's live stream: cache + adapter + resilient socket,
    plus REST-fallback accessors the engine can call synchronously.

    Venue-agnostic: it drives any adapter exposing url() / subscribe_msg() /
    handle() / VENUE. Ships adapters for Binance.US (URL-encoded depth
    stream) and Kraken v2 (post-connect book subscribe). Pass `adapter` to
    select one; the default builds Binance.US from config for back-compat."""

    def __init__(self, config: dict, cache: Optional[LiveMarketCache] = None,
                 adapter=None):
        cfg = config or {}
        self.enabled = bool(cfg.get("enabled", False))
        self.max_age_s = float(cfg.get("max_book_age_sec", 2.0))
        # W2-H8(b): lifted knob, absent-key default is IDENTICAL to the
        # derived one (ResilientWebSocket falls back to its ping_interval),
        # so shipping without the key is behavior-preserving.
        raw_stable = cfg.get("stable_connect_sec")
        self.stable_connect_s: Optional[float] = (
            None if raw_stable is None else float(raw_stable))
        self.cache = cache or LiveMarketCache()
        if adapter is not None:
            self.adapter = adapter
            self._symbols = list(getattr(adapter, "_symbols", []) or [])
        else:
            symbols = cfg.get("binanceus_symbols") or []
            self.adapter = BinanceUSDepthStream(
                symbols, self.cache,
                depth=int(cfg.get("depth", 20)),
                interval_ms=int(cfg.get("interval_ms", 100)))
            self._symbols = list(symbols)
        self.venue = self.adapter.VENUE
        self._ws: Optional[ResilientWebSocket] = None

    def start(self):
        """Start the venue stream when enabled and symbols are configured;
        otherwise stay silently on REST."""
        if not self.enabled:
            return
        if not self._symbols:
            log.warning("ws manager enabled but no symbols configured - "
                        "staying on REST")
            return
        self._ws = ResilientWebSocket(self.adapter.url(),
                                      self.adapter.handle,
                                      subscribe=self.adapter.subscribe_msg(),
                                      backoff_cap=float(
                                          self.max_age_s * 15),
                                      stable_after_s=self.stable_connect_s)
        # wire adapter-initiated resync (e.g. Kraken checksum mismatch) to
        # this socket's own reconnect->subscribe flow; adapters without a
        # request_resubscribe hook (Binance.US) are left untouched. setattr
        # (not a plain attribute assignment) since self.adapter's static
        # type spans adapters that don't declare this attribute.
        if hasattr(self.adapter, "request_resubscribe"):
            setattr(self.adapter, "request_resubscribe",  # noqa: B010
                    self._ws.request_reconnect)
        self._ws.start()
        log.info("ws feed started: %s %s", self.venue, self._symbols)

    def stop(self):
        """Stop and discard the underlying socket (idempotent)."""
        if self._ws is not None:
            self._ws.stop()
            self._ws = None

    def get_order_book(self, symbol: str) -> Optional[dict]:
        """Fresh cached book or None (caller falls back to REST). Disabled
        or stale both return None, so the engine's existing REST path is
        the single source of truth whenever live data is not trustworthy.
        `symbol` is whatever key the adapter caches under (Binance symbol /
        Kraken REST pair).

        recv_ts (owed 42a): the cache's RAW write timestamp rides the
        served book, attached HERE (the cache's get_book stays the pure
        2-key clean_book shape its own tests pin) so the engine's book_ts
        records when the DATA arrived, not when it was looked at. Books
        within max_age_s always have a write stamp; the None-guard is
        for an invalidate() racing between the two cache reads."""
        if not self.enabled:
            return None
        book = self.cache.get_book(self.venue, symbol, self.max_age_s)
        if book is not None:
            ts = self.cache.book_ts(self.venue, symbol)
            if ts is not None:
                book["recv_ts"] = ts
        return book

    def get_mark(self, symbol: str) -> Optional[float]:
        """Fresh cached mark or None (disabled/stale both -> None, caller
        falls back to REST)."""
        if not self.enabled:
            return None
        return self.cache.get_mark(self.venue, symbol, self.max_age_s)

    def health(self) -> dict:
        """Status-schema `ws` payload: enabled/connected/reconnects/
        lib_available plus cache entry counts."""
        return {
            "enabled": self.enabled,
            "connected": bool(self._ws and self._ws.connected),
            "reconnects": self._ws.reconnects if self._ws else 0,
            "checksum_failures": getattr(self.adapter,
                                         "checksum_failures", 0),
            "lib_available": ResilientWebSocket.available(),
            **self.cache.stats(),
        }
